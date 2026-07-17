from django.http import Http404

from tuckit.core.models import Org, OrgMember


class TenantMiddleware:
    """Resolves the <org> URL kwarg into request.org, enforces membership (404 on
    non-member — never reveal existence), and strips the slug kwarg so content views
    keep their original signatures."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        org_slug = view_kwargs.pop("org_slug", None)
        request.org = None
        if org_slug is None:
            return None
        # LoginRequiredMiddleware runs earlier, so anonymous users never reach here
        # for tenant views; guard defensively anyway.
        if not request.user.is_authenticated:
            raise Http404
        org = Org.objects.filter(slug=org_slug).first()
        if org is None or not OrgMember.objects.filter(user=request.user, org=org).exists():
            raise Http404
        request.org = org
        request.session["active_org_id"] = org.id
        return None
