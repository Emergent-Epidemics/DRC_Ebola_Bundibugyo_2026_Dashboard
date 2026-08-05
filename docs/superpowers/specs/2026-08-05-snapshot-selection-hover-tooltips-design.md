# Snapshot page: selection-driven info box + reworked hover tooltips

**Date:** 2026-08-05
**Scope:** "Current Snapshot" tab only (`activeView === "map"`). No behavior change to Trends, Spatial Risk (except the shared case-tooltip layout), Context, or the other views.

**Revision note:** revised after the review in `docs/superpowers/reviews/2026-08-05-snapshot-selection-hover-tooltips-design-review.md`. Key changes: a unified "focused zone" model that reconciles selection with the flow-hub and matrix-origin roles (M1); "start empty" on load — no selection, no arcs, empty matrix choropleth (M2); search routes through selection (D3); corrected the current-behavior framing (D1) and the language-switch claim (D2).

## Motivation

On the snapshot page today:

- The **top-right info box** (`#info-body`) fills from the **hovered** zone (`mouseover` → `infoHTML`, engine.js:1631-1632). `mouseout` only resets the polygon style (1654) — it never touches the info box, and the `info-empty` class is only ever removed, never re-added. So the box is **sticky last-hover**: after the first hover it shows that zone until another hover replaces it. It never reflects a deliberate, persistent choice.
- **Selection** exists only as a layer-specific role: the flow-arc origin (`flowHubNom`) on flow overlays, or the travel origin (`matrixOriginNom`) on matrix layers. On a plain choropleth a single click just zooms to the zone (`fitBounds`).
- The only **hover tooltip** is the active-case marker tooltip; it triggers on the small marker dot only, and crams name + `confirmed · suspected` + a combined (confirmed+suspected) deaths line.

We want hover to be a lightweight, layer-aware readout, and the info box to reflect a deliberate selection that clears on deselect. Active-case markers stay (they are the only case signal when a non-case layer is selected).

## Goals

1. The info box shows the **selected** zone, and clears when nothing is selected.
2. Selection is unified into a single **focused-zone** concept and decoupled from the flow-arrows toggle: click any zone to focus it; click it again or click empty map to clear. Remove click-to-zoom (single- and double-click).
3. The active-case marker tooltip stays **marker-only** and is reworked to three labelled rows.
4. Hovering a zone polygon shows a **new, layer-aware tooltip** (the active layer's value for that zone).

## Core concept: the focused zone

Unify "selected zone", "flow-arc origin", and "matrix (travel) origin" into a single state, `mapSelectedNom` (snapshot view only). Exactly one zone is focused at a time, or none.

- **Focusing a zone** (click / marker click / search) sets `mapSelectedNom` and, as a consequence, the layer-appropriate role:
  - flow overlay active → it is the flow-arc origin (`flowHubNom` follows `mapSelectedNom`).
  - matrix layer active → it is the travel origin (`matrixOriginNom` follows `mapSelectedNom`).
  - plain choropleth → no extra role; just selected.
- **No zone focused** is a first-class state (the load state — see M2):
  - info box shows the placeholder;
  - no flow arcs render (even with the toggle on);
  - a matrix layer renders an **empty choropleth** (no origin ⇒ no values ⇒ all zones drawn as no-data), with a legend/hint prompting the user to select a zone.
- The new hover tooltip (§4) makes this safe on matrix layers: `currentValues.get(nom)` on a travel layer *is* the travel-time/road-distance from the origin, so hovering any zone reads its value directly — the info box no longer needs to fill on hover to inspect other zones.

## Design

### 1. Selection drives the info box

- **Single-click a zone** (polygon or its case marker) focuses it. Re-clicking the focused zone, or clicking empty map, clears the focus.
- While focused, `#info-body` renders `infoHTML(focusedFeature)` and drops the `info-empty` class. While nothing is focused, it shows the placeholder and the `info-empty` class is **re-added** (new: today nothing re-adds it).
- The focused zone gets a persistent highlight in `styleFn` (see D4), visible regardless of overlay/toggle state.
- **Placeholder copy** changes from *"Hover a health zone."* to **"Select a health zone."** (`ui.hover_zone`, EN + FR).

### 2. Focus vs. layer roles, and removing click-to-zoom

The current map-view click handler (engine.js:1688-1701), the marker-click router `handleCaseMarkerClick` (3223-3249), and the search-select path (1867-1889) all branch three ways: `flowArcsOverlayActive → setFlowHub`, `layerUsesMatrix → setMatrixOrigin`, else `fitBounds`. All three are rewritten to the unified model:

- Any zone click → **focus that zone** (toggling off if it is already focused). Focus then propagates to `flowHubNom` (flow overlay) or `matrixOriginNom` (matrix layer) as above.
- Remove the single-click `fitBounds` fallback and the custom `dblclick` → `fitBounds` zoom-to-zone for `activeView === "map"`. (Leaflet's built-in map double-click zoom is not our handler and is left as-is; other views' dblclick untouched.)
- The map-background `click` handler clears the focus for the snapshot view.

### M1 detail — matrix (travel) layers allow no origin

- `setMatrixOrigin` currently refuses null (`if (!nom || nom === matrixOriginNom) return`, 179-181). It must accept null so the origin can be cleared.
- With no origin, a matrix layer produces no `currentValues`; `styleFn`'s no-data branch (1442-1443) already draws such zones transparent, so the map shows an **empty choropleth**. Verify the domain/legend build (`recompute`, ~1359-1399; `updateLegend`) tolerates an all-empty value set without NaN artifacts; if not, add an explicit empty-state guard.
- The legend / layer-meta for a matrix layer with no origin shows a hint (e.g. "Select a health zone to show travel times") instead of a bogus `matrixOriginDisplayName()` (which today falls back to Mongbwalu even when unset). New/adjusted i18n key.
- `matrixOriginNom` initial value becomes null (M2), not the Mongbwalu default.

### M2 detail — start empty on load

- On load: `mapSelectedNom = null`, `flowHubNom = null`, `matrixOriginNom = null`. Info box shows the placeholder; no arcs render even though the flow toggle defaults on; the default layer is `obs::confirmed` (a plain choropleth, unaffected by origin).
- This is a deliberate change from today, where arcs render from the default Mongbwalu hub on load. Documented and intended: arcs now represent the focused zone's mobility, so "nothing focused" ⇒ "no arcs". The flow toggle still gates arcs (toggle off ⇒ no arcs regardless of focus).

### D3 detail — search routes through focus

- The map-view search-select handler (1867-1889) calls the same focus logic (sets `mapSelectedNom`) instead of `setFlowHub`/`setMatrixOrigin` directly, so a searched zone becomes genuinely focused: persistent highlight (not the transient 2500ms `#ffae42`), info box filled from the real focus state.
- Search **keeps** its `fitBounds` zoom-to-frame (1874): searching a possibly-offscreen zone is a navigation action, unlike clicking an already-visible one. This intentional divergence from the removed click-zoom is noted (addresses review N3).

### 3. Active-case marker tooltip — marker-only, three rows

- Trigger unchanged: bound to the marker dot only. No polygon trigger for this tooltip.
- New layout — zone name, then three labelled rows:
  1. **Suspected cases** — `c.suspected`
  2. **Confirmed cases** — `c.confirmed`
  3. **Confirmed deaths** — `c.confirmed_deaths`
- **Consequence to note (review D5):** the current deaths line is `confirmed_deaths + suspected_deaths` (3193). The new layout shows confirmed deaths only, so **suspected deaths is removed from the marker tooltip UI** (snapshot and, via the shared function, Spatial Risk). This is the intended per the requested three-row layout.
- Implemented in the shared `caseMarkerTooltip(c)`, so **Spatial Risk markers get the same 3-row layout** (confirmed decision B).
- i18n: reuse `ui.info.confirmed_deaths` (already "confirmed deaths" in EN+FR, en/fr:225) rather than adding near-duplicates; add full-label `ui.case_tooltip.suspected_cases` / `confirmed_cases` as needed (the existing `case_tooltip.confirmed/suspected/deaths` are lowercase inline fragments — reword deliberately, don't parallel-duplicate).

### 4. New layer-aware polygon hover tooltip

- On `mouseover` of a zone polygon in `activeView === "map"`, show a Leaflet tooltip with the **zone name** (bold) and the active layer's label + this zone's value: `{layer.label}: {fmtLegend(v, layer.legend_round)}`, where `v = currentValues.get(nom)`.
- **No data** (`v` null/NaN — including matrix layers with no origin): show zone name + **"No data"** (confirmed decision A), not a suppressed tooltip.
- Content depends on the active layer, so refresh it on layer change and on hover. Existing hover border highlight stays.
- Snapshot-only. Spatial Risk keeps `updateEpiFloat`; Trends/Context unchanged.
- The case marker sits above its polygon in the pane order, so hovering the marker shows the case tooltip and hovering the polygon elsewhere shows the layer tooltip — one at a time. Same holds for genome markers (review N4): they only appear when the genomes toggle is on, and Leaflet shows whichever layer is under the cursor.

### D4 detail — selection highlight vs. existing highlights

- The focus highlight must be **visually distinct from the `#ffae42` hover** (1629) so selected ≠ hovered (unlike trends/context, which reuse `#ffae42`). Choose a distinct persistent treatment (e.g. heavier border in a different hue) in the plan phase with a quick visual check.
- **Precedence** when the focused zone is also the flow origin or matrix origin (which set their own fill/weight via `isHubZone`/`MATRIX_ORIGIN_FILL`, 1428-1441): define which wins. Recommended: keep the origin fill (it conveys the role) and add the focus border on top.
- Because hover paints over the focus border on the focused zone, special-case `mouseout`/hover to preserve the focus treatment on the focused zone (mirroring the trends `mouseout` special-case at 1637-1640), so hovering the selected zone doesn't visually "unselect" it.

## Affected code

- `Scripts/assets/engine.js`
  - `onEachFeature` `mouseover`/`mouseout`/`click`/`dblclick` (~1611-1710): stop filling `#info-body` on hover; add the layer hover tooltip; click focuses/clears; remove click/dblclick zoom for map view; preserve focus highlight under hover.
  - map-background `click` (~1734): clear focus for map view.
  - `handleCaseMarkerClick` (~3223-3249): route to the same focus logic (including its matrix branch).
  - search-select (~1867-1889): route through focus; keep `fitBounds`; drop the transient highlight in favor of the persistent focus highlight.
  - `styleFn` (~1422): focus-highlight branch + precedence vs hub/epicenter/matrix-origin.
  - `setMatrixOrigin` (~179): accept null; empty-choropleth handling in `recompute`/`updateLegend`/`updateLayerMeta`.
  - `setFlowHub` / focus helper: `flowHubNom` and `matrixOriginNom` follow `mapSelectedNom`; nulls on load.
  - `caseMarkerTooltip` (~3192) + `refreshMarkerTooltips` (~3209): 3-row layout.
  - Init (~15, 11): `flowHubNom`/`matrixOriginNom` start null; the info box + selected-zone refresh on layer change and on **language switch** (new — `applyStaticI18n` early-returns for a non-empty box (205) and the only other refresh re-renders a hardcoded Mongbwalu zone (462-471), so re-rendering the *focused* zone in the new language is new wiring).
- `Scripts/common/chrome.py` (~197): `#info-body` placeholder copy / key.
- `locales/en.yaml`, `locales/fr.yaml`: placeholder copy; `case_tooltip` row labels; layer-tooltip "No data"; matrix "select a zone" hint.

## Edge cases

- **Deselect paths:** re-click focused zone, click its marker again, or click empty map → info box returns to placeholder (`info-empty` re-added), focus highlight cleared, arcs cleared; on a matrix layer the choropleth goes empty (no origin).
- **Layer switch while focused:** info box re-renders with the new layer's `infoHTML`; hover tooltips reflect the new layer; matrix layers recolor from the focused origin. Focus persists across layer switches.
- **Switch to a matrix layer with nothing focused:** empty choropleth + select-a-zone hint.
- **Language switch:** placeholder, tooltip labels, matrix hint, and the *focused* zone's info box all re-render in the new language (requires the new refresh wiring above).
- **Zones with no active cases:** no marker ⇒ no case tooltip; the layer tooltip still shows on hover.

## Out of scope

- Any change to Spatial Risk, Trends, or Context selection/hover behavior, beyond the shared `caseMarkerTooltip` 3-row layout.
- Which layers exist or the default layer.
- The "show cases" / "show flow arcs" toggle semantics (arrows still gated by their toggle, now additionally requiring a focused zone).

## Testing

- Snapshot tab (browser): load shows empty info box and no arcs; hover shows the layer tooltip (+ "No data" where a zone has no value); marker hover shows the 3-row case tooltip; single-click focuses and fills the info box (no zoom); double-click does not zoom; re-click / empty-map click clears focus (info box → placeholder); switch to a travel layer with nothing focused shows an empty choropleth + hint, and clicking a zone populates it from that origin; layer switch updates info box + hover tooltip; language switch re-renders all copy including the focused zone; arrows appear only with the toggle on AND a focused zone, and originate from it; search focuses a zone (persistent highlight, framed by `fitBounds`).
- Spatial Risk: case-marker tooltip shows the 3-row layout; nothing else regressed.
