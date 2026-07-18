"""A logged-in user with no accessible org (e.g. a createsuperuser account
that bypassed the register() service) must not get stuck at the app root.
Regression test for the ERR_TOO_MANY_REDIRECTS login loop; they land on the
org picker (/orgs/, see test_orgs_picker.py) instead."""
import pytest

from tuckit.core.models import User


@pytest.mark.django_db
def test_root_redirects_workspaceless_user_to_org_picker(client):
    u = User.objects.create(email="lonely@example.com")
    client.force_login(u)
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/orgs/"


@pytest.mark.django_db
def test_no_redirect_loop_for_workspaceless_user(client):
    u = User.objects.create(email="lonely3@example.com")
    client.force_login(u)
    r = client.get("/", follow=True)
    # terminates on a real page (no loop)
    assert r.status_code == 200
    assert r.request["PATH_INFO"] == "/orgs/"
    assert len(r.redirect_chain) == 1
