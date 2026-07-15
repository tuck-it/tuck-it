# Auth Screens Styling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Style the three standalone auth templates (login, register, invite acceptance) with the existing design system — no behavior, routing, or service changes.

**Architecture:** The auth templates stay standalone HTML (they do NOT extend `web/base.html`, because pre-signup there is no active workspace/sidebar). The shared `<head>` (theme pre-paint script + the token-chain `<link>`s + title) is extracted to a reusable partial `registration/_auth_head.html` that each template includes with its own `page_title`; this avoids duplicating the head across the three pages, matching the codebase's partial-extraction pattern. The chain loaded is `tokens.brand.css → tokens.product.css → base.css → auth.css` (a new sheet). A new `auth.css` holds a centered-card layout built entirely from `var(--token)` values, reusing base.css primitives (`.button`, form focus, typography, fonts, paper texture). Copy is unified to English.

**Tech Stack:** Django templates, static CSS, pytest (Django test client). Run tests with `uv run pytest`.

## Global Constraints

- CSS values use `var(--token)` ONLY — no literal hex, no hardcoded radius (`--radius` for the 14px card, `--radius-small` for 9px controls).
- `auth.css` is a new **screen** sheet, not a token file — it does NOT participate in the brand-token drift check and must NOT redefine any `--token`.
- Auth templates load `tokens.brand.css → tokens.product.css → base.css → auth.css` in that order (via the shared `registration/_auth_head.html` partial), and do **NOT** link `app.css`.
- Auth templates do **NOT** extend `web/base.html`. The shared `<head>` lives in the partial `registration/_auth_head.html`, included with a `page_title` argument per page (title format: `<page_title> — tuckit`).
- Protected (must not change): URL names (`web:login`/`web:register`/`web:invite_accept`), form field **names** (`username`, `password`, `email`, `org_name`, `slug`), field order, the `next` hidden field on login, `REGISTRATION_OPEN` gating + invite bypass, the invite screen's three-state conditional (invalid / authenticated join / anonymous signup with locked email), all view/service logic, tenant isolation, license copy, public/private repo boundary (no billing/pricing copy).
- Copy language: **English**.
- `docs/superpowers/` stays untracked (already gitignored) — never commit the spec/plan.

---

### Task 1: Create `auth.css` and migrate the login screen

**Files:**
- Create: `tuckit/web/static/web/auth.css`
- Create: `tuckit/web/templates/registration/_auth_head.html` (shared head partial)
- Modify: `tuckit/web/templates/registration/login.html` (full rewrite)
- Test: `tests/web/test_auth_screens.py` (new)

**Interfaces:**
- Produces CSS classes consumed by Tasks 2 & 3: `.auth-shell`, `.auth-card`, `.auth-brand`, `.auth-title`, `.auth-sub`, `.auth-form`, `.auth-field` (wraps `label` + `input`), `.auth-error`, `.auth-note`, `.auth-alt`. Submit buttons reuse base.css `.button.button-primary`.
- Produces `registration/_auth_head.html`, consumed by Tasks 2 & 3 via `{% include "registration/_auth_head.html" with page_title="<Title>" %}`. It renders the full `<head>` element (meta, `<title>{{ page_title }} — tuckit</title>`, theme script, the four `<link>`s). Callers keep their own `{% load static %}`, `<!doctype html>`, `<html lang="en">`, `<body>`.
- The `registration/login.html` template is rendered by Django's built-in `LoginView` (wired at `tuckit/web/urls.py`), whose context provides `form` (an `AuthenticationForm` with fields `username`, `password`) and `next`.

- [ ] **Step 1: Write the failing test**

Create `tests/web/test_auth_screens.py`:

```python
import pytest


@pytest.mark.django_db
def test_login_screen_uses_design_system(client, workspace):
    body = client.get("/login/").content.decode()
    # standalone page, English, not the app shell
    assert '<html lang="en"' in body
    assert 'class="auth-card"' in body
    # token chain linked in order, ending in auth.css; app.css NOT linked
    i_brand = body.find("tokens.brand.css")
    i_product = body.find("tokens.product.css")
    i_base = body.find("web/base.css")
    i_auth = body.find("web/auth.css")
    assert -1 not in (i_brand, i_product, i_base, i_auth)
    assert i_brand < i_product < i_base < i_auth
    assert "web/app.css" not in body
    # login form fields preserved (names unchanged)
    assert 'name="username"' in body
    assert 'name="password"' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_auth_screens.py::test_login_screen_uses_design_system -v`
Expected: FAIL — current `login.html` is bare (`{{ form.as_p }}`, no `auth-card`, no stylesheet links).

- [ ] **Step 3: Create `auth.css`**

Create `tuckit/web/static/web/auth.css`:

```css
/* Auth screens (login, register, invite acceptance).
   Standalone pages that do NOT extend web/base.html — no app shell/sidebar.
   Loaded after tokens.brand + tokens.product + base.css; NOT with app.css.
   Values use var(--token) only — no literal hex, no hardcoded radius. */

.auth-shell {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 20px;
  box-sizing: border-box;
}

.auth-card {
  width: 100%;
  max-width: 380px;
  box-sizing: border-box;
  background: var(--paper-raised);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  box-shadow: 0 4px 20px var(--shadow);
  padding: 32px 28px;
}

.auth-brand {
  font-weight: 650;
  letter-spacing: -0.02em;
  color: var(--ink);
  margin-bottom: 20px;
}

.auth-title { margin-bottom: 6px; }

.auth-sub {
  color: var(--ink-soft);
  font-size: 14px;
  margin: 0 0 24px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.auth-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.auth-field label {
  font-size: 13px;
  font-weight: 560;
  color: var(--ink-soft);
}

.auth-field input {
  width: 100%;
  box-sizing: border-box;
  min-height: 40px;
  padding: 0 12px;
  background: var(--paper-solid);
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: var(--radius-small);
}
/* focus border comes from the base.css input:focus-visible primitive */

.auth-form .button { width: 100%; margin-top: 4px; }

.auth-error {
  margin-bottom: 20px;
  padding: 10px 12px;
  border: 1px solid var(--warn);
  border-radius: var(--radius-small);
  color: var(--warn);
  font-size: 14px;
}

.auth-note {
  color: var(--ink-soft);
  font-size: 14px;
  margin: 0 0 4px;
}
.auth-note strong { color: var(--ink); font-weight: 560; }

.auth-alt {
  margin-top: 20px;
  font-size: 14px;
  color: var(--ink-soft);
  text-align: center;
}
.auth-alt a { color: var(--blue); }
```

- [ ] **Step 4: Create the shared head partial `_auth_head.html`**

Create `tuckit/web/templates/registration/_auth_head.html`:

```html
{% load static %}
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ page_title }} — tuckit</title>
  <script>
    /* Apply saved theme before first paint (no flash). Absent a choice,
       brand tokens fall back to prefers-color-scheme. */
    (function () {
      var saved = localStorage.getItem("theme");
      if (saved === "light" || saved === "dark") {
        document.documentElement.dataset.theme = saved;
      }
    })();
  </script>
  <link rel="stylesheet" href="{% static 'web/tokens.brand.css' %}">
  <link rel="stylesheet" href="{% static 'web/tokens.product.css' %}">
  <link rel="stylesheet" href="{% static 'web/base.css' %}">
  <link rel="stylesheet" href="{% static 'web/auth.css' %}">
</head>
```

- [ ] **Step 5: Rewrite `login.html`**

Replace the entire contents of `tuckit/web/templates/registration/login.html`:

```html
{% load static %}
<!doctype html>
<html lang="en">
{% include "registration/_auth_head.html" with page_title="Log in" %}
<body>
  <main class="auth-shell">
    <div class="auth-card">
      <div class="auth-brand">tuckit</div>
      <h1 class="auth-title">Log in</h1>
      {% if form.non_field_errors %}
        <div class="auth-error">{{ form.non_field_errors|join:" " }}</div>
      {% endif %}
      <form method="post" class="auth-form">
        {% csrf_token %}
        <div class="auth-field">
          <label for="{{ form.username.id_for_label }}">Email</label>
          {{ form.username }}
        </div>
        <div class="auth-field">
          <label for="{{ form.password.id_for_label }}">Password</label>
          {{ form.password }}
        </div>
        {% if next %}<input type="hidden" name="next" value="{{ next }}">{% endif %}
        <button type="submit" class="button button-primary">Log in</button>
      </form>
    </div>
  </main>
</body>
</html>
```

Note: `{{ form.username }}` / `{{ form.password }}` render Django's inputs with the correct `name`/`id`; `.auth-field input` styles them by descendant selector, so no widget class is needed. The label reads "Email" because registered users log in with their email (username == email), while the field name stays `username` (protected).

- [ ] **Step 6: Run the new test and the existing auth behavior tests**

Run: `uv run pytest tests/web/test_auth_screens.py::test_login_screen_uses_design_system tests/web/test_auth.py -v`
Expected: PASS (new markup test passes; existing behavior tests — redirect-to-login, login grants access, healthcheck — still pass since they assert behavior, not markup).

- [ ] **Step 7: Commit**

```bash
git add tuckit/web/static/web/auth.css tuckit/web/templates/registration/_auth_head.html tuckit/web/templates/registration/login.html tests/web/test_auth_screens.py
git commit -m "feat(web): style login screen with design system + add auth.css"
```

---

### Task 2: Migrate the register screen

**Files:**
- Modify: `tuckit/web/templates/registration/register.html` (full rewrite)
- Test: `tests/web/test_auth_screens.py` (add a test)

**Interfaces:**
- Consumes the `.auth-*` classes and `auth.css` from Task 1.
- Rendered by `register_view` (`tuckit/web/views/accounts.py`): context provides `values` (previous POST, for re-render) and optional `error` (string). Field names required by the `register` service: `email`, `org_name`, `slug`, `password`.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_auth_screens.py`:

```python
from django.test import override_settings


@pytest.mark.django_db
@override_settings(REGISTRATION_OPEN=True)
def test_register_screen_uses_design_system(client):
    body = client.get("/register/").content.decode()
    assert 'class="auth-card"' in body
    assert "web/auth.css" in body
    assert "web/app.css" not in body
    for name in ("email", "org_name", "slug", "password"):
        assert f'name="{name}"' in body


@pytest.mark.django_db
@override_settings(REGISTRATION_OPEN=True)
def test_register_duplicate_slug_shows_styled_error(client):
    from tuckit.core.models import Org
    Org.objects.create(name="Taken", slug="taken")
    resp = client.post("/register/", {
        "email": "new@x.com", "org_name": "X", "slug": "taken", "password": "pw123456",
    })
    assert resp.status_code == 200
    assert 'class="auth-error"' in resp.content.decode()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_auth_screens.py::test_register_screen_uses_design_system tests/web/test_auth_screens.py::test_register_duplicate_slug_shows_styled_error -v`
Expected: FAIL — current `register.html` has no `auth-card`/`auth.css`/`auth-error`.

- [ ] **Step 3: Rewrite `register.html`**

Replace the entire contents of `tuckit/web/templates/registration/register.html`:

```html
{% load static %}
<!doctype html>
<html lang="en">
{% include "registration/_auth_head.html" with page_title="Create your account" %}
<body>
  <main class="auth-shell">
    <div class="auth-card">
      <div class="auth-brand">tuckit</div>
      <h1 class="auth-title">Create your account</h1>
      {% if error %}<div class="auth-error">{{ error }}</div>{% endif %}
      <form method="post" class="auth-form">
        {% csrf_token %}
        <div class="auth-field">
          <label for="reg-email">Email</label>
          <input id="reg-email" type="email" name="email" value="{{ values.email }}" required>
        </div>
        <div class="auth-field">
          <label for="reg-org">Organization name</label>
          <input id="reg-org" name="org_name" value="{{ values.org_name }}" required>
        </div>
        <div class="auth-field">
          <label for="reg-slug">Organization slug</label>
          <input id="reg-slug" name="slug" value="{{ values.slug }}" required>
        </div>
        <div class="auth-field">
          <label for="reg-password">Password</label>
          <input id="reg-password" type="password" name="password" required>
        </div>
        <button type="submit" class="button button-primary">Create account</button>
      </form>
    </div>
  </main>
</body>
</html>
```

- [ ] **Step 4: Run the register tests (new + existing behavior)**

Run: `uv run pytest tests/web/test_auth_screens.py tests/web/test_register.py -v`
Expected: PASS — new markup tests pass; existing `test_register.py` (404 when closed, creates account + logs in, duplicate slug re-render) still passes (field names + behavior unchanged).

- [ ] **Step 5: Commit**

```bash
git add tuckit/web/templates/registration/register.html tests/web/test_auth_screens.py
git commit -m "feat(web): style register screen with design system"
```

---

### Task 3: Migrate the invite-acceptance screen

**Files:**
- Modify: `tuckit/web/templates/registration/invite_accept.html` (full rewrite)
- Modify: `tests/web/test_invite_accept.py` (update the invalid-copy assertion)
- Test: `tests/web/test_auth_screens.py` (add a test)

**Interfaces:**
- Consumes the `.auth-*` classes from Task 1.
- Rendered by `invite_accept` view (`tuckit/web/views/accounts.py`): context is either `{"invalid": True}`, or `{"invitation": <Invitation>}` (optionally with `error`). Three UI states: invalid link; authenticated user (join button only); anonymous (locked `invitation.email` note + `password` field). Field name `password` is protected.

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_auth_screens.py`:

```python
from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.invitations import create_invitation


@pytest.mark.django_db
def test_invite_screen_uses_design_system(client):
    org = Org.objects.create(name="Acme", slug="acme")
    owner = User.objects.create(username="o@a.com", email="o@a.com")
    OrgMember.objects.create(user=owner, org=org, role="owner")
    inv = create_invitation(org=org, email="new@x.com", role="member", invited_by=owner)
    body = client.get(f"/invite/{inv.token}/").content.decode()
    assert 'class="auth-card"' in body
    assert "web/auth.css" in body
    assert "web/app.css" not in body
    assert "Join Acme" in body          # English heading with org name
    assert "new@x.com" in body          # locked email shown for anonymous invitee
    assert 'name="password"' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/web/test_auth_screens.py::test_invite_screen_uses_design_system -v`
Expected: FAIL — current `invite_accept.html` is bare Korean HTML (no `auth-card`, no "Join Acme").

- [ ] **Step 3: Rewrite `invite_accept.html`**

Replace the entire contents of `tuckit/web/templates/registration/invite_accept.html`:

```html
{% load static %}
<!doctype html>
<html lang="en">
{% include "registration/_auth_head.html" with page_title="Invitation" %}
<body>
  <main class="auth-shell">
    <div class="auth-card">
      <div class="auth-brand">tuckit</div>
      {% if invalid %}
        <h1 class="auth-title">This invite link is no longer valid</h1>
        <p class="auth-sub">It may have already been used or canceled.</p>
      {% else %}
        <h1 class="auth-title">Join {{ invitation.org.name }}</h1>
        {% if error %}<div class="auth-error">{{ error }}</div>{% endif %}
        <form method="post" class="auth-form">
          {% csrf_token %}
          {% if not user.is_authenticated %}
            <p class="auth-note">Signing up as <strong>{{ invitation.email }}</strong></p>
            <div class="auth-field">
              <label for="inv-password">Password</label>
              <input id="inv-password" type="password" name="password" required>
            </div>
          {% endif %}
          <button type="submit" class="button button-primary">Join</button>
        </form>
      {% endif %}
    </div>
  </main>
</body>
</html>
```

- [ ] **Step 4: Update the invalid-copy assertion in the existing test**

The English rewrite removes the words "invalid" and "유효하지". In `tests/web/test_invite_accept.py`, find the last assertion in `test_used_token_shows_invalid`:

```python
    assert b"invalid" in resp.content.lower() or "유효하지".encode() in resp.content
```

Replace it with:

```python
    assert b"no longer valid" in resp.content.lower()
```

- [ ] **Step 5: Run the invite tests (new markup + updated behavior)**

Run: `uv run pytest tests/web/test_auth_screens.py::test_invite_screen_uses_design_system tests/web/test_invite_accept.py -v`
Expected: PASS — new markup test passes; the four existing invite tests (anon register via invite when closed, logged-in matching-email join, mismatched-email rejected, used-token shows invalid) pass, including the updated invalid-copy assertion.

- [ ] **Step 6: Commit**

```bash
git add tuckit/web/templates/registration/invite_accept.html tests/web/test_invite_accept.py tests/web/test_auth_screens.py
git commit -m "feat(web): style invite acceptance screen; unify auth copy to English"
```

---

### Task 4: Full-suite + drift check + manual render verification

**Files:** none (verification only).

- [ ] **Step 1: Run the design-system drift/foundation test**

Run: `uv run pytest tests/web/test_design_system.py -v`
Expected: PASS — `auth.css` is a new screen sheet, not a token file, so the brand-token drift check and the `base.html` cascade-order test are unaffected. (If `test_brand_tokens_match_landing_when_sibling_present` runs, it only compares `tokens.brand.css`, which we did not touch.)

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest`
Expected: PASS — all tests green. If any unrelated test fails, stop and investigate before proceeding.

- [ ] **Step 3: Manual render check — start the dev server**

Run: `TUCKIT_REGISTRATION_OPEN=1 uv run python manage.py runserver` (background), then open in a browser:
- `http://127.0.0.1:8000/login/`
- `http://127.0.0.1:8000/register/`
- an invite URL (create one from `/settings/invites` while logged in, or via `create_invitation` in `manage.py shell`), e.g. `http://127.0.0.1:8000/invite/<token>/`

Verify for each screen, per the playbook matrix subset:
- Centered card on paper background; texture visible.
- Light AND dark theme (toggle via devtools `prefers-color-scheme`, or run `localStorage.setItem('theme','dark')` then reload) — equivalent hierarchy, readable.
- 320px width (devtools responsive) — no horizontal overflow, card padding intact.
- Keyboard-only: Tab through fields → visible blue focus ring; Enter submits.
- Error state: submit `/register/` with a duplicate slug → styled `.auth-error` banner.
- Invite anonymous state shows the locked email note; used/cancelled invite shows the "no longer valid" card.

- [ ] **Step 4: Confirm no token/hex leakage**

Run: `grep -nE "#[0-9a-fA-F]{3,6}|[0-9]+px" tuckit/web/static/web/auth.css`
Expected: only the `box-shadow` offset/blur px values (`0 4px 20px`) and control sizing px (`padding`, `min-height`) appear — **no hex colors**, and **no** `14px`/`9px` radius literals (radius comes from `var(--radius)` / `var(--radius-small)`). If a hex color or a radius literal appears, replace it with the corresponding token.

- [ ] **Step 5: Stop the dev server.** No commit (verification only).

---

## Notes / out of scope (do not implement here)

- Password reset/change — **next step**, separate spec/plan.
- Email verification, social login, account-profile editing.
- The register screen intentionally has **no** "Forgot password?" link and **no** "Create an account" cross-link this pass (reset doesn't exist; keep scope tight).
- Server-side validation messages from the `register` service may still contain Korean (e.g. the empty-password message). That lives in the service layer (`core/services/accounts.py`), not the templates — out of scope for this styling pass.
- `tuckit-cloud` billing/upgrade surfaces (playbook Phase 6) — not here; core stays free of billing copy.
