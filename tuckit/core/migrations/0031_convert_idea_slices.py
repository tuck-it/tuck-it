from django.db import migrations


def forward(apps, schema_editor):
    """Self-contained backlog conversion using historical models (frozen at this
    migration's state, so `is_triage`/`status='idea'` still exist). idea-Slices
    with a Plan -> 'planned'; idea-Slices without a Plan -> a Ticket reusing the
    slice's number (spec->body, created_at preserved), dropping the slice's
    activity rows; Triage Areas demoted to plain areas ('Triage'->'General').
    Tags on converted idea-Slices are NOT carried over (Ticket has no tags
    field in v1); this drop is intended and one-way.
    One-way; irreversible."""
    Org = apps.get_model("core", "Org")
    Slice = apps.get_model("core", "Slice")
    Area = apps.get_model("core", "Area")
    Ticket = apps.get_model("core", "Ticket")
    Plan = apps.get_model("core", "Plan")
    ActivityEvent = apps.get_model("core", "ActivityEvent")

    for org in Org.objects.all():
        for s in list(Slice.objects.filter(area__org=org, status="idea")):
            if Plan.objects.filter(slice=s).exists():
                s.status = "planned"
                s.save(update_fields=["status", "updated_at"])
                continue
            area = None if s.area.is_triage else s.area
            t = Ticket.objects.create(
                org=org, area=area, title=s.title, body=s.spec,
                status="open", number=s.number, source=s.source, rank=s.rank,
            )
            Ticket.objects.filter(pk=t.pk).update(created_at=s.created_at)
            ActivityEvent.objects.filter(target_type="slice", target_id=s.id).delete()
            s.delete()
        for area in Area.objects.filter(org=org, is_triage=True):
            area.is_triage = False
            if area.name == "Triage":
                area.name = "General"
            area.save(update_fields=["is_triage", "name", "updated_at"])


class Migration(migrations.Migration):
    dependencies = [("core", "0030_ticket")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
