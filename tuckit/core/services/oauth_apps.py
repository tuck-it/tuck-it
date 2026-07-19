from tuckit.core.models import OAuthAccessToken


def list_connected_apps(org) -> list[dict]:
    """One row per client that currently holds an access token in this org."""
    seen: dict[str, dict] = {}
    qs = (
        OAuthAccessToken.objects.filter(org=org)
        .select_related("client").order_by("-last_used_at", "-created_at")
    )
    for tok in qs:
        cid = tok.client.client_id
        if cid not in seen:
            seen[cid] = {
                "client_id": cid,
                "name": tok.client.name or cid,
                "last_used_at": tok.last_used_at,
            }
    return list(seen.values())


def disconnect_app(org, client_id: str) -> int:
    """Revoke every access token (and, by cascade, its refresh token) this client
    holds in the org. Returns the number of access tokens removed."""
    qs = OAuthAccessToken.objects.filter(org=org, client__client_id=client_id)
    count = qs.count()
    qs.delete()
    return count
