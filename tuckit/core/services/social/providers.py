from dataclasses import dataclass


@dataclass(frozen=True)
class SocialIdentity:
    uid: str
    email: str | None
    email_verified: bool
    name: str | None


def _google_identity(userinfo: dict) -> SocialIdentity:
    return SocialIdentity(
        uid=str(userinfo["sub"]),
        email=userinfo.get("email"),
        email_verified=bool(userinfo.get("email_verified")),
        name=userinfo.get("name"),
    )


def _github_identity(user: dict, emails: list) -> SocialIdentity:
    primary = next(
        (e["email"] for e in emails if e.get("primary") and e.get("verified")), None
    )
    return SocialIdentity(
        uid=str(user["id"]),
        email=primary,
        email_verified=primary is not None,
        name=user.get("name") or user.get("login"),
    )


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    authorize_url: str
    token_url: str
    scope: str
    userinfo_url: str
    token_endpoint_headers: dict

    def fetch_identity(self, client) -> SocialIdentity:
        """Call the provider's userinfo endpoint(s) with an authorized Authlib
        client and normalize to a SocialIdentity. `client` is an authenticated
        OAuth2Client (token already set)."""
        if self.name == "google":
            resp = client.get(self.userinfo_url)
            resp.raise_for_status()
            return _google_identity(resp.json())
        if self.name == "github":
            user = client.get(self.userinfo_url); user.raise_for_status()
            emails = client.get("https://api.github.com/user/emails"); emails.raise_for_status()
            return _github_identity(user.json(), emails.json())
        raise ValueError(f"Unknown provider: {self.name}")


PROVIDERS: dict[str, Provider] = {
    "google": Provider(
        name="google",
        label="Google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scope="openid email profile",
        userinfo_url="https://openidconnect.googleapis.com/v1/userinfo",
        token_endpoint_headers={},
    ),
    "github": Provider(
        name="github",
        label="GitHub",
        authorize_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        scope="read:user user:email",
        userinfo_url="https://api.github.com/user",
        token_endpoint_headers={"Accept": "application/json"},
    ),
}


def enabled_providers() -> list[Provider]:
    """Provider descriptors whose credentials are configured (settings.SOCIAL_PROVIDERS)."""
    from django.conf import settings

    configured = getattr(settings, "SOCIAL_PROVIDERS", {})
    return [PROVIDERS[name] for name in configured if name in PROVIDERS]
