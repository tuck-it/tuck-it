import pytest

from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.slugs import normalize_slug, validate_slug


def test_normalize_trims_and_lowercases():
    assert normalize_slug("  Acme ") == "acme"


@pytest.mark.parametrize("raw", ["acme", "my-team", "a1", "ab", "a" * 32])
def test_valid_slugs_pass(raw):
    assert validate_slug(raw) == raw.lower()


@pytest.mark.parametrize("raw", [
    "Acme",            # uppercase (normalized then ok) -> actually becomes 'acme'
])
def test_uppercase_is_normalized_not_rejected(raw):
    assert validate_slug(raw) == "acme"


@pytest.mark.parametrize("raw", [
    "a b",             # space
    "a_b",             # underscore
    "café",            # unicode
    "😀",              # emoji
    "-ab",             # leading hyphen
    "ab-",             # trailing hyphen
    "a--b",            # consecutive hyphen
    "a",               # too short
    "a" * 33,          # too long
    "",                # empty
])
def test_bad_format_rejected(raw):
    with pytest.raises(InvalidValue):
        validate_slug(raw)


def test_org_reserved_rejected():
    for word in ["settings", "login", "cloud", "admin", "account", "check-slug"]:
        with pytest.raises(InvalidValue):
            validate_slug(word)


def test_first_org_is_reserved():
    with pytest.raises(InvalidValue):
        validate_slug("first-org")


def test_orgs_is_reserved():
    # /orgs/ is a permanent single-segment route (the org picker); an org
    # with this slug would be unreachable at its own /<slug>/ home.
    with pytest.raises(InvalidValue):
        validate_slug("orgs")


@pytest.mark.parametrize("segment", [
    "areas", "slices", "plans", "bites", "capture", "triage", "attention",
    "in-progress", "roadmap", "onboarding", "settings", "orgs",
])
def test_app_segments_are_reserved(segment):
    with pytest.raises(InvalidValue):
        validate_slug(segment)
