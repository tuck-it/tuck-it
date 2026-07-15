# Slice view redesign — design spec

**Date:** 2026-07-14
**Repo:** `tuckit` (public, BSL 1.1)
**Source of truth for intent:** `slice_review.png` (Before / After (Proposed))

## Goal

Reproduce the information hierarchy, grouping, empty-state, activity-timeline,
and bottom action bar of the review's **After (Proposed)** layout, while keeping
the **design system 100% identical**: existing tokens only (paper/ink/blue,
`--radius`/`--radius-small`, `--good`/`--warn`, status dots), Onest + IBM Plex
Mono fonts, existing SVG icon set. **No emoji, no new colors, no new UI
primitives** (no dropdown/popover component).

Both the 420px slide-over panel and the full slice page render the **same
partial** (`_slice_panel.html`), so the layout is **context-adaptive**.

## Decisions (locked with user)

1. **Status tabs use status-dots, not emoji.** The mockup's 💡📋🔨✅ are dropped;
   each tab shows the existing `status-dot--{status}` + label.
2. **Metadata: existing fields only, no Priority.** `Slice` has no priority
   field by design (priority is expressed by `rank` ordering + `status`, not a
   label — deliberately lean, Jira-style typed fields are avoided). No migration.
3. **Details block omitted (option C).** With only Source + Area available, a
   Details block is pure redundancy (Area already in breadcrumb, Source already
   in the byline). Skip it; revive later if a genuine new field (e.g. Priority)
   is added.
4. **Context-adaptive rendering** via an `is_panel` flag threaded through
   re-renders so panel chrome survives htmx mutations.
5. **Title stays click-to-edit** (existing pattern); no separate Edit button or
   `⋯` overflow menu (would require a new dropdown primitive).
6. **Copy link / Open full page are text buttons** (no link icon in the set);
   reuse the existing `→` arrow convention.
7. **View-all-bites pagination and Priority are out of scope for v1.**

## Vertical structure (top → bottom)

| # | Section | Content | Context notes |
|---|---------|---------|---------------|
| 1 | Header | breadcrumb `[area icon] {area.name}` linking to the area view | `✕` close **panel only** |
| 2 | Title | 22px, click-to-edit (existing inline pattern) | — |
| 3 | Byline | `Created by {you\|agent} · Updated {timesince} 전`, muted 12px | moved up from footer |
| 4 | Status tabs | wide 4-col segmented control; each tab = `status-dot--{st}` + label; active = `--paper-deep` bg | dropped/restore handled in action bar, not here |
| 5 | Spec box | framed (`--line` border, `--paper-solid`/raised bg, `--radius-small`), click-to-edit; empty → muted placeholder | — |
| 6 | Bites | header row: `Bites  {done}/{total}  [progress bar]  [+ Add bite]`; then **either** the bite list (existing `_bite_row`) **or** the empty-state card | see Bites section |
| 7 | Context | tag chips (`#tag ×`) + `+ Add tag`, section label "Context"; **area chip removed** (now in header) | — |
| 8 | Activity | vertical-connector timeline: node dot per event + actor/verb/target/time | only when `activity` present |
| 9 | Action bar | `Drop slice` (danger, `--warn`) · `Copy link` · `Open full page →`; sticky bottom in panel. Dropped state → `Restore` | `Open full page` **panel only** |

## Component / CSS notes (tokens only)

- **Breadcrumb** — reuse `area` icon; `--ink-faint` text; crumb links to area view.
- **Status tabs** — extend `.seg`/`.seg-item` with a wide variant: full-width
  grid, equal columns, dot shown on every tab (colored per status), active tab
  `--paper-deep` + weight 500. No new colors.
- **Spec box** — `border:1px solid var(--line)`, `background:var(--paper-solid)`,
  `border-radius:var(--radius-small)`; keep `.spec` markdown styles.
- **Bites header** — count via existing `bite_progress` data; progress bar =
  thin track `--paper-deep` + fill `--good`, width = done/total. Width needs a
  numeric percent (see panel.py change). `+ Add bite` button focuses the
  always-present add input.
- **Empty-state card** — `--line` border, `--paper-solid` bg, `--radius`,
  centered: title "아직 bite가 없습니다", sub "이 slice를 구현하기 위한 작은
  단계를 추가해보세요.", CTA `+ Add your first bite` (focuses add input). Shown
  only when `bites` is empty; otherwise the list renders instead.
- **Context/tags** — restyle existing `_slice_tags` chips; remove the inline
  `meta-area` area name; label the section "Context".
- **Activity timeline** — `_activity_row` gets a leading node column: a `1px`
  `--line` vertical connector + a `7px` `--ink-faint` dot; last row drops the
  connector. Keep actor/verb/target/time text.
- **Action bar** — `position: sticky; bottom: 0` inside the scrolling panel,
  top border `--line`, `--paper-solid` bg, negative margins to span the padding.
  `Drop slice` color `--warn`, transparent border. `Copy link` uses the existing
  Alpine clipboard pattern (`navigator.clipboard.writeText`, "Copied" toggle).
  `Open full page →` links to `web:slice`.

## Context-adaptivity mechanism

- Add `is_panel` to `slice_panel_context(slice_, is_panel=False)`.
- The panel is opened via `slice_detail?panel=1`; mutation endpoints
  (`slice_status`, `slice_edit`, `bite_create`) re-render `_slice_panel.html`.
  Thread the flag by appending `?panel=1` to those hx-post URLs **when
  `is_panel`**, and have the mutation views read `request.GET.get("panel")` →
  pass to `slice_panel_context`. This keeps `✕`, `Open full page`, and the
  sticky bar correct after every htmx swap.
- `slices.slice_detail` already computes `is_panel`; pass it into the context.

## Files touched

- `tuckit/web/templates/web/partials/_slice_panel.html` — main rewrite (structure 1–9).
- `tuckit/web/templates/web/partials/_slice_tags.html` — drop area chip, "Context" label.
- `tuckit/web/templates/web/partials/_activity_row.html` — timeline node markup.
- `tuckit/web/static/web/app.css` — new/updated component styles (tokens only).
- `tuckit/web/panel.py` — add `is_panel`, `bites_done`, `bites_total`, `bites_pct` to context.
- `tuckit/web/views/slices.py` — pass `is_panel` into context.
- `tuckit/web/views/mutations.py` — read `?panel=1`, thread `is_panel` through `_panel()`.

## Out of scope (v1)

- Priority field (model change).
- Title `⋯`/Edit overflow menu (new dropdown primitive).
- View-all-bites pagination / bite truncation in panel.
- Any change to the design tokens themselves.

## Testing

- Existing design-system drift test (`tests/web/test_design_system.py`) must
  still pass — no token edits.
- Manual/rendered check both contexts: (a) slide-over panel (close, sticky bar,
  Open full page present), (b) full page (no close, no Open full page).
- Bite empty state vs populated list toggle.
- htmx mutation round-trip (status change, add bite, edit spec, add/remove tag)
  keeps the correct context chrome.
- Light and dark theme.
