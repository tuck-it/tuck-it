# Slice view redesign — design

Date: 2026-07-15
Status: approved (brainstorm)
Scope: the slice slide-over panel (`_slice_panel.html`) + its deep-link/refresh
routing. Product repo only (`tuckit/web`). No cloud/billing surface.

## Problem

The current slice panel has three classes of problems, observed on the live
`building` slice "Bulk slice import via CSV":

1. **Flat hierarchy.** `.panel-inner { display:flex; flex-direction:column;
   gap:14px }` renders every element — breadcrumb, title, byline, status,
   description, bites, context, activity, actions — as a uniform stack with the
   same 14px gap. Within-group and between-group spacing are identical, so no
   grouping reads. Only two hairline dividers exist.
2. **Oversized status + scattered metadata.** Status is a full-width 4-tab
   segmented control that visually competes with the title. Area (top), byline
   (top) and tags (`Context`, far below) are scattered instead of grouped.
3. **Mode-switch on refresh (the core UX bug).** Clicking a slice pushes the
   URL `…/slices/<id>/?panel=1`. That path has no memory of the page the user
   was on. On refresh the server renders `slice_detail.html` (base + the panel
   partial dumped into `.main`) — a narrow panel orphaned in the main column.
   The user opened a right-hand slide-over; refresh jarringly replaces it with a
   full detail page. The mode is not continuous.

Secondary: the `Area` reference ("Core") can render as a raw UA hyperlink
(purple, underlined). The `.crumb-link` token exists (`app.css:1600`,
`color: var(--ink-faint); text-decoration:none`) and there is no global `<a>`
reset, so a raw render means that rule isn't reaching the element (most likely a
stale cached `app.css`; to be confirmed live). The redesign replaces the link
with an Area chip regardless.

## Decisions (locked during brainstorm)

### D1 — Deep-link = overlay param on the current page

tuckit is a server-rendered Django + htmx app (not a SPA), so on a hard refresh
the URL is the only source of truth. To keep the slide-over continuous:

- Clicking a slice keeps the **current page path** and adds `?slice=<id>` to it
  (e.g. `/o/…/home?slice=123`, `/o/…/areas/core?slice=123`) instead of
  navigating to `/slices/<id>/`.
- htmx still swaps the panel into `#panel`. The push happens via the server
  returning an **`HX-Push-Url`** response header computed from the request
  `Referer` (the list page): strip its query, append `?slice=<id>`.
- On full load / refresh of any list page, if `?slice=<id>` is present and the
  slice is accessible, the page renders normally **and** the panel opens with
  that slice — same page, slide-over restored, no mode switch.
- The canonical `/slices/<id>/` full page is **kept** for cold/shared links
  (someone who receives a link with no list context) and gets a breadcrumb back
  to its Area. `Copy link` copies this canonical URL.

Rejected: D2 (entity full-page on refresh — GitHub/Jira style) because it
doesn't match the user's expectation that the slide-over persists; and the
server-referrer-stored variant (fragile).

### C — Panel layout = properties cluster, three zones

Single-column (the slide-over is narrow), grouped into three zones with clear
between-zone separation and tight within-zone spacing:

- **Zone 1 — Header**
  - Area **chip** (`◈ Core`, subtle filled pill) + close `×` on the right.
  - **Title** — dominant H1 (the clear visual #1).
  - **Properties block** — a bordered card of compact key/value rows:
    - `Status` → a **clickable status pill** (dot + label + caret). Click opens
      a **dropdown menu** of the four statuses (idea / planned / building /
      shipped); one click sets it (`hx-post` to `web:slice_status`). Replaces
      the full-width `seg--tabs`. `dropped` remains a separate action in the
      action bar (unchanged).
    - `Created` → you / agent.
    - `Updated` → timesince.
    - `Tags` → inline add; existing tag chips wrap below the row. This
      **replaces** the separate `Context` section — `_slice_tags.html` is reused
      inside the properties block, and the standalone `Context` label/divider is
      removed.
- **Zone 2 — Body**
  - **Description** — label + seamless inline-edit field (see interaction below).
  - **Bites** — label + `done/total` + progress track (reuses `.row-prog-track`)
    + bite rows + "Add a bite…" (unchanged behavior).
- **Zone 3 — Activity** — label + timeline (unchanged behavior).
- **Sticky action bar** (unchanged): Drop slice / Copy link / Open full page.

Section labels use one unified tone (small uppercase `--ink-soft`) across
Description / Bites / Activity — currently `Bites` is 14/600 while
`Context`/`Activity` are 13/600.

### Interaction — Description inline edit (seamless)

Fixes the jarring jump where clicking the placeholder expands a blank 6-row
textarea:

- Click the display → edit **in place**, in the **same box**, with the **same
  background (paper) and same font / size / line-height as the reading view** —
  it must not turn into a white form field. Only a minimal focus affordance.
- The textarea starts at ~2 rows and **auto-grows** to fit content (no fixed
  `rows="6"`, no inner scroll until large).
- Saves on **blur** (consistent with the title) and on **⌘/Ctrl+Enter**; **Esc**
  cancels. The explicit "Save" button is removed.

## Components touched

- `web/templates/web/partials/_slice_panel.html` — restructure into the three
  zones; Area chip; properties block; status dropdown; description inline-edit
  markup; unified section labels.
- `web/static/web/app.css` — new/updated rules: `.area-chip`, `.props`/`.prop-row`,
  `.status-pill` + `.status-menu` (dropdown), seamless `.spec-edit` (inherit bg
  + font, autogrow), unified section-label tone. Remove the now-dead
  `.seg--tabs` slice usage and the panel-specific overrides it no longer needs.
- `web/templates/web/partials/_slice_row.html`, `_slice_card.html` — stop
  pushing `/slices/<id>/`; rely on the server `HX-Push-Url` (current-path +
  `?slice=`). Keep `href` as the canonical full-page URL for no-JS / new-tab.
- `web/panel.py` / `web/views/slices.py` (+ wherever the panel is served) —
  compute and return `HX-Push-Url` from `Referer`; keep `?panel=1` semantics for
  the swapped fragment.
- Base template / a small shared hook (context processor or `base.html`
  include) — on any page, if `?slice=<id>` resolves to an accessible slice,
  render `_slice_panel.html` (is_panel=True) into `#panel` so refresh restores
  the open slide-over. This must be DRY across Home / Board / Area / etc.
- `slice_detail.html` — keep as the canonical full page; add an Area breadcrumb
  and make it read as an intentional full page (not a stray narrow panel).

Status dropdown uses a small Alpine `x-data` for open/close (matches existing
Alpine usage). Description autogrow is a tiny Alpine/textarea handler.

## Workstreams (for the plan)

1. **Routing / deep-link (D1)** — push-url via `HX-Push-Url`, `?slice=`
   restore-on-load hook, canonical full-page breadcrumb. Independently testable
   (request/response assertions on push header + rendered `#panel`).
2. **Panel layout + interactions (C)** — three-zone template, properties block,
   status dropdown, seamless description edit, Area chip, CSS. Visual/behavioral.

## Testing

- Routing: request a list page with `?slice=<id>` → assert `#panel` contains the
  slice and is_panel semantics; request the panel fragment with a `Referer` →
  assert `HX-Push-Url` header = referer-path + `?slice=<id>`; canonical
  `/slices/<id>/` → full page with breadcrumb. Access control: `?slice=` for a
  slice outside the workspace → panel not rendered.
- Existing pytest suite (currently 481 passing) must stay green.
- Live verification (Django dev server + browser): open a slice from Home →
  slide-over; refresh → same page + slide-over restored (no full-page jump);
  change status via dropdown; edit description (no jump, bg/font preserved,
  autogrow, blur-save); Area chip styled (not a raw link).

## Out of scope

- EN/KR label i18n consolidation (noted; separate cleanup).
- Board/Home list redesigns beyond the `?slice=` restore hook.
- Any cloud/billing surface.

## Tokens / constraints

`var(--token)` only; no literal hex, no hardcoded radius (14px surfaces / 9px
controls via `--radius`/`--radius-small`). Accent stays teal `--blue`. Follow
`tuckit-landing/docs/product-ui/MIGRATION_PLAYBOOK.md`.
