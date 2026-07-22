"""Markdown extension coverage.

These are unit tests on the renderer, not on a view: every markdown surface in
the app (slice spec, ticket body, plan overview/constraints, bite body) funnels
through render_markdown_html, so proving it here proves it everywhere.
"""

from tuckit.web.panel import render_markdown_html


def test_pipe_table_renders_as_a_table():
    html = render_markdown_html("| col | val |\n| --- | --- |\n| a | 1 |\n")
    assert "<table>" in html
    assert "<th>col</th>" in html
    assert "<td>1</td>" in html


def test_table_markup_survives_the_sanitizer():
    """nh3 must not strip the table tags markdown just produced."""
    html = render_markdown_html("| a |\n| --- |\n| 1 |\n")
    for tag in ("<table>", "<thead>", "<tbody>", "<tr>", "<th>", "<td>"):
        assert tag in html, f"{tag} was stripped"


def test_a_dash_list_after_a_numbered_list_stays_its_own_list():
    """Without sane_lists the bullet is swallowed into the <ol> as item 2 —
    a shape agents write constantly in specs."""
    html = render_markdown_html("1. first\n\n- bullet\n")
    assert "<ol>" in html
    assert "<ul>" in html


def test_script_in_a_table_cell_is_still_sanitized():
    html = render_markdown_html("| a |\n| --- |\n| <script>alert(1)</script> |\n")
    assert "<script>" not in html
    assert "<table>" in html
