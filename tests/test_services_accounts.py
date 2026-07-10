import pytest

from core.models import Area, Membership, User, Workspace
from core.services.accounts import create_account
from core.services.exceptions import InvalidValue


@pytest.mark.django_db
def test_create_account_creates_full_setup():
    user, ws = create_account(
        email="a@b.com", workspace_name="Space", slug="space", password="pw123456"
    )
    assert user.email == "a@b.com"
    assert user.username == "a@b.com"  # defaults to email
    assert user.check_password("pw123456")
    assert ws.slug == "space"
    assert Membership.objects.filter(user=user, workspace=ws, role="owner").exists()
    assert Area.objects.filter(workspace=ws, is_inbox=True).count() == 1
    assert Area.objects.filter(workspace=ws, is_inbox=False, slug="default").exists()


@pytest.mark.django_db
def test_create_account_explicit_username():
    user, _ = create_account(
        email="a@b.com", workspace_name="S", slug="s", password="pw123456", username="alice"
    )
    assert user.username == "alice"


@pytest.mark.django_db
def test_create_account_duplicate_slug_raises():
    create_account(email="a@b.com", workspace_name="S", slug="dup", password="pw123456")
    with pytest.raises(InvalidValue):
        create_account(email="c@d.com", workspace_name="S2", slug="dup", password="pw123456", username="bob")


@pytest.mark.django_db
def test_create_account_duplicate_username_raises():
    create_account(email="a@b.com", workspace_name="S", slug="s1", password="pw123456", username="same")
    with pytest.raises(InvalidValue):
        create_account(email="c@d.com", workspace_name="S2", slug="s2", password="pw123456", username="same")
