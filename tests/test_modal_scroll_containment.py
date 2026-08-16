"""A modal must scroll its own body, not slide the whole dialog off screen.

The bug this guards against: .modal is a fixed overlay with overflow-y:auto,
so if the sheet inside it has no height bound, the OVERLAY becomes the scroll
container and scrolling drags the entire dialog -- title, close button and all
-- up out of the viewport. The fix is structural (a bounded sheet with an
inner scrolling body), so a modal added later without the wrappers would
silently reproduce the original bug.
"""

import importlib
import re

chrome = importlib.import_module("common.chrome")
CSS_PATH = importlib.import_module("common.paths").SCRIPT_DIR / "assets" / "dashboard.css"

TEMPLATE = chrome.BODY_TEMPLATE
CSS = CSS_PATH.read_text(encoding="utf-8")


def _count(pattern, text):
    return len(re.findall(pattern, text))


def test_every_sheet_splits_into_head_and_body():
    sheets = _count(r'class="sheet"', TEMPLATE)
    assert sheets >= 2, "expected the methods and terms modals in the template"
    assert _count(r'class="sheet-head"', TEMPLATE) == sheets
    assert _count(r'class="sheet-body"', TEMPLATE) == sheets


def test_close_button_and_title_live_in_the_head():
    # If either drops into .sheet-body it scrolls away with the content, which
    # on a long document leaves no visible way to close the dialog.
    for head in re.findall(r'class="sheet-head".*?</div>', TEMPLATE, re.S):
        assert 'class="close"' in head
        assert "<h2" in head


def test_sheet_is_bounded_and_its_body_is_the_scroller():
    sheet_rule = re.search(r"\.modal \.sheet \{(.*?)\}", CSS, re.S)
    assert sheet_rule, ".modal .sheet rule not found"
    body = sheet_rule.group(1)
    # box-sizing matters: .sheet carries 28px of vertical padding, so under the
    # default content-box a max-height:100% cap still overflows the overlay by
    # exactly that padding and leaves the overlay scrollable.
    assert "box-sizing:border-box" in body.replace(" ", "")
    assert "max-height:100%" in body.replace(" ", "")

    body_rule = re.search(r"\.modal \.sheet-body \{(.*?)\}", CSS, re.S)
    assert body_rule, ".modal .sheet-body rule not found"
    decls = body_rule.group(1).replace(" ", "")
    assert "overflow-y:auto" in decls
    # Without min-height:0 a flex item refuses to shrink below its content,
    # so the body never becomes a scroll container.
    assert "min-height:0" in decls
