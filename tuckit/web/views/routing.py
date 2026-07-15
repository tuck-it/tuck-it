from django.http import JsonResponse

from tuckit.core.models import Org, OrgMember, Workspace
from tuckit.core.services.exceptions import InvalidValue
from tuckit.core.services.slugs import normalize_slug, validate_slug


def check_slug(request):
    kind = request.GET.get("kind", "org")
    if kind not in ("org", "workspace"):
        return JsonResponse({"available": False, "error": "알 수 없는 종류"})
    try:
        slug = validate_slug(request.GET.get("slug", ""), kind=kind)
    except InvalidValue as exc:
        return JsonResponse({"available": False, "error": str(exc)})
    if kind == "org":
        taken = Org.objects.filter(slug=slug).exists()
    else:
        org = Org.objects.filter(slug=normalize_slug(request.GET.get("org", ""))).first()
        if (
            org is None
            or not request.user.is_authenticated
            or not OrgMember.objects.filter(user=request.user, org=org).exists()
        ):
            return JsonResponse({"available": False, "error": "조직을 찾을 수 없습니다"})
        taken = Workspace.objects.filter(org=org, slug=slug).exists()
    if taken:
        return JsonResponse({"available": False, "error": "이미 사용 중입니다"})
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
