import pytest
from django.test import override_settings

from tuckit.core.models import ApiToken, User


@pytest.mark.django_db
def test_welcome_renders_standalone_for_logged_in_user(client_local):
    body = client_local.get("/welcome/").content.decode()
    assert '<html lang="en"' in body
    assert "web/welcome.css" in body
    assert "web/app.css" not in body           # standalone, no app shell
    assert "Nothing your agent does" in body   # emotional hero
    assert "/mcp" in body                       # endpoint present


@pytest.mark.django_db
def test_generate_key_creates_one_token_and_reveals_once(client_local, workspace):
    # NOTE: the web `workspace`/`client_local` fixtures bootstrap a token already,
    # so assert an INCREMENT of exactly one, not an absolute count of 0/1.
    before = ApiToken.objects.filter(workspace=workspace).count()
    resp = client_local.post("/welcome/key")
    assert resp.status_code == 200
    assert ApiToken.objects.filter(workspace=workspace).count() == before + 1
    # raw token revealed in the returned fragment
    assert "Bearer" in resp.content.decode()


@pytest.mark.django_db
@override_settings(REGISTRATION_OPEN=True)
def test_signup_redirects_to_welcome(client):
    resp = client.post("/register/", {
        "email": "new@x.com", "org_name": "NewCo", "slug": "newco", "password": "pw123456",
    })
    assert resp.status_code == 302
    assert resp["Location"].endswith("/welcome/")
