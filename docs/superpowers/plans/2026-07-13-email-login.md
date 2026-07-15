# Email-as-login-identifier Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make **email** the login identifier (`USERNAME_FIELD = "email"`, unique) with a custom `UserManager`, keep `username` as an optional non-identity field, and update the signup services + the ~21 test files that create users by username.

**Architecture:** One atomic identity change on the existing swapped `core.User` model — you cannot half-apply it (making email unique/USERNAME_FIELD breaks every `User.objects.create(username=…)`), so the model change, service updates, migration, and test sweep land in a single task that leaves the suite green. Login needs no real template change: Django's `AuthenticationForm` names its field `username` but authenticates against `USERNAME_FIELD`, so `{{ form.username }}` now authenticates by email.

**Tech Stack:** Django (custom user model), pytest. Run tests with `uv run pytest`.

## Global Constraints

- `AUTH_USER_MODEL = "core.User"` stays — this is a field/identity change on the existing model, not a new model.
- `email`: `EmailField(unique=True)`, becomes `USERNAME_FIELD`. `username`: kept but `CharField(max_length=150, blank=True, null=True, unique=True)` — optional, not the identity, not set by signup services.
- `REQUIRED_FIELDS = []` (createsuperuser prompts email + password only).
- Signup services (`register`, `register_invited`, `create_account`, `bootstrap`) no longer take or set a username.
- No data backfill — local and prod DBs are being wiped separately, so the migration applies clean.
- Don't change org/workspace/invite semantics, tenant isolation, or activity/actor threading. Leave the existing Korean password-empty message as-is (the English sweep is a separate effort).
- `docs/superpowers/` stays untracked.
- Out of scope: the "user with zero workspaces" empty-state; password reset; email verification.

## File Structure

- **Modify** `tuckit/core/models/accounts.py` — add `UserManager`, rework `User`.
- **Create** migration under `tuckit/core/migrations/`.
- **Modify** `tuckit/core/services/accounts.py` (`register`), `tuckit/core/services/invitations.py` (`register_invited`).
- **Modify** `tuckit/core/management/commands/create_account.py`, `tuckit/core/management/commands/bootstrap.py`.
- **Modify** ~21 test files (enumerated in Task 1 Step 9) + `tests/web/conftest.py`.

---

### Task 1: Email-login refactor (model + manager + migration + services + test sweep)

**Files:** as listed in File Structure above.

**Interfaces:**
- `register(*, email, org_name, slug, password) -> (User, Org, Workspace)` — `username` param removed.
- `register_invited(*, invitation, password) -> (User, OrgMember)` — `username` param removed.
- `ensure_bootstrap(email="local@tuckit.local", org_slug="default") -> (Workspace, str|None)` — `username` param → `email`.
- `User.objects` is a `UserManager` with `create_user(email, password=None, **extra)` / `create_superuser(email, password=None, **extra)`.

- [ ] **Step 1: Write the failing test for the new identity model**

Create `tests/test_email_login.py`:

```python
import pytest
from django.contrib.auth import authenticate
from django.db import IntegrityError

from tuckit.core.models import User


@pytest.mark.django_db
def test_create_user_by_email_and_login():
    u = User.objects.create_user(email="a@b.com", password="pw123456")
    assert u.email == "a@b.com"
    assert u.username is None
    assert authenticate(username="a@b.com", password="pw123456") == u  # authenticates by email


@pytest.mark.django_db
def test_email_is_unique():
    User.objects.create_user(email="dup@b.com", password="pw123456")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@b.com", password="pw123456")


@pytest.mark.django_db
def test_create_superuser_by_email():
    su = User.objects.create_superuser(email="root@b.com", password="pw123456")
    assert su.is_staff and su.is_superuser and su.email == "root@b.com"


@pytest.mark.django_db
def test_username_field_is_email():
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_email_login.py -v`
Expected: FAIL — `create_user(email=…)` errors (default manager wants username), `USERNAME_FIELD` is "username".

- [ ] **Step 3: Rework the User model + add UserManager**

Replace `tuckit/core/models/accounts.py` with:

```python
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UserManager(BaseUserManager):
    """Email is the identifier; username is optional and never used to log in."""

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
    REQUIRED_FIELDS = []

    objects = UserManager()
```

- [ ] **Step 4: Generate the migration**

Run: `uv run python manage.py makemigrations core`
Expected: a new migration (e.g. `0008_alter_user_email_alter_user_username_...`) with `AlterField` on `email` (unique) and `username` (null/blank). No column dropped. Accept the generated name.

- [ ] **Step 5: Update `register`**

Replace the `register` function in `tuckit/core/services/accounts.py` with:

```python
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
```

(The Korean empty-password string is left unchanged — separate sweep.)

- [ ] **Step 6: Update `register_invited`**

Replace the `register_invited` function in `tuckit/core/services/invitations.py` with:

```python
@transaction.atomic
def register_invited(*, invitation, password) -> tuple[User, OrgMember]:
    if User.objects.filter(email=invitation.email).exists():
        raise InvalidValue(f"User already exists: {invitation.email}")
    if not password:
        raise InvalidValue("비밀번호를 입력해 주세요")
    user = User(email=invitation.email)
    try:
        validate_password(password, user)
    except ValidationError as exc:
        raise InvalidValue(" ".join(exc.messages))
    user.set_password(password)
    user.save()
    member = accept_invitation(token=invitation.token, user=user)
    return user, member
```

- [ ] **Step 7: Update the `create_account` command**

In `tuckit/core/management/commands/create_account.py`: remove the `--username` argument (the `parser.add_argument("--username", …)` line) and remove `username=options["username"]` from the `register(...)` call. The success message already prints `user.email` via `user.username`? — change it to print `user.email`:

```python
        self.stdout.write(
            self.style.SUCCESS(f"Created user {user.email} + org {org.slug}")
        )
```

- [ ] **Step 8: Update `bootstrap`**

In `tuckit/core/management/commands/bootstrap.py`, change `ensure_bootstrap` to key the local user by email:

```python
def ensure_bootstrap(email: str = "local@tuckit.local", org_slug: str = "default") -> tuple[Workspace, str | None]:
    user, _ = User.objects.get_or_create(email=email)
    org, _ = Org.objects.get_or_create(slug=org_slug, defaults={"name": "Default"})
    OrgMember.objects.get_or_create(user=user, org=org, defaults={"role": "owner"})
    workspace = org.workspaces.first() or create_workspace(org, "Default", slug="default")

    raw = None
    if not ApiToken.objects.filter(workspace=workspace).exists():
        _, raw = generate_token(workspace, "local-cli")
    return workspace, raw
```

- [ ] **Step 9: Sweep the test files (username → email identity)**

Apply these edits. The dominant pattern is dropping `username="…", ` from `User.objects.create(...)` calls that already pass an identical `email=`:

**Mechanical — `User.objects.create(username="X", email="X")` → `User.objects.create(email="X")`** in:
- `tests/test_services_orgs.py` (lines 15, 45, 55, 56, 57, 153, 164, 172, 179, 197, 205, 219, 222, 231, 232, 241, 251, 252)
- `tests/test_models_org.py` (10, 19)
- `tests/test_migration_backfill.py` (20) — this exercises the historical 0003 backfill migration; the user creation on line 20 uses the *current* `User` import, so the mechanical `create(email=…)` edit applies. If the test fails on historical-schema interplay (e.g. it pins to a migration state before the new AlterField), investigate rather than force it — the 0003 logic itself is untouched.
- `tests/test_entitlements.py` (21)
- `tests/test_services_invitations.py` (13, 31, 42, 52)
- `tests/web/test_settings_account.py` (16, 51, 67, 90, 110)
- `tests/web/test_settings_invites.py` (11, 45, 59, 63)
- `tests/web/test_settings_workspace.py` (17, 58)
- `tests/web/test_workspace_switch.py` (10)
- `tests/web/test_cross_workspace_access.py` (10)
- `tests/web/test_seat_limit.py` (17)
- `tests/web/test_auth_screens.py` (52)
- `tests/web/test_settings_org.py` (17, 19, 99)
- `tests/web/test_invite_accept.py` (11, 30, 42, 54)

**`create_user` with a non-email username → email** (add an email, drop username):
- `tests/test_models.py:27` `User.objects.create_user(username="bob", password="x")` → `User.objects.create_user(email="bob@x.com", password="x")`
- `tests/test_smoke.py:11` `User.objects.create_user(username="alice", password="x")` → `User.objects.create_user(email="alice@x.com", password="x")`

**Local bootstrap user identity → email** (must match `ensure_bootstrap`'s new `local@tuckit.local`):
- `tests/web/conftest.py:15` `User.objects.get(username="local")` → `User.objects.get(email="local@tuckit.local")`
- `tests/test_bootstrap.py:11` `User.objects.filter(username="local").exists()` → `User.objects.filter(email="local@tuckit.local").exists()`
- `tests/web/test_auth.py`:
  - `:17` `User.objects.filter(username="local").exists()` → `filter(email="local@tuckit.local").exists()`
  - `:24` `User.objects.get(username="local")` → `get(email="local@tuckit.local")`
  - `:27` `client.login(username="local", password="pw123456")` → `client.login(username="local@tuckit.local", password="pw123456")` (the `login()` kwarg stays `username=`; the value is the email, looked up by USERNAME_FIELD)

**`register(..., username=…)` calls — drop the username kwarg** in `tests/test_services_accounts.py`:
- `:26` drop `, username="alice"`
- `:35` drop `, username="bob"`
- `:40`–`:42`: this pair tested duplicate-*username* rejection with two different emails. Rework it to test duplicate-*email* rejection — both calls use the SAME email and the second must raise `InvalidValue`:

```python
    register(email="same@b.com", org_name="S", slug="s1", password="pw123456")
    with pytest.raises(InvalidValue):
        register(email="same@b.com", org_name="S2", slug="s2", password="pw123456")
```

(Read the surrounding test to keep its name/decorators; only the two `register(...)` lines and the assertion change.)

**`create_account` command test** `tests/test_create_account_command.py`:
- `:17` `User.objects.get(username="a@b.com")` → `User.objects.get(email="a@b.com")`
- If the test invokes the command with `--username`, remove that arg from the `call_command(...)`; keep `--email a@b.com`.

- [ ] **Step 10: Run the full suite to verify green**

Run: `uv run pytest`
Expected: PASS — the new `tests/test_email_login.py` passes and every swept test passes. Investigate any remaining `username`-related failure (grep the failure for `username` and apply the same transformation).

- [ ] **Step 11: Commit**

```bash
git add tuckit/core/models/accounts.py tuckit/core/migrations/ tuckit/core/services/accounts.py tuckit/core/services/invitations.py tuckit/core/management/commands/create_account.py tuckit/core/management/commands/bootstrap.py tests/
git commit -m "feat(core): email as login identifier (USERNAME_FIELD=email, username optional)"
```

---

### Task 2: Verification

**Files:** none (verification only).

- [ ] **Step 1: Full suite + drift**

Run: `uv run pytest` and `uv run pytest tests/web/test_design_system.py -v`
Expected: all green (design-system test unaffected).

- [ ] **Step 2: `createsuperuser` prompts email**

Run: `uv run python manage.py createsuperuser` and confirm it prompts for **Email** (not Username) and password. (Cancel with Ctrl-C, or create a throwaway and delete it — this is just to confirm the prompt.)

- [ ] **Step 3: Manual login-by-email end to end**

(The local sqlite files were deleted, so create a fresh DB first.)
Run: `uv run python manage.py migrate` then create an account:
`TUCKIT_PW=pw12345678 uv run python manage.py create_account --email me@example.com --workspace Demo --slug demo --password-env TUCKIT_PW`
Start `uv run python manage.py runserver`, open `/login/`, and log in with **me@example.com** + the password → lands on Home. Confirm the login field accepts the email.

- [ ] **Step 4: Confirm no lingering username-identity references**

Run: `grep -rnE "username=" tuckit tests --include="*.py" | grep -vE "/migrations/|login\(username=|env\.py"`
Expected: no user-creation call still passes `username=`. (`client.login(username=<email>…)` and DB-URL `env.py` parsing are fine.)

- [ ] **Step 5: No commit (verification only).**

---

## Notes / out of scope

- The `scratchpad/prod-reset.sh` and any local reset now use **email identity** (`create_account --email …` / login by email); a bare `username` is no longer accepted by `register`. Update those helpers accordingly when next used.
- Zero-workspace empty-state (so a bare `createsuperuser` account is usable *in the app*) — separate follow-up.
- Password reset, email verification, the full Korean→English sweep — separate efforts.
