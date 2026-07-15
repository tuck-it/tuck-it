# First-run Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give new tuckit accounts a first-run onboarding centered on connecting their AI agent — a dedicated `/welcome/` flow with live agent-connection detection, a persistent Home "Get started" checklist, and guiding empty states.

**Architecture:** One new persisted field (`Workspace.onboarding_dismissed`); all other progress is derived from real data (`ApiToken`/`Slice`/`Area` counts) via a new `onboarding` service. A standalone full-screen `/welcome/` page (does not extend the app shell) walks Welcome → Connect (generate MCP key + copy snippets) → live Celebrate (HTMX polls for the agent's first write). Home renders a checklist card from the same derivation. Copy is English and leads with the emotional framing.

**Tech Stack:** Django templates, Alpine.js + HTMX (already vendored), static CSS with design tokens, pytest (Django test client). Run tests with `uv run pytest`.

## Global Constraints

- CSS values use `var(--token)` ONLY — no literal hex, no hardcoded radius (`var(--radius)` / `var(--radius-small)`). Sizing px is fine.
- `welcome.css` is a new **screen** sheet, not a token file — must NOT define/redefine any `--token`, and does NOT participate in the brand-token drift check.
- The `/welcome/` page is **standalone** — it does NOT extend `web/base.html` (no sidebar shell). It loads `tokens.brand.css → tokens.product.css → base.css → welcome.css`, plus the vendored Alpine + HTMX, plus the theme pre-paint script. It does NOT link `app.css`.
- Type roles: human/body = Onest (`--sans`), agent/code/labels = IBM Plex Mono (`--mono`) — both already `@font-face`'d in base.css.
- Only ONE new model field: `Workspace.onboarding_dismissed = BooleanField(default=False)`. All other onboarding progress is derived (no other new state).
- The live celebration triggers ONLY on an `actor="agent"` `ActivityEvent` created after the connect step loaded (an agent *write*).
- Protected / do not change: MCP/API behavior, tenant isolation, the activity/actor threading, the two invite-flow redirects (`accounts.py:41,48` stay `web:home`), token hashing, license/boundary (no billing/pricing copy).
- Copy: English.
- `docs/superpowers/` stays untracked (already gitignored) — never commit the spec/plan.
- Out of scope: the full English-only sweep (only empty-state copy on newcomer screens is touched), seeded sample slices, invited-member onboarding, a "Ship" 4th checklist step.

## File Structure

- **New** `tuckit/core/services/onboarding.py` — `onboarding_state(workspace)` derivation.
- **Modify** `tuckit/core/models/workspace.py` — add `onboarding_dismissed` field (+ migration).
- **New** `tuckit/web/views/welcome.py` — `welcome`, `welcome_generate_key`, `welcome_agent_check` views.
- **Modify** `tuckit/web/urls.py` — 3 new URL names.
- **Modify** `tuckit/web/views/accounts.py:25` — signup redirect → `web:welcome`.
- **New** `tuckit/web/templates/web/welcome.html` — standalone flow page.
- **New** `tuckit/web/templates/web/partials/_welcome_key.html` — connect-body partial (endpoint + key + snippets), reused by the generate POST.
- **New** `tuckit/web/templates/web/partials/_welcome_celebrate.html` — celebration fragment returned by the poll.
- **New** `tuckit/web/static/web/welcome.css` — flow styles.
- **Modify** `tuckit/web/templates/web/home.html` — "Get started" checklist card.
- **Modify** `tuckit/web/templates/web/partials/_get_started.html` — **New** checklist partial.
- **Modify** `tuckit/web/views/pages.py` (`home`) — pass `onboarding` into context; **New** `dismiss_onboarding` view + URL.
- **Modify** `tuckit/web/static/web/app.css` — checklist card styles.
- **Modify** empty-state templates: `triage`, `in_progress`, `roadmap` partials/pages.
- **Tests** under `tests/` and `tests/web/`.

---

### Task 1: Onboarding state — field, migration, derivation service

**Files:**
- Modify: `tuckit/core/models/workspace.py` (add field)
- Create: `tuckit/core/services/onboarding.py`
- Create: migration under `tuckit/core/migrations/`
- Test: `tests/test_services_onboarding.py`

**Interfaces:**
- Produces `onboarding_state(workspace) -> OnboardingState` (a dataclass) with bool fields `connected`, `captured`, `triaged`, `done`, and int `completed` (0–3). Consumed by Tasks 2 (welcome not needed) and 4 (Home checklist).
- Consumes existing models: `ApiToken` (`workspace` FK), `Slice` (`area__workspace`, `area__is_triage`), `Area`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_services_onboarding.py`:

```python
import pytest

from tuckit.core.models import Area, ApiToken
from tuckit.core.services.onboarding import onboarding_state
from tuckit.core.services.slices import create_slice


@pytest.mark.django_db
def test_fresh_workspace_all_incomplete(workspace):
    st = onboarding_state(workspace)
    assert (st.connected, st.captured, st.triaged) == (False, False, False)
    assert st.done is False and st.completed == 0


@pytest.mark.django_db
def test_token_marks_connected(workspace):
    ApiToken.objects.create(workspace=workspace, name="a", token_hash="x")
    st = onboarding_state(workspace)
    assert st.connected is True and st.completed == 1


@pytest.mark.django_db
def test_slice_marks_captured_only_if_in_triage(workspace):
    triage = Area.objects.get(workspace=workspace, is_triage=True)
    create_slice(triage, "idea", status="idea")
    st = onboarding_state(workspace)
    assert st.captured is True and st.triaged is False


@pytest.mark.django_db
def test_slice_in_normal_area_marks_triaged(workspace):
    default = Area.objects.get(workspace=workspace, is_triage=False)
    create_slice(default, "real", status="planned")
    st = onboarding_state(workspace)
    assert st.captured is True and st.triaged is True


@pytest.mark.django_db
def test_all_done(workspace):
    ApiToken.objects.create(workspace=workspace, name="a", token_hash="x")
    default = Area.objects.get(workspace=workspace, is_triage=False)
    create_slice(default, "real", status="planned")
    st = onboarding_state(workspace)
    assert st.done is True and st.completed == 3
```

(Uses the real `create_slice` service so slice defaults like `rank`/`source` are set correctly — confirm its signature `create_slice(area, title, status=..., source=...)` in `tuckit/core/services/slices.py`.)

(The `workspace` fixture in `tests/conftest.py` bootstraps an org/workspace with the seeded Triage + Default areas.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services_onboarding.py -v`
Expected: FAIL — `ModuleNotFoundError: tuckit.core.services.onboarding`.

- [ ] **Step 3: Create the service**

Create `tuckit/core/services/onboarding.py`:

```python
from dataclasses import dataclass

from tuckit.core.models import ApiToken, Slice, Workspace


@dataclass(frozen=True)
class OnboardingState:
    connected: bool
    captured: bool
    triaged: bool

    @property
    def completed(self) -> int:
        return sum((self.connected, self.captured, self.triaged))

    @property
    def done(self) -> bool:
        return self.completed == 3


def onboarding_state(workspace: Workspace) -> OnboardingState:
    connected = ApiToken.objects.filter(workspace=workspace).exists()
    captured = Slice.objects.filter(area__workspace=workspace).exists()
    triaged = Slice.objects.filter(
        area__workspace=workspace, area__is_triage=False
    ).exists()
    return OnboardingState(connected=connected, captured=captured, triaged=triaged)
```

- [ ] **Step 4: Add the model field**

In `tuckit/core/models/workspace.py`, add to the `Workspace` model (alongside existing fields):

```python
    onboarding_dismissed = models.BooleanField(default=False)
```

- [ ] **Step 5: Make the migration**

Run: `uv run python manage.py makemigrations core`
Expected: creates `tuckit/core/migrations/0007_workspace_onboarding_dismissed.py` (name/number may differ — accept whatever it generates). Verify it adds `onboarding_dismissed`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_services_onboarding.py -v`
Expected: PASS (5/5).

- [ ] **Step 7: Commit**

```bash
git add tuckit/core/services/onboarding.py tuckit/core/models/workspace.py tuckit/core/migrations/ tests/test_services_onboarding.py
git commit -m "feat(core): onboarding_state derivation + Workspace.onboarding_dismissed"
```

---

### Task 2: The `/welcome/` page — view, template, css, generate-key, signup redirect

**Files:**
- Create: `tuckit/web/views/welcome.py`
- Modify: `tuckit/web/urls.py`
- Modify: `tuckit/web/views/accounts.py` (line ~25 redirect)
- Create: `tuckit/web/templates/web/welcome.html`
- Create: `tuckit/web/templates/web/partials/_welcome_key.html`
- Create: `tuckit/web/static/web/welcome.css`
- Test: `tests/web/test_welcome.py`

**Interfaces:**
- Produces URL names `web:welcome` (`GET /welcome/`) and `web:welcome_generate_key` (`POST /welcome/key`). Consumed by Task 3 (adds `web:welcome_agent_check`) and Task 4 (checklist CTA links to `web:welcome`).
- `welcome(request)` context: `mcp_url` (str), `raw_token=None`. `welcome_generate_key(request)` creates a token via `generate_token(ws, "Agent (onboarding)")` and returns the `_welcome_key.html` partial with `raw_token` set.
- Current workspace resolved via `get_current_workspace(request)` (`tuckit/web/auth.py`), same as other views.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_welcome.py`:

```python
import pytest
from django.test import override_settings

from tuckit.core.models import ApiToken, User


@pytest.mark.django_db
def test_welcome_renders_standalone_for_logged_in_user(client_local):
    body = client_local.get("/welcome/").content.decode()
    assert '<html lang="en"' in body
    assert "web/welcome.css" in body
    assert "web/app.css" not in body           # standalone, no app shell
    assert "Nothing your agent does" in body   # emotional hero
    assert "/mcp" in body                       # endpoint present


@pytest.mark.django_db
def test_generate_key_creates_one_token_and_reveals_once(client_local, workspace):
    # NOTE: the web `workspace`/`client_local` fixtures bootstrap a token already,
    # so assert an INCREMENT of exactly one, not an absolute count of 0/1.
    before = ApiToken.objects.filter(workspace=workspace).count()
    resp = client_local.post("/welcome/key")
    assert resp.status_code == 200
    assert ApiToken.objects.filter(workspace=workspace).count() == before + 1
    # raw token revealed in the returned fragment
    assert "Bearer" in resp.content.decode()


@pytest.mark.django_db
@override_settings(REGISTRATION_OPEN=True)
def test_signup_redirects_to_welcome(client):
    resp = client.post("/register/", {
        "email": "new@x.com", "org_name": "NewCo", "slug": "newco", "password": "pw123456",
    })
    assert resp.status_code == 302
    assert resp["Location"].endswith("/welcome/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_welcome.py -v`
Expected: FAIL — `/welcome/` 404 (no URL), and signup still redirects to `/`.

- [ ] **Step 3: Add the views**

Create `tuckit/web/views/welcome.py`:

```python
from django.shortcuts import render
from django.views.decorators.http import require_POST

from tuckit.core.services.tokens import generate_token
from tuckit.web.auth import get_current_workspace


def welcome(request):
    ws = get_current_workspace(request)
    return render(request, "web/welcome.html", {
        "mcp_url": request.build_absolute_uri("/mcp"),
        "workspace": ws,
        "raw_token": None,
    })


@require_POST
def welcome_generate_key(request):
    ws = get_current_workspace(request)
    _token, raw = generate_token(ws, "Agent (onboarding)")
    return render(request, "web/partials/_welcome_key.html", {
        "mcp_url": request.build_absolute_uri("/mcp"),
        "raw_token": raw,
    })
```

- [ ] **Step 4: Wire the URLs**

In `tuckit/web/urls.py`, add inside `urlpatterns` (import `from tuckit.web.views import welcome as welcome_views` at top):

```python
    path("welcome/", welcome_views.welcome, name="welcome"),
    path("welcome/key", welcome_views.welcome_generate_key, name="welcome_generate_key"),
```

- [ ] **Step 5: Flip the signup redirect**

In `tuckit/web/views/accounts.py`, in `register_view`, change the post-success redirect (currently `return redirect("web:home")` at line ~25) to:

```python
        return redirect("web:welcome")
```

(Leave the two invite-flow redirects at lines ~41 and ~48 as `web:home`.)

- [ ] **Step 6: Create `welcome.css`**

Create `tuckit/web/static/web/welcome.css` (adapted from the approved mockup; tokens only):

```css
/* First-run onboarding flow. Standalone page (no app shell). Loaded after
   tokens.brand + tokens.product + base.css; NOT with app.css. var(--token) only. */
:root{ --sans:"Onest Variable","Onest",system-ui,sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace; }
.w-topbar{width:100%;max-width:1180px;margin:0 auto;display:flex;align-items:center;
  justify-content:space-between;padding:22px 28px}
.w-brand{font-weight:650;letter-spacing:-.02em;font-size:17px}
.w-brand span{color:var(--blue)}
.w-skip{background:none;border:0;color:var(--ink-faint);font:inherit;font-size:13.5px;cursor:pointer;text-decoration:none}
.w-skip:hover{color:var(--ink)}
.w-stage{width:100%;max-width:600px;margin:0 auto;padding:12px 24px 64px;
  min-height:70vh;display:flex;flex-direction:column;justify-content:center}
.w-dots{display:flex;gap:7px;justify-content:center;margin:8px 0 30px}
.w-dots i{width:7px;height:7px;border-radius:50%;background:var(--line-strong);transition:.3s var(--ease)}
.w-dots i.on{background:var(--blue);width:22px;border-radius:4px}
.w-eyebrow{font-family:var(--mono);font-size:11.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--blue);margin:0 0 16px}
.w-stage h1{font-size:clamp(28px,6vw,40px);font-weight:650;letter-spacing:-.03em;line-height:1.07;margin:0 0 14px}
.w-lede{font-size:17px;color:var(--ink-soft);margin:0;max-width:44ch}
.w-lede b{color:var(--ink);font-weight:560}
/* activity-stream hero */
.w-stream{margin:28px 0 8px;border:1px solid var(--line);border-radius:var(--radius);
  background:var(--paper-raised);overflow:hidden}
.w-stream-head{display:flex;justify-content:space-between;padding:11px 16px;border-bottom:1px solid var(--line);
  font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-faint)}
.w-live{display:inline-flex;align-items:center;gap:6px;color:var(--good)}
.w-live b{width:6px;height:6px;border-radius:50%;background:var(--good);animation:w-blink 2s infinite}
@keyframes w-blink{0%,100%{opacity:1}50%{opacity:.35}}
.w-evt{display:grid;grid-template-columns:auto 1fr auto;gap:12px;align-items:center;
  padding:13px 16px;border-bottom:1px solid var(--line)}
.w-evt:last-child{border-bottom:0}
.w-who{width:26px;height:26px;border-radius:7px;display:grid;place-items:center;font-size:13px}
.w-who.agent{background:var(--blue-soft);color:var(--blue-strong)}
.w-who.you{background:var(--paper-deep);color:var(--ink-soft)}
.w-line{font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.w-line .actor{font-family:var(--mono);font-size:12px;color:var(--ink-faint);margin-right:7px}
.w-line .verb{color:var(--ink-soft);margin-right:5px}
.w-line .t{font-weight:560}
.w-when{font-family:var(--mono);font-size:11px;color:var(--ink-faint)}
.w-needs{grid-column:1/-1;margin-top:2px}
.w-chip-needs{display:inline-flex;align-items:center;gap:7px;font-family:var(--mono);font-size:10.5px;
  letter-spacing:.08em;text-transform:uppercase;color:var(--warn);
  border:1px solid color-mix(in srgb,var(--warn) 45%,var(--line));padding:3px 9px;border-radius:999px;
  background:color-mix(in srgb,var(--warn) 9%,transparent)}
.w-note{margin:16px 2px 0;font-size:13.5px;color:var(--ink-faint)}
.w-note b{color:var(--ink-soft);font-weight:560}
/* connect */
.w-field{margin:20px 0}
.w-field > label{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink-faint);margin-bottom:7px}
.w-copyrow{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:var(--radius-small);
  background:var(--paper-solid);padding:0 6px 0 13px}
.w-copyrow input{flex:1;border:0;background:none;color:var(--ink);font-family:var(--mono);font-size:13px;
  padding:11px 0;min-width:0;outline:none}
.w-mini{border:1px solid var(--line);background:var(--paper-raised);border-radius:7px;color:var(--ink-soft);
  font:inherit;font-family:var(--mono);font-size:12px;padding:5px 10px;cursor:pointer;white-space:nowrap}
.w-mini:hover{border-color:var(--blue);color:var(--blue)}
.w-snip{margin-top:16px}
.w-snip > label{display:block;font-family:var(--mono);font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-faint);margin:16px 0 7px}
.w-code{border:1px solid var(--line);border-radius:var(--radius-small);background:var(--paper-deep);padding:14px 16px;overflow-x:auto}
.w-code pre{margin:0;font-family:var(--mono);font-size:12.5px;line-height:1.65;color:var(--ink);white-space:pre}
.w-code .k{color:var(--blue-strong)} .w-code .s{color:var(--good)} .w-code .c{color:var(--ink-faint)}
.w-listen{margin-top:24px;display:flex;align-items:center;gap:13px;padding:15px 17px;
  border:1px dashed var(--line-strong);border-radius:var(--radius-small);
  background:color-mix(in srgb,var(--blue-soft) 30%,transparent)}
.w-radar{width:11px;height:11px;border-radius:50%;background:var(--blue);position:relative;flex:none}
.w-radar::after{content:"";position:absolute;inset:-6px;border-radius:50%;border:2px solid var(--blue);
  opacity:.5;animation:w-radar 1.8s var(--ease) infinite}
@keyframes w-radar{0%{transform:scale(.5);opacity:.6}100%{transform:scale(1.6);opacity:0}}
.w-listen .lt{font-size:14px;color:var(--ink-soft)} .w-listen .lt b{color:var(--ink)}
/* celebrate */
.w-celebrate{text-align:center;padding:8px 0}
.w-seal{width:74px;height:74px;border-radius:50%;margin:6px auto 22px;display:grid;place-items:center;
  background:color-mix(in srgb,var(--good) 16%,var(--paper-raised));
  border:1px solid color-mix(in srgb,var(--good) 45%,var(--line))}
.w-seal svg{width:34px;height:34px}
.w-seal path{stroke:var(--good);stroke-width:3.4;fill:none;stroke-linecap:round;stroke-linejoin:round;
  stroke-dasharray:40;stroke-dashoffset:40;animation:w-draw .5s .15s var(--ease) forwards}
@keyframes w-draw{to{stroke-dashoffset:0}}
.w-won{display:inline-flex;align-items:center;gap:11px;margin:2px auto 0;border:1px solid var(--line);
  border-radius:var(--radius-small);background:var(--paper-raised);padding:11px 15px;text-align:left;max-width:100%}
/* nav */
.w-nav{display:flex;align-items:center;gap:14px;margin-top:34px}
.w-nav .grow{flex:1}
/* Reuse the base.css .button / .button-primary primitives (base.css is loaded).
   Only add a ghost variant (base has none) + slightly larger flow sizing + link reset. */
.w-nav .button{min-height:44px;padding:0 22px;text-decoration:none}
.w-ghost{background:none;border-color:var(--line);color:var(--ink-soft)}
.w-ghost:hover{border-color:var(--line-strong);color:var(--ink)}
[x-cloak]{display:none!important}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
```

- [ ] **Step 7: Create the connect-body partial**

Create `tuckit/web/templates/web/partials/_welcome_key.html`:

```html
<div class="w-field">
  <label>MCP endpoint</label>
  <div class="w-copyrow"><input class="mono" value="{{ mcp_url }}" readonly>
    <button type="button" class="w-mini" onclick="wCopy(this)">Copy</button></div>
</div>
{% if raw_token %}
  <div class="w-field">
    <label>Workspace key — copy it now, it won't be shown again</label>
    <div class="w-copyrow"><input value="{{ raw_token }}" readonly>
      <button type="button" class="w-mini" onclick="wCopy(this)">Copy</button></div>
  </div>
  <div class="w-snip">
    <label>Claude Code</label>
    <div class="w-code"><pre><span class="c"># paste in your terminal</span>
claude mcp add tuckit <span class="k">--transport</span> http {{ mcp_url }} \
  <span class="k">--header</span> <span class="s">"Authorization: Bearer {{ raw_token }}"</span></pre></div>
    <label>MCP JSON</label>
    <div class="w-code"><pre>{
  <span class="k">"mcpServers"</span>: {
    <span class="k">"tuckit"</span>: {
      <span class="k">"url"</span>: <span class="s">"{{ mcp_url }}"</span>,
      <span class="k">"headers"</span>: { <span class="k">"Authorization"</span>: <span class="s">"Bearer {{ raw_token }}"</span> }
    }
  }
}</pre></div>
  </div>
{% else %}
  <button type="button" class="button button-primary" style="margin-top:8px"
          hx-post="{% url 'web:welcome_generate_key' %}" hx-target="#w-key" hx-swap="innerHTML">
    Generate your agent key
  </button>
{% endif %}
```

- [ ] **Step 8: Create the welcome page**

Create `tuckit/web/templates/web/welcome.html`:

```html
{% load static %}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Welcome — tuckit</title>
  <script>
    (function(){var s=localStorage.getItem("theme");if(s==="light"||s==="dark")document.documentElement.dataset.theme=s;})();
  </script>
  <link rel="stylesheet" href="{% static 'web/tokens.brand.css' %}">
  <link rel="stylesheet" href="{% static 'web/tokens.product.css' %}">
  <link rel="stylesheet" href="{% static 'web/base.css' %}">
  <link rel="stylesheet" href="{% static 'web/welcome.css' %}">
  <script defer src="{% static 'web/vendor/alpine.min.js' %}"></script>
  <script src="{% static 'web/vendor/htmx.min.js' %}"></script>
</head>
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  <div class="w-topbar">
    <div class="w-brand">tuck<span>it</span></div>
    <a class="w-skip" href="{% url 'web:home' %}">Skip setup</a>
  </div>
  <main class="w-stage" id="w-stage" x-data="{step:0}" x-cloak>
    <div class="w-dots"><i :class="{on:step===0}"></i><i :class="{on:step===1}"></i></div>

    <section x-show="step===0">
      <p class="w-eyebrow">Welcome to tuckit</p>
      <h1>Nothing your agent does slips past you.</h1>
      <p class="w-lede">You and your AI agent work in <b>one shared workspace</b>. Every idea, change, and shipped feature — written by you or by your agent — lands in the same place. tuckit keeps watch, so <b>nothing quietly rots</b>.</p>
      <div class="w-stream" aria-label="Example activity">
        <div class="w-stream-head"><span>Activity · example</span><span class="w-live"><b></b>live</span></div>
        <div class="w-evt"><span class="w-who agent">🤖</span><span class="w-line"><span class="actor">agent</span><span class="verb">created</span><span class="t">"Retry failed webhooks"</span></span><span class="w-when">2m</span></div>
        <div class="w-evt"><span class="w-who you">👤</span><span class="w-line"><span class="actor">you</span><span class="verb">shipped</span><span class="t">"Login redirect fix"</span></span><span class="w-when">1h</span></div>
        <div class="w-evt" style="background:color-mix(in srgb,var(--warn) 6%,transparent)">
          <span class="w-who you">⚠</span><span class="w-line"><span class="t">"Payment-fail alert"</span></span><span class="w-when">9d</span>
          <span class="w-needs"><span class="w-chip-needs">● Needs you · sat in triage 9 days</span></span>
        </div>
      </div>
      <p class="w-note">That last one? Nobody touched it for 9 days. <b>tuckit surfaced it for you</b> — that's the whole point.</p>
      <div class="w-nav"><div class="grow"></div><button type="button" class="button button-primary" @click="step=1">Connect your agent →</button></div>
    </section>

    <section x-show="step===1" x-cloak>
      <p class="w-eyebrow">Step 1 of 2 · Connect</p>
      <h1>Point your agent at this workspace.</h1>
      <p class="w-lede">Your agent reads and writes tuckit over <b>MCP</b>. Add the endpoint and key below to your agent, then ask it to add something.</p>
      <div id="w-key">{% include "web/partials/_welcome_key.html" %}</div>
      <div class="w-listen">
        <span class="w-radar"></span>
        <span class="lt"><b>Listening for your agent…</b> ask it to capture or create something.</span>
      </div>
      <div class="w-nav"><button type="button" class="button w-ghost" @click="step=0">← Back</button><div class="grow"></div><a class="w-skip" href="{% url 'web:home' %}">Skip for now</a></div>
    </section>
  </main>
  <script>
    function wCopy(b){var i=b.previousElementSibling;i.select&&i.select();try{navigator.clipboard.writeText(i.value)}catch(e){}var o=b.textContent;b.textContent="Copied ✓";setTimeout(function(){b.textContent=o},1200)}
  </script>
</body>
</html>
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_welcome.py tests/web/test_register.py -v`
Expected: PASS — welcome renders standalone, generate-key creates one token + reveals it, signup redirects to `/welcome/`, and existing register behavior tests still pass.

- [ ] **Step 10: Commit**

```bash
git add tuckit/web/views/welcome.py tuckit/web/urls.py tuckit/web/views/accounts.py tuckit/web/templates/web/welcome.html tuckit/web/templates/web/partials/_welcome_key.html tuckit/web/static/web/welcome.css tests/web/test_welcome.py
git commit -m "feat(web): /welcome/ onboarding flow (welcome + connect/generate-key) + signup redirect"
```

---

### Task 3: Live agent-connection detection + celebration

**Files:**
- Modify: `tuckit/web/views/welcome.py` (add `welcome_agent_check`, add `baseline` to `welcome` context)
- Modify: `tuckit/web/urls.py` (add URL)
- Modify: `tuckit/web/templates/web/welcome.html` (poll attrs on the listen panel)
- Create: `tuckit/web/templates/web/partials/_welcome_celebrate.html`
- Test: `tests/web/test_welcome.py` (add)

**Interfaces:**
- Produces URL name `web:welcome_agent_check` (`GET /welcome/agent-activity?since=<id>`). Returns `204` when no agent write after `since`, else the celebration fragment.
- Consumes `ActivityEvent` (`workspace`, `actor`, `id`, `target_label`).

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_welcome.py`:

```python
from tuckit.core.models import ActivityEvent, Slice, Area


@pytest.mark.django_db
def test_agent_check_waits_then_celebrates(client_local, workspace):
    # no agent activity yet → 204
    r = client_local.get("/welcome/agent-activity?since=0")
    assert r.status_code == 204
    # an agent write appears
    ev = ActivityEvent.objects.create(
        workspace=workspace, actor="agent", verb="created",
        target_type="slice", target_id=1, target_label="Draft onboarding checklist",
    )
    r = client_local.get("/welcome/agent-activity?since=0")
    assert r.status_code == 200
    assert "Draft onboarding checklist" in r.content.decode()


@pytest.mark.django_db
def test_agent_check_ignores_human_and_old_events(client_local, workspace):
    old = ActivityEvent.objects.create(
        workspace=workspace, actor="agent", verb="created",
        target_type="slice", target_id=1, target_label="old",
    )
    # a later human event must NOT celebrate
    ActivityEvent.objects.create(
        workspace=workspace, actor="human", verb="created",
        target_type="slice", target_id=2, target_label="mine",
    )
    r = client_local.get(f"/welcome/agent-activity?since={old.id}")
    assert r.status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_welcome.py -k agent_check -v`
Expected: FAIL — `/welcome/agent-activity` 404.

- [ ] **Step 3: Add the view + baseline**

In `tuckit/web/views/welcome.py`, add imports and the view, and add `baseline` to the `welcome` context:

```python
from django.http import HttpResponse

from tuckit.core.models import ActivityEvent
```

In `welcome(request)`'s context dict add:

```python
        "baseline": (
            ActivityEvent.objects.filter(workspace=ws).order_by("-id")
            .values_list("id", flat=True).first() or 0
        ),
```

Add the view:

```python
def welcome_agent_check(request):
    ws = get_current_workspace(request)
    try:
        since = int(request.GET.get("since", "0"))
    except ValueError:
        since = 0
    ev = (
        ActivityEvent.objects.filter(workspace=ws, actor="agent", id__gt=since)
        .order_by("id").first()
    )
    if ev is None:
        return HttpResponse(status=204)
    return render(request, "web/partials/_welcome_celebrate.html", {"event": ev})
```

- [ ] **Step 4: Wire the URL**

In `tuckit/web/urls.py` add:

```python
    path("welcome/agent-activity", welcome_views.welcome_agent_check, name="welcome_agent_check"),
```

- [ ] **Step 5: Create the celebration fragment**

Create `tuckit/web/templates/web/partials/_welcome_celebrate.html`:

```html
<div class="w-dots"><i></i><i></i></div>
<section class="w-celebrate">
  <div class="w-seal"><svg viewBox="0 0 24 24"><path d="M4 12.5l5 5L20 6.5"/></svg></div>
  <p class="w-eyebrow" style="color:var(--good)">Connected</p>
  <h1>Your agent just joined the workspace.</h1>
  <div class="w-won"><span class="w-who agent">🤖</span><span class="w-line"><span class="actor">agent</span><span class="verb">{{ event.verb }}</span><span class="t">"{{ event.target_label }}"</span></span></div>
  <p class="w-lede" style="margin:20px auto 0">From now on you'll see everything it does here — and tuckit will flag anything that needs you.</p>
  <div class="w-nav" style="justify-content:center"><a class="button button-primary" href="{% url 'web:home' %}">Go to your workspace →</a></div>
</section>
```

- [ ] **Step 6: Add polling to the listen panel**

In `tuckit/web/templates/web/welcome.html`, replace the `<div class="w-listen">…</div>` block with the polling version (targets the whole stage; when the agent writes, the celebration fragment replaces the stage contents and polling stops):

```html
      <div class="w-listen"
           hx-get="{% url 'web:welcome_agent_check' %}?since={{ baseline }}"
           hx-trigger="load delay:3s, every 3s"
           hx-target="#w-stage" hx-swap="innerHTML">
        <span class="w-radar"></span>
        <span class="lt"><b>Listening for your agent…</b> ask it to capture or create something.</span>
      </div>
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_welcome.py -v`
Expected: PASS — 204 when no/old/human events, celebration fragment (with the real `target_label`) when an agent write with `id > since` exists.

- [ ] **Step 8: Commit**

```bash
git add tuckit/web/views/welcome.py tuckit/web/urls.py tuckit/web/templates/web/welcome.html tuckit/web/templates/web/partials/_welcome_celebrate.html tests/web/test_welcome.py
git commit -m "feat(web): live agent-connection detection + celebration on /welcome/"
```

---

### Task 4: Home "Get started" checklist + dismiss

**Files:**
- Modify: `tuckit/web/views/pages.py` (`home` context; add `dismiss_onboarding` view)
- Modify: `tuckit/web/urls.py` (dismiss URL)
- Create: `tuckit/web/templates/web/partials/_get_started.html`
- Modify: `tuckit/web/templates/web/home.html` (render the card)
- Modify: `tuckit/web/static/web/app.css` (card styles)
- Test: `tests/web/test_get_started.py`

**Interfaces:**
- Consumes `onboarding_state(workspace)` (Task 1) and `Workspace.onboarding_dismissed`.
- Produces URL `web:onboarding_dismiss` (`POST /onboarding/dismiss`), the checklist partial, and Home context key `onboarding` (the state) + `show_get_started` (bool).

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_get_started.py`:

```python
import pytest

from tuckit.core.models import ApiToken, Area
from tuckit.core.services.slices import create_slice


@pytest.mark.django_db
def test_checklist_shows_on_fresh_home(client_local):
    body = client_local.get("/").content.decode()
    assert "Get started" in body
    assert "Connect your AI agent" in body


@pytest.mark.django_db
def test_checklist_hidden_when_all_done(client_local, workspace):
    ApiToken.objects.create(workspace=workspace, name="a", token_hash="x")
    default = Area.objects.get(workspace=workspace, is_triage=False)
    create_slice(default, "real", status="planned")
    body = client_local.get("/").content.decode()
    assert "Get started" not in body


@pytest.mark.django_db
def test_dismiss_hides_checklist(client_local, workspace):
    r = client_local.post("/onboarding/dismiss")
    assert r.status_code in (200, 204, 302)
    workspace.refresh_from_db()
    assert workspace.onboarding_dismissed is True
    assert "Get started" not in client_local.get("/").content.decode()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_get_started.py -v`
Expected: FAIL — no "Get started" markup, no dismiss URL.

- [ ] **Step 3: Add view context + dismiss view**

In `tuckit/web/views/pages.py`, import and extend `home`:

```python
from django.views.decorators.http import require_POST
from django.shortcuts import redirect

from tuckit.core.services.onboarding import onboarding_state
```

In the `home` view, compute and add to context:

```python
    ob = onboarding_state(ws)
    show_get_started = not ws.onboarding_dismissed and not ob.done
```

…and include `"onboarding": ob, "show_get_started": show_get_started` in the render context.

Add:

```python
@require_POST
def dismiss_onboarding(request):
    ws = get_current_workspace(request)
    ws.onboarding_dismissed = True
    ws.save(update_fields=["onboarding_dismissed"])
    return redirect("web:home")
```

(Ensure `get_current_workspace` is imported in `pages.py`; it already resolves the workspace for `home`.)

- [ ] **Step 4: Wire the dismiss URL**

In `tuckit/web/urls.py` add:

```python
    path("onboarding/dismiss", pages.dismiss_onboarding, name="onboarding_dismiss"),
```

(`pages` is already imported for the other page views.)

- [ ] **Step 5: Create the checklist partial**

Create `tuckit/web/templates/web/partials/_get_started.html`:

```html
<section class="get-started" aria-label="Get started">
  <div class="gs-head">
    <div><h2 class="gs-title">Get started</h2>
      <p class="gs-sub">{{ onboarding.completed }} of 3 done — you're almost set.</p></div>
    <form method="post" action="{% url 'web:onboarding_dismiss' %}">{% csrf_token %}
      <button class="gs-dismiss" type="submit">Dismiss</button></form>
  </div>
  <ul class="gs-list">
    <li class="{% if onboarding.connected %}done{% endif %}">
      <span class="gs-box">✓</span><span class="gs-lbl">Connect your AI agent</span>
      <a class="gs-go" href="{% url 'web:welcome' %}">Connect →</a></li>
    <li class="{% if onboarding.captured %}done{% endif %}">
      <span class="gs-box">✓</span><span class="gs-lbl">Capture your first slice</span>
      <span class="gs-go">press <kbd>C</kbd></span></li>
    <li class="{% if onboarding.triaged %}done{% endif %}">
      <span class="gs-box">✓</span><span class="gs-lbl">Triage it into an area</span>
      <a class="gs-go" href="{% url 'web:triage' %}">Open Triage →</a></li>
  </ul>
</section>
```

- [ ] **Step 6: Render it on Home**

In `tuckit/web/templates/web/home.html`, at the very top of the main content (before the first status group), add:

```html
{% if show_get_started %}{% include "web/partials/_get_started.html" %}{% endif %}
```

- [ ] **Step 7: Add card styles**

Append to `tuckit/web/static/web/app.css` (tokens only — no literal hex/radius):

```css
/* First-run "Get started" checklist card (Home). */
.get-started{border:1px solid var(--line);border-radius:var(--radius);background:var(--surface);
  margin-bottom:24px;overflow:hidden}
.gs-head{display:flex;align-items:flex-start;justify-content:space-between;padding:16px 18px 12px}
.gs-title{margin:0;font-size:16px;font-weight:640;letter-spacing:-.01em}
.gs-sub{margin:2px 0 0;font-size:13px;color:var(--muted)}
.gs-dismiss{background:none;border:0;color:var(--muted);font:inherit;font-size:12.5px;cursor:pointer}
.gs-dismiss:hover{color:var(--text)}
.gs-list{margin:0;padding:0;list-style:none}
.gs-list li{display:flex;align-items:center;gap:12px;padding:12px 18px;border-top:1px solid var(--line);font-size:14.5px}
.gs-box{width:19px;height:19px;border-radius:var(--radius-small);border:1.6px solid var(--line-strong);
  flex:none;display:grid;place-items:center;font-size:11px;color:transparent}
.gs-list li.done .gs-box{background:var(--good);border-color:var(--good);color:var(--paper-raised)}
.gs-lbl{flex:1}
.gs-list li.done .gs-lbl{color:var(--muted);text-decoration:line-through;text-decoration-color:var(--line-strong)}
.gs-go{font-family:var(--mono,ui-monospace);font-size:12px;color:var(--accent);text-decoration:none}
.gs-list li.done .gs-go{visibility:hidden}
.gs-go kbd{font-family:inherit;border:1px solid var(--line);border-radius:var(--radius-small);padding:0 5px}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_get_started.py tests/web/test_home.py -v`
Expected: PASS — checklist shows on fresh Home, hides when all done, Dismiss sets the flag and hides it; existing Home tests still pass.

- [ ] **Step 9: Commit**

```bash
git add tuckit/web/views/pages.py tuckit/web/urls.py tuckit/web/templates/web/partials/_get_started.html tuckit/web/templates/web/home.html tuckit/web/static/web/app.css tests/web/test_get_started.py
git commit -m "feat(web): Home Get-started checklist derived from onboarding state + dismiss"
```

---

### Task 5: Guiding empty states (bounded copy pass)

**Files:**
- Modify: `tuckit/web/templates/web/triage.html` (or `partials/_triage_list.html` empty block)
- Modify: `tuckit/web/templates/web/in_progress.html` (replace Korean)
- Modify: `tuckit/web/templates/web/roadmap.html` (replace bare `—`)
- Test: `tests/web/test_empty_states.py`

**Interfaces:** none (copy only). Do not change any view logic, URL, or context key.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_empty_states.py`:

```python
import pytest


@pytest.mark.django_db
def test_triage_empty_guides(client_local):
    body = client_local.get("/triage/").content.decode()
    assert "Nothing to triage" in body
    assert "let your agent add one" in body


@pytest.mark.django_db
def test_in_progress_empty_is_english(client_local):
    body = client_local.get("/in-progress/").content.decode()
    assert "Nothing in progress" in body
    # no Korean left in the empty copy
    assert "진행 중인" not in body
```

(Confirm the Triage/In-Progress URLs from `urls.py` — adjust the paths in the test if they differ, e.g. `/in_progress/`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_empty_states.py -v`
Expected: FAIL — current copy is "Nothing to triage right now." (no agent line) and Korean in in-progress.

- [ ] **Step 3: Update the empty-state copy**

- Triage empty (in `triage.html` / `_triage_list.html`): set the empty text to
  `Nothing to triage. Capture an idea (press C) — or let your agent add one.`
- In Progress (`in_progress.html`): replace the two Korean strings with
  `Nothing in progress. Slices you move to building show up here.` (slices block) and
  `No bites in progress yet.` (bites block).
- Roadmap (`roadmap.html`): replace each empty column's bare `—` with a faint
  `Nothing here yet` (keep it quiet).

Keep all surrounding markup, classes, and view logic unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_empty_states.py tests/web/test_lens_pages.py -v`
Expected: PASS — new guiding English copy present; existing lens-page tests still pass.

- [ ] **Step 5: Commit**

```bash
git add tuckit/web/templates/web/triage.html tuckit/web/templates/web/in_progress.html tuckit/web/templates/web/roadmap.html tests/web/test_empty_states.py
git commit -m "feat(web): guiding English empty states for triage/in-progress/roadmap"
```

(Adjust the exact file paths in the `git add` if the empty blocks live in partials.)

---

### Task 6: Full-suite + drift + manual render verification

**Files:** none (verification only).

- [ ] **Step 1: Design-system drift/foundation test**

Run: `uv run pytest tests/web/test_design_system.py -v`
Expected: PASS — `welcome.css` is a new screen sheet, not a token file; the drift check and base.html cascade test are unaffected.

- [ ] **Step 2: Full suite**

Run: `uv run pytest`
Expected: PASS — all green. Investigate any unrelated failure before proceeding.

- [ ] **Step 3: No token/hex leakage in welcome.css**

Run: `grep -nE "#[0-9a-fA-F]{3,6}" tuckit/web/static/web/welcome.css`
Expected: no matches (colors come only from `var(--token)` / `color-mix` of tokens). If a hex appears, replace with the matching token.

- [ ] **Step 4: Manual end-to-end render**

Run: `TUCKIT_REGISTRATION_OPEN=1 uv run python manage.py runserver` and, in a browser:
- Register a new account → confirm you are redirected to `/welcome/`.
- Step 1 hero renders (paper texture, activity stream, pulsing "Needs you" chip); light AND dark (`localStorage.setItem('theme','dark')` + reload); 320px width — no horizontal overflow.
- Step 2: "Generate your agent key" reveals a token once and fills both snippets; copy buttons work; the listening panel shows the radar pulse.
- Trigger the live celebration: with the token, create an agent-authored ActivityEvent (e.g. via `manage.py shell`: `ActivityEvent.objects.create(workspace=ws, actor="agent", verb="created", target_type="slice", target_id=1, target_label="Draft onboarding checklist")`) → within ~3s the stage swaps to the celebration with that title.
- Go to Home → the "Get started" checklist shows with "Connect your AI agent" checked; Dismiss hides it.
- Empty states on `/triage/`, `/in-progress/`, `/roadmap/` read as guiding English.
- Keyboard: Tab through the flow — visible focus; reduced-motion disables animation.

- [ ] **Step 5: Stop the dev server.** No commit (verification only).

---

## Notes / out of scope (do not implement here)

- Full English-only sweep (12 templates + 4 services) — separate plan; only empty-state copy on newcomer screens is touched here.
- Seeded sample slices; invited-member onboarding; a "Ship" 4th checklist step.
- Read-only agent connections won't trip the celebration (no `ActivityEvent`); the copy nudges a write and Skip covers it — acceptable per spec.
