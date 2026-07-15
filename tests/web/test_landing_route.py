"""landing_route is the single source of truth for where a logged-in user should
land based on account state. Leaf pages consult it instead of redirecting to each
other, which makes redirect cycles structurally impossible."""
import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from tuckit.core.models import User
from tuckit.core.services.orgs import create_org
from tuckit.web.auth import landing_route


def _req(user):
    r = RequestFactory().get("/")
    r.user = user
    r.session = SessionStore()
    return r


@pytest.mark.django_db
def test_landing_route_workspaceless_user_goes_to_first_org():
    u = User.objects.create(email="a@example.com")
    name, kwargs = landing_route(_req(u))
    assert name == "web:first_org"
    assert kwargs == {}


@pytest.mark.django_db
def test_landing_route_user_with_workspace_goes_home():
    u = User.objects.create(email="b@example.com")
    _org, ws = create_org(u, name="Acme")
    name, kwargs = landing_route(_req(u))
    assert name == "web:home"
    assert kwargs == {"org_slug": ws.org.slug, "ws_slug": ws.slug}
