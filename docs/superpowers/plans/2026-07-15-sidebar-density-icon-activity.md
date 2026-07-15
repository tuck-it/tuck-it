# Sidebar Density + Panel-Toggle Icon + Activity Removal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten the sidebar + slice-panel chrome to a Linear-like density, swap the collapse chevron for a panel-toggle icon, and remove the Activity entry points (sidebar button, slide-over, standalone page).

**Architecture:** Mostly CSS value edits in `app.css`, one icon added / one removed in the `web_extras.py` icon table, small template + view + urls edits, two template deletions, and test updates for the removed feature. No model or migration changes.

**Tech Stack:** Django templates, static CSS, a Python icon templatetag, pytest (string/markup-presence + client-GET assertions — the repo's established web-test style; there is no JS/browser harness).

## Global Constraints

- Desktop + shared chrome only. **Reading content is out of scope**: slice description, markdown (`.md-*`), and card title/body keep their sizes. The mobile off-canvas drawer must remain functional.
- CSS: `var(--token)` only — no literal hex, no hardcoded radius. `tests/web/test_sidebar.py::test_new_sidebar_css_uses_no_raw_hex` fails on any hex in `app.css`.
- Do NOT touch `tokens.brand.css` / `tokens.product.css`.
- Density target values (verbatim): `.sidebar` font `13px`, padding `14px 10px`, gap `2px`; `.nav` min-height `32px`, gap `8px`; `.nav-group` gap `2px`; `.nav-sep` margin `8px 4px`; `.util-btn` min-height `30px`; `.capture-btn` min-height `32px`, gap `8px`; `.search-pill` padding `6px 9px`, margin `0 0 6px`; `.ws-name` `13px`; `.side-top` padding `0 4px 4px`; `.panel-title` `18→17px`; `.panel-titlebar .panel-title` `22→20px`; `.section-label` `12→11px`; `.action-bar` padding `13px 22px → 10px 22px`. Icons stay `16px`; `.section` stays `11px`.
- **Keep** on Activity removal: `ActivityEvent` model + migrations, `recent_activity`/`slice_activity` services, `_activity_row.html`, the slice-detail Activity thread in `_slice_panel.html`, the `welcome/agent-activity` route/view, and the `#panel` slide-over machinery in `base.html`.
- Area-nav rows use `<a class="nav area-link">`, so they inherit the `.nav` density change automatically — no separate area edit needed.
- Run tests from the repo root with `uv run pytest`.
- Spec: `docs/superpowers/specs/2026-07-15-sidebar-density-icon-activity-design.md`.

---

### Task 1: Density pass (sidebar + panel frame)

CSS-only value edits in `app.css`. Tighten sidebar chrome and slice-panel frame; leave reading content untouched.

**Files:**
- Modify: `tuckit/tuckit/web/static/web/app.css`
- Test: `tuckit/tests/web/test_sidebar.py`

**Interfaces:**
- Produces: `.sidebar { font-size: 13px }` and the tightened row heights/paddings listed in Global Constraints. No new selectors or tokens.

- [ ] **Step 1: Write the failing test**

Add to `tuckit/tests/web/test_sidebar.py` (the file already imports `re` and defines `APP_CSS`):

```python
def test_sidebar_and_panel_density_tightened():
    css = APP_CSS.read_text(encoding="utf-8")
    # .sidebar carries an explicit 13px so labels drop from the inherited 16px
    assert re.search(r"\.sidebar\s*\{[^}]*font-size:\s*13px", css), ".sidebar must set font-size: 13px"
    assert "min-height: 32px" in css        # nav/capture rows tightened from 40 (new value)
    assert re.search(r"\.util-btn\s*\{[^}]*min-height:\s*30px", css), ".util-btn must be 30px"
    assert "min-height: 40px" not in css    # no 40px sidebar rows remain
    # slice-panel frame stepped down (reading body untouched)
    assert ".panel-titlebar .panel-title { font-size: 20px;" in css
    assert ".section-label { font-size: 11px;" in css
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_sidebar_and_panel_density_tightened -v`
Expected: FAIL.

- [ ] **Step 3: Tighten the `.sidebar` rule**

Replace:

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

with (adds `font-size: 13px`, tightens `padding` and `gap`):

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
  padding: 14px 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 13px;             /* Linear-dense chrome; labels drop from inherited 16px */
}
```

- [ ] **Step 4: Tighten sidebar rows/spacing**

Make these exact replacements in `app.css`:

- `.side-top { display: flex; align-items: center; gap: 4px; padding: 0 4px 6px; }`
  → `.side-top { display: flex; align-items: center; gap: 4px; padding: 0 4px 4px; }`
- In the `.nav {` rule: `  gap: 9px;` → `  gap: 8px;` and `  min-height: 40px;` → `  min-height: 32px;`
- `.nav-group { display: flex; flex-direction: column; gap: 4px; }`
  → `.nav-group { display: flex; flex-direction: column; gap: 2px; }`
- `.nav-sep { height: 1px; background: var(--line); margin: 10px 4px; }`
  → `.nav-sep { height: 1px; background: var(--line); margin: 8px 4px; }`
- In `.util-btn {`: `  min-height: 36px; padding: 6px 10px;` → `  min-height: 30px; padding: 6px 10px;`
- In `.capture-btn {`: `  gap: 9px;` → `  gap: 8px;` and `  min-height: 40px;` → `  min-height: 32px;`
- In `.search-pill {`: `  margin: 0 0 8px; padding: 7px 10px;` → `  margin: 0 0 6px; padding: 6px 9px;`
- `.ws-name { font-size: 14px; font-weight: 600; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }`
  → same line with `font-size: 13px;`

Note: `.nav` and `.capture-btn` are the only sidebar rows at `min-height: 40px`; both become `32px`, so no `min-height: 40px` remains (the density test asserts this).

- [ ] **Step 5: Tighten the slice-panel frame**

Make these exact replacements (leave every other property on each line unchanged):

- `.panel-title { font-size: 18px;` → `.panel-title { font-size: 17px;`
- `.panel-titlebar .panel-title { font-size: 22px;` → `.panel-titlebar .panel-title { font-size: 20px;`
- `.section-label { font-size: 12px;` → `.section-label { font-size: 11px;`
- In the `.action-bar {` rule: `padding: 13px 22px;` → `padding: 10px 22px;`

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/web/test_sidebar.py::test_sidebar_and_panel_density_tightened -v`
Expected: PASS

- [ ] **Step 7: Regression + hex guard**

Run: `uv run pytest tests/web/test_sidebar.py tests/web/test_design_system.py -v`
Expected: PASS (notably `test_new_sidebar_css_uses_no_raw_hex`; the design-drift test may skip when the landing repo is absent).

- [ ] **Step 8: Commit**

```bash
git add tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): tighten sidebar and slice-panel chrome density"
```

---

### Task 2: Panel-toggle collapse icon

Add a lucide `panel-left` icon, use it on the collapse button, and drop the chevron-rotation CSS. Fixes request #2.

**Files:**
- Modify: `tuckit/tuckit/web/templatetags/web_extras.py` (add to `_ICON_PATHS`)
- Modify: `tuckit/tuckit/web/templates/web/partials/_sidebar.html` (swap icon)
- Modify: `tuckit/tuckit/web/static/web/app.css` (remove rotation rules)
- Test: `tuckit/tests/web/test_sidebar.py`

**Interfaces:**
- Consumes: the `{% icon %}` tag and `_ICON_PATHS` (24-viewBox stroke paths).
- Produces: `_ICON_PATHS["panel-left"]`; the collapse button renders it. `chevron` stays (used by `.ws-chev`).

- [ ] **Step 1: Write the failing test**

Add to `tuckit/tests/web/test_sidebar.py`:

```python
@pytest.mark.django_db
def test_collapse_button_uses_panel_left_icon(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'class="side-collapse"' in body
    assert 'd="M9 3v18"' in body            # panel-left divider line rendered on the collapse button


def test_panel_left_registered_and_rotation_removed():
    from tuckit.web.templatetags.web_extras import _ICON_PATHS
    assert "panel-left" in _ICON_PATHS
    assert "chevron" in _ICON_PATHS         # still used by the workspace switcher
    css = APP_CSS.read_text(encoding="utf-8")
    assert "transform: rotate(180deg)" not in css   # chevron-rotation rule gone
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_sidebar.py::test_collapse_button_uses_panel_left_icon tests/web/test_sidebar.py::test_panel_left_registered_and_rotation_removed -v`
Expected: FAIL.

- [ ] **Step 3: Register the `panel-left` icon**

In `tuckit/tuckit/web/templatetags/web_extras.py`, add an entry to the `_ICON_PATHS` dict (place it right after the `"chevron"` line):

```python
    "chevron": '<path d="m9 6 6 6-6 6"/>',
    "panel-left": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18"/>',
```

- [ ] **Step 4: Use it on the collapse button**

In `tuckit/tuckit/web/templates/web/partials/_sidebar.html`, change the collapse button icon:

```html
    <button class="side-collapse" type="button"
            aria-label="Collapse sidebar" title="Collapse sidebar"
            x-on:click="toggleSidebar()">{% icon "panel-left" %}</button>
```

(was `{% icon "chevron" %}`.)

- [ ] **Step 5: Remove the chevron-rotation CSS**

In `tuckit/tuckit/web/static/web/app.css`, delete these two lines (just above the `@media (min-width: 768px)` collapsed block):

```css
.side-collapse .icon { transform: rotate(180deg); transition: transform 0.15s ease; }
html.sidebar-collapsed .side-collapse .icon { transform: rotate(0deg); }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_sidebar.py::test_collapse_button_uses_panel_left_icon tests/web/test_sidebar.py::test_panel_left_registered_and_rotation_removed -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templatetags/web_extras.py tuckit/web/templates/web/partials/_sidebar.html tuckit/web/static/web/app.css tests/web/test_sidebar.py
git commit -m "feat(web): use panel-toggle icon for sidebar collapse"
```

---

### Task 3: Remove Activity button, slide-over, and page

Remove the Activity entry points and their now-dead code/tests. Keep the event model, services, `_activity_row.html`, and the slice-detail thread. Fixes request #3.

**Files:**
- Modify: `tuckit/tuckit/web/templates/web/partials/_sidebar.html` (remove the Activity button)
- Delete: `tuckit/tuckit/web/templates/web/partials/_activity_panel.html`
- Delete: `tuckit/tuckit/web/templates/web/activity.html`
- Modify: `tuckit/tuckit/web/views/pages.py` (remove `activity` view + `recent_activity` usage)
- Modify: `tuckit/tuckit/web/urls.py` (remove the `activity/` route)
- Modify: `tuckit/tuckit/web/templatetags/web_extras.py` (remove the `"activity"` icon)
- Modify: `tuckit/tuckit/web/static/web/app.css` (remove `.side-top-act` rules)
- Test: add removal tests to `tuckit/tests/web/test_sidebar.py`; update `tests/web/test_lens_pages.py`, `tests/web/test_home_shell.py`, `tests/web/test_home.py`, `tests/web/test_icons.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `web:activity` no longer resolves; no `aria-label="Activity"` / `/activity/` in workspace pages; `_ICON_PATHS` has no `"activity"`.

- [ ] **Step 1: Write the failing removal test + update the tests that assert the old entry points**

First, add to `tuckit/tests/web/test_sidebar.py`:

```python
@pytest.mark.django_db
def test_activity_route_and_sidebar_entry_removed(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    assert client_local.get(f"{p}/activity/").status_code == 404   # route gone
    body = client_local.get(f"{p}/").content.decode()
    assert 'aria-label="Activity"' not in body                     # no sidebar button
    assert "/activity/" not in body                                # no link anywhere in the shell


def test_activity_icon_removed():
    from tuckit.web.templatetags.web_extras import _ICON_PATHS
    assert "activity" not in _ICON_PATHS
```

Then update the tests that currently assert the removed entry points:

- In `tests/web/test_lens_pages.py`, **delete these four functions entirely**: `test_activity_page_lists_events`, `test_sidebar_activity_is_bell_not_nav`, `test_activity_panel_branch_returns_slideover`, `test_activity_full_page_still_works` (lines 52–94 in the current file — every `@pytest.mark.django_db def test_activity_*` / `test_sidebar_activity_*` block in that range).
- In `tests/web/test_home_shell.py`, **delete the function** `test_activity_bell_in_utility_row` (the block asserting `'/activity/?panel=1' in body` and `'aria-label="Activity"' in body`). Leave the earlier `>Activity<" not in nav_group` assertion in `test_...` intact.
- In `tests/web/test_home.py`, in `test_home_omits_roadmap_strip_and_recent_activity`, **remove only this line**:
  `    assert '/activity/?panel=1' in body               # Activity via the utility bell`
  (keep the other three asserts in that function).
- In `tests/web/test_icons.py`, **delete the function** `test_activity_icon_differs_from_in_progress` (it reads `_ICON_PATHS["activity"]`, which will no longer exist). Keep `test_sun_and_moon_icons_registered`.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/web/test_sidebar.py::test_activity_route_and_sidebar_entry_removed tests/web/test_sidebar.py::test_activity_icon_removed -v`
Expected: FAIL (route still resolves, button still present, icon still registered).

- [ ] **Step 3: Remove the sidebar Activity button**

In `tuckit/tuckit/web/templates/web/partials/_sidebar.html`, delete the button block:

```html
    <button class="side-top-act" type="button"
            aria-label="Activity" title="Activity"
            hx-get="{% wurl 'web:activity' %}?panel=1" hx-target="#panel">{% icon "activity" %}</button>
```

`.side-top` now holds just the workspace switcher and the collapse button.

- [ ] **Step 4: Delete the two Activity templates**

```bash
git rm tuckit/web/templates/web/partials/_activity_panel.html tuckit/web/templates/web/activity.html
```

- [ ] **Step 5: Remove the `activity` view and `recent_activity` usage**

In `tuckit/tuckit/web/views/pages.py`:

- Delete the `activity` view:

```python
def activity(request):
    ws = get_current_workspace(request)
    events = recent_activity(ws, limit=100) if ws else []
    is_panel = request.GET.get("panel") == "1" and request.headers.get("HX-Request")
    template = "web/partials/_activity_panel.html" if is_panel else "web/activity.html"
    return render(request, template, {"events": events})
```

- Remove the now-unused `recent_activity` import line (`    recent_activity,`) from the `from tuckit.core.services.state import (...)` block.
- Remove the dead context key from the `home` view's `render(...)` dict (the home template does not use it):
  `        "recent_activity": recent_activity(ws) if ws else [],`

- [ ] **Step 6: Remove the route**

In `tuckit/tuckit/web/urls.py`, delete the line:

```python
    path(f"{P}activity/", pages.activity, name="activity"),
```

(Keep `welcome/agent-activity` — it is a different view.)

- [ ] **Step 7: Remove the `activity` icon**

In `tuckit/tuckit/web/templatetags/web_extras.py`, delete the `_ICON_PATHS` entry:

```python
    "activity": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
```

- [ ] **Step 8: Remove the dead `.side-top-act` CSS**

In `tuckit/tuckit/web/static/web/app.css`, split the shared rules so only `.side-collapse` remains:

- `.side-top-act, .side-collapse {` → `.side-collapse {`
- `.side-top-act:hover, .side-collapse:hover { background: var(--paper-raised); color: var(--ink); }` → `.side-collapse:hover { background: var(--paper-raised); color: var(--ink); }`
- `.side-top-act .icon, .side-collapse .icon { stroke: var(--ink-faint); }` → `.side-collapse .icon { stroke: var(--ink-faint); }`
- `.side-top-act:hover .icon, .side-collapse:hover .icon { stroke: var(--ink); }` → `.side-collapse:hover .icon { stroke: var(--ink); }`

And in the `@media (min-width: 768px)` collapsed block, delete the line:

```css
  html.sidebar-collapsed .side-top-act:not(.side-collapse),
```

- [ ] **Step 9: Run the full web suite**

Run: `uv run pytest tests/web/ -v`
Expected: PASS — the new removal tests pass, the four deleted tests are gone, the updated tests pass, and the slice-detail Activity-thread tests in `tests/web/test_slice_detail.py` still pass (`_activity_row.html` and the thread are untouched). No test references `web:activity` anymore.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat(web): remove Activity sidebar button, slide-over, and page"
```

---

## Self-review checklist (controller, before execution)

- Density values in Task 1 match Global Constraints verbatim. ✅
- `chevron` kept (workspace switcher), `activity` removed, `panel-left` added. ✅
- Activity removal keeps model/services/`_activity_row.html`/slice thread/`welcome` poll/`#panel`. ✅
- Every test that asserts the old Activity entry points is updated or deleted (test_lens_pages ×4, test_home_shell ×1, test_home ×1 line, test_icons ×1). ✅
- No `tokens.brand.css`/`tokens.product.css` edits; no hex introduced. ✅
