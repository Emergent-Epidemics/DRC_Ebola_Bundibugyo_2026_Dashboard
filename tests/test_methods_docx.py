"""The Contributors dialog must never ship an internal error message.

load_methods_html() used to catch a missing python-docx and return
"<p style='color:#c66'>python-docx not installed; ...</p>", which went
straight into the payload and rendered inside the public Contributors, Data
and Methods dialog. A missing library is a broken build environment, not
content, so it now stops the build instead.
"""

import importlib
import sys

import pytest

ds = importlib.import_module("common.data_sources")


def test_missing_document_returns_empty_not_an_error_message(tmp_path, capsys):
    absent = tmp_path / "nope.docx"
    assert ds.load_methods_html(absent) == ""
    # Silent absence is how the empty dialog went unnoticed; warn at least.
    assert "WARNING" in capsys.readouterr().out


def test_missing_python_docx_fails_the_build(monkeypatch, tmp_path):
    present = tmp_path / "Contributors_Methods_Data_website.docx"
    present.write_bytes(b"not really a docx, never parsed")
    # Make `from docx import ...` raise ImportError the way an uninstalled
    # dependency would.
    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(RuntimeError) as excinfo:
        ds.load_methods_html(present)
    message = str(excinfo.value)
    assert "python-docx" in message
    assert "requirements.txt" in message


def test_real_document_renders_without_any_error_text():
    if not ds.METHODS_DOCX.exists():
        pytest.skip(f"{ds.METHODS_DOCX.name} not in this checkout")
    pytest.importorskip("docx", reason="python-docx not installed")
    html = ds.load_methods_html()
    assert len(html) > 200, "expected a rendered document, not a stub"
    # The exact failure this module exists to prevent, asserted on the output
    # that actually reaches the payload.
    assert "python-docx" not in html
    assert "#c66" not in html
