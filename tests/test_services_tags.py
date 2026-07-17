import pytest

from tuckit.core.models import Org
from tuckit.core.services.tags import get_or_create_tags, list_tags


@pytest.fixture
def org(db):
    return Org.objects.create(name="Acme", slug="acme")


@pytest.mark.django_db
def test_get_or_create_tags_is_idempotent(org):
    first = get_or_create_tags(org, ["bug", "someday"])
    second = get_or_create_tags(org, ["bug"])
    assert {t.name for t in first} == {"bug", "someday"}
    assert second[0].id == next(t.id for t in first if t.name == "bug")
    assert list_tags(org).count() == 2
