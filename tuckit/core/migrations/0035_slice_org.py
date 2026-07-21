"""Denormalize org onto Slice so per-org number uniqueness is expressible.

Slice reached org only through area, and Django's UniqueConstraint cannot
traverse relations — so the guarantee the ref readers actually rely on (unique
per ORG, since get_slice_by_ref filters area__org) could not be enforced in the
DB at all. Ticket has had uniq_ticket_number_per_org since 0034; this closes the
gap on the other side of the shared number space.

The column is safe to denormalize because set_slice_area() refuses cross-org
moves, so a slice's org never changes after creation.
"""

from django.db import migrations, models
from django.db.models import OuterRef, Subquery
import django.db.models.deletion


def backfill_org(apps, schema_editor):
    Slice = apps.get_model("core", "Slice")
    Area = apps.get_model("core", "Area")
    Slice.objects.update(
        org=Subquery(Area.objects.filter(id=OuterRef("area_id")).values("org_id")[:1])
    )


def noop(apps, schema_editor):
    """Reverse needs no data work: the reversed AddField drops the column."""


class Migration(migrations.Migration):

    dependencies = [("core", "0034_ticket_constraints")]

    operations = [
        # Nullable first so existing rows survive the ADD COLUMN, then backfill,
        # then tighten. Doing it in one non-null step would need a default that
        # would be wrong for every row.
        migrations.AddField(
            model_name="slice",
            name="org",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="slices",
                to="core.org",
            ),
        ),
        migrations.RunPython(backfill_org, noop),
        migrations.AlterField(
            model_name="slice",
            name="org",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="slices",
                to="core.org",
            ),
        ),
        # Last: fails loudly if the data already violates it, which is the point.
        migrations.AddConstraint(
            model_name="slice",
            constraint=models.UniqueConstraint(
                condition=models.Q(("number__isnull", False)),
                fields=("org", "number"),
                name="uniq_slice_number_per_org",
            ),
        ),
    ]
