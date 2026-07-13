from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from tuckit.core.models import Org, User, Workspace
from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.orgs import create_org


@transaction.atomic
def register(*, email, org_name, slug, password) -> tuple[User, Org, Workspace]:
    if User.objects.filter(email=email).exists():
        raise InvalidValue(f"User already exists: {email}")
    if Org.objects.filter(slug=slug).exists():
        raise InvalidValue(f"Org slug already taken: {slug}")

    if not password:
        raise InvalidValue("비밀번호를 입력해 주세요")
    user = User(email=email)
    try:
        validate_password(password, user)
    except ValidationError as exc:
        raise InvalidValue(" ".join(exc.messages))
    user.set_password(password)
    user.save()

    org, workspace = create_org(user, name=org_name, slug=slug)
    return user, org, workspace
