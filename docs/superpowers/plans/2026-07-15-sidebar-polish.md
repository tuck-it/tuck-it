# Sidebar Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the tuckit sidebar viewport-pinned (Settings always reachable), smoothly/consistently collapsible, and drag-resizable with a persisted width.

**Architecture:** Pure CSS + a small vanilla-JS behavior file. The sidebar becomes `position: sticky; height: 100dvh` so it pins to the viewport and scrolls independently. Its width is driven by a `--sidebar-w` CSS variable with a `flex-basis` transition; collapse just overrides that variable to `60px`. A new `sidebar.js` handles pointer/keyboard resize and persists the width to `localStorage`, restored pre-paint in `base.html`.

**Tech Stack:** Django templates, static CSS (`app.css`), vanilla JS (no framework), pytest for structural (string-presence) tests.

## Global Constraints

- Desktop-only changes (`@media (min-width: 768px)` / default). Mobile off-canvas shell (`@media (max-width: 767px)`) MUST remain unaffected — no resize handle, drawer still works.
- CSS: `var(--token)` ONLY. No literal hex, no hardcoded radius. `test_new_sidebar_css_uses_no_raw_hex` fails on any hex in `app.css`.
- Available tokens: `--ease` = `cubic-bezier(0.16, 1, 0.3, 1)`, `--radius-small` = `9px`, `--blue-soft`, `--line`, `--paper-deep`, `--overlay`.
- Resize bounds: min **180px**, max **420px**, default **220px**, collapsed rail **60px**, keyboard step **16px**.
- `localStorage` keys: existing `sidebar-collapsed` ("0"/"1"), new `sidebar-width` (integer px string).
- Do NOT touch `tokens.brand.css` / `tokens.product.css` (width is a component concern; defaults live in `app.css`).
- Run tests from the `tuckit/` repo root with `uv run pytest`.
- Spec: `docs/superpowers/specs/2026-07-15-sidebar-polish-design.md`.

---

### Task 1: Viewport-pinned, resizable-shell CSS

Pin the sidebar to the viewport height, give it independent scroll, and drive its width from `--sidebar-w` with an animated `flex-basis`. This fixes the "Settings below the fold" problem (issue 3) and lays the width-variable groundwork for animation + resize.

**Files:**
- Modify: `tuckit/tuckit/web/static/web/app.css` (the `.sidebar` rule at ~line 15; add a `:root` default near the top of the file)
- Test: `tuckit/tests/web/test_sidebar.py`

**Interfaces:**
- Produces: CSS variable `--sidebar-w` (default `220px`) on `:root`, consumed by `.sidebar { flex-basis }`. Later tasks override `--sidebar-w` (collapse → on `.sidebar`; resize → inline on `<html>`).

- [ ] **Step 1: Write the failing test**

Add to `tuckit/tests/web/test_sidebar.py`:

```python
def test_sidebar_shell_is_pinned_and_width_variable():
    css = APP_CSS.read_text(encoding="utf-8")
    # Viewport-pinned, self-scrolling shell
    assert "position: sticky" in css
    assert "100dvh" in css
    assert "overflow-y: auto" in css
    # Width driven by a variable with an animated flex-basis
    assert "--sidebar-w: 220px" in css            # :root default
    assert "var(--sidebar-w, 220px)" in css        # consumed by .sidebar
    assert "transition: flex-basis" in css
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_sidebar_shell_is_pinned_and_width_variable -v`
Expected: FAIL (assertions on strings not yet in `app.css`).

- [ ] **Step 3: Add the `:root` width default**

Near the very top of `tuckit/tuckit/web/static/web/app.css` (immediately before the `.app` rule at line 13), add:

```css
:root { --sidebar-w: 220px; }
```

- [ ] **Step 4: Rewrite the `.sidebar` rule**

Replace the existing `.sidebar` rule (currently lines ~15-23):

```css
.sidebar {
  flex: 0 0 220px;
  background: var(--paper-deep);
  border-right: 1px solid var(--line);
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
```

with:

```css
.sidebar {
  flex: 0 0 var(--sidebar-w, 220px);
  transition: flex-basis .2s var(--ease);
  position: sticky;
  top: 0;
  align-self: flex-start;      /* don't stretch to .app (document) height */
  height: 100dvh;              /* always the viewport height */
  overflow-x: hidden;          /* clip labels while width animates */
  overflow-y: auto;            /* sidebar scrolls independently when tall */
  background: var(--paper-deep);
  border-right: 1px solid var(--line);
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
```

(The existing `@media (prefers-reduced-motion: reduce) { .sidebar { transition: none; } }` block at ~line 1491 already disables this new `flex-basis` transition — no change needed there.)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/web/test_sidebar.py::test_sidebar_shell_is_pinned_and_width_variable -v`
Expected: PASS

- [ ] **Step 6: Run the full sidebar + design-system suite (no regressions)**

Run: `uv run pytest tests/web/test_sidebar.py tests/web/test_design_system.py -v`
Expected: PASS (notably `test_new_sidebar_css_uses_no_raw_hex` and `test_collapsed_rail_css_present`).

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): pin sidebar to viewport height and drive width via --sidebar-w"
```

---

### Task 2: Consistent, animated collapse

Make the collapsed rail use the width variable (so the transition animates the collapse) and keep the collapse chevron at the **top** in both states instead of dropping below the workspace switcher. Fixes issue 1.

**Files:**
- Modify: `tuckit/tuckit/web/static/web/app.css` (collapsed block at ~lines 1419-1439)
- Test: `tuckit/tests/web/test_sidebar.py`

**Interfaces:**
- Consumes: `--sidebar-w` / `flex-basis` transition from Task 1.
- Produces: collapsed state sets `--sidebar-w: 60px` on `.sidebar`; `.side-collapse` gets `order: -1` inside the collapsed column so the chevron sits first (top).

- [ ] **Step 1: Write the failing test**

Add to `tuckit/tests/web/test_sidebar.py`:

```python
def test_collapse_animates_and_keeps_chevron_on_top():
    css = APP_CSS.read_text(encoding="utf-8")
    # Collapse overrides the width variable (so flex-basis transition animates it)
    assert "html.sidebar-collapsed .sidebar { --sidebar-w: 60px; }" in css
    # Old instant flex-basis swap is gone
    assert "html.sidebar-collapsed .sidebar { flex-basis: 60px; }" not in css
    # Chevron is pulled to the top of the collapsed column
    assert "html.sidebar-collapsed .side-collapse { order: -1; }" in css
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_collapse_animates_and_keeps_chevron_on_top -v`
Expected: FAIL.

- [ ] **Step 3: Swap the collapsed width declaration to the variable**

In `tuckit/tuckit/web/static/web/app.css`, inside `@media (min-width: 768px)` (~line 1423), replace:

```css
  html.sidebar-collapsed .sidebar { flex-basis: 60px; }
```

with:

```css
  html.sidebar-collapsed .sidebar { --sidebar-w: 60px; }
```

- [ ] **Step 4: Keep the chevron on top in the collapsed column**

The collapsed top region already stacks vertically via `html.sidebar-collapsed .side-top { flex-direction: column; gap: 6px; }` (~line 1434). Immediately after that line, add:

```css
  html.sidebar-collapsed .side-collapse { order: -1; }
```

This moves the chevron to the top of the stack (DOM order is workspace → activity → chevron; `order: -1` floats the chevron above the workspace icon). The activity button is already hidden collapsed via `.side-top-act:not(.side-collapse) { display: none; }`.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/web/test_sidebar.py::test_collapse_animates_and_keeps_chevron_on_top -v`
Expected: PASS

- [ ] **Step 6: Manual smoke check**

Run the dev server (`uv run python manage.py runserver` from the repo that wires the app, or via `tuckit-cloud`), open a workspace, click the chevron: width should glide 220↔60px, and the chevron should stay at the top in both states.

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): animate sidebar collapse and pin the chevron to the top"
```

---

### Task 3: Resize handle markup + styles

Add the drag handle element and its CSS (idle/hover/focus, drag-in-progress cursor, hidden when collapsed and on mobile). Behavior comes in Task 4. Fixes issue 2 (visual half).

**Files:**
- Modify: `tuckit/tuckit/web/templates/web/partials/_sidebar.html` (add handle before `</aside>`)
- Modify: `tuckit/tuckit/web/static/web/app.css` (new `.side-resize` styles; hide rules in collapsed block and mobile media query)
- Test: `tuckit/tests/web/test_sidebar.py`

**Interfaces:**
- Produces: `.side-resize` element (`role="separator"`, `tabindex="0"`, `aria-orientation="vertical"`, `aria-valuemin="180"`, `aria-valuemax="420"`) that Task 4's `sidebar.js` binds pointer/keyboard handlers to; `html.resizing` class toggled by Task 4 to freeze the width transition.

- [ ] **Step 1: Write the failing test**

Add to `tuckit/tests/web/test_sidebar.py`:

```python
@pytest.mark.django_db
def test_resize_handle_rendered(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'class="side-resize"' in body
    assert 'role="separator"' in body
    assert 'aria-orientation="vertical"' in body


def test_resize_handle_css_present():
    css = APP_CSS.read_text(encoding="utf-8")
    assert ".side-resize" in css
    assert "col-resize" in css                       # resize cursor
    assert "html.resizing .sidebar { transition: none; }" in css   # 1:1 tracking
    assert "html.sidebar-collapsed .side-resize { display: none; }" in css  # hidden collapsed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_resize_handle_rendered tests/web/test_sidebar.py::test_resize_handle_css_present -v`
Expected: FAIL.

- [ ] **Step 3: Add the handle markup**

In `tuckit/tuckit/web/templates/web/partials/_sidebar.html`, add this as the last child of `<aside class="sidebar">`, immediately before the closing `</aside>` (after the `capture-btn` button):

```html
  <div class="side-resize" role="separator" aria-orientation="vertical"
       aria-label="Resize sidebar" tabindex="0"
       aria-valuemin="180" aria-valuemax="420" aria-valuenow="220"></div>
```

- [ ] **Step 4: Add the handle styles**

Append to `tuckit/tuckit/web/static/web/app.css` (a sensible home is right after the collapsed-sidebar block, ~line 1439):

```css
/* --- Drag-to-resize handle (desktop, expanded only) --- */
.side-resize {
  position: absolute; top: 0; right: 0; bottom: 0;
  width: 6px; z-index: 5;
  cursor: col-resize; background: none;
  touch-action: none;              /* let pointer events drive resize on touch */
}
.side-resize:hover,
.side-resize:focus-visible { background: var(--blue-soft); outline: none; }
html.resizing { cursor: col-resize; user-select: none; }
html.resizing .sidebar { transition: none; }   /* track the cursor 1:1 while dragging */
html.sidebar-collapsed .side-resize { display: none; }
```

- [ ] **Step 5: Hide the handle on mobile**

In the `@media (max-width: 767px)` block, next to the existing `.side-collapse { display: none; }` (~line 1488), add:

```css
  .side-resize { display: none; }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_sidebar.py::test_resize_handle_rendered tests/web/test_sidebar.py::test_resize_handle_css_present tests/web/test_sidebar.py::test_new_sidebar_css_uses_no_raw_hex -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/partials/_sidebar.html tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): add sidebar resize handle markup and styles"
```

---

### Task 4: Resize behavior + persistence + no-flash restore

Wire the handle: pointer drag and keyboard arrows adjust `--sidebar-w` (clamped), persist to `localStorage`, and restore pre-paint so there's no width flash. Completes issue 2 and makes the width durable.

**Files:**
- Create: `tuckit/tuckit/web/static/web/sidebar.js`
- Modify: `tuckit/tuckit/web/templates/web/base.html` (extend the pre-paint restore script; load `sidebar.js`)
- Test: `tuckit/tests/web/test_sidebar.py`

**Interfaces:**
- Consumes: `.side-resize` element and `html.resizing` class from Task 3; `--sidebar-w` variable from Task 1.
- Produces: `localStorage["sidebar-width"]` (integer px string). No exported functions — the file is a self-invoking IIFE bound on load.

- [ ] **Step 1: Write the failing test**

Add to `tuckit/tests/web/test_sidebar.py`:

```python
SIDEBAR_JS = APP_CSS.parent / "sidebar.js"


@pytest.mark.django_db
def test_sidebar_js_loaded_and_width_restored(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert "sidebar.js" in body                 # behavior script loaded
    assert "sidebar-width" in body              # pre-paint restore reads the key


def test_sidebar_js_clamps_to_bounds():
    js = SIDEBAR_JS.read_text(encoding="utf-8")
    assert "180" in js and "420" in js          # min/max bounds
    assert "sidebar-width" in js                # persists under this key
    assert "resizing" in js                     # toggles the no-transition drag class
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_sidebar_js_loaded_and_width_restored tests/web/test_sidebar.py::test_sidebar_js_clamps_to_bounds -v`
Expected: FAIL (`sidebar.js` does not exist; base.html doesn't load it).

- [ ] **Step 3: Create `sidebar.js`**

Create `tuckit/tuckit/web/static/web/sidebar.js`:

```javascript
/* Sidebar drag-to-resize. Adjusts the --sidebar-w custom property live while
   dragging (or via arrow keys when the handle is focused), clamps to
   [MIN, MAX], and persists the result to localStorage["sidebar-width"]. The
   pre-paint script in base.html restores that value before first paint. */
(function () {
  var MIN = 180, MAX = 420, STEP = 16;
  var root = document.documentElement;
  var handle = document.querySelector(".side-resize");
  var sidebar = document.querySelector(".sidebar");
  if (!handle || !sidebar) return;

  function clamp(w) { return Math.max(MIN, Math.min(MAX, w)); }

  function currentWidth() {
    var stored = parseInt(localStorage.getItem("sidebar-width"), 10);
    if (stored >= MIN && stored <= MAX) return stored;
    return 220;
  }

  function apply(w, persist) {
    root.style.setProperty("--sidebar-w", w + "px");
    handle.setAttribute("aria-valuenow", String(w));
    if (persist) localStorage.setItem("sidebar-width", String(w));
  }

  var dragging = false;

  handle.addEventListener("pointerdown", function (e) {
    dragging = true;
    root.classList.add("resizing");
    handle.setPointerCapture(e.pointerId);
    e.preventDefault();
  });

  handle.addEventListener("pointermove", function (e) {
    if (!dragging) return;
    var left = sidebar.getBoundingClientRect().left;
    apply(clamp(Math.round(e.clientX - left)), false);
  });

  function endDrag(e) {
    if (!dragging) return;
    dragging = false;
    root.classList.remove("resizing");
    if (handle.hasPointerCapture(e.pointerId)) handle.releasePointerCapture(e.pointerId);
    var w = parseInt(getComputedStyle(root).getPropertyValue("--sidebar-w"), 10);
    if (w) localStorage.setItem("sidebar-width", String(w));
  }
  handle.addEventListener("pointerup", endDrag);
  handle.addEventListener("pointercancel", endDrag);

  handle.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") { apply(clamp(currentWidth() - STEP), true); e.preventDefault(); }
    else if (e.key === "ArrowRight") { apply(clamp(currentWidth() + STEP), true); e.preventDefault(); }
  });
})();
```

- [ ] **Step 4: Restore the width pre-paint in `base.html`**

In `tuckit/tuckit/web/templates/web/base.html`, inside the existing head IIFE (the block that restores theme and `sidebar-collapsed`, ~lines 16-24), add the width restore right after the `sidebar-collapsed` line:

```javascript
      if (localStorage.getItem("sidebar-collapsed") === "1") {
        document.documentElement.classList.add("sidebar-collapsed");
      }
      var sw = parseInt(localStorage.getItem("sidebar-width"), 10);
      if (sw >= 180 && sw <= 420) {
        document.documentElement.style.setProperty("--sidebar-w", sw + "px");
      }
```

- [ ] **Step 5: Load `sidebar.js`**

In the `<head>` of `base.html`, next to the other `defer` scripts (after the `command_palette.js`/alpine lines, ~line 30), add:

```html
  <script defer src="{% static 'web/sidebar.js' %}"></script>
```

(`defer` runs it after the DOM is parsed, so `.side-resize` exists when the IIFE queries for it.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_sidebar.py::test_sidebar_js_loaded_and_width_restored tests/web/test_sidebar.py::test_sidebar_js_clamps_to_bounds -v`
Expected: PASS

- [ ] **Step 7: Full suite + manual smoke check**

Run: `uv run pytest tests/web/ -v`
Expected: PASS (whole web suite).

Manual: drag the right edge — width tracks the cursor between 180 and 420px and stops at the bounds; reload — the width is retained with no flash; focus the handle (Tab) and press ←/→ — width steps by 16px; collapse — rail is 60px and the handle disappears; expand — the stored width returns.

- [ ] **Step 8: Commit**

```bash
git add tuckit/web/static/web/sidebar.js tuckit/web/templates/web/base.html tests/web/test_sidebar.py
git commit -m "feat(web): drag/keyboard sidebar resize with persisted width"
```

---

## Notes / known trade-offs

- When the sidebar's own content overflows and a scrollbar appears, it overlays the right-edge handle by the scrollbar width. Acceptable for now (sidebar content rarely exceeds viewport at these widths); revisit with `scrollbar-gutter` only if it bites.
- `100dvh` is used (not `100vh`) so mobile browser chrome doesn't clip the pinned column; on desktop the two are equivalent.
- Commit steps assume the tuckit repo's normal git workflow — run them per the maintainer's commit preference.
