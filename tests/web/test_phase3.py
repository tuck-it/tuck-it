import pytest


@pytest.mark.django_db
def test_triage_heading_has_count_and_capture(client_local, workspace):
    from tuckit.core.services.areas import get_or_create_triage
    from tuckit.core.services.slices import create_slice
    create_slice(get_or_create_triage(workspace), "loose end")
    body = client_local.get("/triage/").content.decode()
    assert 'class="page-head"' in body
    assert 'class="page-count"' in body
    assert "cap = true" in body                     # capture action in heading


@pytest.mark.django_db
def test_triage_row_shows_provenance_and_english_controls(client_local, workspace):
    from tuckit.core.services.areas import get_or_create_triage
    from tuckit.core.services.slices import create_slice
    create_slice(get_or_create_triage(workspace), "loose end")
    body = client_local.get("/triage/").content.decode()
    assert 'class="triage-controls"' in body        # controls grouped for reveal
    assert "Assign area" in body
    assert ">Status" in body
    assert "— Area 지정 —" not in body
