# Snapshot page: selection-driven info box + reworked hover tooltips

**Date:** 2026-08-05
**Scope:** "Current Snapshot" tab only (`activeView === "map"`). No behavior change to Trends, Spatial Risk (except the shared case-tooltip layout), Context, or the other views.

## Motivation

On the snapshot page today:

- The **top-right info box** (`#info-body`) fills from the **hovered** zone (`mouseover` → `infoHTML`). It empties again on `mouseout`, so it never reflects a persistent choice.
- **Selection** only exists as the flow-arc origin (`flowHubNom`) and only works while the "show flow arrows" overlay is toggled on; otherwise a single click just zooms to the zone (`fitBounds`).
- The only **hover tooltip** is the active-case marker tooltip, and it only triggers on the small marker dot. Its layout crams name + `confirmed · suspected` + a combined (confirmed+suspected) deaths line.

We want hover to be a lightweight, layer-aware readout, and the info box to reflect a deliberate, persistent selection. Active-case markers stay (they are the only case signal when a non-case layer is selected).

## Goals

1. The info box shows the **selected** zone, not the hovered zone.
2. Selection is **decoupled from the flow-arrows toggle**: click any zone to select it. Remove click-to-zoom (both single- and double-click).
3. The active-case marker tooltip stays **marker-only** and is **cleaned up** to three labelled rows.
4. Hovering a zone polygon shows a **new, layer-aware tooltip** (the active layer's value for that zone).

Mobility-arrow behavior is otherwise unchanged.

## Design

### 1. Selection drives the info box

- Introduce a dedicated snapshot selection state, `mapSelectedNom` (independent of the flow-arrows toggle).
- **Single-click a zone** (polygon or its case marker) sets `mapSelectedNom`. Re-clicking the selected zone, or clicking empty map, clears it.
- While selected, `#info-body` renders `infoHTML(selectedFeature)` and drops the `info-empty` class. While nothing is selected, it shows the empty-state placeholder.
- The selected zone gets a persistent highlight in `styleFn` (border weight/color), so the choice is visible even when the arrows overlay is off. Hover highlight remains a separate, transient effect on top.
- **Placeholder copy** changes from *"Hover a health zone."* to **"Select a health zone."** (`ui.hover_zone`, EN + FR). The `info-empty` restore paths (`applyStaticI18n`, language switch) keep working since they key off the `info-empty` class, not hover.

**Interaction with mobility arrows (unchanged outward behavior):** the selected zone continues to act as the flow-arc origin. Setting `mapSelectedNom` also sets `flowHubNom`; clearing it clears the hub. Arcs still render only when `flowArcsOverlayActive()` is true (the overlay toggle is on) — so with the toggle off, selecting a zone fills the info box and highlights the zone but draws no arcs, exactly as "arrows behavior stays the same" requires.

### 2. Remove click-to-zoom

- Remove the single-click `fitBounds` fallback in the polygon `click` handler for `activeView === "map"`.
- Remove the custom `dblclick` → `fitBounds` zoom-to-zone for `activeView === "map"`. (Other views' dblclick behavior is untouched; Leaflet's own map double-click zoom is not our custom handler and is left as-is.)
- The map-background `click` handler clears the selection (replacing / extending the current "clear flow hub" behavior) for the snapshot view.

### 3. Active-case marker tooltip — marker-only, three rows

- Trigger is unchanged: bound to the marker dot only. **No polygon trigger** for this tooltip.
- New layout — zone name, then three labelled rows:
  1. **Suspected cases** — `c.suspected`
  2. **Confirmed cases** — `c.confirmed`
  3. **Confirmed deaths** — `c.confirmed_deaths` (drops the current combined confirmed+suspected `totalDeaths` line and the inline `·` layout)
- Implemented in the shared `caseMarkerTooltip(c)`, so **Spatial Risk markers get the same 3-row layout** (confirmed decision B).
- New i18n keys (EN + FR), e.g. under `ui.case_tooltip`: `suspected_cases`, `confirmed_cases`, `confirmed_deaths` (the existing `confirmed` / `suspected` / `deaths` fragments were lowercase inline pieces; the new rows want full labels). `ui.info.confirmed_deaths` already reads "confirmed deaths" and can be mirrored.

### 4. New layer-aware polygon hover tooltip

- On `mouseover` of a zone polygon in `activeView === "map"`, bind/show a Leaflet tooltip containing:
  - **Zone name** (bold), then
  - the active layer's label and this zone's value: `{layer.label}: {fmtLegend(v, layer.legend_round)}` where `v = currentValues.get(nom)`.
- **No data:** when `v` is null/NaN for the active layer, show the zone name + **"No data"** (confirmed decision A) rather than suppressing the tooltip.
- Tooltip content is recomputed on layer change and on hover (it depends on the active layer). The existing hover border highlight stays.
- This tooltip is **snapshot-only**. Spatial Risk keeps its own `updateEpiFloat` hover behavior; Trends/Context are unchanged.
- Where a case marker sits on top of its polygon, hovering the marker shows the case tooltip (marker is above the polygon in the pane order); hovering the polygon elsewhere shows the layer tooltip. Only one shows at a time.

## Affected code

- `Scripts/assets/engine.js`
  - `onEachFeature` `mouseover` / `mouseout` / `click` / `dblclick` handlers (~1611–1710): stop filling `#info-body` on hover; add layer-tooltip on hover; make click set/clear `mapSelectedNom`; remove click/dblclick zoom for map view.
  - map-background `click` handler (~1734): clear `mapSelectedNom` for map view.
  - `styleFn` (~1422): add selected-zone highlight branch for map view.
  - `caseMarkerTooltip` (~3192) and `refreshMarkerTooltips` (~3209): 3-row layout.
  - New selection state + a helper to render the info box / highlight from `mapSelectedNom`; wire arrow origin (`flowHubNom`) to follow it.
  - Layer-change path (`recompute` / `applyLayer`) refreshes the hover tooltip content and re-renders the selected zone's info box (it depends on the active layer via `infoHTML`).
- `Scripts/common/chrome.py` (~197): `#info-body` placeholder copy / i18n key if renamed.
- `locales/en.yaml`, `locales/fr.yaml`: placeholder copy; new `case_tooltip` row labels; layer-tooltip "No data" label.

## Edge cases

- **Deselect paths:** re-click selected zone, click its marker again, click empty map → info box returns to placeholder, highlight cleared, arcs cleared (if on).
- **Layer switch while a zone is selected:** info box re-renders with the new layer's `infoHTML`; hover tooltips reflect the new layer. Selection persists.
- **Language switch:** placeholder, tooltip labels, and the selected zone's info box all re-render in the new language.
- **Search-to-select:** out of scope for this change unless trivial to keep consistent; existing search-highlight behavior is left as-is (note for the plan phase to confirm it doesn't fight the new selection highlight).
- **Zones with no active cases:** no marker, so no case tooltip; the layer tooltip still shows on hover.

## Out of scope

- Any change to Spatial Risk, Trends, or Context selection/hover behavior, beyond the shared `caseMarkerTooltip` 3-row layout.
- Changing which layers exist or the default layer.
- Touching the "show cases" / "show flow arrows" toggles' semantics (arrows still gated by their toggle).

## Testing

- Manual/browser verification in the snapshot tab: hover shows layer tooltip (+ "No data" on a zone with no value for the current layer); marker hover shows the 3-row case tooltip; single-click selects and fills the info box (no zoom); double-click does not zoom; re-click / empty-map click deselects; layer switch updates both the info box and hover tooltip; language switch re-renders all copy; arrows still appear only with the overlay toggle on and follow the selected zone.
- Spatial Risk: confirm the case-marker tooltip now shows the 3-row layout and nothing else regressed there.
