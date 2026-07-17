import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_lives_at_org_root(client_local, org):
    assert reverse("web:home", args=[org.slug]) == f"/{org.slug}/"
    assert client_local.get(f"/{org.slug}/").status_code == 200


@pytest.mark.django_db
def test_app_routes_have_no_workspace_segment(client_local, org):
    assert reverse("web:areas", args=[org.slug]) == f"/{org.slug}/areas/"
    assert client_local.get(f"/{org.slug}/areas/").status_code == 200


@pytest.mark.django_db
def test_login_beats_org_slug_route(client):
    resp = client.get("/login/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_org_home_route_is_gone():
    from django.urls import NoReverseMatch

    with pytest.raises(NoReverseMatch):
        reverse("web:org_home", args=["acme"])


@pytest.mark.django_db
def test_non_member_gets_404(client, django_user_model, org):
    other = django_user_model.objects.create_user(email="x@y.z", password="pw")
    client.force_login(other)
    assert client.get(f"/{org.slug}/").status_code == 404


@pytest.mark.django_db
def test_middleware_sets_active_org_id(client_local, org):
    client_local.get(f"/{org.slug}/")
    assert client_local.session["active_org_id"] == org.id
