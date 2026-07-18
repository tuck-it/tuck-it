import pytest
from pathlib import Path

from tuckit.core.models import Org
from tuckit.core.services.tokens import generate_token, hash_token, list_tokens, resolve_org, revoke_token


@pytest.fixture
def org(db):
    return Org.objects.create(name="Acme", slug="acme")


@pytest.mark.django_db
def test_generate_token_stores_only_hash(org):
    token, raw = generate_token(org, "cli")
    assert raw and len(raw) > 20
    assert token.token_hash == hash_token(raw)
    assert token.token_hash != raw


@pytest.mark.django_db
def test_resolve_org_returns_owner_and_stamps_use(org):
    _, raw = generate_token(org, "cli")
    resolved = resolve_org(raw)
    assert resolved == org
    from tuckit.core.models import ApiToken

    assert ApiToken.objects.get(org=org).last_used_at is not None


@pytest.mark.django_db
def test_resolve_org_returns_none_for_bad_token(org):
    generate_token(org, "cli")
    assert resolve_org("not-a-real-token") is None


@pytest.mark.django_db
def test_list_and_revoke_tokens():
    org = Org.objects.create(name="Acme", slug="acme")
    t, _ = generate_token(org, "a")
    assert list(list_tokens(org)) == [t]
    revoke_token(org, t.id)
    assert list(list_tokens(org)) == []


@pytest.mark.django_db
def test_revoke_token_is_org_scoped(org):
    other = Org.objects.create(name="Other Org", slug="other-org")
    token, _ = generate_token(other, "cli")
    revoke_token(org, token.id)
    assert list(list_tokens(other)) == [token]


def test_new_neutral_and_warn_tokens_present():
    static = Path(__file__).resolve().parent.parent / "tuckit/web/static/web"
    brand = (static / "tokens.brand.css").read_text()
    product = (static / "tokens.product.css").read_text()
    # --warn defined for both light and dark in the brand tokens
    assert brand.count("--warn:") >= 2
    # --active is aliased in the product tokens and resolves per-theme via --paper-deep
    assert "--active: var(--paper-deep)" in product
