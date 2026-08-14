# Unified Health-Zone Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the three divergent per-tab health-zone search boxes with one standalone `#zone-search` component that floats over the map on all five non-stub tabs, supports full keyboard operation, and always zooms the map to the selected location.

**Architecture:** Every dashboard page ships all views' markup and activates exactly one (`Scripts/common/chrome.py`), so a single `#zone-search` DOM node — a sibling of `#map` — serves every tab. `dashboard.css` positions it per `body.view-*` across three width bands; one controller in `engine.js` owns filtering, keyboard, and open/close; a `ZONE_SEARCH_VIEWS` table supplies each view's index filter, i18n keys, and `select()` action. The shared zoom is one `fitBounds` call for all views.

**Tech Stack:** Vanilla ES5-flavoured JS (no build step, no bundler), Leaflet 1.9.4 (CDN-pinned), plain CSS in one stylesheet, Python 3.9 page builder, pytest static-source guards.

**Spec:** `docs/superpowers/specs/2026-08-14-unified-zone-search-design.md` (revision 3). Read it before starting — this plan implements it and does not restate its reasoning.

---

## Environment

Everything below assumes the repo root `/Users/user/Documents/work/BDBV2026-Epidemic_Dashboard` and branch `unified-zone-search`.

- **Python is `python3.9`**, not the system `python3` (3.14, which lacks shapely and pytest).
- **Tests run from `Scripts/`** because they import `common.*`; there is no conftest adding it to the path, the cwd does:
  ```bash
  cd Scripts && python3.9 -m pytest ../tests -v
  ```
- **Build:** `python3.9 Scripts/build_dashboard.py` from the repo root. It reads geometry from the sibling repo `../BDBV2026-Data/build/`, which must be present. It writes `output/`.
- **Never edit `Scripts/build_dashboard_public.py`** — it is a superseded single-file variant.
- Do not hand-edit the generated `*.html` at the repo root or in `output/`; they come from the build.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `Scripts/common/chrome.py` | Shared page markup | Add `#zone-search` after `#map`; delete `#zone-search-wrap`, `#trends-search-slot`, `#trends-search-wrap`, `#epi-search-wrap`, `.epi-controls` |
| `Scripts/assets/dashboard.css` | All styling and placement | Add component styling, `.visually-hidden`, three placement bands, rail clamp, three `:root` tokens; delete the dark search block, `.location-search-*`, `#trends-search-slot`, `.epi-controls` |
| `Scripts/assets/engine.js` | Index, controller, per-view table, shared zoom | Replace three search implementations with one; add `expandPanel()`; thread `opts` through `_emitZoneClick` |
| `Scripts/assets/genomic.js` | Genomic page coordinator | Accept `opts.toggle`; publish `--genomic-panel-width` |
| `locales/en.yaml`, `locales/fr.yaml` | UI strings | Add `ui.zone_search_matches` |
| `tests/test_zone_search.py` | Static source guards | New file, 9 tests |

`engine.js` is 4293 lines and this change is net-negative on it. Do not restructure it beyond the spec's removals.

---

## Task 1: Test scaffold and the markup guards

Establishes the test file and drives the `chrome.py` markup change.

**Files:**
- Create: `tests/test_zone_search.py`
- Modify: `Scripts/common/chrome.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_zone_search.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: `test_exactly_one_search_input` FAILS (`assert 0 == 1`), `test_no_retired_search_markup` FAILS (lists `zone-search-wrap`, `trends-search-input`, …), `test_zone_search_is_a_sibling_of_map` FAILS with `ValueError: substring not found`. `test_controls_panel_holds_no_search_input` also fails — the input is in `#controls` today.

- [ ] **Step 3: Add the component to `chrome.py`**

In `BODY_TEMPLATE`, replace this block (the `#trends-search-slot` comment and div, currently after `<div id="map"></div>`):

```html
<!-- Trends only, narrow screens only: engine.js moves #trends-search-wrap
     in here (out of #trends-controls, now down in the stacked bottom
     panel) so location search stays reachable next to the map, in the
     top-left corner the Leaflet zoom control used to occupy on this page
     (see body.view-trends .leaflet-control-zoom in dashboard.css). Moved
     back to its normal spot on wider screens. -->
<div id="trends-search-slot"></div>
```

with:

```html
<!-- Standalone health-zone search: ONE node serving every view, a sibling of
     #map so it is never trapped inside a panel or rail. dashboard.css
     positions it per body.view-* across three width bands; engine.js's
     ZONE_SEARCH_VIEWS table supplies each view's index filter, i18n keys and
     select() action. Replaces the three separate boxes that used to live in
     #controls, #trends-controls and .epi-controls.

     #zone-search-results holds ONLY options (it is a listbox); the
     no-matches message is #zone-search-empty, a sibling shown in its place;
     #zone-search-live is announcement-only. -->
<div id="zone-search">
  <input type="search" id="zone-search-input" autocomplete="off" spellcheck="false"
         role="combobox" aria-autocomplete="list" aria-controls="zone-search-results"
         aria-expanded="false" aria-activedescendant=""
         data-i18n-placeholder="ui.zone_search_placeholder"
         placeholder="Type a health zone name…"
         data-i18n-aria="ui.zone_search" aria-label="Search health zone" />
  <div id="zone-search-results" role="listbox" hidden></div>
  <div id="zone-search-empty" hidden></div>
  <div id="zone-search-live" role="status" aria-live="polite" class="visually-hidden"></div>
</div>
```

- [ ] **Step 4: Delete the old search box from the LAYER panel**

In `BODY_TEMPLATE`, inside `<div id="controls" class="panel">`, delete:

```html
    <div id="zone-search-wrap">
      <input type="search" id="zone-search-input" autocomplete="off" spellcheck="false"
             data-i18n-placeholder="ui.zone_search_placeholder"
             placeholder="Type a health zone name…"
             data-i18n-aria="ui.zone_search" aria-label="Search health zone"
             aria-autocomplete="list" aria-controls="zone-search-results" aria-expanded="false" />
      <div id="zone-search-results" role="listbox" hidden></div>
    </div>
```

so `<div class="panel-body">` now starts directly with `<label for="layer-select" …>`.

- [ ] **Step 5: Delete the Spatial Risk search box**

In `BODY_TEMPLATE`, replace this comment and the `.epi-controls` div that follows it:

```html
  <!-- The table always shows the national ranking; there is no geographic
       scope toggle. The search box below only matches health zones (provinces
       are filtered out in renderEpiSearchResults()), and picking one
       selects/highlights its row rather than filtering the list -- see the
       epi-search-results click handler in wireEpiTrendsUi(). Search wrap
       shares the Trends tab's .location-search-wrap/.location-search-results
       classes for styling. -->
  <div class="epi-controls">
    <div id="epi-search-wrap" class="location-search-wrap">
      <input type="search" id="epi-search-input" autocomplete="off" spellcheck="false"
             data-i18n-placeholder="ui.trends_search_placeholder"
             placeholder="Search for a location…"
             data-i18n-aria="ui.trends_search" aria-label="Search"
             aria-autocomplete="list" aria-controls="epi-search-results" aria-expanded="false" />
      <div id="epi-search-results" class="location-search-results" role="listbox"></div>
    </div>
  </div>
```

with just:

```html
  <!-- The table always shows the national ranking; there is no geographic
       scope toggle. Zone search lives in the standalone #zone-search
       component over the map (see ZONE_SEARCH_VIEWS in engine.js); picking a
       zone there selects/highlights its row rather than filtering the list. -->
```

- [ ] **Step 6: Delete the Trends search box**

In `BODY_TEMPLATE`, inside `<div id="trends-controls">`, delete:

```html
    <div id="trends-search-wrap" class="location-search-wrap">
      <input type="search" id="trends-search-input" autocomplete="off" spellcheck="false"
             data-i18n-placeholder="ui.trends_search_placeholder"
             placeholder="Search for a location…"
             data-i18n-aria="ui.trends_search" aria-label="Search"
             aria-autocomplete="list" aria-controls="trends-search-results" aria-expanded="false" />
      <div id="trends-search-results" class="location-search-results" role="listbox"></div>
    </div>
```

so `#trends-controls` holds only `.trends-scope-row`. In the comment above `<div id="trends-panel">`, change `scope/search controls up top` to `scope controls up top`.

- [ ] **Step 7: Run the tests to verify they pass**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add tests/test_zone_search.py Scripts/common/chrome.py
git commit -m "Add the standalone zone-search node and retire the three per-tab boxes"
```

---

## Task 2: Component styling

The old JS is now null-guarded into inertness (every handler is wrapped in `if (input)` / `if (results)`), so the page still builds. This task makes the new node look right.

**Files:**
- Modify: `Scripts/assets/dashboard.css`
- Modify: `tests/test_zone_search.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_zone_search.py`:

```python
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: both new tests FAIL.

- [ ] **Step 3: Replace the dark search block with the component styling**

In `Scripts/assets/dashboard.css`, replace the whole block from `#zone-search-wrap { position:relative; margin-top:2px; }` through `.zone-search-empty { padding:8px; font-size:12px; color:#888; font-style:italic; }` (currently lines 113–139, ending just before the `#legend` rule) with:

```css
  /* ── Standalone health-zone search ──────────────────────────────────────
     One node (see common/chrome.py), sibling of #map, serving every view.
     Placement per body.view-* lives further down, in the three band blocks.

     No L.DomEvent.disableClickPropagation/disableScrollPropagation is used or
     needed: #zone-search is a SIBLING of #map, not a descendant of the Leaflet
     container, so its events never reach Leaflet's container-bound handlers in
     the first place. Do not "fix" this by moving the node into the map pane. */
  #zone-search {
    position:absolute; z-index:1200;
    width:min(240px, calc(100vw - 24px));
  }
  #zone-search-input {
    display:block; width:100%; box-sizing:border-box;
    min-height:var(--zone-search-height);
    background:#ffffff; color:#2a2a27;
    border:1px solid #e7e3db; border-radius:4px;
    padding:6px 8px; font-size:12px;
    /* Floats over a basemap rather than sitting in a light rail, so the input
       carries the same lift the dropdown does. */
    box-shadow:0 2px 8px rgba(42,42,39,0.18);
  }
  #zone-search-input:focus {
    outline:none; border-color:#9b7d4e; box-shadow:0 0 0 1px rgba(155,125,78,0.35);
  }
  /* Results and the no-matches panel share one position: exactly one of them
     is ever visible, and the empty panel takes the results panel's place
     rather than stacking under it. */
  #zone-search-results,
  #zone-search-empty {
    position:absolute; left:0; right:0; top:100%;
    margin-top:6px;
    background:#ffffff; border:1px solid #e7e3db; border-radius:4px;
    box-shadow:0 4px 14px rgba(0,0,0,0.14);
    z-index:1100;
  }
  #zone-search-results {
    /* The 30vh arm matters on narrow Trends/Spatial Risk, where the map is
       height:40vh -- an unclamped five-row list opens over the whole map. */
    max-height:min(calc(5 * 32px), 30vh);
    overflow-y:auto;
  }
  #zone-search-results[hidden],
  #zone-search-empty[hidden] { display:none !important; }
  #zone-search-empty {
    padding:8px; font-size:12px; color:#9c968b; font-style:italic;
  }
  /* No :hover rule on purpose -- the controller moves .active on pointermove
     so keyboard and mouse can never highlight two different rows at once. */
  .zone-search-option {
    display:block; width:100%; text-align:left;
    background:#ffffff; color:#2a2a27;
    border:none; border-bottom:1px solid #e7e3db; border-radius:0;
    padding:7px 8px; font-size:12px; line-height:1.35;
    min-height:32px; box-sizing:border-box; cursor:pointer;
  }
  .zone-search-option:last-child { border-bottom:none; }
  .zone-search-option.active { background:#f3f1ec; color:#9b7d4e; }
  /* Announcement-only region (#zone-search-live). */
  .visually-hidden {
    position:absolute; width:1px; height:1px;
    margin:-1px; padding:0; border:0;
    clip-path:inset(50%); overflow:hidden; white-space:nowrap;
  }
```

- [ ] **Step 4: Delete the `.location-search-*` block**

Delete the whole block from the comment `/* Shared by #trends-search-wrap (Trends tab) and #epi-search-wrap (Spatial Risk tab) …` through `.location-search-results .zone-search-empty { padding:8px; font-size:12px; color:#9c968b; font-style:italic; }` (currently lines 298–338, ending just before `#epi-trends-panel h2`).

- [ ] **Step 5: Delete `.epi-controls` and `#trends-search-slot`**

Delete:

```css
  /* Holds just the location search now (the National/Provincial scope buttons
     were removed) -- same row layout as #trends-controls on the Trends tab. */
  .epi-controls {
    display:flex; align-items:center; justify-content:space-between;
    gap:10px; flex-wrap:wrap;
  }
```

and:

```css
  /* Sibling of #map (see chrome.py) -- engine.js relocates #trends-search-wrap
     in here on narrow screens (see @media max-width:700px below), out of
     #trends-controls, so search stays reachable next to the map instead of
     being buried in the stacked bottom panel. Hidden/inert otherwise. */
  #trends-search-slot { display:none; }
```

and, inside the `@media (max-width: 700px)` block, the `#trends-search-slot` rule together with its comment:

```css
    /* Location search moves to the map's top-left corner (where the zoom
       control used to be) instead of staying buried in #trends-controls,
       now down in the stacked bottom panel -- engine.js does the actual
       DOM move (wireTrendsSearchSlot()), this just positions the slot. */
    body.view-trends #trends-search-slot {
      display:block; position:absolute; z-index:1000;
      top:12px; left:12px;
      width:min(220px, calc(100vw - 24px));
    }
```

- [ ] **Step 6: Fix the `#trends-controls` layout note**

`#trends-controls` now holds one child, so `justify-content:space-between` is inert. Replace:

```css
  /* #trends-controls: scope buttons + location search side by side, no
     panel/card chrome around them -- they sit directly in the #trends-panel
     rail, above the plots column. */
  #trends-controls {
    display:flex; align-items:center; justify-content:space-between;
    gap:10px; flex-wrap:wrap;
  }
```

with:

```css
  /* #trends-controls: just the scope buttons now (location search moved to
     the standalone #zone-search component over the map). Kept as a flex row
     so a second control can be added back beside the scope buttons without
     re-deriving the layout; no justify-content, since one child needs none. */
  #trends-controls {
    display:flex; align-items:center;
    gap:10px; flex-wrap:wrap;
  }
```

- [ ] **Step 7: Run to verify pass**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: 6 passed.

- [ ] **Step 8: Commit**

```bash
git add Scripts/assets/dashboard.css tests/test_zone_search.py
git commit -m "Style the standalone zone search and retire the light rail vocabulary"
```

---

## Task 3: Tokens and band A placement

**Files:**
- Modify: `Scripts/assets/dashboard.css`
- Modify: `tests/test_zone_search.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_zone_search.py`:

```python
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
    (bands B and C come later in the file and are grouped selectors)."""
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
```

- [ ] **Step 2: Run to verify failure**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: `test_tokens_declared_exactly_once_in_root` FAILS (`--layer-panel-width declared 0 times, expected 1`), `test_band_a_offsets_sit_beside_the_two_corner_panels` FAILS (`no band-A #zone-search rule for view-map`), `test_zone_search_positioned_for_every_non_stub_view` FAILS. `test_search_offset_reads_panel_tokens_only_in_band_a` passes vacuously — there are no `#zone-search` rules inside media queries yet.

- [ ] **Step 3: Add the tokens to `:root`**

Replace:

```css
  :root {
    --view-chrome-height: 44px;
    --epi-panel-width: 50%;
    --trends-panel-width: 40%;
  }
```

with:

```css
  :root {
    --view-chrome-height: 44px;
    --epi-panel-width: 50%;
    --trends-panel-width: 40%;
    /* Band-A (wide-branch) widths of the two panels #zone-search sits beside.
       Read twice each: by the panel's own width rule (unconditional, all
       bands) and by the band-A search offset (default block only), so the
       10px gap between panel and search cannot drift. The narrow branches use
       different numbers on purpose -- see the band B/C blocks. */
    --layer-panel-width: min(340px, calc(100vw - 24px));
    --context-panel-width: min(280px, calc(50vw - 24px));
    /* Sets #zone-search-input's min-height AND every band B/C displacement
       offset, so the two can never disagree about how tall the search is. */
    --zone-search-height: 32px;
  }
```

- [ ] **Step 4: Point the two panels at their tokens**

Replace:

```css
  #controls     {
    top:12px; left:12px;
    width:min(340px, calc(100vw - 24px));
    max-width:min(340px, calc(100vw - 24px));
  }
```

with:

```css
  #controls     {
    top:12px; left:12px;
    width:var(--layer-panel-width);
    max-width:var(--layer-panel-width);
  }
```

and in `#context-national`, replace `width:min(280px, calc(50vw - 24px));` with `width:var(--context-panel-width);` (leave its `max-width:280px` alone).

- [ ] **Step 5: Add band A placement**

Immediately after the `.visually-hidden` rule added in Task 2, add:

```css
  /* ── #zone-search placement, band A (the unqualified default, ≳1000px) ──
     Bands B and C are carved out below with max-width queries only, so no
     viewport width can fall between two rules the way a
     max-width:999px / min-width:1000px pair would at 999.5px.

     On map and context the search sits beside the panel already in the
     corner; the other three tabs have an empty corner. The three rail views
     additionally clamp their width to the visible map -- see the rail clamp
     note on each rule. */
  body.view-map #zone-search {
    top:12px; left:calc(12px + var(--layer-panel-width) + 10px);
  }
  body.view-context #zone-search {
    top:12px; left:calc(12px + var(--context-panel-width) + 10px);
  }
  body.view-trends #zone-search {
    top:12px; left:12px;
    /* The rail can be dragged to 72% (TRENDS_SPLIT_MAX), leaving a map
       narrower than the search; --trends-panel-width is a percentage and
       #zone-search is positioned in #viewport-area, so this tracks a live
       drag for free. */
    width:min(240px, calc(100% - var(--trends-panel-width) - 24px));
  }
  body.view-epi-trends #zone-search {
    top:12px; left:12px;
    width:min(240px, calc(100% - var(--epi-panel-width) - 24px));
  }
  body.view-genomic-epidemiology #zone-search {
    top:12px; left:12px;
    /* #genomic-panel OVERLAYS a full-width #map (no body.view-… #map rule),
       and its width is an inline px style, so genomic.js publishes
       --genomic-panel-width for this clamp. The 70vw fallback matches the
       CSS default before genomic.js runs. */
    width:min(240px, calc(100% - var(--genomic-panel-width, 70vw) - 24px));
  }
  body.stub-view #zone-search { display:none !important; }
```

- [ ] **Step 6: Hide the search during the Spatial Risk JPG export**

In the `body.epi-map-exporting` rule list, add `#zone-search` as the first selector:

```css
  body.epi-map-exporting #zone-search,
  body.epi-map-exporting #epi-trends-legend,
```

(The JPG itself is scoped to `map.getContainer()` and `#zone-search` is outside it; this keeps the box off the screen while `#map` is temporarily full-bleed, same as every other overlay in that list.)

- [ ] **Step 7: Run to verify pass**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: 10 passed.

- [ ] **Step 8: Commit**

```bash
git add Scripts/assets/dashboard.css tests/test_zone_search.py
git commit -m "Add zone-search placement tokens and band A positioning"
```

---

## Task 4: Bands B and C

**Files:**
- Modify: `Scripts/assets/dashboard.css`
- Modify: `tests/test_zone_search.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_zone_search.py`:

```python
# Panels displaced downward by the search in band B or band C. Each must offset
# by --zone-search-height so the gap cannot drift.
DISPLACED = ["#controls", "#info", "#trends-legend", "#epi-trends-legend", "#context-national"]


def test_every_displaced_panel_offsets_by_the_search_height():
    """Each panel the search pushes down must offset by the token, not by a
    literal, so the gap between search and panel cannot drift."""
    offset = "calc(12px + var(--zone-search-height) + 8px)"
    css = _css()
    for panel in DISPLACED:
        rules = _rules_for(css, panel)
        assert rules, f"{panel} has no rule at all -- did a selector get renamed?"
        assert any(offset in body for _sel, body in rules), (
            f"{panel} is displaced by the search but no rule offsets by {offset}"
        )


def test_zone_search_input_reads_the_height_token():
    assert "min-height:var(--zone-search-height)" in _css().replace(" ", "")


def test_zone_search_repositioned_in_band_c():
    """Test 5's per-BAND half: a view positioned only in band A must fail."""
    band_c = _band_c(_css())
    for view in ["map", "context", "trends", "epi-trends"]:
        assert f"body.view-{view} #zone-search" in band_c, (
            f"view-{view} has no band-C #zone-search rule"
        )


def test_genomic_search_hidden_in_band_c():
    band_c = _band_c(_css())
    rules = _rules_for(band_c, "#zone-search")
    genomic = [b for s, b in rules if "genomic-epidemiology" in s]
    assert genomic, "no band-C #zone-search rule for the genomic view"
    assert any("display:none" in b.replace(" ", "") for b in genomic)
```

- [ ] **Step 2: Run to verify failure**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: `test_every_displaced_panel_offsets_by_the_search_height` FAILS (`#controls is displaced by the search but no rule offsets by …`), `test_zone_search_repositioned_in_band_c` FAILS (`view-map has no band-C #zone-search rule`), `test_genomic_search_hidden_in_band_c` FAILS. `test_zone_search_input_reads_the_height_token` passes — the `min-height` went in with the component styling in Task 2.

- [ ] **Step 3: Add band B**

Immediately after the band A block from Task 3, add:

```css
  /* ── Band B — 701px … 999.98px ─────────────────────────────────────────
     The beside-the-panel layout of band A collides with the opposite corner
     here: on map the search would span 362–602px while #info (right:12px,
     max-width:340px) starts at 100vw − 352, meeting at ~954px; on context the
     figures are 302–542px against #context at 100vw − 292, meeting at ~834px.
     #info is content-sized under a bare max-width, so the space actually left
     is not derivable in CSS; context could be clamped (it has a definite
     width) but follows map so the two tabs do not diverge.

     So: corner on every tab, and the two views with something already at
     12px/12px displace it downward. #info needs no displacement -- at ≥701px
     it starts at ≥349px, clear of the search's 252px right edge. */
  @media (max-width: 999.98px) {
    body.view-map #zone-search,
    body.view-context #zone-search { top:12px; left:12px; }
    body.view-map #controls { top:calc(12px + var(--zone-search-height) + 8px); }
    body.view-context #context-national {
      top:calc(12px + var(--zone-search-height) + 8px);
      /* Displacement must not push the panel's bottom edge toward the footer:
         give back exactly what the top took. */
      max-height:calc(80vh - var(--zone-search-height) - 8px);
    }
  }
```

- [ ] **Step 4: Add band C**

Inside the existing `@media (max-width: 700px)` block (the one that already contains `#controls { top:12px; }`), replace:

```css
    #controls       { top:12px; }
    #info           { top:12px; }
```

with:

```css
    /* ── Band C: the search owns the whole top row ──────────────────────
       Full width, so no clamp has to reason about the opposite corner --
       #info can be re-expanded to 60vw by the user at any time, so no static
       clamp derived from its collapsed width could have been correct. The
       rail clamp is switched off here: the rails stack BELOW a full-width
       map at this width. Everything else at top:12px drops below the search
       by exactly its height. */
    body.view-map #zone-search,
    body.view-context #zone-search,
    body.view-trends #zone-search,
    body.view-epi-trends #zone-search {
      top:12px; left:12px; width:calc(100vw - 24px);
    }
    /* No search on Genomic here: #genomic-panel has no narrow rule, so the
       map is a ~108px strip and any usable box would float over the
       phylogeny. See "Known gaps" in the design spec. */
    body.view-genomic-epidemiology #zone-search { display:none !important; }
    #controls       { top:calc(12px + var(--zone-search-height) + 8px); }
    #info {
      top:calc(12px + var(--zone-search-height) + 8px);
      max-height:calc(80vh - var(--zone-search-height) - 8px);
    }
```

- [ ] **Step 5: Displace the two narrow-screen legends**

Still inside the `@media (max-width: 700px)` block, in `body.view-trends #trends-legend` change `top:12px; bottom:auto; right:12px;` to:

```css
      top:calc(12px + var(--zone-search-height) + 8px); bottom:auto; right:12px;
```

and in `body.view-epi-trends #epi-trends-legend` change `top:12px; left:12px; right:auto; bottom:auto;` to:

```css
      top:calc(12px + var(--zone-search-height) + 8px); left:12px; right:auto; bottom:auto;
```

- [ ] **Step 6: Compensate the short-viewport `#info` cap**

The `@media (max-height: 500px)` block tightens `#info` to `max-height:70vh`, and it comes after band C, so it wins. A landscape phone is both bands. Add a combined query immediately after the `@media (max-height: 500px)` block closes:

```css
  /* A landscape phone is band C AND max-height:500px; the 70vh cap above wins
     over band C's, so re-apply the displacement give-back here. Deliberately
     NOT folded into the max-height:500px block: a wide, short window (e.g.
     1200x450) is band A, where nothing is displaced. */
  @media (max-width: 700px) and (max-height: 500px) {
    #info { max-height:calc(70vh - var(--zone-search-height) - 8px); }
  }
```

- [ ] **Step 7: Run to verify pass**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: 14 passed.

- [ ] **Step 8: Commit**

```bash
git add Scripts/assets/dashboard.css tests/test_zone_search.py
git commit -m "Add zone-search placement bands B and C with panel displacement"
```

---

## Task 5: The index and the per-view table

**Files:**
- Modify: `Scripts/assets/engine.js`
- Modify: `tests/test_zone_search.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_zone_search.py`:

```python
def test_zone_search_views_covers_exactly_the_non_stub_views():
    """A tab added later must not silently ship without a search, and a
    removed tab must not leave a dangling entry."""
    engine = _engine()
    start = engine.index("const ZONE_SEARCH_VIEWS = {")
    block = engine[start:engine.index("\n};", start)]
    keys = set(re.findall(r'^\s*"([a-z-]+)":\s*\{', block, flags=re.MULTILINE))
    assert keys == set(NON_STUB_VIEWS), f"ZONE_SEARCH_VIEWS keys {sorted(keys)}"


def test_view_is_read_from_the_body_dataset_not_active_view():
    """bootstrapInitialView() runs at the bottom of engine.js, long after the
    search block, so activeView is still its "map" default there."""
    engine = _engine()
    assert "document.body.dataset.initialView" in engine
    start = engine.index("const ZONE_SEARCH_VIEW =")
    assert "dataset.initialView" in engine[start:start + 200]
```

- [ ] **Step 2: Run to verify failure**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: both FAIL with `ValueError: substring not found`.

- [ ] **Step 3: Rename the index**

In `engine.js`, rename `TRENDS_LOCATION_INDEX` to `LOCATION_INDEX` at its declaration and update the comment above it. Replace:

```js
// --- Trends tab location search: every province + health zone, regardless
// of whether a plot happens to exist for it (unlike the old trendsEntityList()
// approach, which only ever listed places trendsPlotData() had a plot for).
// Mirrors ZONE_SEARCH_INDEX above so behaviour matches the Current Snapshot
// search, just also covering provinces since Trends has a province scope.
const TRENDS_LOCATION_INDEX = (function() {
```

with:

```js
// --- the one search index: every province + health zone, regardless of
// whether a plot happens to exist for it. Each view filters it down by `kind`
// via ZONE_SEARCH_VIEWS below -- only Trends lists provinces, because only
// Trends has a province scope. ZONE_SEARCH_INDEX above is now a private
// intermediate of this list; nothing else reads it.
const LOCATION_INDEX = (function() {
```

Then update its two remaining references. Both are in blocks this plan deletes in Task 6, so a global rename is safe:

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard
grep -n "TRENDS_LOCATION_INDEX" Scripts/assets/engine.js
```

Expected after the edit above: two hits, in `renderTrendsSearchResults()` and `renderEpiSearchResults()`. Change both to `LOCATION_INDEX`.

- [ ] **Step 4: Add the view constant and the per-view table**

Replace the marker comment `// --- health-zone search ---` (immediately above `const ZONE_SEARCH_INDEX`) with:

```js
// --- unified health-zone search -----------------------------------------
// One #zone-search node (common/chrome.py), a sibling of #map, serving every
// view. dashboard.css positions it per body.view-*; the ZONE_SEARCH_VIEWS
// table below supplies each view's index filter, i18n keys and select()
// action; wireZoneSearch() at the end of this section is the single
// controller. Replaces the three separate implementations that used to live
// in #controls, #trends-controls and .epi-controls.
```

Then, immediately after the `LOCATION_INDEX` declaration, add:

```js
// The view comes from <body data-initial-view>, NOT from activeView:
// bootstrapInitialView() runs at the very bottom of this file, so activeView
// is still its "map" default here. Every page is a single view (the nav is
// real cross-page links, and setActiveView() is called once, from that
// bootstrap), so one read at init is enough.
const ZONE_SEARCH_VIEW = document.body.dataset.initialView || "map";

const ZONE_SEARCH_VIEWS = {
  "map": {
    kinds: ["health_zone"],
    placeholder: "ui.zone_search_placeholder",
    aria: "ui.zone_search",
    select: function(entry) { setMapSelection(entry.id); },
  },
  "context": {
    kinds: ["health_zone"],
    placeholder: "ui.zone_search_placeholder",
    aria: "ui.zone_search",
    select: function(entry) { selectContextZone(entry.id); },
  },
  "trends": {
    kinds: ["province", "health_zone"],
    // The only tab that lists provinces, so the only one whose placeholder
    // and accessible name say "location" rather than "health zone".
    placeholder: "ui.trends_search_placeholder",
    aria: "ui.trends_search",
    select: function(entry) {
      // Scope FIRST: setTrendsScope() nulls the selection, so setting the
      // selection before it would be undone immediately.
      if (entry.kind !== trendsScope) {
        document.querySelectorAll(".trends-scope-btn").forEach(function(b) {
          b.classList.toggle("active", b.getAttribute("data-scope") === entry.kind);
        });
        setTrendsScope(entry.kind);
      }
      setTrendsSelection(entry.id);
    },
  },
  "epi-trends": {
    kinds: ["health_zone"],
    placeholder: "ui.zone_search_placeholder",
    aria: "ui.zone_search",
    select: function(entry) {
      // A ranked list of one zone isn't useful, so this selects/highlights the
      // row rather than filtering the table -- same as clicking the row.
      // setEpiSelected() re-renders the table, so find the row afterwards.
      setEpiSelected(entry.id);
      const tbody = document.getElementById("epi-trends-tbody");
      if (!tbody) return;
      const rows = tbody.querySelectorAll("tr[data-nom]");
      for (let i = 0; i < rows.length; i++) {
        if (rows[i].getAttribute("data-nom") === entry.id) {
          if (rows[i].scrollIntoView) rows[i].scrollIntoView({block: "center"});
          break;
        }
      }
    },
  },
  "genomic-epidemiology": {
    kinds: ["health_zone"],
    placeholder: "ui.zone_search_placeholder",
    aria: "ui.zone_search",
    // {toggle:false} matters: _emitZoneClick is a toggle by design (clicking
    // the same polygon twice clears). The search clears its input after every
    // pick, so a repeat search would silently DEselect while the shared zoom
    // still framed the zone -- map says "here", tree says "nothing".
    select: function(entry) {
      if (genomicMapHooks) genomicMapHooks._emitZoneClick(entry.id, {toggle: false});
    },
  },
};
```

- [ ] **Step 5: Run to verify pass**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: 16 passed.

- [ ] **Step 6: Commit**

```bash
git add Scripts/assets/engine.js tests/test_zone_search.py
git commit -m "Add the unified search index and per-view behaviour table"
```

---

## Task 6: The shared zoom

**Files:**
- Modify: `Scripts/assets/engine.js`
- Modify: `tests/test_zone_search.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_zone_search.py`:

```python
def test_no_fitbounds_mixes_padding_with_a_directional_key():
    """Leaflet resolves `paddingBottomRight || padding || [0,0]`, so a
    directional key REPLACES padding on that side instead of adding to it --
    and [0,0] is an array, hence truthy. Mixing them silently drops padding on
    one side, which is invisible in a screenshot unless the fitted geometry
    happens to sit near an edge.
    """
    engine = _engine()
    for call in re.findall(r"fitBounds\((.*?)\n?\s*\}\);", engine, flags=re.DOTALL):
        has_plain = re.search(r"\bpadding\s*:", call)
        has_directional = re.search(r"\bpadding(TopLeft|BottomRight)\s*:", call)
        assert not (has_plain and has_directional), (
            f"fitBounds mixes padding with a directional key:\n{call}"
        )
```

- [ ] **Step 2: Prove the guard actually bites**

This test passes vacuously against today's source — no `fitBounds` call uses a directional key yet — so confirm it can fail before trusting it. Temporarily add to `engine.js`, just below `ZONE_SEARCH_VIEWS`, the exact form the spec warns against:

```js
function zoneSearchZoomToBroken(bounds) {
  map.fitBounds(bounds, {
    padding: [40, 40],
    paddingBottomRight: [0, 0],
  });
}
```

Run:

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py::test_no_fitbounds_mixes_padding_with_a_directional_key -v
```

Expected: FAIL, with `fitBounds mixes padding with a directional key:` and the offending call echoed. Now delete `zoneSearchZoomToBroken` and re-run — expected PASS.

- [ ] **Step 3: Add the zoom helpers**

Immediately after `ZONE_SEARCH_VIEWS`, add:

```js
// Zoom padding as Leaflet [x, y]. Narrow Trends/Spatial Risk maps are
// height:40vh -- ~192px on a 480px viewport -- so [40,40] would eat 80px of it.
function zoneSearchPad() {
  return window.matchMedia("(max-width: 700px)").matches ? [16, 16] : [40, 40];
}

// Width of map hidden behind an OVERLAYING panel. Zero everywhere except
// Genomic: the Trends and Spatial Risk rails narrow #map itself, so Leaflet
// already fits inside the visible area there, but #genomic-panel sits on top
// of a full-width #map. Its width is an inline px style written by
// applyWidth() in genomic.js, so it is read from the element.
function zoneSearchInsetX() {
  if (ZONE_SEARCH_VIEW !== "genomic-epidemiology") return 0;
  const panel = document.getElementById("genomic-panel");
  return panel ? panel.offsetWidth : 0;
}

// NEVER pass `padding` alongside paddingTopLeft/paddingBottomRight: Leaflet
// resolves each side as `paddingBottomRight || padding || [0,0]`, so a
// directional key REPLACES padding on that side rather than adding to it, and
// [0,0] is truthy. tests/test_zone_search.py guards this.
function zoneSearchZoomTo(entry) {
  let bounds = null;
  if (entry.kind === "province") {
    provinceOutlineLayer.eachLayer(function(layer) {
      const props = layer.feature && layer.feature.properties;
      if (!bounds && props && props.province === entry.id) bounds = layer.getBounds();
    });
  } else {
    const layer = findGeoLayerByNom(entry.id);
    if (layer) bounds = layer.getBounds();
  }
  // No geometry (a zone in the index but absent from the drawn layer): the
  // selection still applies, the zoom is simply skipped.
  if (!bounds || !bounds.isValid()) return;
  const pad = zoneSearchPad();
  map.fitBounds(bounds, {
    paddingTopLeft: pad,
    paddingBottomRight: [pad[0] + zoneSearchInsetX(), pad[1]],
    // Caps how far we zoom INTO a small unit; a large province fits well below
    // z10 and never reaches it.
    maxZoom: 10,
  });
}
```

- [ ] **Step 4: Record the reversal in the Trends auto-pan comment**

Replace the comment above `setTrendsSelection`:

```js
// fitMapToTrendsSelection() used to live here and auto pan/zoom the map to
// whichever province/health zone was selected, with padding carved out for
// the old floating trends panel that used to sit on top of the map. Now
// that the map and plots panel are two separate fixed columns (nothing
// overlaps), that auto-pan just made the map jump around distractingly on
// every click, so it's been removed -- selecting a zone/province no longer
// moves the map at all.
```

with:

```js
// fitMapToTrendsSelection() used to live here and auto pan/zoom the map to
// whichever province/health zone was selected, with padding carved out for
// the old floating trends panel that used to sit on top of the map. Now
// that the map and plots panel are two separate fixed columns (nothing
// overlaps), that auto-pan just made the map jump around distractingly on
// every click, so it's been removed -- CLICKING a zone/province still does
// not move the map.
//
// SEARCHING one does, via zoneSearchZoomTo(). The asymmetry is deliberate:
// a searched location can be offscreen, a clicked one cannot. Do not
// "restore consistency" by deleting one side -- they answer different needs.
```

- [ ] **Step 5: Run to verify pass**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: 17 passed.

- [ ] **Step 6: Commit**

```bash
git add Scripts/assets/engine.js tests/test_zone_search.py
git commit -m "Add the shared search zoom with correct Leaflet padding semantics"
```

---

## Task 7: The controller

The largest task. It adds the single controller and deletes all three old implementations.

**Files:**
- Modify: `Scripts/assets/engine.js`

- [ ] **Step 1: Add the controller**

Replace everything from `const zoneSearchInput = document.getElementById("zone-search-input");` down to the closing `}` of the final `if (zoneSearchInput && zoneSearchResults) { … }` block (i.e. the whole old Snapshot implementation, ending just before `// --- province outlines (Trends view) ---`), **keeping `findGeoLayerByNom()`**, which is also used by the flow-arc code. The replacement:

```js
function findGeoLayerByNom(nom) {
  let found = null;
  geoLayer.eachLayer(function(layer) {
    if (!found && layer.feature && layer.feature.properties && layer.feature.properties.nom === nom) {
      found = layer;
    }
  });
  return found;
}

(function wireZoneSearch() {
  const view = ZONE_SEARCH_VIEWS[ZONE_SEARCH_VIEW];
  const root = document.getElementById("zone-search");
  const input = document.getElementById("zone-search-input");
  const results = document.getElementById("zone-search-results");
  const empty = document.getElementById("zone-search-empty");
  const live = document.getElementById("zone-search-live");
  // Stub pages have no table entry: no-op rather than dereference view.kinds.
  if (!view || !root || !input || !results || !empty || !live) return;

  const KINDS = {};
  view.kinds.forEach(function(k) { KINDS[k] = true; });

  let matches = [];
  let activeIdx = -1;

  // Per-view i18n goes on the data-i18n-* ATTRIBUTES, never the properties:
  // applyI18n() re-reads those attributes on every language toggle, so setting
  // input.placeholder here would survive only until the first EN/FR switch --
  // a bug that only ever shows up in the French build.
  input.setAttribute("data-i18n-placeholder", view.placeholder);
  input.setAttribute("data-i18n-aria", view.aria);
  applyI18n();

  function isNarrow() {
    return window.matchMedia("(max-width: 700px)").matches;
  }

  function close() {
    results.hidden = true;
    results.innerHTML = "";
    empty.hidden = true;
    matches = [];
    activeIdx = -1;
    input.setAttribute("aria-expanded", "false");
    input.setAttribute("aria-activedescendant", "");
  }

  function setActive(idx) {
    if (!matches.length) return;
    activeIdx = Math.max(0, Math.min(idx, matches.length - 1));
    const opts = results.querySelectorAll(".zone-search-option");
    opts.forEach(function(el, i) {
      const on = i === activeIdx;
      el.classList.toggle("active", on);
      el.setAttribute("aria-selected", on ? "true" : "false");
    });
    const active = opts[activeIdx];
    if (active) {
      input.setAttribute("aria-activedescendant", active.id);
      if (active.scrollIntoView) active.scrollIntoView({block: "nearest"});
    }
  }

  function render(query) {
    const q = String(query || "").trim().toLowerCase();
    if (!q) {
      close();
      live.textContent = "";
      return;
    }
    matches = LOCATION_INDEX.filter(function(it) {
      return KINDS[it.kind] && it.haystack.indexOf(q) !== -1;
    }).slice(0, 40);
    if (!matches.length) {
      const msg = t("ui.zone_search_no_matches");
      results.hidden = true;
      results.innerHTML = "";
      empty.textContent = msg;
      empty.hidden = false;
      activeIdx = -1;
      // aria-expanded tracks the LISTBOX, and there is nothing selectable.
      input.setAttribute("aria-expanded", "false");
      input.setAttribute("aria-activedescendant", "");
      live.textContent = msg;
      return;
    }
    empty.hidden = true;
    results.innerHTML = matches.map(function(it, i) {
      return "<button type='button' role='option' class='zone-search-option'" +
        " id='zone-search-opt-" + i + "' aria-selected='false' data-idx='" + i + "'>" +
        escHtml(it.label) + "</button>";
    }).join("");
    results.hidden = false;
    input.setAttribute("aria-expanded", "true");
    setActive(0);
    live.textContent = tf("ui.zone_search_matches", {n: matches.length});
  }

  function pick(idx) {
    const entry = matches[idx];
    if (!entry) return;
    view.select(entry);
    zoneSearchZoomTo(entry);
    // The box is a query field, not a state indicator: the selection is
    // visible in the map highlight / info panel / table row / plot titles.
    input.value = "";
    close();
    live.textContent = "";
    // Desktop: stay focused so the next search starts immediately. Narrow:
    // the on-screen keyboard would cover half the map we just zoomed.
    if (isNarrow()) input.blur();
  }

  input.addEventListener("input", function() { render(input.value); });
  input.addEventListener("focus", function() {
    if (input.value.trim()) render(input.value);
  });

  input.addEventListener("keydown", function(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (results.hidden) render(input.value);
      else setActive(activeIdx + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive(activeIdx - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      // No-op on a closed list.
      if (!results.hidden) pick(activeIdx);
    } else if (e.key === "Escape") {
      // preventDefault matters: Chrome and WebKit clear an
      // input[type=search] natively on Esc, which would pre-empt the
      // two-stage close-then-clear.
      e.preventDefault();
      if (!results.hidden || !empty.hidden) close();
      else input.value = "";
    } else if (e.key === "Tab") {
      close();
    }
  });

  // mousedown, not click: the input must not lose focus before we read the
  // index. pointermove moves the ACTIVE row rather than painting a separate
  // hover state, so keyboard and mouse can never highlight two rows at once.
  results.addEventListener("mousedown", function(e) {
    const btn = e.target.closest(".zone-search-option");
    if (!btn) return;
    e.preventDefault();
    pick(parseInt(btn.getAttribute("data-idx"), 10));
  });
  results.addEventListener("pointermove", function(e) {
    const btn = e.target.closest(".zone-search-option");
    if (!btn) return;
    setActive(parseInt(btn.getAttribute("data-idx"), 10));
  });

  document.addEventListener("click", function(e) {
    if (!root.contains(e.target)) close();
  });
})();
```

- [ ] **Step 2: Delete the Trends search implementation**

In `engine.js`:

1. In `setTrendsSelection(key, opts)`, drop the parameter and the search-clearing branch. Replace the signature and the `if (opts.fromSearch) { … }` block so the function becomes:

```js
function setTrendsSelection(key) {
  trendsSelectedKey = key || null;
  // Repaint outlines and the province ring for the new selection. All three
  // scopes want the same call now that the ring reads trendsSelectedKey itself;
  // the branches only survived from when this passed the selection in.
  applyProvinceOutlineStyles(null);
  renderTrendsPlots();
  if (activeView === "trends") geoLayer.setStyle(styleFn);
  refreshZoneSelection();
}
```

2. Delete `renderTrendsSearchResults()` entirely.
3. In `wireTrendsPanelUi()`, delete the `searchInput` / `searchResults` lookups, the input-clearing lines inside the scope-button handler, the two `if (searchInput)` / `if (searchResults)` listener blocks, and the `document.addEventListener("click", …)` dismissal. The IIFE reduces to:

```js
(function wireTrendsPanelUi() {
  const scopeButtons = document.querySelectorAll(".trends-scope-btn");
  scopeButtons.forEach(function(btn) {
    btn.addEventListener("click", function() {
      const scope = btn.getAttribute("data-scope") || "national";
      scopeButtons.forEach(function(b) { b.classList.toggle("active", b === btn); });
      setTrendsScope(scope);
    });
  });
  setTrendsScope("national");
})();
```

4. Delete the entire `wireTrendsSearchSlot()` IIFE together with its leading comment block (`// --- Trends tab: on narrow screens, relocate the location search bar …`).

- [ ] **Step 3: Delete the Spatial Risk search implementation**

In `wireEpiTrendsUi()`, delete `epiSearchInput`, `epiSearchResults`, `epiClearSearchUi()`, `epiApplyHealthZone()`, `renderEpiSearchResults()`, the two listener blocks, and the `document.addEventListener("click", …)` dismissal — everything from `const epiSearchInput = …` down to the comment `// Sortable column headers replace the old rank-by-RR/rank-by-priority`, which stays.

- [ ] **Step 4: Verify no dangling references**

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard
grep -n "TRENDS_LOCATION_INDEX\|zoneSearchWrap\|zoneSearchMatches\|zoneSearchActiveIdx\|selectHealthZone\|renderZoneSearchResults\|closeZoneSearchResults\|setZoneSearchActive\|renderTrendsSearchResults\|renderEpiSearchResults\|epiClearSearchUi\|epiApplyHealthZone\|wireTrendsSearchSlot\|fromSearch\|location-search" Scripts/assets/engine.js
```

Expected: no output.

- [ ] **Step 5: Run the whole suite**

```bash
cd Scripts && python3.9 -m pytest ../tests -v
```

Expected: all pass, including the pre-existing suites.

- [ ] **Step 6: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "Replace the three search implementations with one controller"
```

---

## Task 8: Genomic toggle, readiness, and panel width

**Files:**
- Modify: `Scripts/assets/engine.js`
- Modify: `Scripts/assets/genomic.js`
- Modify: `tests/test_zone_search.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_zone_search.py`:

```python
GENOMIC = REPO / "Scripts" / "assets" / "genomic.js"


def test_zone_click_emitter_threads_options():
    """The search needs a non-toggling select; map clicks keep toggling."""
    engine = ENGINE.read_text(encoding="utf-8")
    assert "_emitZoneClick: function (nom, opts)" in engine
    assert "onZoneClickCb(nom, opts)" in engine


def test_genomic_select_zone_honours_the_toggle_option():
    genomic = GENOMIC.read_text(encoding="utf-8")
    assert "function selectZone(nom, opts)" in genomic
    assert "opts.toggle === false" in genomic


def test_genomic_publishes_its_panel_width():
    """The CSS rail clamp reads --genomic-panel-width; applyWidth() is the
    single writer of the inline px width, so it must publish it too."""
    genomic = GENOMIC.read_text(encoding="utf-8")
    assert "--genomic-panel-width" in genomic
```

- [ ] **Step 2: Run to verify failure**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: three FAILs.

- [ ] **Step 3: Thread `opts` through the hook and gate the search on readiness**

In `engine.js`, in the `genomicMapHooks` IIFE, replace:

```js
    onZoneClick: function (cb) { onZoneClickCb = cb; },
```

with:

```js
    // Registration doubles as the genomic readiness signal: it happens in
    // startCoordinator(), i.e. only once the tree/tip data has resolved. Until
    // then _emitZoneClick no-ops, so the search would zoom the map and select
    // nothing -- and would do so forever if the payload is absent or the tree
    // never mounts. So #zone-search starts hidden on this view and appears
    // here. Hiding rather than disabling means a never-mounting tree leaves no
    // broken-looking box. _emitMarkerClick shares this coordinator, so this
    // one gate covers every genomic entry point.
    //
    // This is the ONE place the search reaches into these otherwise
    // tip-agnostic hooks; it is deliberate, not drift.
    onZoneClick: function (cb) {
      onZoneClickCb = cb;
      const box = document.getElementById("zone-search");
      if (box) box.classList.add("zone-search-ready");
    },
```

and replace:

```js
    _emitZoneClick: function (nom) { if (onZoneClickCb) onZoneClickCb(nom); },
```

with:

```js
    // opts is forwarded untouched; the search passes {toggle:false} so a
    // repeat search selects rather than deselecting. See genomic.js selectZone.
    _emitZoneClick: function (nom, opts) { if (onZoneClickCb) onZoneClickCb(nom, opts); },
```

- [ ] **Step 4: Add the hidden-until-ready CSS**

In `dashboard.css`, immediately after `body.stub-view #zone-search { display:none !important; }`, add:

```css
  /* Genomic only: revealed by genomicMapHooks.onZoneClick() once the tree
     coordinator has registered -- see that hook in engine.js for why. */
  body.view-genomic-epidemiology #zone-search { display:none; }
  body.view-genomic-epidemiology #zone-search.zone-search-ready { display:block; }
```

Note this must come *after* the `body.view-genomic-epidemiology #zone-search` positioning rule from Task 3 so the `display` declarations are additive, not overridden.

- [ ] **Step 5: Honour the toggle option in `genomic.js`**

Replace:

```js
    // marker OR polygon → select that zone's tips; click the same source again → clear
    function selectZone(nom) {
      var key = "zone:" + up(nom);
      if (key === activeKey) { clearAll(); return; }
```

with:

```js
    // marker OR polygon → select that zone's tips; click the same source again → clear.
    // opts.toggle === false suppresses that clear: the search box empties after
    // every pick, so a user searching the same zone twice would otherwise
    // DEselect it while the map still zoomed straight to it.
    function selectZone(nom, opts) {
      var key = "zone:" + up(nom);
      var toggle = !(opts && opts.toggle === false);
      if (toggle && key === activeKey) { clearAll(); return; }
```

and forward the options from the two subscriptions:

```js
    hooks.onMarkerClick(function (nom, opts) { selectZone(nom, opts); });
    hooks.onZoneClick(function (nom, opts) { selectZone(nom, opts); });
```

- [ ] **Step 6: Publish the panel width**

In `genomic.js`, replace `applyWidth()`:

```js
  function applyWidth(px) {
    var panel = document.getElementById("genomic-panel");
    if (!panel) return;
    px = Math.max(MIN_W, Math.min(maxW(), px));
    panel.style.width = px + "px";
    window.dispatchEvent(new Event("resize"));
  }
```

with:

```js
  function applyWidth(px) {
    var panel = document.getElementById("genomic-panel");
    if (!panel) return;
    px = Math.max(MIN_W, Math.min(maxW(), px));
    panel.style.width = px + "px";
    publishPanelWidth(px);
    window.dispatchEvent(new Event("resize"));
  }

  // #genomic-panel OVERLAYS a full-width #map (unlike the Trends and Spatial
  // Risk rails, which narrow #map itself), so dashboard.css needs its width to
  // clamp #zone-search to the visible map strip. The width is an inline px
  // style, unreachable from CSS, so the single writer publishes it as a custom
  // property in the same breath -- the two cannot drift.
  function publishPanelWidth(px) {
    document.documentElement.style.setProperty("--genomic-panel-width", px + "px");
  }
```

Then publish the initial CSS-derived width once at init. In `initResize()`, immediately after the `if (!panel || !handle) return;` guard, add:

```js
    // The starting width comes from the stylesheet (min(634px, 70vw)), not
    // from applyWidth(), so seed the custom property from the live geometry.
    publishPanelWidth(panel.offsetWidth);
```

- [ ] **Step 7: Run to verify pass**

```bash
cd Scripts && python3.9 -m pytest ../tests -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add Scripts/assets/engine.js Scripts/assets/genomic.js Scripts/assets/dashboard.css tests/test_zone_search.py
git commit -m "Give the genomic search a non-toggling select, a readiness gate and a width clamp"
```

---

## Task 9: Narrow-screen panel expansion

**Files:**
- Modify: `Scripts/assets/engine.js`

- [ ] **Step 1: Export `expandPanel` from `wirePanelToggles()`**

`setCollapsed()` owns both the `.collapsed` class and the `+`/`−` glyph, so stripping the class alone leaves an open panel showing `+` whose next tap collapses nothing. Add a module-level binding.

Above the `wirePanelToggles()` IIFE, add:

```js
// Assigned by wirePanelToggles(); lets the zone search open a collapsed detail
// panel on narrow screens without duplicating setCollapsed()'s glyph handling.
let expandPanel = function() {};
```

Then, inside the IIFE, immediately after `setCollapsed()` is defined, add:

```js
  expandPanel = function(panelId) {
    const panel = document.getElementById(panelId);
    if (!panel || !panel.classList.contains("collapsed")) return;
    const btn = panelId === "info"
      ? document.getElementById("info-toggle")
      : document.querySelector('.panel-toggle[data-target="' + panelId + '"]');
    if (btn) setCollapsed(panel, btn, false);
  };
```

(`#info` is the one panel whose toggle is `#info-toggle` rather than a
`.panel-toggle[data-target]`, which is why it is special-cased.)

- [ ] **Step 2: Expand the detail panel after a narrow search selection**

In `wireZoneSearch()`'s `pick()`, replace:

```js
    if (isNarrow()) input.blur();
```

with:

```js
    if (isNarrow()) {
      input.blur();
      // wirePanelToggles() auto-collapses every panel on load at this width,
      // so without this the only feedback from a search is a zoom and a
      // highlight on a map the user may not recognise. #context-national is
      // deliberately left collapsed: the search selects a ZONE, and #context
      // is where zone context appears.
      if (ZONE_SEARCH_VIEW === "map") expandPanel("info");
      else if (ZONE_SEARCH_VIEW === "context") expandPanel("context");
    }
```

- [ ] **Step 3: Verify the ordering is sound**

`wirePanelToggles()` runs later in the file than `wireZoneSearch()`, but `expandPanel` is only *called* from a user event, long after both IIFEs have run. Confirm the declaration precedes both:

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard
grep -n "let expandPanel\|expandPanel = function\|expandPanel(" Scripts/assets/engine.js
```

Expected: the `let expandPanel` line number is lower than the `expandPanel = function` assignment, and both are outside `wireZoneSearch()`.

- [ ] **Step 4: Run the suite**

```bash
cd Scripts && python3.9 -m pytest ../tests -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "Expand the collapsed detail panel after a narrow-screen search"
```

---

## Task 10: Locale key and parity guard

**Files:**
- Modify: `locales/en.yaml`, `locales/fr.yaml`
- Modify: `tests/test_zone_search.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_zone_search.py`:

```python
LOCALES = [REPO / "locales" / "en.yaml", REPO / "locales" / "fr.yaml"]

# Keys engine.js names from JS rather than from a data-i18n attribute. Nothing
# else in the repo checks these exist -- a typo would silently render the key
# path as the UI string, in one language only.
JS_NAMED_KEYS = [
    "zone_search",
    "zone_search_placeholder",
    "zone_search_no_matches",
    "zone_search_matches",
    "trends_search",
    "trends_search_placeholder",
]


def test_every_js_named_locale_key_exists_in_both_locales():
    for path in LOCALES:
        text = path.read_text(encoding="utf-8")
        missing = [k for k in JS_NAMED_KEYS if not re.search(rf"^\s*{k}:", text, re.MULTILINE)]
        assert not missing, f"{path.name} is missing {missing}"


def test_zone_search_views_only_names_existing_keys():
    engine = _engine()
    start = engine.index("const ZONE_SEARCH_VIEWS = {")
    block = engine[start:engine.index("\n};", start)]
    referenced = set(re.findall(r'"ui\.([a-z_]+)"', block))
    for path in LOCALES:
        text = path.read_text(encoding="utf-8")
        missing = [k for k in sorted(referenced) if not re.search(rf"^\s*{k}:", text, re.MULTILINE)]
        assert not missing, f"{path.name} is missing {missing}"
```

- [ ] **Step 2: Run to verify failure**

```bash
cd Scripts && python3.9 -m pytest ../tests/test_zone_search.py -v
```

Expected: `test_every_js_named_locale_key_exists_in_both_locales` FAILS on `zone_search_matches` for both files.

- [ ] **Step 3: Add the key**

In `locales/en.yaml`, after `zone_search_no_matches: "No matches"`:

```yaml
  zone_search_matches: "{n} matches"
```

In `locales/fr.yaml`, after `zone_search_no_matches: "Aucun résultat"`:

```yaml
  zone_search_matches: "{n} résultats"
```

(`tf()` in `engine.js` does the `{n}` substitution; no new machinery.)

- [ ] **Step 4: Run to verify pass**

```bash
cd Scripts && python3.9 -m pytest ../tests -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add locales/en.yaml locales/fr.yaml tests/test_zone_search.py
git commit -m "Add the search match-count string and a locale parity guard"
```

---

## Task 11: Build and manual verification

Static guards cannot see a rendered page. This task is the browser pass.

**Files:**
- Modify: generated `output/*.html`, then repo-root `*.html` and `assets/`

- [ ] **Step 1: Build**

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard
python3.9 Scripts/build_dashboard.py
```

Expected: completes without traceback and writes `output/*.html`. If it fails with a missing-path error, confirm the sibling data repo `../BDBV2026-Data/build/` exists.

- [ ] **Step 2: Serve**

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard/output && python3.9 -m http.server 8000
```

Open `http://localhost:8000/index.html`. `file://` URLs will not work.

- [ ] **Step 3: Work the checklist**

Record the result of each. Any failure stops the task and gets fixed before proceeding.

1. **Band B, ~760px and ~900px**, Snapshot and Context, with `#info` / `#context` expanded: the search sits in the corner, the left panel is pushed down, nothing overlaps.
2. **Rail drag**: on Trends and Spatial Risk at ~760px drag the split to maximum; the search stays inside the visible map. Repeat on Genomic with `#genomic-resize`.
3. **Genomic, same zone twice**: search a zone, then search it again. It stays selected and zoomed — it must not deselect.
4. **Genomic during load**: reload and look before the phylogeny renders. No search box; it appears when the tree does.
5. **Genomic, far-right zone**: search a zone on the eastern edge; it is framed in the visible strip, not behind the panel. Repeat after a resize drag.
6. **Bottom-right zone** on Snapshot and Trends: padding is symmetric — the zone is not flush against the bottom-right edge. (This is the visual counterpart of the `fitBounds` guard.)
7. **EN → FR → EN on Trends**: placeholder stays the location one ("Rechercher un lieu…" in FR), accessible name stays "Search"/"Recherche".
8. **Narrow Snapshot**: expand `#info`, open the dropdown — no overlap. Then search a zone: `#info` expands and its toggle shows `−`, not `+`.
9. **Spatial Risk**: hover a zone with the list open; the dropdown paints above `#epi-float`.
10. **Narrow Trends and Spatial Risk**: select from the search; the map is not over-zoomed and the dropdown does not cover the whole 40vh map.
11. **Landscape phone (e.g. 740×420)**: the displaced `#info` does not run under the footer.
12. **Keyboard only**, one tab: Tab into the input, type, `↓`/`↑` (clamping at both ends), `Enter` selects, `Esc` closes, `Esc` clears.
13. **All five tabs**, wide and narrow: each tab's own selection state updates (map highlight, info/context panel, table row, plot title) and the map zooms.

- [ ] **Step 4: Deploy the build to the repo root**

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard
cp output/*.html .
rm -rf assets && cp -r output/assets assets
```

- [ ] **Step 5: Final full-suite run**

```bash
cd Scripts && python3.9 -m pytest ../tests -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Rebuild pages with the unified zone search"
```

---

## Done

Verify against the spec's §Goals before opening a PR:

1. One component, one behaviour, one treatment across all five non-stub tabs — with the documented Genomic/band-C exception.
2. Standalone over the map, in no panel or rail.
3. `↑`/`↓`/`Enter`/`Esc` work everywhere.
4. Every selection zooms the map.
