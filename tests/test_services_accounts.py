import pytest

from tuckit.core.models import Area, OrgMember, User
from tuckit.core.services.accounts import create_account, register
from tuckit.core.services.exceptions import InvalidValue


@pytest.mark.django_db
def test_register_creates_user_and_org():
    user, org = register(
        email="a@b.com", org_name="Space", slug="space", password="pw123456"
    )
    assert user.email == "a@b.com"
    assert user.check_password("pw123456")
    assert org.slug == "space"
    assert OrgMember.objects.filter(user=user, org=org, role="owner").exists()
    assert Area.objects.filter(org=org).count() == 0  # no magic area — Inbox starts empty


@pytest.mark.django_db
def test_register_does_not_set_username():
    user, _ = register(
        email="a@b.com", org_name="S", slug="s0", password="pw123456"
    )
    assert user.username is None


@pytest.mark.django_db
def test_register_duplicate_org_slug_raises():
    register(email="a@b.com", org_name="S", slug="dup", password="pw123456")
    with pytest.raises(InvalidValue):
        register(email="c@d.com", org_name="S2", slug="dup", password="pw123456")


@pytest.mark.django_db
def test_register_duplicate_email_raises():
    register(email="same@b.com", org_name="S", slug="s1", password="pw123456")
    with pytest.raises(InvalidValue):
        register(email="same@b.com", org_name="S2", slug="s2", password="pw123456")


@pytest.mark.django_db
def test_register_rejects_empty_password():
    with pytest.raises(InvalidValue):
        register(email="a@b.com", org_name="S", slug="s0", password="")


@pytest.mark.django_db
def test_register_rejects_weak_password():
    with pytest.raises(InvalidValue):
        register(email="a@b.com", org_name="S", slug="s0", password="abc")


@pytest.mark.django_db
def test_register_runs_signup_hook():
    from django.test import override_settings

    seen = {}

    def _hook(*, user, org):
        seen["ok"] = (user.email, org.slug)

    import tests.test_services_accounts as mod
    mod._hook = _hook
    with override_settings(TUCKIT_SIGNUP_HOOK="tests.test_services_accounts._hook"):
        register(email="h@b.com", org_name="H", slug="h0", password="pw123456")
    assert seen["ok"] == ("h@b.com", "h0")


@pytest.mark.django_db
def test_create_account_makes_user_with_no_org():
    user = create_account(email="solo@x.z", password="Sup3rSecret!x")
    assert user.pk and user.email == "solo@x.z"
    assert not OrgMember.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_create_account_rejects_duplicate_email():
    create_account(email="dupe@x.z", password="Sup3rSecret!x")
    with pytest.raises(InvalidValue):
        create_account(email="dupe@x.z", password="Sup3rSecret!x")


@pytest.mark.django_db
def test_create_account_rejects_weak_password():
    with pytest.raises(InvalidValue):
        create_account(email="weak@x.z", password="123")
