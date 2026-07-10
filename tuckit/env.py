import os
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured


def env(key, default=None, required=False):
    value = os.environ.get(key, default)
    if required and (value is None or value == ""):
        raise ImproperlyConfigured(f"Missing required environment variable: {key}")
    return value


def env_bool(key, default=False):
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def env_list(key, default=None):
    raw = os.environ.get(key)
    if not raw:
        return list(default) if default is not None else []
    return [item.strip() for item in raw.split(",") if item.strip()]


def parse_database_url(url):
    if not url:
        raise ImproperlyConfigured("DATABASE_URL is required")

    parsed = urlparse(url)
    scheme = parsed.scheme

    if scheme == "sqlite":
        remainder = url[len("sqlite://"):]
        if remainder in (":memory:", ""):
            name = ":memory:"
        elif remainder.startswith("//"):
            name = "/" + remainder.lstrip("/")  # absolute
        else:
            name = remainder.lstrip("/")  # relative
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": name,
        }

    if scheme in ("postgres", "postgresql"):
        options = {}
        query = parse_qs(parsed.query)
        if "sslmode" in query:
            options["sslmode"] = query["sslmode"][0]
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": parsed.path.lstrip("/"),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
            "OPTIONS": options,
        }

    raise ImproperlyConfigured(f"Unsupported DATABASE_URL scheme: {scheme!r}")
