from django.shortcuts import redirect

from tuckit.core.services.orgs import is_org_admin, is_org_owner


def _ws_in_org(request, org):
    """A workspace belonging to `org` for the settings nav / redirects — the app's
    tenant is org-only now (TenantMiddleware no longer resolves a workspace), so
    this just picks a deterministic one: the org's first workspace."""
    if org is None:
        return None
    return org.workspaces.order_by("name").first()


def settings_context(request, *, active):
    """Shared context for the settings shell nav. request.org is set by
    TenantMiddleware; the Workspace group targets a workspace *in this org*."""
    org = request.org
    return {
        "nav_org": org,
        "nav_ws": _ws_in_org(request, org),
        "settings_active": active,
        "can_admin": is_org_admin(request.user, org) if org else False,
        "can_owner": is_org_owner(request.user, org) if org else False,
    }


def settings_root(request):
    ws = _ws_in_org(request, request.org)
    if ws is None:  # org with zero workspaces (shouldn't happen — create_org makes one)
        return redirect("web:settings_org_general", org_slug=request.org.slug)
    return redirect("web:settings_ws_general", org_slug=request.org.slug, ws_slug=ws.slug)


def settings_account_root(request):
    return redirect("web:settings_account_profile", org_slug=request.org.slug)
