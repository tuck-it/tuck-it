from django.db.models import QuerySet
from django.utils.text import slugify

from tuckit.core.models import Area, Workspace
from tuckit.core.services.ranking_helpers import rank_for

TRIAGE_NAME = "Triage"


def list_areas(workspace: Workspace, include_archived: bool = False) -> QuerySet:
    qs = Area.objects.filter(workspace=workspace)
    if not include_archived:
        qs = qs.filter(archived=False)
    return qs


def _unique_slug(workspace: Workspace, name: str) -> str:
    base = slugify(name) or "area"
    slug = base
    i = 2
    while Area.objects.filter(workspace=workspace, slug=slug).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


def create_area(workspace: Workspace, name: str, description: str = "", slug: str | None = None) -> Area:
    slug = slug or _unique_slug(workspace, name)
    rank = rank_for(Area, {"workspace": workspace})
    return Area.objects.create(
        workspace=workspace, name=name, description=description, slug=slug, rank=rank
    )


def get_or_create_triage(workspace: Workspace) -> Area:
    triage = Area.objects.filter(workspace=workspace, is_triage=True).first()
    if triage is not None:
        return triage
    first = Area.objects.filter(workspace=workspace).order_by("rank").first()
    rank = rank_for(Area, {"workspace": workspace}, before=first)
    return Area.objects.create(
        workspace=workspace,
        name=TRIAGE_NAME,
        slug=_unique_slug(workspace, TRIAGE_NAME),
        is_triage=True,
        rank=rank,
    )
