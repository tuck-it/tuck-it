import pytest
from tuckit.core.models import Org, User, OAuthAccessToken
from tuckit.core.services import oauth


@pytest.fixture
def actors(db):
    org = Org.objects.create(name="Acme", slug="acme")
    user = User.objects.create_user(email="a@b.com", password="pw123456")
    client = oauth.create_client("Claude Code", ["http://localhost:9999/cb"])
    return org, user, client


@pytest.mark.django_db
def test_pkce_roundtrip():
    verifier = "abc123-verifier-value-long-enough-string"
    assert oauth.verify_pkce(oauth.s256(verifier), verifier) is True
    assert oauth.verify_pkce(oauth.s256(verifier), "wrong") is False


@pytest.mark.django_db
def test_auth_code_is_single_use(actors):
    org, user, client = actors
    raw = oauth.create_authorization_code(
        client, user, org, "http://localhost:9999/cb", "chal", scope="mcp"
    )
    first = oauth.consume_authorization_code(raw, client, "http://localhost:9999/cb")
    assert first is not None and first.org == org
    # second use fails (deleted)
    assert oauth.consume_authorization_code(raw, client, "http://localhost:9999/cb") is None


@pytest.mark.django_db
def test_consume_rejects_redirect_uri_mismatch(actors):
    org, user, client = actors
    raw = oauth.create_authorization_code(client, user, org, "http://localhost:9999/cb", "chal")
    assert oauth.consume_authorization_code(raw, client, "http://evil/cb") is None


@pytest.mark.django_db
def test_issue_and_resolve_access_token(actors):
    org, user, client = actors
    access, refresh, expires_in = oauth.issue_tokens(client, user, org, "mcp")
    assert expires_in == oauth.ACCESS_TTL_SECONDS
    assert oauth.resolve_oauth_org(access) == org
    assert oauth.resolve_oauth_org("nope") is None


@pytest.mark.django_db
def test_refresh_rotation_revokes_old(actors):
    org, user, client = actors
    _access, refresh, _ = oauth.issue_tokens(client, user, org, "mcp")
    rotated = oauth.rotate_refresh_token(refresh)
    assert rotated is not None
    new_access, new_refresh, expires_in, scope = rotated
    assert oauth.resolve_oauth_org(new_access) == org
    # old refresh no longer works
    assert oauth.rotate_refresh_token(refresh) is None
