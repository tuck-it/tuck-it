from authlib.common.security import generate_token
from authlib.integrations.httpx_client import OAuth2Client

from tuckit.core.services.social.providers import Provider, SocialIdentity


def _client(provider: Provider, cfg: dict, redirect_uri: str, state: str | None = None):
    return OAuth2Client(
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scope=provider.scope,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge_method="S256",
    )


def begin_url(provider: Provider, cfg: dict, redirect_uri: str) -> tuple[str, str, str]:
    """Build the provider authorize URL. Returns (url, state, code_verifier).
    Caller must persist state + code_verifier in the session for the callback."""
    code_verifier = generate_token(48)
    client = _client(provider, cfg, redirect_uri)
    url, state = client.create_authorization_url(provider.authorize_url, code_verifier=code_verifier)
    return url, state, code_verifier


def exchange_and_fetch(
    provider: Provider,
    cfg: dict,
    redirect_uri: str,
    session_state: str,
    code_verifier: str,
    authorization_response: str,
) -> SocialIdentity:
    """Exchange the callback code for a token and fetch the normalized identity.
    This is the ONLY function that talks to the provider; tests mock it."""
    client = _client(provider, cfg, redirect_uri, state=session_state)
    client.fetch_token(
        provider.token_url,
        authorization_response=authorization_response,
        code_verifier=code_verifier,
        headers=provider.token_endpoint_headers or None,
    )
    return provider.fetch_identity(client)
