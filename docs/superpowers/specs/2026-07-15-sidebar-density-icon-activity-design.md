# Sidebar density + panel-toggle icon + Activity removal — design

**Date:** 2026-07-15
**Repo:** tuckit (public core)
**Status:** approved, ready for implementation plan
**Follow-up to:** 2026-07-15-sidebar-polish-design.md (already merged)

Three related chrome-cleanup changes requested together. Desktop + shared
chrome; reading content (slice description, markdown, card body) is untouched.

## Problems / requests

1. **Density too low / fonts too big vs Linear.** The base font is 16px and the
   sidebar inherits it; nav rows are 40px tall. Linear-style app chrome runs
   ~13px with ~28–32px rows. The *reading* areas are fine — only the chrome
   frame (sidebar, nav, panel headers/labels/meta) should tighten.
2. **Collapse icon should be a panel-toggle glyph.** The current `<` chevron
   should become the VSCode/Linear "panel-left" icon (rounded rect + left
   divider line) that reads as "toggle sidebar," not a directional arrow.
3. **Remove the Activity feature entry points.** The sidebar clock button, its
   slide-over, and the standalone Activity page are unwanted. The underlying
   event system stays.

## Decisions (from brainstorming)

- Density scope = **chrome-focused**: sidebar + slice-panel frame. Reading
  content stays at its current size.
- Icon = **panel-left** (lucide), replacing the chevron; drop the collapse
  rotation CSS (same icon in both states, VSCode-style).
- Activity removal scope = **button + slide-over + standalone page/route**.
  Keep `ActivityEvent`, `slice_activity`, `_activity_row.html`, the slice-detail
  Activity thread, the `welcome` agent-activity poll, and the `#panel`
  slide-over infrastructure (used by the slice slide-over).

## Design

### A. Density — chrome-focused

Primary lever: give `.sidebar` an explicit `font-size: 13px` so every label
(nav, util, search, capture) drops from the inherited 16px in one declaration.
Then tighten row heights and gaps to a Linear cadence.

Sidebar (`app.css`):

| Selector | Current | Target |
| --- | --- | --- |
| `.sidebar` | font 16 (inherited), padding `16px 12px`, gap `4px` | `font-size: 13px`, padding `14px 10px`, gap `2px` |
| `.nav` | `min-height: 40px`, gap `9px` | `min-height: 32px`, gap `8px` |
| `.nav-group` | gap `4px` | gap `2px` |
| `.util-btn` | `min-height: 36px` | `min-height: 30px` |
| `.capture-btn` | `min-height: 40px`, gap `9px` | `min-height: 32px`, gap `8px` |
| `.search-pill` | padding `7px 10px`, margin-bottom `8px` | padding `6px 9px`, margin-bottom `6px` |
| `.ws-name` | `14px` | `13px` |
| `.side-top` | padding `0 4px 6px` | padding `0 4px 4px` |
| `.nav-sep` | margin `10px 4px` | margin `8px 4px` |
| `.icon`, `.section` (11px) | — | unchanged |

Area-nav rows (`_area_nav.html` / `.area-row` etc.) inherit the sidebar 13px and
should match nav row height where they set their own — tighten to the same
cadence (min-height ~30–32px) if they hardcode taller.

Slice-panel frame (`app.css`) — headers/labels/meta/buttons only, **not** the
description/markdown body:

| Selector | Current | Target |
| --- | --- | --- |
| `.panel-titlebar .panel-title` (slice slide-over) | `22px` | `20px` |
| `.panel-head .panel-title` | `18px` | `17px` |
| `.section-label` | `12px` | `11px` |
| `.action-bar` padding | `13px 22px` | `10px 22px` |
| `.ghost` buttons | `12px`, padding `4px 8px` | unchanged (already dense) |

The slice title is reduced only one notch (it borders on content); the
description body, markdown (`.md-*`), and card title/body are explicitly out of
scope. The plan pins any additional panel-meta selectors it finds.

Reduced-motion, tokens, and the collapsed 60px rail behavior are unaffected.
`--radius`/`--radius-small` unchanged. `var(--token)` only — no literal hex
(`test_new_sidebar_css_uses_no_raw_hex` still governs `app.css`).

### B. Panel-toggle icon

- Add to `_ICON_PATHS` in `web_extras.py`:
  `"panel-left": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>'`
  (lucide `panel-left`, 24-viewBox, matches the existing stroke-icon style).
- `_sidebar.html`: change the collapse button from `{% icon "chevron" %}` to
  `{% icon "panel-left" %}`.
- `app.css`: remove the chevron-rotation rules
  (`.side-collapse .icon { transform: rotate(180deg)… }` and
  `html.sidebar-collapsed .side-collapse .icon { transform: rotate(0deg) }`).
  The panel-left glyph is identical in both states.
- `chevron` icon stays in `_ICON_PATHS` (still used by the workspace switcher
  `.ws-chev`).

### C. Activity removal (button + slide-over + page)

Remove:
- `_sidebar.html`: the `.side-top-act` Activity clock button.
- `tuckit/web/templates/web/partials/_activity_panel.html` (delete).
- `tuckit/web/templates/web/activity.html` (delete).
- `pages.py`: the `activity` view; the `recent_activity` import and its unused
  `recent_activity` key in the home context.
- `urls.py`: the `activity/` route (`name="activity"`). (Keep
  `welcome/agent-activity` — unrelated.)
- `web_extras.py`: the `"activity"` entry in `_ICON_PATHS`.
- `app.css`: the `.side-top-act` rules (currently sharing a selector with
  `.side-collapse` — split so `.side-collapse` keeps its styles) and the
  collapsed hide rule `html.sidebar-collapsed .side-top-act:not(.side-collapse)`.

Keep: `ActivityEvent` model + migrations, `recent_activity`/`slice_activity`
services, `_activity_row.html`, `_slice_panel.html` Activity thread, the
`welcome` agent-activity poll, and the `#panel` slide-over machinery in
`base.html`.

Tests to update (they currently assert the now-removed entry points — feature
removal, so these change):
- `tests/web/test_lens_pages.py`: remove `test_activity_page_lists_events`,
  `test_activity_panel_branch_returns_slideover`, `test_activity_full_page_still_works`;
  rewrite `test_sidebar_activity_is_bell_not_nav` to assert Activity is entirely
  absent from the sidebar (no `aria-label="Activity"`, no `/activity/`).
- `tests/web/test_home_shell.py`: remove `test_activity_bell_in_utility_row`;
  keep the "Activity is not a nav label" assertion.
- `tests/web/test_home.py`: drop the `'/activity/?panel=1' in body` assertion in
  `test_home_omits_roadmap_strip_and_recent_activity` (keep the rest).
- `tests/web/test_icons.py`: remove `test_activity_icon_differs_from_in_progress`
  (the `activity` icon no longer exists); keep the sun/moon test.
- `tests/test_services_activity.py`, slice-thread tests in
  `tests/web/test_slice_detail.py`, and `tests/web/test_welcome.py` stay green
  (model + slice thread + welcome poll all kept).

## Files touched

- `tuckit/web/static/web/app.css` — density (sidebar + panel frame), remove
  chevron-rotation + `.side-top-act` CSS.
- `tuckit/web/templatetags/web_extras.py` — add `panel-left`, remove `activity`.
- `tuckit/web/templates/web/partials/_sidebar.html` — swap collapse icon, remove
  Activity button.
- `tuckit/web/views/pages.py` — remove `activity` view + `recent_activity` usage.
- `tuckit/web/urls.py` — remove `activity/` route.
- Delete: `activity.html`, `_activity_panel.html`.
- Tests: `test_lens_pages.py`, `test_home_shell.py`, `test_home.py`,
  `test_icons.py` (updates), plus new density/icon assertions.

## Out of scope

- Reading-content typography (slice description, markdown, card body).
- `ActivityEvent` model / migrations / event logging.
- Mobile off-canvas drawer behavior.
- `tokens.brand.css` / `tokens.product.css`.

## Testing

- Density: assert `.sidebar { font-size: 13px }` and the tightened row heights
  present in `app.css`; visual check that sidebar reads denser and reading
  content is unchanged.
- Icon: `panel-left` in `_ICON_PATHS`; sidebar renders it on the collapse
  button; chevron-rotation CSS gone; workspace `.ws-chev` still uses `chevron`.
- Activity: `/activity/` route 404s (removed); no `aria-label="Activity"` /
  `/activity/` in any workspace page; `_activity_panel.html` and `activity.html`
  gone; slice Activity thread still renders (`_activity_row.html` intact);
  `welcome/agent-activity` still works; full suite green after test updates.
