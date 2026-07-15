# Nav Redesign — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the capture bucket Inbox→Triage everywhere, restructure the sidebar into grouped navigation with a prominent Capture button, and fix the capture UX so it gives live feedback (toast + count + row) without a page refresh.

**Architecture:** Three-layer rename (model field → service symbols → user-facing URLs/templates), then a sidebar rewrite, then a capture-view change that returns out-of-band (OOB) htmx swaps. All writes already funnel through the services layer; Phase 1 touches only web + rename, no new models.

**Tech Stack:** Django 5, htmx 2.x (OOB swaps), Alpine.js, uv + pytest. Server-rendered templates.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-07-12-nav-and-triage-redesign-design.md` — this plan implements Phase 1 (parts A + B + E) of §9.
- **No user data to preserve** — the project has no production users; a `RenameField` migration is still required so the schema stays consistent.
- **Every task ends green:** `uv run pytest -q` must pass (baseline: 215 passed) before each commit.
- **New sidebar labels are English:** `Home`, `Triage`, `Areas`, `Settings`, `Capture`. Other in-app Korean copy (Home page groups, capture modal placeholder) is out of scope for Phase 1.
- **Phase boundary:** the state-lens nav items (`Attention`, `In Progress`, `Roadmap`) and the Home dashboard belong to **Phase 2** — do NOT add them here (their target pages don't exist yet; adding them now creates dead links). Phase 1 sidebar = `Home / Triage / Areas / Settings + Capture`.
- **App label:** `core` (migrations depend on `("core", "0004_alter_workspace_org_delete_membership")`).
- **Run commands from the worktree root:** `/Users/goddessana/Developments/tuckit-projects/tuckit/.claude/worktrees/nav-triage-phase1`.

---

## File Structure

**Task 1 — core rename (field + service symbols)**
- Modify: `tuckit/core/models/domain.py`, `tuckit/core/services/areas.py`, `tuckit/core/services/orgs.py`, `tuckit/core/services/state.py`, `tuckit/web/context_processors.py`, `tuckit/web/views/capture.py`
- Create: `tuckit/core/migrations/0005_rename_area_is_inbox_is_triage.py`
- Modify tests: `tests/test_services_orgs.py`, `tests/test_services_accounts.py`, `tests/test_services_areas.py`, `tests/test_bootstrap.py`, `tests/test_services_state.py`, `tests/web/test_home.py`, `tests/web/test_shell.py`, `tests/web/test_cross_workspace_access.py`, `tests/web/test_capture_inbox.py`

**Task 2 — user-facing rename (URLs / views / templates / strings)**
- Modify: `tuckit/web/urls.py`, `tuckit/web/views/capture.py`, `tuckit/settings.py`, `tuckit/web/context_processors.py`, `tuckit/core/services/state.py`, `tuckit/web/templatetags/web_extras.py`, `tuckit/web/templates/web/partials/_sidebar.html`, `tuckit/web/static/web/app.css`
- Rename files: `inbox.html→triage.html`, `partials/_inbox_row.html→partials/_triage_row.html`, `partials/_inbox_count.html→partials/_triage_count.html`
- Rename test file: `tests/web/test_capture_inbox.py→tests/web/test_capture_triage.py`; modify `tests/web/test_integration.py`

**Task 3 — sidebar restructure (B)**
- Modify: `tuckit/web/templates/web/partials/_sidebar.html`, `tuckit/web/static/web/app.css`, `tuckit/web/templatetags/web_extras.py` (icon key)

**Task 4 — capture UX full-set (E)**
- Modify: `tuckit/web/views/capture.py`, `tuckit/web/templates/web/base.html`, `tuckit/web/templates/web/triage.html`, `tuckit/web/static/web/app.css`, `tests/web/test_capture_triage.py`
- Create: `tuckit/web/templates/web/partials/_capture_result.html`

---

## Task 1: Core rename — `is_inbox`→`is_triage`, `get_or_create_inbox`→`get_or_create_triage`, `INBOX_NAME`→`TRIAGE_NAME`

**Files:**
- Modify: `tuckit/core/models/domain.py:23`
- Create: `tuckit/core/migrations/0005_rename_area_is_inbox_is_triage.py`
- Modify: `tuckit/core/services/areas.py`, `tuckit/core/services/orgs.py:2,43`, `tuckit/core/services/state.py:118-120`, `tuckit/web/context_processors.py:13,24-25`, `tuckit/web/views/capture.py:5,13,23,26`
- Test: all test files listed above under "Task 1" in File Structure

**Interfaces:**
- Consumes: nothing (first task).
- Produces:
  - `Area.is_triage: bool` (was `is_inbox`)
  - `tuckit.core.services.areas.get_or_create_triage(workspace) -> Area`
  - `tuckit.core.services.areas.TRIAGE_NAME = "Triage"` (was `INBOX_NAME = "Inbox"`)

- [ ] **Step 1: Rename the model field**

In `tuckit/core/models/domain.py`, line 23, change:
```python
    is_inbox = models.BooleanField(default=False)
```
to:
```python
    is_triage = models.BooleanField(default=False)
```

- [ ] **Step 2: Create the rename migration**

Create `tuckit/core/migrations/0005_rename_area_is_inbox_is_triage.py`:
```python
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_alter_workspace_org_delete_membership"),
    ]

    operations = [
        migrations.RenameField(
            model_name="area",
            old_name="is_inbox",
            new_name="is_triage",
        ),
    ]
```

- [ ] **Step 3: Verify Django sees no further model changes**

Run: `uv run python manage.py makemigrations --check --dry-run`
Expected: `No changes detected` (the RenameField covers the model edit).

- [ ] **Step 4: Rename the service symbols in `areas.py`**

In `tuckit/core/services/areas.py`:
- Line 7: `INBOX_NAME = "Inbox"` → `TRIAGE_NAME = "Triage"`
- Line 35: `def get_or_create_inbox(workspace: Workspace) -> Area:` → `def get_or_create_triage(workspace: Workspace) -> Area:`
- Lines 36-45, replace the body's `inbox`/`is_inbox`/`INBOX_NAME` usages so the function reads:
```python
def get_or_create_triage(workspace: Workspace) -> Area:
    triage = Area.objects.filter(workspace=workspace, is_triage=True).first()
    if triage is not None:
        return triage
    first = Area.objects.filter(workspace=workspace).order_by("rank").first()
    rank = rank_for(Area, {"workspace": workspace}, before=first)
    return Area.objects.create(
        workspace=workspace,
        name=TRIAGE_NAME,
        slug=_unique_slug(workspace, TRIAGE_NAME),
        is_triage=True,
        rank=rank,
    )
```

- [ ] **Step 5: Update the service callers**

- `tuckit/core/services/orgs.py`:
  - Line 2: `from tuckit.core.services.areas import create_area, get_or_create_inbox` → `... import create_area, get_or_create_triage`
  - Line 43: `get_or_create_inbox(ws)` → `get_or_create_triage(ws)`
- `tuckit/core/services/state.py`:
  - Line 118: `inbox = Area.objects.filter(workspace=workspace, is_inbox=True).first()` → `triage = Area.objects.filter(workspace=workspace, is_triage=True).first()`
  - Line 119: `if inbox is not None:` → `if triage is not None:`
  - Line 120: `for s in Slice.objects.filter(area=inbox, ...)` → `for s in Slice.objects.filter(area=triage, ...)` (leave `reason="inbox_stale"` for now — renamed in Task 2)
- `tuckit/web/context_processors.py`:
  - Line 13: `return {"areas": [a for a in list_areas(ws) if not a.is_inbox]}` → `... if not a.is_triage]}`
  - Line 24: `inbox = Area.objects.filter(workspace=ws, is_inbox=True).first()` → `triage = Area.objects.filter(workspace=ws, is_triage=True).first()`
  - Line 25: `n = Slice.objects.filter(area=inbox)...if inbox else 0` → `n = Slice.objects.filter(area=triage)...if triage else 0` (leave function name `inbox_count` and key for Task 2)
- `tuckit/web/views/capture.py`:
  - Line 5: `from tuckit.core.services.areas import get_or_create_inbox, create_area, list_areas` → `... import get_or_create_triage, create_area, list_areas`
  - Line 13: `inbox = get_or_create_inbox(ws)` → `triage = get_or_create_triage(ws)`; line 14 `create_slice(inbox, ...)` → `create_slice(triage, ...)`
  - Line 23: `inbox_area = get_or_create_inbox(ws)` → `triage_area = get_or_create_triage(ws)`; line 25 `list_slices(inbox_area...)` → `list_slices(triage_area...)`
  - Line 26: `if not a.is_inbox` → `if not a.is_triage`

- [ ] **Step 6: Run the suite to see the test failures the rename introduces**

Run: `uv run pytest -q`
Expected: FAIL — tests still importing `get_or_create_inbox` / asserting `is_inbox` error (ImportError / AttributeError). This confirms the tests exercise the renamed surface.

- [ ] **Step 7: Update the tests to the new symbols**

Apply these exact replacements (string-level, all occurrences in each file):
- `get_or_create_inbox` → `get_or_create_triage` in: `tests/test_services_areas.py` (lines 4,46,49,50,61), `tests/test_services_state.py` (6,101,136), `tests/test_bootstrap.py` (30), `tests/web/test_home.py` (6), `tests/web/test_shell.py` (23), `tests/web/test_capture_inbox.py` (2,11,17,24,39,58,70,72,79,81,89)
- `is_inbox` → `is_triage` in: `tests/test_services_orgs.py` (24,25), `tests/test_services_accounts.py` (19,20), `tests/test_services_areas.py` (52,53), `tests/test_bootstrap.py` (14,32), `tests/web/test_capture_inbox.py` (34,85), `tests/web/test_cross_workspace_access.py` (16)
- Rename the test function names that embed the old term (bodies already covered above):
  - `tests/test_services_areas.py:46` `test_get_or_create_inbox_is_idempotent_and_single` → `test_get_or_create_triage_is_idempotent_and_single`
  - `tests/test_services_areas.py:57` `test_inbox_sorts_before_existing_areas` → `test_triage_sorts_before_existing_areas`

Note: `tests/test_services_slices.py:109` uses `create_area(ws, "Inbox")` — that is a plain local fixture area, NOT the triage helper. Leave it unchanged.

- [ ] **Step 8: Run the suite green**

Run: `uv run pytest -q`
Expected: PASS (215 passed).

- [ ] **Step 9: Commit**

```bash
git add tuckit/core/models/domain.py tuckit/core/migrations/0005_rename_area_is_inbox_is_triage.py \
  tuckit/core/services/areas.py tuckit/core/services/orgs.py tuckit/core/services/state.py \
  tuckit/web/context_processors.py tuckit/web/views/capture.py tests/
git commit -m "refactor(core): rename Area.is_inbox→is_triage and inbox service symbols→triage"
```

---

## Task 2: User-facing rename — URLs, view, templates, strings, count

**Files:**
- Modify: `tuckit/web/urls.py:19,28`, `tuckit/web/views/capture.py:21`, `tuckit/settings.py:64`, `tuckit/web/context_processors.py:16-26`, `tuckit/core/services/state.py:121`, `tuckit/web/templatetags/web_extras.py:33-34`, `tuckit/web/templates/web/partials/_sidebar.html:7-9`, `tuckit/web/static/web/app.css:257-258,635,641`
- Rename: `tuckit/web/templates/web/inbox.html→triage.html`, `partials/_inbox_row.html→partials/_triage_row.html`, `partials/_inbox_count.html→partials/_triage_count.html`
- Rename test: `tests/web/test_capture_inbox.py→tests/web/test_capture_triage.py`; modify `tests/web/test_integration.py:11`, `tests/web/test_home.py:23`

**Interfaces:**
- Consumes: `get_or_create_triage`, `is_triage` (Task 1).
- Produces:
  - URL names `web:triage` (GET `/triage/`, the list page) and `web:slice_triage` (POST `/slices/<id>/triage`, the triage action)
  - Context key `triage_count` (was `inbox_count`); context processor `tuckit.web.context_processors.triage_count`
  - View `capture.triage_list(request)`
  - Templates `triage.html`, `partials/_triage_row.html`, `partials/_triage_count.html`
  - DOM ids `triage-list`, `triage-count`; CSS class `triage-row`
  - `attention_items` reason string `"triage_stale"` (was `"inbox_stale"`)

- [ ] **Step 1: Rename the template files**

```bash
git mv tuckit/web/templates/web/inbox.html tuckit/web/templates/web/triage.html
git mv tuckit/web/templates/web/partials/_inbox_row.html tuckit/web/templates/web/partials/_triage_row.html
git mv tuckit/web/templates/web/partials/_inbox_count.html tuckit/web/templates/web/partials/_triage_count.html
```

- [ ] **Step 2: Rewrite `triage.html`**

Replace the contents of `tuckit/web/templates/web/triage.html` with (note `#triage-list` is now the always-present panel container, ready for Task 4's live insert):
```html
{% extends "web/base.html" %}
{% block main %}
  <div class="topbar">
    <h1 class="area-title">Triage</h1>
  </div>
  <section class="group">
    <div class="panel" id="triage-list">
      {% for slice in slices %}{% include "web/partials/_triage_row.html" %}{% endfor %}
      {% if not slices %}<div class="empty muted" id="triage-empty">Triage clean</div>{% endif %}
    </div>
  </section>
{% endblock %}
```

- [ ] **Step 3: Update `_triage_row.html` (class + action url)**

In `tuckit/web/templates/web/partials/_triage_row.html`:
- Line 1: `<form class="inbox-row" hx-post="{% url 'web:triage' slice.id %}"` → `<form class="triage-row" hx-post="{% url 'web:slice_triage' slice.id %}"`
- Line 2: `hx-target="closest .inbox-row"` → `hx-target="closest .triage-row"`

- [ ] **Step 4: Update `_triage_count.html`**

Replace contents of `tuckit/web/templates/web/partials/_triage_count.html` with:
```html
<span class="nav-count" id="triage-count"{% if oob %} hx-swap-oob="true"{% endif %}>{% if triage_count %}{{ triage_count }}{% endif %}</span>
```

- [ ] **Step 5: Update URLs (rename page + resolve name collision)**

In `tuckit/web/urls.py`:
- Line 19: `path("inbox/", capture.inbox, name="inbox"),` → `path("triage/", capture.triage_list, name="triage"),`
- Line 28: `path("slices/<int:slice_id>/triage", capture.triage, name="triage"),` → `path("slices/<int:slice_id>/triage", capture.triage, name="slice_triage"),`

- [ ] **Step 6: Rename the view function and its template refs**

In `tuckit/web/views/capture.py`:
- Line 21: `def inbox(request):` → `def triage_list(request):`
- Line 24: `return render(request, "web/inbox.html", {` → `return render(request, "web/triage.html", {`
- Line 18 (in `capture()`): `return render(request, "web/partials/_inbox_count.html", {"oob": True})` → `return render(request, "web/partials/_triage_count.html", {"oob": True})` (this line is replaced wholesale in Task 4; updating it here keeps the suite green in between)

- [ ] **Step 7: Rename the context processor + settings**

In `tuckit/web/context_processors.py`:
- Line 16: `def inbox_count(request):` → `def triage_count(request):`
- Line 26: `return {"inbox_count": n}` → `return {"triage_count": n}`
- Update the docstring (lines 17-18) wording `inbox`→`triage`.

In `tuckit/settings.py`, line 64:
```python
                "tuckit.web.context_processors.inbox_count",
```
→
```python
                "tuckit.web.context_processors.triage_count",
```

- [ ] **Step 8: Rename the attention reason string**

In `tuckit/core/services/state.py`, line 121:
```python
            items.append({"slice": s, "reason": "inbox_stale", "days": (now - s.updated_at).days})
```
→
```python
            items.append({"slice": s, "reason": "triage_stale", "days": (now - s.updated_at).days})
```

In `tuckit/web/templatetags/web_extras.py`:
- Line 33: `if item.get("reason") == "inbox_stale":` → `if item.get("reason") == "triage_stale":`
- Line 34: `return f"인박스 {days}일째"` → `return f"Triage {days}일째"`

- [ ] **Step 9: Patch the sidebar's inbox references (structure untouched — Task 3 restructures)**

In `tuckit/web/templates/web/partials/_sidebar.html`, lines 7-9:
```html
  <a class="nav{% if request.resolver_match.url_name == 'inbox' %} nav--active{% endif %}"
     href="{% url 'web:inbox' %}">{% icon "inbox" %}<span class="nav-label">인박스</span>
     {% include "web/partials/_inbox_count.html" %}</a>
```
→
```html
  <a class="nav{% if request.resolver_match.url_name == 'triage' %} nav--active{% endif %}"
     href="{% url 'web:triage' %}">{% icon "inbox" %}<span class="nav-label">Triage</span>
     {% include "web/partials/_triage_count.html" %}</a>
```
(Icon key stays `"inbox"` until Task 3.)

- [ ] **Step 10: Rename the CSS class**

In `tuckit/web/static/web/app.css`:
- Line 257 comment `/* Inbox row — ... */` → `/* Triage row — ... */`
- Line 258: `.inbox-row {` → `.triage-row {`
- Line 635: `.panel .inbox-row {` → `.panel .triage-row {`
- Line 641: `.panel .inbox-row:last-child { border-bottom: 0; }` → `.panel .triage-row:last-child { border-bottom: 0; }`

- [ ] **Step 11: Rename the test file and update its URLs/ids/strings**

```bash
git mv tests/web/test_capture_inbox.py tests/web/test_capture_triage.py
```
In `tests/web/test_capture_triage.py`:
- `"/inbox/"` → `"/triage/"` (lines 19, 73)
- `f"/slices/{s.id}/triage"` — path unchanged (URL path is still `/slices/<id>/triage`); no edit needed.
- Line 43: `assert 'id="inbox-count"' in body` → `assert 'id="triage-count"' in body`
- Rename functions: `test_capture_lands_in_inbox_as_idea`→`test_capture_lands_in_triage_as_idea`, `test_inbox_lists_captures`→`test_triage_lists_captures`, `test_triage_moves_out_of_inbox`→`test_triage_moves_out`, `test_capture_returns_oob_inbox_count`→`test_capture_returns_oob_triage_count`, `test_inbox_row_has_no_manual_caret_and_area_placeholder`→`test_triage_row_has_no_manual_caret_and_area_placeholder`
- Line 85 (`test_triage_status_only_keeps_area`): `assert s.area.is_inbox and ...` was already `is_triage` after Task 1 — confirm it reads `assert s.area.is_triage and s.status == "planned"`.

In `tests/web/test_integration.py`, line 11: `"/inbox/"` → `"/triage/"`.

In `tests/web/test_home.py`:
- Line 17: `test_home_sidebar_excludes_inbox_area` → `test_home_sidebar_excludes_triage_area`
- Line 23: `assert "/areas/inbox/" not in body` → `assert "/areas/triage/" not in body` (the triage area slug is now `triage`)

- [ ] **Step 12: Run the suite green**

Run: `uv run pytest -q`
Expected: PASS (215 passed).

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "refactor(web): rename inbox route/view/templates/strings to triage; fix triage url-name collision"
```

---

## Task 3: Sidebar restructure (grouped nav + prominent Capture)

**Files:**
- Modify: `tuckit/web/templates/web/partials/_sidebar.html` (full rewrite), `tuckit/web/static/web/app.css` (append group/capture styles), `tuckit/web/templatetags/web_extras.py:18` (icon key `inbox`→`triage`)
- Test: `tests/web/test_shell.py` (add a grouped-structure assertion)

**Interfaces:**
- Consumes: url names `web:home`, `web:triage`, `web:area_create`, `web:settings`; partial `_triage_count.html`; `_area_nav.html`; context `areas`, `triage_count`.
- Produces: sidebar with CSS hooks `.nav-group`, `.nav-sep`, `.nav-spacer`, `.capture-btn`, `.nav-kbd`; icon key `"triage"`.

- [ ] **Step 1: Write a failing test for the grouped structure + English labels**

Add to `tests/web/test_shell.py`:
```python
@pytest.mark.django_db
def test_sidebar_grouped_with_english_labels_and_capture(client_local, workspace):
    body = client_local.get("/").content.decode()
    assert 'class="nav-group"' in body        # grouped, not a flat list
    assert 'class="capture-btn"' in body       # Capture promoted to its own button
    assert ">Home<" in body and ">Triage<" in body and ">Settings<" in body
    assert 'href="/triage/"' in body
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/web/test_shell.py::test_sidebar_grouped_with_english_labels_and_capture -v`
Expected: FAIL (`nav-group`/`capture-btn` not present).

- [ ] **Step 3: Rename the icon key**

In `tuckit/web/templatetags/web_extras.py`, line 18:
```python
    "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.5 2 12v7h20v-7l-3.5-6.5H5.5Z"/>',
```
→
```python
    "triage": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.5 2 12v7h20v-7l-3.5-6.5H5.5Z"/>',
```

- [ ] **Step 4: Rewrite the sidebar**

Replace the contents of `tuckit/web/templates/web/partials/_sidebar.html` with:
```html
{% load web_extras %}
<aside class="sidebar">
  <div class="brand">tuck-it</div>
  {% include "web/partials/_workspace_switcher.html" %}

  <nav class="nav-group">
    <a class="nav{% if request.resolver_match.url_name == 'home' %} nav--active{% endif %}"
       href="{% url 'web:home' %}">{% icon "home" %}<span class="nav-label">Home</span></a>
    <a class="nav{% if request.resolver_match.url_name == 'triage' %} nav--active{% endif %}"
       href="{% url 'web:triage' %}">{% icon "triage" %}<span class="nav-label">Triage</span>
       {% include "web/partials/_triage_count.html" %}</a>
  </nav>

  <div class="nav-sep"></div>

  <div class="section">Areas</div>
  {% include "web/partials/_area_nav.html" %}
  <form class="area-add" hx-post="{% url 'web:area_create' %}" hx-swap="none"
        hx-on::after-request="this.reset()">
    <input name="name" class="area-add-input" placeholder="＋ Area">
  </form>

  <div class="nav-spacer"></div>

  <a class="nav muted{% if request.resolver_match.url_name == 'settings' %} nav--active{% endif %}"
     href="{% url 'web:settings' %}">{% icon "settings" %}<span class="nav-label">Settings</span></a>
  <button class="nav theme-toggle" type="button"
          x-data="{theme: document.documentElement.dataset.theme || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')}"
          x-on:click="theme = theme === 'dark' ? 'light' : 'dark'; document.documentElement.dataset.theme = theme; localStorage.setItem('theme', theme)">
    <span x-text="theme === 'dark' ? 'Light mode' : 'Dark mode'">Dark mode</span>
  </button>

  <button class="nav capture-btn" type="button"
          x-on:click="cap = true; $nextTick(() => $refs.captureInput && $refs.captureInput.focus())">
    {% icon "plus" %}<span class="nav-label">Capture</span><kbd class="nav-kbd">C</kbd></button>
</aside>
```

- [ ] **Step 5: Append sidebar styles**

Append to `tuckit/web/static/web/app.css`:
```css
/* --- Sidebar grouping (nav redesign, Phase 1) --- */
.nav-group { display: flex; flex-direction: column; gap: 4px; }
.nav-sep { height: 1px; background: var(--border); margin: 10px 4px; }
.nav-spacer { flex: 1 1 auto; }

.capture-btn {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  text-align: left;
  font: inherit;
  cursor: pointer;
  width: 100%;
  margin-top: 6px;
}
.capture-btn:hover { border-color: var(--accent); }
.capture-btn .icon { stroke: var(--accent); }

.nav-kbd {
  font-size: 11px;
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 0 5px;
  font-variant-numeric: tabular-nums;
}
```

- [ ] **Step 6: Run the new test + full suite**

Run: `uv run pytest tests/web/test_shell.py -v && uv run pytest -q`
Expected: new test PASS; full suite PASS (216 passed).

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/templates/web/partials/_sidebar.html tuckit/web/static/web/app.css \
  tuckit/web/templatetags/web_extras.py tests/web/test_shell.py
git commit -m "feat(web): restructure sidebar into groups with prominent Capture button"
```

---

## Task 4: Capture UX full-set (toast + count + live row)

**Files:**
- Modify: `tuckit/web/views/capture.py` (`capture()` returns bundled OOB), `tuckit/web/templates/web/base.html` (toast region), `tuckit/web/static/web/app.css` (toast styles)
- Create: `tuckit/web/templates/web/partials/_capture_result.html`
- Test: `tests/web/test_capture_triage.py`

**Interfaces:**
- Consumes: `get_or_create_triage`, `list_areas`, `create_slice`, `_triage_count.html`, `_triage_row.html`, ids `triage-list`/`triage-empty` (Tasks 1-2).
- Produces: capture response bundling OOB swaps `#toast`, `#triage-count`, an `afterbegin:#triage-list` row, and `delete:#triage-empty`.

- [ ] **Step 1: Write failing tests for the three feedback channels**

In `tests/web/test_capture_triage.py`, replace `test_capture_returns_oob_triage_count` with:
```python
@pytest.mark.django_db
def test_capture_returns_toast_count_and_row(client_local, workspace):
    # No full-page reload: capture returns OOB swaps for toast, count, and the new row.
    get_or_create_triage(workspace)
    resp = client_local.post("/capture", {"title": "빠른 기록"}, HTTP_HX_REQUEST="true")
    assert resp.status_code == 200
    body = resp.content.decode()
    # count badge
    assert 'id="triage-count"' in body
    assert ">1<" in body
    # toast
    assert 'id="toast"' in body
    assert "Captured" in body
    # live row prepended into the triage list (lands only if that page is open)
    assert "afterbegin:#triage-list" in body
    assert "빠른 기록" in body
    # empty-state placeholder gets removed
    assert 'id="triage-empty"' in body
    assert 'hx-swap-oob="delete"' in body
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/web/test_capture_triage.py::test_capture_returns_toast_count_and_row -v`
Expected: FAIL (`id="toast"` / `afterbegin:#triage-list` not present — capture still returns only the count).

- [ ] **Step 3: Create the bundled OOB result partial**

Create `tuckit/web/templates/web/partials/_capture_result.html`:
```html
{# Toast — always shown, auto-dismisses. Replaces the persistent #toast region. #}
<div id="toast" hx-swap-oob="true" class="toast" x-data="{show:true}"
     x-init="setTimeout(() => show=false, 1800)" x-show="show" x-transition x-cloak>Captured ✓</div>

{# Count badge — always refreshed (context processor supplies triage_count). #}
{% include "web/partials/_triage_count.html" with oob=True %}

{# New row — prepended only if the Triage list is on-screen; ignored elsewhere. #}
<template hx-swap-oob="afterbegin:#triage-list">
  {% include "web/partials/_triage_row.html" %}
</template>

{# Remove the "Triage clean" placeholder if it's on the page. #}
<div id="triage-empty" hx-swap-oob="delete"></div>
```

- [ ] **Step 4: Rewrite `capture()` to render the bundle**

In `tuckit/web/views/capture.py`, replace the `capture` view (lines 11-18) with:
```python
def capture(request):
    ws = get_current_workspace(request)
    triage = get_or_create_triage(ws)
    slice_ = create_slice(triage, request.POST["title"], status="idea", source="human")
    # Bundle out-of-band swaps: a confirmation toast + live count + (if the Triage
    # page is open) the new row prepended into #triage-list. htmx ignores OOB
    # targets that aren't on the current page, so one response fits every page.
    return render(request, "web/partials/_capture_result.html", {
        "slice": slice_,
        "areas": [a for a in list_areas(ws) if not a.is_triage],
        "statuses": ["idea", "planned", "building", "shipped"],
    })
```

- [ ] **Step 5: Add the toast region to `base.html`**

In `tuckit/web/templates/web/base.html`, add a persistent toast anchor just before the capture-modal include (line 39). Change:
```html
  <div id="panel"></div>
  {% include "web/partials/_capture_modal.html" %}
```
to:
```html
  <div id="panel"></div>
  <div id="toast" class="toast" x-cloak></div>
  {% include "web/partials/_capture_modal.html" %}
```

- [ ] **Step 6: Add toast styles**

Append to `tuckit/web/static/web/app.css`:
```css
/* --- Capture confirmation toast (nav redesign, Phase 1) --- */
.toast {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 14px;
  color: var(--text);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
  z-index: 50;
}
.toast:empty { display: none; }
```

- [ ] **Step 7: Run the new test + full suite**

Run: `uv run pytest tests/web/test_capture_triage.py -v && uv run pytest -q`
Expected: all PASS (216 passed).

- [ ] **Step 8: Commit**

```bash
git add tuckit/web/views/capture.py tuckit/web/templates/web/partials/_capture_result.html \
  tuckit/web/templates/web/base.html tuckit/web/static/web/app.css tests/web/test_capture_triage.py
git commit -m "feat(web): capture returns toast + live count + row OOB (no refresh needed)"
```

- [ ] **Step 9: Verify the live behavior in a browser (client-side, not covered by unit tests)**

The unit tests assert the response *markup*; the DOM insertion is client-side. Use the `run` skill (or `uvicorn tuckit.asgi:app`) and confirm manually:
1. Open `/triage/` on an empty workspace → "Triage clean".
2. Press `C`, type a title, Enter → toast appears, sidebar count increments, the new row appears at the top of the list and "Triage clean" disappears — **no page reload**.
3. Open `/` (Home), press `C`, capture → toast + count only (no error; the row OOB is silently ignored).

---

## Self-Review

**Spec coverage (Phase 1 = spec §9 parts A + B + E):**
- **A. inbox→triage rename** — Task 1 (field + service symbols + migration) and Task 2 (URLs/view/templates/strings/count/CSS/tests). Covers every reference from spec §8A including the `triage` URL-name collision fix.
- **B. sidebar restructure** — Task 3 (grouped nav, English labels, prominent Capture, icon rename). State-lens items intentionally deferred to Phase 2 per Global Constraints.
- **E. capture UX full-set** — Task 4 (toast + count + live row OOB, empty-state delete). Matches spec §7.

**Placeholder scan:** No TBD/TODO; every code step shows complete code or exact old→new edits. Client-side-only behavior is explicitly routed to a manual verify step (Task 4 Step 9) rather than left as an untested assertion.

**Type/name consistency:** `get_or_create_triage`, `is_triage`, `TRIAGE_NAME`, url names `web:triage`/`web:slice_triage`, context key `triage_count`, ids `triage-list`/`triage-count`/`triage-empty`, class `triage-row`, icon key `triage` — used consistently across Tasks 1→4. Task 4 consumes only names produced by Tasks 1-2.

**Out-of-scope confirmed:** `tests/test_services_slices.py:109` `create_area(ws, "Inbox")` left as-is (local fixture, not the triage helper). Home page Korean group labels and capture-modal placeholder untouched (Phase 2 / not in scope).
