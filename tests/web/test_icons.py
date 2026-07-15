from tuckit.web.templatetags.web_extras import _ICON_PATHS


def test_sun_and_moon_icons_registered():
    assert "sun" in _ICON_PATHS
    assert "moon" in _ICON_PATHS
