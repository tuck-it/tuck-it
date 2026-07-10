import pytest


@pytest.mark.django_db
def test_healthcheck_returns_ok(client):
    resp = client.get("/healthcheck")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
