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
    """The live region is announcement-only: it must be in the a11y tree but
    off-screen. A bare substring check would pass on an empty rule."""
    rules = _rules_for(_css(), ".visually-hidden")
    assert rules, ".visually-hidden is not defined in dashboard.css"
    body = rules[0][1].replace(" ", "")
    for decl in ("position:absolute", "width:1px", "height:1px", "overflow:hidden"):
        assert decl in body, f".visually-hidden is missing {decl}"
    assert 'class="visually-hidden"' in _chrome(), "nothing applies .visually-hidden"


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


def test_stylesheet_nesting_stays_within_helper_assumptions():
    """_rules()/_media_blocks() assume at most one level of nesting
    (@media > rule). Violate that and _rules() silently drops the enclosing
    rule and fabricates a selector from the leftovers -- no error, just wrong
    data, which would make the band assertions below pass vacuously. Fail
    loudly here instead."""
    css = _css()
    assert css.count("{") == css.count("}"), "unbalanced braces in dashboard.css"
    for at_rule in ("@supports", "@keyframes", "@font-face", "@container", "@layer"):
        assert at_rule not in css, (
            f"{at_rule} introduces nesting the CSS test helpers cannot parse; "
            "extend _rules()/_media_blocks() before using it"
        )
    # Native CSS nesting needs no preprocessor and still balances braces, so
    # neither check above sees it. Given `#zone-search { &:hover { ... } }`,
    # _rules() skips the outer rule and matches the INNER block as a flat rule
    # with selector "&:hover" -- dropping #zone-search from the parsed set.
    assert "&" not in css, (
        "native CSS nesting (or a stray &) breaks the flat-rule parser in "
        "_rules(); extend the helpers before using it"
    )


# --token: value;  (comments already stripped by _css())
CSS_DECL = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")

OWNED_TOKENS = ["--layer-panel-width", "--context-panel-width", "--zone-search-height"]


def _root_block():
    """The single :root { ... } declaration block."""
    css = _css()
    start = css.index(":root {")
    return css[start:css.index("}", start)]


def test_tokens_declared_exactly_once_in_root():
    css = _css()
    root = _root_block()
    for token in OWNED_TOKENS:
        declared = [m.group(1) for m in CSS_DECL.finditer(css) if m.group(1) == token]
        assert len(declared) == 1, f"{token} declared {len(declared)} times, expected 1"
        assert token in root, f"{token} is not declared in :root"


def test_search_offset_reads_panel_tokens_only_in_band_a():
    """Band A is the unqualified default; bands B and C are max-width blocks.

    #controls / #context-national read these tokens for their own width in ALL
    bands -- that is correct and unconstrained. The constraint is on the
    CONSUMER: only the band-A search offset may read them.
    """
    for query, body in _media_blocks(_css()):
        for selector, decls in _rules(body):
            if "#zone-search" not in selector:
                continue
            for token in ("--layer-panel-width", "--context-panel-width"):
                assert token not in decls, (
                    f"search offset reads {token} inside {query}: {selector}"
                )


def test_band_a_offsets_sit_beside_the_two_corner_panels():
    """The first #zone-search rule for each of these views is the band-A one
    (bands B and C come later in the file and are grouped selectors). If Task 4
    ever adds a standalone per-view rule in a band-B/C block ABOVE this point,
    this regex matches that instead -- it fails loudly rather than silently,
    since band B/C rules must not contain these tokens, but the fix is to
    anchor the search rather than to relax the assertion."""
    css = _css()
    for view, token in (("map", "--layer-panel-width"), ("context", "--context-panel-width")):
        m = re.search(rf"body\.view-{view} #zone-search \{{([^}}]*)\}}", css)
        assert m, f"no band-A #zone-search rule for view-{view}"
        assert token in m.group(1), f"band-A view-{view} offset does not read {token}"


def test_zone_search_positioned_for_every_non_stub_view():
    css = _css()
    for view in NON_STUB_VIEWS:
        assert f"body.view-{view} #zone-search" in css, f"no #zone-search rule for view-{view}"
    assert "body.stub-view #zone-search" in css
