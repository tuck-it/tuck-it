import pytest
from django.core.exceptions import ImproperlyConfigured

from tuckit.env import env, env_bool, env_list, parse_database_url


def test_env_required_missing_raises(monkeypatch):
    monkeypatch.delenv("SOME_MISSING_KEY", raising=False)
    with pytest.raises(ImproperlyConfigured):
        env("SOME_MISSING_KEY", required=True)


def test_env_returns_default():
    assert env("SOME_MISSING_KEY", default="x") == "x"


def test_env_bool_truthy(monkeypatch):
    monkeypatch.setenv("FLAG", "TRUE")
    assert env_bool("FLAG") is True
    monkeypatch.setenv("FLAG", "0")
    assert env_bool("FLAG") is False
    monkeypatch.delenv("FLAG")
    assert env_bool("FLAG", default=True) is True


def test_env_list_splits_and_trims(monkeypatch):
    monkeypatch.setenv("HOSTS", "a.com, b.com ,, c.com")
    assert env_list("HOSTS") == ["a.com", "b.com", "c.com"]
    monkeypatch.delenv("HOSTS")
    assert env_list("HOSTS", default=["x"]) == ["x"]


def test_parse_postgres_url():
    cfg = parse_database_url("postgres://u:p%40ss@db.host:5432/mydb?sslmode=require")
    assert cfg["ENGINE"] == "django.db.backends.postgresql"
    assert cfg["NAME"] == "mydb"
    assert cfg["USER"] == "u"
    assert cfg["PASSWORD"] == "p@ss"  # URL-decoded
    assert cfg["HOST"] == "db.host"
    assert cfg["PORT"] == "5432"
    assert cfg["OPTIONS"] == {"sslmode": "require"}


def test_parse_sqlite_memory():
    cfg = parse_database_url("sqlite://:memory:")
    assert cfg["ENGINE"] == "django.db.backends.sqlite3"
    assert cfg["NAME"] == ":memory:"


def test_parse_sqlite_relative():
    cfg = parse_database_url("sqlite:///db.sqlite3")
    assert cfg["ENGINE"] == "django.db.backends.sqlite3"
    assert cfg["NAME"] == "db.sqlite3"


def test_parse_sqlite_absolute():
    cfg = parse_database_url("sqlite:////app/data/db.sqlite3")
    assert cfg["ENGINE"] == "django.db.backends.sqlite3"
    assert cfg["NAME"] == "/app/data/db.sqlite3"


def test_parse_empty_raises():
    with pytest.raises(ImproperlyConfigured):
        parse_database_url("")


def test_parse_unsupported_scheme_raises():
    with pytest.raises(ImproperlyConfigured):
        parse_database_url("mysql://u:p@h/db")
