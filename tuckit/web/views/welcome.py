from django.shortcuts import render
from django.views.decorators.http import require_POST

from tuckit.core.services.tokens import generate_token
from tuckit.web.auth import get_current_workspace


def welcome(request):
    ws = get_current_workspace(request)
    return render(request, "web/welcome.html", {
        "mcp_url": request.build_absolute_uri("/mcp"),
        "workspace": ws,
        "raw_token": None,
    })


@require_POST
def welcome_generate_key(request):
    ws = get_current_workspace(request)
    _token, raw = generate_token(ws, "Agent (onboarding)")
    return render(request, "web/partials/_welcome_key.html", {
        "mcp_url": request.build_absolute_uri("/mcp"),
        "raw_token": raw,
    })
