import pytest
from django.test import override_settings

from tuckit.core.entitlements import Entitlements
from tuckit.core.models import Org, OrgMember, User
from tuckit.core.services.exceptions import LimitReached
from tuckit.core.services.invitations import create_invitation


def _limit_1(org):
    return Entitlements(seat_limit=1)


def _limit_2(org):
    return Entitlements(seat_limit=2)


@pytest.fixture
def org_owner(db):
    org = Org.objects.create(name="Acme", slug="acme")
    owner = User.objects.create(email="o@a.com")
    OrgMember.objects.create(user=owner, org=org, role="owner")
    return org, owner


@pytest.mark.django_db
def test_no_hook_is_unlimited(org_owner):
    org, owner = org_owner
    # No TUCKIT_ENTITLEMENTS_HOOK set → unlimited; many invites succeed.
    for i in range(5):
        create_invitation(org=org, email=f"x{i}@y.com", role="member", invited_by=owner)


@override_settings(TUCKIT_ENTITLEMENTS_HOOK="tests.test_entitlements._limit_1")
@pytest.mark.django_db
def test_seat_limit_blocks_invite(org_owner):
    org, owner = org_owner  # already 1 member (owner) == limit 1
    with pytest.raises(LimitReached):
        create_invitation(org=org, email="new@x.com", role="member", invited_by=owner)


@override_settings(TUCKIT_ENTITLEMENTS_HOOK="tests.test_entitlements._limit_2")
@pytest.mark.django_db
def test_pending_invitation_counts_toward_limit(org_owner):
    org, owner = org_owner  # 1 member; limit 2
    create_invitation(org=org, email="a@x.com", role="member", invited_by=owner)  # 1 member + 1 pending = 2
    with pytest.raises(LimitReached):
        create_invitation(org=org, email="b@x.com", role="member", invited_by=owner)
