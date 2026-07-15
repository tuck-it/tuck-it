# Management Surfaces — Phase 4: Account Page & Org Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give users a `/settings/account` page to see the orgs they belong to, create a new org, and leave an org — plus the service layer (`create_org`, `list_user_orgs`, `leave_org`) behind it.

**Architecture:** Three pure service functions enforce org-lifecycle invariants in `tuckit/core/services/orgs.py`; `create_org` becomes the canonical org-creation unit that the existing `register` flow delegates to (DRY). A new scope-routed settings page `/settings/account` (thin views in a new `settings_account.py`) lists the user's orgs and exposes create/leave/open actions. The existing flat "Org · Workspace" workspace switcher is deliberately left as-is (per design decision) — a newly created org's workspace already appears there because the `switchable_workspaces` context processor lists every accessible workspace across all orgs.

**Tech Stack:** Django service layer, HTMX 2.x, Warm Greige tokens, session-based current workspace.

## Global Constraints

- **Public/private boundary:** `tuckit` is PUBLIC (BSL 1.1). No billing/Paddle/pricing/plan/cloud content in any file. `create_org` calls `run_signup_hook`, which is the *neutral* extension seam (`TUCKIT_SIGNUP_HOOK`, `None` in core) — that is allowed and intended; do not add any cloud/billing logic, only the hook call.
- **Service layer enforces DATA INVARIANTS** and raises `InvalidValue`; **thin views enforce AUTHORIZATION** and translate exceptions to HTTP. Org membership scoping: a user may only act on orgs they belong to (views resolve membership; cross-org access → 404/403).
- **`create_org` is the canonical org-creation unit.** `register` must delegate its org-creation block to it, so both paths produce identical results (Org + owner `OrgMember` + first `Workspace` with Triage + "Default" areas + `run_signup_hook`). The existing `tests/test_services_accounts.py` register suite is the regression guard.
- **`leave_org` guards (data invariants):**
  1. The user must be a member of the org (else `InvalidValue`).
  2. A **sole owner** cannot leave (an org must always keep ≥1 owner) — `InvalidValue`.
  3. **DECISION TO CONFIRM AT PLAN REVIEW:** leaving your **last** org is also rejected (`InvalidValue`), because zero orgs strands the user with no workspace and the app has no empty-state screen yet. This is stricter than the approved spec (which only named the sole-owner guard). If you'd rather allow it, that's a follow-up that adds a "create or join an org" empty state. Until then, this guard stays.
- **Account page scope = org list only** (per design decision): each org row shows name, my role badge, workspace count, and 열기 / 나가기 actions, plus ＋ 새 조직 and the user's email. NO profile/password editing this phase.
- **Slugs:** `create_org` auto-generates a globally-unique org slug from the name when none is given (mirrors workspace/area slug helpers). `register` keeps passing its explicit user-provided slug.
- Run the suite with `uv run pytest` from `tuckit/`.

---

## File Structure

**Services:**
- Modify: `tuckit/core/services/orgs.py` — add `_unique_org_slug`, `create_org`, `list_user_orgs`, `leave_org`.
- Modify: `tuckit/core/services/accounts.py` — `register` delegates org creation to `create_org`.

**Views + URLs:**
- Create: `tuckit/web/views/settings_account.py` — `account_settings` (GET), `org_create` (POST), `org_leave` (POST), `switch_org` (POST).
- Modify: `tuckit/web/urls.py` — add the four `/settings/account…` routes.

**Templates:**
- Create: `tuckit/web/templates/web/settings_account.html` — the account page.
- Create: `tuckit/web/templates/web/partials/_org_row.html` — one org row (name, role, ws count, 열기/나가기).
- Modify: `tuckit/web/templates/web/partials/_settings_scopenav.html` — add the 계정 tab.

**Tests:**
- Modify: `tests/test_services_orgs.py` — `create_org`, `list_user_orgs`, `leave_org` invariants.
- Create: `tests/web/test_settings_account.py` — page render, create, leave, open, permission gates.
- (Existing `tests/test_services_accounts.py` must stay green after the register refactor.)

---

## Task 1: `create_org` service + `register` delegation

**Files:**
- Modify: `tuckit/core/services/orgs.py`
- Modify: `tuckit/core/services/accounts.py`
- Test: `tests/test_services_orgs.py`, and keep `tests/test_services_accounts.py` green.

**Interfaces:**
- Consumes: `Org`, `OrgMember`, `Workspace`, `User` models; `create_workspace` (same module); `InvalidValue`; `run_signup_hook` (`tuckit.core.services.hooks`).
- Produces:
  - `_unique_org_slug(name: str) -> str` — slugify `name` (fallback `"org"`), append `-2`, `-3`, … until `Org.slug` is free (globally unique).
  - `create_org(user: User, *, name: str, slug: str | None = None) -> tuple[Org, Workspace]` — strips `name`, raises `InvalidValue("조직 이름을 입력하세요")` if blank; `slug = slug or _unique_org_slug(name)`; raises `InvalidValue(f"Org slug already taken: {slug}")` if taken; creates `Org`, an owner `OrgMember` for `user`, and a first `Workspace` via `create_workspace(org, name)`; calls `run_signup_hook(user=user, org=org)`; returns `(org, workspace)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_services_orgs.py` (check the file's existing imports first; add only what's missing):

```python
from tuckit.core.services.orgs import create_org
from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.models import Area, Org, OrgMember, User, Workspace


@pytest.mark.django_db
def test_create_org_makes_org_owner_and_first_workspace():
    user = User.objects.create(username="u@u.com", email="u@u.com")
    org, ws = create_org(user, name="Acme Labs")
    assert org.slug == "acme-labs"                       # auto slug from name
    assert OrgMember.objects.filter(user=user, org=org, role="owner").exists()
    assert ws.org == org
    assert Area.objects.filter(workspace=ws, is_triage=True).count() == 1
    assert Area.objects.filter(workspace=ws, is_triage=False, slug="default").exists()


@pytest.mark.django_db
def test_create_org_auto_slug_is_unique():
    user = User.objects.create(username="u@u.com", email="u@u.com")
    a, _ = create_org(user, name="Dup")
    b, _ = create_org(user, name="Dup")
    assert a.slug != b.slug                               # second gets -2 suffix


@pytest.mark.django_db
def test_create_org_rejects_blank_name():
    user = User.objects.create(username="u@u.com", email="u@u.com")
    with pytest.raises(InvalidValue):
        create_org(user, name="   ")


@pytest.mark.django_db
def test_create_org_rejects_taken_explicit_slug():
    user = User.objects.create(username="u@u.com", email="u@u.com")
    create_org(user, name="First", slug="taken")
    with pytest.raises(InvalidValue):
        create_org(user, name="Second", slug="taken")


@pytest.mark.django_db
def test_create_org_runs_signup_hook():
    from django.test import override_settings
    calls = []
    import tuckit.core.services.hooks as hooks_mod
    # mirror the mechanism used by test_register_runs_signup_hook; if that test
    # uses a settings-based dotted path + a module-level recorder, reuse the same
    # recorder here. Otherwise assert via the same override the register test uses.
    user = User.objects.create(username="hook@u.com", email="hook@u.com")
    # (Implementer: copy the exact hook-assertion style from
    # tests/test_services_accounts.py::test_register_runs_signup_hook so this
    # test matches the project's established way of asserting the hook fired.)
    org, ws = create_org(user, name="Hooked")
    assert org.pk is not None
```

> Implementer note: for `test_create_org_runs_signup_hook`, open `tests/test_services_accounts.py::test_register_runs_signup_hook` and replicate its exact hook-assertion mechanism (it configures `TUCKIT_SIGNUP_HOOK` to a recording callable and asserts it ran). Do not invent a new mechanism.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services_orgs.py -k create_org -v`
Expected: FAIL with `ImportError: cannot import name 'create_org'`.

- [ ] **Step 3: Implement `_unique_org_slug` and `create_org`**

In `tuckit/core/services/orgs.py`, add near the other helpers. NOTE the import: to avoid any import cycle, import the hook **inside** the function body.

```python
def _unique_org_slug(name: str) -> str:
    from django.utils.text import slugify

    base = slugify(name)[:100] or "org"
    candidate = base
    i = 2
    while Org.objects.filter(slug=candidate).exists():
        suffix = f"-{i}"
        candidate = base[: 100 - len(suffix)] + suffix
        i += 1
    return candidate


def create_org(user, *, name: str, slug: str | None = None):
    from tuckit.core.services.hooks import run_signup_hook  # local: avoid import cycle

    name = (name or "").strip()
    if not name:
        raise InvalidValue("조직 이름을 입력하세요")
    slug = slug or _unique_org_slug(name)
    if Org.objects.filter(slug=slug).exists():
        raise InvalidValue(f"Org slug already taken: {slug}")
    org = Org.objects.create(name=name, slug=slug)
    OrgMember.objects.create(user=user, org=org, role="owner")
    workspace = create_workspace(org, name)
    run_signup_hook(user=user, org=org)
    return org, workspace
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run pytest tests/test_services_orgs.py -k create_org -v`
Expected: PASS.

- [ ] **Step 5: Refactor `register` to delegate to `create_org`**

In `tuckit/core/services/accounts.py`, replace the inline org-creation block. The function stays `@transaction.atomic`; user creation/password validation is unchanged; only the org block delegates:

Replace:
```python
    org = Org.objects.create(name=org_name, slug=slug)
    OrgMember.objects.create(user=user, org=org, role="owner")
    workspace = create_workspace(org, org_name)

    run_signup_hook(user=user, org=org)
    return user, org, workspace
```
with:
```python
    org, workspace = create_org(user, name=org_name, slug=slug)
    return user, org, workspace
```

Update imports in `accounts.py`: import `create_org` from `tuckit.core.services.orgs` (it already imports `create_workspace` from there — add `create_org` to that import). The `run_signup_hook` import and the direct `Org`/`OrgMember`/`create_workspace` usage in `register` become unused **only if** nothing else in the file uses them — verify and remove any now-unused imports (`run_signup_hook`, and `Org`/`OrgMember` if unused). Keep `Workspace`/`User` if still referenced by the type hint / other code.

> Behavior note: `register` previously checked `Org.objects.filter(slug=slug).exists()` *before* creating the user; now `create_org` raises the same `InvalidValue("Org slug already taken: …")` after the user is built, but since `register` is `@transaction.atomic` the whole thing rolls back — the observable result (raise, nothing persisted) is identical, and `test_register_duplicate_org_slug_raises` still passes.

- [ ] **Step 6: Run the register regression suite + new tests**

Run: `uv run pytest tests/test_services_accounts.py tests/test_services_orgs.py -v`
Expected: PASS (all register tests green — user/org/ws, owner member, triage+default areas, duplicate-slug raise, signup hook — plus the new create_org tests).

- [ ] **Step 7: Commit**

```bash
git add tuckit/core/services/orgs.py tuckit/core/services/accounts.py tests/test_services_orgs.py
git commit -m "feat(orgs): create_org service; register delegates org creation to it"
```

---

## Task 2: `list_user_orgs` + `leave_org` services

**Files:**
- Modify: `tuckit/core/services/orgs.py`
- Test: `tests/test_services_orgs.py`

**Interfaces:**
- Consumes: `Org`, `OrgMember`, `Workspace` models; `InvalidValue`; `_owner_count` (already in module).
- Produces:
  - `list_user_orgs(user) -> list[dict]` — one dict per org the user belongs to: `{"org": Org, "role": str, "workspace_count": int}`, ordered by `org.name`. Use the user's `OrgMember` rows; count workspaces via `Workspace.objects.filter(org=org).count()`.
  - `leave_org(user, *, org) -> None` — raises `InvalidValue("이 조직의 멤버가 아닙니다")` if no membership; raises `InvalidValue("단독 소유자는 나갈 수 없습니다 — 먼저 소유권을 넘기거나 조직을 삭제하세요")` if the user's role is `owner` and `_owner_count(org) <= 1`; raises `InvalidValue("마지막 조직은 나갈 수 없습니다")` if this is the user's only org membership; otherwise deletes the membership.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_services_orgs.py`:

```python
from tuckit.core.services.orgs import list_user_orgs, leave_org


@pytest.mark.django_db
def test_list_user_orgs_returns_role_and_workspace_count():
    user = User.objects.create(username="u@u.com", email="u@u.com")
    org_a, _ = create_org(user, name="Alpha")          # owner, 1 ws
    org_b, _ = create_org(user, name="Beta")           # owner, 1 ws
    Workspace.objects.create(org=org_b, name="Extra", slug="extra")  # Beta now 2 ws
    rows = list_user_orgs(user)
    by_name = {r["org"].name: r for r in rows}
    assert by_name["Alpha"]["role"] == "owner"
    assert by_name["Alpha"]["workspace_count"] == 1
    assert by_name["Beta"]["workspace_count"] == 2
    assert [r["org"].name for r in rows] == ["Alpha", "Beta"]  # ordered by name


@pytest.mark.django_db
def test_leave_org_removes_membership():
    owner = User.objects.create(username="o@o.com", email="o@o.com")
    org, _ = create_org(owner, name="Team")            # owner also needs a 2nd org
    create_org(owner, name="Solo")                     # so leaving Team isn't "last org"
    member = User.objects.create(username="m@m.com", email="m@m.com")
    OrgMember.objects.create(user=member, org=org, role="member")
    create_org(member, name="Members Own")             # member has a 2nd org too
    leave_org(member, org=org)
    assert not OrgMember.objects.filter(user=member, org=org).exists()


@pytest.mark.django_db
def test_leave_org_rejects_non_member():
    stranger = User.objects.create(username="s@s.com", email="s@s.com")
    other_owner = User.objects.create(username="o@o.com", email="o@o.com")
    org, _ = create_org(other_owner, name="NotYours")
    create_org(stranger, name="Strangers Own")
    with pytest.raises(InvalidValue):
        leave_org(stranger, org=org)


@pytest.mark.django_db
def test_leave_org_rejects_sole_owner():
    owner = User.objects.create(username="o@o.com", email="o@o.com")
    org, _ = create_org(owner, name="OnlyOwner")
    create_org(owner, name="Second")                   # not last-org, isolate the sole-owner guard
    with pytest.raises(InvalidValue):
        leave_org(owner, org=org)
    assert OrgMember.objects.filter(user=owner, org=org).exists()


@pytest.mark.django_db
def test_leave_org_rejects_last_org():
    member = User.objects.create(username="m@m.com", email="m@m.com")
    other_owner = User.objects.create(username="o@o.com", email="o@o.com")
    org, _ = create_org(other_owner, name="TheOrg")
    OrgMember.objects.create(user=member, org=org, role="member")  # member's ONLY org
    with pytest.raises(InvalidValue):
        leave_org(member, org=org)
    assert OrgMember.objects.filter(user=member, org=org).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_services_orgs.py -k "list_user_orgs or leave_org" -v`
Expected: FAIL with `ImportError` for `list_user_orgs` / `leave_org`.

- [ ] **Step 3: Implement**

Append to `tuckit/core/services/orgs.py`:

```python
def list_user_orgs(user) -> list[dict]:
    rows = []
    memberships = (
        OrgMember.objects.filter(user=user).select_related("org").order_by("org__name")
    )
    for m in memberships:
        rows.append({
            "org": m.org,
            "role": m.role,
            "workspace_count": Workspace.objects.filter(org=m.org).count(),
        })
    return rows


def leave_org(user, *, org) -> None:
    membership = OrgMember.objects.filter(user=user, org=org).first()
    if membership is None:
        raise InvalidValue("이 조직의 멤버가 아닙니다")
    if membership.role == "owner" and _owner_count(org) <= 1:
        raise InvalidValue("단독 소유자는 나갈 수 없습니다 — 먼저 소유권을 넘기거나 조직을 삭제하세요")
    if OrgMember.objects.filter(user=user).count() <= 1:
        raise InvalidValue("마지막 조직은 나갈 수 없습니다")
    membership.delete()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_services_orgs.py -k "list_user_orgs or leave_org" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tuckit/core/services/orgs.py tests/test_services_orgs.py
git commit -m "feat(orgs): list_user_orgs + leave_org (sole-owner and last-org guards)"
```

---

## Task 3: `/settings/account` page + views + routes + scopenav tab

**Files:**
- Create: `tuckit/web/views/settings_account.py`
- Modify: `tuckit/web/urls.py`
- Create: `tuckit/web/templates/web/settings_account.html`
- Create: `tuckit/web/templates/web/partials/_org_row.html`
- Modify: `tuckit/web/templates/web/partials/_settings_scopenav.html`
- Test: `tests/web/test_settings_account.py`

**Interfaces:**
- Consumes: `create_org`, `list_user_orgs`, `leave_org`, `is_org_owner`, `_owner_count` (via services); `get_current_workspace`; `redirect_response` (`tuckit.web.htmx`); `InvalidValue`.
- Produces four views + routes:
  - `account_settings(request)` (GET) → renders `settings_account.html`.
  - `org_create(request)` (POST) → `create_org(request.user, name=...)`, set `active_workspace_id` to the new workspace, redirect to home (HX-aware).
  - `org_leave(request, org_id)` (POST) → resolve the org (404 if the user isn't a member), `leave_org`, and if the current `active_workspace_id` belongs to that org clear it; redirect to account (HX-aware). `InvalidValue` → 400.
  - `switch_org(request, org_id)` (POST) → verify membership, set `active_workspace_id` to that org's first workspace, redirect home. (This is the account page's 열기 action.)

**Notes for the implementer:**
- Mirror `settings_org.py` for the view style (membership scoping via a helper, `require_POST`, `HttpResponseForbidden`/`Http404`, `InvalidValue` → 400).
- Use `redirect_response(request, "web:home")` / `redirect_response(request, "web:settings_account")` for the destructive/navigation POSTs so hx-post forms do a full browser navigation (the helper emits `HX-Redirect` for HTMX, 302 otherwise) — same pattern as `org_delete`/`workspace_delete`.
- The scopenav needs `org`/`workspace` context to render its existing tabs; `account_settings` should pass the current workspace + its org (from `get_current_workspace`) so all three tabs render, plus `active='account'`.
- Membership scoping helper: resolve the target org as an `OrgMember` for `request.user` (404 if not a member), mirroring `settings_org._member_in_current_org`. For `org_leave`/`switch_org`, resolving via the user's own membership is the auth check.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_settings_account.py`:

```python
import pytest

from tuckit.core.models import OrgMember, Org, User, Workspace
from tuckit.core.services.orgs import create_org


def _login(client, user, ws):
    client.force_login(user)
    session = client.session
    session["active_workspace_id"] = ws.id
    session.save()


@pytest.fixture
def acct_ctx(client, db):
    user = User.objects.create(username="u@u.com", email="u@u.com")
    org_a, ws_a = create_org(user, name="Alpha")
    org_b, ws_b = create_org(user, name="Beta")
    return client, user, org_a, ws_a, org_b, ws_b


@pytest.mark.django_db
def test_account_page_lists_my_orgs(acct_ctx):
    client, user, org_a, ws_a, org_b, ws_b = acct_ctx
    _login(client, user, ws_a)
    resp = client.get("/settings/account")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Alpha" in body and "Beta" in body
    assert "u@u.com" in body                       # email shown


@pytest.mark.django_db
def test_create_org_from_account(acct_ctx):
    client, user, org_a, ws_a, org_b, ws_b = acct_ctx
    _login(client, user, ws_a)
    resp = client.post("/settings/account/orgs", {"name": "Gamma"})
    assert resp.status_code in (204, 302)          # navigates to home
    assert OrgMember.objects.filter(user=user, org__name="Gamma", role="owner").exists()
    # active workspace switched to the new org's workspace
    new_ws = Workspace.objects.get(org__name="Gamma")
    assert client.session.get("active_workspace_id") == new_ws.id


@pytest.mark.django_db
def test_leave_org_from_account(acct_ctx):
    client, user, org_a, ws_a, org_b, ws_b = acct_ctx
    _login(client, user, ws_a)                     # currently in Alpha
    om_b = OrgMember.objects.get(user=user, org=org_b)
    resp = client.post(f"/settings/account/orgs/{org_b.id}/leave")
    assert resp.status_code in (204, 302)
    assert not OrgMember.objects.filter(id=om_b.id).exists()


@pytest.mark.django_db
def test_leave_current_org_clears_active_workspace(acct_ctx):
    client, user, org_a, ws_a, org_b, ws_b = acct_ctx
    _login(client, user, ws_a)                     # active = Alpha's ws
    client.post(f"/settings/account/orgs/{org_a.id}/leave")
    assert not OrgMember.objects.filter(user=user, org=org_a).exists()
    assert client.session.get("active_workspace_id") != ws_a.id


@pytest.mark.django_db
def test_leave_sole_owner_returns_400(acct_ctx):
    client, user, org_a, ws_a, org_b, ws_b = acct_ctx
    # make org_a have a second workspace-less owner? No — sole owner of BOTH.
    # user is sole owner of org_a and org_b; leaving org_a is allowed only if a
    # second owner exists. Here user is sole owner, so it must be rejected.
    _login(client, user, ws_b)
    resp = client.post(f"/settings/account/orgs/{org_a.id}/leave")
    assert resp.status_code == 400
    assert OrgMember.objects.filter(user=user, org=org_a).exists()


@pytest.mark.django_db
def test_leave_org_not_a_member_404s(acct_ctx):
    client, user, org_a, ws_a, org_b, ws_b = acct_ctx
    stranger_owner = User.objects.create(username="s@s.com", email="s@s.com")
    foreign, _ = create_org(stranger_owner, name="Foreign")
    _login(client, user, ws_a)
    resp = client.post(f"/settings/account/orgs/{foreign.id}/leave")
    assert resp.status_code == 404
    assert OrgMember.objects.filter(user=stranger_owner, org=foreign).exists()


@pytest.mark.django_db
def test_switch_org_sets_active_workspace(acct_ctx):
    client, user, org_a, ws_a, org_b, ws_b = acct_ctx
    _login(client, user, ws_a)
    resp = client.post(f"/settings/account/orgs/{org_b.id}/open")
    assert resp.status_code in (204, 302)
    assert client.session.get("active_workspace_id") == ws_b.id
```

> Note on `test_leave_sole_owner_returns_400`: `user` is the sole owner of `org_a`, so the sole-owner guard fires (400) before the last-org guard is even relevant. This verifies the view surfaces `InvalidValue` as 400.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_settings_account.py -v`
Expected: FAIL (routes 404 — nothing built yet).

- [ ] **Step 3: Create the views**

Create `tuckit/web/views/settings_account.py`:

```python
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from tuckit.core.models import OrgMember, Workspace
from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.orgs import (
    create_org,
    is_org_owner,
    leave_org,
    list_user_orgs,
    _owner_count,
)
from tuckit.web.auth import get_current_workspace
from tuckit.web.htmx import redirect_response


def account_settings(request):
    ws = get_current_workspace(request)
    orgs = list_user_orgs(request.user) if request.user.is_authenticated else []
    # annotate each row with whether 나가기 is allowed, so the template can hide it
    for row in orgs:
        org = row["org"]
        sole_owner = row["role"] == "owner" and _owner_count(org) <= 1
        row["can_leave"] = not sole_owner and len(orgs) > 1
        row["is_current"] = bool(ws) and ws.org_id == org.id
    return render(request, "web/settings_account.html", {
        "workspace": ws,
        "org": ws.org if ws else None,
        "orgs": orgs,
    })


def _member_org(request, org_id):
    """Return the caller's OrgMember for org_id, or 404 if they aren't a member."""
    return get_object_or_404(OrgMember, org_id=org_id, user=request.user)


@require_POST
def org_create(request):
    try:
        org, ws = create_org(request.user, name=request.POST.get("name", ""))
    except InvalidValue as exc:
        return HttpResponse(str(exc), status=400)
    request.session["active_workspace_id"] = ws.id
    return redirect_response(request, "web:home")


@require_POST
def org_leave(request, org_id):
    membership = _member_org(request, org_id)          # 404 if not a member
    org = membership.org
    try:
        leave_org(request.user, org=org)
    except InvalidValue as exc:
        return HttpResponse(str(exc), status=400)
    ws = get_current_workspace(request)
    if ws is None or ws.org_id == org.id:
        request.session.pop("active_workspace_id", None)
    return redirect_response(request, "web:settings_account")


@require_POST
def switch_org(request, org_id):
    membership = _member_org(request, org_id)          # 404 if not a member
    first_ws = Workspace.objects.filter(org=membership.org).order_by("name").first()
    if first_ws is not None:
        request.session["active_workspace_id"] = first_ws.id
    return redirect_response(request, "web:home")
```

> Detail: after `leave_org`, calling `get_current_workspace(request)` re-resolves a still-accessible workspace; the guard clears the session only when the current workspace still points at the left org (or is gone), letting `get_current_workspace` fall back to another accessible workspace on the next request.

- [ ] **Step 4: Add the URLs**

In `tuckit/web/urls.py`, add `settings_account` to the `from tuckit.web.views import …` line, then add these routes near the other `settings/…` routes:

```python
    path("settings/account", settings_account.account_settings, name="settings_account"),
    path("settings/account/orgs", settings_account.org_create, name="account_org_create"),
    path("settings/account/orgs/<int:org_id>/leave", settings_account.org_leave, name="account_org_leave"),
    path("settings/account/orgs/<int:org_id>/open", settings_account.switch_org, name="account_org_open"),
```

- [ ] **Step 5: Add the scopenav 계정 tab**

Replace `tuckit/web/templates/web/partials/_settings_scopenav.html` with:

```html
<div class="scopenav">
  <a class="scope {% if active == 'account' %}on{% endif %}" href="{% url 'web:settings_account' %}">계정</a>
  <a class="scope {% if active == 'org' %}on{% endif %}" href="{% url 'web:settings_org' %}">조직{% if org %} · {{ org.name }}{% endif %}</a>
  <a class="scope {% if active == 'workspace' %}on{% endif %}" href="{% url 'web:settings_workspace' %}">워크스페이스{% if workspace %} · {{ workspace.name }}{% endif %}</a>
</div>
```

- [ ] **Step 6: Create the templates**

Create `tuckit/web/templates/web/partials/_org_row.html`:

```html
<div class="org-row" data-org-id="{{ row.org.id }}">
  <div class="org-row-main">
    <span class="org-row-name">{{ row.org.name }}</span>
    <span class="role-badge role-badge--{{ row.role }}">{{ row.role }}</span>
    <span class="org-row-meta">워크스페이스 {{ row.workspace_count }}</span>
    {% if row.is_current %}<span class="org-row-meta">· 현재</span>{% endif %}
  </div>
  <div class="org-row-actions">
    {% if not row.is_current %}
      <form hx-post="{% url 'web:account_org_open' row.org.id %}" hx-swap="none">
        <button type="submit" class="btn">열기</button>
      </form>
    {% endif %}
    {% if row.can_leave %}
      <form hx-post="{% url 'web:account_org_leave' row.org.id %}"
            hx-confirm="{{ row.org.name }} 조직에서 나갈까요?">
        <button type="submit" class="btn danger">나가기</button>
      </form>
    {% endif %}
  </div>
</div>
```

Create `tuckit/web/templates/web/settings_account.html`. It matches the confirmed structure of `settings_org.html`: `{% extends "web/base.html" %}` + `{% block main %}`, a `topbar`/`area-title` heading, and `<section class="group">` + `<div class="group-label">` sections (these are the REAL class names — `settings_org.html` uses them, not `.settings-section`):

```html
{% extends "web/base.html" %}
{% block main %}
  {% include "web/partials/_settings_scopenav.html" with active='account' %}
  <div class="topbar"><h1 class="area-title">계정 설정</h1></div>

  <section class="group">
    <div class="group-label">계정</div>
    <div class="empty muted">{{ request.user.email }}</div>
  </section>

  <section class="group">
    <div class="group-label">내 조직</div>
    {% for row in orgs %}
      {% include "web/partials/_org_row.html" %}
    {% endfor %}
    <form class="org-add" hx-post="{% url 'web:account_org_create' %}" hx-swap="none"
          hx-on::after-request="this.reset()">
      <input name="name" class="org-add-input" placeholder="＋ 새 조직" maxlength="200" autocomplete="off">
    </form>
  </section>
{% endblock %}
```

Reused classes that already exist in `app.css`: `.group`, `.group-label`, `.topbar`, `.area-title`, `.empty`, `.muted`, `.btn`, `.btn.danger`, `.scopenav`, `.scope`. The NEW classes introduced by `_org_row.html` and the org-add form — `.org-row`, `.org-row-main`, `.org-row-name`, `.org-row-meta`, `.org-row-actions`, `.role-badge` (+ `--owner/--admin/--member` variants), `.org-add`, `.org-add-input` — do NOT exist yet. Append a small style block for them to `app.css` in this step. Colors ONLY via `var(--token)` (e.g. role badge text `var(--muted)`, owner badge `var(--accent)`; the `.btn.danger` already uses `var(--warn)`) — NO hard-coded hex (app.css enforces this). Model the `.org-add`/`.org-add-input` styles on the existing `.area-add`/`.area-add-input` rules for visual consistency.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_settings_account.py -v`
Expected: PASS (all).

- [ ] **Step 8: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (nothing regressed; the register refactor and new routes are green).

- [ ] **Step 9: Commit**

```bash
git add tuckit/web/views/settings_account.py tuckit/web/urls.py \
        tuckit/web/templates/web/settings_account.html \
        tuckit/web/templates/web/partials/_org_row.html \
        tuckit/web/templates/web/partials/_settings_scopenav.html \
        tests/web/test_settings_account.py
git commit -m "feat(web): /settings/account — list orgs, create org, leave/open"
```

---

## Self-Review Notes (author)

- **Spec coverage:** `create_org` (Task 1), `list_user_orgs` + `leave_org` (Task 2), account page with create/leave/open + email + role badges (Task 3). Switcher deliberately unchanged (design decision); new org auto-appears in the existing `switchable_workspaces` dropdown.
- **register DRY:** `register` delegates to `create_org`; the existing `tests/test_services_accounts.py` suite is the regression guard (Task 1 Step 6).
- **Decision flagged for review:** the last-org `leave_org` guard is stricter than the approved spec — called out in Global Constraints for the user to veto.
- **Public/private boundary:** only the neutral `run_signup_hook` seam is touched; no billing/cloud content.
- **Reuse:** `redirect_response` for hx-post navigation (org create/leave/open); membership scoping mirrors `settings_org.py`; slug helper mirrors `_unique_ws_slug`.
- **Type consistency:** `create_org(user, *, name, slug=None) -> (Org, Workspace)` used identically by `register` and `org_create`. `list_user_orgs` rows are `{"org","role","workspace_count"}`, extended in the view with `can_leave`/`is_current` for the template only.
- **Placeholder scan:** the two "verify against `settings_org.html`" notes (base/block tags, class names) are intentional guardrails, not placeholders — the implementer must confirm the real template structure since settings templates may use a settings-specific base; exact class names are cheap to get wrong. All code steps contain complete code.
