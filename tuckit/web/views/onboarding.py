from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from tuckit.core.models import Area, Slice
from tuckit.core.services.areas import create_area
from tuckit.core.services.bites import create_bite
from tuckit.core.services.slices import create_slice
from tuckit.web.auth import get_current_workspace


def _home(ws):
    return redirect("web:home", org_slug=ws.org.slug, ws_slug=ws.slug)


@require_POST
def create_first_area(request):
    ws = get_current_workspace(request)
    if ws is None:
        return redirect("web:root")
    name = (request.POST.get("name") or "").strip()
    if name:
        create_area(ws, name)
    return _home(ws)


@require_POST
def create_first_slice(request):
    ws = get_current_workspace(request)
    if ws is None:
        return redirect("web:root")
    area = Area.objects.filter(workspace=ws, is_triage=False).order_by("-id").first()
    title = (request.POST.get("title") or "").strip()
    if area and title:
        create_slice(area, title, status="idea", source="human")
    return _home(ws)


@require_POST
def create_first_bite(request):
    ws = get_current_workspace(request)
    if ws is None:
        return redirect("web:root")
    slice_ = Slice.objects.filter(area__workspace=ws).order_by("-id").first()
    title = (request.POST.get("title") or "").strip()
    if slice_ and title:
        create_bite(slice_, title, source="human")
    return _home(ws)
