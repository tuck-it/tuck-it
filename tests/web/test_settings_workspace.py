import pytest


@pytest.mark.django_db
def test_workspace_page_renders(client_local, workspace):
    from tuckit.core.services.tokens import generate_token
    generate_token(workspace, "Existing")
    resp = client_local.get("/settings/workspace")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert workspace.name in body        # rename field
    assert "Existing" in body            # token listed
    assert "/mcp" in body                # agent snippet
    assert "/settings/org" in body       # member-management link to org page


@pytest.mark.django_db
def test_old_settings_redirects_to_workspace(client_local, workspace):
    resp = client_local.get("/settings/")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/settings/workspace"
