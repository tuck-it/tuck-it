import pytest

from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.areas import create_area
from tuckit.core.services.bites import create_bite
from tuckit.core.services.orgs import create_workspace
from tuckit.core.services.slices import create_slice


@pytest.fixture
def owner_with_area(client, db):
    org = Org.objects.create(name="Acme", slug="acme")
    owner = User.objects.create(email="o@a.com")
    OrgMember.objects.create(user=owner, org=org, role="owner")
    ws = create_workspace(org, "Board")
    create_area(ws, "Backend")
    client.force_login(owner)
    session = client.session
    session["active_workspace_id"] = ws.id
    session.save()
    return client, org, ws


@pytest.mark.django_db
def test_sidebar_areas_visible_on_org_only_settings_page(owner_with_area):
    """settings/<org_slug>/ has no ws_slug in the URL, so TenantMiddleware leaves
    request.workspace None on this route. sidebar_areas (and the sibling
    count context processors) must still resolve a workspace via the same
    session/first-accessible fallback the workspace switcher itself uses —
    otherwise the sidebar shows a workspace name but an empty Areas list."""
    client, org, _ws = owner_with_area
    body = client.get(f"/settings/{org.slug}/").content.decode()
    assert "Backend" in body


@pytest.mark.django_db
def test_sidebar_areas_visible_on_account_settings_page(owner_with_area):
    client, _org, _ws = owner_with_area
    body = client.get("/settings/account").content.decode()
    assert "Backend" in body


@pytest.mark.django_db
def test_onboarding_hidden_stays_hidden_after_area_deleted(client_local, workspace):
    from tuckit.core.models import ActivityEvent
    from tuckit.core.services.areas import delete_area
    area = create_area(workspace, "Backend")
    sl = create_slice(area, "Retry webhooks", status="planned")
    create_bite(sl, "Add backoff")
    ActivityEvent.objects.create(
        workspace=workspace, actor="agent", verb="created",
        target_type="slice", target_id=sl.id, target_label=sl.title,
    )
    p = f"/{workspace.org.slug}/{workspace.slug}"
    # First load observes completion → sticky flag set.
    assert "Get started" not in client_local.get(f"{p}/").content.decode()
    workspace.refresh_from_db()
    assert workspace.onboarding_completed is True
    # Delete the only Area → has_area now False, but widget must NOT return.
    delete_area(area)
    assert "Get started" not in client_local.get(f"{p}/").content.decode()
