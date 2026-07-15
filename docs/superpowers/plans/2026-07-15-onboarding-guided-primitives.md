# Onboarding: learn the primitives by hand — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the auto-created throwaway `Default` area and the agent-first onboarding checklist with a Linear-style, four-step "Get started" checklist that walks a new user through creating their **own** first Area → Slice → Bite (each with a plain-language concept explanation) and then connecting their agent.

**Architecture:** Django + server-rendered templates (HTMX/Alpine already vendored). Onboarding progress is derived from real data (no new DB flag beyond the existing `Workspace.onboarding_dismissed`). Three tiny POST endpoints create the first Area/Slice/Bite via the existing service layer and redirect back to Home; the checklist partial renders concept cards with inline forms and sequential gating.

**Tech Stack:** Python 3.13, Django, pytest (`uv run pytest`), existing design-token CSS.

## Global Constraints

- **No new persisted onboarding field.** Only `Workspace.onboarding_dismissed` (already exists) may store state; everything else is derived by query.
- **CSS: `var(--token)` only** — no literal hex, no hardcoded radius (surfaces `--radius`, controls `--radius-small`). New checklist styles go in `app.css`.
- **Copy is English** (matches existing `welcome.html` / `_get_started.html`).
- **Public/private boundary intact** — generic product onboarding only; **no billing/pricing copy**.
- **Do not change** MCP/API behavior, tenant isolation, activity/actor threading, or the **invite-flow redirects** (`accounts.py:41,48` stay `web:home`).
- **`docs/superpowers/` stays untracked** — do not `git add` this plan or the spec.
- Run the full suite with `uv run pytest` from the `tuckit/` repo root. Commit after every task.

---

### Task 1: Remove the auto-`Default` area

A fresh workspace must contain only `Triage`. The first non-triage Area becomes the one the user creates in the checklist.

**Files:**
- Modify: `tuckit/tuckit/core/services/orgs.py:47-57` (`create_workspace`)
- Test: `tests/test_services_orgs.py:22-30`, `tests/test_services_orgs.py:155-165`
- Test: `tests/test_services_accounts.py:10-20`
- Test: `tests/test_bootstrap.py:7-16`

**Interfaces:**
- Consumes: existing `create_workspace(org, name, slug=None) -> Workspace`, `get_or_create_triage(workspace)`.
- Produces: `create_workspace` now creates **only** `Triage` (one Area, `is_triage=True`).

- [ ] **Step 1: Update the failing tests to assert the new behavior**

In `tests/test_services_orgs.py`, rename and rewrite the workspace assertion (was `test_create_workspace_sets_up_inbox_and_default`):

```python
@pytest.mark.django_db
def test_create_workspace_sets_up_inbox_only(org_with_owner):
    org, _ = org_with_owner
    ws = create_workspace(org, "Board")
    assert ws.org == org
    assert Area.objects.filter(workspace=ws, is_triage=True).count() == 1
    assert Area.objects.filter(workspace=ws, is_triage=False).count() == 0
```

In the same file, in `test_create_org_makes_org_owner_and_first_workspace`, replace the `slug="default"` assertion line with:

```python
    assert Area.objects.filter(workspace=ws, is_triage=False).count() == 0
```

In `tests/test_services_accounts.py`, replace the `slug="default"` assertion line with:

```python
    assert Area.objects.filter(workspace=ws, is_triage=False).count() == 0
```

In `tests/test_bootstrap.py::test_bootstrap_creates_full_local_setup`, replace the `slug="default"` assertion line with:

```python
    assert Area.objects.filter(workspace=workspace, is_triage=False).count() == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_services_orgs.py tests/test_services_accounts.py tests/test_bootstrap.py -q`
Expected: FAIL — the `default` area still exists (asserted count 0 but is 1).

- [ ] **Step 3: Remove the auto-`Default` creation**

In `tuckit/tuckit/core/services/orgs.py`, in `create_workspace`, delete the `create_area(ws, "Default")` line (currently line 56):

```python
def create_workspace(org: Org, name: str, slug: str | None = None) -> Workspace:
    name = " ".join((name or "").split())
    if not name:
        raise InvalidValue("워크스페이스 이름을 입력하세요")
    if Workspace.objects.filter(org=org, name__iexact=name).exists():
        raise InvalidValue(f"이미 같은 이름의 워크스페이스가 있습니다: {name}")
    slug = validate_slug(slug, kind="workspace") if slug else _unique_ws_slug(org, name)
    ws = Workspace.objects.create(org=org, name=name, slug=slug)
    get_or_create_triage(ws)
    return ws
```

(`create_area` is still imported and used elsewhere — leave the import.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_services_orgs.py tests/test_services_accounts.py tests/test_bootstrap.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tuckit/core/services/orgs.py tests/test_services_orgs.py tests/test_services_accounts.py tests/test_bootstrap.py
git commit -m "feat: stop auto-creating a Default area at workspace creation"
```

---

### Task 2: Redefine `OnboardingState` to four derived signals

Progress becomes: has a non-triage Area, has a Slice, has a Bite, connected (has a token) — in that order.

**Files:**
- Modify: `tuckit/tuckit/core/services/onboarding.py` (whole file)
- Test: `tests/test_services_onboarding.py` (whole file)

**Interfaces:**
- Produces: `OnboardingState(has_area: bool, has_slice: bool, has_bite: bool, connected: bool)` with properties `completed: int`, `done: bool`, and `current: int` (1=Area, 2=Slice, 3=Bite, 4=Connect, 0=all done). `onboarding_state(workspace) -> OnboardingState`.
- Consumers updated in Task 4 (Home template) — the Home view (`pages.py:19-66`) needs **no change** (it only reads `ob.done`).

- [ ] **Step 1: Rewrite the failing tests**

Replace the entire body of `tests/test_services_onboarding.py`:

```python
import pytest

from tuckit.core.models import ApiToken, Area
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice
from tuckit.core.services.bites import create_bite
from tuckit.core.services.onboarding import onboarding_state


@pytest.mark.django_db
def test_fresh_workspace_all_incomplete(workspace):
    st = onboarding_state(workspace)
    assert (st.has_area, st.has_slice, st.has_bite, st.connected) == (False, False, False, False)
    assert st.done is False and st.completed == 0 and st.current == 1


@pytest.mark.django_db
def test_area_marks_has_area(workspace):
    create_area(workspace, "Backend")
    st = onboarding_state(workspace)
    assert st.has_area is True and st.current == 2


@pytest.mark.django_db
def test_slice_marks_has_slice(workspace):
    area = create_area(workspace, "Backend")
    create_slice(area, "Retry webhooks", status="idea")
    st = onboarding_state(workspace)
    assert st.has_area is True and st.has_slice is True and st.current == 3


@pytest.mark.django_db
def test_bite_marks_has_bite(workspace):
    area = create_area(workspace, "Backend")
    sl = create_slice(area, "Retry webhooks", status="idea")
    create_bite(sl, "Add backoff")
    st = onboarding_state(workspace)
    assert st.has_bite is True and st.current == 4


@pytest.mark.django_db
def test_token_marks_connected(workspace):
    ApiToken.objects.create(workspace=workspace, name="a", token_hash="x")
    st = onboarding_state(workspace)
    assert st.connected is True


@pytest.mark.django_db
def test_all_done(workspace):
    area = create_area(workspace, "Backend")
    sl = create_slice(area, "Retry webhooks", status="planned")
    create_bite(sl, "Add backoff")
    ApiToken.objects.create(workspace=workspace, name="a", token_hash="x")
    st = onboarding_state(workspace)
    assert st.done is True and st.completed == 4 and st.current == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_services_onboarding.py -q`
Expected: FAIL — `OnboardingState` has no `has_area` (still `connected/captured/triaged`).

- [ ] **Step 3: Rewrite the service**

Replace the entire contents of `tuckit/tuckit/core/services/onboarding.py`:

```python
from dataclasses import dataclass

from tuckit.core.models import ApiToken, Area, Bite, Slice, Workspace


@dataclass(frozen=True)
class OnboardingState:
    has_area: bool
    has_slice: bool
    has_bite: bool
    connected: bool

    @property
    def completed(self) -> int:
        return sum((self.has_area, self.has_slice, self.has_bite, self.connected))

    @property
    def done(self) -> bool:
        return self.completed == 4

    @property
    def current(self) -> int:
        """1=Area, 2=Slice, 3=Bite, 4=Connect, 0=all done — the first open step."""
        if not self.has_area:
            return 1
        if not self.has_slice:
            return 2
        if not self.has_bite:
            return 3
        if not self.connected:
            return 4
        return 0


def onboarding_state(workspace: Workspace) -> OnboardingState:
    return OnboardingState(
        has_area=Area.objects.filter(workspace=workspace, is_triage=False).exists(),
        has_slice=Slice.objects.filter(area__workspace=workspace).exists(),
        has_bite=Bite.objects.filter(slice__area__workspace=workspace).exists(),
        connected=ApiToken.objects.filter(workspace=workspace).exists(),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_services_onboarding.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tuckit/core/services/onboarding.py tests/test_services_onboarding.py
git commit -m "feat: redefine onboarding state as area/slice/bite/connected"
```

---

### Task 3: Onboarding creation endpoints

Three POST endpoints that create the first Area/Slice/Bite via services and redirect back to Home. Kept separate from the HTMX-partial create views so onboarding is self-contained and testable.

**Files:**
- Create: `tuckit/tuckit/web/views/onboarding.py`
- Modify: `tuckit/tuckit/web/urls.py` (imports at line ~7; new routes near line 61)
- Test: `tests/web/test_onboarding_create.py`

**Interfaces:**
- Consumes: `get_current_workspace(request)`, `create_area(ws, name)`, `create_slice(area, title, *, status, source)`, `create_bite(slice_, title, *, source)`.
- Produces URL names: `web:onboarding_area`, `web:onboarding_slice`, `web:onboarding_bite` (all under the `<org>/<ws>/` prefix `P`, POST-only, redirect to `web:home`).

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_onboarding_create.py`:

```python
import pytest

from tuckit.core.models import Area, Bite, Slice
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice


@pytest.mark.django_db
def test_create_first_area(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/area", {"name": "Backend"})
    assert r.status_code == 302
    assert Area.objects.filter(workspace=workspace, is_triage=False, name="Backend").exists()


@pytest.mark.django_db
def test_create_first_slice_targets_the_area(client_local, workspace):
    create_area(workspace, "Backend")
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/slice", {"title": "Retry webhooks"})
    assert r.status_code == 302
    assert Slice.objects.filter(area__workspace=workspace, title="Retry webhooks").exists()


@pytest.mark.django_db
def test_create_first_bite_targets_the_slice(client_local, workspace):
    area = create_area(workspace, "Backend")
    create_slice(area, "Retry webhooks", status="idea")
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/bite", {"title": "Add backoff"})
    assert r.status_code == 302
    assert Bite.objects.filter(slice__area__workspace=workspace, title="Add backoff").exists()


@pytest.mark.django_db
def test_slice_without_area_is_noop(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/slice", {"title": "Orphan"})
    assert r.status_code == 302
    assert not Slice.objects.filter(area__workspace=workspace).exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_onboarding_create.py -q`
Expected: FAIL — routes `onboarding/area` etc. do not resolve (404, not 302).

- [ ] **Step 3: Create the views**

Create `tuckit/tuckit/web/views/onboarding.py`:

```python
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from tuckit.core.models import Area, Slice
from tuckit.core.services.areas import create_area
from tuckit.core.services.bites import create_bite
from tuckit.core.services.slices import create_slice
from tuckit.web.auth import get_current_workspace


def _home(ws):
    return redirect("web:home", org_slug=ws.org.slug, ws_slug=ws.slug)


@require_POST
def create_first_area(request):
    ws = get_current_workspace(request)
    if ws is None:
        return redirect("web:root")
    name = (request.POST.get("name") or "").strip()
    if name:
        create_area(ws, name)
    return _home(ws)


@require_POST
def create_first_slice(request):
    ws = get_current_workspace(request)
    if ws is None:
        return redirect("web:root")
    area = Area.objects.filter(workspace=ws, is_triage=False).order_by("-id").first()
    title = (request.POST.get("title") or "").strip()
    if area and title:
        create_slice(area, title, status="idea", source="human")
    return _home(ws)


@require_POST
def create_first_bite(request):
    ws = get_current_workspace(request)
    if ws is None:
        return redirect("web:root")
    slice_ = Slice.objects.filter(area__workspace=ws).order_by("-id").first()
    title = (request.POST.get("title") or "").strip()
    if slice_ and title:
        create_bite(slice_, title, source="human")
    return _home(ws)
```

- [ ] **Step 4: Wire the routes**

In `tuckit/tuckit/web/urls.py`, add `onboarding` to the views import group (near line 7, alongside `pages, slices, mutations, board, capture, ...`):

```python
    pages, slices, mutations, board, capture, health, workspaces, onboarding,
```

Then add three routes next to the existing dismiss route (line 61):

```python
    path(f"{P}onboarding/dismiss", pages.dismiss_onboarding, name="onboarding_dismiss"),
    path(f"{P}onboarding/area", onboarding.create_first_area, name="onboarding_area"),
    path(f"{P}onboarding/slice", onboarding.create_first_slice, name="onboarding_slice"),
    path(f"{P}onboarding/bite", onboarding.create_first_bite, name="onboarding_bite"),
```

(If `onboarding` cannot be added to the existing `from tuckit.web.views import (...)` group because of how it's written, add `from tuckit.web.views import onboarding` on its own line — verify the exact import statement in the file first.)

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_onboarding_create.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/views/onboarding.py tuckit/web/urls.py tests/web/test_onboarding_create.py
git commit -m "feat: add onboarding create endpoints for first area/slice/bite"
```

---

### Task 4: Redesign the "Get started" checklist (4 steps + concept cards)

Rewrite the checklist partial to four steps with expandable concept cards, inline creation forms, and sequential gating. Add styles in `app.css`.

**Files:**
- Modify: `tuckit/tuckit/web/templates/web/partials/_get_started.html` (whole file)
- Modify: `tuckit/tuckit/web/static/web/app.css` (append checklist styles)
- Test: `tests/web/test_get_started.py` (whole file)

**Interfaces:**
- Consumes: template context `onboarding` (the `OnboardingState` from Task 2, with `.has_area/.has_slice/.has_bite/.connected/.completed/.current`) and URL names from Task 3. Home view already supplies `onboarding` + `show_get_started` (`pages.py:61-62`) — no view change.
- Produces: no code interface; a rendered checklist.

- [ ] **Step 1: Rewrite the web tests**

Replace the entire contents of `tests/web/test_get_started.py`:

```python
import pytest

from tuckit.core.models import ApiToken
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice
from tuckit.core.services.bites import create_bite


@pytest.mark.django_db
def test_checklist_shows_four_steps_on_fresh_home(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    body = client_local.get(f"{p}/").content.decode()
    assert "Get started" in body
    assert "Create your first Area" in body
    assert "Add your first Slice" in body
    assert "Break it into Bites" in body
    assert "Connect your agent" in body


@pytest.mark.django_db
def test_fresh_home_gates_slice_step(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    body = client_local.get(f"{p}/").content.decode()
    # no Area yet → the Slice step shows the gate hint, not a create form
    assert "Create an Area first." in body


@pytest.mark.django_db
def test_slice_form_appears_after_area(client_local, workspace):
    create_area(workspace, "Backend")
    p = f"/{workspace.org.slug}/{workspace.slug}"
    body = client_local.get(f"{p}/").content.decode()
    assert "/onboarding/slice" in body
    assert "Create an Area first." not in body


@pytest.mark.django_db
def test_checklist_hidden_when_all_done(client_local, workspace):
    area = create_area(workspace, "Backend")
    sl = create_slice(area, "Retry webhooks", status="planned")
    create_bite(sl, "Add backoff")
    ApiToken.objects.create(workspace=workspace, name="a", token_hash="x")
    p = f"/{workspace.org.slug}/{workspace.slug}"
    body = client_local.get(f"{p}/").content.decode()
    assert "Get started" not in body


@pytest.mark.django_db
def test_dismiss_hides_checklist(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/dismiss")
    assert r.status_code in (200, 204, 302)
    workspace.refresh_from_db()
    assert workspace.onboarding_dismissed is True
    assert "Get started" not in client_local.get(f"{p}/").content.decode()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_get_started.py -q`
Expected: FAIL — the new step labels/gate copy are not in the old 3-step partial.

- [ ] **Step 3: Rewrite the checklist partial**

Replace the entire contents of `tuckit/tuckit/web/templates/web/partials/_get_started.html`:

```django
{% load web_extras %}
<section class="get-started" aria-label="Get started">
  <div class="gs-head">
    <div><h2 class="gs-title">Get started</h2>
      <p class="gs-sub">{{ onboarding.completed }} of 4 — build the structure by hand, then hand the work to your agent.</p></div>
    <form method="post" action="{% wurl 'web:onboarding_dismiss' %}">{% csrf_token %}
      <button class="gs-dismiss" type="submit">Dismiss</button></form>
  </div>
  <ul class="gs-list">

    <li class="gs-step {% if onboarding.has_area %}done{% endif %}">
      <details {% if onboarding.current == 1 %}open{% endif %}>
        <summary><span class="gs-box">✓</span><span class="gs-lbl">Create your first Area</span></summary>
        <div class="gs-card">
          <p class="gs-def"><b>Area</b> — a long-lived domain of responsibility. It never gets “done”; it’s a home for work, so nothing floats around unowned.</p>
          <p class="gs-eg">Examples: Backend, Marketing, Mobile. (<b>Triage</b> is the one built-in Area — the inbox for anything not yet sorted.)</p>
          {% if not onboarding.has_area %}
          <form class="gs-form" method="post" action="{% wurl 'web:onboarding_area' %}">{% csrf_token %}
            <input name="name" placeholder="e.g. Backend" maxlength="200" required>
            <button class="button button-primary" type="submit">+ Create Area</button>
          </form>
          {% endif %}
        </div>
      </details>
    </li>

    <li class="gs-step {% if onboarding.has_slice %}done{% endif %} {% if not onboarding.has_area %}gated{% endif %}">
      <details {% if onboarding.current == 2 %}open{% endif %}>
        <summary><span class="gs-box">✓</span><span class="gs-lbl">Add your first Slice</span></summary>
        <div class="gs-card">
          <p class="gs-def"><b>Slice</b> — one chunk of product work: an idea, feature, or fix. It moves idea → planned → building → shipped.</p>
          <p class="gs-eg">Examples: “Retry failed webhooks”, “Redesign the login screen”.</p>
          {% if onboarding.has_area and not onboarding.has_slice %}
          <form class="gs-form" method="post" action="{% wurl 'web:onboarding_slice' %}">{% csrf_token %}
            <input name="title" placeholder="e.g. Retry failed webhooks" maxlength="300" required>
            <button class="button button-primary" type="submit">+ Add Slice</button>
          </form>
          {% elif not onboarding.has_area %}
          <p class="gs-gate">Create an Area first.</p>
          {% endif %}
        </div>
      </details>
    </li>

    <li class="gs-step {% if onboarding.has_bite %}done{% endif %} {% if not onboarding.has_slice %}gated{% endif %}">
      <details {% if onboarding.current == 3 %}open{% endif %}>
        <summary><span class="gs-box">✓</span><span class="gs-lbl">Break it into Bites</span></summary>
        <div class="gs-card">
          <p class="gs-def"><b>Bite</b> — one implementation step of a Slice: the concrete to-dos (todo → doing → done). When every Bite is done, the Slice ships.</p>
          <p class="gs-eg">Under “Retry failed webhooks” → “Add exponential backoff”, “Cap retries at 5”.</p>
          {% if onboarding.has_slice and not onboarding.has_bite %}
          <form class="gs-form" method="post" action="{% wurl 'web:onboarding_bite' %}">{% csrf_token %}
            <input name="title" placeholder="e.g. Add exponential backoff" maxlength="300" required>
            <button class="button button-primary" type="submit">+ Add Bite</button>
          </form>
          {% elif not onboarding.has_slice %}
          <p class="gs-gate">Add a Slice first.</p>
          {% endif %}
        </div>
      </details>
    </li>

    <li class="gs-step {% if onboarding.connected %}done{% endif %}">
      <details {% if onboarding.current == 4 %}open{% endif %}>
        <summary><span class="gs-box">✓</span><span class="gs-lbl">Connect your agent</span></summary>
        <div class="gs-card">
          <p class="gs-def">You just built the structure by hand — so you <b>understand</b> it. From here your AI agent reads and writes these same Areas, Slices, and Bites over MCP. It does the work; nothing it does slips past you.</p>
          <a class="button button-primary" href="{% url 'web:welcome' %}?step=connect">Connect your agent →</a>
        </div>
      </details>
    </li>
  </ul>
</section>
```

- [ ] **Step 4: Add checklist styles**

Append to `tuckit/tuckit/web/static/web/app.css` (token-only; reuse existing `.get-started`/`.gs-*` rules already in the file — only add the new classes). Verify existing `.gs-*` rules first and avoid duplicating; add at minimum:

```css
/* Get started — expandable concept steps */
.gs-step > details > summary { list-style: none; cursor: pointer; display: flex; align-items: center; gap: .5rem; padding: .5rem 0; }
.gs-step > details > summary::-webkit-details-marker { display: none; }
.gs-step.done .gs-box { background: var(--blue); color: var(--paper); border-color: var(--blue); }
.gs-step.gated { opacity: .55; }
.gs-card { padding: .25rem 0 .75rem 1.75rem; display: grid; gap: .5rem; }
.gs-def { color: var(--ink); }
.gs-eg { color: var(--ink-soft); font-size: .9em; }
.gs-gate { color: var(--ink-soft); font-style: italic; }
.gs-form { display: flex; gap: .5rem; flex-wrap: wrap; }
.gs-form input { flex: 1 1 12rem; border-radius: var(--radius-small); }
```

Note: confirm the exact token names in `tokens.*`/`base.css` (`--ink`, `--ink-soft`, `--paper`, `--blue`, `--radius-small`) and substitute the real ones if they differ — **no literal hex, no hardcoded radius**.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_get_started.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/templates/web/partials/_get_started.html tuckit/web/static/web/app.css tests/web/test_get_started.py
git commit -m "feat: four-step Get started checklist with concept cards"
```

---

### Task 5: Welcome intro → dashboard; connect step deep-link

The first-run intro no longer forces the connect step; its CTA now sends the user into the real Home. The connect step is reachable via `?step=connect` (checklist step 4).

**Files:**
- Modify: `tuckit/tuckit/web/views/welcome.py` (`welcome` view, lines 10-22)
- Modify: `tuckit/tuckit/web/templates/web/welcome.html` (`x-data` on the `<main>`; step-0 CTA button)
- Test: `tests/web/test_welcome.py` (append two tests)

**Interfaces:**
- Consumes: existing `resolve_fallback_workspace`, `wurl 'web:home'`.
- Produces: `welcome` view now passes `start_step` (0 or 1) in context; template initializes Alpine `step` from it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_welcome.py`:

```python
@pytest.mark.django_db
def test_welcome_intro_cta_goes_to_home(client_local, workspace):
    body = client_local.get("/welcome/").content.decode()
    assert "Set up your workspace" in body
    assert 'x-data="{step: 0 }"' in body


@pytest.mark.django_db
def test_welcome_connect_deeplink_opens_connect_step(client_local, workspace):
    body = client_local.get("/welcome/?step=connect").content.decode()
    assert 'x-data="{step: 1 }"' in body
```

(Confirm `test_welcome.py` already imports `pytest` and has `client_local`/`workspace` fixtures — the existing tests in the file use them.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_welcome.py -q`
Expected: FAIL — "Set up your workspace" absent; `x-data` is the hardcoded `{step:0}`.

- [ ] **Step 3: Pass `start_step` from the view**

In `tuckit/tuckit/web/views/welcome.py`, update `welcome`:

```python
def welcome(request):
    ws = resolve_fallback_workspace(request)
    if ws is None:
        return redirect("web:root")
    start_step = 1 if request.GET.get("step") == "connect" else 0
    return render(request, "web/welcome.html", {
        "mcp_url": request.build_absolute_uri("/mcp"),
        "workspace": ws,
        "raw_token": None,
        "start_step": start_step,
        "baseline": (
            ActivityEvent.objects.filter(workspace=ws).order_by("-id")
            .values_list("id", flat=True).first() or 0
        ),
    })
```

- [ ] **Step 4: Update the template**

In `tuckit/tuckit/web/templates/web/welcome.html`:

Change the `<main>` opener from `x-data="{step:0}"` to:

```django
  <main class="w-stage" id="w-stage" x-data="{step: {{ start_step }} }" x-cloak>
```

Change the step-0 nav (currently `<button type="button" class="button button-primary" @click="step=1">Connect your agent →</button>`) to a link into Home:

```django
      <div class="w-nav"><div class="grow"></div><a class="button button-primary" href="{% wurl 'web:home' %}">Set up your workspace →</a></div>
```

Leave step 1 (connect) and the celebrate/live-detection markup unchanged.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_welcome.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/views/welcome.py tuckit/web/templates/web/welcome.html tests/web/test_welcome.py
git commit -m "feat: welcome intro lands on dashboard; connect step deep-linkable"
```

---

### Task 6: Fix stale comment + full-suite green

**Files:**
- Modify: `tests/web/test_area_manage.py:70-71` (stale comment about a pre-created "Default")

- [ ] **Step 1: Update the stale comment**

In `tests/web/test_area_manage.py`, the comment near line 70 says the fixture "pre-creates Triage + a 'Default' area." The fixture now pre-creates only Triage. Update it:

```python
    # the workspace fixture pre-creates only Triage, so filter the full ordered
    # list down to the three areas this test cares about.
```

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (all green). If any test outside the files above assumed a `Default`/non-triage area on the fixture, fix it the same way (create the area explicitly in that test) — but the audit found none beyond the files already handled here.

- [ ] **Step 3: Verify the design-system drift test still passes**

Run: `uv run pytest tests/web/test_design_system.py -q`
Expected: PASS (only `app.css` changed — not a token file).

- [ ] **Step 4: Commit**

```bash
git add tests/web/test_area_manage.py
git commit -m "test: update stale Default-area comment after onboarding change"
```

---

## Self-Review

**Spec coverage:**
- Remove auto-`Default`, keep Triage → Task 1. ✓
- 4-signal derived `OnboardingState` (no new flag) → Task 2. ✓
- Four-step inline checklist with concept cards + gating + dismiss → Task 4. ✓
- Concept card copy (Area/Slice/Bite/Connect, verbatim from spec) → Task 4 template. ✓
- Checklist CTAs actually create Area/Slice/Bite → Task 3 endpoints wired into Task 4 forms. ✓
- First-run entry: intro CTA → Home; connect step via step ④ deep-link → Task 5. ✓
- Invite redirects unchanged; register still → `/welcome/` → untouched (verified, no task needed). ✓
- Bootstrap/tests assuming `Default` fixed → Tasks 1 & 6. ✓
- Empty Home guides via the checklist hero (no separate empty-state widget needed — YAGNI) → covered by Task 4 visibility. ✓
- Token-only CSS, English copy, boundary intact → Global Constraints + Task 4. ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases" — every code step shows real code. One explicit verification note in Task 3 Step 4 (exact import form) and Task 4 Step 4 (confirm token names) — these are "verify the existing pattern," not deferred work.

**Type consistency:** `OnboardingState` fields `has_area/has_slice/has_bite/connected` + `completed/done/current` used identically in the service (Task 2), the template (Task 4), and tests (Tasks 2, 4). URL names `onboarding_area/slice/bite` defined in Task 3 and consumed by the Task 4 template. `start_step` produced in Task 5 view and read in Task 5 template.

## Execution Handoff

(see message)
