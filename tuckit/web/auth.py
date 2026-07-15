from tuckit.core.models import Workspace


def get_current_workspace(request) -> Workspace | None:
    """The workspace resolved for THIS request by TenantMiddleware (strict; used for
    access + view logic). None on non-tenant pages (auth/account/root)."""
    return getattr(request, "workspace", None)


def resolve_fallback_workspace(request) -> Workspace | None:
    """Best-effort workspace for non-tenant pages (e.g. first_org) that still need
    one: prefers the session's active workspace, else the user's first accessible
    one. Membership-checked. None if the user has no accessible workspace."""
    if not request.user.is_authenticated:
        return None
    from tuckit.core.models import OrgMember
    from tuckit.core.services.orgs import accessible_workspaces

    ws_id = request.session.get("active_workspace_id")
    if ws_id:
        ws = Workspace.objects.filter(pk=ws_id).select_related("org").first()
        if ws and OrgMember.objects.filter(user=request.user, org=ws.org).exists():
            return ws
    return accessible_workspaces(request.user).select_related("org").first()


def landing_route(request) -> tuple[str, dict]:
    """Single source of truth for where a logged-in user should land, based on
    account state: their workspace's Home, or the create-first-org page if they
    have none. Returns (url_name, reverse_kwargs).

    Leaf pages (root, first_org) MUST consult this instead of redirecting to one
    another on inferred state — that is what previously produced a root-level
    redirect loop. Centralizing the decision here makes cycles structurally
    impossible.
    """
    ws = resolve_fallback_workspace(request)
    if ws is None:
        return ("web:first_org", {})
    return ("web:home", {"org_slug": ws.org.slug, "ws_slug": ws.slug})


def current_workspace_or_fallback(request) -> Workspace | None:
    """Strict tenant workspace if the URL resolved one (get_current_workspace);
    otherwise the same best-effort fallback as resolve_fallback_workspace. Sidebar
    chrome (Areas list, badge counts, switcher) should read this, not
    get_current_workspace alone — a non-tenant route like settings/<org_slug>/
    (no ws_slug in the URL) leaves request.workspace None, and get_current_workspace
    alone would make every one of those go silently blank instead of showing the
    same workspace the switcher itself falls back to."""
    return get_current_workspace(request) or resolve_fallback_workspace(request)
