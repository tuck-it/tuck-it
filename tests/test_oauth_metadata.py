import pytest


@pytest.mark.django_db
def test_protected_resource_metadata(client):
    resp = client.get("/.well-known/oauth-protected-resource/mcp")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resource"].endswith("/mcp")
    assert isinstance(data["authorization_servers"], list) and data["authorization_servers"]


@pytest.mark.django_db
def test_authorization_server_metadata(client):
    resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authorization_endpoint"].endswith("/oauth/authorize")
    assert data["token_endpoint"].endswith("/oauth/token")
    assert data["registration_endpoint"].endswith("/oauth/register")
    assert data["code_challenge_methods_supported"] == ["S256"]
    assert "authorization_code" in data["grant_types_supported"]
