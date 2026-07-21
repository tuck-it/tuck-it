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
    assert t.resolved_at is None
    assert t.created_by is None
    # area-less (Inbox) ticket is allowed
    inbox = Ticket.objects.create(org=org, area=None, title="Stray idea", rank="m")
    assert inbox.area is None
    # A Ticket links forward to its Slice
    s = Slice.objects.create(area=area, org=org, title="S", rank="m", number=1)
    t.slice = s
    t.save(update_fields=["slice"])
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
    s = Slice.objects.create(area=area, org=org, title="S", rank="m", number=42)
    t.slice = s
    t.save(update_fields=["slice"])
    assert resolve_ref(org, "acme-42") == s


from tuckit.core.services.tickets import (
    create_ticket, query_tickets, ticket_queryset, update_ticket, resolve_ticket,
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
def test_create_ticket_external_key_is_idempotent():
    org = Org.objects.create(name="Acme", slug="acme")
    first = create_ticket(org, "From TODO", external_key="todo:auth.py:42")
    again = create_ticket(org, "From TODO", external_key="todo:auth.py:42")
    assert again.id == first.id                       # no duplicate on agent retry
    assert Ticket.objects.filter(org=org).count() == 1
    org.refresh_from_db()
    assert org.next_slice_number == 2                 # and no number burned


@pytest.mark.django_db
def test_query_tickets_is_open_only():
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    create_ticket(org, "Open")
    resolve_ticket(create_ticket(org, "Dismissed"), "dismissed")
    promote_ticket(create_ticket(org, "Promoted", area=area))
    # open IS the inbox now — no slice join, no "open but hidden" ghost state
    assert [t.title for t in query_tickets(org)] == ["Open"]
    assert ticket_queryset(org).count() == 1


@pytest.mark.django_db
def test_update_and_dismiss_ticket():
    org = Org.objects.create(name="Acme", slug="acme")
    t = create_ticket(org, "T")
    update_ticket(t, title="T2", body="details")
    t.refresh_from_db()
    assert t.title == "T2" and t.body == "details"
    resolve_ticket(t, "dismissed")
    t.refresh_from_db()
    assert t.status == "dismissed" and t.resolved_at is not None


@pytest.mark.django_db
def test_dismissed_and_promoted_are_distinguishable():
    """The whole point of the split: 'we decided not to' must not look like
    'it shipped'."""
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    dismissed = create_ticket(org, "Nope")
    resolve_ticket(dismissed, "dismissed")
    shipped_t = create_ticket(org, "Yep", area=area)
    set_slice_status(promote_ticket(shipped_t), "shipped")
    dismissed.refresh_from_db()
    shipped_t.refresh_from_db()
    assert dismissed.status == "dismissed"
    assert shipped_t.status == "promoted"


@pytest.mark.django_db
def test_update_ticket_rejects_invalid_status_and_manual_promote():
    org = Org.objects.create(name="Acme", slug="acme")
    t = create_ticket(org, "T")
    with pytest.raises(InvalidValue):
        update_ticket(t, status="nonsense")
    with pytest.raises(InvalidValue):
        update_ticket(t, status="promoted")   # must go through promote_ticket
    t.refresh_from_db()
    assert t.status == "open"


from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.slices import set_slice_status, update_slice
from tuckit.core.services.tickets import promote_ticket


@pytest.mark.django_db
def test_promote_inherits_number_and_ends_ticket_lifecycle():
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    t = create_ticket(org, "Fix login", body="the button is misaligned", area=area)
    s = promote_ticket(t)
    assert s.number == t.number          # same ref across promotion
    assert s.spec == ""                  # the body is linked, not copied
    assert s.status == "planned"
    t.refresh_from_db()
    assert t.slice_id == s.id
    assert t.status == "promoted" and t.resolved_at is not None


@pytest.mark.django_db
def test_promote_is_idempotent():
    """A retried request (agent retry, double-submit) must not mint a second
    slice or leave an orphan behind."""
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    t = create_ticket(org, "Fix login", area=area)
    first = promote_ticket(t)
    again = promote_ticket(t)
    assert again.id == first.id
    assert Slice.objects.filter(area__org=org).count() == 1


@pytest.mark.django_db
def test_promote_rejects_a_resolved_ticket():
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    t = create_ticket(org, "Nope", area=area)
    resolve_ticket(t, "dismissed")
    with pytest.raises(InvalidValue):
        promote_ticket(t)


@pytest.mark.django_db
def test_promote_area_less_ticket_requires_area():
    org = Org.objects.create(name="Acme", slug="acme")
    inbox_t = create_ticket(org, "Stray")   # area=None
    with pytest.raises(InvalidValue):
        promote_ticket(inbox_t)
    area = create_area(org, "Backend")
    s = promote_ticket(inbox_t, area=area)
    assert s.area_id == area.id


@pytest.mark.django_db
def test_promote_rejects_cross_org_area():
    org = Org.objects.create(name="Acme", slug="acme")
    other = Org.objects.create(name="Other", slug="other")
    t = create_ticket(org, "Stray")
    with pytest.raises(InvalidValue):
        promote_ticket(t, area=create_area(other, "Theirs"))


@pytest.mark.django_db
def test_slice_status_never_writes_back_to_the_ticket():
    """The Ticket's lifecycle ends at promotion. Delivery is read off the slice,
    so reopening a shipped slice cannot leave the two disagreeing."""
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    t = create_ticket(org, "Fix login", area=area)
    s = promote_ticket(t)
    resolved_at = Ticket.objects.get(pk=t.pk).resolved_at

    set_slice_status(s, "shipped")
    t.refresh_from_db()
    assert t.status == "promoted" and t.resolved_at == resolved_at
    assert t.slice.status == "shipped"          # delivery is derived, not stored

    set_slice_status(s, "building")             # reopened — used to strand the ticket
    t.refresh_from_db()
    assert t.status == "promoted"
    assert t.slice.status == "building"


from datetime import timedelta
from django.utils import timezone
from tuckit.core.services.state import attention_items


@pytest.mark.django_db
def test_slice_default_status_is_planned():
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    from tuckit.core.services.slices import create_slice
    s = create_slice(area, "S")
    assert s.status == "planned"


@pytest.mark.django_db
def test_attention_flags_stale_open_tickets():
    org = Org.objects.create(name="Acme", slug="acme")
    t = create_ticket(org, "Old idea")
    Ticket.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(days=10))
    reasons = [it["reason"] for it in attention_items(org)]
    assert "ticket_stale" in reasons


@pytest.mark.django_db
def test_editing_a_stale_ticket_does_not_reset_the_timer():
    """Staleness is measured from capture, not last touch — renaming or
    reordering an untriaged ticket is not triage."""
    org = Org.objects.create(name="Acme", slug="acme")
    t = create_ticket(org, "Old idea")
    Ticket.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(days=10))
    update_ticket(t.__class__.objects.get(pk=t.pk), title="Old idea, reworded")
    assert "ticket_stale" in [it["reason"] for it in attention_items(org)]


@pytest.mark.django_db
def test_promoted_ticket_leaves_the_inbox_attention_list():
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    t = create_ticket(org, "Old idea", area=area)
    Ticket.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(days=10))
    promote_ticket(Ticket.objects.get(pk=t.pk))
    assert "ticket_stale" not in [it["reason"] for it in attention_items(org)]


@pytest.mark.django_db
def test_slice_holds_many_tickets():
    """The fold triage actually performs is N:1 — a OneToOne cannot express it."""
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    s = Slice.objects.create(area=area, org=org, title="S", rank="m", number=1)
    t1 = Ticket.objects.create(org=org, area=area, title="T1", rank="m", number=1, slice=s)
    t2 = Ticket.objects.create(org=org, area=area, title="T2", rank="n", number=2, slice=s)
    assert set(s.tickets.values_list("id", flat=True)) == {t1.id, t2.id}
    assert t1.slice == s and t2.slice == s


@pytest.mark.django_db
def test_promote_links_instead_of_copying_the_body():
    """spec is the design-doc slot, and "spec is blank" is how the workflow
    detects that a slice has not been designed yet. Seeding it with the capture
    made every promoted slice look designed."""
    org = Org.objects.create(name="Acme", slug="acme")
    area = create_area(org, "Backend")
    t = create_ticket(org, "Fix login", body="Users get a 500 on submit.", area=area)

    s = promote_ticket(t)
    t.refresh_from_db()

    assert s.spec == ""
    assert t.slice_id == s.id                        # reachable through the link
    assert t.body == "Users get a 500 on submit."    # the one copy, untouched
    assert t.status == "promoted"
