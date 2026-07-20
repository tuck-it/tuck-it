import pytest
from django.db import IntegrityError

from tuckit.core.models import Area, Bite, Plan, Slice, Tag


@pytest.mark.django_db
def test_area_slug_unique_per_org(org):
    Area.objects.create(org=org, name="Backend", slug="backend", rank="a0")
    with pytest.raises(IntegrityError):
        Area.objects.create(org=org, name="Backend2", slug="backend", rank="a1")


@pytest.mark.django_db
def test_slice_defaults(org):
    area = Area.objects.create(org=org, name="Backend", slug="backend", rank="a0")
    s = Slice.objects.create(area=area, title="Auth", rank="a0")
    assert s.status == "planned"
    assert s.spec == ""
    assert s.source == "human"
    assert s.completed_at is None


@pytest.mark.django_db
def test_slice_tags_are_org_tags(org):
    area = Area.objects.create(org=org, name="Backend", slug="backend", rank="a0")
    s = Slice.objects.create(area=area, title="Auth", rank="a0")
    tag = Tag.objects.create(org=org, name="bug")
    s.tags.add(tag)
    assert list(s.tags.all()) == [tag]


@pytest.mark.django_db
def test_tag_unique_per_org(org):
    Tag.objects.create(org=org, name="bug")
    with pytest.raises(IntegrityError):
        Tag.objects.create(org=org, name="bug")


@pytest.mark.django_db
def test_bite_requires_plan(org):
    area = Area.objects.create(org=org, name="Backend", slug="backend", rank="a0")
    s = Slice.objects.create(area=area, title="Auth", rank="a0")
    p = Plan.objects.create(slice=s, title="Plan")
    b = Bite.objects.create(plan=p, title="JWT", rank="a0")
    assert b.status == "todo"
    assert b.plan_id == p.id
