# Management Surfaces — Phase 3: Area Inline CRUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users rename, delete, and reorder Areas directly inline in the sidebar — no separate settings page — so managing project structure feels like "just pushing things in," not administration.

**Architecture:** Three pure service functions in `areas.py` enforce data invariants (`rename_area`, `delete_area`, `reorder_area`), mirroring the existing `reorder_slice`/`rename_org` patterns. Thin views in `capture.py` scope every action to the current workspace via `get_area` and return HTMX-friendly responses (OOB/`outerHTML` swaps, `204`). The sidebar `_area_nav.html` gains a per-row partial (`_area_row.html`) with hover rename/delete affordances (Alpine toggles an inline input) and a small `area_nav.js` that wires SortableJS drag-reorder, mirroring `board.js`.

**Tech Stack:** Django service layer, HTMX 2.x, Alpine.js, SortableJS (already vendored), Warm Greige tokens.

## Global Constraints

- **Public/private boundary:** `tuckit` is PUBLIC (BSL 1.1). Nothing about billing/Paddle/pricing/plans/cloud infra may appear in any file this plan touches.
- **Service layer enforces DATA INVARIANTS; views enforce AUTHORIZATION.** Services raise `InvalidValue` (from `tuckit.core.services.exceptions`); views translate that to HTTP and enforce tenant scoping.
- **Permission model = same as `create_area`:** any member with access to the current workspace may rename/delete/reorder its Areas. Area management is content, not org administration — there is deliberately NO `is_org_admin` gate. Tenant isolation is enforced by resolving the Area through `get_area(ws, area_id)`, which 404s across workspaces.
- **The Triage Area is protected:** `delete_area` MUST refuse an Area whose `is_triage=True` by raising `InvalidValue`. (The sidebar list already excludes Triage via the `sidebar_areas` context processor filtering `not a.is_triage`, but the service is the source of truth.) NOTE: a recent refactor renamed `Area.is_inbox`→`is_triage`, `get_or_create_inbox`→`get_or_create_triage`, `INBOX_NAME`→`TRIAGE_NAME="Triage"`, and the route `/inbox/`→`/triage/` (`name="triage"`). Use the current `is_triage`/triage names throughout.
- **Rename keeps the slug stable** (only the display `name` changes), mirroring `workspace_rename`/`rename_org`. This preserves existing `/areas/<slug>/` URLs.
- **Reorder uses fractional ranks** via `rank_for(Area, {"workspace": ...}, before=, after=)` — never renumber siblings. Mirror `reorder_slice` exactly.
- **Deletion cascades** (workspace design decision "경고 후 함께 삭제"): `Slice.area` and `Bite.slice` are `on_delete=CASCADE`, so `area.delete()` removes the Area's Slices and Bites. The UI warns before deleting.
- Run the suite with `uv run pytest` from `tuckit/`.

---

## File Structure

**Services (create functions in existing file):**
- Modify: `tuckit/core/services/areas.py` — add `rename_area`, `delete_area`, `reorder_area`.

**Views + URLs:**
- Modify: `tuckit/web/views/capture.py` — add `area_rename`, `area_delete`, `area_reorder` (Area management lives alongside `area_create`, which is already here).
- Modify: `tuckit/web/urls.py` — add three routes under `areas/<int:area_id>/…`.

**Templates:**
- Create: `tuckit/web/templates/web/partials/_area_row.html` — one Area row (link + hover actions + inline rename form).
- Modify: `tuckit/web/templates/web/partials/_area_nav.html` — loop over `_area_row.html`; load `area_nav.js`.

**Static:**
- Create: `tuckit/web/static/web/area_nav.js` — SortableJS drag-reorder for the sidebar, re-initialized after OOB swaps.
- Modify: `tuckit/web/static/web/app.css` — hover-action + inline-rename styles.

**Tests:**
- Modify: `tests/test_services_areas.py` — service invariants.
- Create: `tests/web/test_area_manage.py` — view behavior (rename/delete/reorder, tenant scoping, Triage protection).

---

## Task 1: Area management services (rename, delete, reorder)

**Files:**
- Modify: `tuckit/core/services/areas.py` (append three functions)
- Test: `tests/test_services_areas.py`

**Interfaces:**
- Consumes: `Area` model (`tuckit.core.models`), `rank_for` (`tuckit.core.services.ranking_helpers`), `InvalidValue` (`tuckit.core.services.exceptions`).
- Produces:
  - `rename_area(area: Area, name: str) -> Area` — strips `name`; raises `InvalidValue("이름을 입력해주세요")` if empty; saves `name` (slug unchanged); returns the Area.
  - `delete_area(area: Area) -> None` — raises `InvalidValue("Triage는 삭제할 수 없습니다")` if `area.is_triage`; otherwise `area.delete()` (cascades to slices/bites).
  - `reorder_area(area: Area, *, before: Area | None = None, after: Area | None = None) -> Area` — sets `area.rank = rank_for(Area, {"workspace": area.workspace}, before=before, after=after)`, saves `rank` + `updated_at`, returns the Area.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_services_areas.py` (the file already imports `pytest`, `Area/Org/Workspace`, and has a `workspace` fixture):

```python
from tuckit.core.services.areas import rename_area, delete_area, reorder_area
from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.slices import create_slice


@pytest.mark.django_db
def test_rename_area_changes_name_but_keeps_slug(workspace):
    a = create_area(workspace, "Back End")
    original_slug = a.slug
    renamed = rename_area(a, "Platform")
    a.refresh_from_db()
    assert a.name == "Platform"
    assert a.slug == original_slug
    assert renamed.id == a.id


@pytest.mark.django_db
def test_rename_area_trims_whitespace(workspace):
    a = create_area(workspace, "X")
    rename_area(a, "  Trimmed  ")
    a.refresh_from_db()
    assert a.name == "Trimmed"


@pytest.mark.django_db
def test_rename_area_rejects_blank(workspace):
    a = create_area(workspace, "Keep")
    with pytest.raises(InvalidValue):
        rename_area(a, "   ")
    a.refresh_from_db()
    assert a.name == "Keep"


@pytest.mark.django_db
def test_delete_area_removes_it_and_cascades_slices(workspace):
    a = create_area(workspace, "Doomed")
    create_slice(a, "child idea", status="idea", source="human")
    delete_area(a)
    assert not Area.objects.filter(workspace=workspace, name="Doomed").exists()
    from tuckit.core.models import Slice
    assert not Slice.objects.filter(area_id=a.id).exists()


@pytest.mark.django_db
def test_delete_area_refuses_triage(workspace):
    triage = get_or_create_triage(workspace)
    with pytest.raises(InvalidValue):
        delete_area(triage)
    assert Area.objects.filter(id=triage.id).exists()


@pytest.mark.django_db
def test_reorder_area_moves_before_sibling(workspace):
    a = create_area(workspace, "A")
    b = create_area(workspace, "B")
    c = create_area(workspace, "C")
    # move c before a  ->  C, A, B
    reorder_area(c, before=a)
    ordered = list(list_areas(workspace))
    assert [x.id for x in ordered] == [c.id, a.id, b.id]


@pytest.mark.django_db
def test_reorder_area_moves_after_sibling(workspace):
    a = create_area(workspace, "A")
    b = create_area(workspace, "B")
    c = create_area(workspace, "C")
    # move a after b  ->  B, A, C
    reorder_area(a, after=b)
    ordered = list(list_areas(workspace))
    assert [x.id for x in ordered] == [b.id, a.id, c.id]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services_areas.py -v`
Expected: FAIL with `ImportError` / `cannot import name 'rename_area'`.

- [ ] **Step 3: Write minimal implementation**

Append to `tuckit/core/services/areas.py` (imports already present: `Area`, `rank_for`; add the exceptions import at the top of the file):

```python
from tuckit.core.services.exceptions import InvalidValue
```

```python
def rename_area(area: Area, name: str) -> Area:
    name = (name or "").strip()
    if not name:
        raise InvalidValue("이름을 입력해주세요")
    area.name = name
    area.save(update_fields=["name", "updated_at"])
    return area


def delete_area(area: Area) -> None:
    if area.is_triage:
        raise InvalidValue("Triage는 삭제할 수 없습니다")
    area.delete()  # cascades to slices/bites via FK on_delete=CASCADE


def reorder_area(area: Area, *, before: Area | None = None, after: Area | None = None) -> Area:
    area.rank = rank_for(Area, {"workspace": area.workspace}, before=before, after=after)
    area.save(update_fields=["rank", "updated_at"])
    return area
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services_areas.py -v`
Expected: PASS (all new tests green; existing area-service tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add tuckit/core/services/areas.py tests/test_services_areas.py
git commit -m "feat(areas): rename/delete/reorder area services with triage guard"
```

---

## Task 2: Area management views + URLs

**Files:**
- Modify: `tuckit/web/views/capture.py`
- Modify: `tuckit/web/urls.py`
- Test: `tests/web/test_area_manage.py` (create)

**Interfaces:**
- Consumes: `rename_area`, `delete_area`, `reorder_area` (Task 1); `get_area` (`tuckit.core.services.resolve`); `get_current_workspace`; `NotFound`, `InvalidValue`.
- Produces three views + routes:
  - `area_rename(request, area_id)` → renders `_area_row.html` for the renamed Area (so the row swaps `outerHTML`).
  - `area_delete(request, area_id)` → `204` on success (HTMX empties the row).
  - `area_reorder(request, area_id)` → `204`; reads optional `before_id`/`after_id` POST params, resolves them via `get_area`.

**Notes for the implementer:**
- Mirror `capture.area_create` (same file) for wiring and the `get_current_workspace` pattern.
- Mirror `board.slice_move` for the reorder neighbor-resolution shape (foreign neighbor → 404).
- `area_rename` must return the same row markup the sidebar uses, so the template context needs `a` (the area) and the `active` flag. Compute `active` the same way `_area_nav.html` does (compare `request.resolver_match`). Simplest: pass `a` and let the template recompute active from `request` — see Task 3's `_area_row.html`, which reads `request.resolver_match` directly, so the view only needs `{"a": area}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_area_manage.py`:

```python
import pytest

from tuckit.core.models import Area, Org, Workspace
from tuckit.core.services.areas import create_area, get_or_create_triage, list_areas
from tuckit.core.services.slices import create_slice


@pytest.mark.django_db
def test_rename_area_updates_and_returns_row(client_local, workspace):
    a = create_area(workspace, "Old")
    resp = client_local.post(f"/areas/{a.id}/rename", {"name": "New"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    a.refresh_from_db()
    assert a.name == "New"
    assert "New" in resp.content.decode()


@pytest.mark.django_db
def test_rename_area_blank_returns_400(client_local, workspace):
    a = create_area(workspace, "Keep")
    resp = client_local.post(f"/areas/{a.id}/rename", {"name": "  "}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 400
    a.refresh_from_db()
    assert a.name == "Keep"


@pytest.mark.django_db
def test_delete_area_returns_204_and_removes(client_local, workspace):
    a = create_area(workspace, "Gone")
    resp = client_local.post(f"/areas/{a.id}/delete", HTTP_HX_REQUEST="true")
    assert resp.status_code == 204
    assert not Area.objects.filter(id=a.id).exists()


@pytest.mark.django_db
def test_delete_triage_returns_400(client_local, workspace):
    triage = get_or_create_triage(workspace)
    resp = client_local.post(f"/areas/{triage.id}/delete", HTTP_HX_REQUEST="true")
    assert resp.status_code == 400
    assert Area.objects.filter(id=triage.id).exists()


@pytest.mark.django_db
def test_manage_foreign_area_404s(client_local, workspace):
    other_org = Org.objects.create(name="Other", slug="other")
    other_ws = Workspace.objects.create(org=other_org, name="Other WS", slug="other-ws")
    foreign = create_area(other_ws, "Foreign")
    resp = client_local.post(f"/areas/{foreign.id}/rename", {"name": "Hax"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 404
    foreign.refresh_from_db()
    assert foreign.name == "Foreign"


@pytest.mark.django_db
def test_reorder_area_before_neighbor(client_local, workspace):
    a = create_area(workspace, "A")
    b = create_area(workspace, "B")
    c = create_area(workspace, "C")
    # move c before a
    resp = client_local.post(
        f"/areas/{c.id}/reorder", {"before_id": a.id}, HTTP_HX_REQUEST="true"
    )
    assert resp.status_code == 204
    ordered = list(list_areas(workspace))
    assert [x.id for x in ordered] == [c.id, a.id, b.id]


@pytest.mark.django_db
def test_reorder_foreign_neighbor_404s(client_local, workspace):
    a = create_area(workspace, "A")
    other_org = Org.objects.create(name="Other", slug="other")
    other_ws = Workspace.objects.create(org=other_org, name="Other WS", slug="other-ws")
    foreign = create_area(other_ws, "Foreign")
    resp = client_local.post(
        f"/areas/{a.id}/reorder", {"before_id": foreign.id}, HTTP_HX_REQUEST="true"
    )
    assert resp.status_code == 404
```

> `client_local` and `workspace` fixtures come from `tests/web/conftest.py` (already used across the web tests).

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_area_manage.py -v`
Expected: FAIL with `404` for every route (URLs not defined yet).

- [ ] **Step 3: Add the views**

Append to `tuckit/web/views/capture.py`. Update the imports at the top of the file to add what's missing:

```python
from tuckit.core.services.areas import get_or_create_triage, create_area, list_areas, rename_area, delete_area, reorder_area
from tuckit.core.services.resolve import get_area, get_slice
```

Add the views:

```python
def area_rename(request, area_id):
    ws = get_current_workspace(request)
    try:
        area = get_area(ws, area_id)
    except NotFound:
        raise Http404
    try:
        rename_area(area, request.POST.get("name", ""))
    except InvalidValue as e:
        return HttpResponse(str(e), status=400)
    return render(request, "web/partials/_area_row.html", {"a": area})


def area_delete(request, area_id):
    ws = get_current_workspace(request)
    try:
        area = get_area(ws, area_id)
    except NotFound:
        raise Http404
    try:
        delete_area(area)
    except InvalidValue as e:
        return HttpResponse(str(e), status=400)
    return HttpResponse(status=204)  # htmx empties the row via hx-swap="outerHTML"


def area_reorder(request, area_id):
    ws = get_current_workspace(request)
    try:
        area = get_area(ws, area_id)
        before = get_area(ws, int(request.POST["before_id"])) if request.POST.get("before_id") else None
        after = get_area(ws, int(request.POST["after_id"])) if request.POST.get("after_id") else None
    except NotFound:
        raise Http404
    reorder_area(area, before=before, after=after)
    return HttpResponse(status=204)
```

- [ ] **Step 4: Add the URLs**

In `tuckit/web/urls.py`, alongside the existing `areas/…` routes, add:

```python
    path("areas/<int:area_id>/rename", capture.area_rename, name="area_rename"),
    path("areas/<int:area_id>/delete", capture.area_delete, name="area_delete"),
    path("areas/<int:area_id>/reorder", capture.area_reorder, name="area_reorder"),
```

> Place these **after** `path("areas/<slug:slug>/", slices.area_view, name="area")`. `<int:area_id>` and `<slug:slug>` do not collide (an int is not matched by the slug pattern for these paths because the trailing segment differs: `rename`/`delete`/`reorder` vs a bare slug), but keeping the management routes grouped with `areas/new` is clearest.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_area_manage.py -v`
Expected: FAIL at the render step for `area_rename` (`_area_row.html` does not exist yet) but PASS for delete/reorder/404 cases. If `area_rename` tests fail only because the template is missing, that is expected — Task 3 creates it. To keep this task independently green, create a **minimal** placeholder now and let Task 3 flesh it out:

Create `tuckit/web/templates/web/partials/_area_row.html` with a minimal body:

```html
{% load web_extras %}
<div class="area-item" data-area-id="{{ a.id }}">{{ a.name }}</div>
```

Re-run: `uv run pytest tests/web/test_area_manage.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/views/capture.py tuckit/web/urls.py tests/web/test_area_manage.py tuckit/web/templates/web/partials/_area_row.html
git commit -m "feat(web): area rename/delete/reorder endpoints (workspace-scoped)"
```

---

## Task 3: Sidebar inline UI — row partial, hover actions, inline rename

**Files:**
- Modify: `tuckit/web/templates/web/partials/_area_row.html` (flesh out the placeholder from Task 2)
- Modify: `tuckit/web/templates/web/partials/_area_nav.html`
- Modify: `tuckit/web/static/web/app.css`
- Test: `tests/web/test_area_manage.py` (add render assertions)

**Interfaces:**
- Consumes: `web:area`, `web:area_rename`, `web:area_delete` URL names; the `{% icon "area" %}` tag from `web_extras`.
- Produces: a self-contained Area row usable both inside the sidebar loop and as the `area_rename` response.

- [ ] **Step 1: Write the failing render tests**

Append to `tests/web/test_area_manage.py`:

```python
@pytest.mark.django_db
def test_sidebar_row_has_rename_and_delete_affordances(client_local, workspace):
    a = create_area(workspace, "Visible")
    # any authenticated page renders the sidebar
    body = client_local.get("/triage/").content.decode()
    assert f'data-area-id="{a.id}"' in body          # draggable row present
    assert f'/areas/{a.id}/rename' in body           # inline rename form target
    assert f'/areas/{a.id}/delete' in body           # delete button target
    assert "Visible" in body


@pytest.mark.django_db
def test_rename_response_is_swappable_row(client_local, workspace):
    a = create_area(workspace, "Old")
    body = client_local.post(
        f"/areas/{a.id}/rename", {"name": "Fresh"}, HTTP_HX_REQUEST="true"
    ).content.decode()
    assert f'data-area-id="{a.id}"' in body          # returns a full row, not bare text
    assert "Fresh" in body
    assert f'/areas/{a.id}/delete' in body           # actions still wired after rename
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_area_manage.py -k "affordances or swappable" -v`
Expected: FAIL — the placeholder row has no rename/delete targets.

- [ ] **Step 3: Flesh out `_area_row.html`**

Replace `tuckit/web/templates/web/partials/_area_row.html` with:

```html
{% load web_extras %}
<div class="area-item" data-area-id="{{ a.id }}" x-data="{editing: false}">
  <a class="nav area-link{% if request.resolver_match.url_name == 'area' and request.resolver_match.kwargs.slug == a.slug %} nav--active{% endif %}"
     href="{% url 'web:area' a.slug %}"
     x-show="!editing"
     x-on:dblclick.prevent="editing = true; $nextTick(() => $refs.renameInput.focus())">
    {% icon "area" %}<span class="nav-label">{{ a.name }}</span>
  </a>
  <div class="area-actions" x-show="!editing">
    <button type="button" class="area-act" title="이름 변경"
            x-on:click="editing = true; $nextTick(() => $refs.renameInput.focus())">✎</button>
    <button type="button" class="area-act area-act--danger" title="삭제"
            hx-post="{% url 'web:area_delete' a.id %}"
            hx-target="closest .area-item" hx-swap="outerHTML"
            hx-confirm="이 Area와 그 안의 모든 항목이 함께 삭제됩니다. 계속할까요?">✕</button>
  </div>
  <form class="area-rename" x-show="editing" x-cloak
        hx-post="{% url 'web:area_rename' a.id %}"
        hx-target="closest .area-item" hx-swap="outerHTML"
        hx-on::after-request="if(event.detail.successful) editing = false">
    <input name="name" value="{{ a.name }}" x-ref="renameInput" class="area-rename-input"
           maxlength="200" autocomplete="off"
           x-on:keydown.escape="editing = false">
  </form>
</div>
```

Notes:
- Double-click the label OR click ✎ to edit; Escape or a successful submit closes the editor (the swap returns a fresh row defaulting to `editing:false`, so state resets automatically).
- Delete uses htmx `hx-confirm` (native confirm) — no modal infra, satisfies "경고 후 함께 삭제." On `204` htmx swaps empty content into the row (`outerHTML`), removing it.
- The row is `data-area-id`-tagged for SortableJS (Task 4). The `filter` on the sortable excludes `.area-act` buttons so clicks on them don't start a drag.

- [ ] **Step 4: Update `_area_nav.html` to use the row partial**

Replace `tuckit/web/templates/web/partials/_area_nav.html` with:

```html
{% load web_extras %}
<div id="area-nav"{% if oob %} hx-swap-oob="true"{% endif %}>
  {% for a in areas %}
    {% include "web/partials/_area_row.html" %}
  {% endfor %}
</div>
<script src="{% static 'web/area_nav.js' %}"></script>
```

Add `{% load static %}` handling: `web_extras` does not provide `static`. Change the first line to load both:

```html
{% load web_extras static %}
```

> The `<script>` sits outside `#area-nav` so an OOB swap that replaces `#area-nav` doesn't re-inject the tag on every create. `area_nav.js` (Task 4) re-initializes SortableJS after such swaps via an htmx event listener.

- [ ] **Step 5: Add CSS**

Append to `tuckit/web/static/web/app.css` (match existing token usage — `--muted`, `--surface`, `--border`, `--accent`):

```css
/* Sidebar Area rows: hover reveals rename/delete; inline rename input. */
.area-item {
  position: relative;
  display: flex;
  align-items: center;
}
.area-item .area-link { flex: 1 1 auto; min-width: 0; }
.area-item .nav-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.area-actions {
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.12s ease;
}
.area-item:hover .area-actions { opacity: 1; }
.area-act {
  border: none;
  background: none;
  color: var(--muted);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 5px;
  font-size: 13px;
  line-height: 1;
}
.area-act:hover { background: var(--surface); color: var(--text); }
.area-act--danger:hover { color: #b4453a; }
.area-rename { flex: 1 1 auto; padding: 2px 0; }
.area-rename-input {
  width: 100%;
  font: inherit;
  padding: 5px 8px;
  border: 1px solid var(--accent);
  border-radius: 6px;
  background: var(--bg);
  color: var(--text);
}
.sortable-ghost { opacity: 0.4; }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_area_manage.py -v`
Expected: PASS (all, including the two render tests).

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/partials/_area_row.html tuckit/web/templates/web/partials/_area_nav.html tuckit/web/static/web/app.css tests/web/test_area_manage.py
git commit -m "feat(web): inline area rename/delete affordances in sidebar"
```

---

## Task 4: Drag-reorder JS (`area_nav.js`)

**Files:**
- Create: `tuckit/web/static/web/area_nav.js`
- Test: manual note in this task (JS drag is not unit-tested here; the reorder endpoint is covered by Task 2). Add one guard test that the script is referenced.

**Interfaces:**
- Consumes: global `Sortable` (vendored in `base.html`), `POST /areas/<id>/reorder` with `before_id`/`after_id` (Task 2).
- Produces: sidebar drag-to-reorder that survives OOB swaps of `#area-nav`.

- [ ] **Step 1: Write the failing guard test**

Append to `tests/web/test_area_manage.py`:

```python
@pytest.mark.django_db
def test_sidebar_loads_reorder_script(client_local, workspace):
    create_area(workspace, "Any")
    body = client_local.get("/triage/").content.decode()
    assert "area_nav.js" in body
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `uv run pytest tests/web/test_area_manage.py -k reorder_script -v`
Expected: PASS already if Task 3 Step 4 added the `<script>` tag; if so, this test simply locks that in. If it fails, the tag is missing — add it. (Either outcome is fine; the test guards regressions.)

- [ ] **Step 3: Write `area_nav.js`**

Create `tuckit/web/static/web/area_nav.js`, mirroring `board.js`:

```javascript
// Sidebar Area drag-reorder: initializes SortableJS on #area-nav and POSTs the
// new position to web:area_reorder on drop. Re-initializes after htmx swaps the
// list (e.g. OOB swap on area create), since the old Sortable instance is bound
// to a replaced DOM node. Depends on the vendored SortableJS (see base.html).
(function () {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : null;
  }

  let instance = null;

  function initAreaNav() {
    const nav = document.getElementById("area-nav");
    if (!nav) return;
    if (instance) { instance.destroy(); instance = null; }
    instance = Sortable.create(nav, {
      animation: 150,
      draggable: ".area-item",
      filter: ".area-act, .area-rename-input",  // don't start a drag from action buttons/input
      onEnd: function (evt) {
        const item = evt.item;
        const areaId = item.getAttribute("data-area-id");
        if (!areaId) return;
        const before = item.nextElementSibling;
        const after = item.previousElementSibling;

        const body = new URLSearchParams();
        if (before && before.getAttribute("data-area-id")) {
          body.set("before_id", before.getAttribute("data-area-id"));
        }
        if (after && after.getAttribute("data-area-id")) {
          body.set("after_id", after.getAttribute("data-area-id"));
        }

        fetch("/areas/" + areaId + "/reorder", {
          method: "POST",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "Content-Type": "application/x-www-form-urlencoded",
          },
          body: body.toString(),
        });
      },
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAreaNav);
  } else {
    initAreaNav();
  }

  // The sidebar Areas list is OOB-swapped on area create; re-bind Sortable to
  // the fresh #area-nav node whenever an htmx swap touches it.
  document.body.addEventListener("htmx:afterSwap", function () {
    if (document.getElementById("area-nav")) initAreaNav();
  });
})();
```

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest`
Expected: PASS (whole suite; nothing regressed).

- [ ] **Step 5: Manual smoke check (report in the implementer's notes)**

Describe (do not automate): with `uv run python manage.py runserver`, create 3 Areas, then in the sidebar — (a) double-click a name → rename inline → Enter persists; (b) hover → ✕ → confirm → row disappears; (c) drag a row above another → order persists on reload; (d) create a new Area → drag still works on the refreshed list.

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/static/web/area_nav.js tests/web/test_area_manage.py
git commit -m "feat(web): drag-reorder areas in the sidebar (sortablejs)"
```

---

## Self-Review Notes (author)

- **Spec coverage:** rename (Task 1 service, Task 2 view, Task 3 UI), delete-with-cascade-and-confirm (Task 1 guard + cascade, Task 2 `204`, Task 3 `hx-confirm`), reorder (Task 1 `reorder_area`, Task 2 endpoint, Task 4 drag). Triage protection: service-level (Task 1, `is_triage`) + list already excludes it. Tenant scoping: `get_area` 404s (Task 2 tests).
- **Permission decision flagged:** no `is_org_admin` gate — mirrors `area_create`. Confirm with the human before execution if org-admin gating is wanted instead.
- **Type consistency:** `reorder_area(area, *, before, after)` signature matches `reorder_slice`; `rank_for(Area, {"workspace": ...}, ...)` matches `create_area`. `area_rename` view returns `_area_row.html` with context `{"a": area}` — the template reads `request` from the request context (RequestContext), so `active` resolves without extra keys.
- **No placeholders:** every step has concrete code/commands.
- **Reuse note:** if any future Area action needs a redirect, reuse `tuckit/web/htmx.py:redirect_response` (added in the HX-Redirect fix).
