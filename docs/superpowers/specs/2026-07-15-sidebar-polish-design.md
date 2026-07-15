# Sidebar polish — design

**Date:** 2026-07-15
**Repo:** tuckit (public core)
**Status:** approved, ready for implementation plan

Polish pass on the sidebar shipped in v0.11.0 (sidebar IA redesign). Three
user-reported problems, one cohesive fix. Desktop (≥768px) only — the mobile
off-canvas shell is unchanged.

## Problems

1. **Toggle is unnatural.** Collapse jumps instantly (no animation) because the
   collapsed state swaps `flex-basis: 220px → 60px` with no transition. The
   collapse chevron also *moves*: expanding keeps `.side-top` a horizontal row,
   collapsing switches it to `flex-direction: column`, dropping the chevron
   below the workspace switcher.
2. **Sidebar can't be resized.** Fixed at 220px, no drag handle.
3. **Sidebar isn't pinned to the viewport.** `.sidebar` is a flex child of
   `.app` (`min-height: 100vh`), so it stretches to *document* height. The
   `nav-spacer` pushes Settings to the bottom, but that bottom is the document
   bottom, not the viewport bottom — so Settings sits below the fold and needs
   scrolling to reach.

## Decisions (from brainstorming)

- Keep **both** collapse (60px icon rail via chevron) **and** drag-resize; they
  are independent controls.
- Collapse button stays **at the top** in both states — never relocates below
  the workspace switcher.
- Persist the resized width (like the existing collapsed-state persistence).

## Design

### A. Viewport-pinned, self-scrolling sidebar (fixes #3)

```css
.sidebar {
  position: sticky;
  top: 0;
  align-self: flex-start;   /* don't stretch to .app height */
  height: 100dvh;           /* always viewport height; dvh handles mobile chrome */
  overflow-y: auto;         /* sidebar scrolls independently when its own content overflows */
}
```

`nav-spacer` (already `flex: 1`) now pushes `util-row` (Settings + theme) to the
viewport bottom, independent of main-content height. When the sidebar's own
content is taller than the viewport, only the sidebar scrolls.

### B. Animated, position-stable toggle (fixes #1)

- Drive width from a CSS variable and transition it:
  ```css
  .sidebar { flex-basis: var(--sidebar-w, 220px); transition: flex-basis .2s var(--ease); }
  ```
- Collapse sets `--sidebar-w: 60px` (on `.sidebar`) → the transition animates
  the width change. Labels still `display:none` when collapsed (can't animate),
  but width glides; `overflow: hidden; white-space: nowrap` prevents label
  reflow mid-animation.
- **Keep the chevron at the top in both states.** Remove the
  `html.sidebar-collapsed .side-top { flex-direction: column }` reflow that
  drops the chevron. In the collapsed rail the top cluster stacks vertically
  with the **chevron first** (via flex `order`), workspace shrunk to its icon,
  activity button hidden.
- `prefers-reduced-motion: reduce` removes the `flex-basis` transition.

### C. Drag-to-resize (fixes #2)

- Add a thin handle on the sidebar's right edge:
  `<div class="side-resize" role="separator" aria-orientation="vertical"
   aria-label="Resize sidebar" tabindex="0">`.
- Pointer drag: on `pointerdown` capture the pointer and add a `.resizing` class
  to `<html>` (which sets `transition: none` so width tracks the cursor 1:1); on
  `pointermove` set `--sidebar-w` clamped to **[180px, 420px]**; on `pointerup`
  release capture, drop `.resizing`, and persist.
- Keyboard: when the handle has focus, ←/→ adjust width by 16px (clamped) and
  persist.
- Desktop only (≥768px). Hidden when collapsed and on mobile.
- Logic lives in a new self-contained file `web/static/web/sidebar.js`.

### D. Persistence & no-flash restore (fixes #1/#2 durability)

- Persist `localStorage["sidebar-width"]` (px integer). Collapsed state keeps
  using the existing `localStorage["sidebar-collapsed"]`.
- Extend the existing pre-paint inline script in `base.html` (already restoring
  `sidebar-collapsed`) to also set `--sidebar-w` inline on
  `document.documentElement` before first paint — no width flash.
- **Cascade for width precedence:**
  - Default `--sidebar-w: 220px` declared on `:root` (in `app.css`).
  - Resize writes `--sidebar-w` inline on `<html>` (inherited by `.sidebar`).
  - Collapse declares `--sidebar-w: 60px` directly on `.sidebar`, which wins for
    that element over the inherited `<html>` value.
  - Result: collapsing ignores the stored width (shows 60px); expanding restores
    the stored width.

## Defaults

| Setting        | Value  |
| -------------- | ------ |
| Default width  | 220px  |
| Min width      | 180px  |
| Max width      | 420px  |
| Collapsed rail | 60px   |
| Keyboard step  | 16px   |
| Transition     | 0.2s var(--ease) |

## Files touched

- `tuckit/web/static/web/app.css` — sticky/`100dvh` layout, `flex-basis`
  variable + transition, collapsed `side-top` order fix, `.side-resize` +
  `.resizing` styles, `:root` width defaults.
- `tuckit/web/templates/web/partials/_sidebar.html` — add `.side-resize` handle;
  ensure chevron stays top in collapsed order.
- `tuckit/web/templates/web/base.html` — one line in the pre-paint script to
  restore `--sidebar-w`; load `sidebar.js`.
- `tuckit/web/static/web/sidebar.js` — **new**, drag + keyboard resize logic and
  persistence.

## Out of scope

- Mobile off-canvas shell (unchanged).
- Any change to sidebar content, IA, or navigation items.
- Design tokens in `tokens.brand.css` (width is a component concern; defaults
  live in `app.css`). No literal hex/radius — `var(--token)` only per repo rules.

## Testing

- Sidebar stays pinned to the viewport; Settings visible at the bottom with both
  short and very tall main content, and at short viewport heights.
- Collapse/expand animates smoothly; chevron stays at the top in both states.
- Drag resizes within [180, 420]; width persists across reload; no width flash
  on load.
- Collapsed state shows the 60px rail regardless of stored width; expanding
  restores it.
- Keyboard: handle focus + ←/→ resizes and persists.
- `prefers-reduced-motion` disables the width transition.
- Mobile (<768px) unaffected: no handle, off-canvas menu works.
