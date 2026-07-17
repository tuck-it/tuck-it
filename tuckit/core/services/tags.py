from django.db.models import QuerySet

from tuckit.core.models import Org, Tag, Workspace


def get_or_create_tags(workspace: Workspace, names: list[str]) -> list[Tag]:
    """NOTE: deliberately still workspace-scoped, not org-scoped — see task-5
    report. Tag has a (workspace, name) DB uniqueness constraint (org-scoped
    uniqueness isn't added until Task 12), and an org can hold several
    workspaces that each reuse the same tag name. An org-scoped get_or_create
    lookup could match a *different* workspace's row (wrong tag reused) or,
    on create, omit the still-required workspace= and violate the non-null
    FK. Every call site (slices.py) already has the exact owning workspace
    on hand via `area.workspace`, so there's no need to widen this to org."""
    tags = []
    for name in names:
        tag, _ = Tag.objects.get_or_create(
            workspace=workspace, org=workspace.org, name=name  # TODO(task-12): drop workspace=
        )
        tags.append(tag)
    return tags


def list_tags(org: Org) -> QuerySet:
    return Tag.objects.filter(org=org).order_by("name")
