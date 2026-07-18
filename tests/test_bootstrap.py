import pytest

from tuckit.core.management.commands.bootstrap import ensure_bootstrap
from tuckit.core.models import Area, OrgMember, User


@pytest.mark.django_db
def test_bootstrap_creates_full_local_setup():
    org, raw = ensure_bootstrap()
    assert User.objects.filter(email="local@tuckit.local").exists()
    assert OrgMember.objects.filter(org=org, role="owner").exists()
    assert Area.objects.filter(org=org, is_triage=False).count() == 0
    assert Area.objects.filter(org=org, is_triage=True).count() == 1
    assert raw is not None  # token minted on first run


@pytest.mark.django_db
def test_bootstrap_is_idempotent():
    ensure_bootstrap()
    org, raw = ensure_bootstrap()
    assert OrgMember.objects.count() == 1
    assert Area.objects.filter(org=org).count() == 1  # Triage only, not duplicated
    assert raw is None  # no new token on subsequent runs


@pytest.mark.django_db
def test_bootstrap_creates_inbox_area():
    org, _ = ensure_bootstrap()
    assert org.areas.filter(is_triage=True).count() == 1
