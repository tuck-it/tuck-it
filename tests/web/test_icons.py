from tuckit.web.templatetags.web_extras import _ICON_PATHS


def test_sun_and_moon_icons_registered():
    assert "sun" in _ICON_PATHS
    assert "moon" in _ICON_PATHS


def test_activity_icon_differs_from_in_progress():
    # both were near-identical waveforms; they must be visually distinct
    assert _ICON_PATHS["activity"] != _ICON_PATHS["in-progress"]
