import pytest
from django.http import Http404
from django.test import RequestFactory

from tuckit.core.models import Org, OrgMember, User
from tuckit.web.middleware import TenantMiddleware


def _view(request, *args, **kwargs):
    return None


@pytest.fixture
def tenant(db):
    member = User.objects.create(email="member@a.com")
    outsider = User.objects.create(email="outsider@a.com")
    org = Org.objects.create(name="Acme", slug="acme")
    OrgMember.objects.create(user=member, org=org, role="owner")
    return member, outsider, org


@pytest.mark.django_db
def test_member_resolves_and_strips_kwargs(tenant):
    member, _outsider, org = tenant
    request = RequestFactory().get(f"/{org.slug}/")
    request.user = member
    request.session = {}
    view_kwargs = {"org_slug": org.slug, "keep": "me"}

    mw = TenantMiddleware(lambda r: r)
    result = mw.process_view(request, _view, [], view_kwargs)

    assert result is None
    assert request.org == org
    # slug kwarg stripped so content views keep their signatures
    assert "org_slug" not in view_kwargs
    assert view_kwargs == {"keep": "me"}
    # active org persisted for root_redirect / switcher
    assert request.session["active_org_id"] == org.id


@pytest.mark.django_db
def test_nonmember_raises_404(tenant):
    _member, outsider, org = tenant
    request = RequestFactory().get(f"/{org.slug}/")
    request.user = outsider
    request.session = {}
    view_kwargs = {"org_slug": org.slug}

    mw = TenantMiddleware(lambda r: r)
    with pytest.raises(Http404):
        mw.process_view(request, _view, [], view_kwargs)


@pytest.mark.django_db
def test_no_org_slug_leaves_request_org_none(tenant):
    member, _outsider, _org = tenant
    request = RequestFactory().get("/login/")
    request.user = member
    request.session = {}

    mw = TenantMiddleware(lambda r: r)
    result = mw.process_view(request, _view, [], {})

    assert result is None
    assert request.org is None
