from django.conf import settings
from django.contrib.auth import login
from django.http import Http404
from django.shortcuts import redirect, render

from core.services.accounts import register
from core.services.exceptions import InvalidValue


def register_view(request):
    if not settings.REGISTRATION_OPEN:
        raise Http404
    if request.method == "POST":
        try:
            user, _org, _ws = register(
                email=request.POST.get("email", ""),
                org_name=request.POST.get("org_name", ""),
                slug=request.POST.get("slug", ""),
                password=request.POST.get("password", ""),
            )
        except InvalidValue as exc:
            return render(request, "registration/register.html", {"error": str(exc), "values": request.POST})
        login(request, user)
        return redirect("web:home")
    return render(request, "registration/register.html", {"values": {}})
