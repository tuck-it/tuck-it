# Email as login identifier — design

**Date:** 2026-07-13
**Repo:** `tuckit` (public core — ships to self-host AND cloud)
**Status:** design approved, spec for implementation

## Problem

The app authenticates by Django's default `username` field, and the register
service just copies email into it (`username = username or email`,
`accounts.py:12`). So it *looks* like email login but isn't — it's
username-login where the username happens to hold an email. Any account whose
username ≠ email (e.g. a CLI/admin-created one) exposes the seam: you log in
with the username, not the email. The principle is email/password login, and
the custom `User` model was defined "so real auth can extend it later"
(`accounts.py` docstring) — this is that extension.

## Decision

Make **email the login identifier** (`USERNAME_FIELD = "email"`), and **keep the
`username` field** as an optional, non-identifying attribute (retained per the
user's call — no destructive column drop; available for a future handle/display
name). `username` is no longer required, no longer set by the signup services,
and is not the login field.

## Non-goals (out of scope)

- The "user with zero workspaces" empty-state / making bare `createsuperuser`
  usable *in the app* (separate follow-up — this spec only touches auth identity).
- Password reset, email verification.
- No data backfill: local and prod DBs are being wiped as part of this work, so
  the migration is applied clean (no email-uniqueness backfill needed).

## Model change

`tuckit/core/models/accounts.py`:

```python
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    """Email is the identifier; username is optional and not used to log in."""

    use_in_migrations = True

    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra.get("is_staff") is not True or extra.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_staff and is_superuser = True")
        return self._create(email, password, **extra)


class User(AbstractUser):
    """Custom user — login by email; username kept but optional (not identity)."""

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, blank=True, null=True, unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # email is USERNAME_FIELD; createsuperuser prompts email + password only

    objects = UserManager()
```

Notes:
- `username unique=True, null=True` → unique only among set values; multiple NULLs
  are allowed (Postgres & SQLite), so unset usernames don't collide.
- `createsuperuser` now prompts for **email** + password (no username), via the
  custom manager — a side benefit that makes the CLI consistent with email login.

## Services / commands (drop the `username` argument; leave username unset)

- **`register`** (`core/services/accounts.py`): signature becomes
  `register(*, email, org_name, slug, password)`. Uniqueness check on
  `User.objects.filter(email=email)`. Construct `User(email=email)` (no username),
  `validate_password`, `set_password`, save; then `create_org(...)` as today.
- **`register_invited`** (`core/services/invitations.py`): drop `username`;
  `User(email=invitation.email)`.
- **`create_account`** management command: remove the `--username` argument and
  stop passing it to `register`. Success message prints `user.email`.
- **`bootstrap`** management command: create the local dev user by email, e.g.
  `User.objects.get_or_create(email="local@tuckit.local")` (was `username="local"`).
  This is the fixture identity used by `tests/web/conftest.py`.

## Login (minimal template change)

Django's `AuthenticationForm` always names its form field `username` but
authenticates against `UserModel.USERNAME_FIELD`. So `registration/login.html`'s
`{{ form.username }}` keeps working and now authenticates by **email**; the
existing "Email" label is already correct. Only tidy the field's `autocomplete`
to `email`/`username` if desired. `client.login(username=<email>, password=...)`
in tests still works (the kwarg is named `username` but the value is looked up by
`USERNAME_FIELD`).

## Migration

After the model change, `uv run python manage.py makemigrations core` generates
an `AlterField` migration: `email` → `unique=True` (and effectively required as
USERNAME_FIELD), `username` → `null=True, blank=True` (still unique). No column is
dropped. Applied clean on the freshly-wiped local and prod DBs (no backfill).

## Tests (~21 files, mechanical)

Sweep `username=`-based user creation to email-based:
- `User.objects.create(username=X, email=Y)` / `create_user(username=…)` →
  `User.objects.create_user(email=Y, …)` (or `User.objects.create(email=Y)`).
- `tests/web/conftest.py`: `User.objects.get(username="local")` →
  `User.objects.get(email="local@tuckit.local")` (match bootstrap's new identity).
- `client.login(username=<email>, …)` / `force_login(user)` remain valid.
- Add/adjust a focused test asserting login authenticates by email and that a
  user whose username differs from (or is absent) still logs in with their email.
- `test_create_account_command.py`: drop `--username` expectations.

Run the full suite green; the design-system drift test is unaffected.

## Protected / constraints

- Public/private boundary intact (auth is core; no billing copy).
- Don't change org/workspace/invite semantics, tenant isolation, or the
  activity/actor threading.
- `AUTH_USER_MODEL = "core.User"` stays; this is a field/identity change on the
  existing swapped model, not a new model.
- `docs/superpowers/` stays untracked (gitignored).

## Definition of done

- Users log in with **email** + password; `USERNAME_FIELD = "email"`, email unique.
- `username` retained as an optional, non-identity field; signup services don't set it.
- `register` / `register_invited` / `create_account` / `bootstrap` no longer take or
  require a username; `createsuperuser` prompts email.
- Migration applies clean on wiped DBs; full test suite green.
- Login template authenticates by email with the "Email" label.
