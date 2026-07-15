# Bounding "Shipped" on the Board — design

**Date:** 2026-07-14
**Status:** Approved (pending spec review)
**Scope:** `tuckit` (public repo). Neutral product feature — no billing/infra, so it
belongs in the OSS core, not `tuckit-cloud`.

## Problem

`shipped` is the only slice status that grows monotonically. On the Board tab
(`web:roadmap`) the Shipped column (kanban) and Shipped group (list) render
**every** shipped slice, always expanded, sorted by `(area.name, rank)` — so over
time the board becomes a completion archive with no sense of recency. Home's
"Recently shipped" section has the same unbounded behavior when expanded.

## Goal

- The Board shows only **recent** shipped work; the rest is one click away.
- "Recent" is **workspace-configurable** (the user is unsure whether count or a
  time window fits, so support both).
- **No new top-level URL or nav item.** The recent IA reduced the sidebar to
  Home / Inbox / Board and folded lens pages into Home; a bespoke `/shipped/`
  page would fight that. Instead, reuse the Board tab filtered by the slice
  `status` dimension — a first-class field that generalizes to any status.

## Non-goals

- Capping the **per-Area** board (`web:area`, `?view=board`). Single-area, different
  character — out of scope.
- Filtering/archiving `dropped`.
- Pagination of the filtered list (acceptable for now; revisit if a workspace
  ever has thousands of shipped slices).

## Approach summary

1. Two workspace settings bound the Shipped column/group on the default Board
   views: a **mode** (`count` | `days`) and a **limit** (default `count` / `8`).
2. Shipped is re-sorted **newest-first by `completed_at`** everywhere it appears.
3. When the cap hides some, a **`View all shipped (N) →`** link points to
   `web:roadmap?view=list&status=shipped` — the *same* Board tab, list view,
   filtered to a single status, **uncapped**, flat, with Area badges.
4. The `?status=<value>` filter is generic (works for `building`, `planned`, …),
   exposing the slice status dimension rather than a one-off page.
5. Home's "Recently shipped" is capped by the same setting and its "view all"
   link points to the **same** filtered URL.

## Data model — `Workspace`

Add two fields (both with safe defaults; a data migration is unnecessary — the
defaults apply to existing rows):

```python
SHIPPED_BOARD_MODE_CHOICES = [("count", "Count"), ("days", "Days")]
shipped_board_mode  = models.CharField(max_length=5, choices=SHIPPED_BOARD_MODE_CHOICES, default="count")
shipped_board_limit = models.PositiveSmallIntegerField(default=8)
```

- `count` mode → show the `limit` most recent shipped slices.
- `days` mode → show shipped slices with `completed_at` within the last `limit` days.
- Validation (service/view): `limit` clamped to `1..365`; mode must be a valid choice.

## Service layer — `core/services/state.py`

1. **Re-sort shipped by recency.** In `roadmap_state`, the `shipped` bucket sorts
   by `completed_at` desc (fallback `updated_at` desc for legacy rows with null
   `completed_at`). Idea/planned/building buckets keep `(area.name, rank)`.
   `roadmap_state` continues to return the **full** shipped list (used for the
   total count and the filtered/archive view).

2. **New helper** `cap_shipped(workspace, shipped) -> (visible, total)`:
   ```python
   def cap_shipped(workspace, shipped):
       total = len(shipped)
       if workspace.shipped_board_mode == "days":
           cutoff = timezone.now() - timedelta(days=workspace.shipped_board_limit)
           visible = [s for s in shipped if s.completed_at and s.completed_at >= cutoff]
       else:  # count
           visible = shipped[: workspace.shipped_board_limit]
       return visible, total
   ```
   Pure function of an already-fetched list — no extra queries.

3. `roadmap_board_groups(workspace)` builds the kanban tuples using the **capped**
   shipped list (still `idea → planned → building → shipped` order).

## View layer — `web/views/pages.py`

`roadmap(request)` gains a `status` branch:

```python
STATUS_KEYS = {"idea", "planned", "building", "shipped"}

def roadmap(request):
    ws = get_current_workspace(request)
    state = roadmap_state(ws) if ws else {}
    status = request.GET.get("status")

    if status in STATUS_KEYS:
        # Focused single-status flat list — the "view all" / archive surface.
        return render(request, "web/roadmap.html", {
            "filter_status": status,
            "filter_slices": state.get(status, []),   # uncapped
            "show_area": True,
        })

    view = "list" if request.GET.get("view") == "list" else "board"
    visible_shipped, shipped_total = cap_shipped(ws, state.get("shipped", [])) if ws else ([], 0)
    shipped_hidden = shipped_total - len(visible_shipped)
    board_state = {**state, "shipped": visible_shipped}
    return render(request, "web/roadmap.html", {
        "state": board_state,
        "groups": roadmap_board_groups_from(board_state),  # tuples from capped state
        "view": view,
        "has_any_slice": any(state.values()),
        "show_area": True,
        "board_scope": "workspace",
        "shipped_total": shipped_total,
        "shipped_hidden": shipped_hidden,
    })
```

`roadmap_board_groups_from(state_dict)` is a thin variant that tuples an existing
dict (so the view controls capping); alternatively `roadmap_board_groups` takes
the pre-capped state. Either is fine — pick one in implementation.

`board.slice_move` already re-renders the workspace board when `?scope=workspace`;
it will pass the same `shipped_total`/`shipped_hidden` so the footer link survives
a drag-driven re-render.

## Settings — view + endpoint + template

- **Endpoint** `web:settings_shipped_board` (POST, org-admin gated, matching the
  existing `workspace_rename` pattern): validates and saves `shipped_board_mode`
  + `shipped_board_limit`; returns 204 (or the updated control fragment for htmx).
- **URL**: `settings/<org>/<ws>/shipped-board` in `settings_patterns`.
- **Form** in `settings_workspace.html`: a `<select>` (Count / Days) + number
  input, labeled e.g. "Shipped shown on board". Sits alongside workspace name /
  tokens.

## Template changes

- **`_board.html`** (kanban): after a column's cards, render the footer only for
  the workspace board's shipped column with hidden items:
  ```
  {% if board_scope and status == "shipped" and shipped_hidden %}
    <a class="board-col-more" href="?view=list&status=shipped">View all shipped ({{ shipped_total }}) →</a>
  {% endif %}
  ```
  Area board leaves `shipped_hidden` unset → no footer.
- **`_status_group.html`** (list): optional `more_url` / `more_count` params; the
  roadmap list's Shipped include passes them to render the same link. Home and
  other includes omit them → no footer.
- **`roadmap.html`**: three render modes —
  1. `filter_status` set → a heading (`Shipped`), a "← Board" back link, and a flat
     `.panel` of `_slice_row` (uncapped, `show_area=True`). No kanban, no toggle.
  2. board view (default) → kanban with capped shipped + footer.
  3. list view → 4 groups; shipped group capped + footer.
- **`home.html`**: the "Recently shipped" section caps its list via `cap_shipped`
  (home view change) and adds a `View all shipped (N) →` link to the same
  `?view=list&status=shipped` URL. Stays collapsed-by-default.
- **`_slice_card.html` / `_slice_row.html`**: already show the Area badge under
  `show_area` — reused as-is.

## New CSS

- `.board-col-more` / `.group-more`: a quiet mono link (reuse `--ink-soft`,
  `--radius-small`, `var(--mono)`), consistent with existing quiet affordances.
  Tokens only — no literal hex/radius.

## Edge cases

- **Null `completed_at`** on legacy shipped rows: sort falls back to `updated_at`;
  in `days` mode such rows are excluded (no completion date to window on) — this
  is acceptable and rare.
- **Cap ≥ total**: no hidden items → no footer link; `?status=shipped` still works
  if the user navigates there directly.
- **`limit = 0`**: disallowed by validation (min 1). If somehow 0, `count` shows
  none and the footer links to the full list — not broken, just degenerate.
- **Empty workspace**: board renders 4 empty columns; existing empty hint applies.

## Testing (pytest, `tests/web` + `tests/`)

- `cap_shipped`: count mode returns first N; days mode filters by cutoff; total
  reported correctly; null `completed_at` handling.
- roadmap board caps shipped and renders `View all shipped (N)` when hidden > 0;
  no footer when total ≤ limit.
- `?view=list&status=shipped` renders **all** shipped, newest-first, with
  `card`/`row` Area badges, and **not** the kanban (`id="board"` absent).
- `?status=building` generically renders the building list (proves the dimension
  is reusable).
- Shipped ordering is `completed_at` desc.
- Settings endpoint updates both fields; rejects invalid mode and out-of-range
  limit; admin-gating enforced.
- Home "Recently shipped" is capped and its view-all link targets the filtered URL.

## Out of scope / future

- Per-Area board capping.
- `dropped` archive.
- Pagination / date-grouping of the filtered list (deliberately flat now).
