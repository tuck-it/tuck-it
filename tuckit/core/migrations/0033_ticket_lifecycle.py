"""Ticket lifecycle: open/closed -> open/promoted/dismissed/duplicate.

A Ticket's status now answers only "are we doing this?" and stops moving once
that is answered. It no longer tracks delivery — that is read off the linked
Slice — so the old auto-close-on-ship sync (and the drift it caused when a
shipped slice reopened) is gone.

The old `closed` conflated two different outcomes; this splits them by looking
at whether a Slice was ever linked:
    closed + linked slice -> promoted    (it shipped/dropped as a Slice)
    closed + no slice     -> dismissed   (decided against at triage)
    open   + linked slice -> promoted    (in flight; used to be an invisible
                                          "open but filtered out of the Inbox")
    open   + no slice     -> open        (still the Inbox)
"""

from django.db import migrations, models


def forward(apps, schema_editor):
    Ticket = apps.get_model("core", "Ticket")
    Slice = apps.get_model("core", "Slice")
    Org = apps.get_model("core", "Org")

    _dedupe_numbers(Ticket, Org)
    _dedupe_external_keys(Ticket)

    promoted_ids = set(
        Slice.objects.filter(ticket__isnull=False).values_list("ticket_id", flat=True)
    )
    for t in Ticket.objects.all().iterator():
        if t.id in promoted_ids:
            status = "promoted"
        elif t.status == "closed":
            status = "dismissed"
        else:
            status = "open"
        # ticket_resolved_at_matches_status is added right after this runs, so
        # every row must satisfy it: resolved rows need a timestamp, open rows
        # must have none. closed_at was renamed to resolved_at above and is the
        # best available time; updated_at is the fallback when it was never set.
        resolved_at = None
        if status != "open":
            resolved_at = t.resolved_at or t.updated_at
        Ticket.objects.filter(pk=t.pk).update(status=status, resolved_at=resolved_at)


def backward(apps, schema_editor):
    Ticket = apps.get_model("core", "Ticket")
    # promoted used to be represented as "open with a linked slice".
    Ticket.objects.filter(status="promoted").update(status="open", resolved_at=None)
    Ticket.objects.filter(status__in=["dismissed", "duplicate"]).update(status="closed")


def _dedupe_numbers(Ticket, Org):
    """uniq_ticket_number_per_org is about to be enforced. Service code mints
    numbers under a row lock, but admin/import/raw-ORM paths never did — hand any
    collision a fresh number so the constraint can be added without failing the
    deploy. Ticket/Slice number sharing is intended and untouched; only
    ticket-vs-ticket duplicates are repaired."""
    for org in Org.objects.all().iterator():
        seen = set()
        for t in Ticket.objects.filter(org=org).order_by("id").iterator():
            if t.number is None:
                continue
            if t.number not in seen:
                seen.add(t.number)
                continue
            fresh = org.next_slice_number
            org.next_slice_number = fresh + 1
            org.save(update_fields=["next_slice_number"])
            Ticket.objects.filter(pk=t.pk).update(number=fresh)
            seen.add(fresh)


def _dedupe_external_keys(Ticket):
    """Same idea for uniq_ticket_external_key_per_org: keep the earliest ticket
    for a key and blank the later ones (the key is a de-dup hint, not data)."""
    seen = set()
    for t in Ticket.objects.exclude(external_key="").order_by("id").iterator():
        pair = (t.org_id, t.external_key)
        if pair in seen:
            Ticket.objects.filter(pk=t.pk).update(external_key="")
        else:
            seen.add(pair)


class Migration(migrations.Migration):
    dependencies = [("core", "0032_drop_idea_and_is_triage")]

    operations = [
        migrations.RenameField(
            model_name="ticket", old_name="closed_at", new_name="resolved_at",
        ),
        migrations.AlterField(
            model_name="ticket",
            name="status",
            field=models.CharField(
                choices=[
                    ("open", "Open"),
                    ("promoted", "Promoted"),
                    ("dismissed", "Dismissed"),
                    ("duplicate", "Duplicate"),
                ],
                default="open",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="activityevent",
            name="verb",
            field=models.CharField(
                choices=[
                    ("created", "created"),
                    ("status_changed", "status changed"),
                    ("moved", "moved"),
                    ("shipped", "shipped"),
                    ("dropped", "dropped"),
                    ("planned", "planned"),
                    ("noted", "noted"),
                    ("promoted", "promoted"),
                    ("dismissed", "dismissed"),
                    ("triaged", "triaged"),
                    ("closed", "closed"),
                ],
                max_length=20,
            ),
        ),
        # Constraints and indexes land in 0034, NOT here: Postgres refuses to
        # build an index on a table with pending trigger events from row updates
        # made earlier in the same transaction ("cannot CREATE INDEX ... because
        # it has pending trigger events"). A separate migration = a separate
        # transaction, so the conversion below has committed by then.
        migrations.RunPython(forward, backward),
    ]
