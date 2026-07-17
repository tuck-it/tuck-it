import pytest

from tuckit.core.models import Org, OrgMember, User


@pytest.fixture
def user_ctx(client, db):
    user = User.objects.create(email="u@a.com")
    org = Org.objects.create(name="Acme", slug="acme")
    OrgMember.objects.create(user=user, org=org, role="owner")
    client.force_login(user)
    return client, org


@pytest.mark.django_db
def test_org_slug_available(user_ctx):
    client, org = user_ctx
    resp = client.get("/api/check-slug", {"slug": "freshname"})
    assert resp.status_code == 200
    assert resp.json() == {"available": True, "error": None}


@pytest.mark.django_db
def test_org_slug_taken(user_ctx):
    client, org = user_ctx
    resp = client.get("/api/check-slug", {"slug": "acme"})
    assert resp.json()["available"] is False


@pytest.mark.django_db
def test_org_slug_invalid_format(user_ctx):
    client, org = user_ctx
    resp = client.get("/api/check-slug", {"slug": "Bad Slug"})
    body = resp.json()
    assert body["available"] is False and body["error"]


@pytest.mark.django_db
@pytest.mark.parametrize("segment", ["areas", "capture", "roadmap", "orgs"])
def test_reserved_app_segment_is_unavailable(client, segment):
    resp = client.get(f"/api/check-slug?slug={segment}")
    assert resp.json() == {
        "available": False,
        "error": f"'{segment}' is reserved and can't be used.",
    }
