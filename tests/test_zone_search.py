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
    "trends-search-results",
    "trends-search-wrap",
    "trends-search-slot",
    "epi-search-input",
    "epi-search-results",
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


def test_retired_css_vocabulary_is_gone():
    """.location-search-* was the light rail vocabulary; it is now the
    component's own styling and the class names go away. .zone-search-option
    is NOT in this list -- it is retained as the new option class."""
    css, engine = _css(), _engine()
    for selector in (".location-search-wrap", ".location-search-results"):
        assert selector not in css, f"{selector} still styled in dashboard.css"
        assert selector not in engine, f"{selector} still referenced in engine.js"


def test_component_has_a_visually_hidden_utility():
    assert ".visually-hidden" in _css()


# --- CSS structure helpers -------------------------------------------------
# The repo has no CSS parser dependency and this stylesheet nests at most one
# level (@media > rule), so brace-balance walks are enough.

def _media_blocks(css):
    """[(query, body)] for every @media block."""
    blocks = []
    for m in re.finditer(r"(@media[^{]*)\{", css):
        depth, i = 1, m.end()
        while depth and i < len(css):
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
            i += 1
        blocks.append((m.group(1).strip(), css[m.end():i - 1]))
    return blocks


def _band_c(css):
    """The narrow branch. There is more than one max-width:700px block in the
    file, so concatenate them all."""
    return "\n".join(
        body for query, body in _media_blocks(css)
        if query == "@media (max-width: 700px)"
    )


def _rules(text):
    """[(selector, body)] for every flat rule. @media headers do not match --
    their bodies contain braces, which the body pattern forbids."""
    return [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", text)]


def _rules_for(text, target):
    """Rules whose selector list contains exactly `target` as a whole selector
    (so #info matches "#info" and "body.view-x #info", not "#info-body")."""
    out = []
    for selector, body in _rules(text):
        if re.search(rf"(^|[\s,]){re.escape(target)}\s*(,|$)", selector):
            out.append((selector, body))
    return out
