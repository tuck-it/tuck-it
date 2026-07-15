# Sidebar redesign — design

Date: 2026-07-13
Repo: `tuckit` (public). This spec lives under `docs/superpowers/` and is
**local-only — never commit** (per workspace memory `docs-superpowers-local-only`).

## Goal

Fix four rough edges in the home sidebar so it reads as one intentional design
instead of parts copy-pasted from different apps:

1. Workspace switcher uses a raw native `<select>` (ugly OS dropdown; the
   `Org · Workspace` label doesn't communicate the hierarchy).
2. Nav ordering doesn't match best-practice grouping.
3. "Light mode" toggle is an oversized bordered button, visually out of place.
4. "Capture" button has a mismatched border+raised treatment.

Constraints (from `tuckit/CLAUDE.md`): colors/radius via `var(--token)` ONLY —
no literal hex, no hardcoded radius. Accent is the single teal `--blue`. Stack
is Django templates + Alpine.js + HTMX. Files touched all live under
`tuckit/tuckit/web/`.

## Data model context

`Org` has many `Workspace`s. `switchable_workspaces` (context processor)
returns every `Workspace` the user can access, each exposing `ws.org.name` and
`ws.name`. The switcher's job is to pick the active workspace, scoped by org.

## 1. Workspace switcher → custom Alpine popover

Replace `partials/_workspace_switcher.html`'s native `<form><select>` with an
Alpine popover. Always render it (even with a single workspace) as the app's
identity anchor.

**Trigger button (`.ws-switch`)**
- Leading monogram: rounded square (`--radius-small`, `--blue-soft` bg, `--blue`
  text), first letter of the workspace name.
- Two-line label: Org name on top (caption, `--ink-faint`, small), Workspace
  name below (`--ink`, primary weight). Truncate with ellipsis.
- Trailing `chevron` icon rotated to point down; rotates 180° when open.
- Flat by default; hover → `--paper-raised`. Uses `--radius-small`.

**Panel (`.ws-menu`)**
- Absolutely positioned below the trigger, `--surface` bg, `1px var(--line)`
  border, `--radius`, box-shadow via `--shadow`, small entry transition.
- Workspaces grouped by Org. Org name is a faint mono header reusing the
  `.section` treatment. Each workspace row: name + a `check` icon on the active
  one (`--blue`). Row hover → `--paper-raised`.
- Clicking a row submits a per-row `<form method="post"
  action="{% url 'web:switch_workspace' %}">` carrying that `workspace_id`
  (keeps the existing backend contract; no JS-only submit).
- Divider, then a "Workspace settings" link → `web:settings_workspace`.
- Closes on `@click.outside` and `@keydown.escape`; `aria-expanded` on trigger.

**Single-workspace case:** still renders the trigger + panel; panel shows the one
workspace (checked) and the Settings link. No dead-end.

## 2. Nav ordering + icon fix

New order (top nav group): **Home · Attention · Triage · In Progress · Roadmap
· Activity**. Rationale: action queues (Attention, Triage — Triage carries a
count) first, then work-state views (In Progress, Roadmap), then passive history
(Activity) last.

Change: move `Triage` up to 3rd; `Activity` becomes last. Edit only the row
order in `partials/_sidebar.html` (each row keeps its existing markup, including
the Triage count include).

Icon fix: `in-progress` and `activity` currently share a near-identical
waveform path in `_ICON_PATHS`. Give `activity` a distinct glyph (e.g. a
pulse-in-a-list / clock-ish mark) so the two nav items aren't confusable. Only
the `activity` entry in `web_extras.py` changes.

## 3. Bottom utility row (Settings + theme)

Replace the full-width `Settings` nav row **and** the big bordered `.theme-toggle`
button with one compact row `.util-row` (flex, small gap) holding two flat
icon-buttons `.util-btn`:
- Settings: `settings` icon, links to `web:settings_workspace`; keeps the
  active state when on a settings route.
- Theme toggle: `sun`/`moon` icon that swaps with `theme`. Keeps the existing
  Alpine logic (`document.documentElement.dataset.theme`, localStorage). Icon
  only; `aria-label`/`title` = "Switch to light/dark mode".

`.util-btn`: `--ink-faint`, hover → `--ink` + `--paper-raised`,
`--radius-small`, square-ish tap target (min 34–36px). No borders.

Add `sun` and `moon` paths to `_ICON_PATHS`.

Decision: keep a small **Settings** text label alongside its icon is optional;
default to icon + short label for Settings, icon-only for theme, so the row
stays quiet but Settings remains discoverable. (If the row feels cramped, both
become icon-only.)

## 4. Capture → single solid-teal primary CTA

Keep at the very bottom. Restyle `.capture-btn`:
- `background: var(--blue)`, text on it a light token that reads on teal — use
  `--paper` (light parchment) for the label/icon so it's legible in both themes
  against `--blue`. Icon stroke inherits.
- Remove the `1px var(--line)` border and `--paper-raised` bg.
- Hover: subtle — `--blue-strong` background.
- `.nav-kbd` "C" badge: right-aligned, subtle on the teal (translucent, e.g.
  border/text tuned so it's quiet). Keep `--radius-small`.

## Files touched

- `templates/web/partials/_workspace_switcher.html` — rewrite as popover.
- `templates/web/partials/_sidebar.html` — reorder nav rows; replace the
  Settings row + theme button with `.util-row`; Capture markup unchanged
  (styling only).
- `templatetags/web_extras.py` — add `sun`, `moon`; change `activity` glyph.
- `static/web/app.css` — new `.ws-switch`/`.ws-menu`, `.util-row`/`.util-btn`;
  remove/replace `.theme-toggle`; restyle `.capture-btn`; drop the old
  `.workspace-switcher select` rules if any.

## Out of scope

- No backend changes beyond reusing `web:switch_workspace`.
- No "+ New workspace" creation flow (may be a cloud/entitlement concern).
- The `+ Area` inline add input keeps its current behavior.
- No mobile-drawer behavior changes beyond inheriting the new styles.

## Verification

Run the app, load Home, and confirm: switcher opens a styled popover (grouped by
org, active checked, closes on outside/Esc), nav order is Home·Attention·Triage·
In Progress·Roadmap·Activity with distinct icons, bottom row is a compact
icon utility row, Capture is a solid teal primary. Toggle theme both directions
and re-check all four in dark + light. Confirm no literal hex/radius were added
(`git diff` on app.css).
