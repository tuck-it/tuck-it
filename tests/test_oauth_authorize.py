from urllib.parse import urlparse, parse_qs

import pytest

from tuckit.core.models import Org, User, OrgMember, OAuthAuthorizationCode
from tuckit.core.services import oauth


@pytest.fixture
def setup(db):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(email="a@b.com", password="pw123456")
    OrgMember.objects.create(user=user, org=org, role="owner")
    client_obj = oauth.create_client("Claude Code", ["http://localhost:9999/cb"])
    return org, user, client_obj


def _params(client_obj, verifier="verifier-1234567890-abcdefghij"):
    return {
        "response_type": "code",
        "client_id": client_obj.client_id,
        "redirect_uri": "http://localhost:9999/cb",
        "code_challenge": oauth.s256(verifier),
        "code_challenge_method": "S256",
        "state": "xyz",
        "scope": "mcp",
    }


@pytest.mark.django_db
def test_authorize_requires_login(client, setup):
    _org, _user, client_obj = setup
    resp = client.get("/oauth/authorize", _params(client_obj))
    assert resp.status_code == 302 and "/login" in resp["Location"]


@pytest.mark.django_db
def test_authorize_get_renders_consent(client, setup):
    _org, user, client_obj = setup
    client.force_login(user)
    resp = client.get("/oauth/authorize", _params(client_obj))
    assert resp.status_code == 200
    assert b"Claude Code" in resp.content


@pytest.mark.django_db
def test_authorize_bad_redirect_uri_shows_error_no_redirect(client, setup):
    _org, user, client_obj = setup
    client.force_login(user)
    p = _params(client_obj)
    p["redirect_uri"] = "http://evil/cb"
    resp = client.get("/oauth/authorize", p)
    assert resp.status_code == 400  # error page, NOT a redirect


@pytest.mark.django_db
def test_authorize_post_issues_code(client, setup):
    org, user, client_obj = setup
    client.force_login(user)
    p = _params(client_obj)
    p["org_id"] = str(org.id)
    resp = client.post("/oauth/authorize", p)
    assert resp.status_code == 302
    q = parse_qs(urlparse(resp["Location"]).query)
    assert q["state"] == ["xyz"]
    assert q["code"]
    assert OAuthAuthorizationCode.objects.count() == 1
