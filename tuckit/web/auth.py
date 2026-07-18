from tuckit.core.models import Org


def get_current_org(request) -> Org | None:
    """The org resolved for THIS request by TenantMiddleware (strict; used for
    access + view logic). None on non-tenant pages (auth/account/root)."""
    return getattr(request, "org", None)


def resolve_fallback_org(request) -> Org | None:
    """Best-effort org for non-tenant pages that still need one: prefers the
    session's active org, else the user's first accessible one. Membership-checked.
    None if the user belongs to no org."""
    if not request.user.is_authenticated:
        return None
    from tuckit.core.models import OrgMember
    from tuckit.core.services.orgs import accessible_orgs

    org_id = request.session.get("active_org_id")
    if org_id:
        org = Org.objects.filter(pk=org_id).first()
        if org and OrgMember.objects.filter(user=request.user, org=org).exists():
            return org
    return accessible_orgs(request.user).first()


def landing_route(request) -> tuple[str, dict]:
    """Single source of truth for where a logged-in user should land, based on
    account state: their org's Home, or the org picker if they have none.
    Returns (url_name, reverse_kwargs).

    Leaf pages (root, orgs) MUST consult this instead of redirecting to one another
    on inferred state — that is what previously produced a root-level redirect loop.
    Centralizing the decision here makes cycles structurally impossible.
    """
    org = resolve_fallback_org(request)
    if org is None:
        return ("web:orgs", {})
    return ("web:home", {"org_slug": org.slug})


def current_org_or_fallback(request) -> Org | None:
    """Strict tenant org if the URL resolved one (get_current_org); otherwise the
    same best-effort fallback as resolve_fallback_org. Sidebar chrome (Areas list,
    badge counts, switcher) should read this, not get_current_org alone — a
    non-tenant route leaves request.org None, and get_current_org alone would make
    every one of those go silently blank instead of showing the same org the
    switcher itself falls back to."""
    return get_current_org(request) or resolve_fallback_org(request)
