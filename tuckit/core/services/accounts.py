from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from tuckit.core.models import Org, User
from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.orgs import create_org
from tuckit.core.services.slugs import validate_slug


def create_account(*, email: str, password: str) -> User:
    """Create a user account only (no org). Raises InvalidValue on duplicate
    email, empty password, or a password that fails Django's validators."""
    email = (email or "").strip()
    if not email:
        raise InvalidValue("Please enter your email.")
    if User.objects.filter(email=email).exists():
        raise InvalidValue(f"A user with this email already exists: {email}")
    if not password:
        raise InvalidValue("Please enter a password.")
    user = User(email=email)
    try:
        validate_password(password, user)
    except ValidationError as exc:
        raise InvalidValue(" ".join(exc.messages))
    user.set_password(password)
    user.save()
    return user


@transaction.atomic
def register(*, email, org_name, slug, password) -> tuple[User, Org]:
    """Account + first org in one call (used by the CLI create_account command)."""
    slug = validate_slug(slug)  # raises on bad/reserved format
    if Org.objects.filter(slug=slug).exists():
        raise InvalidValue(f"That organization URL is already taken: {slug}")
    user = create_account(email=email, password=password)
    org = create_org(user, name=org_name, slug=slug)
    return user, org
