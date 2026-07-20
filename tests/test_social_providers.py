from django.test import override_settings

from tuckit.core.services.social.providers import (
    PROVIDERS, SocialIdentity, _github_identity, _google_identity, enabled_providers,
)


def test_google_identity_from_userinfo():
    ident = _google_identity(
        {"sub": "sub-1", "email": "u@g.com", "email_verified": True, "name": "U"}
    )
    assert ident == SocialIdentity(uid="sub-1", email="u@g.com", email_verified=True, name="U")


def test_google_identity_unverified_defaults_false():
    ident = _google_identity({"sub": "s", "email": "u@g.com"})
    assert ident.email_verified is False


def test_github_identity_picks_primary_verified_email():
    user = {"id": 42, "login": "octo", "name": "Octo Cat"}
    emails = [
        {"email": "secondary@x.com", "primary": False, "verified": True},
        {"email": "octo@x.com", "primary": True, "verified": True},
    ]
    ident = _github_identity(user, emails)
    assert ident == SocialIdentity(uid="42", email="octo@x.com", email_verified=True, name="Octo Cat")


def test_github_identity_no_verified_primary():
    user = {"id": 7, "login": "no-name", "name": None}
    emails = [{"email": "e@x.com", "primary": True, "verified": False}]
    ident = _github_identity(user, emails)
    assert ident.email is None
    assert ident.email_verified is False
    assert ident.name == "no-name"  # falls back to login


@override_settings(SOCIAL_PROVIDERS={"google": {"client_id": "id", "client_secret": "sec"}})
def test_enabled_providers_reflects_settings():
    names = [p.name for p in enabled_providers()]
    assert names == ["google"]


@override_settings(SOCIAL_PROVIDERS={})
def test_enabled_providers_empty_when_unconfigured():
    assert enabled_providers() == []


def test_registry_has_google_and_github():
    assert set(PROVIDERS) == {"google", "github"}
    assert PROVIDERS["google"].label == "Google"
    assert PROVIDERS["github"].label == "GitHub"
