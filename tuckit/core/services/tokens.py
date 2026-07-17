import hashlib
import secrets

from django.utils import timezone

from tuckit.core.models import ApiToken, Org, Workspace


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_token(workspace: Workspace, name: str) -> tuple[ApiToken, str]:
    """NOTE: kept workspace-scoped, not migrated to org — every call site
    (web/views/settings.py, web/views/onboarding.py) already has the exact
    Workspace on hand, and ApiToken.workspace is still the non-null legacy FK
    (dropped in Task 12), so there's no ambiguity to resolve here."""
    raw = secrets.token_urlsafe(32)
    token = ApiToken.objects.create(
        workspace=workspace, org=workspace.org, name=name, token_hash=hash_token(raw)  # TODO(task-12): drop workspace=
    )
    return token, raw


def list_tokens(workspace: Workspace):
    return ApiToken.objects.filter(workspace=workspace).order_by("-created_at")


def revoke_token(workspace: Workspace, token_id: int) -> None:
    ApiToken.objects.filter(workspace=workspace, pk=token_id).delete()


def resolve_org(raw: str) -> Org | None:
    """Authoritative bearer-token -> tenant resolution for the MCP wire
    protocol. Returns the Org (not the Workspace) now that Org is the tenant
    boundary the tools operate against."""
    try:
        token = ApiToken.objects.select_related("org").get(token_hash=hash_token(raw))
    except ApiToken.DoesNotExist:
        return None
    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    return token.org
