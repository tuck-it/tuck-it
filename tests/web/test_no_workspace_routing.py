"""A logged-in user with no accessible workspace (e.g. a createsuperuser account
that bypassed the register() service) must not get stuck at the app root.
Regression test for the ERR_TOO_MANY_REDIRECTS login loop; they land on a
standalone "create your first org" page instead."""
import pytest

from tuckit.core.models import OrgMember, User, Workspace


@pytest.mark.django_db
def test_root_redirects_workspaceless_user_to_first_org(client):
    u = User.objects.create(email="lonely@example.com")
    client.force_login(u)
    r = client.get("/")
    assert r.status_code == 302
    assert r.headers["Location"] == "/first-org/"


@pytest.mark.django_db
def test_no_redirect_loop_for_workspaceless_user(client):
    u = User.objects.create(email="lonely3@example.com")
    client.force_login(u)
    r = client.get("/", follow=True)
    # terminates on a real page (no loop) — the first-org page
    assert r.status_code == 200
    assert r.request["PATH_INFO"] == "/first-org/"
    assert len(r.redirect_chain) == 1


@pytest.mark.django_db
def test_first_org_page_renders_for_workspaceless_user(client):
    u = User.objects.create(email="lonely4@example.com")
    client.force_login(u)
    body = client.get("/first-org/").content.decode()
    assert "Create your first organization" in body


@pytest.mark.django_db
def test_first_org_post_creates_org_and_lands_on_home(client):
    u = User.objects.create(email="lonely5@example.com")
    client.force_login(u)
    r = client.post("/first-org/", {"name": "Acme"})
    assert r.status_code == 302
    assert OrgMember.objects.filter(user=u, role="owner").exists()
    ws = Workspace.objects.get(org__members__user=u)
    assert r.headers["Location"] == f"/{ws.org.slug}/{ws.slug}/"


@pytest.mark.django_db
def test_first_org_redirects_to_home_when_user_already_has_workspace(client, org):
    # org fixture creates local@tuckit.local with an org (and workspace, until Task 12)
    u = User.objects.get(email="local@tuckit.local")
    client.force_login(u)
    r = client.get("/first-org/")
    assert r.status_code == 302
    assert r.headers["Location"].startswith(f"/{org.slug}/")
