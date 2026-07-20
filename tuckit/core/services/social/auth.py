from django.conf import settings
from django.db import transaction

from tuckit.core.models import SocialAccount, User


class SocialLoginError(Exception):
    """Raised when a social login cannot proceed. The message is user-safe."""


def create_social_account(*, email: str, name: str | None) -> User:
    """Create a passwordless user for a social sign-up. Mirrors create_account's
    duplicate/empty-email checks but sets an unusable password (login is via the
    provider). Does NOT create an org and does NOT fire the signup hook — that
    happens later at first create_org, same as the email flow."""
    email = (email or "").strip()
    if not email:
        raise SocialLoginError("This provider did not return a usable email address.")
    if User.objects.filter(email=email).exists():
        raise SocialLoginError(f"A user with this email already exists: {email}")
    user = User(email=email)
    user.set_unusable_password()
    user.save()
    return user


@transaction.atomic
def resolve_social_login(
    *, provider: str, uid: str, email: str | None, email_verified: bool, name: str | None
) -> User:
    """Turn a verified provider identity into a logged-in-able User.

    Branch order IS the security contract:
      1. Known (provider, uid) -> that user (returning login).
      2. Existing user matches the email:
         2a. Email verified -> auto-link.
         2b. Email unverified -> refuse (anti-takeover).
      3. No such user:
         3a. REGISTRATION_OPEN -> provision a passwordless account.
         3b. Registration closed -> refuse."""
    existing = SocialAccount.objects.filter(provider=provider, uid=uid).select_related("user").first()
    if existing:
        return existing.user

    email = (email or "").strip()
    match = User.objects.filter(email=email).first() if email else None

    if match is not None:
        if not email_verified:
            raise SocialLoginError(
                "An account with this email already exists. Log in with your "
                "password to link this provider."
            )
        SocialAccount.objects.create(user=match, provider=provider, uid=uid)
        return match

    if not settings.REGISTRATION_OPEN:
        raise SocialLoginError("No account found.")

    user = create_social_account(email=email, name=name)
    SocialAccount.objects.create(user=user, provider=provider, uid=uid)
    return user
