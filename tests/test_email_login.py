import pytest
from django.contrib.auth import authenticate
from django.db import IntegrityError

from tuckit.core.models import User


@pytest.mark.django_db
def test_create_user_by_email_and_login():
    u = User.objects.create_user(email="a@b.com", password="pw123456")
    assert u.email == "a@b.com"
    assert u.username is None
    assert authenticate(username="a@b.com", password="pw123456") == u  # authenticates by email


@pytest.mark.django_db
def test_email_is_unique():
    User.objects.create_user(email="dup@b.com", password="pw123456")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="dup@b.com", password="pw123456")


@pytest.mark.django_db
def test_create_superuser_by_email():
    su = User.objects.create_superuser(email="root@b.com", password="pw123456")
    assert su.is_staff and su.is_superuser and su.email == "root@b.com"


@pytest.mark.django_db
def test_username_field_is_email():
    assert User.USERNAME_FIELD == "email"
    assert User.REQUIRED_FIELDS == []
