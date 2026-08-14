# Harmonised Zone State Styling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the outbreak map one resting/hover/selected grammar for health zones across all five tabs, with an off-white resting border, and make a selected zone's highlight immune to being overpainted by a hovered neighbour.

**Architecture:** All state colours and weights become CSS custom properties in the brand theme layer, read through `themeVar()` with full JS fallbacks. Every tier's weight is a multiplier on one zoom ramp, so no tier can invert against the resting border. Selection stops being a property of the zone polygon and becomes two stacked `fill: none` paths in a dedicated Leaflet pane above the polygons, fed by a single derived accessor over the five existing per-view selection variables.

**Tech Stack:** Vanilla ES5-flavoured JS against Leaflet 1.x (`Scripts/assets/engine.js`), CSS custom properties (`Data/Branding/dashboard-theme.css`), pytest for static guard tests, `Scripts/build_dashboard.py` to build.

**Spec:** `docs/superpowers/specs/2026-08-14-map-zone-state-styling-design.md`

---

## Context an engineer needs before starting

**Source vs. build output.** `Scripts/assets/engine.js` and `Data/Branding/dashboard-theme.css` are
the sources. The repo-root `assets/` and `output/` directories are **build artifacts** regenerated
by CI — never hand-edit them, and never commit them from a local build. Every `git add` in this
plan lists explicit source paths for that reason. If a local build dirties them, run
`git checkout -- output assets` before committing.

`Scripts/build_dashboard_public.py` contains a stale inline copy of several of these same
functions. It predates the assets split and is **not** part of this work. Leave it alone.

**Build and serve** (used by the verification steps in most tasks):

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard
python3.9 Scripts/build_dashboard.py
cd output && python3.9 -m http.server 8765
```

Then open `http://localhost:8765/index.html`. The pages must be served over HTTP — opening the
file directly will not work. `python3.9` specifically; the system `python3` is a different
interpreter here.

**Run tests** from `Scripts/`:

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard/Scripts && python3.9 -m pytest ../tests -q
```

**Leaflet notes.** In a path style object, `opacity` is the *stroke* opacity and `fillOpacity` is
the fill; `fill: false` disables fill entirely. Panes are stacking contexts ordered by `zIndex`;
Leaflet's defaults that matter here are `overlayPane` 400 (where the zone polygons live),
`markerPane` 600 and `tooltipPane` 650. Existing custom panes: `flow-arcs` 450, `epi-links` 455,
`province-outline` 550.

## File structure

| File | Responsibility | Change |
|---|---|---|
| `Data/Branding/dashboard-theme.css` | brand token values | add `--zone-*` / `--province-*-mult` block; delete three now-unused province hover tokens |
| `Scripts/assets/engine.js` | all map behaviour | ramp + `zoneStroke()`, `SelectionRing`, derived selection, tier application, hover guards, province split, dead-code removal |
| `tests/test_zone_state_styling.py` | static guards | new: token/fallback parity, ramp arithmetic, literal containment, dead-code removal |

---

### Task 1: Add the token block to the theme layer

**Files:**
- Modify: `Data/Branding/dashboard-theme.css:29` (after `--province-outline-weight-wide-hover`)

- [ ] **Step 1: Read the current province block to find the insertion point**

Run: `sed -n '15,32p' Data/Branding/dashboard-theme.css`
Expected: the `--province-outline*` declarations, ending with `--province-outline-weight-wide-hover: 2;`

- [ ] **Step 2: Insert the token block immediately after that line**

```css
  /* ── Health-zone state styling ──────────────────────────────────────────
     One resting / hover / selected grammar for zone polygons, shared by every
     tab. See docs/superpowers/specs/2026-08-14-map-zone-state-styling-design.md.

     Every tier's weight is a MULTIPLIER on zoneWeight(zoom), never a fixed px.
     Fixed weights were the old bug: a 1.6px hub stroke or a 0.8px focus stroke
     renders thinner than the resting border at some zooms and thicker at
     others. Multipliers hold the hierarchy at every zoom.

     This whole layer is optional -- build_dashboard.py only appends it when
     non-empty -- so engine.js carries each value below as its themeVar()
     fallback, and tests/test_zone_state_styling.py fails the build if the two
     ever drift apart. */
  --zone-stroke: #fdfaf4;
  --zone-stroke-opacity: 0.7;
  --zone-stroke-weight-base: 1.7;
  /* ramp-min is both the z5 intercept and the clamp floor, deliberately: the
     map sets no minZoom, so below z5 the border simply stops thinning. */
  --zone-stroke-ramp-min: 0.6;
  --zone-stroke-ramp-max: 1.15;
  --zone-stroke-ramp-slope: 0.1;
  --zone-hover-stroke: #ffffff;
  --zone-hover-stroke-opacity: 0.98;
  --zone-hover-weight-mult: 1.7;
  --zone-selected-stroke: #ffae42;
  --zone-selected-stroke-opacity: 1;
  --zone-selected-weight-mult: 2.2;
  --zone-selected-casing: #5c3a12;
  --zone-selected-casing-opacity: 0.9;
  --zone-selected-casing-mult: 3.6;
  /* Fill-less zones: an off-white stroke over the CARTO light basemap is
     invisible, so these keep a warm grey. */
  --zone-nodata-stroke: #6b635a;
  --zone-nodata-stroke-opacity: 0.45;
  --zone-nodata-weight-mult: 1;
  --zone-hidden-weight-mult: 0.7;
  /* "Active zone with no count" is a should-never-happen state sitting on a
     solid mid-grey fill. It stays loud and stays black. */
  --zone-failloud-stroke: #111;
  --zone-failloud-stroke-opacity: 1;
  --zone-failloud-weight-mult: 1;
  --zone-focus-weight-mult: 1.35;
  /* Spatial risk dims non-focus zones by fill; without this their borders stay
     at full strength and a bright mesh fights the dimming. */
  --zone-dim-stroke-opacity: 0.25;
  --zone-role-stroke: #111;
  --zone-role-weight-mult-origin: 1.6;
  --zone-role-weight-mult-epicenter: 1.35;
  /* Provinces get their own multipliers: zone rings are zoom-scaled and
     province rings are not, so sharing multipliers would make which ring reads
     as "heavier" flip mid-zoom. */
  --province-hover-stroke: #ffffff;
  --province-hover-stroke-opacity: 0.98;
  --province-hover-weight-mult: 1.7;
  --province-selected-weight-mult: 2.2;
  --province-selected-casing-mult: 3.6;
```

- [ ] **Step 3: Delete the three province tokens that the new hover grammar replaces**

Remove these lines from the same file:

```css
  --province-outline-hover: #b23b2e;
  --province-outline-weight-hover: 1.5;
  --province-outline-weight-wide-hover: 2;
```

- [ ] **Step 4: Confirm nothing else references the deleted tokens**

Run: `grep -rn "province-outline-hover\|province-outline-weight-hover\|province-outline-weight-wide-hover" Data Scripts`
Expected: only `Scripts/assets/engine.js` hits (lines ~2131-2138), which Task 8 rewrites. No hits in any `.css`.

- [ ] **Step 5: Commit**

```bash
git add Data/Branding/dashboard-theme.css
git commit -m "Add zone state styling tokens to the theme layer"
```

---

### Task 2: Guard test for token/fallback parity and ramp arithmetic

The theme layer is optional, so the JS fallbacks *are* the specification. This test makes a
fallback that drifts from the CSS a test failure. Written before the JS that satisfies it.

**Files:**
- Create: `tests/test_zone_state_styling.py`

- [ ] **Step 1: Write the failing test**

```python
"""Static guards for the harmonised zone-state styling tokens.

The brand theme layer (Data/Branding/dashboard-theme.css) is optional -- 
build_dashboard.py appends it only when non-empty -- so engine.js must carry
every token's value as its themeVar() fallback. A fallback that drifts from the
CSS produces a dashboard that renders differently with and without branding,
silently. These tests make that drift a build failure.

See docs/superpowers/specs/2026-08-14-map-zone-state-styling-design.md.
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "Scripts" / "assets" / "engine.js"
THEME = REPO / "Data" / "Branding" / "dashboard-theme.css"

# themeVar("--token", "fallback") / zoneNum("--token", "fallback") -- both are
# token readers; zoneNum() is the numeric wrapper around themeVar(). Either
# quote style, since nothing in this repo enforces one. Groups: 1 and 3 are the
# quote characters (needed for the backreferences), so the token is group 2 and
# the fallback is group 4. A match's .start()/.end() spans the whole call.
THEMEVAR = re.compile(
    r"""(?:themeVar|zoneNum)\(\s*(["'])(--[a-z0-9-]+)\1\s*,\s*(["'])([^"']*)\3\s*\)"""
)
# --token: value;
CSS_DECL = re.compile(r'(--[a-z0-9-]+)\s*:\s*([^;]+);')

# Only the families this spec owns. Other theme tokens are consumed by CSS
# rules rather than by themeVar(), so they are out of scope here.
OWNED_PREFIXES = ("--zone-", "--province-")


def _engine_source():
    return ENGINE.read_text(encoding="utf-8")


def _css_tokens():
    text = THEME.read_text(encoding="utf-8")
    # A commented-out declaration must not look like a live one: last-match-wins
    # would otherwise let a stale "/* was --x: 1.5; */" shadow the real value, or
    # make a deleted token look defined -- a silent false pass in exactly the
    # drift these tests exist to catch.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return {m.group(1): m.group(2).strip() for m in CSS_DECL.finditer(text)}


def _owned_css_tokens():
    return {k: v for k, v in _css_tokens().items() if k.startswith(OWNED_PREFIXES)}


def _fallbacks():
    """token -> set of distinct fallback strings used in engine.js."""
    out = {}
    for m in THEMEVAR.finditer(_engine_source()):
        # Groups 1 and 3 are the quote characters; see THEMEVAR above.
        out.setdefault(m.group(2), set()).add(m.group(4).strip())
    return out


def _equivalent(a, b):
    """Compare as numbers when both parse as numbers, else case-insensitively.

    Lets the CSS say `0.1` where the JS fallback says `0.10` without a spurious
    failure, while still catching a genuine value change.
    """
    try:
        return abs(float(a) - float(b)) < 1e-9
    except ValueError:
        return a.strip().lower() == b.strip().lower()


def test_every_owned_css_token_is_read_by_engine():
    missing = sorted(set(_owned_css_tokens()) - set(_fallbacks()))
    assert not missing, f"tokens defined in the theme but never read by engine.js: {missing}"


def test_every_token_engine_reads_exists_in_css():
    css = _css_tokens()
    referenced = {t for t in _fallbacks() if t.startswith(OWNED_PREFIXES)}
    missing = sorted(referenced - set(css))
    assert not missing, f"engine.js reads tokens that the theme does not define: {missing}"


def test_fallbacks_match_the_css_values():
    css = _owned_css_tokens()
    problems = []
    for token, fallbacks in sorted(_fallbacks().items()):
        if token not in css:
            continue
        if len(fallbacks) > 1:
            problems.append(f"{token}: engine.js uses inconsistent fallbacks {sorted(fallbacks)}")
            continue
        (fallback,) = tuple(fallbacks)
        if not _equivalent(fallback, css[token]):
            problems.append(f"{token}: fallback {fallback!r} != css {css[token]!r}")
    assert not problems, "theme/fallback drift:\n" + "\n".join(problems)


def test_ramp_produces_the_documented_weights():
    """The ramp is the one number the whole visual system hangs off.

    A slope edit that silently changes the national view is exactly the kind of
    regression nobody notices in a local z9 screenshot.
    """
    css = _css_tokens()
    base = float(css["--zone-stroke-weight-base"])
    lo = float(css["--zone-stroke-ramp-min"])
    hi = float(css["--zone-stroke-ramp-max"])
    slope = float(css["--zone-stroke-ramp-slope"])

    def weight(zoom):
        return base * max(lo, min(hi, lo + (zoom - 5) * slope))

    assert round(weight(5), 2) == 1.02, "national z5 resting weight changed"
    assert round(weight(8), 2) == 1.53, "default-view z8 resting weight changed"
    assert round(weight(9), 2) == 1.70, "z9 resting weight changed"
    assert round(weight(12), 3) == 1.955, "ramp ceiling changed"
    assert weight(3) == weight(5), "ramp must not keep thinning below z5"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_zone_state_styling.py -q`
Expected: `test_every_owned_css_token_is_read_by_engine` FAILS listing every `--zone-*` token
(engine.js reads none of them yet). `test_ramp_produces_the_documented_weights` PASSES already,
since it only reads the CSS added in Task 1.

- [ ] **Step 3: Commit the test**

```bash
git add tests/test_zone_state_styling.py
git commit -m "Add failing guard test for zone token/fallback parity"
```

---

### Task 3: Weight ramp and `zoneStroke()` resolver

**Files:**
- Modify: `Scripts/assets/engine.js:583-591` (replace `zoomWeight`, add the new functions after it)

- [ ] **Step 1: Read the current `zoomWeight` to confirm the insertion point**

Run: `sed -n '583,596p' Scripts/assets/engine.js`
Expected: the `zoomWeight` comment and function, then `map.createPane("flow-arcs")`.

- [ ] **Step 2: Add the new ramp and resolver after `zoomWeight`**

**Leave `zoomWeight` in place.** Six call sites still use it until Task 6 migrates them; deleting
it here would leave the build broken between tasks. Task 6 removes it once nothing calls it.

Insert the following immediately after the closing brace of `zoomWeight`:

```js
// Zone borders read as hairlines at the national default zoom (many small
// zones packed together) and gain presence as you zoom into the outbreak.
// One ramp drives the resting stroke; every other state is a multiple of it,
// so the hierarchy (resting < focus < hover < selected) holds at every zoom.
//
// ramp-min is both the z5 intercept and the clamp floor on purpose: the map
// sets no minZoom, so below z5 the border stops thinning rather than vanishing.
function zoneWeight(zoom) {
  const base = zoneNum("--zone-stroke-weight-base", "1.7");
  const lo = zoneNum("--zone-stroke-ramp-min", "0.6");
  const hi = zoneNum("--zone-stroke-ramp-max", "1.15");
  const slope = zoneNum("--zone-stroke-ramp-slope", "0.1");
  return base * Math.max(lo, Math.min(hi, lo + (zoom - 5) * slope));
}

// themeVar() returns strings; this is the numeric read. The fallback is parsed
// too, so a malformed theme value degrades to the documented default rather
// than to NaN (a NaN weight silently drops the stroke entirely in Leaflet).
//
// Reads a token directly rather than taking a resolved value, so each token
// appears exactly once in the source with exactly one fallback literal.
// tests/test_zone_state_styling.py treats zoneNum() as a token reader alongside
// themeVar() for that reason -- do not inline themeVar() at the call sites.
function zoneNum(name, fallback) {
  const v = parseFloat(themeVar(name, fallback));
  return isFinite(v) ? v : parseFloat(fallback);
}

// Stroke half of a zone's style, by state. Weight is already resolved for the
// current zoom. Callers Object.assign() this onto the fill half, so nothing
// hardcodes a colour or a weight.
//
// "hidden"  -- zone not visible for the active spatial-risk layer
// "failloud" -- active zone with no count; should never happen, must stay loud
// "focus"   -- spatial-risk flow-connected neighbour of the selected zone
// "dim"     -- spatial-risk non-focus zone while something is selected
function zoneStroke(state) {
  const w = zoneWeight(map.getZoom());
  const rest = themeVar("--zone-stroke", "#fdfaf4");
  const restOp = zoneNum("--zone-stroke-opacity", "0.7");
  switch (state) {
    case "hover":
      return {
        color: themeVar("--zone-hover-stroke", "#ffffff"),
        opacity: zoneNum("--zone-hover-stroke-opacity", "0.98"),
        weight: w * zoneNum("--zone-hover-weight-mult", "1.7")
      };
    case "nodata":
      return {
        color: themeVar("--zone-nodata-stroke", "#6b635a"),
        opacity: zoneNum("--zone-nodata-stroke-opacity", "0.45"),
        weight: w * zoneNum("--zone-nodata-weight-mult", "1")
      };
    case "hidden":
      return {
        color: themeVar("--zone-nodata-stroke", "#6b635a"),
        opacity: zoneNum("--zone-nodata-stroke-opacity", "0.45"),
        weight: w * zoneNum("--zone-hidden-weight-mult", "0.7")
      };
    case "failloud":
      return {
        color: themeVar("--zone-failloud-stroke", "#111"),
        opacity: zoneNum("--zone-failloud-stroke-opacity", "1"),
        weight: w * zoneNum("--zone-failloud-weight-mult", "1")
      };
    case "focus":
      return {color: rest, opacity: restOp, weight: w * zoneNum("--zone-focus-weight-mult", "1.35")};
    case "dim":
      return {color: rest, opacity: zoneNum("--zone-dim-stroke-opacity", "0.25"), weight: w};
    case "epicenter":
      return {
        color: themeVar("--zone-role-stroke", "#111"),
        opacity: 1,
        weight: w * zoneNum("--zone-role-weight-mult-epicenter", "1.35")
      };
    case "origin":
      return {
        color: themeVar("--zone-role-stroke", "#111"),
        opacity: 1,
        weight: w * zoneNum("--zone-role-weight-mult-origin", "1.6")
      };
    default:   // "rest"
      return {color: rest, opacity: restOp, weight: w};
  }
}
```

- [ ] **Step 3: Run the guard test**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_zone_state_styling.py -q`
Expected: `test_every_owned_css_token_is_read_by_engine` still FAILS, now listing only the five
`--province-*` tokens plus `--zone-selected-*` (read in Tasks 4 and 8). The parity and ramp tests
PASS.

- [ ] **Step 4: Confirm the old ramp is still intact and still called**

Run: `grep -n "zoomWeight" Scripts/assets/engine.js`
Expected: the function definition plus its six call sites (`1324`, `1352`, `1355`, `1504`, `1520`,
`1527`). Both ramps coexist until Task 6.

- [ ] **Step 5: Build to confirm the file still parses**

Run: `python3.9 Scripts/build_dashboard.py`
Expected: exits 0. Serve and load the Snapshot tab — it must look exactly as it did before this
task, since nothing calls the new functions yet. Check the browser console for errors.

- [ ] **Step 6: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "Add zone weight ramp and zoneStroke resolver"
```

---

### Task 4: `SelectionRing` factory and the zone ring pane

**Files:**
- Modify: `Scripts/assets/engine.js:592-596` (after the `flow-arcs` / `epi-links` pane block)

- [ ] **Step 1: Read the existing pane block**

Run: `sed -n '592,600p' Scripts/assets/engine.js`
Expected: `map.createPane("flow-arcs")` … `const epiLinkLayer = L.layerGroup();`

- [ ] **Step 2: Add the factory and the zone ring instance after that block**

```js
// A selected zone's highlight is drawn OUTSIDE the polygon layer, in its own
// pane. Inside the polygon layer, every hover handler calls bringToFront() on
// the zone under the cursor, so a hovered neighbour's border paints over the
// selected zone's shared edge -- and no amount of re-fronting survives the next
// restyle. A higher pane makes the guarantee structural instead.
//
// The ring is two stacked paths because a single Leaflet path carries one
// stroke: a dark casing underneath, then the amber ring. The casing's visible
// part is the half that sticks out, (casingMult - innerMult) / 2 of the resting
// weight on each side.
function SelectionRing(paneName, zIndex, weights) {
  map.createPane(paneName);
  const pane = map.getPane(paneName);
  pane.style.zIndex = String(zIndex);
  // Clicks must reach the polygon underneath, or click-to-deselect dies the
  // moment a zone is selected.
  pane.style.pointerEvents = "none";
  const group = L.layerGroup().addTo(map);
  let current = [];

  function ring(features, color, opacity, weight) {
    return L.geoJSON({type: "FeatureCollection", features: features}, {
      pane: paneName,
      interactive: false,
      style: function () {
        return {color: color, opacity: opacity, weight: weight, fill: false};
      }
    });
  }

  function draw() {
    group.clearLayers();
    if (!current.length) return;
    // The caller resolves its own weights, so every token is read with literal
    // arguments at the call site. Passing token NAMES in here instead would
    // hide them from tests/test_zone_state_styling.py, whose regex only sees
    // literal zoneNum()/themeVar() calls -- the guard would silently stop
    // covering exactly the tokens that draw the selection.
    const w = weights();
    group.addLayer(ring(
      current,
      themeVar("--zone-selected-casing", "#5c3a12"),
      zoneNum("--zone-selected-casing-opacity", "0.9"),
      w.casing
    ));
    group.addLayer(ring(
      current,
      themeVar("--zone-selected-stroke", "#ffae42"),
      zoneNum("--zone-selected-stroke-opacity", "1"),
      w.inner
    ));
  }

  return {
    // Takes GeoJSON features, not keys: one factory serves both the zone (nom)
    // and province (province name) key spaces, and each caller already knows
    // how to resolve its own keys.
    set: function (features) { current = (features || []).filter(Boolean); draw(); },
    clear: function () { current = []; draw(); },
    redraw: draw
  };
}

// 445: above the zone polygons (overlayPane, 400), below the flow arcs (450)
// and epi-links (455). Selecting a zone on the spatial-risk tab is what draws
// its arcs, so a ring above them would occlude every arc terminus at the
// selected zone. Markers (600) and tooltips (650) still draw over the ring --
// requirement 4 is a guarantee against zones, not against everything.
const zoneRings = SelectionRing("zone-selection", 445, function () {
  const base = zoneWeight(map.getZoom());
  return {
    inner: base * zoneNum("--zone-selected-weight-mult", "2.2"),
    casing: base * zoneNum("--zone-selected-casing-mult", "3.6")
  };
});
```

- [ ] **Step 3: Build and confirm nothing broke**

Run: `python3.9 Scripts/build_dashboard.py`
Expected: exits 0. Serve and load `http://localhost:8765/index.html`; the map renders exactly as
before (the ring layer is empty until Task 5 feeds it). Check the browser console is free of
errors.

- [ ] **Step 4: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "Add SelectionRing factory and the zone-selection pane"
```

---

### Task 5: Derived selection accessor, wired at every mutation site

**Files:**
- Modify: `Scripts/assets/engine.js` — add the accessor after `featureByNom` (`198-206`); add calls
  at `212`, `1133`, `1138`, `1397`, `2525`, `2559`, `2802`, `2811`, `3060`, `3535`; add the
  backstop in `restyleZonesForActiveView` (`1857`) and `setActiveView`.

- [ ] **Step 1: Add the accessor and painter after `featureByNom`**

Insert immediately after the closing brace of `featureByNom` (line 206):

```js
// One derived read of "what is selected right now". The five per-view
// selection variables stay where they are -- merging them would touch every
// view's logic -- but only this function is allowed to answer the question, so
// the tabs cannot drift apart into five different selection treatments again.
function currentSelectedNoms() {
  if (activeView === "map") return mapSelectedNom ? [mapSelectedNom] : [];
  if (activeView === "epi-trends") return epiSelectedNom ? [epiSelectedNom] : [];
  if (activeView === "context") return contextSelectedNom ? [contextSelectedNom] : [];
  if (activeView === "genomic-epidemiology") return genomicHighlightNoms.slice();
  if (activeView === "trends") {
    // Province scope selects a province, not a zone; that ring is drawn by
    // applyProvinceOutlineStyles() into the province-selection pane.
    if (trendsScope === "health_zone" && trendsSelectedKey) return [trendsSelectedKey];
    return [];
  }
  return [];
}

function refreshZoneSelection() {
  zoneRings.set(currentSelectedNoms().map(featureByNom).filter(Boolean));
}
```

- [ ] **Step 2: Add `refreshZoneSelection()` at all nine mutation sites**

Add the call as the **last statement** of each function body listed below. Exact anchors:

| Function | Add after |
|---|---|
| `setMapSelection` | `renderMapInfoBox();` |
| `setEpiSelected` | `recomputeEpiTrends();` |
| `leaveEpiTrendsView` | `document.body.classList.remove("view-epi-trends", "epi-splitting");` |
| `setTrendsSelection` | the closing brace of the `if (opts.fromSearch) { … }` block |
| `setTrendsScope` | the closing brace of the `if (activeView === "trends") { … }` block |
| `clearContextSelection` | `renderContextPanel(null);` |
| `selectContextZone` | `renderContextPanel(nom);` |
| `leaveTrendsView` | the closing brace of the `if (savedMapLayerId) { … }` block |
| `genomicMapHooks.highlightZones` | the `genomeLayer.eachLayer(…)` call that toggles `genome-marker-sel` |

`setEpiSelected` needs only the one call at the end — it covers both branches.

- [ ] **Step 3: Add the backstop in `restyleZonesForActiveView`**

Replace the whole function at `1857-1878` with:

```js
// Re-apply zone borders (e.g. after a zoom, so the weight ramp picks up the new
// zoom). styleFn encodes every resting/tier style; selection lives in its own
// pane and is rebuilt here rather than re-fronted, which is what the old
// per-view bringToFront() blocks were doing.
function restyleZonesForActiveView() {
  geoLayer.setStyle(styleFn);
  refreshZoneSelection();
}
```

- [ ] **Step 4: Add the backstop in `setActiveView`**

In `setActiveView`, add `refreshZoneSelection();` immediately after the line `activeView = view;`.

This backstop covers zoom and tab switches. It does **not** make Step 2 redundant:
`clearContextSelection` and `selectContextZone` never trigger a restyle — they only call
`geoLayer.resetStyle(oneLayer)` — so without their explicit calls the Context tab would keep a
stale ring.

- [ ] **Step 5: Verify the call count**

Run: `grep -c "refreshZoneSelection()" Scripts/assets/engine.js`
Expected: `12` — one definition, nine mutation sites, two backstops.

- [ ] **Step 6: Build and verify selection now paints twice**

Run: `python3.9 Scripts/build_dashboard.py`, serve, open the Snapshot tab, click a zone.
Expected: the zone shows BOTH its old dark focus border (still coming from `styleFn`, removed in
Task 6) AND the new cased amber ring. Two highlights at once is the correct intermediate state.
Click it again — both clear.

- [ ] **Step 7: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "Paint zone selection through one derived accessor"
```

---

### Task 6: Move zone styling onto the tokens, strip selection from `styleFn`

This is the task that removes the five divergent selection treatments.

**Files:**
- Modify: `Scripts/assets/engine.js:1320-1374` (`epiTrendsStyleFn`), `1470-1531` (`styleFn`),
  `2983-2991` (`recomputeTrendsMap`), `2534-2545` (`setTrendsSelection`)
- Modify: `tests/test_zone_state_styling.py` (add the literal-containment guard)

- [ ] **Step 1: Add the failing literal-containment test**

Append to `tests/test_zone_state_styling.py`:

```python
def test_selection_colours_appear_only_as_theme_fallbacks():
    """The five tabs must not be able to hardcode their own selection colour.

    Scoped to occurrences rather than banned outright, because the token system
    itself requires themeVar("--zone-selected-stroke", "#ffae42") -- an outright
    ban would fail a correct implementation.
    """
    source = _engine_source()
    allowed = {(m.start(), m.end()) for m in THEMEVAR.finditer(source)}

    def inside_themevar(pos):
        return any(start <= pos < end for start, end in allowed)

    problems = []
    for literal in ("#ffae42", "#1a1a1a", "#9a7a16"):
        for m in re.finditer(re.escape(literal), source):
            if not inside_themevar(m.start()):
                line = source.count("\n", 0, m.start()) + 1
                problems.append(f"{literal} at engine.js:{line}")
    assert not problems, "hardcoded zone state colours:\n" + "\n".join(problems)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_zone_state_styling.py::test_selection_colours_appear_only_as_theme_fallbacks -q`
Expected: FAIL listing roughly ten locations — the three hover sites, the six selection sites, and
the prose mention in the comment at `1510`.

- [ ] **Step 3: Add the shared fill helper above `styleFn`**

Insert immediately before `function styleFn(feature) {` at line 1470:

```js
// Fill half of a zone's style. The stroke half comes from zoneStroke().
// `bump` is the selected/highlighted variant: it keeps the layer's fill (so the
// value stays readable under the ring) and lifts the opacity slightly. Both the
// snapshot and genomic branches used to carry their own copy of this.
function zoneFillStyle(v, has, ref, layer, bump) {
  if (!has) return {fillOpacity: 0};
  const isZero = currentDomain.isLog ? v <= 0 : v === 0;
  if (bump) {
    return {fillColor: valueToColor(v, ref, layer), fillOpacity: isZero ? 0.55 : 0.85};
  }
  const isOutbreak = layer && layer.palette === "outbreak";
  return {
    fillColor: valueToColor(v, ref, layer),
    fillOpacity: isZero ? (isOutbreak ? 0.48 : 0.55) : (isOutbreak ? 0.72 : 0.85)
  };
}
```

- [ ] **Step 4: Replace the body of `styleFn` (lines 1470-1531)**

```js
function styleFn(feature) {
  if (activeView === "epi-trends") return epiTrendsStyleFn(feature);
  const ref = feature.properties.nom;
  const v = currentValues.get(ref);
  const has = v != null && !Number.isNaN(v);
  const layer = getLayer(layerSelect.value);
  // Selected zones keep their choropleth fill and get an opacity bump; the ring
  // itself is drawn in the zone-selection pane, not here.
  const selected =
    (activeView === "genomic-epidemiology" && genomicHighlightNoms.indexOf(ref) !== -1) ||
    (activeView === "map" && ref === mapSelectedNom);
  // In Provincial scope, suppress ALL zone-level strokes so the province
  // outlines are the only line work. Fills are untouched.
  const prov = function (s) {
    if (activeView === "trends" && trendsScope === "province") s.weight = 0;
    return s;
  };
  if (isHubZone(ref, layer)) {
    return prov(Object.assign({}, zoneStroke("origin"), {
      fillColor: MATRIX_ORIGIN_FILL, fillOpacity: 0.92
    }));
  }
  if (isEpicenterZone(ref, layer)) {
    return prov(Object.assign({}, zoneStroke("epicenter"), {
      fillColor: EPICENTER_FILL, fillOpacity: 0.88
    }));
  }
  if (selected) {
    return prov(Object.assign({}, zoneStroke("rest"), zoneFillStyle(v, has, ref, layer, true)));
  }
  if (!has) {
    return prov(Object.assign({}, zoneStroke("nodata"), {fillOpacity: 0}));
  }
  return prov(Object.assign({}, zoneStroke("rest"), zoneFillStyle(v, has, ref, layer, false)));
}
```

- [ ] **Step 5: Replace the body of `epiTrendsStyleFn` (lines 1320-1374)**

```js
function epiTrendsStyleFn(feature) {
  const ref = feature.properties.nom;
  const row = INVASION_ZONES[ref];
  if (!row || !epiZoneVisible(row)) {
    return Object.assign({}, zoneStroke("hidden"), {fillColor: "#222", fillOpacity: 0.04});
  }
  let fill = ZERO_FILL;
  let has = false;
  if (row.was_active_before) {
    const z = ZONE_DATA[ref] || {};
    const v = z.effective_confirmed_cases;
    if (v != null && !Number.isNaN(Number(v))) {
      has = true;
      const num = Number(v);
      if (num <= 0) fill = NODATA_FILL;
      else {
        let t = (Math.log(num) - Math.log(epiCasesDomain.min)) /
          (Math.log(epiCasesDomain.max) - Math.log(epiCasesDomain.min) || 1);
        if (!isFinite(t)) t = 0;
        t = Math.max(0, Math.min(1, t));
        fill = rgb(lerpColor(epiCasesDomain.palette, t));
      }
    }
  } else if (row.p_case_invasion != null && !Number.isNaN(row.p_case_invasion)) {
    has = true;
    let t = (row.p_case_invasion - epiInvasionDomain.min) /
      (epiInvasionDomain.max - epiInvasionDomain.min || 1);
    if (!isFinite(t)) t = 0;
    t = Math.max(0, Math.min(1, t));
    fill = rgb(lerpColor(epiInvasionDomain.palette, t));
  }
  if (!has) {
    // Fail-loud: an active zone with no count. Sits on a solid mid-grey fill,
    // so it keeps a black stroke where every other state went off-white.
    return Object.assign({}, zoneStroke("failloud"), {fillColor: NODATA_FILL, fillOpacity: 0.55});
  }
  let fillOpacity = 0.82;
  let stroke = zoneStroke("rest");
  if (epiSelectedNom) {
    const focus = epiFocusNoms && epiFocusNoms.has(ref);
    if (ref === epiSelectedNom) {
      fillOpacity = 0.95;          // ring comes from the zone-selection pane
    } else if (focus) {
      fillOpacity = 0.78;
      stroke = zoneStroke("focus");
    } else {
      // Dimming is the focus signal: drop the stroke too, or a bright mesh of
      // full-strength borders reads straight through the dimmed fills.
      fillOpacity = 0.12;
      stroke = zoneStroke("dim");
    }
  }
  return Object.assign({}, stroke, {fillColor: fill, fillOpacity: fillOpacity});
}
```

- [ ] **Step 6: Delete the leftover selection re-paint blocks**

In `setTrendsSelection`, replace:

```js
  if (activeView === "trends") {
    // Restyle health-zone polygons to emphasize selection.
    geoLayer.setStyle(styleFn);
    if (trendsScope === "health_zone" && trendsSelectedKey) {
      geoLayer.eachLayer(function(layer) {
        if (layer.feature && layer.feature.properties.nom === trendsSelectedKey) {
          layer.setStyle({weight: 2, color: "#ffae42"});
          layer.bringToFront();
        }
      });
    }
  }
```

with:

```js
  if (activeView === "trends") geoLayer.setStyle(styleFn);
```

In `recomputeTrendsMap` (around `2983`), replace:

```js
  geoLayer.setStyle(styleFn);
  if (activeView === "trends" && trendsScope === "health_zone" && trendsSelectedKey) {
    geoLayer.eachLayer(function(layer) {
      if (layer.feature && layer.feature.properties.nom === trendsSelectedKey) {
        layer.setStyle({weight: 2, color: "#ffae42"});
        layer.bringToFront();
      }
    });
  }
```

with:

```js
  // No selection re-paint needed: the ring lives in its own pane and survives
  // this restyle untouched. This fires on every time-slider tick.
  geoLayer.setStyle(styleFn);
```

In `selectContextZone`, delete these two lines (the ring replaces them):

```js
  layer.setStyle({weight: 1.6, color: "#ffae42"});
  layer.bringToFront();
```

In `clearContextSelection`, delete the `geoLayer.resetStyle(contextSelectedLayer);` line and the
`contextSelectedLayer` guard around it, keeping `contextSelectedNom = null;` and
`renderContextPanel(null);`. In `selectContextZone`, delete the
`if (contextSelectedLayer && contextSelectedLayer !== layer) { geoLayer.resetStyle(contextSelectedLayer); }`
block and the `contextSelectedLayer = layer;` assignment.

In `genomicMapHooks.highlightZones`, delete the `geoLayer.eachLayer(...)` block that calls
`bringToFront()` on highlighted zones — the ring pane replaces it.

- [ ] **Step 7: Delete the old `zoomWeight` ramp, now that nothing calls it**

Run: `grep -n "zoomWeight" Scripts/assets/engine.js`
Expected: only the function definition — all six call sites were replaced by `zoneStroke()` in
Steps 4 and 5. Delete the function and its comment (lines `583-591`). If any call site remains,
migrate it before deleting.

- [ ] **Step 8: Check what still references `contextSelectedLayer`**

Run: `grep -n "contextSelectedLayer" Scripts/assets/engine.js`
Expected: only the `let contextSelectedLayer = null;` declaration at `2795` and the read inside
`clearSearchHighlight` at `1998`. **Leave both for now** — Task 9 deletes `clearSearchHighlight`
wholesale and removes the declaration with it. Deleting the declaration here would leave
`clearSearchHighlight` referencing an undeclared variable.

- [ ] **Step 9: Run the tests**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_zone_state_styling.py -q`
Expected: the literal-containment test now fails on **one** remaining hit — the prose `#ffae42` in
the comment at old line `1510` ("distinct from the amber (#ffae42) hover"), if that comment
survived your `styleFn` rewrite. Delete the stale comment; the behaviour it describes is gone.
Re-run: all tests PASS.

- [ ] **Step 10: Build and verify**

Run: `python3.9 Scripts/build_dashboard.py`, serve, then check every tab:
- Snapshot: borders are off-white; selecting a zone shows exactly ONE highlight (the cased amber
  ring), not the old dark border.
- Spatial risk: select a zone — focus neighbours have slightly heavier borders, non-focus zones
  are dimmed in both fill *and* stroke.
- Trends health zone: select a zone, drag the time slider — the ring stays put through every tick.
- Genomic: the coordinator's highlighted zones show the same amber ring, not gold.

- [ ] **Step 11: Commit**

```bash
git add Scripts/assets/engine.js tests/test_zone_state_styling.py
git commit -m "Style zones from tokens; move selection out of styleFn"
```

---

### Task 7: Hover suppression on selected zones — styling only

**Files:**
- Modify: `Scripts/assets/engine.js:1717-1791` (the `mouseover` / `mouseout` handlers)

The trap: these handlers do more than restyle. Snapshot binds the layer-value tooltip; Spatial risk
drives the floating readout. Suppressing the whole handler would take the tooltip and readout away
from the zone the user just clicked — a functional regression, not a styling change.

- [ ] **Step 1: Add the selection check at the top of `mouseover`**

Immediately after the `if (activeView === "genomic-epidemiology") return;` line inside `mouseover`,
insert:

```js
        // Requirement 3 is about STYLING only. A selected zone keeps its
        // tooltip, its floating readout and its province-hover behaviour --
        // it just does not repaint its border. Guard the setStyle/bringToFront
        // pairs below, never the whole handler.
        const isSelected = currentSelectedNoms().indexOf(feature.properties.nom) !== -1;
```

- [ ] **Step 2: Guard each `setStyle` / `bringToFront` pair**

In the `trends` branch, replace:

```js
          e.target.setStyle({weight: 1.6, color: "#ffae42"});
          e.target.bringToFront();
          return;
```

with:

```js
          if (!isSelected) {
            e.target.setStyle(zoneStroke("hover"));
            e.target.bringToFront();
          }
          return;
```

In the `epi-trends` branch, replace:

```js
          e.target.setStyle({weight: 1.6, color: "#ffae42"});
          e.target.bringToFront();
          updateEpiFloat(feature.properties.nom, e.latlng);
          return;
```

with:

```js
          if (!isSelected) {
            e.target.setStyle(zoneStroke("hover"));
            e.target.bringToFront();
          }
          updateEpiFloat(feature.properties.nom, e.latlng);   // fires for selected zones too
          return;
```

In the default (snapshot) branch at the end of `mouseover`, replace:

```js
        e.target.setStyle({weight: 1.6, color: "#ffae42"});
        e.target.bringToFront();
```

with:

```js
        if (!isSelected) {
          e.target.setStyle(zoneStroke("hover"));
          e.target.bringToFront();
        }
```

Leave the `bindTooltip(...).openTooltip(...)` line that follows it **outside** the guard.

- [ ] **Step 3: Add hover to the Context tab**

Replace the whole `if (activeView === "context") { return; }` block inside `mouseover` with:

```js
        if (activeView === "context") {
          if (!isSelected) {
            e.target.setStyle(zoneStroke("hover"));
            e.target.bringToFront();
          }
          return;
        }
```

And in `mouseout`, replace:

```js
        if (activeView === "context") {
          if (e.target !== contextSelectedLayer) {
            geoLayer.resetStyle(e.target);
          }
          return;
        }
```

with:

```js
        if (activeView === "context") {
          geoLayer.resetStyle(e.target);
          return;
        }
```

`resetStyle` on a selected zone is now harmless — its ring is in another pane, and `styleFn`
carries no selection stroke to lose.

- [ ] **Step 4: Fix the `mouseout` asymmetry in the trends branch**

Replace:

```js
          geoLayer.resetStyle(e.target);
          if (trendsScope === "health_zone" && trendsSelectedKey &&
              feature.properties.nom === trendsSelectedKey) {
            e.target.setStyle({weight: 2, color: "#ffae42"});
          }
          return;
```

with:

```js
          geoLayer.resetStyle(e.target);
          return;
```

Leave the `epi-trends` `mouseout` branch alone — `hideEpiFloat()` must keep firing for a selected
zone, or the float readout strands open after the cursor leaves.

- [ ] **Step 5: Build and verify the exact regression this task guards against**

Run: `python3.9 Scripts/build_dashboard.py`, serve, then:
- Snapshot: click a zone, then hover it. Its border must NOT change — and its layer-value tooltip
  MUST still appear.
- Spatial risk: click a zone, then hover it. Border unchanged; the floating readout must still
  appear, and must disappear when the cursor leaves.
- Snapshot: click a zone, then hover a **neighbouring** zone. The neighbour lifts to white; the
  selected zone's amber ring stays fully intact along the shared edge. This is requirement 4.
- Context: hover any zone — it lifts to white. Click it — ring appears, hover no longer changes it.

- [ ] **Step 6: Verify the ring survives a pan (the `tearDownHoverDecoration` edge case)**

`tearDownHoverDecoration()` runs on `movestart` to clear hover decoration that a pan would
otherwise strand. It must not touch the selection ring, which is not hover decoration and lives in
another pane.

Select a zone, then pan the map by dragging.
Expected: the hover lift on whatever was under the cursor clears, and the selected zone's ring is
untouched throughout the drag and after it settles.

- [ ] **Step 7: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "Suppress hover restyle on selected zones without losing tooltips"
```

---

### Task 8: Province outlines — split hover from selection

**Files:**
- Modify: `Scripts/assets/engine.js:2128-2165` (`provinceOutlineStyle`, `applyProvinceOutlineStyles`),
  `setTrendsProvinceHover` (~`2179`)

- [ ] **Step 1: Replace `provinceOutlineStyle` and add the base-weight helper**

Replace lines `2128-2144` with:

```js
function provinceBaseWeight() {
  const provinceMode = activeView === "trends" && trendsScope === "province";
  return provinceMode
    ? zoneNum("--province-outline-weight-wide", "1.4")
    : zoneNum("--province-outline-weight", "1");
}

// Provinces keep their gold resting colour -- that is what makes the province
// layer read as a different layer from the zones -- but adopt the same state
// grammar: hover is a white lift, selection is the cased amber ring drawn in
// the province-selection pane. A SELECTED province draws its RESTING outline;
// without that it would show a red base line under an amber ring.
function provinceOutlineStyle(state) {
  const provinceMode = activeView === "trends" && trendsScope === "province";
  if (state === "hover") {
    return {
      color: themeVar("--province-hover-stroke", "#ffffff"),
      opacity: zoneNum("--province-hover-stroke-opacity", "0.98"),
      weight: provinceBaseWeight() * zoneNum("--province-hover-weight-mult", "1.7"),
      fillOpacity: 0,
    };
  }
  return {
    color: themeVar("--province-outline", "#9b7d4e"),
    weight: provinceBaseWeight(),
    opacity: provinceMode ? 0.95 : 0.88,
    fillOpacity: 0,
  };
}
```

- [ ] **Step 2: Add the province ring instance after the province-outline pane**

The `provinceOutlineLayer` block sits at `2146-2154`. Insert after it:

```js
// 560: above the province outlines (550). Province rings are NOT zoom-scaled --
// they multiply the province resting weight, which is fixed.
const provinceRings = SelectionRing("province-selection", 560, function () {
  const base = provinceBaseWeight();
  return {
    inner: base * zoneNum("--province-selected-weight-mult", "2.2"),
    casing: base * zoneNum("--province-selected-casing-mult", "3.6")
  };
});

function provinceFeaturesFor(name) {
  if (!name) return [];
  const fc = PAYLOAD.province_boundaries || {features: []};
  return (fc.features || []).filter(function (f) {
    return f.properties && f.properties.province === name;
  });
}
```

- [ ] **Step 3: Replace `applyProvinceOutlineStyles`**

Replace lines `2156-2165` with:

```js
// Hover and selection were a single variable: whichever province was passed in
// got the red style, and hover was suppressed entirely once anything was
// selected. They are now distinct states -- hovering a non-selected province
// still lifts it while another is selected, and the selected one ignores hover.
function applyProvinceOutlineStyles(hoveredProvince) {
  trendsHoveredProvince = hoveredProvince || null;
  const selected = (activeView === "trends" && trendsScope === "province")
    ? trendsSelectedKey : null;
  provinceOutlineLayer.eachLayer(function (layer) {
    const name = layer.feature.properties.province;
    const isHover = !!trendsHoveredProvince && name === trendsHoveredProvince && name !== selected;
    layer.setStyle(provinceOutlineStyle(isHover ? "hover" : "rest"));
    if (isHover) layer.bringToFront();
  });
  provinceRings.set(provinceFeaturesFor(selected));
}
```

Note the removed `document.body.classList.toggle("trends-province-hovered", …)` line: that class
has no CSS consumer anywhere in the project. Confirm before deleting.

Run: `grep -rn "trends-province-hovered" Scripts Data`
Expected: no hits after the edit.

- [ ] **Step 4: Drop the hover suppression gate**

Replace `setTrendsProvinceHover` with:

```js
function setTrendsProvinceHover(province) {
  // No longer gated on "nothing selected": a selected province ignores hover,
  // but its neighbours still respond.
  if (activeView === "trends" && trendsScope === "province") {
    applyProvinceOutlineStyles(province || null);
  }
}
```

- [ ] **Step 5: Fix the one remaining caller that passed a selection**

In `setTrendsSelection`, the province branch currently calls
`applyProvinceOutlineStyles(trendsSelectedKey)` — it is now passing a *selection* into a *hover*
parameter. Change that call to `applyProvinceOutlineStyles(null)`; the function reads
`trendsSelectedKey` itself.

Run: `grep -n "applyProvinceOutlineStyles(" Scripts/assets/engine.js`
Expected: the definition plus calls that pass either `null` or a hovered province name — no call
passes `trendsSelectedKey`.

- [ ] **Step 6: Run the guard test**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_zone_state_styling.py -q`
Expected: ALL PASS — the `--province-*` tokens are now read, so
`test_every_owned_css_token_is_read_by_engine` finally goes green.

- [ ] **Step 7: Build and verify**

Run: `python3.9 Scripts/build_dashboard.py`, serve, open Trends → Provincial scope:
- Hover a province: white lift, no red anywhere.
- Click it: cased amber ring, and the base outline underneath is **gold**, not red.
- With it still selected, hover a different province: that one lifts; the selected one does not
  change.

- [ ] **Step 8: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "Split province hover from selection and adopt the shared grammar"
```

---

### Task 9: Delete the dead search-highlight machinery

`searchHighlightLayer` and `searchHighlightTimer` are never assigned a layer or a timer — the only
writes in the file are `= null`. They are leftovers from before zone search switched to persistent
focus (see the comment at `2068`). There is no search highlight state to harmonise; there is dead
code to remove.

**Files:**
- Modify: `Scripts/assets/engine.js:1980-1981`, `1993-2002`, `2062`
- Modify: `tests/test_zone_state_styling.py`

- [ ] **Step 1: Confirm the code really is dead before deleting it**

Run: `grep -n "searchHighlightLayer\|searchHighlightTimer" Scripts/assets/engine.js`
Expected: exactly the declarations at `1980-1981`, the body of `clearSearchHighlight` at
`1993-2002`, and nothing that assigns either a non-null value. If any assignment exists, STOP —
the mechanism is live and this task needs rethinking.

- [ ] **Step 2: Add the failing regression test**

Append to `tests/test_zone_state_styling.py`:

```python
def test_dead_search_highlight_machinery_is_gone():
    """Removed in the zone-state harmonisation: never assigned, never rendered.

    Guarded because the obvious "fix" for a future search-highlight request is
    to resurrect these, which would reintroduce a sixth zone state outside the
    shared grammar.
    """
    source = _engine_source()
    for name in ("searchHighlightLayer", "searchHighlightTimer", "clearSearchHighlight"):
        assert name not in source, f"{name} should have been deleted"
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_zone_state_styling.py::test_dead_search_highlight_machinery_is_gone -q`
Expected: FAIL — `searchHighlightLayer should have been deleted`.

- [ ] **Step 4: Delete the declarations**

Remove lines `1980-1981`:

```js
let searchHighlightLayer = null;
let searchHighlightTimer = null;
```

- [ ] **Step 5: Delete `clearSearchHighlight` entirely**

Remove the whole function (`1993-2002`):

```js
function clearSearchHighlight() {
  if (searchHighlightTimer) {
    clearTimeout(searchHighlightTimer);
    searchHighlightTimer = null;
  }
  if (searchHighlightLayer && searchHighlightLayer !== contextSelectedLayer) {
    geoLayer.resetStyle(searchHighlightLayer);
  }
  searchHighlightLayer = null;
}
```

- [ ] **Step 6: Delete its only call site**

In `selectHealthZone`, remove the `clearSearchHighlight();` line from the `activeView === "map"`
branch (around `2062`), and the now-stale comment line
`// No transient timer: the focus highlight is persistent via styleFn.`

- [ ] **Step 7: Run the tests**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_zone_state_styling.py -q`
Expected: ALL PASS.

- [ ] **Step 8: Build and verify search still works**

Run: `python3.9 Scripts/build_dashboard.py`, serve, then on the Snapshot tab type a zone name into
the zone search box and pick a result.
Expected: the map frames the zone and it becomes the selected zone, with the cased amber ring. On
the Context tab, the same search selects the zone and opens its panel.

- [ ] **Step 9: Commit**

```bash
git add Scripts/assets/engine.js tests/test_zone_state_styling.py
git commit -m "Remove dead search-highlight machinery"
```

---

### Task 10: Full verification pass

No code changes unless something here fails. Every item below maps to a spec requirement or to a
case that broke during design review.

**Files:** none (verification only)

- [ ] **Step 1: Run the whole test suite**

Run: `cd Scripts && python3.9 -m pytest ../tests -q`
Expected: all tests pass, including the pre-existing ones.

- [ ] **Step 2: Verify the dashboard renders identically with no theme layer**

This is the invariant the entire token system rests on — nothing else tests it end to end.

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard
mv Data/Branding/dashboard-theme.css /tmp/dashboard-theme.css.bak
python3.9 Scripts/build_dashboard.py
```

Serve and screenshot the Snapshot tab at the default view. Then:

```bash
mv /tmp/dashboard-theme.css.bak Data/Branding/dashboard-theme.css
python3.9 Scripts/build_dashboard.py
```

Serve and screenshot again. Expected: the two screenshots are visually identical in every zone
border, hover and selection colour. Any difference means a `themeVar()` fallback drifted from the
CSS — and the guard test in Task 2 should have caught it, so fix the test too.

- [ ] **Step 3: Walk all five tabs at three zooms**

At z5 (national), z8 (default) and z9, on Snapshot / Trends / Spatial risk / Context / Genomic:
borders are off-white and legible; no black hairline grid anywhere except role markers and the
fail-loud state.

- [ ] **Step 4: Requirement 4 — the case that started this**

On each tab that supports selection: select a zone, then hover an adjacent zone sharing a border.
Expected: the selected zone's ring is unbroken along the shared edge.

- [ ] **Step 5: Requirement 3 without the B1 regression**

Snapshot: hover the selected zone — border unchanged, tooltip still appears.
Spatial risk: hover the selected zone — border unchanged, float readout appears and then clears on
mouseout.

- [ ] **Step 6: Zoom and tab-switch persistence**

Select a zone, zoom in two levels: the ring rebuilds heavier and stays aligned. Switch to another
tab and back: the ring matches *that* tab's own selection, not the previous tab's.

- [ ] **Step 7: Trends time slider**

Trends → health zone scope, select a zone, drag the slider through its full range. The ring must
not flicker or disappear on any tick.

- [ ] **Step 8: Spatial-risk stacking and dimming**

Select a zone with flow arcs visible: arcs draw **over** the ring at their terminus. Then at
national zoom, confirm non-focus zones still read as dimmed — their borders must not form a bright
mesh over the faded fills.

- [ ] **Step 9: Genomic multi-zone**

Have the coordinator highlight an adjacent multi-zone set. Expected: the cluster reads as one
thicker keyline around its outer edge; interior shared edges carrying two casings is accepted
behaviour, not a bug.

- [ ] **Step 10: Palette contrast floor**

For each palette in `PALETTES` (OUTBREAK, REDS, RISK_ORANGES, PURPLES, PLASMA, VIRIDIS) plus
`ZERO_FILL` `#c4bfb6`, switch to a layer using it and confirm the off-white border is still
discernible at its palest stop. The mockups covered OUTBREAK only. If any palette fails badly,
raise it rather than silently bumping `--zone-stroke-opacity` — the light-end trade-off was
accepted deliberately and changing it is a design decision.

- [ ] **Step 11: National line-load comparison**

Load the built page at z5 side by side against the same page from `main`. The resting border is
~5.8× heavier by design; confirm the national view still reads as a choropleth rather than as a
mesh.

- [ ] **Step 12: Discard build artifacts and confirm a clean tree**

```bash
git checkout -- output assets
git status --short
```

Expected: no modifications outside `Scripts/assets/engine.js`, `Data/Branding/dashboard-theme.css`,
`tests/test_zone_state_styling.py` and the docs — all of which are already committed.

---

## Requirement traceability

| Requirement | Implemented by |
|---|---|
| 1 — off-white resting border | Tasks 1, 3, 6 |
| 2 — one selection treatment everywhere | Tasks 4, 5, 6, 8 + the literal-containment guard |
| 3 — selected zone ignores hover | Task 7 (styling only; tooltips and readouts preserved) |
| 4 — selection never overpainted | Task 4 (pane z-order), verified in Tasks 7 and 10 |
| Fallbacks are the real spec | Task 2 guard test, Task 10 Step 2 |
| Tier weights cannot invert | Tasks 1, 3, 6 (all tiers are ramp multipliers) |
| Dead code removal | Tasks 6, 8, 9 |
