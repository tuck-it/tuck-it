# Nav Redesign — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **DO NOT COMMIT this plan or the spec.** `docs/superpowers/` is git-ignored and must never land in the public `tuckit` repo — see the workspace's "docs/superpowers local-only" policy. Keep these files untracked.

**Goal:** Make "what's the state right now?" visible from the sidebar by adding a state-lens nav group (Attention / In Progress / Roadmap, alongside the existing Triage) with count badges, each linking to a dedicated page; add a Roadmap status-distribution board; and add a light Roadmap-distribution strip to Home. Home otherwise stays as-is.

**Architecture:** Pure read-side feature. New aggregation functions in `state.py`, three new page views/templates reusing the existing `_slice_row.html` / `_status_group.html` partials, two new count context processors, and a sidebar expansion. No model changes, no migration.

**Tech Stack:** Django 5, server-rendered templates, htmx/Alpine (only for existing patterns), uv + pytest.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-07-12-nav-and-triage-redesign-design.md` — this implements Phase 2 = part **C** of §9 (state-lens pages + light Home), **excluding the activity log / Recent-activity card, which is Phase 3**.
- **Scope decision (supersedes spec §5's full Home rebuild):** Home already renders Attention / building / planned / tail. Do NOT rebuild it into 4 cards. Home gets ONLY a compact Roadmap-distribution strip; all other Phase 2 work is the sidebar lens group + the three lens pages.
- **Base:** current `main` = `663d094` (Phase 1 + the parallel management-surfaces work already merged). Branch Phase 2 work from there.
- **No model changes → no migration.** If you find yourself writing a migration, stop and reconsider.
- **Every task ends green:** `uv run pytest -q` (baseline: **226 passed**) before each commit.
- **Reuse, don't duplicate:** render slice lists with the existing `web/partials/_slice_row.html` and `web/partials/_status_group.html`; reuse `attention_items(ws)` and `attention_label`.
- **Labels English:** `Attention`, `In Progress`, `Roadmap` (nav + page titles). Existing Korean copy on Home stays.
- **Exclude Triage-area slices from Roadmap/In-Progress** (they're pre-roadmap captures): filter `area__is_triage=False`. Exclude `status="dropped"`.
- **App label:** `core`.

---

## File Structure

**Task 1 — aggregation services**
- Modify: `tuckit/core/services/state.py` (add `roadmap_state`, `in_progress_state`; import `Bite`)
- Test: `tests/test_services_state.py`

**Task 2 — lens pages**
- Modify: `tuckit/web/views/pages.py` (add `attention`, `in_progress`, `roadmap` views; extend `home`), `tuckit/web/urls.py` (3 routes)
- Create: `tuckit/web/templates/web/attention.html`, `.../in_progress.html`, `.../roadmap.html`
- Test: `tests/web/test_lens_pages.py`

**Task 3 — count context processors**
- Modify: `tuckit/web/context_processors.py` (add `attention_count`, `in_progress_count`), `tuckit/settings.py` (register both)
- Test: `tests/web/test_shell.py`

**Task 4 — sidebar state-lens group**
- Modify: `tuckit/web/templates/web/partials/_sidebar.html`, `tuckit/web/templatetags/web_extras.py` (3 icons), `tuckit/web/static/web/app.css` (nav-count-for-attention styling if needed)
- Test: `tests/web/test_shell.py`

**Task 5 — Home Roadmap strip**
- Modify: `tuckit/web/templates/web/home.html`, `tuckit/web/static/web/app.css` (`.roadmap-strip`)
- Test: `tests/web/test_home.py`

---

## Task 1: Aggregation services (`roadmap_state`, `in_progress_state`)

**Files:**
- Modify: `tuckit/core/services/state.py`
- Test: `tests/test_services_state.py`

**Interfaces:**
- Consumes: existing `Slice`, `Bite`, `Workspace`, `Area`.
- Produces:
  - `roadmap_state(workspace) -> dict` with keys `idea|planned|building|shipped`, each a list of `Slice` (non-triage, non-dropped, sorted by area name then rank).
  - `in_progress_state(workspace) -> dict` with keys `slices` (building `Slice`s, non-triage) and `bites` (doing `Bite`s).

- [ ] **Step 1: Write failing tests**

Add to `tests/test_services_state.py`:
```python
def test_roadmap_state_buckets_non_triage_slices():
    from tuckit.core.services.areas import create_area, get_or_create_triage
    from tuckit.core.services.slices import create_slice
    from tuckit.core.services.state import roadmap_state
    from tests.factories import make_workspace  # if a helper exists; else inline below
    ws = _ws()
    a = create_area(ws, "Backend")
    create_slice(a, "idea one", status="idea")
    create_slice(a, "planned one", status="planned")
    create_slice(a, "building one", status="building")
    create_slice(a, "shipped one", status="shipped")
    create_slice(a, "dropped one", status="dropped")
    create_slice(get_or_create_triage(ws), "captured", status="idea")  # triage excluded
    rs = roadmap_state(ws)
    assert [s.title for s in rs["idea"]] == ["idea one"]        # triage 'captured' excluded
    assert [s.title for s in rs["planned"]] == ["planned one"]
    assert [s.title for s in rs["building"]] == ["building one"]
    assert [s.title for s in rs["shipped"]] == ["shipped one"]
    assert "dropped" not in rs                                   # dropped never bucketed


def test_in_progress_state_has_building_slices_and_doing_bites():
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    from tuckit.core.services.bites import create_bite
    from tuckit.core.services.state import in_progress_state
    ws = _ws()
    a = create_area(ws, "Backend")
    s = create_slice(a, "building slice", status="building")
    create_slice(a, "idea slice", status="idea")
    b = create_bite(s, "doing bite", status="doing")
    create_bite(s, "todo bite", status="todo")
    st = in_progress_state(ws)
    assert [x.title for x in st["slices"]] == ["building slice"]
    assert [x.title for x in st["bites"]] == ["doing bite"]
```
If the file has no `_ws()`/workspace helper, mirror the existing tests in this file (they already build a workspace — copy that exact setup; e.g. `test_attention_flags_stale_inbox_and_stalled_building` shows the pattern). Use the same construction, not a new factory.

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_services_state.py -k "roadmap_state or in_progress_state" -v`
Expected: FAIL (`ImportError: cannot import name 'roadmap_state'`).

- [ ] **Step 3: Implement the services**

In `tuckit/core/services/state.py`, change the import line 5 to include `Bite`:
```python
from tuckit.core.models import Area, Bite, Slice, Workspace
```
Append these functions to the file:
```python
def roadmap_state(workspace: Workspace) -> dict:
    """Non-triage, non-dropped slices grouped by roadmap status — powers the
    Roadmap board and its distribution counts."""
    slices = list(
        Slice.objects.filter(area__workspace=workspace, area__is_triage=False)
        .exclude(status="dropped")
        .select_related("area")
        .prefetch_related("tags")
    )

    def bucket(status: str) -> list:
        return sorted(
            [s for s in slices if s.status == status],
            key=lambda s: (s.area.name, s.rank),
        )

    return {
        "idea": bucket("idea"),
        "planned": bucket("planned"),
        "building": bucket("building"),
        "shipped": bucket("shipped"),
    }


def in_progress_state(workspace: Workspace) -> dict:
    """What's actively being worked right now: building slices + doing bites."""
    slices = list(
        Slice.objects.filter(
            area__workspace=workspace, area__is_triage=False, status="building"
        )
        .select_related("area")
        .prefetch_related("tags")
        .order_by("area__name", "rank")
    )
    bites = list(
        Bite.objects.filter(slice__area__workspace=workspace, status="doing")
        .select_related("slice", "slice__area")
        .order_by("slice__area__name", "rank")
    )
    return {"slices": slices, "bites": bites}
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_services_state.py -q`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

Run: `uv run pytest -q` → 228 passed (226 + 2).
```bash
git add tuckit/core/services/state.py tests/test_services_state.py
git commit -m "feat(core): roadmap_state + in_progress_state aggregations for Phase 2 lenses"
```

---

## Task 2: Lens pages (Attention / In Progress / Roadmap)

**Files:**
- Modify: `tuckit/web/views/pages.py`, `tuckit/web/urls.py`
- Create: `tuckit/web/templates/web/attention.html`, `in_progress.html`, `roadmap.html`
- Test: `tests/web/test_lens_pages.py` (new)

**Interfaces:**
- Consumes: `attention_items`, `roadmap_state`, `in_progress_state` (Task 1); partials `_slice_row.html`, `_status_group.html`, `_status_dot.html`; `attention_label` tag.
- Produces: URL names `web:attention` (`/attention/`), `web:in_progress` (`/in-progress/`), `web:roadmap` (`/roadmap/`); `home` view now also passes `roadmap` context.

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_lens_pages.py`:
```python
import pytest
from datetime import timedelta
from django.utils import timezone
from tuckit.core.models import Slice
from tuckit.core.services.areas import create_area, get_or_create_triage
from tuckit.core.services.slices import create_slice
from tuckit.core.services.bites import create_bite


@pytest.mark.django_db
def test_attention_page_lists_stale_items(client_local, workspace):
    a = create_area(workspace, "Backend")
    s = create_slice(a, "정체된 작업", status="building")
    Slice.objects.filter(pk=s.pk).update(updated_at=timezone.now() - timedelta(days=9))
    body = client_local.get("/attention/").content.decode()
    assert "정체된 작업" in body
    assert "9일째 진척 없음" in body


@pytest.mark.django_db
def test_attention_page_all_clear_when_empty(client_local, workspace):
    body = client_local.get("/attention/").content.decode()
    assert "all-clear" in body


@pytest.mark.django_db
def test_in_progress_page_shows_building_and_doing(client_local, workspace):
    a = create_area(workspace, "Backend")
    s = create_slice(a, "빌딩 슬라이스", status="building")
    create_bite(s, "두잉 바이트", status="doing")
    body = client_local.get("/in-progress/").content.decode()
    assert "빌딩 슬라이스" in body
    assert "두잉 바이트" in body


@pytest.mark.django_db
def test_roadmap_page_shows_distribution_and_slices(client_local, workspace):
    a = create_area(workspace, "Backend")
    create_slice(a, "로드맵 항목", status="planned")
    create_slice(get_or_create_triage(workspace), "캡처", status="idea")  # excluded
    body = client_local.get("/roadmap/").content.decode()
    assert "로드맵 항목" in body
    assert "Planned" in body
    assert "캡처" not in body   # triage slices excluded from roadmap
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/web/test_lens_pages.py -v`
Expected: FAIL (404 / NoReverseMatch — routes don't exist).

- [ ] **Step 3: Add the views**

Replace `tuckit/web/views/pages.py` with:
```python
from django.shortcuts import render

from tuckit.core.services.state import (
    home_state,
    attention_items,
    roadmap_state,
    in_progress_state,
)
from tuckit.web.auth import get_current_workspace


def home(request):
    ws = get_current_workspace(request)
    return render(request, "web/home.html", {
        "workspace": ws,
        "state": home_state(ws) if ws else {},
        "roadmap": roadmap_state(ws) if ws else {},
    })


def attention(request):
    ws = get_current_workspace(request)
    return render(request, "web/attention.html", {
        "items": attention_items(ws) if ws else [],
    })


def in_progress(request):
    ws = get_current_workspace(request)
    return render(request, "web/in_progress.html", {
        "state": in_progress_state(ws) if ws else {"slices": [], "bites": []},
    })


def roadmap(request):
    ws = get_current_workspace(request)
    return render(request, "web/roadmap.html", {
        "state": roadmap_state(ws) if ws else {},
    })
```

- [ ] **Step 4: Add the routes**

In `tuckit/web/urls.py`, insert after line 19 (`path("triage/", ...)`):
```python
    path("attention/", pages.attention, name="attention"),
    path("in-progress/", pages.in_progress, name="in_progress"),
    path("roadmap/", pages.roadmap, name="roadmap"),
```

- [ ] **Step 5: Create `attention.html`**

`tuckit/web/templates/web/attention.html` (reuses the Home attention rendering exactly):
```html
{% extends "web/base.html" %}
{% load web_extras %}
{% block main %}
  <div class="topbar"><h1 class="area-title">Attention</h1></div>
  {% if items %}
  <section class="group">
    <div class="panel">
      {% for it in items %}
        {% attention_label it as lbl %}
        {% include "web/partials/_slice_row.html" with slice=it.slice reason=lbl %}
      {% endfor %}
    </div>
  </section>
  {% else %}
  <section class="group">
    <div class="all-clear">{% icon "check" "icon icon-clear" %}<span>놓친 것 없어요 — 다 챙겼습니다</span></div>
  </section>
  {% endif %}
{% endblock %}
```

- [ ] **Step 6: Create `in_progress.html`**

`tuckit/web/templates/web/in_progress.html`:
```html
{% extends "web/base.html" %}
{% load web_extras %}
{% block main %}
  <div class="topbar"><h1 class="area-title">In Progress</h1></div>
  {% include "web/partials/_status_group.html" with label="Building" slices=state.slices empty_text="진행 중인 Slice가 없어요" %}
  <section class="group">
    <div class="group-label">Doing</div>
    {% if state.bites %}
      <div class="panel">
        {% for bite in state.bites %}
          <a class="slice-row" href="{% url 'web:slice' bite.slice.id %}"
             hx-get="{% url 'web:slice' bite.slice.id %}?panel=1" hx-target="#panel" hx-push-url="true">
            {% include "web/partials/_status_dot.html" with status=bite.status %}
            <span class="row-title">{{ bite.title }}</span>
            <span class="row-meta">{{ bite.slice.title }}</span>
          </a>
        {% endfor %}
      </div>
    {% else %}
      <div class="empty muted">진행 중인 Bite가 없어요</div>
    {% endif %}
  </section>
{% endblock %}
```

- [ ] **Step 7: Create `roadmap.html`**

`tuckit/web/templates/web/roadmap.html`:
```html
{% extends "web/base.html" %}
{% load web_extras %}
{% block main %}
  <div class="topbar"><h1 class="area-title">Roadmap</h1></div>
  <div class="roadmap-dist">
    <span class="rm-seg">Idea {{ state.idea|length }}</span>
    <span class="rm-seg">Planned {{ state.planned|length }}</span>
    <span class="rm-seg rm-building">Building {{ state.building|length }}</span>
    <span class="rm-seg rm-shipped">Shipped {{ state.shipped|length }}</span>
  </div>
  {% include "web/partials/_status_group.html" with label="Building" slices=state.building empty_text="—" %}
  {% include "web/partials/_status_group.html" with label="Planned" slices=state.planned empty_text="—" %}
  {% include "web/partials/_status_group.html" with label="Idea" slices=state.idea empty_text="—" %}
  {% include "web/partials/_status_group.html" with label="Shipped" slices=state.shipped empty_text="—" %}
{% endblock %}
```

- [ ] **Step 8: Run tests + commit**

Run: `uv run pytest tests/web/test_lens_pages.py -q && uv run pytest -q`
Expected: new tests PASS; full suite 232 passed (228 + 4).
```bash
git add tuckit/web/views/pages.py tuckit/web/urls.py \
  tuckit/web/templates/web/attention.html tuckit/web/templates/web/in_progress.html \
  tuckit/web/templates/web/roadmap.html tests/web/test_lens_pages.py
git commit -m "feat(web): Attention / In Progress / Roadmap lens pages"
```

---

## Task 3: Count context processors (`attention_count`, `in_progress_count`)

**Files:**
- Modify: `tuckit/web/context_processors.py`, `tuckit/settings.py`
- Test: `tests/web/test_shell.py`

**Interfaces:**
- Consumes: `attention_items` (Task 1 file), `Slice`, `Bite`.
- Produces: context vars `attention_count`, `in_progress_count` available to every template.

- [ ] **Step 1: Write failing test**

Add to `tests/web/test_shell.py`:
```python
@pytest.mark.django_db
def test_sidebar_exposes_lens_counts(client_local, workspace):
    from datetime import timedelta
    from django.utils import timezone
    from tuckit.core.models import Slice
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    a = create_area(workspace, "Backend")
    s = create_slice(a, "정체", status="building")            # counts as in-progress AND, when stale, attention
    Slice.objects.filter(pk=s.pk).update(updated_at=timezone.now() - timedelta(days=9))
    body = client_local.get("/").content.decode()
    # both lens links carry a count badge with value 1
    assert 'href="/attention/"' in body
    assert 'href="/in-progress/"' in body
```
(The count *rendering* is asserted in Task 4; here we only prove the context is wired + links exist once Task 4 lands. If you run this before Task 4 the href asserts fail — that's the RED.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/web/test_shell.py::test_sidebar_exposes_lens_counts -v`
Expected: FAIL (`href="/attention/"` not in body yet).

- [ ] **Step 3: Add the context processors**

Append to `tuckit/web/context_processors.py`:
```python
def attention_count(request):
    """Count of items needing attention (stale triage + stalled building), for
    the sidebar Attention badge."""
    from tuckit.core.services.state import attention_items

    ws = get_current_workspace(request)
    if not ws:
        return {}
    return {"attention_count": len(attention_items(ws))}


def in_progress_count(request):
    """Count of actively-worked items (building slices + doing bites), for the
    sidebar In Progress badge."""
    from tuckit.core.models import Bite, Slice

    ws = get_current_workspace(request)
    if not ws:
        return {}
    n = (
        Slice.objects.filter(
            area__workspace=ws, area__is_triage=False, status="building"
        ).count()
        + Bite.objects.filter(slice__area__workspace=ws, status="doing").count()
    )
    return {"in_progress_count": n}
```

- [ ] **Step 4: Register both in settings**

In `tuckit/settings.py`, in the `context_processors` list (after `triage_count`, line 64), add:
```python
                "tuckit.web.context_processors.attention_count",
                "tuckit.web.context_processors.in_progress_count",
```

- [ ] **Step 5: Leave the test RED for now**

This task's test depends on Task 4's sidebar markup. Run the full suite to confirm nothing else broke:
Run: `uv run pytest -q -k "not test_sidebar_exposes_lens_counts"`
Expected: 232 passed (the new test stays failing until Task 4).

- [ ] **Step 6: Commit (context wiring only)**

```bash
git add tuckit/web/context_processors.py tuckit/settings.py tests/web/test_shell.py
git commit -m "feat(web): attention_count + in_progress_count context processors"
```
(The test committed here is red until Task 4; that's an intentional cross-task pair — Task 4 turns it green. Note it in the report so the reviewer isn't surprised.)

---

## Task 4: Sidebar state-lens group (nav items + icons + badges)

**Files:**
- Modify: `tuckit/web/templates/web/partials/_sidebar.html`, `tuckit/web/templatetags/web_extras.py`
- Test: `tests/web/test_shell.py` (turns Task 3's test green + adds badge assertions)

**Interfaces:**
- Consumes: url names `web:attention`, `web:in_progress`, `web:roadmap` (Task 2); context `attention_count`, `in_progress_count` (Task 3), `triage_count` (existing).
- Produces: sidebar nav-group containing Home + the four lenses; icon keys `attention`, `in-progress`, `roadmap`.

- [ ] **Step 1: Add the three icons**

In `tuckit/web/templatetags/web_extras.py`, add to `_ICON_PATHS` (after the `triage` entry):
```python
    "attention": '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v4"/><path d="M12 17h.01"/>',
    "in-progress": '<path d="M3 12h4l2 6 4-14 2 8h6"/>',
    "roadmap": '<path d="M4 6h4v13H4zM10 3h4v16h-4zM16 9h4v10h-4z"/>',
```

- [ ] **Step 2: Expand the sidebar nav-group**

In `tuckit/web/templates/web/partials/_sidebar.html`, replace the `<nav class="nav-group">…</nav>` block (lines 6-12) with:
```html
  <nav class="nav-group">
    <a class="nav{% if request.resolver_match.url_name == 'home' %} nav--active{% endif %}"
       href="{% url 'web:home' %}">{% icon "home" %}<span class="nav-label">Home</span></a>
    <a class="nav{% if request.resolver_match.url_name == 'attention' %} nav--active{% endif %}"
       href="{% url 'web:attention' %}">{% icon "attention" %}<span class="nav-label">Attention</span>
       {% if attention_count %}<span class="nav-count">{{ attention_count }}</span>{% endif %}</a>
    <a class="nav{% if request.resolver_match.url_name == 'in_progress' %} nav--active{% endif %}"
       href="{% url 'web:in_progress' %}">{% icon "in-progress" %}<span class="nav-label">In Progress</span>
       {% if in_progress_count %}<span class="nav-count">{{ in_progress_count }}</span>{% endif %}</a>
    <a class="nav{% if request.resolver_match.url_name == 'roadmap' %} nav--active{% endif %}"
       href="{% url 'web:roadmap' %}">{% icon "roadmap" %}<span class="nav-label">Roadmap</span></a>
    <a class="nav{% if request.resolver_match.url_name == 'triage' %} nav--active{% endif %}"
       href="{% url 'web:triage' %}">{% icon "triage" %}<span class="nav-label">Triage</span>
       {% include "web/partials/_triage_count.html" %}</a>
  </nav>
```

- [ ] **Step 3: Strengthen Task 3's test into a full badge assertion**

Replace `test_sidebar_exposes_lens_counts` (added in Task 3) with:
```python
@pytest.mark.django_db
def test_sidebar_lens_group_with_counts(client_local, workspace):
    from datetime import timedelta
    from django.utils import timezone
    from tuckit.core.models import Slice
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    a = create_area(workspace, "Backend")
    s = create_slice(a, "정체", status="building")
    Slice.objects.filter(pk=s.pk).update(updated_at=timezone.now() - timedelta(days=9))
    body = client_local.get("/").content.decode()
    for name in ("Attention", "In Progress", "Roadmap"):
        assert f">{name}<" in body
    assert 'href="/attention/"' in body and 'href="/in-progress/"' in body and 'href="/roadmap/"' in body
    # building slice is both "in progress" (1) and, being 9d stale, "attention" (1)
    assert body.count('class="nav-count"') >= 2   # at least attention + in-progress badges rendered
```

- [ ] **Step 4: Run tests + full suite**

Run: `uv run pytest tests/web/test_shell.py -q && uv run pytest -q`
Expected: all PASS; full suite 233 passed (232 + the now-green cross-task test, renamed).

- [ ] **Step 5: Commit**

```bash
git add tuckit/web/templates/web/partials/_sidebar.html tuckit/web/templatetags/web_extras.py tests/web/test_shell.py
git commit -m "feat(web): sidebar state-lens group (Attention / In Progress / Roadmap) with count badges"
```

---

## Task 5: Home Roadmap-distribution strip

**Files:**
- Modify: `tuckit/web/templates/web/home.html`, `tuckit/web/static/web/app.css`
- Test: `tests/web/test_home.py`

**Interfaces:**
- Consumes: `roadmap` context from `home` view (Task 2 wired it), url `web:roadmap`.
- Produces: a `.roadmap-strip` link on Home.

- [ ] **Step 1: Write failing test**

Add to `tests/web/test_home.py`:
```python
@pytest.mark.django_db
def test_home_shows_roadmap_strip(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    a = create_area(workspace, "Backend")
    create_slice(a, "빌딩", status="building")
    body = client_local.get("/").content.decode()
    assert 'class="roadmap-strip"' in body
    assert 'href="/roadmap/"' in body
    assert "Building 1" in body
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/web/test_home.py::test_home_shows_roadmap_strip -v`
Expected: FAIL (`roadmap-strip` not present).

- [ ] **Step 3: Add the strip to Home**

In `tuckit/web/templates/web/home.html`, immediately after `{% block main %}` (line 3), insert:
```html
  <a class="roadmap-strip" href="{% url 'web:roadmap' %}">
    <span class="rm-seg">Idea {{ roadmap.idea|length }}</span>
    <span class="rm-seg">Planned {{ roadmap.planned|length }}</span>
    <span class="rm-seg rm-building">Building {{ roadmap.building|length }}</span>
    <span class="rm-seg rm-shipped">Shipped {{ roadmap.shipped|length }}</span>
  </a>
```

- [ ] **Step 4: Add styles**

Append to `tuckit/web/static/web/app.css`:
```css
/* --- Roadmap distribution strip / board (nav redesign, Phase 2) --- */
.roadmap-strip {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
  text-decoration: none;
}
.roadmap-dist {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.rm-seg {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 10px;
  color: var(--muted);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.roadmap-strip:hover .rm-seg { border-color: var(--accent); }
.rm-building { color: var(--text); }
.rm-shipped { color: var(--muted); }
```

- [ ] **Step 5: Run tests + full suite + commit**

Run: `uv run pytest tests/web/test_home.py -q && uv run pytest -q`
Expected: all PASS; full suite 234 passed.
```bash
git add tuckit/web/templates/web/home.html tuckit/web/static/web/app.css tests/web/test_home.py
git commit -m "feat(web): Home roadmap-distribution strip linking to /roadmap/"
```

---

## Self-Review

**Spec coverage (Phase 2 = spec part C, minus Phase-3 activity log):**
- Sidebar state-lens group (Attention / In Progress / Roadmap + existing Triage) with count badges — Tasks 3+4. This is the spec's core "지금 상태가 사이드바에서 보인다" goal.
- Dedicated lens pages — Task 2 (`/attention/`, `/in-progress/`, `/roadmap/`).
- Roadmap status distribution + board — Task 2 (`roadmap.html`) + Task 5 (Home strip), fed by `roadmap_state` (Task 1).
- Home stays light (only the strip added) — matches the agreed scope decision, NOT spec §5's full 4-card rebuild.
- Recent-activity card / activity log — **intentionally deferred to Phase 3** (Global Constraints).

**Placeholder scan:** No TBD/TODO. One deliberate cross-task pattern: Task 3 commits a test that stays red until Task 4 (documented in Task 3 Step 6 and Task 4 Step 3, which replaces it green). This is the one place a task doesn't end fully green on its own new test — flagged explicitly so the controller/reviewer expects it. If you prefer strict per-task green, move the test creation entirely into Task 4 and have Task 3 commit only the context processors.

**Type/name consistency:** `roadmap_state`/`in_progress_state` return shapes (`idea|planned|building|shipped`; `slices`/`bites`) are consumed identically in views/templates. URL names `attention`/`in_progress`/`roadmap` match `resolver_match.url_name` checks in the sidebar. Icon keys `attention`/`in-progress`/`roadmap` match `{% icon %}` calls.

**Reuse check:** lens pages reuse `_slice_row.html` and `_status_group.html`; Attention reuses the exact Home attention markup + `attention_label`; no new slice-row variant introduced. Only genuinely new markup: the doing-bite rows (in_progress.html) and the roadmap distribution segments.

**Out of scope confirmed:** no model changes / migration; Home's existing sections untouched; Triage nav item + its OOB count partial unchanged.
