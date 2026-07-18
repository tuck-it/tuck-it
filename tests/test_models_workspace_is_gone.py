import pytest


def test_workspace_model_no_longer_exists():
    import tuckit.core.models as models

    assert not hasattr(models, "Workspace")


@pytest.mark.django_db
def test_org_stat_snapshot_replaces_the_workspace_one(org):
    from tuckit.core.models import OrgStatSnapshot
    import datetime

    snap = OrgStatSnapshot.objects.create(org=org, date=datetime.date(2026, 7, 17))
    assert list(org.stat_snapshots.all()) == [snap]


@pytest.mark.django_db
def test_area_slug_unique_per_org(org):
    """Deferred here from Task 3: this invariant only becomes true once Workspace is
    gone, because an org could previously hold several workspaces each seeding a
    `triage` Area."""
    from django.db import IntegrityError

    from tuckit.core.models import Area

    Area.objects.create(org=org, name="Backend", slug="backend", rank="n")
    with pytest.raises(IntegrityError):
        Area.objects.create(org=org, name="Other", slug="backend", rank="o")


@pytest.mark.django_db
def test_tag_name_unique_per_org(org):
    from django.db import IntegrityError

    from tuckit.core.models import Tag

    Tag.objects.create(org=org, name="urgent")
    with pytest.raises(IntegrityError):
        Tag.objects.create(org=org, name="urgent")
