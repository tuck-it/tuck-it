"""Smoke tests for the core Django admin registrations.

These guard the local-dev admin: every core model should be registered and its
changelist should render for a superuser. Catches registration mistakes (e.g. a
list_display field that doesn't exist, or a broken custom User admin).
"""

import pytest
from django.contrib import admin
from django.urls import reverse

from tuckit.core.models import (
    ActivityEvent,
    ApiToken,
    Area,
    Bite,
    Invitation,
    Org,
    OrgMember,
    OrgStatSnapshot,
    Slice,
    Tag,
    User,
)

CORE_MODELS = [
    User,
    Org,
    OrgMember,
    Invitation,
    ApiToken,
    OrgStatSnapshot,
    Tag,
    Area,
    Slice,
    Bite,
    ActivityEvent,
]


@pytest.fixture
def admin_client(client, db):
    superuser = User.objects.create_superuser(email="admin@tuckit.local", password="pw")
    client.force_login(superuser)
    return client


@pytest.mark.parametrize("model", CORE_MODELS, ids=lambda m: m.__name__)
def test_core_model_registered(model):
    assert model in admin.site._registry, f"{model.__name__} is not registered in the admin"


@pytest.mark.parametrize("model", CORE_MODELS, ids=lambda m: m.__name__)
def test_admin_changelist_renders(admin_client, model):
    url = reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")
    resp = admin_client.get(url)
    assert resp.status_code == 200


def test_admin_index_renders(admin_client):
    resp = admin_client.get(reverse("admin:index"))
    assert resp.status_code == 200
