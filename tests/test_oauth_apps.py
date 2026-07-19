import pytest

from tuckit.core.models import Org, User, OrgMember
from tuckit.core.services import oauth
from tuckit.core.services.oauth_apps import list_connected_apps, disconnect_app


@pytest.fixture
def connected(db):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(email="a@b.com", password="pw123456")
    OrgMember.objects.create(user=user, org=org, role="owner")
    c = oauth.create_client("Claude Code", ["http://localhost:9999/cb"])
    access, _r, _ = oauth.issue_tokens(c, user, org, "mcp")
    return org, user, c, access


@pytest.mark.django_db
def test_list_connected_apps(connected):
    org, _user, c, _access = connected
    apps = list_connected_apps(org)
    assert len(apps) == 1
    assert apps[0]["name"] == "Claude Code"
    assert apps[0]["client_id"] == c.client_id


@pytest.mark.django_db
def test_disconnect_revokes_tokens(connected):
    org, _user, c, access = connected
    n = disconnect_app(org, c.client_id)
    assert n >= 1
    assert oauth.resolve_oauth_org(access) is None
    assert list_connected_apps(org) == []
