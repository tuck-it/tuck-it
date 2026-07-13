from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from tuckit.core.services.state import (
    home_state,
    attention_items,
    roadmap_state,
    roadmap_board_groups,
    in_progress_state,
    recent_activity,
)
from tuckit.core.services.onboarding import onboarding_state
from tuckit.web.auth import get_current_workspace


def home(request):
    ws = get_current_workspace(request)
    ob = onboarding_state(ws) if ws else None
    show_get_started = bool(ws and not ws.onboarding_dismissed and ob and not ob.done)
    return render(request, "web/home.html", {
        "workspace": ws,
        "state": home_state(ws) if ws else {},
        "in_progress": in_progress_state(ws) if ws else {"slices": [], "bites": []},
        "roadmap": roadmap_state(ws) if ws else {},
        "recent_activity": recent_activity(ws) if ws else [],
        "onboarding": ob,
        "show_get_started": show_get_started,
    })


def attention(request):
    ws = get_current_workspace(request)
    return render(request, "web/attention.html", {
        "items": attention_items(ws) if ws else [],
    })


def in_progress(request):
    ws = get_current_workspace(request)
    return render(request, "web/in_progress.html", {
        "state": in_progress_state(ws) if ws else {"slices": [], "bites": []},
    })


def roadmap(request):
    ws = get_current_workspace(request)
    view = "list" if request.GET.get("view") == "list" else "board"
    state = roadmap_state(ws) if ws else {}
    return render(request, "web/roadmap.html", {
        "state": state,
        "groups": roadmap_board_groups(ws) if ws else [],
        "view": view,
        "has_any_slice": any(state.values()) if state else False,
        # Board tab spans every area, so surface each slice's area on its card/row.
        "show_area": True,
        "board_scope": "workspace",
    })


def activity(request):
    ws = get_current_workspace(request)
    events = recent_activity(ws, limit=100) if ws else []
    is_panel = request.GET.get("panel") == "1" and request.headers.get("HX-Request")
    template = "web/partials/_activity_panel.html" if is_panel else "web/activity.html"
    return render(request, template, {"events": events})


@require_POST
def dismiss_onboarding(request):
    ws = get_current_workspace(request)
    if ws is None:
        return redirect("web:root")
    ws.onboarding_dismissed = True
    ws.save(update_fields=["onboarding_dismissed"])
    return redirect("web:home", org_slug=ws.org.slug, ws_slug=ws.slug)
