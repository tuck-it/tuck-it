import pytest

from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.orgs import create_workspace


def _login(client, user, ws):
    client.force_login(user)
    session = client.session
    session["active_workspace_id"] = ws.id
    session.save()


@pytest.fixture
def org_ctx(client, db):
    org = Org.objects.create(name="Acme", slug="acme")
    owner = User.objects.create(username="o@a.com", email="o@a.com")
    OrgMember.objects.create(user=owner, org=org, role="owner")
    member = User.objects.create(username="m@a.com", email="m@a.com")
    OrgMember.objects.create(user=member, org=org, role="member")
    ws = create_workspace(org, "Board")
    return client, org, owner, member, ws


@pytest.mark.django_db
def test_org_page_lists_members_and_workspaces(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, owner, ws)
    resp = client.get("/settings/org")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Acme" in body
    assert "o@a.com" in body and "m@a.com" in body
    assert "Board" in body


@pytest.mark.django_db
def test_org_page_requires_login(client, db):
    resp = client.get("/settings/org")
    assert resp.status_code in (302, 403)


@pytest.mark.django_db
def test_owner_renames_org(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, owner, ws)
    resp = client.post("/settings/org/rename", {"name": "Beta"})
    assert resp.status_code == 200
    org.refresh_from_db()
    assert org.name == "Beta"


@pytest.mark.django_db
def test_member_cannot_rename_org(org_ctx):
    client, org, owner, member, ws = org_ctx
    _login(client, member, ws)
    resp = client.post("/settings/org/rename", {"name": "Beta"})
    assert resp.status_code == 403
    org.refresh_from_db()
    assert org.name == "Acme"
