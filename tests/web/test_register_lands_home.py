import pytest
from django.test import override_settings

from tuckit.core.models import User, Workspace


@pytest.mark.django_db
@override_settings(REGISTRATION_OPEN=True)
def test_self_service_register_lands_on_home(client):
    r = client.post("/register/", {
        "email": "new@example.com", "org_name": "Acme",
        "slug": "acme", "password": "pw12345678",
    })
    assert r.status_code == 302
    u = User.objects.get(email="new@example.com")
    ws = Workspace.objects.get(org__members__user=u)
    assert r.headers["Location"] == f"/{ws.org.slug}/"
