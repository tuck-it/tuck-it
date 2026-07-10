import os

# Set required env BEFORE importing the real settings. pytest-django loads this
# module (DJANGO_SETTINGS_MODULE) before any conftest.py, so this is the earliest
# reliable place to inject test env. DEBUG=1 keeps prod security (SSL redirect,
# manifest static storage) off during tests.
os.environ.setdefault("DATABASE_URL", "sqlite://:memory:")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,localhost")
os.environ.setdefault("DJANGO_DEBUG", "1")

from tuckit.settings import *  # noqa: E402,F401,F403
