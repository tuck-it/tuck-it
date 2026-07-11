from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string

from tuckit.core.services.exceptions import LimitReached


@dataclass(frozen=True)
class Entitlements:
    seat_limit: int | None = None  # None = unlimited


_UNLIMITED = Entitlements()


def resolve_entitlements(org) -> Entitlements:
    """Return the org's limits. No hook configured (self-host) → everything unlimited."""
    path = getattr(settings, "TUCKIT_ENTITLEMENTS_HOOK", None)
    if not path:
        return _UNLIMITED
    return import_string(path)(org)


def assert_can_add_seat(org) -> None:
    ent = resolve_entitlements(org)
    if ent.seat_limit is None:
        return
    # Lazy imports avoid an import cycle (invitations -> entitlements -> orgs/models).
    from tuckit.core.models import Invitation
    from tuckit.core.services.orgs import seat_count

    pending = Invitation.objects.filter(org=org, accepted_at__isnull=True).count()
    if seat_count(org) + pending >= ent.seat_limit:
        raise LimitReached(f"seat limit reached ({ent.seat_limit})")
