from tuckit.web.templatetags.web_extras import attention_label


def test_ticket_stale_label():
    assert attention_label({"reason": "ticket_stale", "days": 11}) == "Inbox 11d"


def test_building_stalled_label_unchanged():
    assert attention_label({"reason": "building_stalled", "days": 5}) == "5d idle"


def test_unknown_reason_falls_back_to_generic_label():
    assert attention_label({"reason": "something_else", "days": 3}) == "3d idle"
