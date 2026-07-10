import pytest
from django.db import IntegrityError

from core.models import ApiToken, Membership, User, Workspace


@pytest.mark.django_db
def test_workspace_defaults():
    ws = Workspace.objects.create(name="MyProduct", slug="myproduct")
    assert ws.description == ""
    assert ws.created_at is not None


@pytest.mark.django_db
def test_workspace_slug_unique():
    Workspace.objects.create(name="A", slug="dup")
    with pytest.raises(IntegrityError):
        Workspace.objects.create(name="B", slug="dup")


@pytest.mark.django_db
def test_membership_is_unique_per_user_workspace():
    ws = Workspace.objects.create(name="A", slug="a")
    user = User.objects.create_user(username="bob", password="x")
    Membership.objects.create(user=user, workspace=ws, role="owner")
    with pytest.raises(IntegrityError):
        Membership.objects.create(user=user, workspace=ws, role="member")


@pytest.mark.django_db
def test_api_token_hash_unique():
    ws = Workspace.objects.create(name="A", slug="a")
    ApiToken.objects.create(workspace=ws, name="t1", token_hash="abc")
    with pytest.raises(IntegrityError):
        ApiToken.objects.create(workspace=ws, name="t2", token_hash="abc")
