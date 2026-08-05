# Snapshot selection-driven info box + reworked hover tooltips — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the "Current Snapshot" tab, make the top-right info box reflect a deliberately *selected* health zone (not the hovered one), add a lightweight layer-aware polygon hover tooltip, and rework the active-case marker tooltip into three clean rows.

**Architecture:** Unify "selected zone", "flow-arc origin", and "matrix travel origin" into one `mapSelectedNom` state ("the focused zone"). Clicking a zone focuses it; the focus drives the info box, the persistent highlight, and (where relevant) the flow/matrix role. Nothing is focused on load ("start empty"): no arcs, and matrix layers show an empty choropleth. Hover shows a per-zone, per-layer value tooltip. All changes are gated to `activeView === "map"`.

**Tech Stack:** Vanilla ES5-style JS over Leaflet 1.9 (`Scripts/assets/engine.js`), Python page builder (`Scripts/build_dashboard.py` + `Scripts/common/chrome.py`), YAML locales (`locales/{en,fr}.yaml`).

---

## Testing approach (read first)

This codebase has **no JavaScript test harness** — `tests/` holds only Python `pytest` for data helpers, and the UI is Leaflet/DOM behavior. We are **not** introducing a JS test framework (YAGNI; follows the existing pattern). Verification is **in-browser**, per task, via this loop:

**Fast inner loop (engine.js-only changes):**
```bash
# from repo root — regenerate the served copy of the engine without a full data build
cp Scripts/assets/engine.js output/assets/engine.js
# serve the already-built page (payload is inlined in output/index.html)
cd output && python3 -m http.server 8099   # leave running; open http://localhost:8099/index.html
```
Then reload the tab and check the behavior described in the task. `output/index.html` already exists (a prior build); the inlined payload is fine for UI testing.

**Full build (needed when you change `locales/*` or `chrome.py`, because those are baked into the HTML/payload):**
```bash
# needs the project Python env (numpy/pandas/shapely/pyyaml/python-docx) — see README "Environment setup".
# e.g. conda activate ebov2026
python Scripts/build_dashboard.py     # writes output/index.html + output/assets/*
```
If the build env is unavailable in this session, make the source edits, verify engine.js logic via the fast loop, and note in the commit that the authoritative full build runs in CI (`.github/workflows/build-dashboard.yml`). New i18n keys will render as raw keys in the fast loop until a full build.

**Browser checks** may be performed with the Claude-in-Chrome MCP tools (navigate to `http://localhost:8099/index.html`, use `computer`/`read_page`) or by the human. Each task lists the exact things to confirm.

Commit after each task.

---

## File structure

| File | Responsibility | Change |
|------|----------------|--------|
| `Scripts/assets/engine.js` | The shared JS engine; all snapshot interaction logic | Modify (bulk of the work) |
| `Scripts/common/chrome.py` | Page HTML template incl. the `#info-body` placeholder | Modify (1 line) |
| `locales/en.yaml`, `locales/fr.yaml` | UI strings | Modify (add/adjust keys) |

No new files.

---

## Task 1: i18n + placeholder copy

**Files:**
- Modify: `locales/en.yaml`
- Modify: `locales/fr.yaml`
- Modify: `Scripts/common/chrome.py:197`

- [ ] **Step 1: Add the new `ui.case_tooltip` row labels + hover/hint keys in `locales/en.yaml`.**

Find (en.yaml, ~215-219):
```yaml
  case_tooltip:
    confirmed: "confirmed"
    suspected: "suspected"
    deaths: "deaths"
    unnamed: "(unnamed)"
```
Replace with:
```yaml
  case_tooltip:
    confirmed: "confirmed"
    suspected: "suspected"
    deaths: "deaths"
    suspected_cases: "Suspected cases"
    confirmed_cases: "Confirmed cases"
    confirmed_deaths: "Confirmed deaths"
    unnamed: "(unnamed)"
```

- [ ] **Step 2: Add the layer-tooltip "no data" and matrix "select origin" hints in `locales/en.yaml`.**

Find (en.yaml:105):
```yaml
  hover_zone: "Hover a health zone."
```
Replace with:
```yaml
  hover_zone: "Select a health zone."
  layer_no_data: "No data"
  matrix_select_hint: "Select a health zone to show travel times."
```

- [ ] **Step 3: Mirror the row labels in `locales/fr.yaml`.**

Find (fr.yaml, ~215-219):
```yaml
  case_tooltip:
    confirmed: "confirmés"
    suspected: "suspectés"
    deaths: "décès"
    unnamed: "(sans nom)"
```
Replace with:
```yaml
  case_tooltip:
    confirmed: "confirmés"
    suspected: "suspectés"
    deaths: "décès"
    suspected_cases: "Cas suspectés"
    confirmed_cases: "Cas confirmés"
    confirmed_deaths: "Décès confirmés"
    unnamed: "(sans nom)"
```

- [ ] **Step 4: Mirror the hover/hint keys in `locales/fr.yaml`.**

Find (fr.yaml:105):
```yaml
  hover_zone: "Survolez une zone de santé."
```
Replace with:
```yaml
  hover_zone: "Sélectionnez une zone de santé."
  layer_no_data: "Aucune donnée"
  matrix_select_hint: "Sélectionnez une zone de santé pour afficher les temps de trajet."
```

- [ ] **Step 5: Update the pre-JS placeholder in `chrome.py`.**

Find (`Scripts/common/chrome.py:197`):
```html
  <div id="info-body" class="info-empty" data-i18n="ui.hover_zone">Hover a health zone.</div>
```
Replace with:
```html
  <div id="info-body" class="info-empty" data-i18n="ui.hover_zone">Select a health zone.</div>
```

- [ ] **Step 6: Full build and verify the placeholder copy.**

Run: `python Scripts/build_dashboard.py` (project env). Expected: prints `wrote .../index.html`. If the env is unavailable, skip the build and note it; the `data-i18n` key still resolves at runtime after CI builds.
Browser: load the snapshot page; the empty top-right box reads **"Select a health zone."** (EN) / **"Sélectionnez une zone de santé."** (FR via the language switch).

- [ ] **Step 7: Commit.**
```bash
git add locales/en.yaml locales/fr.yaml Scripts/common/chrome.py
git commit -m "Snapshot: selection-oriented info-box copy + case-tooltip row labels"
```

---

## Task 2: Rework the active-case marker tooltip into three rows

**Files:**
- Modify: `Scripts/assets/engine.js:3192-3200` (`caseMarkerTooltip`)

- [ ] **Step 1: Replace `caseMarkerTooltip` with the three-row layout.**

Find (engine.js:3192-3200):
```javascript
function caseMarkerTooltip(c) {
  const totalDeaths = (c.confirmed_deaths || 0) + (c.suspected_deaths || 0);
  return (
    "<strong>" + (c.name || t("ui.case_tooltip.unnamed")) + "</strong><br/>" +
    t("ui.case_tooltip.confirmed") + ": " + c.confirmed + "  ·  " +
    t("ui.case_tooltip.suspected") + ": " + c.suspected +
    (totalDeaths > 0 ? "<br/>" + t("ui.case_tooltip.deaths") + ": " + totalDeaths : "")
  );
}
```
Replace with:
```javascript
function caseMarkerTooltip(c) {
  const row = function(label, val) {
    return "<div class='case-tt-row'><span>" + label + "</span><span>" + fmt(Number(val) || 0) + "</span></div>";
  };
  return (
    "<strong>" + (c.name || t("ui.case_tooltip.unnamed")) + "</strong>" +
    row(t("ui.case_tooltip.suspected_cases"), c.suspected) +
    row(t("ui.case_tooltip.confirmed_cases"), c.confirmed) +
    row(t("ui.case_tooltip.confirmed_deaths"), c.confirmed_deaths)
  );
}
```

Note: `fmt` (engine.js:1465) already renders integers with thousands separators and `—` for null. `suspected_deaths` is intentionally no longer shown (the old combined `deaths` figure included it; the new "Confirmed deaths" row shows `confirmed_deaths` only — an accuracy improvement, not a removed field).

- [ ] **Step 2: (Optional) add minimal styling for the rows.** In `Scripts/assets/dashboard.css`, add near the case-icon styles:
```css
.case-tt-row { display:flex; justify-content:space-between; gap:12px; }
.case-tt-row span:last-child { font-variant-numeric: tabular-nums; }
```
If you skip this, the rows still render (flex just makes label/value align); include it for the clean look the spec asks for.

- [ ] **Step 3: Verify in the browser (fast loop).**

Run: `cp Scripts/assets/engine.js output/assets/engine.js` (and CSS if edited: the CSS is inlined at build time, so for the fast loop also `cp Scripts/assets/dashboard.css output/assets/dashboard.css`). Reload.
Confirm: hovering a case marker (a red dot on a confirmed-case zone) shows the zone name and three rows — Suspected cases / Confirmed cases / Confirmed deaths — and nothing else. (New i18n labels appear as raw keys until a full build; verify the three-row structure and values now, and the labels after Task 8's build.)

- [ ] **Step 4: Commit.**
```bash
git add Scripts/assets/engine.js Scripts/assets/dashboard.css
git commit -m "Snapshot: three-row active-case marker tooltip"
```

---

## Task 3: Focused-zone state, info box, and selection highlight

**Files:**
- Modify: `Scripts/assets/engine.js` (add state + helpers near the other map globals; `styleFn`; init nulls)

- [ ] **Step 1: Initialize the focus/role state to null on load.**

Find (engine.js:15):
```javascript
let flowHubNom = PAYLOAD.flow_default_hub || "Mongbwalu";
```
Replace with:
```javascript
let flowHubNom = null;              // set only via the focused zone (setMapSelection)
```

Find (engine.js:11):
```javascript
let matrixOriginNom = PAYLOAD.matrix_default_origin || "Mongbwalu";
```
Replace with:
```javascript
let matrixOriginNom = null;         // set only via the focused zone (setMapSelection)
```

Find (engine.js:16):
```javascript
let flowHubUserSelected = !!(PAYLOAD.flow_arcs_available && FLOW_ARC_LAYER);
```
Replace with:
```javascript
let flowHubUserSelected = false;
let mapSelectedNom = null;          // the single "focused zone" for the snapshot view
```

**Cross-page safety note:** `engine.js` is shared across all pages. This null-init is safe for Spatial Risk: `enterEpiTrendsView` sets `flowHubNom = PAYLOAD.flow_default_hub || flowHubNom` on view entry (engine.js:1340) and `setEpiSelected` sets it directly, so epi-trends never depends on the old Mongbwalu init. `matrixOriginNom` is read only by matrix layers, which appear only in the snapshot layer dropdown.

- [ ] **Step 2: Add focus helpers.** Insert immediately after `setFlowHub` (after engine.js:195, the line `}` closing `setFlowHub`):
```javascript
function featureByNom(nom) {
  if (!nom) return null;
  const feats = (PAYLOAD.geometry && PAYLOAD.geometry.features) || [];
  for (let i = 0; i < feats.length; i++) {
    if (feats[i].properties && feats[i].properties.nom === nom) return feats[i];
  }
  return null;
}

// The snapshot view's single focused zone. Drives the info box, the persistent
// highlight, and — where the active layer cares — the flow-arc origin and the
// matrix travel origin. Passing the already-focused nom (or null) clears focus.
function setMapSelection(nom) {
  const next = (nom && nom === mapSelectedNom) ? null : (nom || null);
  mapSelectedNom = next;
  flowHubNom = next;
  flowHubUserSelected = !!next;
  matrixOriginNom = next;
  applyMatrixOriginToLayers();
  rebuildLayerSelect();
  recompute();
  syncMatrixUi();
  renderMapInfoBox();
}

function renderMapInfoBox() {
  const el = document.getElementById("info-body");
  if (!el) return;
  const feat = featureByNom(mapSelectedNom);
  if (!feat) {
    el.className = "info-empty";
    el.textContent = t("ui.hover_zone");   // "Select a health zone."
    return;
  }
  el.className = "";
  el.innerHTML = infoHTML(feat);
}
```

- [ ] **Step 3: Add the persistent focus highlight to `styleFn`.**

Find (engine.js:1435-1441), the epicenter branch, and insert a focus branch *before* it so a focused non-hub zone is highlighted. Find:
```javascript
  if (isEpicenterZone(ref, layer)) {
    return {
      color: "#111", weight: zoomWeight(0.5),
      fillColor: EPICENTER_FILL,
      fillOpacity: 0.88
    };
  }
```
Replace with:
```javascript
  if (isEpicenterZone(ref, layer)) {
    return {
      color: "#111", weight: zoomWeight(0.5),
      fillColor: EPICENTER_FILL,
      fillOpacity: 0.88
    };
  }
  if (activeView === "map" && ref === mapSelectedNom) {
    // Focus highlight: a heavy dark border, distinct from the amber (#ffae42)
    // hover. Keep whatever fill the layer would give (matrix origin still reads
    // as MATRIX_ORIGIN_FILL via isHubZone, handled above), so the border is the
    // focus signal and the fill still conveys the layer value/role.
    const base = has ? {
      fillColor: valueToColor(v, ref, layer),
      fillOpacity: (currentDomain.isLog ? v <= 0 : v === 0) ? 0.55 : 0.85
    } : { fillOpacity: 0 };
    return Object.assign({ color: "#1a1a1a", weight: 2.4 }, base);
  }
```

**Precedence note:** this branch sits *after* `isHubZone` (engine.js:1428). On matrix layers that set `origin_highlight`, the focused zone is the origin and `isHubZone` returns first, so it keeps the `MATRIX_ORIGIN_FILL` (blue) treatment rather than the dark focus border. That is acceptable per spec D4 ("keep the origin fill; the fill still conveys the role") — the origin is still visibly distinct. On all other layers the focus border applies.

- [ ] **Step 4: Remove the load-time Mongbwalu pre-fill so the box starts empty.** An IIFE currently pre-populates the info box with Mongbwalu on load (which would defeat "start empty"). Delete it.

Find (engine.js:3680-3689):
```javascript
// Pre-populate the zone info panel with Mongbwalu.
(function preloadMongbwalu() {
  for (const feat of PAYLOAD.geometry.features) {
    if ((feat.properties.nom || "").toLowerCase() === "mongbalu") {
      document.getElementById("info-body").className = "";
      document.getElementById("info-body").innerHTML = infoHTML(feat);
      return;
    }
  }
})();
```
Replace with:
```javascript
// The snapshot info box starts empty (placeholder) until a zone is focused.
// (The #info-body element keeps its `info-empty` class from chrome.py, and
// applyStaticI18n in initDashboardI18n fills it with the placeholder string.)
```
With `preloadMongbwalu` gone, `mapSelectedNom` is null and the box shows the placeholder on load — no extra call needed.

- [ ] **Step 5: Verify (fast loop).** `cp Scripts/assets/engine.js output/assets/engine.js`, reload.
Confirm: on load the info box shows the placeholder and no flow arcs are drawn (previously arcs drew from Mongbwalu). Nothing is highlighted. (Clicking does not yet select — that is Task 4.) In the console, run `setMapSelection('Bunia')` (use a real nom from the map) and confirm the info box fills, the zone gets a dark heavy border, and (with the flow toggle on) arcs draw from it; run `setMapSelection('Bunia')` again and confirm it clears.

- [ ] **Step 6: Commit.**
```bash
git add Scripts/assets/engine.js
git commit -m "Snapshot: focused-zone state, selection-driven info box, focus highlight"
```

---

## Task 4: Rewire clicks/search to focus; remove click-to-zoom

**Files:**
- Modify: `Scripts/assets/engine.js` — polygon `click`/`dblclick` (~1687-1710), map-background `click` (~1734-1741), `handleCaseMarkerClick` (~3237-3247), search-select (~1867-1874)

- [ ] **Step 1: Replace the map-view polygon `click` branch.**

Find (engine.js:1687-1702):
```javascript
        const layer = getLayer(layerSelect.value);
        if (activeView === "map" && flowArcsOverlayActive()) {
          L.DomEvent.stop(e);
          // Re-clicking the current flow origin clears it (arcs disappear);
          // empty-map click clears too -- see the map "click" handler below.
          const nom = feature.properties.nom;
          setFlowHub(nom === flowHubNom ? null : nom);
          return;
        }
        if (activeView === "map" && layerUsesMatrix(layer)) {
          L.DomEvent.stop(e);
          setMatrixOrigin(feature.properties.nom);
          return;
        }
        map.fitBounds(e.target.getBounds(), {padding:[40,40]});
      },
```
Replace with:
```javascript
        if (activeView === "map") {
          L.DomEvent.stop(e);
          // One "focused zone" for the snapshot view: click to focus, click the
          // focused zone again to clear. Focus drives the info box, the flow-arc
          // origin, and the matrix travel origin. No click-to-zoom.
          setMapSelection(feature.properties.nom);
          return;
        }
      },
```

- [ ] **Step 2: Remove the map-view `dblclick` zoom.**

Find (engine.js:1703-1710):
```javascript
      dblclick: function(e) {
        if (activeView === "context") return;
        if (activeView === "trends" && trendsScope === "national") {
          return;
        }
        L.DomEvent.stop(e);
        map.fitBounds(e.target.getBounds(), {padding:[40,40]});
      }
```
Replace with:
```javascript
      dblclick: function(e) {
        if (activeView === "context") return;
        if (activeView === "map") return;   // no zoom-to-zone on the snapshot view
        if (activeView === "trends" && trendsScope === "national") {
          return;
        }
        L.DomEvent.stop(e);
        map.fitBounds(e.target.getBounds(), {padding:[40,40]});
      }
```

- [ ] **Step 3: Update the map-background `click` to clear focus.**

Find (engine.js:1734-1741):
```javascript
map.on("click", function() {
  if (activeView === "context") clearContextSelection();
  if (activeView === "epi-trends") setEpiSelected(null);
  // Snapshot: clearing the flow origin (arcs off) is its deselect. Only while
  // arcs are the active overlay -- matrix layers keep their origin, and their
  // arcs are already suppressed so flowArcsOverlayActive() is false there.
  if (activeView === "map" && flowArcsOverlayActive()) setFlowHub(null);
});
```
Replace with:
```javascript
map.on("click", function() {
  if (activeView === "context") clearContextSelection();
  if (activeView === "epi-trends") setEpiSelected(null);
  // Snapshot: clicking empty map clears the focused zone (info box → placeholder,
  // highlight cleared, arcs cleared, matrix choropleth goes empty).
  if (activeView === "map") setMapSelection(null);
});
```

- [ ] **Step 4: Route case-marker clicks through focus.**

Find (engine.js:3237-3247):
```javascript
  if (activeView === "map") {
    if (flowArcsOverlayActive()) {
      setFlowHub(nom === flowHubNom ? null : nom);
      return true;
    }
    // Matrix layers need an origin, so no toggle-to-null here.
    if (layerUsesMatrix(getLayer(layerSelect.value))) {
      setMatrixOrigin(nom);
      return true;
    }
  }
  return false;
```
Replace with:
```javascript
  if (activeView === "map") {
    setMapSelection(nom);
    return true;
  }
  return false;
```

- [ ] **Step 5: Route search-select through focus (keep its zoom-to-frame).**

Find (engine.js:1867-1882):
```javascript
  } else if (activeView === "map") {
    clearSearchHighlight();
    if (flowArcsOverlayActive()) {
      setFlowHub(nom);
    } else if (layerUsesMatrix(getLayer(layerSelect.value))) {
      setMatrixOrigin(nom);
    }
    map.fitBounds(layer.getBounds(), {padding: [40, 40], maxZoom: 10});
    layer.setStyle({weight: 1.6, color: "#ffae42"});
    layer.bringToFront();
    searchHighlightLayer = layer;
    const infoBody = document.getElementById("info-body");
    if (infoBody) {
      infoBody.className = "";
      infoBody.innerHTML = infoHTML(feature);
    }
```
Replace with:
```javascript
  } else if (activeView === "map") {
    clearSearchHighlight();
    // Searching focuses the zone (persistent highlight + info box come from the
    // focus state itself, not a transient overlay). Keep the zoom-to-frame: a
    // searched zone may be offscreen, unlike an already-visible clicked one.
    setMapSelection(nom);
    map.fitBounds(layer.getBounds(), {padding: [40, 40], maxZoom: 10});
```
Then find the trailing transient-highlight timer that followed the old block (engine.js:1883-1889):
```javascript
    searchHighlightTimer = setTimeout(function() {
      if (searchHighlightLayer === layer && layer !== contextSelectedLayer) {
        geoLayer.resetStyle(layer);
      }
      searchHighlightLayer = null;
      searchHighlightTimer = null;
    }, 2500);
```
Replace with:
```javascript
    // No transient timer: the focus highlight is persistent via styleFn.
```
Leave the `context` branch above untouched. (`searchHighlightLayer`/`clearSearchHighlight` remain used by the context view; do not delete them.)

- [ ] **Step 6: Verify (fast loop).** `cp Scripts/assets/engine.js output/assets/engine.js`, reload.
Confirm on the snapshot tab: single-click a zone → info box fills, dark border appears, no zoom; click it again → clears; click a different zone → focus moves; click empty ocean/map → clears; double-click a zone → no zoom; click a case marker → focuses its zone; type in the search box and pick a result → that zone is focused (persistent border, info box filled) and the map frames it. With the flow toggle on, arcs follow the focused zone; toggle off → no arcs but focus/info persist.

- [ ] **Step 7: Commit.**
```bash
git add Scripts/assets/engine.js
git commit -m "Snapshot: click/search focus a zone; remove click-to-zoom"
```

---

## Task 5: Hover — remove info-box fill, add layer-aware tooltip, preserve focus

**Files:**
- Modify: `Scripts/assets/engine.js` — add `layerHoverTooltipHTML`; map-view `mouseover`/`mouseout` (~1629-1654)

- [ ] **Step 1: Add the hover-tooltip content builder.** Insert right after `infoHTML` (after engine.js:1607, the `}` closing `infoHTML`):
```javascript
// Lightweight per-zone readout for the snapshot hover tooltip: the active
// layer's label and this zone's value (matrix layers → travel time/distance
// from the focused origin). "No data" when the layer has no value here.
function layerHoverTooltipHTML(feature) {
  const ref = feature.properties.nom;
  const name = feature.properties.name || t("ui.case_tooltip.unnamed");
  const layer = getLayer(layerSelect.value);
  const v = currentValues.get(ref);
  const has = v != null && !Number.isNaN(v);
  const body = has
    ? (layer ? layer.label + ": " : "") + fmtLegend(v, layer && layer.legend_round != null ? layer.legend_round : "int")
    : t("ui.layer_no_data");
  return "<strong>" + name + "</strong><br/>" + body;
}
```

- [ ] **Step 2: Rewrite the map-view `mouseover` tail (stop filling the info box; show the tooltip).**

Find (engine.js:1629-1632), the final `mouseover` block (the one reached for the map view, after the trends/context/epi-trends early returns):
```javascript
        e.target.setStyle({weight: 1.6, color: "#ffae42"});
        e.target.bringToFront();
        document.getElementById("info-body").className = "";
        document.getElementById("info-body").innerHTML = infoHTML(feature);
      },
```
Replace with:
```javascript
        e.target.setStyle({weight: 1.6, color: "#ffae42"});
        e.target.bringToFront();
        // Hover no longer fills the info box (that follows the focused zone).
        // Show a lightweight, layer-aware tooltip instead.
        e.target.bindTooltip(layerHoverTooltipHTML(feature), {sticky: true, direction: "top"}).openTooltip(e.latlng);
      },
```

- [ ] **Step 3: Preserve the focus highlight on `mouseout` for the map view.**

Find (engine.js:1653-1654), the final `mouseout` fallthrough for the map view:
```javascript
        geoLayer.resetStyle(e.target);
      },
```
Replace with:
```javascript
        if (e.target.getTooltip()) e.target.unbindTooltip();
        geoLayer.resetStyle(e.target);
        // resetStyle re-applies styleFn, which already paints the focus border
        // for the focused zone, so leaving a focused zone keeps its highlight.
      },
```

Note: `styleFn` (Task 3, Step 3) re-paints the focus border on `resetStyle`, so no extra work is needed to keep the selected zone highlighted after hovering it. The amber hover only overrides while the pointer is on the zone.

- [ ] **Step 4: Verify (fast loop).** `cp Scripts/assets/engine.js output/assets/engine.js`, reload.
Confirm: hovering any zone shows a small tooltip with the zone name and the active layer's value (e.g. on the default confirmed-cases layer, "…: 42"); hovering a zone with no value for the layer shows "No data" (raw key `ui.layer_no_data` until full build); the info box does NOT change on hover; hovering the currently-focused zone still leaves its dark border after you move away. Switch layers (e.g. Population) and confirm the tooltip value updates accordingly.

- [ ] **Step 5: Commit.**
```bash
git add Scripts/assets/engine.js
git commit -m "Snapshot: layer-aware hover tooltip; hover no longer fills info box"
```

---

## Task 6: Matrix null-origin empty state + hint; zoom restyle keeps focus

**Files:**
- Modify: `Scripts/assets/engine.js` — `matrixOriginDisplayName` (~119-121), `updateLayerMeta` (~1476-1481), `zoomend` restyle (~1719-1732)

- [ ] **Step 1: Make the matrix origin display name null-aware.**

Find (engine.js:119-121):
```javascript
function matrixOriginDisplayName() {
  return hubDisplayName(matrixOriginNom);
}
```
Replace with:
```javascript
function matrixOriginDisplayName() {
  return matrixOriginNom ? hubDisplayName(matrixOriginNom) : "—";
}
```

- [ ] **Step 2: Show the select-a-zone hint in the layer meta when a matrix layer has no origin.**

Find (engine.js:1478-1481):
```javascript
  if (layerUsesMatrix(layer)) {
    const originLine = tf("ui.matrix_origin", {origin: matrixOriginDisplayName()});
    html = (html ? html + "<br>" : "") + originLine;
  }
```
Replace with:
```javascript
  if (layerUsesMatrix(layer)) {
    const originLine = matrixOriginNom
      ? tf("ui.matrix_origin", {origin: matrixOriginDisplayName()})
      : t("ui.matrix_select_hint");
    html = (html ? html + "<br>" : "") + originLine;
  }
```

- [ ] **Step 3: Keep the focus highlight after a zoom.** `styleFn` already encodes the focus border, and the map-view `zoomend` handler re-applies `styleFn` wholesale (engine.js:1719-1720 `geoLayer.setStyle(styleFn)`), so the focus survives zoom automatically. No code change needed — **verify only** (Step 4). (Do not add a map-view branch to the `zoomend` special-cases; those are for trends/context whose highlights live outside `styleFn`.)

- [ ] **Step 4: Verify (fast loop + full build for the hint string).** `cp Scripts/assets/engine.js output/assets/engine.js`, reload.
Confirm: with nothing focused, switch the layer dropdown to a travel/matrix layer (e.g. "Travel time…") → the map shows an **empty choropleth** (no zone fills) and the layer-meta line reads the select hint (raw key `ui.matrix_select_hint` until full build); click a zone → it becomes the origin and the choropleth fills with travel times from it, and the layer-meta shows "Travel origin: <zone>"; hovering other zones shows their travel time in the hover tooltip; zoom in/out → the focused zone keeps its dark border. Click empty map → choropleth empties again.

- [ ] **Step 5: Commit.**
```bash
git add Scripts/assets/engine.js
git commit -m "Snapshot: matrix layers allow no origin (empty choropleth + hint)"
```

---

## Task 7: Re-render the focused zone on language switch

**Files:**
- Modify: `Scripts/assets/engine.js` — `setLang` map-view branch (~461-472)

- [ ] **Step 1: Replace the hardcoded-Mongbwalu re-render with a focus-driven one.**

Find (engine.js:461-472), the `else` branch of `setLang`:
```javascript
  } else {
    const infoBody = document.getElementById("info-body");
    if (infoBody && !infoBody.classList.contains("info-empty")) {
      for (const feat of PAYLOAD.geometry.features) {
        if ((feat.properties.name || "").toLowerCase() === (TRAVEL_FROM || "Mongbwalu").toLowerCase() ||
            (feat.properties.nom || "").toLowerCase() === "mongbalu") {
          infoBody.innerHTML = infoHTML(feat);
          break;
        }
      }
    }
  }
```
Replace with:
```javascript
  } else {
    // Map view: re-render the focused zone's info box (or the placeholder) in
    // the new language. applyStaticI18n early-returns for a non-empty info box,
    // so this is the path that keeps a selected zone localized.
    renderMapInfoBox();
  }
```

- [ ] **Step 2: Verify (fast loop).** `cp Scripts/assets/engine.js output/assets/engine.js`, reload.
Confirm: focus a zone (info box filled) → switch language → the info box re-renders in the new language for that same zone; with nothing focused, switching language shows the placeholder in the new language. The hover tooltip and marker tooltip also read in the new language (via `refreshMarkerTooltips`, already called in `setLang`).

- [ ] **Step 3: Commit.**
```bash
git add Scripts/assets/engine.js
git commit -m "Snapshot: localize the focused zone's info box on language switch"
```

---

## Task 8: Full build + comprehensive verification

**Files:** none (build + verify)

- [ ] **Step 1: Full build.** With the project env active:
```bash
python Scripts/build_dashboard.py
```
Expected: `wrote .../output/index.html`, `.../spatial-risk.html`, etc., no traceback. (If the env is unavailable in this session, state that the authoritative build is CI-run and that all string keys were added in Task 1; skip to Step 2 using the fast-loop copies.)

- [ ] **Step 2: Serve and run the full snapshot checklist.**
```bash
cd output && python3 -m http.server 8099
```
Open `http://localhost:8099/index.html` and confirm, in order:
  1. **Load:** info box shows "Select a health zone."; no flow arcs.
  2. **Hover:** any zone → tooltip with the zone name + active layer label and value; a no-value zone → "No data".
  3. **Marker hover:** a case-marker dot → three rows (Suspected cases / Confirmed cases / Confirmed deaths), correct values, no other text.
  4. **Select:** single-click a zone → info box fills with that zone; dark focus border; no zoom. Double-click → no zoom.
  5. **Deselect:** re-click the focused zone, or click empty map → placeholder returns, border gone.
  6. **Arrows:** with "show flow arrows" on and a zone focused → arcs originate from it; toggle off → arcs gone, focus/info persist; nothing focused → no arcs regardless of toggle.
  7. **Matrix layer:** switch to a travel layer with nothing focused → empty choropleth + select hint; click a zone → fills from that origin; hover reads travel times; click empty map → empties.
  8. **Search:** search a zone, pick it → focused (persistent border + info box), map frames it.
  9. **Language:** focus a zone, switch FR/EN → info box, hover tooltip, and marker tooltip all localize; placeholder localizes when nothing focused.

- [ ] **Step 3: Regression check on Spatial Risk.** Open `http://localhost:8099/spatial-risk.html`; confirm the case-marker tooltip now shows the three-row layout and the tab's own hover/selection behavior is unchanged.

- [ ] **Step 4: Final commit (only if the full build changed `output/` and `output/` is tracked).**
```bash
git status --short          # check whether output/ is tracked or gitignored
# If output/ is tracked and you intend to commit built artifacts:
git add -A && git commit -m "Snapshot: rebuild dashboard with selection/hover changes"
# If output/ is gitignored (CI builds it), skip — the source commits from Tasks 1–7 are the deliverable.
```

---

## Self-review notes (author)

- **Spec coverage:** §1 info box → Tasks 3,4,7; §2 remove zoom + focus model → Tasks 3,4; §3 marker tooltip → Task 2; §4 hover tooltip → Task 5; M1 matrix empty state → Tasks 3(step1),4,6; M2 start empty → Task 3(step1 null-init + step4 removing `preloadMongbwalu`); D2 language switch → Task 7; D3 search → Task 4(step5); D4 highlight distinct/precedence → Task 3(step3) + Task 5(step3); D1 (framing) → spec only; copy/i18n → Task 1.
- **Type/name consistency:** `mapSelectedNom`, `setMapSelection`, `renderMapInfoBox`, `featureByNom`, `layerHoverTooltipHTML` are defined once (Task 3 / Task 5) and referenced consistently thereafter. `setFlowHub`/`setMatrixOrigin` are left defined but no longer called from map-view paths (still referenced by epi-trends internals, which set `flowHubNom` directly).
- **No-JS-test caveat** is stated up front; verification is browser-based by design.
