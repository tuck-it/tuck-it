# Bounding "Shipped" on the Board — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound the ever-growing Shipped column/group on the Board tab to a workspace-configurable recent window, with a "View all shipped" link that reuses the Board tab filtered by slice status — no new URL or nav item.

**Architecture:** Two `Workspace` fields (`shipped_board_mode`, `shipped_board_limit`) drive a pure `cap_shipped()` helper in the state service. The `web:roadmap` view caps the Shipped bucket for the default board/list views and grows a generic `?status=<value>` branch that renders any single status as an uncapped flat list. Home reuses the same cap + link.

**Tech Stack:** Django 5, htmx + Alpine.js, pytest / pytest-django, uv. Static CSS tokens (`tokens.brand.css` → `tokens.product.css` → `base.css` → `app.css`).

## Global Constraints

- Public repo `tuckit` — no billing/infra/pricing code. This feature is neutral product UI, so it belongs here.
- CSS: `var(--token)` only — no literal hex, no hardcoded radius (14px surfaces / 9px controls via `--radius`/`--radius-small`). Accent teal is `--blue`.
- Run everything with `uv run` from `/Users/goddessana/Developments/tuckit-projects/tuckit`.
- Do NOT `git add` anything under `docs/superpowers/` — specs/plans stay untracked in the public repo.
- Slice statuses: `idea`, `planned`, `building`, `shipped`, `dropped`. `roadmap_state` already excludes `dropped` and `is_triage` areas.
- Out of scope: per-Area board cap, `dropped` archive, pagination/date-grouping of the filtered list.

---

### Task 1: Workspace settings fields + migration

**Files:**
- Modify: `tuckit/core/models/workspace.py:10-28`
- Test: `tests/test_models_workspace.py` (create)

**Interfaces:**
- Produces: `Workspace.shipped_board_mode` (`CharField`, `"count"|"days"`, default `"count"`), `Workspace.shipped_board_limit` (`PositiveSmallIntegerField`, default `8`), and module const `SHIPPED_BOARD_MODE_CHOICES`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_models_workspace.py`:
```python
import pytest
from tuckit.core.management.commands.bootstrap import ensure_bootstrap


@pytest.mark.django_db
def test_workspace_shipped_board_defaults():
    ws, _ = ensure_bootstrap()
    assert ws.shipped_board_mode == "count"
    assert ws.shipped_board_limit == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models_workspace.py -q`
Expected: FAIL — `AttributeError: 'Workspace' object has no attribute 'shipped_board_mode'`.

- [ ] **Step 3: Add the fields**

In `tuckit/core/models/workspace.py`, add the choices const above the class and the two fields after `onboarding_dismissed` (line 15):
```python
SHIPPED_BOARD_MODE_CHOICES = [("count", "Count"), ("days", "Days")]


class Workspace(models.Model):
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="workspaces")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, validators=[_SLUG_VALIDATOR])
    description = models.TextField(blank=True, default="")
    onboarding_dismissed = models.BooleanField(default=False)
    shipped_board_mode = models.CharField(
        max_length=5, choices=SHIPPED_BOARD_MODE_CHOICES, default="count"
    )
    shipped_board_limit = models.PositiveSmallIntegerField(default=8)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

- [ ] **Step 4: Generate the migration**

Run: `uv run python manage.py makemigrations core`
Expected: creates `tuckit/core/migrations/0010_workspace_shipped_board_mode_and_more.py` (or similar) adding both fields with defaults.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_models_workspace.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/core/models/workspace.py tuckit/core/migrations/0010_*.py tests/test_models_workspace.py
git commit -m "feat(board): add workspace shipped-board cap settings"
```

---

### Task 2: `cap_shipped` helper + shipped recency sort

**Files:**
- Modify: `tuckit/core/services/state.py:128-149` (roadmap_state shipped sort), add helpers near `ROADMAP_BOARD_ORDER` (line 152)
- Test: `tests/test_services_state.py` (append)

**Interfaces:**
- Consumes: `Workspace.shipped_board_mode`, `Workspace.shipped_board_limit`.
- Produces:
  - `ROADMAP_STATUS_KEYS = {"idea", "planned", "building", "shipped"}`
  - `cap_shipped(workspace, shipped: list) -> tuple[list, int]` — returns `(visible, total)`, pure (no queries).
  - `roadmap_board_view(workspace) -> dict` with keys `state` (capped dict), `groups` (list of `(status, slices)`), `shipped_total` (int), `shipped_hidden` (int).
  - `roadmap_state` shipped bucket sorted by `completed_at` desc (fallback `updated_at`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_services_state.py`:
```python
import pytest
from datetime import timedelta
from django.utils import timezone
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice
from tuckit.core.services.state import cap_shipped, roadmap_board_view, roadmap_state


@pytest.mark.django_db
def test_cap_shipped_count_mode(workspace):
    workspace.shipped_board_mode = "count"
    workspace.shipped_board_limit = 2
    a = create_area(workspace, "A")
    for i in range(5):
        create_slice(a, f"s{i}", status="shipped")
    shipped = roadmap_state(workspace)["shipped"]
    visible, total = cap_shipped(workspace, shipped)
    assert total == 5
    assert len(visible) == 2


@pytest.mark.django_db
def test_cap_shipped_days_mode_excludes_old(workspace):
    workspace.shipped_board_mode = "days"
    workspace.shipped_board_limit = 30
    a = create_area(workspace, "A")
    recent = create_slice(a, "recent", status="shipped")
    old = create_slice(a, "old", status="shipped")
    old.completed_at = timezone.now() - timedelta(days=90)
    old.save(update_fields=["completed_at"])
    shipped = roadmap_state(workspace)["shipped"]
    visible, total = cap_shipped(workspace, shipped)
    assert total == 2
    titles = {s.title for s in visible}
    assert "recent" in titles and "old" not in titles


@pytest.mark.django_db
def test_shipped_sorted_newest_first(workspace):
    a = create_area(workspace, "A")
    first = create_slice(a, "first", status="shipped")
    second = create_slice(a, "second", status="shipped")
    first.completed_at = timezone.now() - timedelta(days=5)
    first.save(update_fields=["completed_at"])
    shipped = roadmap_state(workspace)["shipped"]
    assert [s.title for s in shipped][:2] == ["second", "first"]


@pytest.mark.django_db
def test_roadmap_board_view_reports_overflow(workspace):
    workspace.shipped_board_mode = "count"
    workspace.shipped_board_limit = 1
    a = create_area(workspace, "A")
    create_slice(a, "s1", status="shipped")
    create_slice(a, "s2", status="shipped")
    view = roadmap_board_view(workspace)
    assert view["shipped_total"] == 2
    assert view["shipped_hidden"] == 1
    shipped_group = dict(view["groups"])["shipped"]
    assert len(shipped_group) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services_state.py -k "cap_shipped or shipped_sorted or roadmap_board_view" -q`
Expected: FAIL — `ImportError: cannot import name 'cap_shipped'`.

- [ ] **Step 3: Implement helpers and the sort change**

In `tuckit/core/services/state.py`, add imports at the top (the file already imports `timezone`; add `timedelta` if missing — it is already imported at line 1):
`from datetime import timedelta` is already present. Good.

Change the `roadmap_state` return (lines 138-149) so shipped sorts by recency:
```python
    def bucket(status: str) -> list:
        return sorted(
            [s for s in slices if s.status == status],
            key=lambda s: (s.area.name, s.rank),
        )

    shipped = sorted(
        [s for s in slices if s.status == "shipped"],
        key=lambda s: (s.completed_at or s.updated_at),
        reverse=True,
    )
    return {
        "idea": bucket("idea"),
        "planned": bucket("planned"),
        "building": bucket("building"),
        "shipped": shipped,
    }
```

Replace the `ROADMAP_BOARD_ORDER` block (lines 152-160) with:
```python
ROADMAP_BOARD_ORDER = ["idea", "planned", "building", "shipped"]
ROADMAP_STATUS_KEYS = {"idea", "planned", "building", "shipped"}


def cap_shipped(workspace: Workspace, shipped: list) -> tuple[list, int]:
    """Trim a recency-sorted shipped list to the workspace's board window.
    Returns (visible, total). Pure — operates on an already-fetched list."""
    total = len(shipped)
    if workspace.shipped_board_mode == "days":
        cutoff = timezone.now() - timedelta(days=workspace.shipped_board_limit)
        visible = [s for s in shipped if s.completed_at and s.completed_at >= cutoff]
    else:  # count
        visible = list(shipped[: workspace.shipped_board_limit])
    return visible, total


def roadmap_board_view(workspace: Workspace) -> dict:
    """Capped kanban groups + shipped overflow meta for the workspace Board tab."""
    state = roadmap_state(workspace)
    visible, total = cap_shipped(workspace, state["shipped"])
    capped = {**state, "shipped": visible}
    return {
        "state": capped,
        "groups": [(status, capped[status]) for status in ROADMAP_BOARD_ORDER],
        "shipped_total": total,
        "shipped_hidden": total - len(visible),
    }
```

Delete the old `roadmap_board_groups` function (it is replaced by `roadmap_board_view`). Callers are updated in Tasks 3 and 4.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services_state.py -k "cap_shipped or shipped_sorted or roadmap_board_view" -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add tuckit/core/services/state.py tests/test_services_state.py
git commit -m "feat(board): cap_shipped helper + recency-sorted shipped"
```

---

### Task 3: Roadmap view — cap the board + generic `?status=` filter

**Files:**
- Modify: `tuckit/web/views/pages.py:4-10` (imports), `:44-56` (roadmap view)
- Modify: `tuckit/web/templates/web/roadmap.html` (rewrite)
- Modify: `tuckit/web/templates/web/partials/_board.html` (shipped footer)
- Modify: `tuckit/web/templates/web/partials/_status_group.html` (optional footer)
- Modify: `tuckit/web/static/web/app.css` (`.board-col-more` / `.group-more`)
- Test: `tests/web/test_board.py` (append)

**Interfaces:**
- Consumes: `roadmap_state`, `roadmap_board_view`, `ROADMAP_STATUS_KEYS` from Task 2.
- Produces: `web:roadmap` accepts `?view=board|list` and `?status=<idea|planned|building|shipped>`. Template context keys: `state`, `groups`, `view`, `has_any_slice`, `show_area`, `board_scope`, `shipped_total`, `shipped_hidden`, and for the filter branch `filter_status`, `filter_slices`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_board.py`:
```python
@pytest.mark.django_db
def test_board_caps_shipped_and_links_to_all(client_local, workspace):
    workspace.shipped_board_mode = "count"
    workspace.shipped_board_limit = 1
    workspace.save(update_fields=["shipped_board_mode", "shipped_board_limit"])
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    create_slice(a, "shipped one", status="shipped")
    create_slice(a, "shipped two", status="shipped")
    body = client_local.get(f"{p}/roadmap/").content.decode()
    assert "View all shipped (2)" in body
    assert 'href="?view=list&status=shipped"' in body


@pytest.mark.django_db
def test_status_filter_shows_all_shipped_flat(client_local, workspace):
    workspace.shipped_board_limit = 1
    workspace.save(update_fields=["shipped_board_limit"])
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    create_slice(a, "shipped one", status="shipped")
    create_slice(a, "shipped two", status="shipped")
    body = client_local.get(f"{p}/roadmap/?view=list&status=shipped").content.decode()
    assert "shipped one" in body and "shipped two" in body   # uncapped
    assert 'id="board"' not in body                          # not the kanban
    assert 'class="card-area"' in body or 'class="row-area"' in body


@pytest.mark.django_db
def test_status_filter_is_generic(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Core")
    create_slice(a, "building thing", status="building")
    body = client_local.get(f"{p}/roadmap/?status=building").content.decode()
    assert "building thing" in body
    assert 'id="board"' not in body


@pytest.mark.django_db
def test_board_no_footer_when_within_limit(client_local, workspace):
    workspace.shipped_board_limit = 8
    workspace.save(update_fields=["shipped_board_limit"])
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    create_slice(a, "only one", status="shipped")
    body = client_local.get(f"{p}/roadmap/").content.decode()
    assert "View all shipped" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_board.py -k "caps_shipped or status_filter or no_footer" -q`
Expected: FAIL (footer/filter absent).

- [ ] **Step 3: Update the roadmap view**

In `tuckit/web/views/pages.py`, update the import block (lines 4-10):
```python
from tuckit.core.services.state import (
    home_state,
    attention_items,
    roadmap_state,
    roadmap_board_view,
    ROADMAP_STATUS_KEYS,
    in_progress_state,
    recent_activity,
)
```

Replace the `roadmap` view (lines 44-48, currently the edited version):
```python
def roadmap(request):
    ws = get_current_workspace(request)
    status = request.GET.get("status")
    if ws and status in ROADMAP_STATUS_KEYS:
        # Focused single-status flat list — the "view all" / archive surface.
        state = roadmap_state(ws)
        return render(request, "web/roadmap.html", {
            "filter_status": status,
            "filter_slices": state.get(status, []),
            "show_area": True,
        })

    view = "list" if request.GET.get("view") == "list" else "board"
    board = roadmap_board_view(ws) if ws else {
        "state": {}, "groups": [], "shipped_total": 0, "shipped_hidden": 0,
    }
    return render(request, "web/roadmap.html", {
        "state": board["state"],
        "groups": board["groups"],
        "view": view,
        "has_any_slice": any(board["state"].values()),
        "show_area": True,
        "board_scope": "workspace",
        "shipped_total": board["shipped_total"],
        "shipped_hidden": board["shipped_hidden"],
    })
```

- [ ] **Step 4: Rewrite `roadmap.html` with the three render modes**

Replace `tuckit/web/templates/web/roadmap.html` entirely:
```html
{% extends "web/base.html" %}
{% load web_extras %}
{% block main %}
  {% if filter_status %}
    <header class="page-head">
      <div class="page-head-l"><h1 class="page-title">{{ filter_status|capfirst }}</h1></div>
      <div class="view-toggle">
        <a class="view-toggle-link" href="{% wurl 'web:roadmap' %}">← Board</a>
      </div>
    </header>
    {% if filter_slices %}
      <div class="panel">{% for slice in filter_slices %}{% include "web/partials/_slice_row.html" %}{% endfor %}</div>
    {% else %}
      <div class="empty muted">Nothing here yet.</div>
    {% endif %}
  {% else %}
    <header class="page-head">
      <div class="page-head-l"><h1 class="page-title">Board</h1></div>
      <div class="view-toggle">
        <a class="view-toggle-link{% if view == 'board' %} view-toggle-link--active{% endif %}"
           href="?view=board">Board</a>
        <a class="view-toggle-link{% if view == 'list' %} view-toggle-link--active{% endif %}"
           href="?view=list">List</a>
      </div>
    </header>
    {% if view == "list" %}
      <div class="roadmap-dist">
        <span class="rm-seg">Idea {{ state.idea|length }}</span>
        <span class="rm-seg">Planned {{ state.planned|length }}</span>
        <span class="rm-seg rm-building">Building {{ state.building|length }}</span>
        <span class="rm-seg rm-shipped">Shipped {{ shipped_total }}</span>
      </div>
      {% include "web/partials/_status_group.html" with label="Building" slices=state.building empty_text="Nothing here yet" %}
      {% include "web/partials/_status_group.html" with label="Planned" slices=state.planned empty_text="Nothing here yet" %}
      {% include "web/partials/_status_group.html" with label="Idea" slices=state.idea empty_text="Nothing here yet" %}
      {% include "web/partials/_status_group.html" with label="Shipped" slices=state.shipped empty_text="Nothing here yet" more_url="?view=list&status=shipped" more_count=shipped_total more_label="shipped" more_hidden=shipped_hidden %}
    {% else %}
      {% include "web/partials/_board.html" %}
      {% if not has_any_slice %}
        <div class="empty muted">Nothing here yet — add a slice in any area and it shows up on the board.</div>
      {% endif %}
    {% endif %}
  {% endif %}
{% endblock %}
```

- [ ] **Step 5: Add the kanban shipped footer to `_board.html`**

In `tuckit/web/templates/web/partials/_board.html`, add the footer inside `.board-col`, right after the `.board-col-cards` div (after line 13):
```html
        <div class="board-col-cards">
          {% for slice in slices %}{% include "web/partials/_slice_card.html" %}{% endfor %}
        </div>
        {% if board_scope and status == "shipped" and shipped_hidden %}
          <a class="board-col-more" href="?view=list&status=shipped">View all shipped ({{ shipped_total }}) →</a>
        {% endif %}
```

- [ ] **Step 6: Add the optional list footer to `_status_group.html`**

Replace `tuckit/web/templates/web/partials/_status_group.html` with:
```html
{% load web_extras %}
<section class="group">
  {% include "web/partials/_group_label.html" with label=label count=slices|length %}
  {% if slices %}
    <div class="panel">
      {% for slice in slices %}{% include "web/partials/_slice_row.html" %}{% endfor %}
    </div>
  {% else %}
    <div class="empty muted">{{ empty_text|default:"" }}</div>
  {% endif %}
  {% if more_hidden %}
    <a class="group-more" href="{{ more_url }}">View all {{ more_label }} ({{ more_count }}) →</a>
  {% endif %}
</section>
```
(Preserve the original first line / `{% load %}` if present — check the current file head and keep its existing load tags.)

- [ ] **Step 7: Add footer CSS to `app.css`**

Append near the board rules (after `.card-bites`, around line 271) in `tuckit/web/static/web/app.css`:
```css
/* "View all" affordance under a capped shipped column / group. */
.board-col-more, .group-more {
  display: inline-block;
  margin-top: 8px;
  padding: 6px 4px;
  color: var(--ink-soft);
  font-family: var(--mono);
  font-size: 12px;
  text-decoration: none;
}
.board-col-more { padding-left: 8px; }
.board-col-more:hover, .group-more:hover { color: var(--ink); }
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_board.py -q`
Expected: PASS (all, including the 4 new + existing 15).

- [ ] **Step 9: Commit**

```bash
git add tuckit/web/views/pages.py tuckit/web/templates/web/roadmap.html \
        tuckit/web/templates/web/partials/_board.html \
        tuckit/web/templates/web/partials/_status_group.html \
        tuckit/web/static/web/app.css tests/web/test_board.py
git commit -m "feat(board): cap shipped column + generic status filter view"
```

---

### Task 4: Preserve the footer across drag re-render (`slice_move`)

**Files:**
- Modify: `tuckit/web/views/board.py:10-11` (import), `:37-49` (workspace re-render branch)
- Test: `tests/web/test_board.py` (append)

**Interfaces:**
- Consumes: `roadmap_board_view` from Task 2.
- Produces: `board.slice_move` with `?scope=workspace` re-renders `_board.html` including `shipped_total` / `shipped_hidden` so the "View all" footer survives.

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_board.py`:
```python
@pytest.mark.django_db
def test_workspace_move_rerender_keeps_shipped_footer(client_local, workspace):
    workspace.shipped_board_mode = "count"
    workspace.shipped_board_limit = 1
    workspace.save(update_fields=["shipped_board_mode", "shipped_board_limit"])
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    create_slice(a, "shipped one", status="shipped")
    create_slice(a, "shipped two", status="shipped")
    mover = create_slice(a, "mover", status="planned")
    resp = client_local.post(
        f"{p}/slices/{mover.id}/move?scope=workspace",
        {"status": "building"}, HTTP_HX_REQUEST="true",
    )
    body = resp.content.decode()
    assert "View all shipped (2)" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_board.py::test_workspace_move_rerender_keeps_shipped_footer -q`
Expected: FAIL — footer absent (branch passes no shipped meta).

- [ ] **Step 3: Update the import and workspace branch**

In `tuckit/web/views/board.py`, change the import (line 11):
```python
from tuckit.core.services.state import roadmap_board_view
```
Replace the workspace branch inside the `HX-Request` block (currently lines ~41-46):
```python
        if request.GET.get("scope") == "workspace":
            board = roadmap_board_view(ws)
            return render(request, "web/partials/_board.html", {
                "groups": board["groups"],
                "show_area": True,
                "board_scope": "workspace",
                "shipped_total": board["shipped_total"],
                "shipped_hidden": board["shipped_hidden"],
            })
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_board.py -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add tuckit/web/views/board.py tests/web/test_board.py
git commit -m "feat(board): keep shipped footer on workspace drag re-render"
```

---

### Task 5: Workspace setting — endpoint, URL, form

**Files:**
- Modify: `tuckit/web/views/settings.py` (add `shipped_board_prefs` view; reuse existing `require_POST`, `is_org_admin`, `HttpResponse`, `HttpResponseForbidden` imports — verify at file head)
- Modify: `tuckit/web/urls.py:41-46` (settings_patterns — add route)
- Modify: `tuckit/web/templates/web/settings_workspace.html` (add a section)
- Test: `tests/web/test_settings.py` (append or create)

**Interfaces:**
- Consumes: `Workspace.shipped_board_mode`, `Workspace.shipped_board_limit`.
- Produces: `web:shipped_board_prefs` (POST, org-admin gated). Accepts `mode` in `{count, days}` and `limit` int in `1..365`. 204 on success, 400 on invalid input, 403 for non-admins.

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_settings.py` (create the file with this content if it does not exist):
```python
import pytest
from tuckit.core.models import Workspace


@pytest.mark.django_db
def test_shipped_board_prefs_updates(client_local, workspace):
    p = f"/settings/{workspace.org.slug}/{workspace.slug}/shipped-board"
    resp = client_local.post(p, {"mode": "days", "limit": "30"})
    assert resp.status_code == 204
    ws = Workspace.objects.get(pk=workspace.pk)
    assert ws.shipped_board_mode == "days"
    assert ws.shipped_board_limit == 30


@pytest.mark.django_db
def test_shipped_board_prefs_rejects_bad_mode(client_local, workspace):
    p = f"/settings/{workspace.org.slug}/{workspace.slug}/shipped-board"
    resp = client_local.post(p, {"mode": "weeks", "limit": "5"})
    assert resp.status_code == 400


@pytest.mark.django_db
def test_shipped_board_prefs_rejects_out_of_range(client_local, workspace):
    p = f"/settings/{workspace.org.slug}/{workspace.slug}/shipped-board"
    resp = client_local.post(p, {"mode": "count", "limit": "0"})
    assert resp.status_code == 400
```
Note: the bootstrapped `local@tuckit.local` user is an org admin (verify via `is_org_admin`); if the tests 403, the fixture user needs admin — confirm before assuming a code bug.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_settings.py -k shipped_board -q`
Expected: FAIL — `NoReverseMatch` / 404 (route missing).

- [ ] **Step 3: Add the view**

Confirm the imports at the head of `tuckit/web/views/settings.py` include `require_POST`, `HttpResponse`, `HttpResponseForbidden`, `get_current_workspace`, `is_org_admin` (the existing `token_create`/`workspace_rename` views use them). Add the view:
```python
@require_POST
def shipped_board_prefs(request):
    ws = get_current_workspace(request)
    if ws is None or not is_org_admin(request.user, ws.org):
        return HttpResponseForbidden("권한이 없습니다")
    mode = request.POST.get("mode")
    if mode not in ("count", "days"):
        return HttpResponse("invalid mode", status=400)
    try:
        limit = int(request.POST.get("limit", ""))
    except (TypeError, ValueError):
        return HttpResponse("invalid limit", status=400)
    if not (1 <= limit <= 365):
        return HttpResponse("limit out of range", status=400)
    ws.shipped_board_mode = mode
    ws.shipped_board_limit = limit
    ws.save(update_fields=["shipped_board_mode", "shipped_board_limit", "updated_at"])
    return HttpResponse(status=204)
```

- [ ] **Step 4: Register the URL**

In `tuckit/web/urls.py`, add inside `settings_patterns` after the `workspace_rename` line (line 43):
```python
    path("settings/<slug:org_slug>/<slug:ws_slug>/shipped-board", settings_views.shipped_board_prefs, name="shipped_board_prefs"),
```

- [ ] **Step 5: Add the settings form**

In `tuckit/web/templates/web/settings_workspace.html`, add a section after the "Connect an agent" section (after line 42):
```html
  <section class="group">
    <div class="group-label">Shipped shown on board</div>
    <div class="hint">How many completed slices the Board tab keeps visible before "View all shipped".</div>
    <form class="shipped-board-prefs" hx-post="{% url 'web:shipped_board_prefs' current_workspace.org.slug current_workspace.slug %}" hx-swap="none">
      <select name="mode">
        <option value="count"{% if workspace.shipped_board_mode == 'count' %} selected{% endif %}>Most recent (count)</option>
        <option value="days"{% if workspace.shipped_board_mode == 'days' %} selected{% endif %}>Last N days</option>
      </select>
      <input name="limit" type="number" min="1" max="365" value="{{ workspace.shipped_board_limit }}">
      <button type="submit" class="btn">Save</button>
    </form>
  </section>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_settings.py -k shipped_board -q`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/views/settings.py tuckit/web/urls.py \
        tuckit/web/templates/web/settings_workspace.html tests/web/test_settings.py
git commit -m "feat(settings): configure shipped-board cap (mode + limit)"
```

---

### Task 6: Home "Recently shipped" — cap + unified link

**Files:**
- Modify: `tuckit/web/views/pages.py` (home view — cap shipped, pass meta)
- Modify: `tuckit/web/templates/web/home.html:38-50`
- Test: `tests/web/test_home.py` (append)

**Interfaces:**
- Consumes: `cap_shipped` from Task 2.
- Produces: home context gains `shipped_total`, `shipped_hidden`; `state.shipped` is capped. Template links to `{% wurl 'web:roadmap' %}?view=list&status=shipped`.

- [ ] **Step 1: Write the failing test**

Append to `tests/web/test_home.py`:
```python
import pytest
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice


@pytest.mark.django_db
def test_home_recently_shipped_caps_and_links(client_local, workspace):
    workspace.shipped_board_mode = "count"
    workspace.shipped_board_limit = 1
    workspace.save(update_fields=["shipped_board_mode", "shipped_board_limit"])
    p = f"/{workspace.org.slug}/{workspace.slug}"
    a = create_area(workspace, "Design")
    create_slice(a, "shipped one", status="shipped")
    create_slice(a, "shipped two", status="shipped")
    body = client_local.get(f"{p}/").content.decode()
    assert "Recently shipped 2" in body           # count shows the true total
    assert "status=shipped" in body               # unified view-all link
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_home.py::test_home_recently_shipped_caps_and_links -q`
Expected: FAIL — link absent; count reflects uncapped list.

- [ ] **Step 3: Cap shipped in the home view**

In `tuckit/web/views/pages.py`, update the `home` view. Add `cap_shipped` to the state import (extend the Task 3 import block to also import `cap_shipped`). Then compute the cap:
```python
def home(request):
    ws = get_current_workspace(request)
    ob = onboarding_state(ws) if ws else None
    show_get_started = bool(ws and not ws.onboarding_dismissed and ob and not ob.done)
    state = home_state(ws) if ws else {}
    shipped_total = shipped_hidden = 0
    if ws:
        visible, shipped_total = cap_shipped(ws, state.get("shipped", []))
        shipped_hidden = shipped_total - len(visible)
        state = {**state, "shipped": visible}
    return render(request, "web/home.html", {
        "workspace": ws,
        "state": state,
        "in_progress": in_progress_state(ws) if ws else {"slices": [], "bites": []},
        "roadmap": roadmap_state(ws) if ws else {},
        "recent_activity": recent_activity(ws) if ws else [],
        "onboarding": ob,
        "show_get_started": show_get_started,
        "shipped_total": shipped_total,
        "shipped_hidden": shipped_hidden,
    })
```

- [ ] **Step 4: Update the home template**

In `tuckit/web/templates/web/home.html`, replace the "Recently shipped" section (lines 38-50):
```html
  <section class="group" x-data="{open:false}">
    <button class="tail-toggle group-label muted" type="button" x-on:click="open=!open" :class="{'tail-open': open}">
      {% icon "chevron" "icon icon-chev" %}
      Recently shipped {{ shipped_total }}
    </button>
    <div class="tail-body" x-show="open" x-cloak>
      {% if state.shipped %}
        <div class="panel">{% for slice in state.shipped %}{% include "web/partials/_slice_row.html" %}{% endfor %}</div>
        {% if shipped_hidden %}
          <a class="group-more" href="{% wurl 'web:roadmap' %}?view=list&status=shipped">View all shipped ({{ shipped_total }}) →</a>
        {% endif %}
      {% else %}
        <div class="empty muted">Nothing shipped yet.</div>
      {% endif %}
    </div>
  </section>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_home.py -q`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/views/pages.py tuckit/web/templates/web/home.html tests/web/test_home.py
git commit -m "feat(home): cap recently-shipped + unified view-all link"
```

---

### Task 7: Full-suite regression + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS (all — prior 426 + the new tests from Tasks 1-6).

- [ ] **Step 2: Manual smoke (server already runs via `uv run --env-file .env uvicorn tuckit.asgi:app --port 8000`)**

- Set limit to 1 in Workspace settings; confirm the Board Shipped column shows 1 card + "View all shipped (N) →".
- Click it → lands on `?view=list&status=shipped`, all shipped listed flat with Area badges, "← Board" returns.
- Toggle mode to `days`, limit 0-day edge rejected in settings; 30 days shows recent only.
- Home "Recently shipped" expands to the capped list with the same view-all link.

- [ ] **Step 3: Final commit (if any smoke fixups)**

```bash
git add -A -- ':!docs/superpowers'
git commit -m "chore(board): shipped cap smoke fixups"
```

---

## Self-Review

**Spec coverage:**
- Workspace settings (mode + limit) → Task 1 + Task 5. ✓
- Recency sort + `cap_shipped` → Task 2. ✓
- Board cap + footer (kanban & list) → Task 3. ✓
- Generic `?status=` filter / archive-as-filter → Task 3. ✓
- Footer survives drag re-render → Task 4. ✓
- Home cap + unified link → Task 6. ✓
- CSS tokens-only footer → Task 3 Step 7. ✓
- Out-of-scope items (area board, dropped, pagination) → untouched. ✓

**Placeholder scan:** No TBD/TODO; every code/test step carries real content. The `_status_group.html` note to preserve existing `{% load %}` tags is a concrete instruction, not a placeholder.

**Type consistency:** `roadmap_board_view` returns `{state, groups, shipped_total, shipped_hidden}` — consumed identically in Task 3 (view) and Task 4 (slice_move). `cap_shipped(workspace, shipped) -> (visible, total)` used in Tasks 2/3/6 with matching arity. `ROADMAP_STATUS_KEYS` defined Task 2, imported Task 3. Template context keys (`shipped_total`, `shipped_hidden`, `board_scope`, `show_area`, `more_hidden`) match across `_board.html`, `_status_group.html`, `roadmap.html`, `home.html`.
