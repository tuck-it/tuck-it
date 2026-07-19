import pytest
from starlette.testclient import TestClient

from tuckit.core.models import Org, User
from tuckit.core.services import oauth


@pytest.mark.django_db(transaction=True)
def test_401_has_resource_metadata_header(asgi_app):
    with TestClient(asgi_app) as client:
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert resp.status_code == 401
        assert "resource_metadata=" in resp.headers.get("www-authenticate", "")


@pytest.mark.django_db(transaction=True)
def test_oauth_access_token_passes_auth(asgi_app):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(email="a@b.com", password="pw123456")
    c = oauth.create_client("Claude Code", ["http://localhost:9999/cb"])
    access, _refresh, _ = oauth.issue_tokens(c, user, org, "mcp")
    with TestClient(asgi_app) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert resp.status_code not in (401, 404)  # reached MCP (may 421 on Host, like ApiToken test)
