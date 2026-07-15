# Org/Workspace Home & Overview — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the org a first-class destination — a real org home page at `/<org_slug>/`, a "my orgs & workspaces" overview, a navigable switcher, and breadcrumbs — by re-surfacing existing capabilities, not adding new ones.

**Architecture:** New org-home route `/<org_slug>/` resolved by the existing `TenantMiddleware` (sets `request.org`, 404s non-members, leaves `request.workspace` None). Org home absorbs the old `settings/<org>/` page (members/invites/rename/delete inline) plus a workspace grid; the old GET page is deleted (mutation endpoints kept as POST targets). The account page is redesigned to enumerate workspaces per org. Switcher org headers become links; a breadcrumb partial is added to the app shell.

**Tech Stack:** Django (server-rendered templates), htmx + Alpine.js, pytest. CSS via the brand/product/base/app token layers.

## Global Constraints

- **Public repo (tuckit, BSL 1.1).** No billing/cloud/paddle code. No secrets.
- **Do NOT commit** `docs/superpowers/` (spec/plan stay untracked per workspace convention).
- **Access model unchanged.** Org membership ⇒ access to all its workspaces. No `WorkspaceMember`, no per-workspace roles, no ownership transfer.
- **Design tokens only.** In CSS use `var(--token)` — never a literal hex or radius. Surfaces use `var(--radius)` (14px), controls `var(--radius-small)` (9px). Accent is `var(--blue)`. Existing tokens include: `--paper`, `--paper-raised`, `--surface`, `--line`, `--line-strong`, `--muted`, `--ink`, `--ink-soft`, `--blue`, `--radius`, `--radius-small`, `--ease`.
- **Reuse existing classes/partials** where they exist (`.settings-page`, `.group`, `.settings-section`, `.panel`, `.field`, `.btn`, `.role-badge--{role}`, `_member_row.html`, `_invite_row.html`, `_member_manage_modal.html`).
- **Tests:** pytest, `@pytest.mark.django_db`. Follow `tests/web/` shape — `client.force_login(user)`, build orgs via `Org.objects.create` + `OrgMember.objects.create` or `create_org(user, name=...)`.
- Run the full suite with `cd tuckit && uv run pytest`. The design-system drift test must keep passing.

---

### Task 1: Reserve the `first-org` slug

Closes the last single-segment collision gap: `first-org/` is a literal route, so an org with that slug would be shadowed at its root.

**Files:**
- Modify: `tuckit/tuckit/core/services/slugs.py:8-14`
- Test: `tests/test_services_slugs.py`

**Interfaces:**
- Produces: nothing new — `RESERVED_ORG_SLUGS` gains `"first-org"`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_services_slugs.py`:

```python
import pytest

from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.slugs import validate_slug


def test_first_org_is_reserved():
    with pytest.raises(InvalidValue):
        validate_slug("first-org", kind="org")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tuckit && uv run pytest tests/test_services_slugs.py::test_first_org_is_reserved -v`
Expected: FAIL (validate_slug returns "first-org" instead of raising).

- [ ] **Step 3: Add the reserved word**

In `tuckit/tuckit/core/services/slugs.py`, add `"first-org"` to `RESERVED_ORG_SLUGS`:

```python
RESERVED_ORG_SLUGS = {
    "settings", "login", "logout", "register", "invite", "welcome",
    "healthcheck", "cloud", "static", "media", "account", "check-slug",
    "admin", "api", "app", "www", "assets", "about", "help", "support",
    "status", "docs", "blog", "pricing", "terms", "privacy", "mail",
    "new", "me", "null", "undefined", "first-org",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd tuckit && uv run pytest tests/test_services_slugs.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd tuckit && git add tuckit/core/services/slugs.py tests/test_services_slugs.py
git commit -m "fix: reserve 'first-org' org slug to prevent route shadowing"
```

---

### Task 2: `list_user_orgs` enumerates each org's workspaces

The account overview needs the actual workspaces per org, not just a count.

**Files:**
- Modify: `tuckit/tuckit/core/services/orgs.py:150-161`
- Test: `tests/test_services_orgs.py:207-212` (extend)

**Interfaces:**
- Produces: `list_user_orgs(user)` now returns rows with an added key `"workspaces"` — a list of `Workspace` for that org, ordered by name. Existing keys (`org`, `role`, `workspace_count`) are unchanged. Consumed by Task 5.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_services_orgs.py`:

```python
@pytest.mark.django_db
def test_list_user_orgs_includes_workspaces():
    from tuckit.core.models import User
    from tuckit.core.services.orgs import create_org, create_workspace, list_user_orgs

    user = User.objects.create(email="w@w.com")
    org, first_ws = create_org(user, name="Acme")
    second_ws = create_workspace(org, "Marketing")

    rows = list_user_orgs(user)
    assert len(rows) == 1
    names = [w.name for w in rows[0]["workspaces"]]
    assert names == sorted([first_ws.name, second_ws.name])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tuckit && uv run pytest tests/test_services_orgs.py::test_list_user_orgs_includes_workspaces -v`
Expected: FAIL with `KeyError: 'workspaces'`.

- [ ] **Step 3: Add workspaces to each row**

In `tuckit/tuckit/core/services/orgs.py`, update `list_user_orgs`:

```python
def list_user_orgs(user) -> list[dict]:
    rows = []
    memberships = (
        OrgMember.objects.filter(user=user).select_related("org").order_by("org__name")
    )
    for m in memberships:
        workspaces = list(Workspace.objects.filter(org=m.org).order_by("name"))
        rows.append({
            "org": m.org,
            "role": m.role,
            "workspace_count": len(workspaces),
            "workspaces": workspaces,
        })
    return rows
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd tuckit && uv run pytest tests/test_services_orgs.py -v`
Expected: PASS (new test + existing `test_list_user_orgs_returns_role_and_workspace_count`).

- [ ] **Step 5: Commit**

```bash
cd tuckit && git add tuckit/core/services/orgs.py tests/test_services_orgs.py
git commit -m "feat: list_user_orgs includes each org's workspaces"
```

---

### Task 3: Org home page at `/<org_slug>/`

The centerpiece. New view + template + route. Reuses the org context that `settings_org.org_settings` builds today, renders a two-pane layout (left rail: identity, members, danger; right: workspace grid + new-workspace form). The old `settings_org` page still exists after this task (removed in Task 4).

**Files:**
- Modify: `tuckit/tuckit/web/views/settings_org.py` (add `org_home` view)
- Create: `tuckit/tuckit/web/templates/web/org_home.html`
- Create: `tuckit/tuckit/web/templates/web/partials/_org_ws_grid.html`
- Modify: `tuckit/tuckit/web/urls.py` (add `org_home` route, appended last)
- Modify: `tuckit/tuckit/web/static/web/app.css` (org-home layout classes)
- Test: `tests/web/test_org_home.py` (new)

**Interfaces:**
- Consumes: `request.org` (set by `TenantMiddleware` from the `<org_slug>` kwarg), `is_org_admin`, `is_org_owner`, `list_org_members` (all in `settings_org.py` / `orgs.py`).
- Produces: URL name `web:org_home` taking one arg `org_slug` → `/<org_slug>/`. Consumed by Tasks 4, 5, 6, 7.

- [ ] **Step 1: Write the failing tests**

Create `tests/web/test_org_home.py`:

```python
import pytest

from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.orgs import create_workspace


@pytest.fixture
def org_ctx(client, db):
    org = Org.objects.create(name="Acme", slug="acme")
    owner = User.objects.create(email="o@a.com")
    OrgMember.objects.create(user=owner, org=org, role="owner")
    member = User.objects.create(email="m@a.com")
    OrgMember.objects.create(user=member, org=org, role="member")
    ws = create_workspace(org, "Board")
    return client, org, owner, member, ws


@pytest.mark.django_db
def test_org_home_renders_members_and_workspaces(org_ctx):
    client, org, owner, member, ws = org_ctx
    client.force_login(owner)
    resp = client.get(f"/{org.slug}/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Acme" in body
    assert "o@a.com" in body and "m@a.com" in body
    assert "Board" in body
    # Opening a workspace links to its home
    assert f'href="/{org.slug}/{ws.slug}/"' in body


@pytest.mark.django_db
def test_org_home_shows_new_workspace_form_for_admin(org_ctx):
    client, org, owner, member, ws = org_ctx
    client.force_login(owner)
    body = client.get(f"/{org.slug}/").content.decode()
    assert f'action="/settings/{org.slug}/workspaces/new"' in body


@pytest.mark.django_db
def test_org_home_hides_new_workspace_form_for_member(org_ctx):
    client, org, owner, member, ws = org_ctx
    client.force_login(member)
    body = client.get(f"/{org.slug}/").content.decode()
    assert f'action="/settings/{org.slug}/workspaces/new"' not in body


@pytest.mark.django_db
def test_org_home_404_for_nonmember(org_ctx):
    client, org, owner, member, ws = org_ctx
    other = Org.objects.create(name="Other", slug="other")
    stranger = User.objects.create(email="s@s.com")
    OrgMember.objects.create(user=stranger, org=other, role="owner")
    client.force_login(stranger)  # not a member of `acme`
    resp = client.get(f"/{org.slug}/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_org_home_requires_login(org_ctx):
    client, org, owner, member, ws = org_ctx
    resp = client.get(f"/{org.slug}/")
    assert resp.status_code in (302, 404)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tuckit && uv run pytest tests/web/test_org_home.py -v`
Expected: FAIL (no `org_home` route → 404 on `/acme/`, or NoReverseMatch once template refs are added).

- [ ] **Step 3: Add the `org_home` view**

Append to `tuckit/tuckit/web/views/settings_org.py`:

```python
def org_home(request):
    """First-class org landing at /<org_slug>/. request.org is set by
    TenantMiddleware (404 for non-members); request.workspace stays None."""
    org = request.org
    members = list(list_org_members(org))
    workspaces = list(org.workspaces.order_by("name"))
    invitations = list(Invitation.objects.filter(org=org, accepted_at__isnull=True))
    for inv in invitations:
        inv.link = request.build_absolute_uri(reverse("web:invite_accept", args=[inv.token]))
    return render(request, "web/org_home.html", {
        "workspace": request.workspace,
        "org": org,
        "members": members,
        "workspaces": workspaces,
        "invitations": invitations,
        "can_admin": is_org_admin(request.user, org),
        "can_owner": is_org_owner(request.user, org),
        "role_choices": OrgMember.ROLE_CHOICES,
    })
```

- [ ] **Step 4: Add the route (appended LAST so literals win)**

In `tuckit/tuckit/web/urls.py`, add a new group and extend `urlpatterns`:

```python
# --- org home (tenant; org-only, single segment; MUST be last so literal
#     single-segment routes like login/ first-org/ always win) ---
org_patterns = [
    path("<slug:org_slug>/", settings_org.org_home, name="org_home"),
]

urlpatterns = auth_patterns + settings_patterns + root_patterns + app_patterns + org_patterns
```

- [ ] **Step 5: Create the workspace-grid partial**

Create `tuckit/tuckit/web/templates/web/partials/_org_ws_grid.html`:

```html
{% load web_extras %}
<div class="ws-grid">
  {% for ws in workspaces %}
    <a class="ws-card" href="{% url 'web:home' org.slug ws.slug %}">
      <span class="ws-card-name">{{ ws.name }}</span>
      <span class="ws-card-open">Open →</span>
    </a>
  {% endfor %}
  {% if can_admin %}
    <form class="ws-new" method="post" action="{% url 'web:workspace_create' org.slug %}">
      {% csrf_token %}
      <input name="name" class="ws-new-input" placeholder="＋ New workspace" maxlength="200"
             autocomplete="off" required>
    </form>
  {% endif %}
</div>
```

- [ ] **Step 6: Create the org home template**

Create `tuckit/tuckit/web/templates/web/org_home.html`:

```html
{% extends "web/base.html" %}
{% load web_extras %}
{% block title %}{{ org.name }} · tuckit{% endblock %}
{% block main %}
<div class="orghome">
  <header class="orghome-bar">
    <div class="orghome-id">
      <h1 class="orghome-name" x-data="{editing:false, name:'{{ org.name|escapejs }}', saved:'{{ org.name|escapejs }}'}">
        <span x-show="!editing" {% if can_admin %}x-on:click="editing = true"{% endif %}>
          <span x-text="name"></span>{% if can_admin %}{% icon "edit" %}{% endif %}
        </span>
        {% if can_admin %}
        <input name="name" class="title-edit" x-show="editing" x-cloak x-model="name"
               hx-post="{% url 'web:org_rename' org.slug %}" hx-trigger="blur, keydown[key=='Enter']"
               hx-vals="js:{name: name}" hx-swap="none"
               hx-on::after-request="if(event.detail.successful){saved=name}else{name=saved; showToast(event.detail.xhr.responseText,'err')}"
               x-on:keydown.enter="editing=false" x-on:blur="editing=false">
        {% endif %}
      </h1>
      <span class="role-badge role-badge--{{ can_owner|yesno:'owner,member' }}">
        {% if can_owner %}owner{% elif can_admin %}admin{% else %}member{% endif %}
      </span>
    </div>
    <div class="orghome-meta">{{ workspaces|length }} workspace{{ workspaces|length|pluralize }} · {{ members|length }} member{{ members|length|pluralize }}</div>
  </header>

  <div class="orghome-rail">
    <aside class="orghome-side">
      <div class="orghome-block">
        <div class="settings-title">Members</div>
        <table class="member-table">
          <tbody id="members-list">
            {% for m in members %}{% include "web/partials/_member_row.html" %}{% endfor %}
            {% if can_admin %}
              {% for inv in invitations %}{% include "web/partials/_invite_row.html" with inv=inv %}{% endfor %}
            {% endif %}
          </tbody>
        </table>
        {% if can_admin %}
        <form class="token-add" hx-post="{% url 'web:invite_create' org.slug %}" hx-target="#members-list" hx-swap="beforeend"
              hx-on::after-request="this.reset()">
          <input type="email" name="email" placeholder="Email" required>
          <span class="settings-select"><select name="role">
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select></span>
          <button type="submit" class="btn">Invite</button>
        </form>
        {% endif %}
      </div>

      {% if can_owner %}
      <div class="orghome-block">
        <div class="settings-title danger">Danger zone</div>
        <form hx-post="{% url 'web:org_delete' org.slug %}" hx-confirm="The organization and all its workspaces will be deleted. Continue?">
          <button type="submit" class="btn danger">Delete organization</button>
        </form>
      </div>
      {% endif %}
    </aside>

    <section class="orghome-main">
      <div class="settings-title">Workspaces</div>
      {% include "web/partials/_org_ws_grid.html" %}
    </section>
  </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Add org-home CSS (tokens only)**

Append to `tuckit/tuckit/web/static/web/app.css`:

```css
/* --- Org home (/<org>/) --- */
.orghome { padding: 24px; max-width: 960px; }
.orghome-bar { display: flex; flex-wrap: wrap; align-items: baseline; gap: 10px; margin-bottom: 20px; }
.orghome-id { display: flex; align-items: center; gap: 10px; }
.orghome-name { font-size: 22px; font-weight: 650; margin: 0; }
.orghome-meta { color: var(--muted); font-size: 13px; }
.orghome-rail { display: grid; grid-template-columns: 300px 1fr; gap: 24px; align-items: start; }
.orghome-side { display: flex; flex-direction: column; gap: 20px; }
.orghome-block { border: 1px solid var(--line); border-radius: var(--radius); padding: 14px 16px; background: var(--paper-raised); }
.ws-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; }
.ws-card { display: flex; flex-direction: column; gap: 8px; border: 1px solid var(--line); border-radius: var(--radius); padding: 14px; background: var(--paper-raised); text-decoration: none; color: var(--ink); }
.ws-card:hover { border-color: var(--line-strong); }
.ws-card-name { font-weight: 600; }
.ws-card-open { color: var(--blue); font-size: 12px; }
.ws-new { display: flex; border: 1px dashed var(--line); border-radius: var(--radius); }
.ws-new-input { width: 100%; border: 0; background: transparent; padding: 14px; color: var(--blue); font: inherit; border-radius: var(--radius); }
.ws-new-input:focus-visible { outline: none; }
@media (max-width: 720px) { .orghome-rail { grid-template-columns: 1fr; } }
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd tuckit && uv run pytest tests/web/test_org_home.py -v`
Expected: PASS (all 5).

- [ ] **Step 9: Guard against route regressions**

Run: `cd tuckit && uv run pytest tests/web/test_tenant_routing.py tests/web/test_tenant_middleware.py tests/web/test_no_workspace_routing.py -v`
Expected: PASS (single-segment org route didn't shadow existing routes).

- [ ] **Step 10: Commit**

```bash
cd tuckit && git add tuckit/web/views/settings_org.py tuckit/web/urls.py \
  tuckit/web/templates/web/org_home.html tuckit/web/templates/web/partials/_org_ws_grid.html \
  tuckit/web/static/web/app.css tests/web/test_org_home.py
git commit -m "feat: org home page at /<org_slug>/ with workspace grid + inline management"
```

---

### Task 4: Remove the old org-settings page and repoint references

Org home replaces `settings/<org>/`. Delete the GET page (no redirect stub). Keep every mutation endpoint — org home POSTs to them.

**Files:**
- Modify: `tuckit/tuckit/web/views/settings_org.py` (delete `org_settings`)
- Delete: `tuckit/tuckit/web/templates/web/settings_org.html`
- Modify: `tuckit/tuckit/web/urls.py:31` (delete `settings_org` GET route)
- Modify: `tuckit/tuckit/web/templates/web/partials/_settings_scopenav.html:3`
- Modify: `tuckit/tuckit/web/templates/web/settings_workspace.html:53`
- Modify: `tuckit/tuckit/web/templates/web/partials/_sidebar.html:40`
- Test: `tests/web/test_settings_org.py` (repoint GET-path tests)

**Interfaces:**
- Consumes: `web:org_home` from Task 3.
- Produces: `web:settings_org` name no longer exists. Mutation names (`org_rename`, `org_member_role`, `org_member_remove`, `org_member_manage`, `org_delete`, `workspace_create`, `invite_*`) unchanged.

- [ ] **Step 1: Update the affected tests first (they must still pass on new URLs)**

In `tests/web/test_settings_org.py`, change the six GET-path tests from `/settings/{org.slug}/` to `/{org.slug}/`. Specifically the `client.get(f"/settings/{org.slug}/")` calls in: `test_org_page_lists_members_and_workspaces`, `test_org_only_settings_branch_works_for_member`, `test_org_page_requires_login`, `test_nonmember_gets_404_on_other_org_settings`, `test_org_page_shows_invite_form_and_pending`, and the two `client.get(f"/settings/{org_b.slug}/")`-style GETs in `test_invite_urls_use_viewed_org_not_session_fallback`. Leave every `POST` to `/settings/{org.slug}/…` (rename/role/remove/delete/invites) unchanged — those routes remain.

Example diff for the first test:

```python
@pytest.mark.django_db
def test_org_page_lists_members_and_workspaces(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, owner)
    resp = client.get(f"/{org.slug}/")          # was /settings/{org.slug}/
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Acme" in body
    assert "o@a.com" in body and "m@a.com" in body
    assert "Board" in body
```

For `test_invite_urls_use_viewed_org_not_session_fallback`, the GET becomes `client.get(f"/{org_b.slug}/")`; the body assertions (`/settings/{org_b.slug}/invites` present, `/settings/{org_a.slug}/invites` absent) still hold because org home reuses the same invite form.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tuckit && uv run pytest tests/web/test_settings_org.py -v`
Expected: the GET tests FAIL now (old view still renders `settings_org.html`, but URL `/{org}/` already works from Task 3 — so these may PASS already). If they pass, that confirms org home covers them; proceed. The point of removal is the steps below.

- [ ] **Step 3: Delete the `org_settings` view**

In `tuckit/tuckit/web/views/settings_org.py`, delete the entire `org_settings` function (lines 19-35). Keep all mutation views and their imports (`reverse` is still used by nothing else — check: if `reverse` becomes unused after deleting `org_settings`, it moved to `org_home` in Task 3, which also uses it, so keep the import).

- [ ] **Step 4: Delete the template**

```bash
cd tuckit && git rm tuckit/web/templates/web/settings_org.html
```

- [ ] **Step 5: Delete the GET route**

In `tuckit/tuckit/web/urls.py`, remove this line from `settings_patterns`:

```python
path("settings/<slug:org_slug>/", settings_org.org_settings, name="settings_org"),
```

(Keep lines 32-40 — the `org_rename`/members/delete/workspace_create/invites routes.)

- [ ] **Step 6: Repoint the scope-nav Organization tab**

In `tuckit/tuckit/web/templates/web/partials/_settings_scopenav.html`, line 3:

```html
  <a class="scope {% if active == 'org' %}on{% endif %}" href="{% url 'web:org_home' org.slug %}">Organization</a>
```

- [ ] **Step 7: Repoint the workspace-settings "Manage →" link**

In `tuckit/tuckit/web/templates/web/settings_workspace.html`, line 53:

```html
        <a class="btn" href="{% url 'web:org_home' current_workspace.org.slug %}">Manage →</a>
```

- [ ] **Step 8: Fix the sidebar active-state check**

In `tuckit/tuckit/web/templates/web/partials/_sidebar.html`, line 40, replace the `settings_org` url_name reference with `org_home`:

```html
    <a class="util-btn util-settings{% if request.resolver_match.url_name == 'settings_workspace' or request.resolver_match.url_name == 'org_home' %} util-btn--active{% endif %}"
```

- [ ] **Step 9: Verify no dangling `settings_org` references remain**

Run: `cd tuckit && grep -rn "settings_org\b" tuckit/ tests/`
Expected: only the module import in `urls.py:7` (`settings_org` the module, used for mutation views) and the filename `views/settings_org.py`. No `web:settings_org` URL name, no `settings_org.html`.

- [ ] **Step 10: Run the full settings + routing suites**

Run: `cd tuckit && uv run pytest tests/web/test_settings_org.py tests/web/test_settings_workspace.py tests/web/test_settings.py tests/web/test_sidebar.py tests/web/test_settings_invites.py -v`
Expected: PASS.

- [ ] **Step 11: Commit**

```bash
cd tuckit && git add -A tuckit/web tests/web/test_settings_org.py
git commit -m "refactor: delete old org settings page; org home replaces it, mutations reused"
```

---

### Task 5: Redesign the account overview (nested tree)

`settings/account` enumerates each org's workspaces as chips (using Task 2's data), with an `org home →` link and a per-org new-workspace form — replacing the count-only display.

**Files:**
- Modify: `tuckit/tuckit/web/views/settings_account.py:26-37` (annotate `can_create`)
- Rewrite: `tuckit/tuckit/web/templates/web/partials/_org_row.html`
- Modify: `tuckit/tuckit/web/static/web/app.css` (chip styles)
- Test: `tests/web/test_settings_account.py`

**Interfaces:**
- Consumes: `list_user_orgs` rows with `workspaces` (Task 2); `web:org_home` (Task 3); `web:workspace_create` (existing).
- Produces: none downstream.

- [ ] **Step 1: Write the failing tests**

Add to `tests/web/test_settings_account.py`:

```python
@pytest.mark.django_db
def test_account_page_lists_workspaces_not_just_counts(acct_ctx):
    client, user, org_a, ws_a, org_b, ws_b = acct_ctx
    _login(client, user, ws_a)
    body = client.get("/settings/account").content.decode()
    # each workspace is individually linked (open)
    assert f'href="/{org_a.slug}/{ws_a.slug}/"' in body
    assert f'href="/{org_b.slug}/{ws_b.slug}/"' in body
    # org home reachable from the overview
    assert f'href="/{org_a.slug}/"' in body


@pytest.mark.django_db
def test_account_page_has_new_workspace_form_for_owned_org(acct_ctx):
    client, user, org_a, ws_a, org_b, ws_b = acct_ctx
    _login(client, user, ws_a)          # user is owner of both orgs
    body = client.get("/settings/account").content.decode()
    assert f'action="/settings/{org_a.slug}/workspaces/new"' in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tuckit && uv run pytest tests/web/test_settings_account.py::test_account_page_lists_workspaces_not_just_counts tests/web/test_settings_account.py::test_account_page_has_new_workspace_form_for_owned_org -v`
Expected: FAIL (`_org_row.html` shows only counts; no per-ws links, no org-home link, no create form).

- [ ] **Step 3: Annotate create permission in the view**

In `tuckit/tuckit/web/views/settings_account.py`, inside the `for row in orgs:` loop (after `row["first_workspace"] = …`), add:

```python
        row["can_create_ws"] = row["role"] in ("owner", "admin")
```

- [ ] **Step 4: Rewrite the org row partial**

Replace `tuckit/tuckit/web/templates/web/partials/_org_row.html` with:

```html
<div class="org-card" data-org-id="{{ row.org.id }}">
  <div class="org-card-head">
    <a class="org-card-name" href="{% url 'web:org_home' row.org.slug %}">{{ row.org.name }}</a>
    <span class="role-badge role-badge--{{ row.role }}">{{ row.role }}</span>
    <span class="org-row-meta">{{ row.workspace_count }} workspace{{ row.workspace_count|pluralize }}</span>
    {% if row.is_current %}<span class="org-row-meta">· current</span>{% endif %}
    <a class="org-card-open" href="{% url 'web:org_home' row.org.slug %}">Org home →</a>
  </div>
  <div class="org-ws-chips">
    {% for ws in row.workspaces %}
      <a class="org-ws-chip" href="{% url 'web:home' row.org.slug ws.slug %}">
        <span class="nm">{{ ws.name }}</span><span class="go">Open →</span>
      </a>
    {% endfor %}
    {% if row.can_create_ws %}
      <form class="org-ws-chip org-ws-new" method="post" action="{% url 'web:workspace_create' row.org.slug %}">
        {% csrf_token %}
        <input name="name" placeholder="＋ New workspace" maxlength="200" autocomplete="off" required>
      </form>
    {% endif %}
  </div>
  {% if row.can_leave %}
  <div class="org-card-foot">
    <form hx-post="{% url 'web:account_org_leave' row.org.id %}" hx-confirm="Leave {{ row.org.name }}?">
      <button type="submit" class="btn danger">Leave</button>
    </form>
  </div>
  {% endif %}
</div>
```

- [ ] **Step 5: Add chip CSS (tokens only)**

Append to `tuckit/tuckit/web/static/web/app.css`:

```css
/* --- Account overview: org cards + workspace chips --- */
.org-card { border: 1px solid var(--line); border-radius: var(--radius); margin-bottom: 12px; overflow: hidden; }
.org-card-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; padding: 12px 15px; background: var(--paper-raised); border-bottom: 1px solid var(--line); }
.org-card-name { font-weight: 650; font-size: 15px; color: var(--ink); text-decoration: none; }
.org-card-name:hover { color: var(--blue); }
.org-card-open { margin-left: auto; color: var(--blue); font-size: 12px; text-decoration: none; }
.org-ws-chips { display: flex; flex-wrap: wrap; gap: 8px; padding: 12px 15px; }
.org-ws-chip { display: flex; align-items: center; gap: 8px; border: 1px solid var(--line); border-radius: var(--radius-small); padding: 7px 11px; text-decoration: none; color: var(--ink); }
.org-ws-chip:hover { border-color: var(--line-strong); }
.org-ws-chip .nm { font-size: 13px; }
.org-ws-chip .go { color: var(--blue); font-size: 11px; }
.org-ws-new { border-style: dashed; }
.org-ws-new input { border: 0; background: transparent; font: inherit; color: var(--blue); width: 140px; }
.org-ws-new input:focus-visible { outline: none; }
.org-card-foot { padding: 8px 15px; border-top: 1px dashed var(--line); }
```

- [ ] **Step 6: Run the account tests**

Run: `cd tuckit && uv run pytest tests/web/test_settings_account.py -v`
Expected: PASS (new tests + existing `test_account_page_lists_my_orgs`, `test_account_page_open_links_target_other_orgs` — note the latter asserts `href="/{org_b.slug}/{ws_b.slug}/"` which the chips still emit).

- [ ] **Step 7: Commit**

```bash
cd tuckit && git add tuckit/web/views/settings_account.py \
  tuckit/web/templates/web/partials/_org_row.html tuckit/web/static/web/app.css \
  tests/web/test_settings_account.py
git commit -m "feat: account overview enumerates workspaces per org with create + org-home links"
```

---

### Task 6: Switcher — navigable org headers + overview entry

Make org group headers link to org home; add a footer link to the account overview.

**Files:**
- Modify: `tuckit/tuckit/web/templates/web/partials/_workspace_switcher.html:16-31`
- Modify: `tuckit/tuckit/web/static/web/app.css` (org-header link style, if needed)
- Test: `tests/web/test_workspace_switch.py`

**Interfaces:**
- Consumes: `web:org_home` (Task 3), `web:settings_account` (existing), `switchable_workspaces` context (existing).

- [ ] **Step 1: Write the failing test**

Add to `tests/web/test_workspace_switch.py` (match the file's existing fixture style; if it has a logged-in workspace fixture, reuse it — otherwise build one as below):

```python
import pytest

from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.orgs import create_workspace


@pytest.mark.django_db
def test_switcher_links_org_header_to_org_home_and_overview(client, db):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create(email="u@a.com")
    OrgMember.objects.create(user=user, org=org, role="owner")
    ws = create_workspace(org, "Board")
    client.force_login(user)
    body = client.get(f"/{org.slug}/{ws.slug}/").content.decode()
    assert f'href="/{org.slug}/"' in body          # org header → org home
    assert 'href="/settings/account"' in body       # footer → overview
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd tuckit && uv run pytest tests/web/test_workspace_switch.py::test_switcher_links_org_header_to_org_home_and_overview -v`
Expected: FAIL (org header is a plain `<div>`, no overview link).

- [ ] **Step 3: Make org headers links + add overview footer**

In `tuckit/tuckit/web/templates/web/partials/_workspace_switcher.html`, replace the `{% regroup … %}` block and the footer:

```html
    {% regroup switchable_workspaces by org as org_groups %}
    {% for group in org_groups %}
      <a class="ws-menu-org ws-menu-org-link" href="{% url 'web:org_home' group.grouper.slug %}" role="menuitem">
        {{ group.grouper.name }}<span class="ws-menu-org-go">Home →</span>
      </a>
      {% for ws in group.list %}
        <a href="{% url 'web:home' ws.org.slug ws.slug %}"
           class="ws-menu-item{% if ws.id == current_workspace.id %} ws-menu-item--active{% endif %}" role="menuitem">
          <span class="ws-menu-name">{{ ws.name }}</span>
          {% if ws.id == current_workspace.id %}{% icon "check" "icon ws-check" %}{% endif %}
        </a>
      {% endfor %}
    {% endfor %}
    <div class="ws-menu-sep"></div>
    <a class="ws-menu-item ws-menu-settings" href="{% url 'web:settings_account' %}" role="menuitem">
      {% icon "settings" %}<span>All organizations</span>
    </a>
    <a class="ws-menu-item ws-menu-settings"
       href="{% url 'web:settings_workspace' current_workspace.org.slug current_workspace.slug %}" role="menuitem">
      {% icon "settings" %}<span>Workspace settings</span>
    </a>
```

- [ ] **Step 4: Add minimal CSS for the org-header link**

Append to `tuckit/tuckit/web/static/web/app.css`:

```css
/* --- Switcher: navigable org header --- */
.ws-menu-org-link { display: flex; align-items: center; justify-content: space-between; text-decoration: none; color: var(--muted); }
.ws-menu-org-link:hover { color: var(--blue); }
.ws-menu-org-go { font-size: 11px; opacity: 0; }
.ws-menu-org-link:hover .ws-menu-org-go { opacity: 1; }
```

(If `.ws-menu-org` already sets padding/typography, the link inherits it; keep the existing class on the element so spacing is unchanged.)

- [ ] **Step 5: Run the test**

Run: `cd tuckit && uv run pytest tests/web/test_workspace_switch.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd tuckit && git add tuckit/web/templates/web/partials/_workspace_switcher.html \
  tuckit/web/static/web/app.css tests/web/test_workspace_switch.py
git commit -m "feat: switcher org headers link to org home; add All organizations entry"
```

---

### Task 7: Breadcrumb in the app shell

A slim breadcrumb making the current level explicit and giving a one-level-up link. Shown only when there's an org/workspace context (hidden on auth/first-org pages).

**Files:**
- Create: `tuckit/tuckit/web/templates/web/partials/_breadcrumb.html`
- Modify: `tuckit/tuckit/web/templates/web/base.html:65` (include at top of `<main>`)
- Modify: `tuckit/tuckit/web/static/web/app.css` (breadcrumb style)
- Test: `tests/web/test_org_home.py` + `tests/web/test_home_shell.py`

**Interfaces:**
- Consumes: `request.org` (org home), `current_workspace` context processor (workspace pages), `web:org_home`, `web:settings_account`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/web/test_org_home.py`:

```python
@pytest.mark.django_db
def test_org_home_breadcrumb(org_ctx):
    client, org, owner, member, ws = org_ctx
    client.force_login(owner)
    body = client.get(f"/{org.slug}/").content.decode()
    assert 'class="crumbbar"' in body
    assert 'href="/settings/account"' in body   # "My orgs" → overview
```

Add to `tests/web/test_home_shell.py` (reuses the `client_local` + `workspace` fixtures in `tests/web/conftest.py`):

```python
@pytest.mark.django_db
def test_workspace_breadcrumb_links_to_org_home(client_local, workspace):
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'class="crumbbar"' in body
    assert f'href="/{workspace.org.slug}/"' in body    # org segment → org home
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd tuckit && uv run pytest tests/web/test_org_home.py::test_org_home_breadcrumb "tests/web/test_home_shell.py::test_workspace_breadcrumb_links_to_org_home" -v`
Expected: FAIL (no `.crumbbar` in output).

- [ ] **Step 3: Create the breadcrumb partial**

Create `tuckit/tuckit/web/templates/web/partials/_breadcrumb.html`:

```html
{% if request.workspace %}
<nav class="crumbbar" aria-label="Breadcrumb">
  <a href="{% url 'web:org_home' request.workspace.org.slug %}">{{ request.workspace.org.name }}</a>
  <span class="crumb-sep">/</span>
  <span class="crumb-here">{{ request.workspace.name }}</span>
</nav>
{% elif request.org %}
<nav class="crumbbar" aria-label="Breadcrumb">
  <a href="{% url 'web:settings_account' %}">My orgs</a>
  <span class="crumb-sep">/</span>
  <span class="crumb-here">{{ request.org.name }}</span>
</nav>
{% endif %}
```

Note: use `request.workspace` (the strict tenant workspace), NOT the fallback `current_workspace`, so the breadcrumb never shows a stale workspace on a non-workspace page.

- [ ] **Step 4: Include it in the shell**

In `tuckit/tuckit/web/templates/web/base.html`, change line 65:

```html
    <main class="main">{% include "web/partials/_breadcrumb.html" %}{% block main %}{% endblock %}</main>
```

- [ ] **Step 5: Add breadcrumb CSS (tokens only)**

Append to `tuckit/tuckit/web/static/web/app.css`:

```css
/* --- App-shell breadcrumb --- */
.crumbbar { display: flex; align-items: center; gap: 8px; padding: 10px 24px 0; font-size: 13px; }
.crumbbar a { color: var(--blue); text-decoration: none; }
.crumbbar a:hover { text-decoration: underline; }
.crumb-sep { color: var(--muted); }
.crumb-here { font-weight: 600; color: var(--ink); }
```

- [ ] **Step 6: Run the tests**

Run: `cd tuckit && uv run pytest tests/web/test_org_home.py "tests/web/test_home_shell.py" -v`
Expected: PASS.

- [ ] **Step 7: Full-suite regression**

Run: `cd tuckit && uv run pytest`
Expected: PASS. Watch specifically that `tests/web/test_design_system.py` still passes (no literal hex/radius introduced) and no page-layout tests broke from the added breadcrumb node.

- [ ] **Step 8: Commit**

```bash
cd tuckit && git add tuckit/web/templates/web/partials/_breadcrumb.html \
  tuckit/web/templates/web/base.html tuckit/web/static/web/app.css \
  tests/web/test_org_home.py tests/web/test_home_shell.py
git commit -m "feat: app-shell breadcrumb (org/workspace) with one-level-up links"
```

---

## Self-Review

**Spec coverage:**
- §5.1 Org home → Task 3. §5.2 Account overview → Tasks 2+5. §5.3 Switcher → Task 6. §5.4 Breadcrumb → Task 7. §5.5 New-workspace button → surfaced in Tasks 3 (org home) & 5 (overview). §5.6 Reserved slug → Task 1. §6 Remove old org settings → Task 4. §7 Routing/collision → Task 3 (route appended last) + Task 1 (reserved word) + Task 3 Step 9 (regression guard). §8 Service reuse → Tasks 2/3/5. §9 Access model unchanged → no membership code touched. §10 Testing → each task ships tests.
- Note (§5.3 partial): the switcher's "＋ New workspace" entry is intentionally omitted; create-workspace is surfaced on org home and the account overview (permission-gated forms) rather than duplicating a permission check in the switcher chrome. Flagged for the reviewer.

**Placeholder scan:** No TBD/TODO; every code/template/CSS block is complete.

**Type/name consistency:** `web:org_home` (one arg `org_slug`) is defined in Task 3 and consumed identically in Tasks 4-7. `list_user_orgs` row key `workspaces` defined in Task 2, consumed in Task 5. `can_create_ws` defined in Task 5 Step 3, used in Task 5 Step 4. Mutation URL names referenced in Task 3's template (`org_rename`, `invite_create`, `org_delete`, `workspace_create`) all exist in `urls.py` and are preserved by Task 4.

**Open item for the implementer:** `role-badge--{{ can_owner|yesno:'owner,member' }}` in Task 3 Step 6 renders `owner` or `member` for the badge *class*; the visible label branches correctly (owner/admin/member). If an admin-specific badge color is wanted, add `role-badge--admin` handling — cosmetic, out of scope.
