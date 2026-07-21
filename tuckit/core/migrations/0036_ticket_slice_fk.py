"""Reverse Slice.ticket (OneToOne) into Ticket.slice (FK).

Triage folds several captures into one piece of work — three tickets describing
facets of the same problem become one slice. A OneToOne cannot say that, so the
fold was being recorded by hand: paste the bodies into the parent's spec and
close the originals as 'duplicate', which misdescribes a merge as a coincidence.

The AlterField first is not cosmetic. Slice.ticket declares related_name="slice",
which occupies the `slice` attribute on Ticket; adding a real field with that
name while the reverse accessor exists is a system-check error (fields.E302).
Dropping the accessor is state-only — related_name emits no SQL.
"""

from django.db import migrations, models
from django.db.models import Count
import django.db.models.deletion


def forward(apps, schema_editor):
    Slice = apps.get_model("core", "Slice")
    Ticket = apps.get_model("core", "Ticket")
    for s in Slice.objects.exclude(ticket=None).only("id", "ticket_id").iterator():
        Ticket.objects.filter(pk=s.ticket_id).update(slice=s.pk)


def backward(apps, schema_editor):
    """Reversible only while no slice owns more than one ticket — the OneToOne
    has nowhere to put the extras. Fail loudly rather than dropping links."""
    Ticket = apps.get_model("core", "Ticket")
    Slice = apps.get_model("core", "Slice")
    crowded = (
        Ticket.objects.exclude(slice=None)
        .values("slice_id")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )
    if crowded.exists():
        raise RuntimeError(
            "cannot reverse 0036: some slices own multiple tickets, which the "
            "OneToOne cannot represent. Release the extra tickets first."
        )
    for t in Ticket.objects.exclude(slice=None).only("id", "slice_id").iterator():
        Slice.objects.filter(pk=t.slice_id).update(ticket=t.pk)


class Migration(migrations.Migration):

    dependencies = [("core", "0035_slice_org")]

    operations = [
        migrations.AlterField(
            model_name="slice",
            name="ticket",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="core.ticket",
            ),
        ),
        migrations.AddField(
            model_name="ticket",
            name="slice",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tickets",
                to="core.slice",
            ),
        ),
        migrations.RunPython(forward, backward),
        migrations.RemoveField(model_name="slice", name="ticket"),
    ]
