# Slice View Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the slice slide-over panel with a grouped three-zone layout (properties cluster, dropdown status, seamless inline description) and fix the deep-link so a refresh restores the same page with the slide-over open instead of jumping to a full page.

**Architecture:** Two workstreams. **A (panel redesign)** rewrites `_slice_panel.html` + `app.css` into header/body/activity zones with an Area chip, a properties block whose Status row is a dropdown, and a seamless auto-growing description editor. **B (deep-link)** stops pushing `/slices/<id>/` and instead pushes `<current-path>?slice=<id>`; on any page load with `?slice=`, `#panel` auto-loads the panel via htmx `hx-trigger="load"`, so the slide-over is continuous across refresh. The canonical `/slices/<id>/` full page stays for shared/cold links.

**Tech Stack:** Django templates, htmx, Alpine.js, static CSS with design tokens. pytest + pytest-django.

## Global Constraints

- CSS uses `var(--token)` ONLY — no literal hex, no hardcoded radius. Surfaces use `--radius` (14px), controls `--radius-small` (9px). Accent is teal `--blue`.
- `tokens.brand.css` is shared/synced — DO NOT hand-edit it. All new rules go in `app.css`.
- Existing pytest suite must stay green (baseline: 481 passed, 1 skipped). Run `uv run pytest -q` from `tuckit/`.
- `docs/superpowers/` is local-only — never `git add` files under it (public repo boundary).
- Statuses are exactly `["idea", "planned", "building", "shipped"]` (from `slice_panel_context`); `dropped` is NOT a status option — it stays a separate action-bar action.
- Commit after each task. Branch work stays on the current branch.

---

## Workstream A — Panel redesign (C)

### Task A1: Area chip replaces the breadcrumb link

**Files:**
- Modify: `tuckit/web/templates/web/partials/_slice_panel.html:3-9`
- Modify: `tuckit/web/static/web/app.css` (replace `.panel-crumb`/`.crumb-link` block ~1599-1603)
- Test: `tests/web/test_slice_detail.py`

**Interfaces:**
- Produces: `.area-chip` anchor (links to `web:area`), present in both panel and full-page modes; panel-only `.crumb-close` button unchanged in behavior.

- [ ] **Step 1: Update the failing tests to expect the chip**

In `tests/web/test_slice_detail.py`, in `test_panel_header_title_and_status_tabs` replace the crumb assertion:

```python
    assert 'class="area-chip"' in body
    assert f'href="/{workspace.org.slug}/{workspace.slug}/areas/{a.slug}/"' in body   # chip links to area
    assert "Design" in body
```

(delete the old `assert 'class="panel-crumb"' in body` line in this test.)

In `test_full_page_hides_panel_only_chrome` replace `assert 'class="panel-crumb"' in body` with:

```python
    assert 'class="area-chip"' in body     # breadcrumb chip still shown on full page
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_slice_detail.py::test_panel_header_title_and_status_tabs tests/web/test_slice_detail.py::test_full_page_hides_panel_only_chrome -q`
Expected: FAIL (`area-chip` not found).

- [ ] **Step 3: Rewrite the header markup**

Replace `_slice_panel.html` lines 3-9 (the `<div class="panel-crumb">…</div>` block) with:

```html
  <div class="panel-crumb">
    <a class="area-chip" href="{% wurl 'web:area' slice.area.slug %}">{% icon "area" "icon area-chip-icon" %}{{ slice.area.name }}</a>
    {% if is_panel %}
    <button class="ghost crumb-close" type="button" aria-label="Close panel"
            hx-on:click="closePanel(document.getElementById('panel'))">{% icon "close" "icon" %}</button>
    {% endif %}
  </div>
```

- [ ] **Step 4: Replace the CSS**

In `app.css`, replace the `.panel-crumb`/`.crumb-link`/`.crumb-icon` rules (~1599-1603) with:

```css
.panel-crumb { display: flex; align-items: center; gap: 8px; }
.area-chip { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px;
  background: var(--paper-deep); border: 1px solid var(--line); border-radius: 20px;
  color: var(--ink-soft); font-size: 12px; text-decoration: none; width: max-content; }
.area-chip:hover { border-color: var(--border); color: var(--ink); }
.area-chip-icon { width: 13px; height: 13px; }
.crumb-close { margin-left: auto; color: var(--ink-faint); padding: 3px; line-height: 0; }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_slice_detail.py -q`
Expected: PASS (all in file).

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/templates/web/partials/_slice_panel.html tuckit/web/static/web/app.css tests/web/test_slice_detail.py
git commit -m "feat(web): Area chip replaces raw breadcrumb link in slice panel"
```

---

### Task A2: Properties block with dropdown Status (replaces full-width status tabs)

**Files:**
- Modify: `tuckit/web/templates/web/partials/_slice_panel.html` (byline `:17`, status-row `:19-29`)
- Modify: `tuckit/web/static/web/app.css` (add properties + status-menu rules; the old `.seg--tabs` slice rules ~1610-1612 become dead — remove in Task A4)
- Test: `tests/web/test_slice_detail.py`, `tests/web/test_slice_mutations.py`

**Interfaces:**
- Consumes: `statuses` list, `slice.status`, `panel_qs` from `slice_panel_context`.
- Produces: `.props` block containing `.prop-row` rows; a `.status-select` (Alpine `{open}`) with `.status-pill` trigger and `.status-menu` of `.status-opt` buttons that `hx-post` to `web:slice_status`.

- [ ] **Step 1: Update the failing tests**

In `tests/web/test_slice_detail.py::test_panel_header_title_and_status_tabs`, replace the byline + seg assertions:

```python
    assert 'class="props"' in body
    assert 'class="status-menu"' in body
    assert body.count('class="status-opt') == 4          # one option per status
    assert "status-opt--on" in body                       # active (building) option marked
    assert "Created" in body and "Updated" in body        # properties rows
```

(delete the old lines asserting `panel-byline`, `seg--tabs`, `status-dot` count == 4, `seg-item--on`, and `spec-box` in this test — `spec-box` is handled in Task A3.)

In `tests/web/test_slice_mutations.py`, find the test asserting `class="seg seg--tabs"` / `seg-item--on` (~line 47-48) and replace with:

```python
    assert 'class="status-menu"' in body           # status control re-rendered after change
    assert "status-opt--on" in body                # active option marked
```

And the test asserting `panel-byline` / `Created by you` / `Updated` (~line 122-124) — replace `panel-byline` and `Created by you` assertions with:

```python
    assert 'class="props"' in body
    assert "Created" in body
    assert "Updated" in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_slice_detail.py::test_panel_header_title_and_status_tabs -q` and `uv run pytest tests/web/test_slice_mutations.py -q`
Expected: FAIL (`props` / `status-menu` not found).

- [ ] **Step 3: Replace byline + status-row with the properties block**

Replace `_slice_panel.html` line 17 (the `.panel-byline` div) AND lines 19-29 (the `.status-row` div) with a single properties block:

```html
  <div class="props">
    <div class="prop-row">
      <span class="prop-key">Status</span>
      <div class="prop-val status-select" x-data="{open:false}" x-on:keydown.escape="open=false">
        <button type="button" class="status-pill" x-on:click="open=!open" :aria-expanded="open">
          <span class="status-dot status-dot--{{ slice.status }}"></span>{{ slice.status }}{% icon "chevron" "icon" %}
        </button>
        <div class="status-menu" x-show="open" x-cloak x-on:click.outside="open=false">
          {% for st in statuses %}
          <button type="button" class="status-opt {% if st == slice.status %}status-opt--on{% endif %}"
                  x-on:click="open=false"
                  hx-post="{% wurl 'web:slice_status' slice.id %}{{ panel_qs }}" hx-vals='{"status": "{{ st }}"}'
                  hx-target="closest .panel-inner" hx-swap="outerHTML">
            <span class="status-dot status-dot--{{ st }}"></span>{{ st }}{% if st == slice.status %}<span class="status-check">✓</span>{% endif %}
          </button>
          {% endfor %}
        </div>
      </div>
    </div>
    <div class="prop-row">
      <span class="prop-key">Created</span>
      <span class="prop-val">{% if slice.source == 'agent' %}agent{% else %}you{% endif %}</span>
    </div>
    <div class="prop-row">
      <span class="prop-key">Updated</span>
      <span class="prop-val">{{ slice.updated_at|timesince }} 전</span>
    </div>
  </div>
```

(The `Tags` row is added in Task A4 when the Context section is folded in.)

- [ ] **Step 4: Add the CSS**

Append to `app.css` (in the slice-panel redesign region):

```css
.props { border: 1px solid var(--line); border-radius: var(--radius-small); background: var(--paper-solid); padding: 2px 12px; }
.prop-row { display: flex; align-items: center; gap: 12px; min-height: 34px; border-top: 1px solid var(--line); }
.prop-row:first-child { border-top: none; }
.prop-key { flex: 0 0 76px; font-size: 12px; color: var(--ink-faint); }
.prop-val { font-size: 12px; color: var(--ink); display: flex; align-items: center; gap: 6px; }
.status-select { position: relative; }
.status-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 9px; background: var(--paper-raised); border: 1px solid var(--line); border-radius: 20px; font-size: 12px; font-weight: 600; color: var(--ink); cursor: pointer; text-transform: capitalize; }
.status-pill:hover { border-color: var(--border); }
.status-pill .icon { width: 12px; height: 12px; color: var(--ink-faint); }
.status-menu { position: absolute; z-index: 5; top: calc(100% + 4px); left: 0; min-width: 150px; padding: 4px; background: var(--paper-solid); border: 1px solid var(--line); border-radius: var(--radius-small); box-shadow: 0 8px 20px var(--shadow); }
.status-opt { display: flex; align-items: center; gap: 8px; width: 100%; padding: 6px 8px; font-size: 12px; color: var(--ink); background: none; border: none; border-radius: var(--radius-small); cursor: pointer; text-align: left; text-transform: capitalize; }
.status-opt:hover { background: var(--paper-deep); }
.status-opt--on { font-weight: 600; }
.status-check { margin-left: auto; color: var(--blue); }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_slice_detail.py -q tests/web/test_slice_mutations.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/templates/web/partials/_slice_panel.html tuckit/web/static/web/app.css tests/web/test_slice_detail.py tests/web/test_slice_mutations.py
git commit -m "feat(web): properties block with dropdown status replaces full-width status tabs"
```

---

### Task A3: Seamless inline description editor

**Files:**
- Modify: `tuckit/web/templates/web/partials/_slice_panel.html` (spec block `:31-38`)
- Modify: `tuckit/web/static/web/app.css` (redefine `.spec-edit`; drop `.spec-box`)
- Modify: `tuckit/web/templates/web/base.html` (add `autosize` helper JS)
- Test: `tests/web/test_slice_detail.py`

**Interfaces:**
- Consumes: `spec_html`, `slice.spec`, `panel_qs`. Panel root `x-data` already declares `editSpec`.
- Produces: `.desc-block` with a `.section-label` "Description", a `.spec` display, and a seamless auto-growing `.spec-edit` textarea (saves on blur / ⌘+Enter, cancels on Esc). Global JS `autosize(el)`.

- [ ] **Step 1: Update/replace the failing tests**

`test_spec_html_is_sanitized` scopes to `<div class="spec"…</div>` — keep it. Add a new test to `tests/web/test_slice_detail.py`:

```python
@pytest.mark.django_db
def test_description_is_seamless_inline_edit(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    p = f"/{workspace.org.slug}/{workspace.slug}"
    s = create_slice(create_area(workspace, "Design"), "설명")
    body = client_local.get(f"{p}/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="section-label">Description' in body   # labeled section
    assert 'class="spec-edit"' in body                   # inline editor present
    assert 'rows="6"' not in body                        # no big fixed textarea jump
    assert 'class="spec-box"' not in body                # framed box removed
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/web/test_slice_detail.py::test_description_is_seamless_inline_edit -q`
Expected: FAIL.

- [ ] **Step 3: Replace the spec block markup**

Replace `_slice_panel.html` lines 31-38 (the `<div class="spec-box">…</div>`) with:

```html
  <div class="desc-block">
    <div class="section-label">Description</div>
    <div class="spec" x-show="!editSpec"
         x-on:click="editSpec=true; $nextTick(()=>{ $refs.specEdit.focus(); autosize($refs.specEdit); })">{% if slice.spec %}{{ spec_html|safe }}{% else %}<span class="muted">설명을 추가하려면 클릭…</span>{% endif %}</div>
    <form x-show="editSpec" x-cloak hx-post="{% wurl 'web:slice_edit' slice.id %}{{ panel_qs }}"
          hx-target="closest .panel-inner" hx-swap="outerHTML">
      <textarea name="spec" class="spec-edit" x-ref="specEdit" rows="2"
                x-on:input="autosize($event.target)"
                x-on:keydown.escape.stop="editSpec=false"
                x-on:keydown.meta.enter.prevent="$el.form.requestSubmit()"
                x-on:keydown.ctrl.enter.prevent="$el.form.requestSubmit()"
                x-on:blur="$el.value !== $el.defaultValue ? $el.form.requestSubmit() : (editSpec=false)">{{ slice.spec }}</textarea>
    </form>
  </div>
```

- [ ] **Step 4: Add the `autosize` helper to base.html**

In `tuckit/web/templates/web/base.html`, inside the existing `<script>` block that defines `closePanel` (right after the `function closePanel(...)` definition, ~line 97), add:

```javascript
    /* Grow a textarea to fit its content — used by the seamless description editor
       so entering edit mode never jumps to a fixed-height box. */
    function autosize(el) { el.style.height = "auto"; el.style.height = el.scrollHeight + "px"; }
```

- [ ] **Step 5: Replace the CSS — seamless editor, drop the box**

In `app.css`, change the `.spec-edit` rule (~890) so the editor visually matches the reading view (same paper background, same font/line-height, no frame), and delete the `.spec-box` rules (~1613-1615):

```css
.spec-edit { width: 100%; background: transparent; border: none; color: var(--ink);
  font: inherit; line-height: 1.6; padding: 0; resize: none; overflow: hidden; }
.spec-edit:focus { outline: none; }
```

(Remove the old `.spec-edit { … border … padding … background: var(--paper-raised) }` declaration and its `:focus` border rule, and remove `.spec-box`/`.spec-box .spec-edit`.)

- [ ] **Step 6: Run to verify pass**

Run: `uv run pytest tests/web/test_slice_detail.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/partials/_slice_panel.html tuckit/web/templates/web/base.html tuckit/web/static/web/app.css tests/web/test_slice_detail.py
git commit -m "feat(web): seamless auto-growing inline description editor"
```

---

### Task A4: Fold Context tags into properties + three-zone spacing + cleanup

**Files:**
- Modify: `tuckit/web/templates/web/partials/_slice_panel.html` (properties `Tags` row; remove standalone Context section `:63-67`; unify section labels; wrap zones)
- Modify: `tuckit/web/static/web/app.css` (`.panel-inner` zone spacing, unified `.section-label`, remove dead `.seg--tabs`, `.panel-byline`, `.context-block`, `.bites-label` size drift)
- Test: `tests/web/test_slice_detail.py`

**Interfaces:**
- Consumes: `_slice_tags.html` partial (reused inside the properties block).
- Produces: `Tags` prop-row; standalone `Context` section removed; consistent `.section-label` tone for Description / Bites / Activity.

- [ ] **Step 1: Update the failing test**

Replace `test_context_tags_have_no_area_chip` in `tests/web/test_slice_detail.py` with:

```python
@pytest.mark.django_db
def test_tags_live_in_properties_not_a_context_section(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    p = f"/{workspace.org.slug}/{workspace.slug}"
    s = create_slice(create_area(workspace, "Design"), "태그")
    body = client_local.get(f"{p}/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="section-label">Context' not in body   # standalone Context section removed
    assert '<span class="prop-key">Tags' in body          # tags now a property row
    assert "Add tag" in body
    assert "meta-area" not in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/web/test_slice_detail.py::test_tags_live_in_properties_not_a_context_section -q`
Expected: FAIL.

- [ ] **Step 3: Add the Tags prop-row**

In `_slice_panel.html`, inside the `.props` block (from Task A2), add a fourth row after the `Updated` row:

```html
    <div class="prop-row prop-row--tags">
      <span class="prop-key">Tags</span>
      <div class="prop-val">{% include "web/partials/_slice_tags.html" %}</div>
    </div>
```

- [ ] **Step 4: Remove the standalone Context section**

Delete the Context block in `_slice_panel.html` (the `<div class="panel-divider"></div>` + `<div class="context-block">…{% include _slice_tags %}…</div>`, original lines 63-67).

- [ ] **Step 5: Unify section labels + wrap zones**

Ensure Description (Task A3), Bites, and Activity each lead with `<div class="section-label">…</div>`. Change the Bites header label from `<span class="bites-label">Bites</span>` to `<span class="section-label">Bites</span>` (keep the count + progress + add-button in the same `.bites-head` row). Remove the now-unused `.panel-divider` before Activity (spacing handles separation).

- [ ] **Step 6: CSS — zone spacing, unified label, remove dead rules**

In `app.css`:

```css
.panel-inner { display: flex; flex-direction: column; gap: 20px; padding: 22px; }  /* larger gap = zone separation */
.section-label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--ink-soft); margin-bottom: 8px; }
.desc-block, .bites-block, .slice-activity { display: flex; flex-direction: column; }
.prop-row--tags { align-items: flex-start; padding: 6px 0; }
.prop-row--tags .prop-val { flex-wrap: wrap; }
```

Delete now-dead rules: `.seg--tabs` and `.seg--tabs .seg-item` (~1610-1612), `.panel-byline` (~1607), `.bites-label` (~1618), `.context-block` if any, and the standalone `.panel-divider` rule if no longer referenced (grep first).

- [ ] **Step 7: Run the full slice suite**

Run: `uv run pytest tests/web/test_slice_detail.py tests/web/test_slice_mutations.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tuckit/web/templates/web/partials/_slice_panel.html tuckit/web/static/web/app.css tests/web/test_slice_detail.py
git commit -m "feat(web): fold tags into properties, three-zone spacing, unified labels"
```

---

## Workstream B — Deep-link restore (D1)

### Task B1: Push `<current-path>?slice=<id>` instead of the slice path

**Files:**
- Modify: `tuckit/web/templatetags/web_extras.py` (add `slice_push_url` tag)
- Modify: `tuckit/web/templates/web/partials/_slice_row.html:2-3`, `_slice_card.html:2-3`
- Test: `tests/web/test_slice_routing.py` (new)

**Interfaces:**
- Produces: `{% slice_push_url slice.id %}` → current request path with `slice=<id>` merged into the query (existing `slice`/`panel` params dropped), path-only (no host). Used as the `hx-push-url` value on slice rows/cards. The `href` stays the canonical `web:slice` URL (no-JS / open-in-new-tab).

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_slice_routing.py`:

```python
import pytest
from django.test import RequestFactory
from tuckit.web.templatetags.web_extras import slice_push_url


def _ctx(path):
    return {"request": RequestFactory().get(path)}


def test_slice_push_url_appends_param_to_current_path():
    assert slice_push_url(_ctx("/acme/main/home"), 42) == "/acme/main/home?slice=42"


def test_slice_push_url_preserves_other_query_and_replaces_slice():
    out = slice_push_url(_ctx("/acme/main/board?view=board&slice=9"), 42)
    assert out == "/acme/main/board?view=board&slice=42"


def test_slice_push_url_drops_panel_param():
    assert slice_push_url(_ctx("/acme/main/home?panel=1"), 7) == "/acme/main/home?slice=7"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/web/test_slice_routing.py -q`
Expected: FAIL (`cannot import name 'slice_push_url'`).

- [ ] **Step 3: Implement the tag**

In `tuckit/web/templatetags/web_extras.py`, add near the top (after existing imports add `urllib.parse`):

```python
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


@register.simple_tag(name="slice_push_url", takes_context=True)
def slice_push_url(context, slice_id):
    """Path (no host) for the current page with `slice=<id>` merged into the query,
    dropping any existing `slice`/`panel` params. htmx pushes this so a refresh
    restores the same list page with the slide-over reopened."""
    request = context["request"]
    parts = urlsplit(request.get_full_path())
    query = [(k, v) for k, v in parse_qsl(parts.query) if k not in ("slice", "panel")]
    query.append(("slice", str(slice_id)))
    return urlunsplit(("", "", parts.path, urlencode(query), ""))
```

- [ ] **Step 4: Use it in the row and card**

`_slice_row.html` line 2-3 — change `hx-push-url="true"` to the tag:

```html
<a class="slice-row" href="{% wurl 'web:slice' slice.id %}"
   hx-get="{% wurl 'web:slice' slice.id %}?panel=1" hx-target="#panel" hx-push-url="{% slice_push_url slice.id %}">
```

`_slice_card.html` line 3 — change `hx-push-url="{% wurl 'web:slice' slice.id %}"` to:

```html
     hx-get="{% wurl 'web:slice' slice.id %}?panel=1" hx-target="#panel" hx-push-url="{% slice_push_url slice.id %}">
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/web/test_slice_routing.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/templatetags/web_extras.py tuckit/web/templates/web/partials/_slice_row.html tuckit/web/templates/web/partials/_slice_card.html tests/web/test_slice_routing.py
git commit -m "feat(web): slice click pushes current-path?slice=<id> for continuous slide-over"
```

---

### Task B2: Restore the slide-over on load when `?slice=<id>` is present

**Files:**
- Modify: `tuckit/web/templates/web/base.html:62-64` (`#panel` div)
- Test: `tests/web/test_slice_routing.py`

**Interfaces:**
- Consumes: `request.GET.slice` (available via the `request` context processor). Reuses the existing `web:slice … ?panel=1` endpoint (returns the panel fragment when `HX-Request`).
- Produces: `#panel` self-loads the panel via `hx-trigger="load"` when the URL carries `?slice=<id>`.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_slice_routing.py`:

```python
@pytest.mark.django_db
def test_page_with_slice_param_autoloads_panel(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    p = f"/{workspace.org.slug}/{workspace.slug}"
    s = create_slice(create_area(workspace, "Design"), "복원")
    body = client_local.get(f"{p}/?slice={s.id}").content.decode()   # home is /{org}/{ws}/
    assert 'hx-trigger="load"' in body
    assert f'/slices/{s.id}/?panel=1' in body    # panel endpoint wired into #panel

@pytest.mark.django_db
def test_page_without_slice_param_does_not_autoload(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    body = client_local.get(f"{p}/").content.decode()
    assert 'id="panel"' in body
    assert 'hx-trigger="load"' not in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/web/test_slice_routing.py -q`
Expected: FAIL (`hx-trigger="load"` absent).

- [ ] **Step 3: Wire the auto-load into `#panel`**

In `base.html`, replace the `#panel` opening tag (lines 62-64) with:

```html
  <div id="panel" role="dialog" aria-modal="true" aria-labelledby="panel-title"
       {% if request.GET.slice %}hx-get="{% wurl 'web:slice' request.GET.slice %}?panel=1" hx-trigger="load" hx-target="#panel"{% endif %}
       x-on:keydown.escape="$el.innerHTML.trim() && closePanel($el)"
       x-on:keydown.tab="trapPanel($event, $el)"></div>
```

An invalid/inaccessible `slice` id makes the endpoint 404; htmx leaves `#panel` empty, degrading gracefully.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/web/test_slice_routing.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tuckit/web/templates/web/base.html tests/web/test_slice_routing.py
git commit -m "feat(web): restore slide-over on load when URL carries ?slice=<id>"
```

---

### Task B3: Strip `?slice` from the URL when the panel closes

**Files:**
- Modify: `tuckit/web/templates/web/base.html` (`closePanel` JS ~94-97)

**Interfaces:**
- Consumes: nothing new. Produces: `closePanel` also removes `slice` from `window.location` (via `history.pushState`) so a later refresh does not reopen a panel the user closed.

- [ ] **Step 1: Extend `closePanel`**

Replace the `closePanel` function body in `base.html` with:

```javascript
    function closePanel(el) {
      el.innerHTML = "";
      if (window.__panelOpener) { window.__panelOpener.focus(); window.__panelOpener = null; }
      var u = new URL(window.location.href);
      if (u.searchParams.has("slice")) {
        u.searchParams.delete("slice");
        history.pushState({}, "", u.pathname + (u.search ? u.search : "") + u.hash);
      }
    }
```

- [ ] **Step 2: Verify the suite still passes**

Run: `uv run pytest -q`
Expected: PASS (481+ passed; JS change is not unit-tested — behavior is confirmed in Task C1 live verification).

- [ ] **Step 3: Commit**

```bash
git add tuckit/web/templates/web/base.html
git commit -m "feat(web): closing the slide-over clears ?slice from the URL"
```

---

## Workstream C — Verification

### Task C1: Live end-to-end verification

**Files:** none (verification only).

- [ ] **Step 1: Full suite green**

Run: `uv run pytest -q`
Expected: all pass (≥ 481 + new routing/description tests), 1 skipped.

- [ ] **Step 2: Drive the app (use the `verify` skill)**

Start the dev server (`DJANGO_SETTINGS_MODULE=tuckit.settings uv run python manage.py runserver`) and, logged in, confirm each item by observation:

- Open a slice from Home → right slide-over opens; URL becomes `…/home?slice=<id>`.
- **Refresh** → same Home page renders with the slide-over reopened (no jump to a full page). This is the core bug fix.
- Close the panel → URL loses `?slice`; refresh stays on Home with no panel.
- Change status via the **dropdown** (one click opens, one click sets) → panel re-renders with the new status marked.
- Click the description → edits **in place**, same paper background and font, starts small and grows with content; blur or ⌘/Ctrl+Enter saves, Esc cancels — no jump to a big empty box.
- Area **chip** is styled (filled pill, not a raw purple underlined link) in both the slide-over and the canonical `/slices/<id>/` full page. If it still renders raw, hard-refresh to rule out a stale cached `app.css`, then confirm.
- Open a shared canonical link `/slices/<id>/` directly → intentional full page with the Area chip as breadcrumb, no close `×`, no "Open full page".

- [ ] **Step 3: Report** PASS/FAIL with screenshots per the verify skill. Fix and re-verify any FAIL before completion.

---

## Self-Review notes

- **Spec coverage:** D1 → B1/B2/B3 + canonical full page (A1 chip serves as breadcrumb, existing `test_full_page_hides_panel_only_chrome`). C layout → A2 (properties+status), A4 (tags fold, zones, labels). Status dropdown → A2. Seamless description → A3. Area chip → A1. Live confirm of the stale-CSS "Core" symptom → C1. Out-of-scope items (i18n, list redesigns) intentionally excluded.
- **Broken-by-redesign tests** are updated inside the task that changes the markup (A1, A2, A3, A4), following TDD (update expectation → see fail → implement → pass).
- **Type/name consistency:** `slice_push_url(context, slice_id)` defined in B1, consumed in B1 templates; `autosize(el)` defined in A3, consumed in A3; `.status-menu`/`.status-opt`/`.props`/`.area-chip`/`.spec-edit` class names match across template + CSS + tests.
- **Route confirmed:** home is `/{org}/{ws}/` (`urls.py:60`, `name="home"`), so B2's test uses `f"{p}/"`.
