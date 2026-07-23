from django.http import HttpResponse, JsonResponse

from tuckit.core.services.activity import events_since, latest_activity_id


def live(request):
    """Poll target: cheap org-scoped activity cursor. 204 when nothing is newer
    than `since`; otherwise the new events + the advanced cursor. request.org is
    set by TenantMiddleware (membership already enforced)."""
    org = request.org
    try:
        since = int(request.GET.get("since", 0))
    except (TypeError, ValueError):
        since = 0
    latest = latest_activity_id(org)
    if latest <= since:
        return HttpResponse(status=204)
    events = [
        {
            "id": e.id,
            "actor": e.actor,
            "verb": e.verb,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "target_label": e.target_label,
        }
        for e in events_since(org, since)
    ]
    return JsonResponse({"cursor": latest, "events": events})
