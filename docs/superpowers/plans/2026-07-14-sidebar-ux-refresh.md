# Sidebar UX Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the tuckit left sidebar (IA grouping, Linear-style workspace top, stronger active state, area `⋮` menu, collapse mode, Cmd+K palette) without changing the design system or adding backend features.

**Architecture:** Pure Django-template + CSS + vanilla/Alpine JS change in the public `tuckit` repo. No models, migrations, views, URLs, or context processors change — everything reuses existing context (`areas`, `triage_count`, `switchable_workspaces`, `current_workspace`) and existing routes. New UI (command palette, collapse) is client-only.

**Tech Stack:** Django templates, Alpine.js (vendored), htmx (vendored), SortableJS (vendored), a single components CSS file (`app.css`), design tokens in `tokens.brand.css` / `tokens.product.css`.

## Global Constraints

- **Colors/radius via `var(--token)` ONLY** — no literal hex, no hardcoded radius. Surfaces use `--radius` (14px), controls `--radius-small` (9px). Accent = single teal `--blue`. (px widths/paddings/positions are allowed; only colors and radii must be tokens.)
- All sidebar **component** CSS lives in `tuckit/web/static/web/app.css`. Any genuinely new *token* goes in `tokens.product.css` only — never `base.css`, never brand, never inline.
- `<link>` order stays brand → product → base → app (`base.html:8-11`).
- Public repo: **no** billing/cloud/entitlement/pricing content.
- Spec + this plan stay **untracked** in `docs/superpowers/` (never committed to public `tuckit`).
- Repo root for commands: `/Users/goddessana/Developments/tuckit-projects/tuckit`. Run tests with `uv run pytest`.
- Reuse existing partials/logic wherever possible (workspace popover Alpine, theme-toggle Alpine, area rename/delete htmx, SortableJS reorder). Do not duplicate them.
- Out of scope (do NOT build): Starred, Recently Viewed, Archived view, My Filters, Tags-as-destination, per-area color/icon, archiving from the `⋮` menu.

---

## File Structure

**Modify:**
- `tuckit/web/templatetags/web_extras.py` — add `search` and `dots` icons to `_ICON_PATHS`.
- `tuckit/web/templates/web/base.html` — add `pal` state + `⌘K` hotkey + palette include; add pre-paint collapse script + `toggleSidebar()`.
- `tuckit/web/templates/web/partials/_sidebar.html` — top region (workspace card + bell + collapse + search pill), MAIN header, Areas header `+`, bottom stack (Light mode row), bell removed from bottom.
- `tuckit/web/templates/web/partials/_workspace_switcher.html` — make it flex-fill inside the new top row (minor).
- `tuckit/web/templates/web/partials/_area_row.html` — replace inline actions with a `⋮` popover (Rename / Delete).
- `tuckit/web/static/web/app.css` — all the above component styles + collapsed-mode rules + palette + pill.

**Create:**
- `tuckit/web/templates/web/partials/_command_palette.html` — Cmd+K overlay partial.
- `tuckit/web/static/web/command_palette.js` — palette Alpine component.
- `tests/web/test_sidebar.py` — render smoke tests.

---

### Task 1: Add `search` and `dots` icons

**Files:**
- Modify: `tuckit/web/templatetags/web_extras.py:27-45` (the `_ICON_PATHS` dict)
- Test: `tests/web/test_sidebar.py`

**Interfaces:**
- Produces: `{% icon "search" %}` and `{% icon "dots" %}` render non-empty `<svg>` paths (used by later tasks for the search pill and the area `⋮` menu).

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_sidebar.py`:

```python
from tuckit.web.templatetags.web_extras import icon


def test_search_and_dots_icons_have_paths():
    assert "<path" in icon("search")
    assert "<path" in icon("dots") or "<circle" in icon("dots")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_search_and_dots_icons_have_paths -v`
Expected: FAIL — both icons return empty `<svg>` (no matching key).

- [ ] **Step 3: Add the icons**

In `web_extras.py`, add two entries to `_ICON_PATHS` (after `"menu"`):

```python
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "dots": '<circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/>',
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/web/test_sidebar.py::test_search_and_dots_icons_have_paths -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tuckit/web/templatetags/web_extras.py tests/web/test_sidebar.py
git commit -m "feat(web): add search and dots icons for sidebar refresh"
```

---

### Task 2: Command palette (Cmd+K)

Built before the sidebar top region because the search pill (Task 3) triggers it. The palette navigates to existing destinations only; no backend.

**Files:**
- Create: `tuckit/web/templates/web/partials/_command_palette.html`
- Create: `tuckit/web/static/web/command_palette.js`
- Modify: `tuckit/web/templates/web/base.html:23-25` (load the script), `:33-35` (add `pal` state + `⌘K` hotkey), `:57` (include the partial)
- Modify: `tuckit/web/static/web/app.css` (palette styles, append near capture styles ~line 1188)
- Test: `tests/web/test_sidebar.py`

**Interfaces:**
- Consumes: body Alpine scope exposes `pal` (bool) and `cap` (bool, existing). Context var `areas` (list of Area with `.name`, `.slug`), `current_workspace`.
- Produces: setting `pal = true` opens the palette; the search pill (Task 3) and `⌘K` both do this. The palette rows are anchors/buttons with `data-label`.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_sidebar.py`:

```python
import pytest


@pytest.mark.django_db
def test_command_palette_rendered_with_area_rows(client_local, workspace):
    from tuckit.core.services.areas import create_area
    create_area(workspace, "Backend")
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'id="command-palette"' in body           # overlay present
    assert 'data-label="Backend"' in body           # area is a command row
    assert 'data-label="Home"' in body               # static nav command
    assert "command_palette.js" in body              # component script loaded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_command_palette_rendered_with_area_rows -v`
Expected: FAIL — palette markup not present.

- [ ] **Step 3: Create the palette JS component**

Create `tuckit/web/static/web/command_palette.js`:

```js
/* Cmd+K palette. Rows are rendered server-side with data-label; this filters
   them client-side, supports up/down/enter, and clicks the active row.
   No backend — every row is a link or a local action. */
function commandPalette() {
  return {
    q: "",
    active: 0,
    rows() {
      return Array.prototype.slice.call(this.$refs.list.querySelectorAll("[data-label]"));
    },
    visible() {
      var q = this.q.trim().toLowerCase();
      return this.rows().filter(function (r) {
        return !q || r.dataset.label.toLowerCase().indexOf(q) !== -1;
      });
    },
    open() {
      this.q = "";
      this.active = 0;
      this.$nextTick(function () {
        this.filter();
        this.$refs.search.focus();
      }.bind(this));
    },
    filter() {
      var vis = this.visible();
      this.rows().forEach(function (r) { r.style.display = "none"; });
      vis.forEach(function (r) { r.style.display = ""; });
      if (this.active >= vis.length) this.active = Math.max(0, vis.length - 1);
      this.highlight(vis);
    },
    highlight(vis) {
      var list = vis || this.visible();
      this.rows().forEach(function (r) { r.classList.remove("cmdk-row--active"); });
      if (list[this.active]) list[this.active].classList.add("cmdk-row--active");
    },
    move(d) {
      var vis = this.visible();
      if (!vis.length) return;
      this.active = (this.active + d + vis.length) % vis.length;
      this.highlight(vis);
      vis[this.active].scrollIntoView({ block: "nearest" });
    },
    choose() {
      var vis = this.visible();
      if (vis[this.active]) vis[this.active].click();
    },
  };
}
```

- [ ] **Step 4: Create the palette partial**

Create `tuckit/web/templates/web/partials/_command_palette.html`:

```django
{% load web_extras %}
<div id="command-palette" class="cmdk-overlay" x-show="pal" x-cloak
     x-data="commandPalette()" x-effect="if (pal) open()"
     x-on:click.self="pal = false"
     x-on:keydown.escape="pal = false">
  <div class="cmdk-box" role="dialog" aria-modal="true" aria-label="Command palette">
    <input class="cmdk-input" type="text" placeholder="Search…" x-ref="search"
           x-model="q" autocomplete="off" spellcheck="false"
           x-on:input="filter()"
           x-on:keydown.down.prevent="move(1)"
           x-on:keydown.up.prevent="move(-1)"
           x-on:keydown.enter.prevent="choose()">
    <div class="cmdk-list" x-ref="list">
      <a class="cmdk-row" data-label="Home" href="{% wurl 'web:home' %}">{% icon "home" %}<span>Home</span></a>
      <a class="cmdk-row" data-label="Inbox" href="{% wurl 'web:triage' %}">{% icon "triage" %}<span>Inbox</span></a>
      <a class="cmdk-row" data-label="Board" href="{% wurl 'web:roadmap' %}">{% icon "roadmap" %}<span>Board</span></a>
      {% for a in areas %}
        <a class="cmdk-row" data-label="{{ a.name }}" href="{% wurl 'web:area' a.slug %}">{% icon "area" %}<span>{{ a.name }}</span></a>
      {% endfor %}
      <a class="cmdk-row" data-label="Settings" href="{% url 'web:settings_workspace' current_workspace.org.slug current_workspace.slug %}">{% icon "settings" %}<span>Settings</span></a>
      <button class="cmdk-row" type="button" data-label="Capture new item"
              x-on:click="pal = false; cap = true; $nextTick(() => $refs.captureInput && $refs.captureInput.focus())">{% icon "plus" %}<span>Capture new item</span></button>
    </div>
  </div>
</div>
```

- [ ] **Step 5: Wire palette into base.html**

In `base.html`, load the script after the sortable vendor line (`:25`):

```django
  <script src="{% static 'web/vendor/sortable.min.js' %}"></script>
  <script defer src="{% static 'web/command_palette.js' %}"></script>
```

Extend the body `x-data` (`:34`) to add `pal: false` (keep `cap`, `menu`, `trapFocus` unchanged):

```django
      x-data="{cap: false, menu: false, pal: false, trapFocus(e){ if(!this.menu) return; const f=[...this.$refs.sidebarWrap.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select,textarea')].filter(el=>el.offsetParent!==null); if(!f.length) return; const first=f[0], last=f[f.length-1]; if(e.shiftKey && document.activeElement===first){ e.preventDefault(); last.focus(); } else if(!e.shiftKey && document.activeElement===last){ e.preventDefault(); first.focus(); } }}"
```

Extend the window keydown (`:35`) to add the `⌘K` / `Ctrl+K` opener (keep the existing `c` capture handler):

```django
      x-on:keydown.window="if (!cap && $event.key === 'c' && !['INPUT','TEXTAREA'].includes($event.target.tagName)) { cap = true; $nextTick(() => $refs.captureInput && $refs.captureInput.focus()) }"
      x-on:keydown.k.window.prevent.stop="if ($event.metaKey || $event.ctrlKey) pal = true">
```

Include the partial next to the capture modal (`:57`):

```django
  {% include "web/partials/_capture_modal.html" %}
  {% include "web/partials/_command_palette.html" %}
```

- [ ] **Step 6: Add palette CSS**

Append to `app.css` (after the `.nav-kbd` block, ~line 1187), tokens only:

```css
/* --- Cmd+K command palette --- */
.cmdk-overlay {
  position: fixed; inset: 0; z-index: 60;
  display: flex; align-items: flex-start; justify-content: center;
  padding-top: 12vh; background: var(--overlay);
}
.cmdk-box {
  width: min(560px, 92vw);
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: 0 12px 40px var(--shadow);
  overflow: hidden;
}
.cmdk-input {
  width: 100%; font: inherit; font-size: 15px;
  padding: 14px 16px; border: none; border-bottom: 1px solid var(--line);
  background: none; color: var(--ink);
}
.cmdk-input:focus { outline: none; }
.cmdk-list { max-height: 50vh; overflow-y: auto; padding: 6px; }
.cmdk-row {
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 9px 10px; border: none; background: none; font: inherit;
  color: var(--ink); text-align: left; text-decoration: none; cursor: pointer;
  border-radius: var(--radius-small);
}
.cmdk-row .icon { stroke: var(--ink-faint); }
.cmdk-row:hover, .cmdk-row--active { background: var(--blue-soft); }
.cmdk-row--active .icon { stroke: var(--blue); }
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `uv run pytest tests/web/test_sidebar.py::test_command_palette_rendered_with_area_rows -v`
Expected: PASS

- [ ] **Step 8: Manual smoke**

Run the app (`uv run python manage.py runserver` from repo root, or the project's run skill), load a workspace, press `⌘K` (mac) / `Ctrl+K`: palette opens, typing filters, ↑/↓ moves highlight, Enter navigates, Esc closes.

- [ ] **Step 9: Commit**

```bash
git add tuckit/web/static/web/command_palette.js tuckit/web/templates/web/partials/_command_palette.html tuckit/web/templates/web/base.html tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): add Cmd+K command palette over existing destinations"
```

---

### Task 3: Sidebar top region — workspace card + bell + search pill

Replaces the `tuckit` wordmark with the workspace switcher at the very top, moves the Activity bell up beside it, and adds a `Search ⌘K` pill that opens the palette. (Collapse button is added in Task 5.)

**Files:**
- Modify: `tuckit/web/templates/web/partials/_sidebar.html:2-4` (remove `.brand`, build top region), `:30-32` (remove bell from bottom `util-row`)
- Modify: `tuckit/web/templates/web/partials/_workspace_switcher.html:3` (flex-fill wrap)
- Modify: `tuckit/web/static/web/app.css:32` (remove/repurpose `.brand`), `:35` (`.ws-switch-wrap` flex), and append new `.side-top` / `.search-pill` styles
- Test: `tests/web/test_sidebar.py`

**Interfaces:**
- Consumes: `pal` (Task 2). `current_workspace`, `switchable_workspaces` (existing). `{% icon "search" %}` (Task 1).
- Produces: `.side-top` container holds the workspace switcher + `.side-top-act` bell; `.search-pill` opens `pal`.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_sidebar.py`:

```python
@pytest.mark.django_db
def test_top_region_has_workspace_and_search_no_wordmark(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'class="side-top"' in body
    assert 'class="ws-switch"' in body          # workspace switcher is at top
    assert 'class="search-pill"' in body        # search pill present
    # the old sidebar wordmark <div class="brand">tuckit</div> is gone
    assert '<div class="brand">tuckit</div>' not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_top_region_has_workspace_and_search_no_wordmark -v`
Expected: FAIL — `.brand` wordmark still present, no `.side-top`/`.search-pill`.

- [ ] **Step 3: Rebuild the top of `_sidebar.html`**

Replace lines 2-4 (`<aside class="sidebar">` … workspace include) with:

```django
<aside class="sidebar">
  <div class="side-top">
    {% include "web/partials/_workspace_switcher.html" %}
    <button class="side-top-act" type="button"
            aria-label="Activity" title="Activity"
            hx-get="{% wurl 'web:activity' %}?panel=1" hx-target="#panel">{% icon "activity" %}</button>
  </div>
  <button class="search-pill" type="button" x-on:click="pal = true">
    {% icon "search" %}<span class="nav-label">Search</span><kbd class="nav-kbd">⌘K</kbd>
  </button>
```

- [ ] **Step 4: Remove the bell from the bottom util-row**

In `_sidebar.html`, delete the `util-activity` button block (old `:30-32`) so the bottom `util-row` no longer contains the bell (Settings + theme stay for now; theme becomes a labeled row in Task 6):

```django
  <div class="util-row">
    <a class="util-btn util-settings{% if request.resolver_match.url_name == 'settings_workspace' or request.resolver_match.url_name == 'settings_org' %} util-btn--active{% endif %}"
       href="{% url 'web:settings_workspace' current_workspace.org.slug current_workspace.slug %}">{% icon "settings" %}<span class="util-label">Settings</span></a>
    <button class="util-btn util-theme" type="button"
            x-data="{theme: document.documentElement.dataset.theme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')}"
            x-on:click="theme = theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = theme; localStorage.setItem('theme', theme)"
            :aria-label="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'"
            :title="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'">
      <span x-show="theme === 'dark'">{% icon "sun" %}</span>
      <span x-show="theme !== 'dark'" style="display:none">{% icon "moon" %}</span>
    </button>
  </div>
```

- [ ] **Step 5: Make the workspace wrap flex-fill**

In `_workspace_switcher.html:3`, add a class so it fills the row (keep all existing attributes):

```django
<div class="ws-switch-wrap side-top-ws" x-data="{open: false}" x-on:keydown.escape="open = false">
```

- [ ] **Step 6: Update CSS**

In `app.css`, replace the `.brand` rule (`:32`) with the top-region styles and adjust `.ws-switch-wrap`:

```css
.side-top { display: flex; align-items: center; gap: 4px; padding: 0 4px 6px; }
.side-top-ws { flex: 1 1 auto; padding: 0 !important; }
.side-top-act {
  flex: 0 0 auto; width: 32px; height: 32px;
  display: grid; place-items: center;
  background: none; border: none; cursor: pointer;
  border-radius: var(--radius-small); color: var(--ink-faint);
}
.side-top-act:hover { background: var(--paper-raised); color: var(--ink); }
.side-top-act .icon { stroke: var(--ink-faint); }
.side-top-act:hover .icon { stroke: var(--ink); }
.ws-menu { min-width: 200px; }

.search-pill {
  display: flex; align-items: center; gap: 8px; width: 100%;
  margin: 0 0 8px; padding: 7px 10px;
  background: var(--paper-raised); border: 1px solid var(--line);
  border-radius: var(--radius-small);
  color: var(--ink-faint); font: inherit; cursor: pointer;
}
.search-pill:hover { border-color: var(--blue); color: var(--ink); }
.search-pill .icon { stroke: var(--ink-faint); }
.search-pill .nav-label { text-align: left; }
```

(`.ws-switch-wrap` keeps its base rule at `:35`; `.side-top-ws` overrides its padding so the popover still anchors correctly.)

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/web/test_sidebar.py::test_top_region_has_workspace_and_search_no_wordmark -v`
Expected: PASS

- [ ] **Step 8: Regression + manual smoke**

Run: `uv run pytest tests/web/ -q`
Expected: PASS (no test depended on the sidebar wordmark).
Manual: workspace dropdown still opens/switches; bell opens the Activity slide-over; Search pill opens the palette.

- [ ] **Step 9: Commit**

```bash
git add tuckit/web/templates/web/partials/_sidebar.html tuckit/web/templates/web/partials/_workspace_switcher.html tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): Linear-style workspace top with bell + search pill"
```

---

### Task 4: MAIN header, active accent bar, Inbox pill

**Files:**
- Modify: `tuckit/web/templates/web/partials/_sidebar.html:6` (add `.section` "Main" before the nav group)
- Modify: `tuckit/web/static/web/app.css:115` (accent bar on `.nav--active`), `:104` (`.nav-count` → pill)
- Test: `tests/web/test_sidebar.py`

**Interfaces:**
- Consumes: existing `.nav--active`, `.nav-count`, `triage_count`.
- Produces: no template contract for later tasks; visual only + a `.section` "Main" label.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_sidebar.py`:

```python
from pathlib import Path

APP_CSS = Path(__file__).resolve().parents[2] / "tuckit" / "web" / "static" / "web" / "app.css"


@pytest.mark.django_db
def test_main_section_header_present(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert ">Main</div>" in body


def test_active_nav_has_accent_bar_via_token():
    css = APP_CSS.read_text(encoding="utf-8")
    assert "inset 3px 0 0 var(--blue)" in css       # accent bar, token color
    assert ".nav-count" in css and "var(--blue-soft)" in css  # inbox pill uses token bg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py -k "main_section or accent_bar" -v`
Expected: FAIL — no "Main" header, no accent-bar rule, `.nav-count` still plain text.

- [ ] **Step 3: Add the MAIN header**

In `_sidebar.html`, add a section label immediately before the `<nav class="nav-group">` (old `:6`):

```django
  <div class="section">Main</div>
  <nav class="nav-group">
```

- [ ] **Step 4: Add the accent bar + Inbox pill CSS**

In `app.css`, update the active-nav rule (`:115`) to add the left accent bar (keep the background/color/weight):

```css
.nav.nav--active { background: var(--blue-soft); color: var(--ink); font-weight: 600; box-shadow: inset 3px 0 0 var(--blue); }
```

Replace the `.nav-count` rule (`:104`) with a rounded pill using existing tokens:

```css
.nav-count {
  min-width: 20px; padding: 1px 7px; border-radius: 999px;
  background: var(--blue-soft); color: var(--blue);
  font-family: var(--mono); font-size: 11px; font-weight: 600;
  font-variant-numeric: tabular-nums; text-align: center;
}
.nav-count:empty { display: none; }
```

(`.nav-count:empty { display: none }` keeps the badge hidden at zero, matching current behavior where `triage_count` renders empty.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_sidebar.py -k "main_section or accent_bar" -v`
Expected: PASS

- [ ] **Step 6: Manual smoke**

Load Home / an Area: the active row shows the teal left bar + soft background. Create a triage item so Inbox count > 0: it renders as a rounded teal pill; at zero it disappears.

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/partials/_sidebar.html tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): MAIN header, active accent bar, rounded Inbox pill"
```

---

### Task 5: Sidebar collapse / expand (icon-only)

Adds the top-right `«` collapse toggle, persists state pre-paint (no flash), and an icon-only rail. Alpine-free persistence via an `html.sidebar-collapsed` class + `localStorage`, scoped to desktop so it never conflicts with the mobile off-canvas drawer.

**Files:**
- Modify: `tuckit/web/templates/web/base.html:16-21` (pre-paint restore alongside theme), add `toggleSidebar()` to the bottom script block (`:62+`)
- Modify: `tuckit/web/templates/web/partials/_sidebar.html` (add collapse button into `.side-top`)
- Modify: `tuckit/web/static/web/app.css` (append collapsed-mode rules)
- Test: `tests/web/test_sidebar.py`

**Interfaces:**
- Consumes: `{% icon "chevron" %}` (existing). `.side-top` (Task 3).
- Produces: `window.toggleSidebar()` toggles `document.documentElement.classList` `sidebar-collapsed` + persists `localStorage['sidebar-collapsed']`.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_sidebar.py`:

```python
@pytest.mark.django_db
def test_collapse_button_and_toggle_present(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'class="side-collapse"' in body
    assert "toggleSidebar()" in body


def test_collapsed_rail_css_present():
    css = APP_CSS.read_text(encoding="utf-8")
    assert "html.sidebar-collapsed .sidebar" in css
    assert "@media (min-width: 768px)" in css       # desktop-scoped so mobile drawer is unaffected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py -k "collapse_button or collapsed_rail" -v`
Expected: FAIL — no collapse button, no collapsed CSS.

- [ ] **Step 3: Pre-paint restore in base.html**

Extend the head theme script (`base.html:16-21`) to also restore the collapsed class before first paint:

```django
    (function () {
      var saved = localStorage.getItem("theme");
      if (saved === "light" || saved === "dark") {
        document.documentElement.dataset.theme = saved;
      }
      if (localStorage.getItem("sidebar-collapsed") === "1") {
        document.documentElement.classList.add("sidebar-collapsed");
      }
    })();
```

- [ ] **Step 4: Add `toggleSidebar()`**

In the bottom `<script>` block of `base.html` (after `showToast`, ~`:75`), add:

```javascript
    /* Sidebar collapse: desktop-only icon rail, persisted. The class lives on
       <html> so the head script can restore it before paint (no flash). */
    function toggleSidebar() {
      var on = document.documentElement.classList.toggle("sidebar-collapsed");
      localStorage.setItem("sidebar-collapsed", on ? "1" : "0");
    }
```

- [ ] **Step 5: Add the collapse button**

In `_sidebar.html`, add the collapse button inside `.side-top` after the bell:

```django
    <button class="side-top-act side-collapse" type="button"
            aria-label="Collapse sidebar" title="Collapse sidebar"
            x-on:click="toggleSidebar()">{% icon "chevron" %}</button>
```

- [ ] **Step 6: Add collapsed-mode CSS**

Append to `app.css` (near the mobile `@media` block, ~line 1425), desktop-scoped:

```css
/* --- Collapsed (icon-only) sidebar, desktop only --- */
.side-collapse .icon { transform: rotate(180deg); transition: transform 0.15s ease; }
html.sidebar-collapsed .side-collapse .icon { transform: rotate(0deg); }
@media (min-width: 768px) {
  html.sidebar-collapsed .sidebar { flex-basis: 60px; }
  html.sidebar-collapsed .nav-label,
  html.sidebar-collapsed .section,
  html.sidebar-collapsed .nav-count,
  html.sidebar-collapsed .nav-kbd,
  html.sidebar-collapsed .ws-labels,
  html.sidebar-collapsed .ws-chev,
  html.sidebar-collapsed .search-pill .nav-label,
  html.sidebar-collapsed .side-top-act:not(.side-collapse),
  html.sidebar-collapsed .area-actions { display: none; }
  html.sidebar-collapsed .side-top { flex-direction: column; gap: 6px; }
  html.sidebar-collapsed .nav,
  html.sidebar-collapsed .capture-btn,
  html.sidebar-collapsed .search-pill { justify-content: center; padding-left: 0; padding-right: 0; }
}
```

(Collapsed rail hides labels/badges/section headers and the non-collapse top actions; the `.nav` icon `title` attributes still expose labels on hover. Mobile — below 768px — is untouched, so the off-canvas drawer keeps full labels.)

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_sidebar.py -k "collapse_button or collapsed_rail" -v`
Expected: PASS

- [ ] **Step 8: Manual smoke**

Desktop width: click `«` → sidebar shrinks to an icon rail, chevron flips; reload → stays collapsed (no flash); click again → expands. Shrink the window below 768px → the mobile drawer opens full-width regardless of collapsed state.

- [ ] **Step 9: Commit**

```bash
git add tuckit/web/templates/web/base.html tuckit/web/templates/web/partials/_sidebar.html tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): collapsible icon-only sidebar with persisted state"
```

---

### Task 6: Areas section header `+` and per-row `⋮` menu

Promotes area-add to a header `+` button (revealing the existing hx-post form) and moves the hover rename/delete actions into a single `⋮` popover.

**Files:**
- Modify: `tuckit/web/templates/web/partials/_sidebar.html:18-23` (Areas header with `+`, relocate the add form)
- Modify: `tuckit/web/templates/web/partials/_area_row.html:9-16` (replace inline actions with `⋮` popover)
- Modify: `tuckit/web/static/web/app.css:1214-1232` (area actions → popover styles) and the Areas header
- Test: `tests/web/test_sidebar.py`

**Interfaces:**
- Consumes: `{% icon "dots" %}` and `{% icon "plus" %}` (Task 1 / existing). Existing routes `web:area_create`, `web:area_rename`, `web:area_delete`. SortableJS reorder unchanged.
- Produces: each `.area-item` has an `.area-menu` popover with Rename + Delete; the Areas `.section` header has an `.area-add-btn`.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_sidebar.py`:

```python
@pytest.mark.django_db
def test_areas_header_add_and_row_menu(client_local, workspace):
    from tuckit.core.services.areas import create_area
    create_area(workspace, "Backend")
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'class="section area-section"' in body      # header row
    assert 'class="area-add-btn"' in body               # + button in header
    assert 'class="area-menu"' in body                  # per-row ⋮ popover
    assert 'class="area-menu-item"' in body             # Rename item in popover
    assert 'class="area-menu-item area-menu-item--danger"' in body  # Delete item wired to area_delete
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_areas_header_add_and_row_menu -v`
Expected: FAIL — no `.area-section` header/`.area-add-btn`/`.area-menu`.

- [ ] **Step 3: Rebuild the Areas header in `_sidebar.html`**

Replace the Areas block (old `:18-23`: `<div class="section">Areas</div>`, the include, and the standalone `.area-add` form) with a header that has a `+` button revealing the add form:

```django
  <div class="section area-section" x-data="{adding: false}">
    <span>Areas</span>
    <button type="button" class="area-add-btn" aria-label="Add area" title="Add area"
            x-on:click="adding = !adding; $nextTick(() => adding && $refs.areaAddInput && $refs.areaAddInput.focus())">{% icon "plus" %}</button>
    <form class="area-add" x-show="adding" x-cloak
          hx-post="{% wurl 'web:area_create' %}" hx-swap="none"
          hx-on::after-request="this.reset(); adding = false">
      <input name="name" x-ref="areaAddInput" class="area-add-input" placeholder="New area name…" autocomplete="off">
    </form>
  </div>
  {% include "web/partials/_area_nav.html" %}
```

(The add form moves *inside* the header's Alpine scope so `+` toggles it. The `x-show`/`x-cloak` keeps it hidden until toggled. `_area_nav.html` still renders the list below.)

- [ ] **Step 4: Replace inline actions with a `⋮` popover in `_area_row.html`**

Replace the `.area-actions` block (`:9-16`) with a single `⋮` button opening an Alpine popover; extend the row's `x-data` to hold `menu` state. Change line 2 and the actions block:

```django
<div class="area-item" data-area-id="{{ a.id }}" x-data="{editing: false, menu: false}">
```

Then replace `:9-16` (`<div class="area-actions">…</div>`) with:

```django
  <div class="area-menu" x-show="!editing" x-on:keydown.escape="menu = false">
    <button type="button" class="area-act" title="Area actions" aria-haspopup="menu"
            x-on:click="menu = !menu">{% icon "dots" %}</button>
    <div class="area-menu-pop" x-show="menu" x-cloak x-on:click.outside="menu = false" role="menu">
      <button type="button" class="area-menu-item" role="menuitem"
              x-on:click="menu = false; editing = true; $nextTick(() => { $refs.renameInput.focus(); $refs.renameInput.select() })">Rename</button>
      <button type="button" class="area-menu-item area-menu-item--danger" role="menuitem"
              hx-post="{% wurl 'web:area_delete' a.id %}"
              hx-target="closest .area-item" hx-swap="outerHTML"
              hx-confirm="This area and all items in it will be deleted. Continue?">Delete</button>
    </div>
  </div>
```

(The existing rename `<form>` at the bottom of `_area_row.html` and the double-click-to-rename on the link are unchanged; the popover's Rename button just flips `editing`.)

- [ ] **Step 5: Update CSS**

In `app.css`, make the Areas `.section` a flex header and add the popover styles. Add after the `.section` rule (`:88`):

```css
.section.area-section { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.section.area-section > span { flex: 1 1 auto; }
.area-add-btn {
  flex: 0 0 auto; display: grid; place-items: center; width: 22px; height: 22px;
  background: none; border: none; cursor: pointer; color: var(--ink-faint);
  border-radius: var(--radius-small); padding: 0;
}
.area-add-btn:hover { background: var(--paper-raised); color: var(--ink); }
.area-add-btn .icon { width: 14px; height: 14px; stroke: var(--ink-faint); }
.section.area-section .area-add { flex: 1 1 100%; margin-top: 4px; }
```

Replace the `.area-actions` / `.area-act` block (`:1214-1232`) with the `⋮` popover styles (keep `.area-item`, `.area-rename*`, `.sortable-ghost`):

```css
.area-menu { position: relative; opacity: 0; transition: opacity 0.12s ease; }
.area-item:hover .area-menu { opacity: 1; }
.area-act {
  border: none; background: none; color: var(--ink-faint); cursor: pointer;
  padding: 2px 6px; border-radius: var(--radius-small); line-height: 1;
}
.area-act:hover { background: var(--paper-raised); color: var(--ink); }
.area-act .icon { width: 15px; height: 15px; stroke: var(--ink-faint); }
.area-menu-pop {
  position: absolute; top: 100%; right: 0; z-index: 25; margin-top: 2px; padding: 4px;
  min-width: 130px; background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: 0 8px 28px var(--shadow);
}
.area-menu-item {
  display: block; width: 100%; text-align: left; background: none; border: none;
  font: inherit; color: var(--ink); cursor: pointer;
  padding: 7px 9px; border-radius: var(--radius-small);
}
.area-menu-item:hover { background: var(--paper-raised); }
.area-menu-item--danger { color: var(--warn); }
.area-menu:focus-within { opacity: 1; }
```

(`.area-menu:focus-within { opacity: 1; }` keeps the `⋮` and its popover visible while open: clicking the `⋮` focuses it, so the group stays opaque even after the pointer leaves the row. The popover's own `x-show="menu"` controls whether it's in the DOM.)

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/web/test_sidebar.py::test_areas_header_add_and_row_menu -v`
Expected: PASS

- [ ] **Step 7: Regression + manual smoke**

Run: `uv run pytest tests/web/ -q`
Expected: PASS.
Manual: `+` in the Areas header reveals the input and creates an area (htmx OOB refresh). Hover an area → `⋮` appears; open it → Rename flips to the inline input, Delete confirms + removes. Drag-reorder still works (SortableJS on `#area-nav`).

- [ ] **Step 8: Commit**

```bash
git add tuckit/web/templates/web/partials/_sidebar.html tuckit/web/templates/web/partials/_area_row.html tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): Areas header add-button and per-row actions menu"
```

---

### Task 7: Bottom stack — Light mode row

Promotes the icon-only theme toggle to a labeled full-width `Light mode` / `Dark mode` row, matching the review's bottom stack (Settings / theme / Capture).

**Files:**
- Modify: `tuckit/web/templates/web/partials/_sidebar.html` (the `util-row` theme button → labeled row)
- Modify: `tuckit/web/static/web/app.css:1142-1156` (`.util-row` stacks vertically; theme row full-width)
- Test: `tests/web/test_sidebar.py`

**Interfaces:**
- Consumes: existing theme Alpine logic, `{% icon "sun" %}` / `{% icon "moon" %}`.
- Produces: visual only; a labeled theme row.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_sidebar.py`:

```python
@pytest.mark.django_db
def test_theme_toggle_is_labeled_row(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert "util-theme" in body
    assert "util-theme-label" in body     # promoted to a labeled row
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_theme_toggle_is_labeled_row -v`
Expected: FAIL — theme button is icon-only, no `util-theme-label`.

- [ ] **Step 3: Make the theme toggle a labeled row**

In `_sidebar.html`, replace the `util-theme` button (kept from Task 3's `util-row`) with a full-width labeled row that shows the label for the mode you'd switch *to*:

```django
    <button class="util-btn util-theme" type="button"
            x-data="{theme: document.documentElement.dataset.theme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')}"
            x-on:click="theme = theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = theme; localStorage.setItem('theme', theme)"
            :aria-label="theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'">
      <span x-show="theme === 'dark'">{% icon "sun" %}</span>
      <span x-show="theme !== 'dark'" style="display:none">{% icon "moon" %}</span>
      <span class="util-label util-theme-label" x-text="theme === 'dark' ? 'Light mode' : 'Dark mode'">Dark mode</span>
    </button>
```

- [ ] **Step 4: Stack the util-row vertically**

In `app.css`, update `.util-row` / `.util-theme` (`:1142`, `:1151`) so both Settings and theme are full-width rows:

```css
.util-row { display: flex; flex-direction: column; gap: 2px; margin-top: 6px; }
.util-settings { justify-content: flex-start; }
.util-theme { justify-content: flex-start; width: 100%; }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/web/test_sidebar.py::test_theme_toggle_is_labeled_row -v`
Expected: PASS

- [ ] **Step 6: Manual smoke**

Bottom of sidebar shows `Settings`, `Light mode`/`Dark mode` (label reflects the target mode and toggles the theme + persists), then the teal `Capture` button with its `C` kbd. Collapsed rail (Task 5) hides these labels.

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/partials/_sidebar.html tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): promote theme toggle to a labeled bottom row"
```

---

### Task 8: Full verification + no-hex guard

**Files:**
- Test: `tests/web/test_sidebar.py`

- [ ] **Step 1: Add a diff-safe no-hex guard for the new CSS**

The design-drift test already asserts token usage in the token files. Add a targeted guard that the sidebar CSS additions introduced no raw hex. Append to `tests/web/test_sidebar.py`:

```python
import re


def test_new_sidebar_css_uses_no_raw_hex():
    css = APP_CSS.read_text(encoding="utf-8")
    # No 3/6-digit hex color literals anywhere in the components file.
    hexes = re.findall(r"#[0-9a-fA-F]{3,8}\b", css)
    assert hexes == [], f"app.css must use var(--token), found hex: {hexes}"
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/web/test_sidebar.py::test_new_sidebar_css_uses_no_raw_hex -v`
Expected: PASS (if it fails, replace the offending literal with the appropriate `var(--token)`).

- [ ] **Step 3: Run the full web suite**

Run: `uv run pytest tests/web/ -q`
Expected: PASS — including `test_design_system.py` (tokens unchanged) and existing home/sidebar tests.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Final manual pass (verify skill)**

Drive the app and confirm end-to-end: workspace dropdown at top (no wordmark), bell opens Activity, Search pill + `⌘K` open the palette and navigate, MAIN header + accent-bar active state + Inbox pill, Areas `+` add and `⋮` rename/delete + drag reorder, collapse toggles and persists, Light/Dark row toggles, Capture (`C`) works, and everything looks right in both light and dark themes.

- [ ] **Step 6: Commit**

```bash
git add tests/web/test_sidebar.py
git commit -m "test(web): guard sidebar CSS against raw hex + full verification"
```

---

## Self-Review Notes

- **Spec coverage:** Linear top/no-wordmark (T3) ✓; bell to top (T3) ✓; MAIN grouping + accent bar + Inbox pill (T4) ✓; Areas header `+` + `⋮` menu, reorder preserved (T6) ✓; collapse/persist, mobile-safe (T5) ✓; Cmd+K palette over existing destinations + Search pill (T2/T3) ✓; Light mode row (T7) ✓; token-only + drift test green + no-hex guard (T8) ✓. Out-of-scope items (Starred/RecentlyViewed/Archived/MyFilters/color-icon) intentionally absent.
- **Placeholders:** the one intentional no-op CSS placeholder in T6 Step 5 is explicitly replaced in the same step by `.area-menu:focus-within { opacity: 1; }` — do not ship the no-op line.
- **Type/name consistency:** `pal` (body scope) is defined in T2 Step 5 before use by the Search pill (T3) and palette (T2). `toggleSidebar()` defined in T5 before its button uses it (same task). `.side-top` created in T3, consumed by T5's collapse button. Icon names `search`/`dots` defined in T1, used in T3/T6.
- **Note:** the mobile top bar (`.topbar-brand`) keeps the `tuckit` wordmark — that's the mobile header, not the sidebar, and is out of scope.
