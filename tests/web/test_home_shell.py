import pytest


@pytest.mark.django_db
def test_sidebar_uses_tuckit_wordmark(client_local, workspace):
    body = client_local.get("/").content.decode()
    assert ">tuckit<" in body
    assert ">tuck-it<" not in body


@pytest.mark.django_db
def test_page_head_present_with_title(client_local, workspace):
    body = client_local.get("/").content.decode()
    assert 'class="page-head"' in body
    assert 'class="page-title"' in body
