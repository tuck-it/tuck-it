import pytest
from django.test import RequestFactory
from tuckit.web.templatetags.web_extras import slice_push_url


def _ctx(path):
    return {"request": RequestFactory().get(path)}


def test_slice_push_url_appends_param_to_current_path():
    assert slice_push_url(_ctx("/acme/main/home"), 42) == "/acme/main/home?slice=42"


def test_slice_push_url_preserves_other_query_and_replaces_slice():
    out = slice_push_url(_ctx("/acme/main/board?view=board&slice=9"), 42)
    assert out == "/acme/main/board?view=board&slice=42"


def test_slice_push_url_drops_panel_param():
    assert slice_push_url(_ctx("/acme/main/home?panel=1"), 7) == "/acme/main/home?slice=7"
