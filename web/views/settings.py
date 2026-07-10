from django.shortcuts import render
from django.http import HttpResponse

from core.services.tokens import list_tokens, generate_token, revoke_token
from web.auth import get_current_workspace


def settings(request):
    ws = get_current_workspace(request)
    return render(request, "web/settings.html", {
        "workspace": ws,
        "tokens": list(list_tokens(ws)),
        "mcp_url": request.build_absolute_uri("/mcp"),
    })


def token_create(request):
    ws = get_current_workspace(request)
    token, raw = generate_token(ws, request.POST.get("name") or "token")
    return render(request, "web/partials/_token_row.html", {"token": token, "raw": raw})


def token_revoke(request, token_id):
    ws = get_current_workspace(request)
    revoke_token(ws, token_id)
    return HttpResponse(status=204)


def workspace_rename(request):
    ws = get_current_workspace(request)
    ws.name = request.POST["name"]
    ws.save(update_fields=["name", "updated_at"])
    return HttpResponse(ws.name)
