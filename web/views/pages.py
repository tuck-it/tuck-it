from django.shortcuts import render

from core.services.state import home_state
from web.auth import get_current_workspace


def home(request):
    ws = get_current_workspace(request)
    state = home_state(ws) if ws else {}
    return render(request, "web/home.html", {"workspace": ws, "state": state})
