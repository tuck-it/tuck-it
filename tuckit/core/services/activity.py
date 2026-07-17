from tuckit.core.models import ActivityEvent

_TARGET_TYPES = {"Slice": "slice", "Bite": "bite", "Area": "area"}


def _target_workspace(target, target_type: str):
    """ActivityEvent.workspace is still a non-null FK (dropped in Task 12).
    record_activity now takes `org`, not a workspace, but every target object
    still carries an unambiguous real workspace via its own FK chain — use
    that (not an org-wide guess) so per-workspace reads like slice_activity()
    keep matching the rows this writes."""
    if target_type == "area":
        return target.workspace
    if target_type == "slice":
        return target.area.workspace
    return target.plan.slice.area.workspace  # bite


def record_activity(org, *, actor, verb, target, from_value="", to_value=""):
    """Append one immutable activity row. Denormalizes target label so the log
    survives the target being deleted/dropped."""
    label = getattr(target, "title", None) or getattr(target, "name", "")
    try:
        target_type = _TARGET_TYPES[type(target).__name__]
    except KeyError:
        raise ValueError(f"unsupported activity target: {type(target).__name__}") from None
    ActivityEvent.objects.create(
        workspace=_target_workspace(target, target_type),  # TODO(task-12): drop workspace=
        org=org,
        actor=actor,
        verb=verb,
        target_type=target_type,
        target_id=target.id,
        target_label=(label or "")[:300],
        from_value=from_value or "",
        to_value=to_value or "",
    )


def status_verb(to_status: str) -> str:
    """The verb to record for a status change — terminal states get their own."""
    return {"shipped": "shipped", "dropped": "dropped"}.get(to_status, "status_changed")


def slice_activity(slice_):
    """Read-only, chronological activity for one slice — its own events plus its
    bites' events, oldest-first — so the detail reads like a comment thread."""
    from django.db.models import Q

    from tuckit.core.models import ActivityEvent, Bite

    bite_ids = list(Bite.objects.filter(plan__slice=slice_).values_list("id", flat=True))
    return list(
        ActivityEvent.objects.filter(workspace=slice_.area.workspace)
        .filter(Q(target_type="slice", target_id=slice_.id)
                | Q(target_type="bite", target_id__in=bite_ids))
        .order_by("created_at")
    )
