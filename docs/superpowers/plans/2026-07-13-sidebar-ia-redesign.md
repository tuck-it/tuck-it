# Sidebar IA Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the sidebar from 6 object tabs to 3 attention surfaces (Home · Inbox · Board) + Areas, demote Activity to a slide-over panel, and make Home the single "now" surface — all by relabeling and rewiring existing views, with zero model changes.

**Architecture:** Django templates + Alpine.js + HTMX. Sidebar is `partials/_sidebar.html`. Reuses the existing `#panel` slide-over (htmx swaps its innerHTML; focus mgmt in `base.html`). Every surface reuses existing services in `core/services/state.py` (`in_progress_state`, `attention_items`, `home_state`, `roadmap_state`, `recent_activity`). Routes and route-names are UNCHANGED (`web:triage`, `web:roadmap`, `web:activity` stay); only user-facing labels + Home content change.

**Tech Stack:** Python 3 / Django 5.2, Alpine.js, HTMX, plain CSS with design tokens.

## Global Constraints

- Colors/radius via `var(--token)` ONLY — no literal hex, no hardcoded radius. Accent `--blue`. Surfaces `--radius`, controls `--radius-small`.
- PUBLIC `tuckit` repo — no billing/cloud/pricing.
- **No model/schema changes, no migrations.** Reuse existing services/fields only.
- Route paths & names stay put this pass (deep-link project owns URL restructuring). We change labels + which nav entries appear.
- Icon tag: `{% icon "name" "extra-class" %}`. Reuse the existing `activity` (clock) glyph for the Activity bell — do NOT add a new icon.
- Run tests: `uv run pytest <path> -v` (repo root = this worktree/tuckit repo; no `cd tuckit`).
- Do NOT commit `docs/superpowers/` (local-only).

---

### Task 1: Activity slide-over — view panel branch + partial

**Files:**
- Modify: `tuckit/tuckit/web/views/pages.py` (`activity` view: panel branch)
- Create: `tuckit/tuckit/web/templates/web/partials/_activity_panel.html`
- Test: `tuckit/tests/web/test_lens_pages.py` (append)

No CSS change — `.panel-inner`, `.panel`, `.panel-head`, `.ghost`, and `.activity-row` already exist and are reused as-is.

**Interfaces:**
- Consumes: `recent_activity(ws, limit=100)`, existing `#panel` mechanism (a partial whose root is `.panel-inner`, with a `[aria-label="Close panel"]` button calling `closePanel(document.getElementById('panel'))`), `_activity_row.html`.
- Produces: `web:activity` returns `_activity_panel.html` when `?panel=1` + `HX-Request`, else the full `activity.html`.

- [ ] **Step 1: Write the failing test**

Append to `tuckit/tests/web/test_lens_pages.py`:

```python
@pytest.mark.django_db
def test_activity_panel_branch_returns_slideover(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice, set_slice_status
    a = create_area(workspace, "Backend")
    s = create_slice(a, "패널 이벤트", status="building")
    set_slice_status(s, "shipped")
    # panel branch: HX request with ?panel=1 returns just the slide-over inner
    body = client_local.get("/activity/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="panel-inner"' in body
    assert 'aria-label="Close panel"' in body
    assert "패널 이벤트" in body
    assert "<aside class=\"sidebar\"" not in body   # not the full page shell


@pytest.mark.django_db
def test_activity_full_page_still_works(client_local, workspace):
    body = client_local.get("/activity/").content.decode()
    assert 'class="page-title"' in body            # full page, not panel
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_lens_pages.py::test_activity_panel_branch_returns_slideover -v`
Expected: FAIL — `panel-inner` absent (full page returned).

- [ ] **Step 3: Add the panel branch to the view**

In `tuckit/tuckit/web/views/pages.py`, replace the `activity` function:

```python
def activity(request):
    ws = get_current_workspace(request)
    events = recent_activity(ws, limit=100) if ws else []
    is_panel = request.GET.get("panel") == "1" and request.headers.get("HX-Request")
    template = "web/partials/_activity_panel.html" if is_panel else "web/activity.html"
    return render(request, template, {"events": events})
```

- [ ] **Step 4: Create the panel partial**

Create `tuckit/tuckit/web/templates/web/partials/_activity_panel.html` (mirrors `_slice_panel.html`'s shell):

```django
<div class="panel-inner">
  <div class="panel-head">
    <div class="panel-head-main">
      <span class="panel-title" id="panel-title">Activity</span>
    </div>
    <a class="ghost" href="{% url 'web:activity' %}">Open full</a>
    <button class="ghost" type="button" aria-label="Close panel"
            hx-on:click="closePanel(document.getElementById('panel'))">✕</button>
  </div>
  {% if events %}
    <div class="panel">
      {% for event in events %}{% include "web/partials/_activity_row.html" %}{% endfor %}
    </div>
  {% else %}
    <div class="empty muted">No activity yet</div>
  {% endif %}
</div>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_lens_pages.py -v`
Expected: PASS (new panel test + full-page test + existing lens tests).

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/views/pages.py tuckit/web/templates/web/partials/_activity_panel.html tests/web/test_lens_pages.py
git commit -m "feat(web): serve Activity as a slide-over panel branch (?panel=1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Sidebar IA — Home/Inbox/Board + Activity bell

**Files:**
- Modify: `tuckit/tuckit/web/templates/web/partials/_sidebar.html`
- Test: `tuckit/tests/web/test_home_shell.py`, `tuckit/tests/web/test_shell.py`, `tuckit/tests/web/test_lens_pages.py`, `tuckit/tests/web/test_home.py`

**Interfaces:**
- Consumes: existing routes `web:home`, `web:triage`, `web:roadmap`, `web:activity`, `web:settings_workspace`; `triage_count` include; `activity` icon.
- Produces: nav group = Home, Inbox (label; route `web:triage`), Board (label; route `web:roadmap`). Attention/In-Progress/standalone-Activity removed from nav. Util row gains an Activity bell button: `hx-get="{% url 'web:activity' %}?panel=1" hx-target="#panel"`.

- [ ] **Step 1: Rewrite the failing tests**

Replace `test_home_shell.py::test_nav_order_queues_before_states_activity_last` with:

```python
@pytest.mark.django_db
def test_nav_is_home_inbox_board_only(client_local, workspace):
    body = client_local.get("/").content.decode()
    i_home = body.find(">Home<")
    i_inbox = body.find(">Inbox<")
    i_board = body.find(">Board<")
    assert -1 not in (i_home, i_inbox, i_board)
    assert i_home < i_inbox < i_board
    # object tabs removed from the nav group
    assert ">Attention<" not in body
    assert ">In Progress<" not in body
    # Activity is no longer a nav label; it's the utility bell
    nav_group = body.split('class="nav-group"')[1].split("</nav>")[0]
    assert ">Activity<" not in nav_group
    # old names gone as labels
    assert ">Triage<" not in body
    assert ">Roadmap<" not in body


@pytest.mark.django_db
def test_activity_bell_in_utility_row(client_local, workspace):
    body = client_local.get("/").content.decode()
    assert '/activity/?panel=1' in body            # bell opens the slide-over
    assert 'aria-label="Activity"' in body
```

In `test_shell.py::test_sidebar_grouped_with_english_labels_and_capture`, replace the label assertions block:

```python
    assert ">Home<" in body and ">Inbox<" in body and ">Settings<" in body
    assert 'href="/triage/"' in body               # Inbox anchor keeps the route
    assert ">Board<" in body                        # was Roadmap
    assert ">Attention<" not in body and ">In Progress<" not in body
    assert 'class="nav-sep"' in body
```

Replace `test_shell.py::test_sidebar_lens_group_with_counts` body with the new IA (Inbox count in sidebar; lens badges moved to Home):

```python
@pytest.mark.django_db
def test_sidebar_inbox_count_and_no_lens_tabs(client_local, workspace):
    from tuckit.core.services.areas import get_or_create_triage
    from tuckit.core.services.slices import create_slice
    create_slice(get_or_create_triage(workspace), "미분류", status="idea")
    body = client_local.get("/").content.decode()
    assert ">Inbox<" in body
    assert 'id="triage-count"' in body                       # inbox count badge kept
    assert 'href="/attention/"' not in body                  # lens tabs gone from nav
    assert 'href="/in-progress/"' not in body
```

Replace `test_lens_pages.py::test_sidebar_has_activity_lens` with:

```python
@pytest.mark.django_db
def test_sidebar_activity_is_bell_not_nav(client_local, workspace):
    body = client_local.get("/").content.decode()
    assert 'aria-label="Activity"' in body and '/activity/?panel=1' in body
    nav_group = body.split('class="nav-group"')[1].split("</nav>")[0]
    assert ">Activity<" not in nav_group
```

In `test_lens_pages.py::test_activity_page_lists_events`, change the sidebar-link assertion line:

```python
    assert '/activity/?panel=1' in body   # Activity reachable via the utility bell
```

In `test_home.py::test_home_omits_roadmap_strip_and_recent_activity`, change the two reachability lines:

```python
    assert 'href="/roadmap/"' in body                 # Board still reachable via sidebar
    assert '/activity/?panel=1' in body               # Activity via the utility bell
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_home_shell.py tests/web/test_shell.py tests/web/test_lens_pages.py -v -k "nav_is_home or activity_bell or grouped_with_english or inbox_count or activity_is_bell or activity_page_lists"`
Expected: FAIL (new labels/bell not present yet).

- [ ] **Step 3: Rewrite the sidebar nav group + util row**

In `tuckit/tuckit/web/templates/web/partials/_sidebar.html`, replace the `<nav class="nav-group">…</nav>` block with:

```django
  <nav class="nav-group">
    <a class="nav{% if request.resolver_match.url_name == 'home' %} nav--active{% endif %}"
       href="{% url 'web:home' %}">{% icon "home" %}<span class="nav-label">Home</span></a>
    <a class="nav{% if request.resolver_match.url_name == 'triage' %} nav--active{% endif %}"
       href="{% url 'web:triage' %}">{% icon "triage" %}<span class="nav-label">Inbox</span>
       {% include "web/partials/_triage_count.html" %}</a>
    <a class="nav{% if request.resolver_match.url_name == 'roadmap' %} nav--active{% endif %}"
       href="{% url 'web:roadmap' %}">{% icon "roadmap" %}<span class="nav-label">Board</span></a>
  </nav>
```

Then in the `.util-row`, insert an Activity bell button between Settings and the theme toggle (after the `</a>` of `util-settings`, before the theme `<button>`):

```django
    <button class="util-btn util-activity" type="button"
            aria-label="Activity" title="Activity"
            hx-get="{% url 'web:activity' %}?panel=1" hx-target="#panel">{% icon "activity" %}</button>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_home_shell.py tests/web/test_shell.py tests/web/test_lens_pages.py tests/web/test_home.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tuckit/web/templates/web/partials/_sidebar.html tests/web/test_home_shell.py tests/web/test_shell.py tests/web/test_lens_pages.py tests/web/test_home.py
git commit -m "feat(web): sidebar IA -> Home/Inbox/Board + Areas; Activity as utility bell

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Home becomes the single "now" surface

**Files:**
- Modify: `tuckit/tuckit/web/views/pages.py` (`home` passes `in_progress`)
- Modify: `tuckit/tuckit/web/templates/web/home.html`
- Test: `tuckit/tests/web/test_home.py`

**Interfaces:**
- Consumes: `in_progress_state(ws)` → `{"slices", "bites"}`; existing `home_state` for attention + shipped.
- Produces: Home shows Attention strip + Now (building slices) + Doing (doing bites) + Recently shipped. No planned/ideas/someday.

- [ ] **Step 1: Update the failing tests**

In `tuckit/tests/web/test_home.py::test_home_has_heading_and_capture`, change the label assertion (drop "Next", add "Doing"):

```python
    assert "Needs you" in body and "Now" in body and "Doing" in body
    assert "Next" not in body                       # planned pipeline moved to Board
```

Add a new test:

```python
@pytest.mark.django_db
def test_home_shows_doing_bites_and_no_planned(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice
    from tuckit.core.services.bites import create_bite
    a = create_area(workspace, "Backend")
    s = create_slice(a, "빌딩 슬라이스", status="building")
    create_bite(s, "지금 하는 것", status="doing")
    create_slice(a, "다음 계획", status="planned")
    body = client_local.get("/").content.decode()
    assert "지금 하는 것" in body                    # doing bite on Home
    assert "다음 계획" not in body                   # planned NOT on Home (it's on Board)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_home.py::test_home_shows_doing_bites_and_no_planned tests/web/test_home.py::test_home_has_heading_and_capture -v`
Expected: FAIL — "다음 계획" still on Home; "Doing" absent.

- [ ] **Step 3: Pass in_progress to the home view**

In `tuckit/tuckit/web/views/pages.py`, add the import if missing (it already imports `in_progress_state`) and add to the `home` render context:

```python
def home(request):
    ws = get_current_workspace(request)
    ob = onboarding_state(ws) if ws else None
    show_get_started = bool(ws and not ws.onboarding_dismissed and ob and not ob.done)
    return render(request, "web/home.html", {
        "workspace": ws,
        "state": home_state(ws) if ws else {},
        "in_progress": in_progress_state(ws) if ws else {"slices": [], "bites": []},
        "roadmap": roadmap_state(ws) if ws else {},
        "recent_activity": recent_activity(ws) if ws else [],
        "onboarding": ob,
        "show_get_started": show_get_started,
    })
```

- [ ] **Step 4: Rewrite the Home body**

In `tuckit/tuckit/web/templates/web/home.html`, replace everything from the `{% if show_get_started %}` line through the end of the tail `</section>` (currently lines 16–39) with:

```django
  {% if show_get_started %}{% include "web/partials/_get_started.html" %}{% endif %}

  {% include "web/partials/_status_group.html" with label="Now" slices=in_progress.slices empty_text="Nothing in progress. Move a slice to building and it shows up here." %}

  <section class="group">
    <div class="group-label">Doing</div>
    {% if in_progress.bites %}
      <div class="panel">
        {% for bite in in_progress.bites %}
          <a class="slice-row" href="{% url 'web:slice' bite.slice.id %}"
             hx-get="{% url 'web:slice' bite.slice.id %}?panel=1" hx-target="#panel" hx-push-url="true">
            {% include "web/partials/_status_dot.html" with status=bite.status %}
            <span class="row-title">{{ bite.title }}</span>
            <span class="row-meta">{{ bite.slice.title }}</span>
          </a>
        {% endfor %}
      </div>
    {% else %}
      <div class="empty muted">No bites in progress yet.</div>
    {% endif %}
  </section>

  <section class="group" x-data="{open:false}">
    <button class="tail-toggle group-label muted" type="button" x-on:click="open=!open" :class="{'tail-open': open}">
      {% icon "chevron" "icon icon-chev" %}
      Recently shipped {{ state.shipped|length }}
    </button>
    <div class="tail-body" x-show="open" x-cloak>
      {% if state.shipped %}
        <div class="panel">{% for slice in state.shipped %}{% include "web/partials/_slice_row.html" %}{% endfor %}</div>
      {% else %}
        <div class="empty muted">Nothing shipped yet.</div>
      {% endif %}
    </div>
  </section>
```

(The header + attention section above line 16 stay unchanged. `Now` now uses `in_progress.slices` — building slices — identical set to the old `state.building`, so `test_home_lists_building_and_attention` still passes.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_home.py -v`
Expected: PASS (new tests + existing home tests; `test_home_tail_contains_shipped_items` still sees `tail-body` + the shipped title).

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/views/pages.py tuckit/web/templates/web/home.html tests/web/test_home.py
git commit -m "feat(web): Home = single now surface (focus + doing + shipped); pipeline moves to Board

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Inbox page — heading + agent source badge

**Files:**
- Modify: `tuckit/tuckit/web/templates/web/triage.html` (heading "Triage" → "Inbox")
- Modify: `tuckit/tuckit/web/templates/web/partials/_triage_row.html` (source badge)
- Modify: `tuckit/tuckit/web/static/web/app.css` (`.source-badge`)
- Test: `tuckit/tests/web/test_capture_triage.py` (append)

**Interfaces:**
- Consumes: `slice.source` (existing field, `human`/`agent`).
- Produces: page heading "Inbox"; each row shows an `agent`/`you` badge with `.source-badge` (agent variant `--accent`).

- [ ] **Step 1: Write the failing test**

Append to `tuckit/tests/web/test_capture_triage.py`:

```python
@pytest.mark.django_db
def test_inbox_heading_and_agent_source_badge(client_local, workspace):
    from tuckit.core.services.areas import get_or_create_triage
    from tuckit.core.services.slices import create_slice
    tri = get_or_create_triage(workspace)
    create_slice(tri, "에이전트가 만든 것", status="idea", source="agent")
    body = client_local.get("/triage/").content.decode()
    assert '<h1 class="page-title">Inbox</h1>' in body       # renamed heading
    assert 'class="source-badge is-agent"' in body           # agent item flagged
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_capture_triage.py::test_inbox_heading_and_agent_source_badge -v`
Expected: FAIL — heading still "Triage", no `.source-badge`.

- [ ] **Step 3: Rename the heading**

In `tuckit/tuckit/web/templates/web/triage.html`, change:

```django
      <h1 class="page-title">Triage</h1>
```

to:

```django
      <h1 class="page-title">Inbox</h1>
```

- [ ] **Step 4: Add the source badge to the row**

In `tuckit/tuckit/web/templates/web/partials/_triage_row.html`, replace the `row-meta` line:

```django
  <span class="row-meta">{% if slice.source == 'agent' %}agent{% else %}you{% endif %} · {{ slice.created_at|timesince }}</span>
```

with:

```django
  <span class="source-badge{% if slice.source == 'agent' %} is-agent{% endif %}">{% if slice.source == 'agent' %}agent{% else %}you{% endif %}</span>
  <span class="row-meta">{{ slice.created_at|timesince }}</span>
```

- [ ] **Step 5: Add the badge CSS**

In `tuckit/tuckit/web/static/web/app.css`, near `.activity-actor` (~line 1013), add:

```css
.source-badge {
  font-family: var(--mono); font-size: 10px; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--ink-faint);
  border: 1px solid var(--line); border-radius: var(--radius-small);
  padding: 1px 6px; flex: 0 0 auto;
}
.source-badge.is-agent { color: var(--accent); border-color: var(--accent); }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_capture_triage.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/triage.html tuckit/web/templates/web/partials/_triage_row.html tuckit/web/static/web/app.css tests/web/test_capture_triage.py
git commit -m "feat(web): Inbox heading + agent/you source badge on intake rows

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Board page heading rename

**Files:**
- Modify: `tuckit/tuckit/web/templates/web/roadmap.html` (heading "Roadmap" → "Board")
- Test: `tuckit/tests/web/test_lens_pages.py` (append)

**Interfaces:**
- Consumes: `roadmap_state` (unchanged — already the full idea→shipped pipeline).
- Produces: page heading "Board".

- [ ] **Step 1: Write the failing test**

Append to `tuckit/tests/web/test_lens_pages.py`:

```python
@pytest.mark.django_db
def test_board_page_heading(client_local, workspace):
    body = client_local.get("/roadmap/").content.decode()
    assert '<h1 class="page-title">Board</h1>' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_lens_pages.py::test_board_page_heading -v`
Expected: FAIL — heading still "Roadmap".

- [ ] **Step 3: Rename the heading**

In `tuckit/tuckit/web/templates/web/roadmap.html`, change:

```django
  <header class="page-head"><div class="page-head-l"><h1 class="page-title">Roadmap</h1></div></header>
```

to:

```django
  <header class="page-head"><div class="page-head-l"><h1 class="page-title">Board</h1></div></header>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_lens_pages.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tuckit/web/templates/web/roadmap.html tests/web/test_lens_pages.py
git commit -m "feat(web): rename Roadmap page heading to Board

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Per-item activity thread on slice detail

**Files:**
- Modify: `tuckit/tuckit/core/services/activity.py` (add `slice_activity`)
- Modify: `tuckit/tuckit/web/panel.py` (`slice_panel_context` adds `activity`)
- Modify: `tuckit/tuckit/web/templates/web/partials/_slice_panel.html` (thread section)
- Modify: `tuckit/tuckit/web/static/web/app.css` (`.slice-activity` spacing — minimal)
- Test: `tuckit/tests/web/test_slice_detail.py` (append)

**Interfaces:**
- Consumes: `ActivityEvent` (`target_type`/`target_id`), `slice_.bites`,
  `slice_.area.workspace`, `_activity_row.html`.
- Produces: `slice_activity(slice_) -> list[ActivityEvent]` (oldest-first, this
  slice's events + its bites' events); `slice_panel_context` gains `activity`;
  the panel renders a `.slice-activity` thread. Read-only — no writes.

- [ ] **Step 1: Write the failing test**

Append to `tuckit/tests/web/test_slice_detail.py`:

```python
@pytest.mark.django_db
def test_slice_panel_shows_its_activity_thread(client_local, workspace):
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice, set_slice_status
    from tuckit.core.services.bites import create_bite
    a = create_area(workspace, "Backend")
    s = create_slice(a, "스레드 슬라이스", status="idea")   # logs created (slice)
    set_slice_status(s, "building")                          # logs status_changed (slice)
    create_bite(s, "첫 바이트")                              # logs created (bite)
    body = client_local.get(f"/slices/{s.id}/?panel=1", HTTP_HX_REQUEST="true").content.decode()
    assert 'class="slice-activity"' in body                  # thread section present
    assert body.count('class="activity-row"') >= 3           # slice + status + bite events
    assert "첫 바이트" in body                               # bite event joined into the slice thread


@pytest.mark.django_db
def test_slice_activity_helper_is_chronological_and_scoped(workspace):
    from tuckit.core.services.activity import slice_activity
    from tuckit.core.services.areas import create_area
    from tuckit.core.services.slices import create_slice, set_slice_status
    a = create_area(workspace, "Backend")
    s = create_slice(a, "A", status="idea")
    set_slice_status(s, "building")
    other = create_slice(a, "B", status="idea")              # unrelated slice's events excluded
    events = slice_activity(s)
    times = [e.created_at for e in events]
    assert times == sorted(times) and len(events) >= 2        # oldest-first
    assert all(not (e.target_type == "slice" and e.target_id == other.id) for e in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_slice_detail.py::test_slice_panel_shows_its_activity_thread -v`
Expected: FAIL — no `slice_activity`, no `.slice-activity` in the panel.

- [ ] **Step 3: Add the `slice_activity` helper**

In `tuckit/tuckit/core/services/activity.py`, add (top-level, with the existing imports; add `from django.db.models import Q` if absent):

```python
def slice_activity(slice_):
    """Read-only, chronological activity for one slice — its own events plus its
    bites' events, oldest-first — so the detail reads like a comment thread."""
    from django.db.models import Q

    from tuckit.core.models import ActivityEvent

    bite_ids = list(slice_.bites.values_list("id", flat=True))
    return list(
        ActivityEvent.objects.filter(workspace=slice_.area.workspace)
        .filter(Q(target_type="slice", target_id=slice_.id)
                | Q(target_type="bite", target_id__in=bite_ids))
        .order_by("created_at")
    )
```

- [ ] **Step 4: Add `activity` to the panel context**

In `tuckit/tuckit/web/panel.py`, import and use the helper:

```python
from tuckit.core.services.activity import slice_activity
from tuckit.core.services.bites import list_bites


def slice_panel_context(slice_) -> dict:
    return {
        "slice": slice_,
        "spec_html": render_markdown_html(slice_.spec),
        "bites": list(list_bites(slice_)),
        "statuses": ["idea", "planned", "building", "shipped"],
        "activity": slice_activity(slice_),
    }
```

- [ ] **Step 5: Render the thread in the panel**

In `tuckit/tuckit/web/templates/web/partials/_slice_panel.html`, immediately AFTER
the `<div class="panel-meta">…</div>` block (before the
`<div class="status-row status-destructive">`), add:

```django
  {% if activity %}
  <div class="slice-activity">
    <div class="group-label">Activity</div>
    <div class="panel">
      {% for event in activity %}{% include "web/partials/_activity_row.html" %}{% endfor %}
    </div>
  </div>
  {% endif %}
```

- [ ] **Step 6: Minimal spacing CSS**

In `tuckit/tuckit/web/static/web/app.css`, near `.panel-meta` (~line 711), add:

```css
.slice-activity { margin-top: 6px; }
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_slice_detail.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tuckit/core/services/activity.py tuckit/web/panel.py tuckit/web/templates/web/partials/_slice_panel.html tuckit/web/static/web/app.css tests/web/test_slice_detail.py
git commit -m "feat(web): per-item activity thread on slice detail (read-only, Linear-style)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: Full-suite + visual verification

**Files:** none (verification only).

- [ ] **Step 1: Run the web suite**

Run: `uv run pytest tests/web -q`
Expected: all pass (or 1 skip = the landing-drift test if landing sibling absent).

- [ ] **Step 2: Guard against literal hex / hardcoded radius in the diff**

Run: `git diff main -- tuckit/web/static/web/app.css | grep -E '^\+' | grep -iE '#[0-9a-f]{3,6}|[0-9]+px' | grep -viE 'var\(--|width|height|min-height|font-size|letter-spacing|padding|margin|gap|top|left|right|z-index|blur|[0-9]+px [0-9]+px' || echo "CLEAN"`
Expected: `CLEAN`.

- [ ] **Step 3: Visual check (light + dark)**

Drive the app (isolated temp DB + session cookie, as in prior sidebar work, or the `run` skill). Confirm on `/`:
- Sidebar = Home · Inbox · Board + Areas; no Attention/In-Progress/Activity tabs; utility row shows Settings · Activity(clock) · theme.
- Clicking the Activity bell opens the slide-over panel with events + Close.
- Home shows Now (building) + Doing (bites) + Recently-shipped tail; no planned/ideas/someday.
- Inbox (`/triage/`) heading "Inbox"; agent rows show a teal `agent` badge.
- Board (`/roadmap/`) heading "Board" with the full pipeline.
- Opening a slice (click a row → slide-over) shows an **Activity** thread at the
  bottom listing its own + its bites' events, oldest-first.
Toggle theme both ways and re-check.

- [ ] **Step 4: Final commit (only if verification tweaks were needed)**

```bash
git add -A && git commit -m "chore(web): IA redesign verification tweaks"
```

---

## Notes for the implementer

- **No `urls.py` changes.** Route names `web:triage`/`web:roadmap`/`web:activity` stay; only labels/headings change. `nav--active` still matches on those url_names. The deep-link project renames paths later.
- The Activity bell reuses the existing `#panel` slide-over — no new focus/close JS; `base.html` already wires `closePanel`, focus trap, and opener restore for `#panel`.
- Attention & In-Progress **views/routes are intentionally kept** (content now lives on Home) — do not delete them; other efforts / bookmarks may reference them, and the deep-link plan assumes current routes.
- Context processors `attention_count` / `in_progress_count` stay (Home + `test_lens_count_context_processors` use them).
- `Now` on Home uses `in_progress.slices` (building) — same set the old `state.building` showed, so unrelated home assertions keep passing.
