from django.db import transaction
from django.utils import timezone

from tuckit.core.models import Org, Ticket
from tuckit.core.services.activity import record_activity
from tuckit.core.services.ranking_helpers import rank_for
from tuckit.core.services.slices import allocate_number

_UNSET = object()


def create_ticket(
    org: Org,
    title: str,
    *,
    body: str = "",
    area=None,
    source: str = "human",
    created_by=None,
    before: Ticket | None = None,
    after: Ticket | None = None,
) -> Ticket:
    rank = rank_for(Ticket, {"org": org}, before=before, after=after)
    with transaction.atomic():
        number = allocate_number(org)
        ticket = Ticket.objects.create(
            org=org, area=area, title=title, body=body,
            source=source, created_by=created_by, number=number, rank=rank,
        )
        record_activity(org, actor=source, verb="created", target=ticket)
    return ticket


def query_tickets(
    org: Org, *, status: str = "open", unpromoted_only: bool = True,
    area=None, query: str | None = None, limit: int | None = None,
) -> list[Ticket]:
    """Inbox query. Defaults to open, not-yet-promoted tickets (the raw backlog)."""
    qs = Ticket.objects.filter(org=org)
    if status:
        qs = qs.filter(status=status)
    if unpromoted_only:
        qs = qs.filter(slice__isnull=True)
    if area is not None:
        qs = qs.filter(area=area)
    if query:
        from django.db.models import Q
        qs = qs.filter(Q(title__icontains=query) | Q(body__icontains=query))
    if limit:
        qs = qs[:limit]
    return list(qs)


def update_ticket(
    ticket: Ticket, *, title: str | None = None, body: str | None = None,
    status: str | None = None, area=_UNSET,
    before: Ticket | None = None, after: Ticket | None = None,
    actor: str = "human",
) -> Ticket:
    if title is not None:
        ticket.title = title
    if body is not None:
        ticket.body = body
    if area is not _UNSET:
        ticket.area = area
    if before is not None or after is not None:
        ticket.rank = rank_for(Ticket, {"org": ticket.org}, before=before, after=after)
    if status is not None and status != ticket.status:
        return _apply_status(ticket, status, actor=actor, save_first=True)
    ticket.save()
    return ticket


def close_ticket(ticket: Ticket, *, actor: str = "human") -> Ticket:
    if ticket.status == "closed":
        return ticket
    return _apply_status(ticket, "closed", actor=actor)


def _apply_status(ticket: Ticket, status: str, *, actor: str, save_first: bool = False) -> Ticket:
    old = ticket.status
    ticket.status = status
    ticket.closed_at = timezone.now() if status == "closed" else None
    with transaction.atomic():
        ticket.save()
        if status != old:
            verb = "closed" if status == "closed" else "status_changed"
            record_activity(ticket.org, actor=actor, verb=verb, target=ticket,
                            from_value=old, to_value=status)
    return ticket
