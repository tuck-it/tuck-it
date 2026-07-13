import pytest
from django.test import override_settings

from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.invitations import create_invitation


@pytest.mark.django_db
def test_login_screen_uses_design_system(client, workspace):
    body = client.get("/login/").content.decode()
    # standalone page, English, not the app shell
    assert '<html lang="en"' in body
    assert 'class="auth-card"' in body
    # token chain linked in order, ending in auth.css; app.css NOT linked
    i_brand = body.find("tokens.brand.css")
    i_product = body.find("tokens.product.css")
    i_base = body.find("web/base.css")
    i_auth = body.find("web/auth.css")
    assert -1 not in (i_brand, i_product, i_base, i_auth)
    assert i_brand < i_product < i_base < i_auth
    assert "web/app.css" not in body
    # login form fields preserved (names unchanged)
    assert 'name="username"' in body
    assert 'name="password"' in body


@pytest.mark.django_db
@override_settings(REGISTRATION_OPEN=True)
def test_register_screen_uses_design_system(client):
    body = client.get("/register/").content.decode()
    assert 'class="auth-card"' in body
    assert "web/auth.css" in body
    assert "web/app.css" not in body
    for name in ("email", "org_name", "slug", "password"):
        assert f'name="{name}"' in body


@pytest.mark.django_db
@override_settings(REGISTRATION_OPEN=True)
def test_register_duplicate_slug_shows_styled_error(client):
    Org.objects.create(name="Taken", slug="taken")
    resp = client.post("/register/", {
        "email": "new@x.com", "org_name": "X", "slug": "taken", "password": "pw123456",
    })
    assert resp.status_code == 200
    assert 'class="auth-error"' in resp.content.decode()


@pytest.mark.django_db
def test_invite_screen_uses_design_system(client):
    org = Org.objects.create(name="Acme", slug="acme")
    owner = User.objects.create(email="o@a.com")
    OrgMember.objects.create(user=owner, org=org, role="owner")
    inv = create_invitation(org=org, email="new@x.com", role="member", invited_by=owner)
    body = client.get(f"/invite/{inv.token}/").content.decode()
    assert 'class="auth-card"' in body
    assert "web/auth.css" in body
    assert "web/app.css" not in body
    assert "Join Acme" in body          # English heading with org name
    assert "new@x.com" in body          # locked email shown for anonymous invitee
    assert 'name="password"' in body
