# Slice View Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the slice detail/panel layout to match `slice_review.png`'s "After (Proposed)" — breadcrumb, larger title, wide status tabs, framed spec, Bites progress + empty-state card, Context section, Activity timeline, and a bottom action bar — using existing design tokens only.

**Architecture:** One shared partial (`_slice_panel.html`) renders both the 420px slide-over and the full page. An `is_panel` flag threaded through the context (and re-appended as `?panel=1` on htmx mutation URLs) makes panel-only chrome (close button, "Open full page") survive htmx swaps. All styling reuses existing CSS tokens; no token edits, no emoji, no new JS primitives.

**Tech Stack:** Django templates, htmx, Alpine.js, static CSS with design tokens, pytest + Django test client.

## Global Constraints

- **Design system 100% unchanged.** Colors via `var(--token)` ONLY — no literal hex. Radius via `--radius` (14px surfaces) / `--radius-small` (9px controls) ONLY — no hardcoded radius. Fonts stay Onest (sans, `inherit`) / IBM Plex Mono (`var(--mono)`). Accent is `--blue`. Status colors via existing `.status-dot--{status}` classes and `--good`/`--warn`.
- **No new tokens.** `tokens.brand.css` / `tokens.product.css` must not change; the drift test `tests/web/test_design_system.py` must stay green.
- **No emoji** in status tabs or anywhere; use existing `.status-dot--{status}` + the SVG icon set (`{% icon "name" %}`: `area`, `plus`, `close`, `check`, `chevron`, `note`, `activity`, …).
- **No new UI primitives** (no dropdown/popover). Title stays click-to-edit. Buttons reuse `.ghost`.
- **No Priority field, no model migration.** Metadata uses only existing fields.
- CSS lives in `tuckit/web/static/web/app.css` only (screen components). Never edit `base.css` or the token files for this work.
- Tenant-scoped URLs use `{% wurl 'web:name' args %}`. Test URL prefix is `/{org.slug}/{ws.slug}`.
- Korean UI copy where the review shows Korean (empty-state text, "Updated … 전").

---

## File Structure

- `tuckit/web/panel.py` — context builder gains `is_panel`, `panel_qs`, `bites_done`, `bites_total`, `bites_pct`.
- `tuckit/web/views/slices.py` — pass `is_panel` into the context.
- `tuckit/web/views/mutations.py` — `_panel()` reads `?panel=1` and threads `is_panel`.
- `tuckit/web/templates/web/partials/_slice_panel.html` — full structural rewrite.
- `tuckit/web/templates/web/partials/_slice_tags.html` — drop area chip, relabel add button.
- `tuckit/web/templates/web/partials/_activity_row.html` — add timeline node span.
- `tuckit/web/static/web/app.css` — new component styles (tokens only).
- `tests/web/test_slice_detail.py`, `tests/web/test_slice_mutations.py` — new + updated assertions.

---

## Task 1: Context plumbing (`is_panel`, `panel_qs`, bite progress numbers)

**Files:**
- Modify: `tuckit/web/panel.py`
- Modify: `tuckit/web/views/slices.py:27-36`
- Modify: `tuckit/web/views/mutations.py:19-20`
- Test: `tests/web/test_slice_detail.py`

**Interfaces:**
- Produces: `slice_panel_context(slice_, is_panel: bool = False) -> dict` with keys `slice, spec_html, bites, statuses, activity, is_panel, panel_qs, bites_done, bites_total, bites_pct`.
- `panel_qs` is `"?panel=1"` when `is_panel` else `""`.
- Consumes: `tuckit.core.services.bites.bite_progress(slice_) -> tuple[int,int]` (already exists).

- [ ] **Step 1: Create the feature branch**

Run:
```bash
cd /Users/goddessana/Developments/tuckit-projects/tuckit
git checkout -b slice-view-redesign
```

- [ ] **Step 2: Write the failing test for context flags + progress numbers**

Add to `tests/web/test_slice_detail.py`:
```python
@pytest.mark.django_db
def test_slice_panel_context_flags_and_progress(workspace):
    from tuckit.web.panel import slice_panel_context
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    from tuckit.core.services.bites import create_bite
    s = create_slice(create_area(workspace, "Design"), "T")
    create_bite(s, "a", status="done")
    create_bite(s, "b")  # 1 of 2 done -> 50%

    panel = slice_panel_context(s, is_panel=True)
    assert panel["is_panel"] is True
    assert panel["panel_qs"] == "?panel=1"
    assert (panel["bites_done"], panel["bites_total"], panel["bites_pct"]) == (1, 2, 50)

    page = slice_panel_context(s)  # default is_panel=False
    assert page["is_panel"] is False
    assert page["panel_qs"] == ""
```

- [ ] **Step 3: Run it and confirm it fails**

Run: `uv run pytest tests/web/test_slice_detail.py::test_slice_panel_context_flags_and_progress -v`
Expected: FAIL (`slice_panel_context()` takes 1 positional arg / missing keys).

- [ ] **Step 4: Update `slice_panel_context`**

In `tuckit/web/panel.py`, add the import and rewrite the function:
```python
from tuckit.core.services.activity import slice_activity
from tuckit.core.services.bites import list_bites, bite_progress


def slice_panel_context(slice_, is_panel: bool = False) -> dict:
    done, total = bite_progress(slice_)
    return {
        "slice": slice_,
        "spec_html": render_markdown_html(slice_.spec),
        "bites": list(list_bites(slice_)),
        "statuses": ["idea", "planned", "building", "shipped"],
        "activity": slice_activity(slice_),
        "is_panel": is_panel,
        "panel_qs": "?panel=1" if is_panel else "",
        "bites_done": done,
        "bites_total": total,
        "bites_pct": round(done / total * 100) if total else 0,
    }
```
(Keep the existing `render_markdown_html` / `render_spec_html` definitions above it unchanged.)

- [ ] **Step 5: Pass `is_panel` from the detail view**

In `tuckit/web/views/slices.py`, replace the body of `slice_detail` after `slice_` is resolved:
```python
    is_panel = request.GET.get("panel") == "1" and bool(request.headers.get("HX-Request"))
    ctx = slice_panel_context(slice_, is_panel=is_panel)
    template = "web/partials/_slice_panel.html" if is_panel else "web/slice_detail.html"
    return render(request, template, ctx)
```

- [ ] **Step 6: Thread `is_panel` through mutations**

In `tuckit/web/views/mutations.py`, replace `_panel`:
```python
def _panel(request, slice_):
    is_panel = request.GET.get("panel") == "1"
    return render(
        request, "web/partials/_slice_panel.html",
        slice_panel_context(slice_, is_panel=is_panel),
    )
```

- [ ] **Step 7: Run the test and the existing slice suites**

Run: `uv run pytest tests/web/test_slice_detail.py tests/web/test_slice_mutations.py -v`
Expected: the new test PASSES; existing tests still pass (only template not yet changed).

- [ ] **Step 8: Commit**

```bash
git add tuckit/web/panel.py tuckit/web/views/slices.py tuckit/web/views/mutations.py tests/web/test_slice_detail.py
git commit -m "feat(web): thread is_panel + bite progress into slice panel context"
```

---

## Task 2: Header, title, byline, wide status tabs, framed spec

**Files:**
- Modify: `tuckit/web/templates/web/partials/_slice_panel.html` (top half)
- Modify: `tuckit/web/static/web/app.css`
- Modify: `tests/web/test_slice_mutations.py` (update `test_slice_panel_has_meta_footer`)
- Test: `tests/web/test_slice_detail.py`

**Interfaces:**
- Consumes from Task 1: `is_panel`, `panel_qs`.
- Produces markup classes later tasks/tests rely on: `.panel-crumb`, `.crumb-link`, `.panel-titlebar`, `.panel-byline`, `.seg--tabs`, `.spec-box`. Keeps existing `.seg`, `.seg-item`, `.seg-item--on`, `.spec`, `.title-edit`, `.spec-edit`, `.status-dot--{st}`.

- [ ] **Step 1: Write failing tests for the new top-of-panel structure**

Add to `tests/web/test_slice_detail.py`:
```python
@pytest.mark.django_db
def test_panel_header_title_and_status_tabs(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    s = create_slice(a, "다크모드 폴리시", status="building")

    # panel context
    body = client_local.get(f"{p}/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="panel-crumb"' in body
    assert f'href="/{workspace.org.slug}/{workspace.slug}/areas/{a.slug}/"' in body   # breadcrumb links to area
    assert "Design" in body
    assert 'class="panel-byline"' in body
    assert "seg--tabs" in body
    assert body.count('class="status-dot status-dot--') == 4    # a dot on every status tab
    assert "seg-item--on" in body                               # active (building) tab
    assert 'class="spec-box"' in body
    # panel-only chrome present
    assert "closePanel" in body
    assert "Open full page" in body


@pytest.mark.django_db
def test_full_page_hides_panel_only_chrome(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    s = create_slice(a, "전체페이지")
    body = client_local.get(f"{p}/slices/{s.id}/").content.decode()   # full page, no panel=1
    assert "closePanel" not in body        # no close button on the full page
    assert "Open full page" not in body    # no self-link on the full page
    assert 'class="panel-crumb"' in body   # breadcrumb still shown
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/web/test_slice_detail.py::test_panel_header_title_and_status_tabs tests/web/test_slice_detail.py::test_full_page_hides_panel_only_chrome -v`
Expected: FAIL (classes/strings not present yet).

- [ ] **Step 3: Rewrite the top of `_slice_panel.html`**

Replace lines 2–31 (from `<div class="panel-inner" ...>` through the closing `</form>` of the spec edit) with:
```django
<div class="panel-inner" x-data="{editTitle:false, editSpec:false}">
  <div class="panel-crumb">
    <a class="crumb-link" href="{% wurl 'web:area' slice.area.slug %}">{% icon "area" "icon crumb-icon" %}{{ slice.area.name }}</a>
    {% if is_panel %}
    <button class="ghost crumb-close" type="button" aria-label="Close panel"
            hx-on:click="closePanel(document.getElementById('panel'))">{% icon "close" "icon" %}</button>
    {% endif %}
  </div>

  <div class="panel-titlebar">
    <span class="panel-title" id="panel-title" x-show="!editTitle" x-on:click="editTitle=true">{{ slice.title }}</span>
    <input name="title" value="{{ slice.title }}" class="title-edit" x-show="editTitle" x-cloak
           hx-post="{% wurl 'web:slice_edit' slice.id %}{{ panel_qs }}" hx-trigger="blur, keydown[key=='Enter']"
           hx-target="closest .panel-inner" hx-swap="outerHTML">
  </div>
  <div class="panel-byline">Created by {% if slice.source == 'agent' %}agent{% else %}you{% endif %} · Updated {{ slice.updated_at|timesince }} 전</div>

  <div class="status-row">
    <div class="seg seg--tabs">
      {% for st in statuses %}
        <button class="seg-item {% if st == slice.status %}seg-item--on{% endif %}"
                hx-post="{% wurl 'web:slice_status' slice.id %}{{ panel_qs }}" hx-vals='{"status": "{{ st }}"}'
                hx-target="closest .panel-inner" hx-swap="outerHTML">
          <span class="status-dot status-dot--{{ st }}"></span>{{ st }}
        </button>
      {% endfor %}
    </div>
  </div>

  <div class="spec-box">
    <div class="spec" x-show="!editSpec" x-on:click="editSpec=true">{% if slice.spec %}{{ spec_html|safe }}{% else %}<span class="muted">설명을 추가하려면 클릭…</span>{% endif %}</div>
    <form x-show="editSpec" x-cloak hx-post="{% wurl 'web:slice_edit' slice.id %}{{ panel_qs }}"
          hx-target="closest .panel-inner" hx-swap="outerHTML">
      <textarea name="spec" class="spec-edit" rows="6">{{ slice.spec }}</textarea>
      <button class="ghost" type="submit">Save</button>
    </form>
  </div>
```
Leave the rest of the file (from `<div class="group-label"><span>Bites</span>…` onward) unchanged for now — Task 3 rewrites it.

- [ ] **Step 4: Add the CSS for header / title / byline / tabs / spec box**

Append to `tuckit/web/static/web/app.css` (all values are tokens or plain px sizes):
```css
/* --- Slice panel redesign --- */
.panel-crumb { display: flex; align-items: center; gap: 8px; }
.crumb-link { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-faint); font-size: 12px; text-decoration: none; }
.crumb-link:hover { color: var(--ink); }
.crumb-icon { width: 14px; height: 14px; }
.crumb-close { margin-left: auto; color: var(--ink-faint); padding: 3px; line-height: 0; }

.panel-titlebar { display: flex; align-items: flex-start; gap: 10px; }
.panel-title { font-size: 22px; font-weight: 600; line-height: 1.3; letter-spacing: -0.02em; cursor: text; }
.panel-byline { font-size: 12px; color: var(--ink-faint); margin-top: -6px; }

/* Wide segmented status control: 4 equal columns, a dot on every tab. */
.seg--tabs { display: grid; grid-template-columns: repeat(4, 1fr); width: 100%; }
.seg--tabs .seg-item { justify-content: center; padding: 8px 6px; }

.spec-box { border: 1px solid var(--line); border-radius: var(--radius-small); background: var(--paper-solid); padding: 11px 13px; }
.spec-box .spec { cursor: text; }
.spec-box .spec-edit { margin-bottom: 8px; }
```

- [ ] **Step 5: Update the now-stale meta-footer test**

The old bottom `panel-meta` footer is being removed (its info moved into `.panel-byline`). In `tests/web/test_slice_mutations.py`, replace `test_slice_panel_has_meta_footer` with:
```python
@pytest.mark.django_db
def test_slice_panel_shows_byline(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    p = f"/{workspace.org.slug}/{workspace.slug}"
    s = create_slice(create_area(workspace, "제품"), "메타 확인")  # default source=human
    body = client_local.get(f"{p}/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="panel-byline"' in body
    assert "Created by you" in body
    assert "Updated" in body
```
(Note: the `.panel-meta` footer markup is deleted in Task 3 when the lower half is rewritten; this test is updated now so it describes the target state.)

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/web/test_slice_detail.py tests/web/test_slice_mutations.py -v`
Expected: new header/full-page tests PASS; `test_status_control_is_segmented` still PASSES (`.seg`/`seg-item--on` retained); `test_slice_panel_shows_byline` PASSES.

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/partials/_slice_panel.html tuckit/web/static/web/app.css tests/web/test_slice_detail.py tests/web/test_slice_mutations.py
git commit -m "feat(web): slice panel header, byline, wide status tabs, framed spec"
```

---

## Task 3: Bites block (count + progress + empty-state card) and lower-panel rewrite

**Files:**
- Modify: `tuckit/web/templates/web/partials/_slice_panel.html` (lower half)
- Modify: `tuckit/web/static/web/app.css`
- Test: `tests/web/test_slice_detail.py`

**Interfaces:**
- Consumes from Task 1: `bites`, `bites_done`, `bites_total`, `bites_pct`, `panel_qs`, `activity`, `is_panel`.
- Produces classes tests rely on: `.bites-block`, `.bites-head`, `.bites-label`, `.bites-empty`, `.section-label`, `.panel-divider`, `.context-block`, `.timeline`, `.action-bar`, `.action-drop`. REUSES existing `.row-prog-track` (+ its `i` fill) for the progress bar — no new progress class. Keeps `.bite-add`, `#bites-{id}`, `.slice-activity`, `.activity-row`, `.dropped-tag`.
- The always-present add input carries `x-ref="biteAdd"`; the header button and empty-state CTA focus it via `$refs.biteAdd.focus()`.

- [ ] **Step 1: Write failing tests for bites progress + empty state + action bar**

Add to `tests/web/test_slice_detail.py`:
```python
@pytest.mark.django_db
def test_bites_progress_and_empty_state(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    from tuckit.core.services.bites import create_bite
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    s = create_slice(a, "S")

    # empty: card shown, no count
    body = client_local.get(f"{p}/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="bites-empty"' in body
    assert "아직 bite가 없습니다" in body
    assert 'class="row-prog-track"' not in body   # no progress bar when there are no bites

    # with bites: count + progress shown, card gone
    create_bite(s, "a", status="done")
    create_bite(s, "b")
    body = client_local.get(f"{p}/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="bites-empty"' not in body
    assert "1/2" in body
    assert 'class="row-prog-track"' in body
    assert "width: 50%" in body


@pytest.mark.django_db
def test_action_bar_has_copy_and_drop(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    p = f"/{workspace.org.slug}/{workspace.slug}"
    s = create_slice(create_area(workspace, "Design"), "액션", status="building")
    body = client_local.get(f"{p}/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="action-bar"' in body
    assert "Copy link" in body
    assert "Drop slice" in body
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/web/test_slice_detail.py::test_bites_progress_and_empty_state tests/web/test_slice_detail.py::test_action_bar_has_copy_and_drop -v`
Expected: FAIL.

- [ ] **Step 3: Rewrite the lower half of `_slice_panel.html`**

Replace everything from the old `<div class="group-label"><span>Bites</span>…` line down to the final `</div>` that closes `.panel-inner` with:
```django
  <div class="bites-block">
    <div class="bites-head">
      <span class="bites-label">Bites</span>
      {% if bites_total %}
        <span class="group-count">{{ bites_done }}/{{ bites_total }}</span>
        <span class="row-prog-track"><i style="width: {{ bites_pct }}%"></i></span>
      {% endif %}
      <button class="ghost bites-add-btn" type="button" x-on:click="$refs.biteAdd.focus()">{% icon "plus" "icon" %} Add bite</button>
    </div>
    <div id="bites-{{ slice.id }}">
      {% for bite in bites %}{% include "web/partials/_bite_row.html" %}{% endfor %}
    </div>
    {% if not bites %}
    <div class="bites-empty">
      <div class="bites-empty-title">아직 bite가 없습니다</div>
      <div class="bites-empty-sub">이 slice를 구현하기 위한 작은 단계를 추가해보세요.</div>
      <button class="ghost bites-empty-cta" type="button" x-on:click="$refs.biteAdd.focus()">{% icon "plus" "icon" %} Add your first bite</button>
    </div>
    {% endif %}
    <form hx-post="{% wurl 'web:bite_create' slice.id %}{{ panel_qs }}" hx-target="closest .panel-inner" hx-swap="outerHTML">
      <input name="title" placeholder="Add a bite…" class="bite-add" x-ref="biteAdd">
    </form>
  </div>

  <div class="panel-divider"></div>
  <div class="context-block">
    <div class="section-label">Context</div>
    {% include "web/partials/_slice_tags.html" %}
  </div>

  {% if activity %}
  <div class="panel-divider"></div>
  <div class="slice-activity">
    <div class="section-label">Activity</div>
    <div class="timeline">
      {% for event in activity %}{% include "web/partials/_activity_row.html" %}{% endfor %}
    </div>
  </div>
  {% endif %}

  <div class="action-bar">
    {% if slice.status == 'dropped' %}
      <span class="dropped-tag">dropped</span>
      <button class="ghost" hx-post="{% wurl 'web:slice_status' slice.id %}{{ panel_qs }}" hx-vals='{"status": "idea"}'
              hx-target="closest .panel-inner" hx-swap="outerHTML">Restore</button>
    {% else %}
      <button class="ghost action-drop" hx-post="{% wurl 'web:slice_status' slice.id %}{{ panel_qs }}" hx-vals='{"status": "dropped"}'
              hx-target="closest .panel-inner" hx-swap="outerHTML">Drop slice</button>
    {% endif %}
    <span class="action-spacer"></span>
    <button class="ghost" type="button" x-data="{copied:false}"
            x-on:click="navigator.clipboard.writeText(window.location.origin + '{% wurl 'web:slice' slice.id %}'); copied=true; setTimeout(()=>copied=false,1500)"
            x-text="copied ? 'Copied' : 'Copy link'">Copy link</button>
    {% if is_panel %}
    <a class="ghost" href="{% wurl 'web:slice' slice.id %}">Open full page →</a>
    {% endif %}
  </div>
</div>
```
This deletes the old `.panel-meta` footer and the old standalone Bites `group-label` / `Drop` `status-row`.

- [ ] **Step 4: Add the CSS for bites block, dividers, section label, action bar**

Append to `tuckit/web/static/web/app.css`:
```css
.bites-block { display: flex; flex-direction: column; gap: 4px; }
.bites-head { display: flex; align-items: center; gap: 10px; }
.bites-label { font-size: 14px; font-weight: 600; color: var(--ink); }
.bites-add-btn { margin-left: auto; display: inline-flex; align-items: center; gap: 4px; }
/* Bites progress bar REUSES the existing `.row-prog-track` component
   (app.css ~L221): 44px neutral track, `--line-strong` fill — "a quiet
   neutral fill, never the accent." No new progress CSS is added. */

.bites-empty { border: 1px solid var(--line); border-radius: var(--radius); background: var(--paper-solid);
  padding: 22px 16px; text-align: center; display: flex; flex-direction: column; align-items: center; gap: 5px; margin-top: 4px; }
.bites-empty-title { font-size: 14px; color: var(--ink-soft); }
.bites-empty-sub { font-size: 12px; color: var(--ink-faint); }
.bites-empty-cta { margin-top: 8px; display: inline-flex; align-items: center; gap: 5px; }

.section-label { font-size: 13px; font-weight: 600; color: var(--ink); margin-bottom: 8px; }
.panel-divider { height: 1px; background: var(--line); }

.action-bar { position: sticky; bottom: 0; display: flex; align-items: center; gap: 8px;
  margin: 6px -22px -22px; padding: 13px 22px; background: var(--paper-solid); border-top: 1px solid var(--line); }
.action-spacer { flex: 1; }
.action-drop { color: var(--warn); border-color: transparent; }
.action-drop:hover { border-color: var(--warn); }
```

- [ ] **Step 5: Run the tests + full slice suite**

Run: `uv run pytest tests/web/test_slice_detail.py tests/web/test_slice_mutations.py -v`
Expected: new tests PASS; `test_slice_panel_active_shows_drop_control` ("Drop") and `test_slice_panel_dropped_shows_restore` ("Restore") still PASS; `test_slice_panel_shows_its_activity_thread` (`slice-activity`, `activity-row`) still PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/templates/web/partials/_slice_panel.html tuckit/web/static/web/app.css tests/web/test_slice_detail.py
git commit -m "feat(web): slice bites progress, empty-state card, context + sticky action bar"
```

---

## Task 4: Context tags cleanup + Activity timeline styling

**Files:**
- Modify: `tuckit/web/templates/web/partials/_slice_tags.html`
- Modify: `tuckit/web/templates/web/partials/_activity_row.html`
- Modify: `tuckit/web/static/web/app.css`
- Test: `tests/web/test_slice_detail.py`

**Interfaces:**
- Consumes: `.timeline` wrapper (Task 3) and `.section-label "Context"` (Task 3).
- Produces: `_slice_tags.html` without the area chip and with an "＋ Add tag" button; `_activity_row.html` with a leading `.tl-node` span that is `display:none` unless inside `.timeline` (so the global activity feed is unaffected).

- [ ] **Step 1: Write failing tests**

Add to `tests/web/test_slice_detail.py`:
```python
@pytest.mark.django_db
def test_context_tags_have_no_area_chip(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    s = create_slice(a, "태그")
    body = client_local.get(f"{p}/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="section-label">Context' in body
    assert "meta-area" not in body        # area chip removed from the tags row
    assert "Add tag" in body


@pytest.mark.django_db
def test_activity_timeline_has_nodes(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice, set_slice_status
    p = f"/{workspace.org.slug}/{workspace.slug}"
    s = create_slice(create_area(workspace, "Design"), "타임라인", status="idea")
    set_slice_status(s, "building")
    body = client_local.get(f"{p}/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="timeline"' in body
    assert 'class="tl-node"' in body      # a node marker per activity row
```

- [ ] **Step 2: Run them and confirm they fail**

Run: `uv run pytest tests/web/test_slice_detail.py::test_context_tags_have_no_area_chip tests/web/test_slice_detail.py::test_activity_timeline_has_nodes -v`
Expected: FAIL.

- [ ] **Step 3: Remove the area chip and relabel the add button in `_slice_tags.html`**

Rewrite `tuckit/web/templates/web/partials/_slice_tags.html`:
```django
{% load web_extras %}
<div class="slice-tags" id="slice-tags-{{ slice.id }}" x-data="{adding:false}">
  {% for t in slice.tags.all %}
    <span class="tag"><span class="tag-hash">#</span>{{ t.name }}<button class="tag-x" type="button"
      hx-post="{% wurl 'web:slice_tags' slice.id %}" hx-vals='{"remove": "{{ t.name }}"}'
      hx-target="#slice-tags-{{ slice.id }}" hx-swap="outerHTML" aria-label="Remove tag">×</button></span>
  {% endfor %}
  <button class="addtag" type="button" x-show="!adding"
          x-on:click="adding=true; $nextTick(()=>$refs.tagin.focus())">＋ Add tag</button>
  <form x-show="adding" x-cloak hx-post="{% wurl 'web:slice_tags' slice.id %}"
        hx-target="#slice-tags-{{ slice.id }}" hx-swap="outerHTML">
    <input name="add" class="tag-input" x-ref="tagin" placeholder="Tag name…" autocomplete="off">
  </form>
</div>
```
(Only the `meta-area` span is deleted and "＋ Tag" → "＋ Add tag"; everything else is unchanged.)

- [ ] **Step 4: Add the timeline node to `_activity_row.html`**

Rewrite `tuckit/web/templates/web/partials/_activity_row.html`:
```django
<div class="activity-row">
  <span class="tl-node"><i></i></span>
  <span class="activity-actor{% if event.actor == 'agent' %} is-agent{% endif %}">{% if event.actor == 'agent' %}agent{% else %}you{% endif %}</span>
  <span class="activity-body">{{ event.get_verb_display }} <span class="activity-target">{{ event.target_label }}</span>{% if event.to_value %} <span class="muted">{{ event.from_value }} → {{ event.to_value }}</span>{% endif %}</span>
  <span class="activity-time muted">{{ event.created_at|timesince }}</span>
</div>
```

- [ ] **Step 5: Add timeline CSS (scoped so other feeds are unaffected)**

Append to `tuckit/web/static/web/app.css`:
```css
/* Timeline node — only visible inside a .timeline (slice panel Activity).
   The global activity feed renders the same partial but has no .timeline
   wrapper, so the node stays hidden there. */
.tl-node { display: none; }
.timeline { position: relative; }
.timeline .activity-row { padding: 8px 0; }
.timeline .tl-node { display: flex; justify-content: center; position: relative; flex: 0 0 auto; width: 12px; align-self: stretch; }
.timeline .tl-node::before { content: ""; position: absolute; left: 50%; top: 14px; bottom: -8px; width: 1px; background: var(--line); transform: translateX(-50%); }
.timeline .activity-row:last-child .tl-node::before { display: none; }
.timeline .tl-node i { width: 7px; height: 7px; border-radius: 50%; background: var(--ink-faint); margin-top: 6px; }
```

- [ ] **Step 6: Run the new tests + the global activity feed test**

Run: `uv run pytest tests/web/test_slice_detail.py tests/web/test_phase3.py -v`
Expected: new tests PASS; existing activity-feed tests in `test_phase3.py` still PASS (node is `display:none` outside `.timeline`; markup addition is inert there).

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/partials/_slice_tags.html tuckit/web/templates/web/partials/_activity_row.html tuckit/web/static/web/app.css tests/web/test_slice_detail.py
git commit -m "feat(web): Context tags cleanup + Activity timeline styling"
```

---

## Task 5: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Run the whole web suite + drift test**

Run: `uv run pytest tests/web -v`
Expected: all PASS, including `tests/web/test_design_system.py` (tokens untouched) and all slice/mutation/activity tests.

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest`
Expected: all PASS.

- [ ] **Step 3: Visual check both contexts (use the run/verify skill)**

Launch the app and confirm, in **light and dark**:
- Slide-over panel: breadcrumb → area, close `✕` works, large title click-to-edit, wide 4-tab status with dots, framed spec, Bites empty-state card then (after adding) count + 50%-style progress bar, Context tags with "＋ Add tag", Activity timeline with connector dots, sticky action bar with `Drop slice` / `Copy link` (copies URL, shows "Copied") / `Open full page →`.
- Full page (`/…/slices/<id>/`): same layout **without** the close button and **without** "Open full page".
- htmx round-trips inside the panel (change status, add bite, edit spec, add/remove tag) keep the panel chrome (close + Open full page + sticky bar) — this confirms `?panel=1` threading.

- [ ] **Step 4: Confirm the plan/spec stay untracked (public-repo boundary)**

Run: `git status --porcelain docs/superpowers`
Expected: shows `docs/superpowers/` as untracked (`??`). Do NOT `git add` it. If it ever appears staged, unstage before any merge to `main`.

---

## Self-Review

**Spec coverage:**
- Header/breadcrumb, title, byline → Task 2. ✓
- Wide status tabs (dots, no emoji) → Task 2. ✓
- Framed spec box → Task 2. ✓
- Bites count + progress + empty-state card → Task 3. ✓
- Context (tags, area chip removed) → Task 3 (label) + Task 4 (partial). ✓
- Activity timeline → Task 3 (wrapper) + Task 4 (node + CSS). ✓
- Bottom action bar (Drop slice / Copy link / Open full page panel-only) → Task 3. ✓
- Context-adaptivity (`is_panel`, `panel_qs`) → Task 1, exercised in Tasks 2–3 tests. ✓
- Details block omitted → not built (correct). ✓
- No token edits / drift test green → Task 5. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `slice_panel_context(slice_, is_panel=False)` signature and all context keys (`is_panel`, `panel_qs`, `bites_done`, `bites_total`, `bites_pct`) are defined in Task 1 and consumed consistently in Tasks 2–4. Class names introduced in Task 2/3 (`.seg--tabs`, `.spec-box`, `.progress`, `.bites-empty`, `.section-label`, `.timeline`, `.tl-node`, `.action-bar`, `.action-drop`) are referenced by matching tests. ✓
