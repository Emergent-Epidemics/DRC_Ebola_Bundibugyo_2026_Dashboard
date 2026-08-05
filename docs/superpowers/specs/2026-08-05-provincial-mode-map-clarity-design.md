# Provincial-mode map clarity + clean province outlines

**Date:** 2026-08-05
**Branch:** `provincial-mode-map-clarity` (off `main`)
**Status:** Design approved, pending spec review

## Problem

On the Epidemiological Trends tab, when the **Provincial** scope is active, the
outbreak map does not communicate that *provinces* are the selectable unit:

1. **Zone borders and hover dominate.** Every health-zone polygon still draws its
   own resting border and still highlights on hover, so the map reads as a field
   of selectable zones rather than selectable provinces. The province outlines
   (drawn on top) do not stand out enough against this.

2. **Residual internal borders on province outlines.** The dissolved province
   polygons carry sliver holes — thousands of them (~6,145 interior rings across
   26 provinces; e.g. Kongo-Central alone has 715). Each hole is stroked, so a
   selected province shows a red outer border *plus* a mess of internal lines.
   Root cause: `unary_union` of the source health-zone polygons leaves tiny
   gaps/slivers wherever adjacent zone edges do not exactly coincide, and those
   slivers survive as interior rings.

## Goals

- In Provincial scope, provinces read unambiguously as the selectable unit.
- A selected province shows a clean red outline with no internal border artifacts.

## Non-goals / scope guards

- No change to `national` or `health_zone` scopes, nor to the snapshot (`map`) or
  `epi-trends` views.
- Zone **fills** in Provincial scope stay as-is — the per-zone choropleth
  (confirmed-cases gradient) is data, not chrome, and remains visible.
- Legacy `Scripts/build_dashboard_public.py` is not touched (it is superseded by
  `Scripts/build_dashboard.py`; see its own header note).

## Design

### 1. Hide health-zone borders in Provincial scope — `Scripts/assets/engine.js`

In `styleFn`, when `activeView === "trends" && trendsScope === "province"`,
suppress the per-zone stroke (`weight: 0`). Keep `fillColor` / `fillOpacity`
exactly as computed. The province outlines live in the separate
`province-outline` map pane (drawn on top), so with zone strokes gone they become
the only line work on the map. Adjacent zones with different fill values still
show a colour boundary — that is the choropleth data, not a drawn border, and is
acceptable.

The `mouseout` and `zoomend` re-style paths already route through `styleFn` /
`geoLayer.resetStyle`, so they inherit the suppressed stroke automatically — no
separate handling needed.

### 2. Hover highlights the parent province — `Scripts/assets/engine.js`

The `geoLayer` `mouseover` / `mouseout` handlers currently paint the hovered
*zone* amber (`#ffae42`) whenever `trendsScope !== "national"`. For the
`trendsScope === "province"` case specifically:

- `mouseover`: call `setTrendsProvinceHover(feature.properties.province)` instead
  of styling the zone. Do not `bringToFront` the zone.
- `mouseout`: call `setTrendsProvinceHover(null)` instead of the amber reset.

This reuses the existing province-outline highlight path
(`setTrendsProvinceHover` → `applyProvinceOutlineStyles` → `provinceOutlineStyle`),
so hovering anywhere over a province highlights that whole province's outline —
matching click, which selects the province.

The existing gate inside `setTrendsProvinceHover` is preserved: hover-highlight
applies only while no province is selected yet
(`trendsScope === "province" && !trendsSelectedKey`). Once a province is
selected, hover gives no feedback, as today. Click-to-select behaviour is
unchanged.

The `health_zone` scope keeps its current amber zone hover — only the `province`
branch changes.

### 3. Clean province outlines — `Scripts/common/data_sources.py`

In `build_province_boundaries()`, eliminate the sliver holes, before the existing
`simplify` / coordinate-round steps:

1. **Snap** each source zone geometry to a small coordinate grid
   (`shapely.set_precision`) so shared edges between adjacent zones coincide
   exactly. This removes most slivers at the source of the union.
2. **Union** as today (`unary_union`).
3. **Drop sliver holes.** Strip interior rings whose area is below a threshold
   from each Polygon / MultiPolygon part, via a small helper that rebuilds each
   polygon keeping only its exterior ring plus interior rings at or above the
   threshold. The threshold is set well above sliver size and well below any
   plausible real hole. DRC provinces have no legitimate donut holes, so this is
   safe; keeping a threshold rather than stripping every interior ring is a
   deliberate safety net.

Then the payload is rebuilt so `trends.html` (and the other pages) pick up the
cleaned geometry.

**Grid size / threshold** are tunable constants chosen during implementation and
validated against the success criterion below (start conservative, confirm the
interior-ring count collapses without eroding the exterior outline).

## Success criteria

- Provincial scope: no dark per-zone borders on the map; province outlines are the
  only line work; zone choropleth fills still render.
- Provincial scope: hovering the map highlights the parent province's outline;
  clicking selects the province (unchanged).
- Interior-ring (hole) count across all province boundary features drops to ~0
  (verified by re-running the geometry check used during diagnosis), and each
  province's exterior outline is visually unchanged from before.
- A selected province shows a clean red outline with no internal lines.
- `national` / `health_zone` scopes and the `map` / `epi-trends` views are
  visually and behaviourally unchanged.

## Files touched

- `Scripts/assets/engine.js` — `styleFn` (zone-border suppression), `geoLayer`
  `mouseover` / `mouseout` (province-hover wiring).
- `Scripts/common/data_sources.py` — `build_province_boundaries()` (snap + union +
  drop-slivers) plus a small strip-small-holes helper.
- Rebuild of `output/` + served `assets/` and the inlined payload in the HTML
  pages (build artifact).
