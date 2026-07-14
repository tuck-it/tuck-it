from tuckit.web.templatetags.web_extras import spec_summary


def test_empty_spec_returns_blank():
    assert spec_summary("") == ""
    assert spec_summary(None) == ""


def test_plain_first_line():
    assert spec_summary("결제 도입 플로우\n\n본문...") == "결제 도입 플로우"


def test_strips_markdown_heading():
    assert spec_summary("# 결제 도입\n내용") == "결제 도입"


def test_skips_yaml_frontmatter():
    spec = "---\nname: billing\n---\n# 결제 도입\n본문"
    assert spec_summary(spec) == "결제 도입"


def test_skips_blank_and_hr_lines():
    assert spec_summary("\n\n---\n\n실제 첫 줄") == "실제 첫 줄"


def test_strips_list_and_quote_markers():
    assert spec_summary("> 인용 첫 줄") == "인용 첫 줄"
    assert spec_summary("* 리스트 첫 줄") == "리스트 첫 줄"


def test_strips_wrapping_emphasis():
    assert spec_summary("*강조된 첫 줄*") == "강조된 첫 줄"


def test_truncates_to_limit():
    out = spec_summary("가" * 200, limit=10)
    assert out == "가" * 10 + "…"
