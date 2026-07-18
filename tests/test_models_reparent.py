import pytest

from tuckit.core.models import ApiToken, Area, Org, Tag


@pytest.fixture
def org(db):
    return Org.objects.create(name="Acme", slug="acme")


@pytest.mark.django_db
def test_area_belongs_to_org(org):
    area = Area.objects.create(org=org, name="Backend", slug="backend", rank="n")
    assert area.org == org
    assert list(org.areas.all()) == [area]


@pytest.mark.django_db
def test_tag_belongs_to_org(org):
    tag = Tag.objects.create(org=org, name="urgent")
    assert list(org.tags.all()) == [tag]


@pytest.mark.django_db
def test_api_token_belongs_to_org(org):
    token = ApiToken.objects.create(org=org, name="agent", token_hash="x" * 64)
    assert list(org.tokens.all()) == [token]
