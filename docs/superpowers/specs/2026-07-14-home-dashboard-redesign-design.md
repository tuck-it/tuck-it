# Home dashboard redesign — design

Date: 2026-07-14
Repo: `tuckit` (public OSS core, BSL 1.1)
Status: approved, ready for implementation plan

## Goal

Rework the Home page from a single-column stacked list into a scannable
dashboard that surfaces (a) at-a-glance workspace metrics with day-over-day
movement, (b) what needs attention, and (c) a focused three-column view of
current work — while **strictly** preserving the existing design system
(background, tokens, radii, teal `--blue` accent) and using only English UI
copy.

Source of the visual target: `home_review.png` (the "After (Proposed)" mockup).
Two elements from the mockup are intentionally NOT ported:

- The Capture **split-button + "…" overflow menu** — speculative UI with no
  defined actions (YAGNI). Keep the existing single **Capture** button.
- The **confetti emoji** on the shipped strip — clashes with the calm
  paper-texture aesthetic. Restrained strip instead.

## Constraints / decisions (already settled)

1. **Summary cards = counts + deltas** (no sparklines). Deltas need historical
   count data, obtained via lazy daily snapshots (below).
2. **Needs-attention = quiet panel**, not a red banner/band. The design system
   avoids colored bands ("status dot, never a banner/band"). Prominence comes
   from position (top), not fill.
3. **Full 3-column dashboard** layout, reusing the existing `.board` grid
   vocabulary. Collapses to stacked / scroll-snap on mobile like the board does.
4. All CSS lives in `app.css`, tokens only. No edits to `tokens.brand.css` or
   `base.css`. No literal hex, no hardcoded radii.
5. UI copy in English only.

## 1. Data layer — lazy daily snapshots

Lives in the public `tuckit` core (neutral product functionality — no billing).

### Model: `WorkspaceStatSnapshot`

Fields:

- `workspace` — FK to `Workspace`, `related_name="stat_snapshots"`
- `date` — `DateField` (workspace-local calendar day; use `timezone.localdate()`)
- `building_ct` — `IntegerField`
- `backlog_ct` — `IntegerField`
- `shipped_week_ct` — `IntegerField`
- `attention_ct` — `IntegerField`

Constraints:

- `unique_together` / `UniqueConstraint` on `(workspace, date)`
- Index on `(workspace, date)` for the "most recent prior day" lookup

Migration: new migration in the app that owns `Workspace`
(`tuckit/core/migrations/`).

### Service: `snapshot_today(workspace) -> dict`

Location: `tuckit/core/services/state.py` (alongside `home_state`).

Behavior:

1. Compute today's four counts from live data:
   - `building_ct` = count of `building` slices (reuse `home_state` buckets or
     query directly — avoid double work; see "Wiring" below)
   - `backlog_ct` = planned + ideas + someday counts
   - `shipped_week_ct` = slices with `completed_at >= now - 7 days`
   - `attention_ct` = `len(attention_items(workspace))`
2. `update_or_create` today's snapshot row with those counts (idempotent per
   day; if counts changed during the day, the row is refreshed).
3. Find the most recent snapshot with `date < today` for this workspace.
4. Return a structure the view can turn into `metrics`:

```python
{
  "building":      {"value": 5, "delta": +1},   # delta None if no prior day
  "backlog":       {"value": 6, "delta": -2},
  "shipped_week":  {"value": 2, "delta": +1},
  "attention":     {"value": 2, "delta": 0},
}
```

- `delta` is `today - prior`, or **`None`** when there is no prior-day row
  (first day). `None` renders as no delta line — never "+0" for missing history.
  An actual zero change **does** render (e.g. "no change" / "0 since yesterday").

Notes / accepted trade-offs:

- This writes on a GET request. That is an accepted, cheap single upsert
  (standard lightweight-analytics pattern), kept isolated in the service so the
  view stays a thin caller.
- `update_or_create` handles the concurrent-first-visit race well enough for
  this use; a rare double-write just overwrites identical counts.
- Empty/no-workspace path (unauthenticated or no current workspace) must **not**
  attempt a snapshot — the view guards on `ws` and passes empty metrics.

## 2. View — `pages.home`

`tuckit/web/views/pages.py`:

- When `ws` is present, call `snapshot_today(ws)` and build a `metrics` list of
  4 entries in display order (building, backlog, shipped_week, attention), each
  `{"label", "value", "delta"}` with an English label:
  - "Building", "Backlog", "Shipped this week", "Needs attention"
- Pass `metrics` to the template. When no `ws`, pass `metrics = []` (or omit) so
  the cards row renders nothing / a neutral empty.
- Keep all existing context keys the template still needs (`state`,
  `in_progress`, `shipped_total`, `shipped_hidden`, `show_get_started`, etc.).
  Remove only the now-redundant `building_ct` / `queued_ct` / `later_ct` context
  vars **iff** nothing else in the template references them after the rewrite;
  otherwise leave them.

## 3. Template / layout — `home.html`

Rows, top to bottom:

1. **Header** — existing `.page-head`. Title "Home" + subtitle
   "Today's progress and what to focus on next" + single **Capture** button
   (unchanged behavior).
2. **Summary cards** — `.stat-cards` grid of 4 `.stat-card`, each:
   `label` / big `value` / `.stat-delta` line. Delta shows an ↑/↓ glyph +
   number + "since yesterday"; omitted entirely when `delta is None`.
3. **needs_you** — existing `_group_label` + `_attention_panel` include,
   unchanged (quiet panel; all-clear when empty). Stays at top for prominence.
4. **Get started** — existing `_get_started` include, when `show_get_started`.
5. **Three-column grid** — `.home-cols` reusing `.board`/`.board-col` styling:
   - **Focus** (`state.building`) — slice rows with `bite_bar` progress, area +
     tags, capped list + "View all →" to the board's building filter.
   - **Doing** (`in_progress.bites`) — bite rows; empty state = quiet CTA that
     opens Capture (`cap = true`) instead of bare muted text.
   - **Next + Later** — two stacked mini-panels in one column:
     - Next = `state.planned`, "View all →"
     - Later = `state.ideas` + `state.someday`, "View all →"
     Each "View all" links to the existing roadmap list with `?status=` filter
     (no new URLs/routes).
6. **recently_shipped** — `.shipped-strip`: always-visible horizontal row of
   `.shipped-chip` (title + area), plus "View all →" when `shipped_hidden`.
   Replaces the previous collapsed fold. No confetti.

Reuse existing partials wherever possible: `_slice_row.html`, `_bite_row.html`
(or the inline doing-row markup already in home), `_status_dot.html`,
`_group_label.html`, `_attention_panel.html`, `bite_bar` templatetag.

## 4. CSS — `app.css` only, tokens only

New component blocks (all using `var(--token)`, `--radius` / `--radius-small`,
`--blue`):

- `.stat-cards` — responsive grid (4 across on wide, wraps down on narrow).
- `.stat-card` — surface with `--radius`, existing panel/border tokens.
- `.stat-card-label`, `.stat-card-value` (tabular-nums), `.stat-delta`
  with `--stat-delta-up` / `--stat-delta-down` **expressed via existing ink
  tokens** (no new palette entries; e.g. up = `--blue` or the existing positive
  ink, down = `--ink-faint`/muted). Neutral "no change" uses muted ink.
- `.home-cols` — 3-column grid mirroring `.board`
  (`grid-template-columns: repeat(3, minmax(...))`), same gap scale.
- Column headers reuse `.board-col-head` / `.board-col-label` /
  `.board-col-count` vocabulary (or thin aliases) so Focus/Doing/Next match the
  Board tab visually.
- `.shipped-strip` (horizontal flex, wraps) + `.shipped-chip`
  (`--radius-small`, muted surface).
- Mobile: same horizontal scroll-snap treatment the `.board` already uses so the
  three columns aren't squeezed on small screens.

No changes to `tokens.brand.css`, `tokens.product.css`, or `base.css`.

## 5. Testing

- **Service** (`tests` for `state.py`):
  - `snapshot_today` creates a row on first call; second call same day updates,
    not duplicates (idempotent per `(workspace, date)`).
  - Delta = today minus most-recent prior-day row.
  - First-ever day → all deltas `None`.
  - Counts match the live buckets (building / backlog / shipped-this-week /
    attention).
- **View** (`tests/web` home tests):
  - Authenticated workspace: `metrics` present, 4 entries, correct values.
  - No-workspace path renders without attempting a snapshot (no crash, empty
    cards).
  - Existing home render tests remain green after markup changes.
- **Design-system drift**: the existing `tests/web/test_design_system.py` must
  still pass (no brand-token edits).

## Out of scope (YAGNI)

- Sparklines / multi-day trend charts.
- Capture split-button dropdown and "…" overflow menu.
- Confetti / celebratory animation.
- Any scheduled job / management command (snapshots are lazy on view).
- New roadmap routes (reuse `?status=` filters).
