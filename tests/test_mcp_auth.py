import pytest
from starlette.testclient import TestClient

from tuckit.core.models import Org
from tuckit.core.services.tokens import generate_token


@pytest.mark.django_db(transaction=True)
def test_mcp_requires_bearer_token(asgi_app):
    with TestClient(asgi_app) as client:
        # No Authorization header -> middleware rejects before MCP runs.
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert resp.status_code == 401


@pytest.mark.django_db(transaction=True)
def test_authenticated_request_routes_through_mcp_rewrite(asgi_app):
    """Assert that a POST to bare /mcp WITH a bearer token reaches the gated MCP app."""
    # Create an org and generate a real token.
    org = Org.objects.create(name="Acme", slug="acme")
    _, raw_token = generate_token(org, "test-token")

    with TestClient(asgi_app) as client:
        # With Authorization header -> should reach the MCP mount (not 401/404).
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
            headers={"Authorization": f"Bearer {raw_token}"},
        )
        # The response should pass auth (not 401) and be routed to MCP (not 404).
        # The MCP app itself may return 4xx or other codes, but crucially not 401
        # (auth blocked) or 404 (fell through to Django).
        assert resp.status_code not in (401, 404)  # observed: 421 from MCP Host header validation
