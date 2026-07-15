# Sidebar Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the home sidebar read as one intentional design — replace the raw native workspace `<select>` with a custom popover, regroup the nav, and restyle the theme toggle and Capture button so nothing looks copy-pasted.

**Architecture:** Django templates + Alpine.js + HTMX. The sidebar is `partials/_sidebar.html` including `partials/_workspace_switcher.html`. Styling is `static/web/app.css`. Icons come from `templatetags/web_extras.py` `_ICON_PATHS`. A new context processor exposes the active workspace to every template so the switcher trigger can always show identity.

**Tech Stack:** Python 3 / Django, Alpine.js, HTMX, plain CSS with design tokens.

## Global Constraints

- Colors and radius via `var(--token)` ONLY — no literal hex, no hardcoded radius. (from `tuckit/CLAUDE.md`)
- Accent is the single teal `--blue`. Surfaces use `--radius` (14px), controls use `--radius-small` (9px).
- This is the PUBLIC `tuckit` repo. No billing/cloud/pricing anything. (from workspace `CLAUDE.md`)
- Available tokens: `--paper`, `--paper-raised`, `--paper-deep`, `--surface`, `--ink`, `--ink-soft`, `--ink-faint`, `--blue`, `--blue-strong`, `--blue-soft`, `--line`, `--line-strong`, `--shadow`, `--overlay`, `--radius`, `--radius-small`, `--mono`.
- `{% icon "name" %}` tag signature is `icon(name, cls="icon")` — pass extra classes as the 2nd arg: `{% icon "chevron" "icon ws-chev" %}`.
- Run tests with: `cd tuckit && uv run pytest <path> -v`

---

### Task 1: Context layer — expose active workspace, order switchable list

**Files:**
- Modify: `tuckit/tuckit/web/context_processors.py` (add `current_workspace`, sort `switchable_workspaces`)
- Modify: `tuckit/tuckit/settings.py:59-67` (register new processor)
- Test: `tuckit/tests/web/test_home_shell.py` (append)

**Interfaces:**
- Consumes: `get_current_workspace(request)` (already imported in the module), `accessible_workspaces(request.user)`.
- Produces: template context `current_workspace` (a `Workspace` or absent), and `switchable_workspaces` sorted by `(org.name, name)` so Django `{% regroup %}` groups correctly.

- [ ] **Step 1: Write the failing test**

Append to `tuckit/tests/web/test_home_shell.py`:

```python
@pytest.mark.django_db
def test_current_workspace_in_template_context(client_local, workspace):
    resp = client_local.get("/")
    assert resp.context["current_workspace"].id == workspace.id


@pytest.mark.django_db
def test_switchable_workspaces_sorted_by_org_then_name(client_local, workspace):
    resp = client_local.get("/")
    ws = list(resp.context["switchable_workspaces"])
    keys = [(w.org.name, w.name) for w in ws]
    assert keys == sorted(keys)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tuckit && uv run pytest tests/web/test_home_shell.py::test_current_workspace_in_template_context -v`
Expected: FAIL with `KeyError: 'current_workspace'`.

- [ ] **Step 3: Add the `current_workspace` processor and sort `switchable_workspaces`**

In `tuckit/tuckit/web/context_processors.py`, add a new function (near `switchable_workspaces`):

```python
def current_workspace(request):
    """Expose the active workspace to every template so the sidebar switcher's
    trigger can always show the current org · workspace identity, regardless of
    whether the current view passes `workspace` itself."""
    ws = get_current_workspace(request)
    return {"current_workspace": ws} if ws else {}
```

Change the return line of `switchable_workspaces` from:

```python
    return {"switchable_workspaces": list(accessible_workspaces(request.user))}
```

to:

```python
    workspaces = sorted(
        accessible_workspaces(request.user),
        key=lambda w: (w.org.name, w.name),
    )
    return {"switchable_workspaces": workspaces}
```

- [ ] **Step 4: Register the processor**

In `tuckit/tuckit/settings.py`, in the `context_processors` list (currently ending at line 67 with `switchable_workspaces`), add below it:

```python
                "tuckit.web.context_processors.current_workspace",
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd tuckit && uv run pytest tests/web/test_home_shell.py -v`
Expected: PASS (both new tests + the existing three).

- [ ] **Step 6: Commit**

```bash
cd tuckit && git add tuckit/web/context_processors.py tuckit/settings.py tests/web/test_home_shell.py
git commit -m "feat(web): expose current_workspace + sort switchable_workspaces for sidebar"
```

---

### Task 2: Icons — add sun/moon, differentiate activity glyph

**Files:**
- Modify: `tuckit/tuckit/web/templatetags/web_extras.py:16-32` (`_ICON_PATHS`)
- Test: `tuckit/tests/web/test_icons.py` (create)

**Interfaces:**
- Produces: icon names `"sun"` and `"moon"` usable as `{% icon "sun" %}`; a redrawn `"activity"` path distinct from `"in-progress"`.

- [ ] **Step 1: Write the failing test**

Create `tuckit/tests/web/test_icons.py`:

```python
from tuckit.web.templatetags.web_extras import _ICON_PATHS


def test_sun_and_moon_icons_registered():
    assert "sun" in _ICON_PATHS
    assert "moon" in _ICON_PATHS


def test_activity_icon_differs_from_in_progress():
    # both were near-identical waveforms; they must be visually distinct
    assert _ICON_PATHS["activity"] != _ICON_PATHS["in-progress"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tuckit && uv run pytest tests/web/test_icons.py -v`
Expected: FAIL — `test_sun_and_moon_icons_registered` KeyError/AssertionError; the activity test currently passes only if paths already differ (they do differ slightly today, so it may pass — that's fine, the sun/moon test is the gate).

- [ ] **Step 3: Edit `_ICON_PATHS`**

In `tuckit/tuckit/web/templatetags/web_extras.py`, replace the `"activity"` entry and add `"sun"`/`"moon"`. The `"activity"` line currently reads:

```python
    "activity": '<path d="M3 12h4l3 8 4-16 3 8h4"/>',
```

Replace it with a clock glyph (reads as "recent activity", clearly unlike the In Progress waveform), and add the two new icons — final block:

```python
    "activity": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>',
    "menu": '<path d="M4 7h16M4 12h16M4 17h16"/>',
```

(The `"menu"` line already exists as the last entry — keep it last; insert the three new/edited entries before it. Do not duplicate `"menu"`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tuckit && uv run pytest tests/web/test_icons.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd tuckit && git add tuckit/web/templatetags/web_extras.py tests/web/test_icons.py
git commit -m "feat(web): add sun/moon icons and distinct activity glyph"
```

---

### Task 3: Workspace switcher → custom Alpine popover

**Files:**
- Rewrite: `tuckit/tuckit/web/templates/web/partials/_workspace_switcher.html`
- Modify: `tuckit/tuckit/web/static/web/app.css` (add switcher styles; near the `.brand` rule, ~line 27)
- Test: `tuckit/tests/web/test_home_shell.py` (append)

**Interfaces:**
- Consumes: `current_workspace` (Task 1), `switchable_workspaces` sorted by org (Task 1), `web:switch_workspace` URL (existing POST endpoint taking `workspace_id`), `web:settings_workspace` URL, `{% icon %}` incl. `check`/`chevron`/`settings`.
- Produces: markup classes `.ws-switch-wrap`, `.ws-switch`, `.ws-menu` consumed by CSS.

- [ ] **Step 1: Write the failing test**

Append to `tuckit/tests/web/test_home_shell.py`:

```python
@pytest.mark.django_db
def test_switcher_is_custom_popover_not_native_select(client_local, workspace):
    body = client_local.get("/").content.decode()
    assert 'class="ws-switch"' in body            # custom trigger button
    assert 'class="ws-menu"' in body              # popover panel
    assert '<select name="workspace_id"' not in body   # native 2001 dropdown gone
    assert 'name="workspace_id"' in body          # switch form contract intact
    assert 'action="/switch-workspace"' in body   # posts to existing endpoint
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tuckit && uv run pytest tests/web/test_home_shell.py::test_switcher_is_custom_popover_not_native_select -v`
Expected: FAIL — `ws-switch` absent, `<select name="workspace_id"` still present.

- [ ] **Step 3: Rewrite the switcher template**

Replace the entire contents of `tuckit/tuckit/web/templates/web/partials/_workspace_switcher.html` with:

```django
{% load web_extras %}
{% if current_workspace %}
<div class="ws-switch-wrap" x-data="{open: false}" x-on:keydown.escape="open = false">
  <button type="button" class="ws-switch" x-on:click="open = !open"
          :aria-expanded="open.toString()" aria-haspopup="menu">
    <span class="ws-mono">{{ current_workspace.name|first|upper }}</span>
    <span class="ws-labels">
      <span class="ws-org">{{ current_workspace.org.name }}</span>
      <span class="ws-name">{{ current_workspace.name }}</span>
    </span>
    {% icon "chevron" "icon ws-chev" %}
  </button>

  <div class="ws-menu" x-show="open" x-transition.origin.top
       x-on:click.outside="open = false" role="menu" style="display:none">
    {% regroup switchable_workspaces by org as org_groups %}
    {% for group in org_groups %}
      <div class="ws-menu-org">{{ group.grouper.name }}</div>
      {% for ws in group.list %}
        <form method="post" action="{% url 'web:switch_workspace' %}" class="ws-menu-form">
          {% csrf_token %}
          <input type="hidden" name="workspace_id" value="{{ ws.id }}">
          <button type="submit" class="ws-menu-item{% if ws.id == current_workspace.id %} ws-menu-item--active{% endif %}" role="menuitem">
            <span class="ws-menu-name">{{ ws.name }}</span>
            {% if ws.id == current_workspace.id %}{% icon "check" "icon ws-check" %}{% endif %}
          </button>
        </form>
      {% endfor %}
    {% endfor %}
    <div class="ws-menu-sep"></div>
    <a class="ws-menu-item ws-menu-settings" href="{% url 'web:settings_workspace' %}" role="menuitem">
      {% icon "settings" %}<span>Workspace settings</span>
    </a>
  </div>
</div>
{% endif %}
```

- [ ] **Step 4: Add switcher CSS**

In `tuckit/tuckit/web/static/web/app.css`, immediately AFTER the `.brand { ... }` line (~line 27), add:

```css
/* --- Workspace switcher popover --- */
.ws-switch-wrap { position: relative; padding: 0 4px 8px; }
.ws-switch {
  display: flex; align-items: center; gap: 9px; width: 100%;
  background: none; border: none; font: inherit; cursor: pointer;
  color: var(--ink); text-align: left;
  padding: 6px 8px; border-radius: var(--radius-small);
}
.ws-switch:hover { background: var(--paper-raised); }
.ws-mono {
  flex: 0 0 auto; width: 26px; height: 26px;
  display: grid; place-items: center;
  background: var(--blue-soft); color: var(--blue);
  border-radius: var(--radius-small);
  font-family: var(--mono); font-size: 13px; font-weight: 600;
}
.ws-labels { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; line-height: 1.25; }
.ws-org { font-size: 11px; color: var(--ink-faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ws-name { font-size: 14px; font-weight: 600; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ws-chev { width: 14px; height: 14px; stroke: var(--ink-faint); transform: rotate(90deg); transition: transform 0.15s ease; }
.ws-switch[aria-expanded="true"] .ws-chev { transform: rotate(-90deg); }

.ws-menu {
  position: absolute; top: 100%; left: 4px; right: 4px; z-index: 30;
  margin-top: 2px; padding: 6px;
  background: var(--surface); border: 1px solid var(--line);
  border-radius: var(--radius); box-shadow: 0 8px 28px var(--shadow);
}
.ws-menu-org {
  font-size: 11px; font-family: var(--mono); text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--ink-faint); padding: 8px 8px 4px;
}
.ws-menu-form { margin: 0; }
.ws-menu-item {
  display: flex; align-items: center; gap: 8px; width: 100%;
  background: none; border: none; font: inherit; cursor: pointer;
  color: var(--ink); text-align: left; text-decoration: none;
  padding: 7px 8px; border-radius: var(--radius-small);
}
.ws-menu-item:hover { background: var(--paper-raised); }
.ws-menu-name { flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ws-menu-item--active { font-weight: 600; }
.ws-check { width: 15px; height: 15px; stroke: var(--blue); flex: 0 0 auto; }
.ws-menu-sep { height: 1px; background: var(--line); margin: 6px 4px; }
.ws-menu-settings { color: var(--ink-faint); }
.ws-menu-settings .icon { stroke: var(--ink-faint); }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd tuckit && uv run pytest tests/web/test_home_shell.py tests/web/test_workspace_switch.py -v`
Expected: PASS (new popover test + existing switch-endpoint tests unaffected).

- [ ] **Step 6: Commit**

```bash
cd tuckit && git add tuckit/web/templates/web/partials/_workspace_switcher.html tuckit/web/static/web/app.css tests/web/test_home_shell.py
git commit -m "feat(web): replace native workspace select with custom popover switcher"
```

---

### Task 4: Nav reorder — queues first, Activity last

**Files:**
- Modify: `tuckit/tuckit/web/templates/web/partials/_sidebar.html:6-22` (reorder `<a>` rows)
- Test: `tuckit/tests/web/test_home_shell.py` (append)

**Interfaces:**
- Consumes: nothing new. Purely reorders existing rows; every row keeps its exact markup (icons, counts, the Triage count include).
- Produces: nav order Home · Attention · Triage · In Progress · Roadmap · Activity.

- [ ] **Step 1: Write the failing test**

Append to `tuckit/tests/web/test_home_shell.py`:

```python
@pytest.mark.django_db
def test_nav_order_queues_before_states_activity_last(client_local, workspace):
    body = client_local.get("/").content.decode()
    i_att = body.find(">Attention<")
    i_tri = body.find(">Triage<")
    i_prog = body.find(">In Progress<")
    i_road = body.find(">Roadmap<")
    i_act = body.find(">Activity<")
    assert -1 not in (i_att, i_tri, i_prog, i_road, i_act)
    assert i_att < i_tri < i_prog < i_road < i_act
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tuckit && uv run pytest tests/web/test_home_shell.py::test_nav_order_queues_before_states_activity_last -v`
Expected: FAIL — today Triage is last, so `i_tri < i_prog` is false.

- [ ] **Step 3: Reorder the nav rows**

In `tuckit/tuckit/web/templates/web/partials/_sidebar.html`, the `<nav class="nav-group">` block currently lists rows in the order: Home, Attention, In Progress, Roadmap, Activity, Triage. Reorder the row anchors so the sequence becomes Home, Attention, Triage, In Progress, Roadmap, Activity. The block must read exactly:

```django
  <nav class="nav-group">
    <a class="nav{% if request.resolver_match.url_name == 'home' %} nav--active{% endif %}"
       href="{% url 'web:home' %}">{% icon "home" %}<span class="nav-label">Home</span></a>
    <a class="nav{% if request.resolver_match.url_name == 'attention' %} nav--active{% endif %}"
       href="{% url 'web:attention' %}">{% icon "attention" %}<span class="nav-label">Attention</span>
       {% if attention_count %}<span class="nav-count">{{ attention_count }}</span>{% endif %}</a>
    <a class="nav{% if request.resolver_match.url_name == 'triage' %} nav--active{% endif %}"
       href="{% url 'web:triage' %}">{% icon "triage" %}<span class="nav-label">Triage</span>
       {% include "web/partials/_triage_count.html" %}</a>
    <a class="nav{% if request.resolver_match.url_name == 'in_progress' %} nav--active{% endif %}"
       href="{% url 'web:in_progress' %}">{% icon "in-progress" %}<span class="nav-label">In Progress</span>
       {% if in_progress_count %}<span class="nav-count">{{ in_progress_count }}</span>{% endif %}</a>
    <a class="nav{% if request.resolver_match.url_name == 'roadmap' %} nav--active{% endif %}"
       href="{% url 'web:roadmap' %}">{% icon "roadmap" %}<span class="nav-label">Roadmap</span></a>
    <a class="nav{% if request.resolver_match.url_name == 'activity' %} nav--active{% endif %}"
       href="{% url 'web:activity' %}">{% icon "activity" %}<span class="nav-label">Activity</span></a>
  </nav>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tuckit && uv run pytest tests/web/test_home_shell.py::test_nav_order_queues_before_states_activity_last -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd tuckit && git add tuckit/web/templates/web/partials/_sidebar.html tests/web/test_home_shell.py
git commit -m "feat(web): reorder sidebar nav — queues first, Activity last"
```

---

### Task 5: Bottom utility row — compact Settings + theme icons

**Files:**
- Modify: `tuckit/tuckit/web/templates/web/partials/_sidebar.html:35-41` (replace Settings row + theme button)
- Modify: `tuckit/tuckit/web/static/web/app.css` (add `.util-row`/`.util-btn`; remove `.theme-toggle` rule at line ~453)
- Test: `tuckit/tests/web/test_home_shell.py` (append)

**Interfaces:**
- Consumes: `sun`/`moon` icons (Task 2), `settings` icon, `web:settings_workspace` URL. Reuses the existing theme Alpine expression verbatim.
- Produces: markup classes `.util-row`, `.util-btn` consumed by CSS. Removes classes `.theme-toggle` and the "Light mode"/"Dark mode" text label.

- [ ] **Step 1: Write the failing test**

Append to `tuckit/tests/web/test_home_shell.py`:

```python
@pytest.mark.django_db
def test_bottom_utility_row_replaces_bordered_theme_button(client_local, workspace):
    body = client_local.get("/").content.decode()
    assert 'class="util-row"' in body                 # compact icon row present
    assert "theme-toggle" not in body                 # old bordered button gone
    assert ">Light mode<" not in body                 # text label gone
    assert ">Dark mode<" not in body
    assert "Switch to light mode" in body             # icon toggle keeps an accessible name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tuckit && uv run pytest tests/web/test_home_shell.py::test_bottom_utility_row_replaces_bordered_theme_button -v`
Expected: FAIL — `util-row` absent, `theme-toggle` still present.

- [ ] **Step 3: Replace the Settings row + theme button in the template**

In `tuckit/tuckit/web/templates/web/partials/_sidebar.html`, replace this block (the `<a class="nav muted ...">Settings</a>` anchor and the `<button class="nav theme-toggle" ...>` button, currently lines 35–41):

```django
  <a class="nav muted{% if request.resolver_match.url_name == 'settings_workspace' or request.resolver_match.url_name == 'settings_org' %} nav--active{% endif %}"
     href="{% url 'web:settings_workspace' %}">{% icon "settings" %}<span class="nav-label">Settings</span></a>
  <button class="nav theme-toggle" type="button"
          x-data="{theme: document.documentElement.dataset.theme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')}"
          x-on:click="theme = theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = theme; localStorage.setItem('theme', theme)">
    <span x-text="theme === 'dark' ? 'Light mode' : 'Dark mode'">Dark mode</span>
  </button>
```

with:

```django
  <div class="util-row">
    <a class="util-btn util-settings{% if request.resolver_match.url_name == 'settings_workspace' or request.resolver_match.url_name == 'settings_org' %} util-btn--active{% endif %}"
       href="{% url 'web:settings_workspace' %}">{% icon "settings" %}<span class="util-label">Settings</span></a>
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

- [ ] **Step 4: Swap the CSS**

In `tuckit/tuckit/web/static/web/app.css`, DELETE the `.theme-toggle` rule (line ~453):

```css
/* Theme toggle — plain nav-style button, pinned to the bottom of the sidebar. */
.theme-toggle { margin-top: auto; color: var(--ink-faint); }
```

Then add, in the sidebar grouping section (right after `.nav-spacer { ... }` at ~line 766):

```css
/* --- Bottom utility row: Settings + theme toggle --- */
.util-row { display: flex; gap: 4px; margin-top: 6px; }
.util-btn {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  min-height: 36px; padding: 6px 10px;
  color: var(--ink-faint); text-decoration: none;
  background: none; border: none; font: inherit; cursor: pointer;
  border-radius: var(--radius-small);
}
.util-settings { flex: 1 1 auto; justify-content: flex-start; }
.util-theme { flex: 0 0 auto; width: 36px; }
.util-btn:hover { background: var(--paper-raised); color: var(--ink); }
.util-btn .icon { stroke: var(--ink-faint); }
.util-btn:hover .icon { stroke: var(--ink); }
.util-btn--active { color: var(--ink); background: var(--blue-soft); }
.util-btn--active .icon { stroke: var(--blue); }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd tuckit && uv run pytest tests/web/test_home_shell.py -v`
Expected: PASS (new utility-row test + all prior home_shell tests).

- [ ] **Step 6: Commit**

```bash
cd tuckit && git add tuckit/web/templates/web/partials/_sidebar.html tuckit/web/static/web/app.css tests/web/test_home_shell.py
git commit -m "feat(web): compact Settings+theme utility row, drop bordered Light mode button"
```

---

### Task 6: Capture → single solid-teal primary CTA

**Files:**
- Modify: `tuckit/tuckit/web/static/web/app.css:768-795` (`.capture-btn` and its `.nav-kbd`)
- Test: `tuckit/tests/web/test_home_shell.py` (append)

**Interfaces:**
- Consumes: nothing new. The Capture button markup in `_sidebar.html` (lines 43–45) is UNCHANGED; only CSS changes.
- Produces: `.capture-btn` restyled as a solid `--blue` primary; its `.nav-kbd` "C" badge reads quietly on teal.

- [ ] **Step 1: Write the failing test**

Append to `tuckit/tests/web/test_home_shell.py`:

```python
from pathlib import Path

APP_CSS = Path(__file__).resolve().parents[2] / "tuckit" / "web" / "static" / "web" / "app.css"


@pytest.mark.django_db
def test_capture_button_still_rendered(client_local, workspace):
    body = client_local.get("/").content.decode()
    assert 'class="capture-btn"' in body


def test_capture_button_is_solid_teal_primary():
    css = APP_CSS.read_text(encoding="utf-8")
    block = css.split(".capture-btn {", 1)[1].split("}", 1)[0]
    assert "background: var(--blue)" in block   # solid teal, not paper-raised
    assert "border: none" in block              # mismatched border removed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tuckit && uv run pytest "tests/web/test_home_shell.py::test_capture_button_is_solid_teal_primary" -v`
Expected: FAIL — current `.capture-btn` uses `background: var(--paper-raised)` and `border: 1px solid var(--line)`.

- [ ] **Step 3: Restyle `.capture-btn` and its kbd**

In `tuckit/tuckit/web/static/web/app.css`, replace the existing `.capture-btn` rule and its two hover/icon follow-ups (lines ~768–786):

```css
.capture-btn {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 40px;
  color: var(--ink);
  line-height: 1.5;
  background: var(--paper-raised);
  border: 1px solid var(--line);
  border-radius: var(--radius-small);
  text-align: left;
  font: inherit;
  cursor: pointer;
  width: 100%;
  padding: 6px 10px;
  margin-top: 6px;
}
.capture-btn:hover { border-color: var(--blue); }
.capture-btn .icon { stroke: var(--blue); }
```

with:

```css
.capture-btn {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 40px;
  line-height: 1.5;
  background: var(--blue);
  border: none;
  border-radius: var(--radius-small);
  text-align: left;
  font: inherit;
  font-weight: 600;
  color: var(--paper);
  cursor: pointer;
  width: 100%;
  padding: 6px 12px;
  margin-top: 6px;
}
.capture-btn:hover { background: var(--blue-strong); }
.capture-btn .icon { stroke: var(--paper); }
.capture-btn .nav-kbd { color: var(--paper); border-color: var(--paper); opacity: 0.65; }
```

Note: `font: inherit` resets weight and color, so `font-weight: 600` and `color: var(--paper)` are placed AFTER it so they win.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tuckit && uv run pytest tests/web/test_home_shell.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd tuckit && git add tuckit/web/static/web/app.css tests/web/test_home_shell.py
git commit -m "feat(web): restyle Capture as solid teal primary CTA"
```

---

### Task 7: Full-suite + visual verification

**Files:** none (verification only).

- [ ] **Step 1: Run the web test suite**

Run: `cd tuckit && uv run pytest tests/web -q`
Expected: all pass. In particular `tests/web/test_design_system.py` (token cascade) and `tests/web/test_home_shell.py` green.

- [ ] **Step 2: Guard against literal hex / hardcoded radius in the diff**

Run: `cd tuckit && git diff main -- tuckit/web/static/web/app.css | grep -nE '^\+' | grep -iE '#[0-9a-f]{3,6}|[0-9]+px' | grep -viE 'var\(--|width|height|min-height|font-size|letter-spacing|padding|margin|gap|top|left|right|z-index|blur|[0-9]+px [0-9]+px'`
Expected: no color/radius literals. (Box-shadow offset/blur px and layout px are allowed; colors and border-radius must be tokens.) Review any hit.

- [ ] **Step 3: Visual check in the running app (light + dark)**

Use the `run` skill (or `cd tuckit && uv run python manage.py runserver`) and load `/`. Confirm:
- Switcher: click opens a styled popover grouped by org, active workspace checked, closes on outside-click and Esc; chevron rotates; monogram + Org(caption)/Workspace(name) legible.
- Nav order: Home · Attention · Triage · In Progress · Roadmap · Activity, with Activity's clock icon distinct from In Progress's waveform.
- Bottom: compact row with Settings (icon+label) and a sun/moon icon button; no oversized bordered button.
- Capture: solid teal primary; "C" badge quiet; hover darkens.
Toggle theme both ways and re-verify all four in dark and light.

- [ ] **Step 4: Final commit (if any verification tweaks were needed)**

```bash
cd tuckit && git add -A && git commit -m "chore(web): sidebar redesign verification tweaks"
```

(If no tweaks were needed, skip.)

---

## Notes for the implementer

- Do NOT commit anything under `docs/superpowers/` — it stays untracked in this public repo (workspace rule).
- The theme toggle's Alpine logic is copied verbatim from the old button — do not "improve" the localStorage/`dataset.theme` wiring; a separate boot script elsewhere reads it on load.
- `font: inherit` in `.capture-btn` resets weight — the `font-weight: 600` MUST come after it (Task 6, Step 3).
- Django `{% regroup %}` only groups CONSECUTIVE items, which is why Task 1 sorts `switchable_workspaces` by org first. Don't skip Task 1's sort or the popover groups will fragment.
