from django.http import JsonResponse

from tuckit.core.models import Org
from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.slugs import validate_slug


def check_slug(request):
    try:
        slug = validate_slug(request.GET.get("slug", ""))
    except InvalidValue as exc:
        return JsonResponse({"available": False, "error": str(exc)})
    taken = Org.objects.filter(slug=slug).exists()
    if taken:
        return JsonResponse({"available": False, "error": "Already taken."})
    return JsonResponse({"available": True, "error": None})


from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from tuckit.web.auth import landing_route


@login_required
def root_redirect(request):
    # The single landing decision lives in landing_route(); this view just obeys
    # it. No per-view redirect logic → no redirect cycle.
    name, kwargs = landing_route(request)
    return redirect(name, **kwargs)
