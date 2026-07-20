import pytest

from tuckit.core.models import Org, Ticket, Slice
from tuckit.core.services.areas import create_area
from tuckit.core.services.refs import ticket_ref
from tuckit.core.services.resolve import get_ticket, get_ticket_by_ref, resolve_ref


@pytest.mark.django_db
def test_ticket_defaults_and_slice_link():
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    t = Ticket.objects.create(org=org, area=area, title="Fix login", rank="m")
    assert t.status == "open"
    assert t.source == "human"
    assert t.body == ""
    assert t.closed_at is None
    assert t.created_by is None
    # area-less (Inbox) ticket is allowed
    inbox = Ticket.objects.create(org=org, area=None, title="Stray idea", rank="m")
    assert inbox.area is None
    # Slice can link back to a Ticket
    s = Slice.objects.create(area=area, title="S", rank="m", number=1, ticket=t)
    assert t.slice == s


@pytest.mark.django_db
def test_ref_and_resolution_prefers_slice():
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    t = Ticket.objects.create(org=org, area=area, title="T", rank="m", number=42)
    assert ticket_ref(t) == "acme-42"
    assert get_ticket(org, t.id) == t
    assert get_ticket_by_ref(org, "acme-42") == t
    # unpromoted -> ref resolves to the Ticket
    assert resolve_ref(org, "acme-42") == t
    # promote: a Slice inherits number 42 -> ref now resolves to the Slice
    s = Slice.objects.create(area=area, title="S", rank="m", number=42, ticket=t)
    assert resolve_ref(org, "acme-42") == s


from tuckit.core.services.tickets import (
    create_ticket, query_tickets, update_ticket, close_ticket,
)


@pytest.mark.django_db
def test_create_ticket_mints_shared_number_and_defaults_to_inbox():
    org = Org.objects.create(name="Acme", slug="acme")
    t1 = create_ticket(org, "First")
    t2 = create_ticket(org, "Second")
    assert (t1.number, t2.number) == (1, 2)          # shared per-org sequence
    assert t1.area is None and t1.status == "open"    # inbox by default
    org.refresh_from_db()
    assert org.next_slice_number == 3


@pytest.mark.django_db
def test_query_tickets_open_inbox_only():
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    open_t = create_ticket(org, "Open")
    closed_t = create_ticket(org, "Closed")
    close_ticket(closed_t)
    # a promoted ticket has a linked slice -> excluded from the raw inbox
    promoted = create_ticket(org, "Promoted")
    Slice.objects.create(area=area, title="S", rank="m", number=promoted.number, ticket=promoted)
    rows = query_tickets(org)
    assert [t.title for t in rows] == ["Open"]


@pytest.mark.django_db
def test_update_and_close_ticket():
    org = Org.objects.create(name="Acme", slug="acme")
    t = create_ticket(org, "T")
    update_ticket(t, title="T2", body="details")
    t.refresh_from_db()
    assert t.title == "T2" and t.body == "details"
    close_ticket(t)
    t.refresh_from_db()
    assert t.status == "closed" and t.closed_at is not None
