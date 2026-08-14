"""Static guards for the unified health-zone search component.

The search is one DOM node (common/chrome.py) shared by every view, positioned
by dashboard.css per body.view-* and driven by ZONE_SEARCH_VIEWS in engine.js.
Nothing at runtime checks that those three stay in agreement, so these tests do.

See docs/superpowers/specs/2026-08-14-unified-zone-search-design.md.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CHROME = REPO / "Scripts" / "common" / "chrome.py"
ENGINE = REPO / "Scripts" / "assets" / "engine.js"
CSS = REPO / "Scripts" / "assets" / "dashboard.css"

# Views that render a real map + search. Kept as a literal rather than imported
# so a mistake in chrome.NAV_ITEMS cannot make this test agree with itself.
NON_STUB_VIEWS = ["map", "trends", "epi-trends", "context", "genomic-epidemiology"]

# Search boxes replaced by the single component. None may come back.
RETIRED_IDS = [
    "zone-search-wrap",
    "trends-search-input",
    "trends-search-wrap",
    "trends-search-slot",
    "epi-search-input",
    "epi-search-wrap",
]


def _chrome():
    return CHROME.read_text(encoding="utf-8")


def _engine():
    return ENGINE.read_text(encoding="utf-8")


def _css():
    """dashboard.css with comments stripped.

    A commented-out rule must not satisfy (or trip) any of these guards --
    that is a silent false pass in exactly the drift they exist to catch.
    """
    return re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL)


def test_exactly_one_search_input():
    assert _chrome().count('id="zone-search-input"') == 1


def test_no_retired_search_markup():
    text = _chrome()
    present = [i for i in RETIRED_IDS if i in text]
    assert not present, f"retired search markup still in chrome.py: {present}"


def test_controls_panel_holds_no_search_input():
    """#zone-search must not have been left inside the LAYER panel."""
    text = _chrome()
    start = text.index('<div id="controls"')
    end = text.index('<div id="legend"', start)
    assert 'type="search"' not in text[start:end]


def test_zone_search_is_a_sibling_of_map():
    """Not nested in #controls or any rail -- one node, positioned by CSS."""
    text = _chrome()
    map_at = text.index('<div id="map"></div>')
    search_at = text.index('<div id="zone-search">')
    controls_at = text.index('<div id="controls"')
    assert map_at < search_at < controls_at
