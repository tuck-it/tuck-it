import pytest
from django.test import override_settings

from tuckit.core.models import SocialAccount, User
from tuckit.core.services.social.auth import (
    SocialLoginError, create_social_account, resolve_social_login,
)


def _resolve(**kw):
    base = dict(provider="google", uid="sub-1", email="u@g.com", email_verified=True, name="U")
    base.update(kw)
    return resolve_social_login(**base)


@pytest.mark.django_db
def test_returning_login_matches_on_provider_uid():
    u = User.objects.create_user(email="old@g.com", password="pw123456")
    SocialAccount.objects.create(user=u, provider="google", uid="sub-1")
    # Even if the provider now reports a different email, uid wins:
    assert _resolve(email="new@g.com") == u
    assert SocialAccount.objects.count() == 1  # no duplicate created


@pytest.mark.django_db
def test_auto_link_when_email_verified_and_user_exists():
    u = User.objects.create_user(email="u@g.com", password="pw123456")
    result = _resolve(email_verified=True)
    assert result == u
    assert SocialAccount.objects.get(provider="google", uid="sub-1").user == u


@pytest.mark.django_db
def test_refuse_link_when_email_unverified():
    User.objects.create_user(email="u@g.com", password="pw123456")
    with pytest.raises(SocialLoginError):
        _resolve(email_verified=False)
    assert not SocialAccount.objects.exists()


@override_settings(REGISTRATION_OPEN=True)
@pytest.mark.django_db
def test_provision_new_user_when_registration_open():
    result = _resolve(email="fresh@g.com", email_verified=True)
    assert result.email == "fresh@g.com"
    assert not result.has_usable_password()
    assert SocialAccount.objects.get(provider="google", uid="sub-1").user == result


@override_settings(REGISTRATION_OPEN=False)
@pytest.mark.django_db
def test_refuse_provision_when_registration_closed():
    with pytest.raises(SocialLoginError):
        _resolve(email="fresh@g.com", email_verified=True)
    assert not User.objects.filter(email="fresh@g.com").exists()


@override_settings(REGISTRATION_OPEN=True)
@pytest.mark.django_db
def test_provision_requires_email():
    with pytest.raises(SocialLoginError):
        _resolve(email=None, email_verified=False)


@pytest.mark.django_db
def test_create_social_account_is_passwordless():
    u = create_social_account(email="p@g.com", name="P")
    assert u.email == "p@g.com"
    assert not u.has_usable_password()
