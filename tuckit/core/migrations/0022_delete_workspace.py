from django.db import migrations, models
from django.db.models import Count


def _dedup_rename(model, field_name, suffix_fn):
    """For each (org, field_name) group with >1 row, keep the lowest-id row
    unchanged and rename the rest via suffix_fn(base_value, n) until the
    result is unique within the org. Never deletes a row."""
    max_length = getattr(model._meta.get_field(field_name), 'max_length', None)
    dup_groups = list(
        model.objects.values('org_id', field_name)
        .annotate(_n=Count('id'))
        .filter(_n__gt=1)
        .order_by('org_id', field_name)
    )
    for group in dup_groups:
        org_id = group['org_id']
        base_value = group[field_name]
        rows = list(
            model.objects.filter(org_id=org_id, **{field_name: base_value}).order_by('id')
        )
        # Values already in use elsewhere in the org (excluding this exact
        # duplicate group, which is what we're about to rename) -- must not
        # collide with the suffixes we generate below.
        existing = set(
            model.objects.filter(org_id=org_id)
            .exclude(id__in=[r.id for r in rows])
            .values_list(field_name, flat=True)
        )
        existing.add(base_value)  # lowest-id row keeps this value unchanged
        n = 2
        for row in rows[1:]:
            candidate = suffix_fn(base_value, n)
            if max_length:
                candidate = candidate[:max_length]
            while candidate in existing:
                n += 1
                candidate = suffix_fn(base_value, n)
                if max_length:
                    candidate = candidate[:max_length]
            existing.add(candidate)
            setattr(row, field_name, candidate)
            row.save(update_fields=[field_name])
            n += 1


def _dedup_delete(model, group_fields):
    """For each group sharing group_fields with >1 row, keep the lowest-id
    row and delete the rest. Only safe for derived/regenerable data."""
    dup_groups = list(
        model.objects.values(*group_fields)
        .annotate(_n=Count('id'))
        .filter(_n__gt=1)
    )
    for group in dup_groups:
        lookup = {f: group[f] for f in group_fields}
        ids = list(
            model.objects.filter(**lookup).order_by('id').values_list('id', flat=True)
        )
        keep_id = ids[0]
        model.objects.filter(**lookup).exclude(id=keep_id).delete()


def dedup_pre_org_uniqueness(apps, schema_editor):
    """Legacy orgs could have 2+ Workspaces (pre-Task-12), each seeding its
    own Area(slug="triage"), reusing Tag names, and snapshotting the same
    day. With workspace gone and org the sole tenant column, those rows now
    collide under the new (org,slug) / (org,name) / (org,date) uniqueness.
    Deduplicate before the constraints below are added:
      - Area (org, slug): never delete (slices hang off Areas) -- suffix
        the duplicates' slugs instead: "<slug>-2", "<slug>-3", ...
      - Tag (org, name): never delete (may be referenced by slices) --
        suffix the duplicates' names instead: "<name> (2)", "<name> (3)", ...
      - OrgStatSnapshot (org, date): derived data, regenerated on Home
        load -- keep the lowest-id row per (org, date) and delete the rest.
    """
    Area = apps.get_model('core', 'Area')
    Tag = apps.get_model('core', 'Tag')
    OrgStatSnapshot = apps.get_model('core', 'OrgStatSnapshot')

    _dedup_rename(Area, 'slug', lambda base, n: f"{base}-{n}")
    _dedup_rename(Tag, 'name', lambda base, n: f"{base} ({n})")
    _dedup_delete(OrgStatSnapshot, ['org_id', 'date'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_workspace_fk_nullable'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='WorkspaceStatSnapshot',
            new_name='OrgStatSnapshot',
        ),
        # Dedup pass: must run before AlterUniqueTogether(area/tag) and
        # AddConstraint(uniq_org_snapshot_per_day) below -- those are the
        # operations that would raise IntegrityError against real databases
        # where an org ever had 2+ legacy workspaces. `org` has been the
        # backfilled tenant column on these models since 0020, so grouping
        # by it here is valid even though the `workspace` field itself
        # isn't dropped from Area/Tag/OrgStatSnapshot until later in this
        # same migration.
        migrations.RunPython(dedup_pre_org_uniqueness, noop),
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
