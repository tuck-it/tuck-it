import sys
import pytest


@pytest.fixture
def asgi_app():
    """Provide a fresh ASGI app instance for each test with reloaded modules.

    This ensures the MCP session manager gets a fresh instance for each test,
    avoiding the "can only be called once per instance" error.
    """
    # Remove cached modules to force a fresh import
    modules_to_remove = [key for key in sys.modules if key.startswith("tuckit") or key.startswith("core.mcp")]
    for mod in modules_to_remove:
        del sys.modules[mod]

    # Import fresh
    from tuckit.asgi import app
    yield app

    # Clean up after the test
    modules_to_remove = [key for key in sys.modules if key.startswith("tuckit") or key.startswith("core.mcp")]
    for mod in modules_to_remove:
        del sys.modules[mod]
