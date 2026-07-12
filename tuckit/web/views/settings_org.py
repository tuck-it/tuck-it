from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from tuckit.core.models import OrgMember
from tuckit.core.services.orgs import is_org_admin, is_org_owner, list_org_members
from tuckit.web.auth import get_current_workspace


def org_settings(request):
    ws = get_current_workspace(request)
    org = ws.org if ws else None
    members = list(list_org_members(org)) if org else []
    workspaces = list(org.workspaces.order_by("name")) if org else []
    return render(request, "web/settings_org.html", {
        "workspace": ws,
        "org": org,
        "members": members,
        "workspaces": workspaces,
        "can_admin": bool(org and is_org_admin(request.user, org)),
        "can_owner": bool(org and is_org_owner(request.user, org)),
        "role_choices": OrgMember.ROLE_CHOICES,
    })


# The org page (above) links/posts to these four endpoints, but their real
# behavior is scoped to later tasks (org rename, member role/remove, org
# delete) in the management-surfaces plan. Routing them to a stub here keeps
# `{% url %}` resolvable in settings_org.html / _member_row.html so this
# task's GET page renders; the bodies are placeholders for those tasks to
# replace, not final behavior.
@require_POST
def org_rename(request):
    return HttpResponse(status=501)


@require_POST
def member_role(request, member_id):
    return HttpResponse(status=501)


@require_POST
def member_remove(request, member_id):
    return HttpResponse(status=501)


@require_POST
def org_delete(request):
    return HttpResponse(status=501)
