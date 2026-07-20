import pytest

from tuckit.core.models import Org, Ticket, Slice
from tuckit.core.services.areas import create_area


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
