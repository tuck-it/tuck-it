"""DB-level guarantees for Ticket, split out of 0033.

Separate from the data conversion on purpose: Postgres cannot CREATE INDEX on a
table that still has pending trigger events from row updates earlier in the same
transaction, and 0033 rewrites every ticket's status. Running these in their own
migration (= own transaction) means 0033 has committed first.

`choices` never reaches the database, so the check constraint is what actually
stops a raw write from storing a bogus status.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0033_ticket_lifecycle")]

    operations = [
        migrations.AddConstraint(
            model_name="ticket",
            constraint=models.UniqueConstraint(
                condition=models.Q(("number__isnull", False)),
                fields=("org", "number"),
                name="uniq_ticket_number_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="ticket",
            constraint=models.UniqueConstraint(
                condition=models.Q(("external_key", ""), _negated=True),
                fields=("org", "external_key"),
                name="uniq_ticket_external_key_per_org",
            ),
        ),
        migrations.AddConstraint(
            model_name="ticket",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("resolved_at__isnull", True), ("status", "open"))
                    | models.Q(
                        ("resolved_at__isnull", False),
                        ("status__in", ("promoted", "dismissed", "duplicate")),
                    )
                ),
                name="ticket_resolved_at_matches_status",
            ),
        ),
        migrations.AddIndex(
            model_name="ticket",
            index=models.Index(
                fields=["org", "status", "rank"], name="ticket_inbox_order_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="ticket",
            index=models.Index(
                fields=["org", "status", "created_at"], name="ticket_stale_idx"
            ),
        ),
    ]
