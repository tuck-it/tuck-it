import pytest
from django.db import IntegrityError

from tuckit.core.models import ApiToken, Org, OrgMember, User


@pytest.mark.django_db
def test_membership_is_unique_per_user_org():
    user = User.objects.create_user(email="bob@x.com", password="x")
    org = Org.objects.create(name="O", slug="o")
    OrgMember.objects.create(user=user, org=org, role="owner")
    with pytest.raises(IntegrityError):
        OrgMember.objects.create(user=user, org=org, role="member")


@pytest.mark.django_db
def test_api_token_hash_unique():
    org = Org.objects.create(name="Acme", slug="acme")
    ApiToken.objects.create(org=org, name="t1", token_hash="abc")
    with pytest.raises(IntegrityError):
        ApiToken.objects.create(org=org, name="t2", token_hash="abc")
