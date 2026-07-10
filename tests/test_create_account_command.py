import pytest
from django.core.management import CommandError, call_command

from core.models import User, Workspace


@pytest.mark.django_db
def test_command_creates_account_from_password_env(monkeypatch):
    monkeypatch.setenv("SEED_PW", "secret123")
    call_command(
        "create_account",
        email="a@b.com",
        workspace="Space",
        slug="space",
        password_env="SEED_PW",
    )
    user = User.objects.get(username="a@b.com")
    assert user.check_password("secret123")
    assert Workspace.objects.filter(slug="space").exists()


@pytest.mark.django_db
def test_command_errors_when_password_env_missing(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    with pytest.raises(CommandError):
        call_command(
            "create_account",
            email="a@b.com",
            workspace="Space",
            slug="space",
            password_env="NOPE",
        )
