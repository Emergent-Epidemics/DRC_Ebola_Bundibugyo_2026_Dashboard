"""The methods document must not repeat the dialog's own title.

The modal already renders "Contributors, Data, and Methods" in its header, so
a source document that opens with the same title shows it twice. This mirrors
_TERMS_HEADER_SKIP_RE, which drops the equivalent line from the terms source.

The bar is deliberately narrow: only a LEADING heading whose text IS the
title. "Contributors" on its own is the document's first section, a peer of
"Data" and "Methods", and must survive.
"""

import importlib

ds = importlib.import_module("common.data_sources")

drop = ds._drop_repeated_title


def test_drops_leading_english_title():
    html = "<h2>Contributors, Data, and Methods</h2>\n<p>Body.</p>"
    assert drop(html) == "<p>Body.</p>"


def test_drops_leading_french_title():
    html = "<h2>Contributeurs, données et méthodes</h2>\n\n<h3>Direction</h3>"
    assert drop(html) == "<h3>Direction</h3>"


def test_tolerates_title_variants():
    for title in (
        "Contributors, Data and Methods",      # no Oxford comma
        "Contributors, Data, and Methods:",    # trailing punctuation
        "CONTRIBUTORS, DATA, AND METHODS",     # case
        "Contributors, Data &amp; Methods",    # ampersand, escaped
    ):
        assert drop(f"<h2>{title}</h2><p>Body.</p>") == "<p>Body.</p>", title


def test_keeps_the_contributors_section_heading():
    # The real English document opens with this. It is a section, not a title.
    html = "<h2>Contributors</h2>\n<p>This work is led by...</p>"
    assert drop(html) == html


def test_keeps_other_leading_headings():
    html = "<h3>Data sources</h3><p>Body.</p>"
    assert drop(html) == html


def test_only_strips_at_the_top():
    # A mid-document heading with the same text is the author's, not a repeat
    # of the dialog header.
    html = "<p>Intro.</p><h2>Contributors, Data, and Methods</h2><p>Body.</p>"
    assert drop(html) == html


def test_french_fallback_html_is_deduped(monkeypatch, tmp_path):
    fr = tmp_path / "methods_fr.html"
    fr.write_text(
        "<h2>Contributeurs, données et méthodes</h2>\n<h3>Direction du projet</h3>",
        encoding="utf-8",
    )
    monkeypatch.setattr(ds, "METHODS_DOCX_FR", tmp_path / "absent.docx")
    monkeypatch.setattr(ds, "METHODS_HTML_FR", fr)
    out = ds.load_methods_html_lang("fr")
    assert out.startswith("<h3>Direction du projet</h3>")
    assert "Contributeurs, données et méthodes" not in out
