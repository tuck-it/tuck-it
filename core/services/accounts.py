from django.db import transaction

from core.models import Membership, User, Workspace
from core.services.areas import create_area, get_or_create_inbox
from core.services.exceptions import InvalidValue


@transaction.atomic
def create_account(*, email, workspace_name, slug, password, username=None):
    username = username or email
    if User.objects.filter(username=username).exists():
        raise InvalidValue(f"User already exists: {username}")
    if Workspace.objects.filter(slug=slug).exists():
        raise InvalidValue(f"Workspace slug already taken: {slug}")

    user = User(username=username, email=email)
    user.set_password(password)
    user.save()

    workspace = Workspace.objects.create(name=workspace_name, slug=slug)
    Membership.objects.create(user=user, workspace=workspace, role="owner")
    get_or_create_inbox(workspace)
    create_area(workspace, "Default")
    return user, workspace
