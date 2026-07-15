# Inline agent-connect; remove /welcome/ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold the agent-connect experience (endpoint, one-time key, snippets, live "your agent just joined" celebration) inline into checklist step ④ on Home, complete step ④ when the agent actually writes, and delete the standalone `/welcome/` page and its intro narrative entirely.

**Architecture:** Django + server-rendered templates with htmx/Alpine (already loaded on Home via base.html). Onboarding progress stays derived (no new DB rows). Two tenant-scoped onboarding endpoints replace the welcome ones; the step ④ card swaps fragments in place. `base.html` globally makes htmx swap on 204, so the poller uses only HTTP 200 fragments (self-replacing while waiting).

**Tech Stack:** Python 3.13, Django, pytest (`uv run pytest`), htmx 2.x, Alpine, token CSS.

## Global Constraints

- **No new persisted onboarding field.** Progress is derived by query; only the existing `Workspace.onboarding_dismissed` stores state.
- **Poller uses HTTP 200 only, never 204** — base.html:42 opts htmx into swapping on 204, which would wipe the poller.
- **CSS: `var(--token)` only** in `app.css` — no literal hex, no hardcoded radius. Do not reintroduce `.w-*` classes or `welcome.css`.
- **Copy buttons** use the in-repo inline Alpine pattern (`x-on:click="navigator.clipboard.writeText($refs.v.value)"` with a scoped `x-data`), not a global `wCopy()`.
- **Public/private boundary intact** — generic onboarding only; no billing/pricing copy.
- **Complete removal:** after the work, `grep -rniI "welcome" tuckit/web` and the test tree return **no live reference** to the removed page/URLs/partials/css/view.
- `docs/superpowers/` stays untracked. Run `uv run pytest` from the `tuckit/` repo root; commit after each task.

---

### Task 1: Redefine `OnboardingState` — `connected` = real agent activity, add `has_key`

**Files:**
- Modify: `tuckit/tuckit/core/services/onboarding.py`
- Test: `tests/test_services_onboarding.py`
- Test: `tests/web/test_get_started.py` (the one "all done" test that used a token for `connected`)

**Interfaces:**
- Produces: `OnboardingState(has_area, has_slice, has_bite, connected, has_key=False)`.
  `connected` = an `ActivityEvent` with `actor="agent"` exists. `has_key` = an
  `ApiToken` exists. `completed`/`done`/`current` still count only the four step
  signals (`has_area, has_slice, has_bite, connected`).

- [ ] **Step 1: Update the onboarding-state tests**

Replace the token-based `connected` tests in `tests/test_services_onboarding.py`.
Replace the whole `test_token_marks_connected` and `test_all_done` with:

```python
@pytest.mark.django_db
def test_token_marks_has_key_not_connected(workspace):
    ApiToken.objects.create(workspace=workspace, name="a", token_hash="x")
    st = onboarding_state(workspace)
    assert st.has_key is True
    assert st.connected is False  # a key alone is not "connected"


@pytest.mark.django_db
def test_agent_activity_marks_connected(workspace):
    from tuckit.core.models import ActivityEvent
    ActivityEvent.objects.create(
        workspace=workspace, actor="agent", verb="created",
        target_type="slice", target_id=1, target_label="Retry webhooks",
    )
    st = onboarding_state(workspace)
    assert st.connected is True


@pytest.mark.django_db
def test_all_done(workspace):
    from tuckit.core.models import ActivityEvent
    area = create_area(workspace, "Backend")
    sl = create_slice(area, "Retry webhooks", status="planned")
    create_bite(sl, "Add backoff")
    ActivityEvent.objects.create(
        workspace=workspace, actor="agent", verb="created",
        target_type="slice", target_id=sl.id, target_label=sl.title,
    )
    st = onboarding_state(workspace)
    assert st.done is True and st.completed == 4 and st.current == 0
```

- [ ] **Step 2: Update the get-started "all done" test to use an agent event**

In `tests/web/test_get_started.py`, `test_checklist_hidden_when_all_done`
currently marks connected with `ApiToken`. Replace its `ApiToken...create(...)`
line with an agent activity event:

```python
    from tuckit.core.models import ActivityEvent
    ActivityEvent.objects.create(
        workspace=workspace, actor="agent", verb="created",
        target_type="slice", target_id=sl.id, target_label=sl.title,
    )
```

(Keep the `create_area`/`create_slice`/`create_bite` lines; drop the
`from tuckit.core.models import ApiToken` import if now unused in the file.)

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_services_onboarding.py tests/web/test_get_started.py -q`
Expected: FAIL — `OnboardingState` has no `has_key`; `connected` still keyed to token.

- [ ] **Step 4: Redefine the service**

Replace the whole `tuckit/tuckit/core/services/onboarding.py`:

```python
from dataclasses import dataclass

from tuckit.core.models import ActivityEvent, ApiToken, Area, Bite, Slice, Workspace


@dataclass(frozen=True)
class OnboardingState:
    has_area: bool
    has_slice: bool
    has_bite: bool
    connected: bool
    has_key: bool = False

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
        connected=ActivityEvent.objects.filter(workspace=workspace, actor="agent").exists(),
        has_key=ApiToken.objects.filter(workspace=workspace).exists(),
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_services_onboarding.py tests/web/test_get_started.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tuckit/core/services/onboarding.py tests/test_services_onboarding.py tests/web/test_get_started.py
git commit -m "feat: onboarding 'connected' = real agent activity; add has_key"
```

---

### Task 2: Onboarding connect endpoints + fragments

**Files:**
- Modify: `tuckit/tuckit/web/views/onboarding.py`
- Modify: `tuckit/tuckit/web/urls.py`
- Create: `tuckit/tuckit/web/templates/web/partials/_get_started_key.html`
- Create: `tuckit/tuckit/web/templates/web/partials/_get_started_listen.html`
- Create: `tuckit/tuckit/web/templates/web/partials/_get_started_celebrate.html`
- Test: `tests/web/test_onboarding_connect.py`

**Interfaces:**
- Consumes: `get_current_workspace`, `generate_token(ws, name) -> (ApiToken, raw)`, `ActivityEvent`.
- Produces URL names `web:onboarding_connect_key` (POST) and `web:onboarding_agent_check` (GET), both under `P`.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_onboarding_connect.py`:

```python
import pytest

from tuckit.core.models import ActivityEvent, ApiToken


@pytest.mark.django_db
def test_connect_key_creates_token_and_shows_snippet(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.post(f"{p}/onboarding/connect-key")
    assert r.status_code == 200
    assert ApiToken.objects.filter(workspace=workspace).count() == 1
    body = r.content.decode()
    assert "MCP endpoint" in body
    assert "claude mcp add" in body        # Claude Code snippet
    assert 'id="gs-listen"' in body        # poller included


@pytest.mark.django_db
def test_agent_check_waiting_returns_poller(client_local, workspace):
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.get(f"{p}/onboarding/agent-activity?since=0")
    assert r.status_code == 200
    assert 'id="gs-listen"' in r.content.decode()   # keeps polling, not 204


@pytest.mark.django_db
def test_agent_check_celebrates_on_agent_event(client_local, workspace):
    ActivityEvent.objects.create(
        workspace=workspace, actor="agent", verb="created",
        target_type="slice", target_id=1, target_label="Retry webhooks",
    )
    p = f"/{workspace.org.slug}/{workspace.slug}"
    r = client_local.get(f"{p}/onboarding/agent-activity?since=0")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Retry webhooks" in body                 # celebrate fragment
    assert 'id="gs-listen"' not in body             # polling stops
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_onboarding_connect.py -q`
Expected: FAIL — routes `onboarding/connect-key` / `onboarding/agent-activity` do not resolve (404).

- [ ] **Step 3: Add the views**

Append to `tuckit/tuckit/web/views/onboarding.py` (and add imports at the top:
`from tuckit.core.models import ActivityEvent, Area, Slice` — add `ActivityEvent`;
`from tuckit.core.services.tokens import generate_token`):

```python
def _agent_baseline(ws) -> int:
    return (
        ActivityEvent.objects.filter(workspace=ws).order_by("-id")
        .values_list("id", flat=True).first() or 0
    )


@require_POST
def connect_key(request):
    ws = get_current_workspace(request)
    if ws is None:
        return redirect("web:root")
    _token, raw = generate_token(ws, "Agent (onboarding)")
    return render(request, "web/partials/_get_started_key.html", {
        "mcp_url": request.build_absolute_uri("/mcp"),
        "raw_token": raw,
        "agent_baseline": _agent_baseline(ws),
    })


def agent_check(request):
    ws = get_current_workspace(request)
    if ws is None:
        return redirect("web:root")
    try:
        since = int(request.GET.get("since", "0"))
    except ValueError:
        since = 0
    ev = (
        ActivityEvent.objects.filter(workspace=ws, actor="agent", id__gt=since)
        .order_by("id").first()
    )
    if ev is None:
        # 200 (not 204 — base.html:42 swaps on 204); re-serve the poller.
        return render(request, "web/partials/_get_started_listen.html", {"agent_baseline": since})
    return render(request, "web/partials/_get_started_celebrate.html", {"event": ev})
```

- [ ] **Step 4: Wire the routes**

In `tuckit/tuckit/web/urls.py`, next to the other onboarding routes:

```python
    path(f"{P}onboarding/bite", onboarding.create_first_bite, name="onboarding_bite"),
    path(f"{P}onboarding/connect-key", onboarding.connect_key, name="onboarding_connect_key"),
    path(f"{P}onboarding/agent-activity", onboarding.agent_check, name="onboarding_agent_check"),
```

- [ ] **Step 5: Create the listen fragment (the self-replacing poller)**

Create `tuckit/tuckit/web/templates/web/partials/_get_started_listen.html`:

```django
{% load web_extras %}
<div id="gs-listen" class="gs-listen"
     hx-get="{% wurl 'web:onboarding_agent_check' %}?since={{ agent_baseline }}"
     hx-trigger="every 3s" hx-target="#gs-listen" hx-swap="outerHTML">
  <span class="gs-radar" aria-hidden="true"></span>
  <span><b>Listening for your agent…</b> ask it to capture or create something.</span>
</div>
```

- [ ] **Step 6: Create the key fragment (generate response)**

Create `tuckit/tuckit/web/templates/web/partials/_get_started_key.html`:

```django
{% load web_extras %}
<div class="gs-field">
  <label>MCP endpoint</label>
  <div class="gs-copyrow" x-data>
    <input class="gs-mono" value="{{ mcp_url }}" readonly x-ref="v">
    <button type="button" class="gs-mini" x-on:click="navigator.clipboard.writeText($refs.v.value)">Copy</button>
  </div>
</div>
<div class="gs-field">
  <label>Workspace key — copy it now, it won't be shown again</label>
  <div class="gs-copyrow" x-data>
    <input class="gs-mono" value="{{ raw_token }}" readonly x-ref="v">
    <button type="button" class="gs-mini" x-on:click="navigator.clipboard.writeText($refs.v.value)">Copy</button>
  </div>
</div>
<div class="gs-snip" x-data>
  <label>Claude Code</label>
  <pre class="gs-code" x-ref="cc">claude mcp add tuckit --transport http {{ mcp_url }} --header "Authorization: Bearer {{ raw_token }}"</pre>
  <button type="button" class="gs-mini" x-on:click="navigator.clipboard.writeText($refs.cc.textContent)">Copy</button>
</div>
{% include "web/partials/_get_started_listen.html" %}
```

- [ ] **Step 7: Create the celebrate fragment (replaces the poller, no poller inside)**

Create `tuckit/tuckit/web/templates/web/partials/_get_started_celebrate.html`:

```django
<div class="gs-celebrate">
  <span class="gs-seal" aria-hidden="true">🎉</span>
  <div>
    <b>Your agent just joined.</b>
    <div class="gs-won"><span class="gs-who">🤖</span> agent {{ event.verb }} “{{ event.target_label }}”</div>
  </div>
  <p class="gs-eg">From now on you'll see everything it does here — and tuckit flags anything that needs you.</p>
</div>
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_onboarding_connect.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add tuckit/web/views/onboarding.py tuckit/web/urls.py tuckit/web/templates/web/partials/_get_started_key.html tuckit/web/templates/web/partials/_get_started_listen.html tuckit/web/templates/web/partials/_get_started_celebrate.html tests/web/test_onboarding_connect.py
git commit -m "feat: inline agent-connect + live-detect endpoints and fragments"
```

---

### Task 3: Inline the ④ card on Home (context + template + styles)

**Files:**
- Modify: `tuckit/tuckit/web/views/pages.py` (`home`)
- Modify: `tuckit/tuckit/web/templates/web/partials/_get_started.html` (step ④)
- Modify: `tuckit/tuckit/web/static/web/app.css`
- Test: `tests/web/test_get_started.py`

**Interfaces:**
- Consumes: `onboarding` (with `.connected`/`.has_key`), and new context `mcp_url`, `agent_baseline`. URL names from Task 2.

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_get_started.py`:

```python
@pytest.mark.django_db
def test_step4_shows_generate_key_when_no_key(client_local, workspace):
    create_area(workspace, "Backend")  # so checklist shows and ④ is reachable
    p = f"/{workspace.org.slug}/{workspace.slug}"
    body = client_local.get(f"{p}/").content.decode()
    assert "/onboarding/connect-key" in body     # generate button target
    assert "/welcome/" not in body               # no link out to the old page


@pytest.mark.django_db
def test_step4_shows_poller_when_key_exists(client_local, workspace):
    from tuckit.core.models import ApiToken
    ApiToken.objects.create(workspace=workspace, name="a", token_hash="x")
    p = f"/{workspace.org.slug}/{workspace.slug}"
    body = client_local.get(f"{p}/").content.decode()
    assert 'id="gs-listen"' in body              # listening/poller state
    assert "/onboarding/agent-activity" in body
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_get_started.py -q`
Expected: FAIL — ④ still renders the `/welcome/` link, no connect-key/poller.

- [ ] **Step 3: Pass `mcp_url` + `agent_baseline` from Home**

In `tuckit/tuckit/web/views/pages.py`, add the import at the top:

```python
from tuckit.core.models import ActivityEvent
```

Then in `home`, add these two keys to the `render(...)` context dict (alongside
`"onboarding": ob,`):

```python
        "mcp_url": request.build_absolute_uri("/mcp"),
        "agent_baseline": (
            ActivityEvent.objects.filter(workspace=ws).order_by("-id")
            .values_list("id", flat=True).first() or 0
        ) if ws else 0,
```

- [ ] **Step 4: Replace the ④ step in the checklist partial**

In `tuckit/tuckit/web/templates/web/partials/_get_started.html`, replace the
entire fourth `<li>` (the "Connect your agent" step, currently ending with the
`<a … href="{% url 'web:welcome' %}?step=connect">` link) with:

```django
    <li class="gs-step {% if onboarding.connected %}done{% endif %}">
      <details {% if onboarding.current == 4 %}open{% endif %}>
        <summary><span class="gs-box">✓</span><span class="gs-lbl">Connect your agent</span></summary>
        <div class="gs-card">
          <p class="gs-def">You just built the structure by hand — so you <b>understand</b> it. From here your AI agent reads and writes these same Areas, Slices, and Bites over MCP. It does the work; nothing it does slips past you.</p>
          <div id="gs-connect">
            {% if onboarding.connected %}
              <p class="gs-done-note">✓ Your agent is connected — you're all set.</p>
            {% else %}
              <div class="gs-field">
                <label>MCP endpoint</label>
                <div class="gs-copyrow" x-data>
                  <input class="gs-mono" value="{{ mcp_url }}" readonly x-ref="v">
                  <button type="button" class="gs-mini" x-on:click="navigator.clipboard.writeText($refs.v.value)">Copy</button>
                </div>
              </div>
              {% if onboarding.has_key %}
                <p class="gs-eg">You've generated a key. Point your agent at the endpoint above — it'll show up here.</p>
                {% include "web/partials/_get_started_listen.html" %}
                <button type="button" class="button" hx-post="{% wurl 'web:onboarding_connect_key' %}" hx-target="#gs-connect" hx-swap="innerHTML">Generate another key</button>
              {% else %}
                <button type="button" class="button button-primary" hx-post="{% wurl 'web:onboarding_connect_key' %}" hx-target="#gs-connect" hx-swap="innerHTML">Generate agent key</button>
              {% endif %}
            {% endif %}
          </div>
        </div>
      </details>
    </li>
```

- [ ] **Step 5: Add the connect-card styles to app.css**

Append to `tuckit/tuckit/web/static/web/app.css` (token-only; confirm token
names exist as in the existing `.gs-*` block and substitute if different):

```css
/* Get started — inline agent connect */
#gs-connect { display: grid; gap: 10px; }
.gs-field { display: grid; gap: 4px; }
.gs-field label { font-size: 12px; color: var(--muted); }
.gs-copyrow { display: flex; gap: 6px; }
.gs-mono { flex: 1; font-family: var(--mono); font-size: 12px; padding: 6px 8px; border: 1px solid var(--line-strong); border-radius: var(--radius-small); background: var(--paper); color: var(--text); }
.gs-mini { font-size: 12px; padding: 6px 10px; border: 1px solid var(--line-strong); border-radius: var(--radius-small); background: var(--surface); color: var(--text); cursor: pointer; }
.gs-mini:hover { background: var(--paper-deep); }
.gs-snip { display: grid; gap: 4px; }
.gs-code { font-family: var(--mono); font-size: 12px; white-space: pre-wrap; word-break: break-all; padding: 8px 10px; border: 1px solid var(--line); border-radius: var(--radius-small); background: var(--paper-deep); color: var(--text); margin: 0; }
.gs-listen { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--muted); }
.gs-radar { width: 9px; height: 9px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 0 0 var(--accent); animation: gs-pulse 1.8s infinite; }
@keyframes gs-pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--accent) 50%, transparent); } 70% { box-shadow: 0 0 0 8px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }
@media (prefers-reduced-motion: reduce) { .gs-radar { animation: none; } }
.gs-celebrate { display: grid; gap: 6px; padding: 10px; border: 1px solid var(--line); border-radius: var(--radius-small); background: var(--paper-deep); }
.gs-seal { font-size: 22px; }
.gs-won { font-family: var(--mono); font-size: 12px; color: var(--muted); }
.gs-done-note { margin: 0; color: var(--good); font-size: 13px; }
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_get_started.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/views/pages.py tuckit/web/templates/web/partials/_get_started.html tuckit/web/static/web/app.css tests/web/test_get_started.py
git commit -m "feat: inline agent-connect card in checklist step 4"
```

---

### Task 4: Remove /welcome/ entirely; register → Home

**Files:**
- Delete: `tuckit/tuckit/web/views/welcome.py`
- Delete: `tuckit/tuckit/web/templates/web/welcome.html`
- Delete: `tuckit/tuckit/web/templates/web/partials/_welcome_key.html`
- Delete: `tuckit/tuckit/web/templates/web/partials/_welcome_celebrate.html`
- Delete: `tuckit/tuckit/web/static/web/welcome.css`
- Delete: `tests/web/test_welcome.py`
- Modify: `tuckit/tuckit/web/urls.py`
- Modify: `tuckit/tuckit/web/views/accounts.py`

**Interfaces:**
- Removes URL names `web:welcome`, `web:welcome_generate_key`, `web:welcome_agent_check`.

- [ ] **Step 1: Update the register test expectation**

In `tests/web/test_welcome.py` there may be a register-redirect assertion; that
file is being deleted. Instead, ensure `tests/web/` has a register test. Search:
`grep -rniI "register" tests/web tests | grep -i redirect`. If a register→welcome
assertion exists elsewhere, update it to expect Home. If the only register-flow
assertions live in `test_welcome.py` (deleted), add one to a kept file — create
`tests/web/test_register_lands_home.py`:

```python
import pytest
from django.test import override_settings

from tuckit.core.models import User, Workspace


@pytest.mark.django_db
@override_settings(REGISTRATION_OPEN=True)
def test_self_service_register_lands_on_home(client):
    r = client.post("/register/", {
        "email": "new@example.com", "org_name": "Acme",
        "slug": "acme", "password": "pw12345678",
    })
    assert r.status_code == 302
    u = User.objects.get(email="new@example.com")
    ws = Workspace.objects.get(org__members__user=u)
    assert r.headers["Location"] == f"/{ws.org.slug}/{ws.slug}/"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/web/test_register_lands_home.py -q`
Expected: FAIL — register still redirects to `/welcome/`.

- [ ] **Step 3: Point register at Home**

In `tuckit/tuckit/web/views/accounts.py`, in `register_view`, change the success
branch (rename the unpacked vars and the redirect):

```python
            user, org, ws = register(
                email=request.POST.get("email", ""),
                org_name=request.POST.get("org_name", ""),
                slug=request.POST.get("slug", ""),
                password=request.POST.get("password", ""),
            )
        except InvalidValue as exc:
            return render(request, "registration/register.html", {"error": str(exc), "values": request.POST})
        login(request, user)
        return redirect("web:home", org_slug=org.slug, ws_slug=ws.slug)
```

- [ ] **Step 4: Remove the welcome routes and import**

In `tuckit/tuckit/web/urls.py`: delete the three `path("welcome/…")` lines
(lines for `welcome`, `welcome/key`, `welcome/agent-activity`) and remove
`welcome as welcome_views` from the `from tuckit.web.views import (...)` group.

- [ ] **Step 5: Delete the welcome view, templates, css, and test**

```bash
git rm tuckit/web/views/welcome.py \
       tuckit/web/templates/web/welcome.html \
       tuckit/web/templates/web/partials/_welcome_key.html \
       tuckit/web/templates/web/partials/_welcome_celebrate.html \
       tuckit/web/static/web/welcome.css \
       tests/web/test_welcome.py
```

- [ ] **Step 6: Verify no dead references remain (Definition of Done)**

Run:
```bash
grep -rniI "welcome" tuckit/web tests
```
Expected: **no matches** in code (no `web:welcome*`, `welcome.html`, `welcome.css`,
`_welcome_*`, `welcome_views`, `start_step`). If anything prints, fix it. Then:

```bash
uv run pytest -q
```
Expected: PASS (full suite green, including the design-system drift test — `welcome.css` removed, new styles live in `app.css`).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove /welcome/ page and intro narrative; register lands on Home"
```

---

## Self-Review

**Spec coverage:**
- Inline connect (endpoint/key/snippets) → Task 2 fragments + Task 3 card. ✓
- Live celebration, HTTP-200 self-replacing poller (204 caveat) → Task 2 (`agent_check`, listen/celebrate fragments) + Task 3 (poller in card). ✓
- ④ completes on real agent activity; `connected`/`has_key` split → Task 1. ✓
- Home passes `mcp_url`/`agent_baseline` → Task 3. ✓
- Remove /welcome/ page, intro, partials, css, URLs, view, test → Task 4 + grep DoD. ✓
- register → Home → Task 4. ✓
- Token-only CSS, no `.w-*`, inline Alpine copy → Task 3 styles + fragments. ✓
- Boundary intact; docs untracked → Global Constraints. ✓

**Placeholder scan:** No TBD/TODO; every code step shows real code. Step 4.1 has a conditional ("if a register assertion exists elsewhere") but provides a concrete fallback test either way.

**Type/name consistency:** `OnboardingState(has_area, has_slice, has_bite, connected, has_key)` used identically across service (T1), tests (T1/T3), and template (`onboarding.connected`/`.has_key`, T3). URL names `onboarding_connect_key`/`onboarding_agent_check` defined in T2 and consumed by the fragments/card. `#gs-connect` (card container, generate target) and `#gs-listen` (poller, `outerHTML` self-replace) used consistently. `agent_baseline` produced by `home` (T3) and `connect_key` (T2), consumed by the listen fragment.

## Execution Handoff

(see message)
