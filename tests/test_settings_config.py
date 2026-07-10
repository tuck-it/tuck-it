from django.conf import settings


def test_whitenoise_middleware_present():
    assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE
    # must sit immediately after SecurityMiddleware
    sec = settings.MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
    wn = settings.MIDDLEWARE.index("whitenoise.middleware.WhiteNoiseMiddleware")
    assert wn == sec + 1


def test_static_root_configured():
    assert str(settings.STATIC_ROOT).endswith("staticfiles")


def test_staticfiles_storage_debug_gated():
    # Tests run under DEBUG=True (test shim), which must use plain storage so
    # {% static %} needs no collectstatic manifest. Production (DEBUG=False)
    # uses WhiteNoise compressed-manifest storage (verified at deploy time).
    assert settings.DEBUG is True
    assert (
        settings.STORAGES["staticfiles"]["BACKEND"]
        == "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


def test_database_engine_is_sqlite_in_tests():
    # Confirms DATABASE_URL was consumed and produced a sqlite engine in the test
    # env. Do NOT assert NAME == ":memory:" — Django's sqlite test-DB setup mutates
    # settings.DATABASES["default"]["NAME"] in place to a shared-cache URI once any
    # @pytest.mark.django_db test runs, so the value is collection-order-dependent.
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    # In-memory check that survives Django's mutation of NAME (":memory:" early,
    # "file:memorydb_default?mode=memory&cache=shared" after test-DB setup).
    assert "memory" in settings.DATABASES["default"]["NAME"]
