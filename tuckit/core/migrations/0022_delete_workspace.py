from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_workspace_fk_nullable'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='WorkspaceStatSnapshot',
            new_name='OrgStatSnapshot',
        ),
        migrations.RemoveConstraint(
            model_name='orgstatsnapshot',
            name='uniq_ws_snapshot_per_day',
        ),
        migrations.AddConstraint(
            model_name='orgstatsnapshot',
            constraint=models.UniqueConstraint(fields=('org', 'date'), name='uniq_org_snapshot_per_day'),
        ),
        # AlterUniqueTogether must precede the RemoveField for the same model:
        # the old ("workspace", ...) unique_together has to stop referencing
        # the field before the field itself is dropped, or the SQLite table
        # rebuild in RemoveField fails looking up a field that no longer
        # exists in the target state.
        migrations.AlterUniqueTogether(
            name='area',
            unique_together={('org', 'slug')},
        ),
        migrations.AlterUniqueTogether(
            name='tag',
            unique_together={('org', 'name')},
        ),
        migrations.RemoveField(
            model_name='area',
            name='workspace',
        ),
        migrations.RemoveField(
            model_name='tag',
            name='workspace',
        ),
        migrations.RemoveField(
            model_name='apitoken',
            name='workspace',
        ),
        migrations.RemoveIndex(
            model_name='activityevent',
            name='core_activi_workspa_ac91de_idx',
        ),
        migrations.RemoveField(
            model_name='activityevent',
            name='workspace',
        ),
        migrations.RemoveField(
            model_name='orgstatsnapshot',
            name='workspace',
        ),
        migrations.DeleteModel(
            name='Workspace',
        ),
    ]
