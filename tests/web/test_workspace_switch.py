import pytest

from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.orgs import create_workspace


@pytest.fixture
def two_workspaces(db):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create(email="o@a.com")
    user.set_password("pw123456")
    user.save()
    OrgMember.objects.create(user=user, org=org, role="owner")
    a = create_workspace(org, "Alpha")
    b = create_workspace(org, "Beta")
    return user, a, b


@pytest.mark.django_db
def test_navigating_to_org_sets_active(client, two_workspaces):
    # Visiting an org's URL makes it the active org (TenantMiddleware records it
    # in the session) — the app's tenant is org-only now.
    user, a, b = two_workspaces
    client.force_login(user)
    resp = client.get(f"/{b.org.slug}/")
    assert resp.status_code == 200
    assert client.session["active_org_id"] == b.org.id


# Removed in Task 6: test_switcher_renders_sibling_workspace_links asserted the
# switcher links to sibling *workspaces* of one org. With workspace gone from the
# URL, a,b share an org so both asserts collapsed to the same href="/<org>/" —
# a vacuous always-true check. The switcher becomes a flat *org* list in Task 9,
# which deletes this whole file after porting any live coverage into test_sidebar.


@pytest.mark.django_db
def test_old_switch_route_is_gone(client, two_workspaces):
    # The POST switch endpoints were removed when switching became link-based.
    # Trailing slash: since Task 3 the org-home catch-all (<slug:org_slug>/)
    # matches any single path segment, so a slash-less request would instead
    # trip Django's APPEND_SLASH/POST safety net rather than exercise the
    # 404-for-unknown-org path this test cares about.
    user, a, b = two_workspaces
    client.force_login(user)
    assert client.post("/switch-workspace/", {"workspace_id": b.id}).status_code == 404


@pytest.mark.django_db
def test_navigating_to_inaccessible_workspace_404s(client, two_workspaces):
    # A non-member must never reach (or learn the existence of) a foreign
    # workspace: TenantMiddleware 404s instead of the old 403.
    user, a, b = two_workspaces
    other_org = Org.objects.create(name="Other", slug="other")
    outsider_ws = create_workspace(other_org, "Foreign")
    client.force_login(user)
    resp = client.get(f"/{outsider_ws.org.slug}/")
    assert resp.status_code == 404


# test_create_workspace_in_org removed in Task 8: /settings/workspaces/new and
# the workspace-creation UI are gone along with the rest of the
# workspace-settings surface (settings IA merge). Workspace creation via
# create_workspace() itself is still covered at the service layer
# (tests/test_services_orgs.py).


@pytest.mark.django_db
def test_switcher_links_org_header_to_org_home_and_overview(client, db):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create(email="u@a.com")
    OrgMember.objects.create(user=user, org=org, role="owner")
    ws = create_workspace(org, "Board")
    client.force_login(user)
    body = client.get(f"/{org.slug}/").content.decode()
    assert f'href="/{org.slug}/"' in body          # org header → org home
    assert f'href="/{org.slug}/settings/account/organizations"' in body       # footer → overview


@pytest.mark.django_db
def test_switcher_all_orgs_points_to_account_settings(client, db):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create(email="u2@a.com")
    OrgMember.objects.create(user=user, org=org, role="owner")
    ws = create_workspace(org, "Product")
    client.force_login(user)
    body = client.get(f"/{org.slug}/").content.decode()
    assert f'href="/{org.slug}/settings/account/organizations"' in body
