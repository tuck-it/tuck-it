# Sidebar UX Refresh — Design

**Date:** 2026-07-14
**Repo:** `tuckit` (public OSS core)
**Scope:** Sidebar IA / UX reorganization of existing features + two net-new sidebar-only UI pieces (collapse, Cmd+K palette). No new backend models or destination pages.
**Reference:** `sidebar_review.png` (Before/After proposal, 8 points + extras)

## Goal

Rework the left sidebar to sharpen information architecture, current-location
emphasis, and area management — while keeping the design system **byte-identical**
(no new color/font/radius literals; `var(--token)` only) and moving the very top of
the sidebar to a **Linear-style workspace dropdown** (replacing the `tuckit` wordmark).

## Explicit scope decisions

**In scope:**
- IA grouping with `MAIN` / `AREAS` section headers.
- Stronger active state: existing `--blue-soft` background **plus** a left accent bar.
- Inbox badge restyled as a rounded, colored pill (reusing existing tokens).
- Per-area `⋮` popover menu (Rename / Delete) replacing inline hover actions; drag
  reorder (SortableJS + `rank`) preserved; `+` add button promoted to the section header.
- **Linear-style top:** workspace switcher becomes the topmost element, wordmark removed.
- **Activity bell moved to the top** (beside the workspace card / collapse button).
- **Sidebar collapse/expand** (icon-only mode), state persisted in `localStorage`.
- **Cmd+K command palette** over existing destinations only (client-side, no backend),
  plus a thin `Search ⌘K` discoverability pill under the workspace card.
- Bottom stack as full-width rows: `Settings`, `Light mode` (theme toggle promoted to a
  labeled row, reusing existing Alpine/localStorage logic), highlighted `Capture` (`C`).

**Out of scope (net-new features requiring backend/destination pages — deferred):**
- VIEWS: Starred, Recently Viewed, Archived *view*.
- FILTERS: My Filters / saved filters; Tags as a sidebar destination.
- Per-area color/icon customization (would need an `Area` migration).
- Archiving areas from the `⋮` menu (backend supports `Area.archived`, but there is no
  un-archive view yet — omitting avoids a one-way trap).

## Current implementation (baseline)

- Sidebar template: `tuckit/web/templates/web/partials/_sidebar.html`, included from
  `base.html:49` inside `.sidebar-wrap`.
- Partials: `_workspace_switcher.html` (Alpine popover), `_area_nav.html` → `_area_row.html`
  (loop + drag), `_triage_count.html` (Inbox badge).
- CSS: single `tuckit/web/static/web/app.css` ("components" layer, loaded 4th after
  brand → product → base). Sidebar selectors: `.sidebar` (`:15`), `.brand` (`:32`),
  `.ws-*` (`:34-79`), `.section` (`:81`), `.nav` / `.nav--active` (`:90-116`),
  `.util-row` / `.util-btn` (`:1141-1155`), `.capture-btn` (`:1157`), `.area-*` (`:1205-1242`).
- JS: `area_nav.js` (SortableJS reorder), inline Alpine for workspace popover / theme /
  capture / mobile menu / activity `#panel` slide-over (`base.html`).
- Data: context processors (`context_processors.py`) supply `areas`, `triage_count`,
  `switchable_workspaces`, `current_workspace` globally — no view changes needed.

## Component-by-component design

### 1. Top region — workspace card + bell + collapse
Replace `.brand` with a single-line workspace card built on the existing switcher data:

```
┌─────────────────────────────┐
│ [D] Default            ⌄  🔔 «│   ← workspace popover trigger · activity bell · collapse
├─────────────────────────────┤
│  🔍 Search             ⌘K    │   ← Cmd+K discoverability pill
└─────────────────────────────┘
```

- Reuse `switchable_workspaces` / `current_workspace` and the popover open/close Alpine.
  Only markup + CSS change to the one-line card form.
- Activity bell: move the existing `.util-activity` button (its `hx-get` to `web:activity`
  `#panel` slide-over) from the bottom `util-row` up here. Behavior unchanged.
- Collapse `«` toggles `.app--sidebar-collapsed` (see §5).
- Search pill triggers the same palette as `⌘K` (see §4).

### 2. MAIN nav + active state + badge
- Add a `.section` "Main" header above Home / Inbox / Board (labels/urls unchanged:
  `home` / `triage` / `roadmap`).
- Active state: keep `.nav--active { background: var(--blue-soft) }` and add a **left
  accent bar** — a 3px `--blue` inset (e.g. `box-shadow: inset 3px 0 0 var(--blue)` or a
  `::before` bar) so the token stays the source of truth. Applies to Home/Inbox/Board and
  active Area rows.
- Inbox badge: restyle `.nav-count` from muted text to a **rounded pill** using existing
  tokens (`--blue` text/`--blue-soft` bg or equivalent). Value + OOB refresh unchanged
  (`_triage_count.html`, `triage_count`).

### 3. AREAS section
- Section header row: "Areas" label + right-aligned `+` button. The `+` promotes the
  existing `web:area_create` flow (inline input on click, or reveal the existing add form).
  The standalone bottom `.area-add` form is removed in favor of the header `+`.
- Each `_area_row.html`: replace inline hover rename/delete with a right-aligned `⋮`
  button opening a small popover → **Rename** (existing inline-rename form) and **Delete**
  (existing hx-post). Drag handle + SortableJS reorder + `hx-swap-oob` refresh unchanged.
- No VIEWS/FILTERS sections (no destinations). The `.section` header + `+` pattern is
  reusable if such sections are added later.

### 4. Cmd+K command palette
- New Alpine component (modal overlay, same pattern as `_capture_modal.html`) opened by a
  global `⌘K` / `Ctrl+K` handler (mirrors the existing `c` hotkey in `base.html:35`) and by
  the Search pill.
- Static + data-driven command list, all **existing** destinations: Home, Inbox, Board,
  each Area (`{% for a in areas %}`), Settings, Capture, toggle theme. Client-side fuzzy
  filter, ↑/↓ keyboard nav, Enter navigates (`window.location` / triggers the action),
  Esc closes. No new routes, no server round-trip.
- File: new `_command_palette.html` partial, included in `base.html`; minimal JS (Alpine
  inline or a small `command_palette.js`).

### 5. Collapse / expand (icon-only)
- `«` toggles a root class `.app--sidebar-collapsed`; persist to `localStorage`
  (`tuckit:sidebar-collapsed`), restore on load before paint to avoid flash.
- Collapsed: width ~220px → ~60px rail; hide `.nav-label`, section headers, badges, the
  search pill's label, area names; show icons only. Icon `title`/tooltip exposes the label.
  Collapse chevron flips to `»` to expand.
- Pure CSS off the root class + small JS for toggle/persist. Kept independent from the
  mobile off-canvas (`@media max-width:767px`) logic so they don't conflict; on mobile the
  drawer behavior wins and collapse is inert.

### 6. Bottom stack
- Full-width rows: `Settings` (existing link + active state), `Light mode` (promote the
  existing theme-toggle Alpine into a labeled icon+label row; label reflects current theme),
  and the highlighted `.capture-btn` with its `C` kbd. Activity bell no longer here (moved
  to top). `.util-row` simplified accordingly.

## Design-system rules (hard constraints)

- **No literal hex, no hardcoded radius/px color values.** All new styling via `var(--token)`.
  Surfaces use `--radius` (14px), controls `--radius-small` (9px). Accent = single teal `--blue`.
- Any genuinely new token (e.g. accent-bar width, collapsed rail width) goes in
  `tokens.product.css` only — never in `base.css`/`app.css` as a literal, never in brand.
- `<link>` order and file boundaries unchanged; all sidebar component CSS stays in `app.css`.
- The `tuckit` design-drift pytest (`tests/web/test_design_system.py`) must keep passing.

## Data flow / backend

No model, migration, view, URL, or context-processor changes. Everything reuses existing
`areas`, `triage_count`, `switchable_workspaces`, `current_workspace`, and existing routes
(`web:home`, `web:triage`, `web:roadmap`, `web:area`, `web:area_create`, `web:area_reorder`,
`web:activity`, `web:settings_workspace`).

## Testing

- Keep the design-drift pytest green.
- Template smoke: sidebar renders with workspace card at top, bell at top, no wordmark, MAIN
  header, accent-bar active state, Inbox pill, area `⋮` menu, Search pill, bottom rows.
- Interaction smoke (manual or lightweight): `⌘K` opens palette and navigates; Search pill
  opens palette; collapse toggles + persists across reload; area rename/delete/reorder still
  work; theme toggle still persists; activity slide-over still opens from the new bell spot.
- Verify no new color/radius literals introduced (grep for hex in the diff).

## Risks / notes

- Public repo: this stays a **neutral UI change** — no billing/cloud/entitlement code.
- Spec kept **untracked** in `docs/superpowers/` per workspace convention (never committed
  to public `tuckit`).
- Collapse + mobile drawer interaction is the main integration risk — keep them isolated.
