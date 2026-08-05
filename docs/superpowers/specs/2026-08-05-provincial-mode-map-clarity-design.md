# Provincial-mode map clarity + clean province outlines

**Date:** 2026-08-05
**Branch:** `provincial-mode-map-clarity` (off `main`)
**Status:** Design approved; critical-review points §§1–13 incorporated across four
review passes (original §§1–6; second-look §7 + §2b retraction; third-read §8–§10;
final §11 detached sliver parts / §12 grid-size bracket / §13 square-degree units).
See `…-design-review.md`. Ready to plan.

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

- No **behavioural** change to `national` or `health_zone` scopes, nor to the
  snapshot (`map`) or `epi-trends` views. One deliberate *visual* side effect: the
  province outline layer renders in national and health_zone scopes too
  (`setTrendsScope` at `engine.js:2378` calls `showProvinceOutlines()` at `2385`
  for every trends scope), drawing from the same `province_boundaries` geometry.
  Cleaning
  that geometry (§3) removes the internal sliver lines in those scopes as well —
  an intended improvement, not pixel-identity. Do not expect a "no visual diff"
  result there.
- Zone **fills** of data zones in Provincial scope stay as-is — the per-zone
  choropleth (confirmed-cases gradient) is data, not chrome, and remains visible.
  (No-data zones are handled explicitly in §1.)
- Legacy `Scripts/build_dashboard_public.py` is not touched (it is superseded by
  `Scripts/build_dashboard.py`; see its own header note).

## Design

### 1. Hide health-zone borders in Provincial scope — `Scripts/assets/engine.js`

`styleFn` (`engine.js:1422`–`1454`) has four non-epi return points, each
hard-coding `color`/`weight`: hub zone (`1428`), epicenter zone (`1435`), no-data
zone (`1442`), data zone (`1449`) — there is no single "computed style" object to
amend. So compute the style as today, then apply one suppression step just before
returning, in the non-epi path:

```js
// after the normal style object is chosen, before returning:
if (activeView === "trends" && trendsScope === "province") {
  style.weight = 0;   // no zone-level stroke in Provincial scope
}
```

(Refactoring the branches to build a `style` variable and fall through to a single
`return style` is the cleanest way to attach this; the implementer may instead add
an early Provincial-scope branch — either is fine as long as every non-epi branch
is covered.)

Notes:
- **No-data zones do not go invisible** (verified against `recomputeTrendsMap` →
  `getTrendsConfirmedAt`, `engine.js:2786`, `2741`). In trends scope
  `recomputeTrendsMap` sets `currentValues` for *every* geometry feature, and
  `getTrendsConfirmedAt` coalesces any missing zone/series to `0`. So `has` in
  `styleFn` is always true and the border-only `!has` branch (`engine.js:1442`)
  never runs in trends — there are no fill-less zones to blank out. Data zones
  (including zero-case zones, which take the data branch with a muted fill) keep
  their fill; only the stroke is removed. No faint-fill fallback is needed.
- **Hub/epicenter branches are suppressed too, by intent.** `styleFn` reads
  `getLayer(layerSelect.value)` even in trends (`engine.js:1427`), and
  `isHubZone` / `isEpicenterZone` depend only on that layer's matrix/epicenter
  config, not the view (`engine.js:104`–`113`) — so if `layerSelect` carries an
  epicenter/matrix layer, those emphasis borders *can* fire on the trends map. The
  blanket `weight: 0` strips them in Provincial scope. This is deliberate:
  Provincial scope removes **all** zone-level strokes, whatever the layer.
- The province outlines live in the separate `province-outline` map pane (drawn on
  top), so with zone strokes gone they become the only line work. Adjacent data
  zones with different fill values still show a colour boundary — that is the
  choropleth data, not a drawn border, and is acceptable.
- The `mouseout` and `zoomend` re-style paths already route through `styleFn` /
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
(`trendsScope === "province" && !trendsSelectedKey`, `engine.js:2002`).

**This is a deliberate behaviour change, not a no-op.** Today the trends
`mouseover` paints the hovered zone amber whenever the scope isn't national —
*including after a province is selected* (`engine.js:1614`–`1616`). Routing hover
through the gated `setTrendsProvinceHover` therefore **removes** that
post-selection amber feedback: once a province is selected, hovering another
province gives no feedback. This is intended — amber *zone* highlighting
undercuts the "provinces are the unit" message — and was confirmed as the desired
behaviour (the alternative, keep-highlighting-the-hovered-outline-even-when-one-
is-selected, was considered and rejected). Click-to-select behaviour is unchanged.

The `health_zone` scope keeps its current amber zone hover — only the `province`
branch changes.

### 3. Clean province outlines — `Scripts/common/data_sources.py`

> **This is not a cosmetic-only change.** `build_province_boundaries()` doubles as
> the **authoritative province roster**: `payload.py:107` derives `province_names`
> from its features and feeds them to `load_dashboard_plots(...)` (plot
> generation), and `engine.js` builds the Trends search dropdown from the same
> features (`TRENDS_LOCATION_INDEX`). If the new pipeline ever drops a province —
> zones collapsing to empty under `set_precision`, or a `merged.is_empty` filter
> (`data_sources.py:744`) — that province silently vanishes from **plots and
> search**, not just the map outline. Therefore a **province-count invariant** is
> part of this change (see below), and it matters more than the interior-ring count.

In `build_province_boundaries()`, eliminate the sliver artefacts (interior-ring
holes and detached parts), before the existing `simplify` / coordinate-round steps:

1. **Snap** each source zone geometry to a small coordinate grid
   (`shapely.set_precision`) so shared edges between adjacent zones coincide
   exactly. This removes most slivers at the source of the union. Ordering matters:
   `set_precision` can itself yield invalid/empty geometry, and the current code
   already runs `make_valid(shape(...))` per zone (`data_sources.py:736`). Use the
   safe order **`make_valid` → `set_precision` → `make_valid`**, and skip any zone
   that comes out empty/invalid (as the existing loop already does).
2. **Union** as today (`unary_union`).
3. **Drop sliver holes *and* sliver parts (from review §11).** A small helper
   cleans each dissolved geometry two ways, using the same area threshold:
   - **Interior rings:** rebuild each part keeping its exterior ring plus only
     interior rings at or above the threshold (drops the ~6,145 hole slivers).
   - **Detached exterior parts:** for a MultiPolygon, drop whole parts below the
     threshold. `unary_union` can leave tiny detached fragments where two zone
     edges cross rather than coincide; the strip-holes rebuild would otherwise keep
     such a fragment (it has its own valid exterior ring) and draw it. This slips
     **both** other guards — it rides inside the province's single MultiPolygon
     feature (province-count invariant still matches) and it has no hole (ring
     count still ~0) — so it needs its own pass.

   Both are safe for DRC provinces (no legitimate donut holes, no legitimate small
   island exclaves — provinces are contiguous land), and both keep a threshold
   rather than blindly stripping, as a deliberate safety net.

   **Empirical grounding (current geometry):** the four MultiPolygon provinces each
   have exactly one real part of 5–10 deg² and secondary parts ≤ 4e-4 deg²
   (≈ 5 km²) down to ~1e-7 deg² — a >1000× gap with nothing in between. So a
   threshold anywhere in that gap cleanly separates real land from slivers, for
   both rings and parts.

Then the payload is rebuilt so `trends.html` (and the other pages) pick up the
cleaned geometry.

**Alternative considered — `coverage_union_all`.** The slivers exist because the
health-zone polygons are *meant* to be a coverage but don't share exact edges, and
`shapely.coverage_union_all` targets exactly this without a hole-area threshold.
It was considered but not chosen as the primary path because: (a) it requires a
*valid* coverage, which the gapped source is not, so a `set_precision` snap is
needed first regardless — snap is not optional either way; and (b) `requirements.txt`
pins only `shapely>=2.0`, and coverage semantics/GEOS support vary by version. The
snap+union+strip path is robust to an invalid-coverage input. Implementation may
spike `coverage_union_all` after the snap (verifying the installed shapely/GEOS
version on the build box first); if it cleanly removes the slivers it can replace
step 3 and its threshold. Otherwise the strip-holes helper stands.

**Province-count invariant (from review §7, §9) — the load-bearing guard.** Assert
the output has **exactly one feature per input province** (same count, e.g.
26 in → 26 out), each retaining its `province` property. Fail the build loudly if a
province would be dropped — silent province loss breaks plot generation and Trends
search, not just the outline. This assertion, not the ring count, is the primary
success gate for §3.

Anchor the invariant to the distinct `province` values in the **raw source
features** — collected *before* any geometry filtering — **not** to the
`by_province` keys. `by_province` is populated only after the per-zone
`make_valid` / `geom_type` filter (`data_sources.py:736`–`739`), so a province
whose zones are *all* dropped by that filter would never enter `by_province`, the
count would still match, and the province would silently vanish anyway — the exact
failure this guard exists to catch, just one step upstream of `set_precision`.
Comparing against the raw province set closes that loop.

**Threshold as a guard, not a hand-tuned magic number (from review §5, §11).** The
no-small-holes / no-small-islands assumption is load-bearing, so make it
self-checking: after cleanup, log the *largest dropped* area — for **both** interior
rings and detached parts — and assert each stays below an absolute bound. A future
source/geometry change that introduces a genuine (large) hole or a real island then
trips a loud build failure instead of silently erasing it. This also gives the
threshold a principled value (comfortably above observed sliver areas ≈ 4e-4 deg²,
comfortably below the real-part/real-outline scale of ≥ ~0.8 deg²) rather than an
eyeballed one.

**Units (from review §13).** Geometry is EPSG:4326 lon/lat, so the sliver
threshold and the absolute bound above are in **square degrees**, not m² — state
this at the constants so nobody sets a metric value off by orders of magnitude.
(DRC straddles the equator, so deg² is reasonably uniform across provinces; no
reprojection needed. 1 deg² ≈ 12,300 km² near the equator.)

**`set_precision` grid size — bracket it (from review §12).** Snapping perturbs
*every* vertex (including the province's outer edge) by up to ~half a grid cell, so
"exterior outline unchanged" means *visually* unchanged at display scale, not
byte-identical. Keep the grid in the window **`[1e-5, <1e-3]` degrees**: at/above
the `COORD_DECIMALS = 5` quantum (~1e-5 deg ≈ 1 m; below it, the final rounding
erases the snap) and comfortably below `SIMPLIFY_TOL = 0.001` (~110 m; at/above it,
snapping fights simplify and visibly moves the outline). Pick within that bracket,
don't tune blind.

**Validate ring count on the final, post-round geometry (from review §10).** The
drop-slivers step runs before the existing `simplify` / `_round_coords`
(`COORD_DECIMALS = 5`) steps, and coordinate quantization can in principle
re-introduce a degenerate sub-threshold interior ring. So run the "~0 interior
rings" validation against the **final emitted geometry** (after rounding), not the
pre-round intermediate. If quantization is found to reintroduce rings, move the
strip-holes pass to *after* `_round_coords` instead.

**Grid size / threshold** are tunable constants chosen during implementation and
validated against the success criteria below (start conservative, confirm the
interior-ring count collapses without eroding the exterior outline).

## Success criteria

- Provincial scope: no per-zone strokes on the map; province outlines are the only
  line work; all zone fills (including zero-case zones) still render as today.
- Provincial scope: hovering the map highlights the parent province's outline while
  no province is selected; after a province is selected, hover gives no feedback;
  clicking selects the province (unchanged).
- **Province-count invariant holds: `build_province_boundaries()` returns exactly
  one feature per input province (count unchanged), each keeping its `province`
  property — asserted in the builder, so a geometry regression fails the build
  loudly.** Trends search and plot generation still list every province.
- On the **final post-round geometry**: interior-ring (hole) count drops to ~0 and
  no MultiPolygon retains a sub-threshold detached part (both re-checked via the
  diagnosis geometry script); each province's exterior outline is visually
  unchanged at display scale; and the largest dropped ring **and** largest dropped
  part are logged and below their asserted (square-degree) bounds.
- A selected province shows a clean red outline with no internal lines.
- `national` / `health_zone` scopes and the `map` / `epi-trends` views are
  **behaviourally** unchanged. The province outlines shown in national/health_zone
  scopes also lose their internal sliver lines — an intended consequence of the
  shared cleaned geometry, not a regression (see Non-goals).

## Files touched

- `Scripts/assets/engine.js` — `styleFn` (province-scope stroke suppression via a
  single `weight: 0` step) and the `geoLayer` `mouseover` / `mouseout` province
  branch (route to `setTrendsProvinceHover`). No new style constants.
- `Scripts/common/data_sources.py` — `build_province_boundaries()` (make_valid →
  set_precision → make_valid, union, drop-slivers) plus a small helper that strips
  both sub-threshold interior rings **and** sub-threshold detached parts, the
  **province-count invariant assertion**, and largest-dropped-ring / -part
  logging/assertions (square-degree units).
- Rebuild of `output/` + served `assets/` and the inlined payload in the HTML
  pages (build artifact).
