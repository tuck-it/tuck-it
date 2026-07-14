import pytest

from tuckit.web.templatetags.web_extras import icon


def test_search_and_dots_icons_have_paths():
    assert "<path" in icon("search")
    assert "<path" in icon("dots") or "<circle" in icon("dots")


@pytest.mark.django_db
def test_command_palette_rendered_with_area_rows(client_local, workspace):
    from tuckit.core.services.areas import create_area
    create_area(workspace, "Backend")
    body = client_local.get(f"/{workspace.org.slug}/{workspace.slug}/").content.decode()
    assert 'id="command-palette"' in body           # overlay present
    assert 'data-label="Backend"' in body           # area is a command row
    assert 'data-label="Home"' in body               # static nav command
    assert "command_palette.js" in body              # component script loaded
