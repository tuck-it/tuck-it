"""Blank specs that are verbatim copies of their origin ticket's body.

Before 0037, promote_ticket() seeded Slice.spec with Ticket.body, so a non-empty
spec stopped meaning "this slice has been designed" — the signal the workflow
reads to decide whether the next step is brainstorming or planning.

Only EXACT copies are cleared. A spec someone edited afterwards is their work
and is left alone, even though it is not a design doc either; guessing at intent
would destroy more than it fixes.

Non-destructive: ticket bodies are never touched, so anything cleared here is
still readable off the ticket the slice links to.
"""

from django.db import migrations


def clear_copies(apps, schema_editor):
    Slice = apps.get_model("core", "Slice")
    for s in Slice.objects.exclude(spec="").iterator():
        # Origin = the linked ticket that gave this slice its number. Inlined
        # rather than imported from services: migrations are frozen, service
        # code is not.
        origin = s.tickets.filter(number=s.number).first()
        if origin is not None and s.spec == origin.body:
            s.spec = ""
            s.save(update_fields=["spec"])


def noop(apps, schema_editor):
    """Not reversible: which blank specs were once copies is not recoverable.
    Nothing is lost — the bodies were never destroyed."""


class Migration(migrations.Migration):

    dependencies = [("core", "0036_ticket_slice_fk")]

    operations = [migrations.RunPython(clear_copies, noop)]
