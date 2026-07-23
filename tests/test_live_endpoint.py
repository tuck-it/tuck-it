import pytest
from django.urls import reverse
from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.areas import create_area
from tuckit.core.services.slices import create_slice
from tuckit.core.services.activity import latest_activity_id


@pytest.fixture
def member(db):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(email="m@b.co", password="pw123456")
    OrgMember.objects.create(user=user, org=org, role="owner")
    return org, user


@pytest.mark.django_db
def test_live_204_when_nothing_new(client, member):
    org, user = member
    client.force_login(user)
    cursor = latest_activity_id(org)
    resp = client.get(reverse("web:live", args=[org.slug]) + f"?since={cursor}")
    assert resp.status_code == 204


@pytest.mark.django_db
def test_live_returns_new_events_and_cursor(client, member):
    org, user = member
    client.force_login(user)
    cursor = latest_activity_id(org)
    create_slice(create_area(org, "Backend"), "Login", status="building")
    resp = client.get(reverse("web:live", args=[org.slug]) + f"?since={cursor}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cursor"] > cursor
    verbs = {e["verb"] for e in data["events"]}
    assert "created" in verbs
    assert all(e["id"] > cursor for e in data["events"])
    # Cursor must be the newest DELIVERED event id (not a max read before the
    # fetch), so the next poll can't re-deliver an event already sent.
    assert data["cursor"] == max(e["id"] for e in data["events"])


@pytest.mark.django_db
def test_live_missing_since_treated_as_zero(client, member):
    org, user = member
    client.force_login(user)
    create_area(org, "Backend")
    resp = client.get(reverse("web:live", args=[org.slug]))
    assert resp.status_code == 200
    assert len(resp.json()["events"]) >= 1


@pytest.mark.django_db
def test_live_404_for_non_member(client, member):
    org, _ = member
    other = User.objects.create_user(email="x@b.co", password="pw123456")
    client.force_login(other)
    resp = client.get(reverse("web:live", args=[org.slug]))
    assert resp.status_code == 404
