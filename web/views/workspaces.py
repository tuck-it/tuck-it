from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from core.models import Workspace
from core.services.orgs import create_workspace, is_org_admin, user_can_access_workspace
from web.auth import get_current_workspace


@login_required
def switch_workspace(request):
    ws = Workspace.objects.filter(pk=request.POST.get("workspace_id")).select_related("org").first()
    if ws is None or not user_can_access_workspace(request.user, ws):
        return HttpResponseForbidden("이 워크스페이스에 접근할 수 없습니다")
    request.session["active_workspace_id"] = ws.id
    return redirect("web:home")


@login_required
def workspace_create(request):
    current = get_current_workspace(request)
    if current is None or not is_org_admin(request.user, current.org):
        return HttpResponseForbidden("권한이 없습니다")
    ws = create_workspace(current.org, request.POST.get("name") or "Workspace")
    request.session["active_workspace_id"] = ws.id
    return redirect("web:home")
