from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_alter_workspace_org_delete_membership"),
    ]

    operations = [
        migrations.RenameField(
            model_name="area",
            old_name="is_inbox",
            new_name="is_triage",
        ),
    ]
