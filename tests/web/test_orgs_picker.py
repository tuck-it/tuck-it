import pytest

from tuckit.core.models import Org, OrgMember


@pytest.mark.django_db
def test_picker_lists_every_org_the_user_belongs_to(client_local, org, django_user_model):
    second = Org.objects.create(name="Second Co", slug="second-co")
    user = django_user_model.objects.get(email="local@tuckit.local")
    OrgMember.objects.create(user=user, org=second, role="owner")

    resp = client_local.get("/orgs/")

    assert resp.status_code == 200
    body = resp.content.decode()
    assert org.name in body
    assert "Second Co" in body


@pytest.mark.django_db
def test_picker_empty_state_is_the_create_form(client, django_user_model):
    user = django_user_model.objects.create_user(email="new@x.z", password="pw")
    client.force_login(user)

    resp = client.get("/orgs/")

    assert resp.status_code == 200
    assert "<form" in resp.content.decode()


@pytest.mark.django_db
def test_picker_shows_signed_in_identity_and_logout(client, django_user_model):
    # A logged-in user with zero orgs lands here; the page must make it obvious
    # they ARE signed in (and let them switch accounts), or it reads like a
    # dead-end signup form.
    user = django_user_model.objects.create_user(email="who@x.z", password="pw")
    client.force_login(user)

    resp = client.get("/orgs/")

    body = resp.content.decode()
    assert "who@x.z" in body                 # identity is shown
    assert 'action="/logout/"' in body       # a logout control is present


@pytest.mark.django_db
def test_creating_an_org_lands_on_its_home(client, django_user_model):
    user = django_user_model.objects.create_user(email="new@x.z", password="pw")
    client.force_login(user)

    resp = client.post("/orgs/", {"name": "Fresh Co", "slug": "fresh-co"})

    assert resp.status_code == 302
    assert resp.headers["Location"] == "/fresh-co/"


@pytest.mark.django_db
def test_first_org_route_is_gone():
    from django.urls import NoReverseMatch, reverse

    with pytest.raises(NoReverseMatch):
        reverse("web:first_org")
