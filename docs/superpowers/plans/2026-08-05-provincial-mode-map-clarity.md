# Provincial-mode Map Clarity + Clean Province Outlines Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Epidemiological Trends tab in Provincial scope, make provinces read as the selectable unit (hide zone strokes, redirect hover to the province outline) and give province outlines clean geometry (no residual internal sliver lines).

**Architecture:** Two independent changes. (1) `Scripts/common/data_sources.py::build_province_boundaries()` gains a snap → union → strip-slivers pipeline plus a province-count invariant, cleaning the dissolved geometry that every trends scope draws. (2) `Scripts/assets/engine.js` suppresses per-zone strokes and routes map hover to the province-outline highlight in Provincial scope. A rebuild embeds both into the pages.

**Tech Stack:** Python 3.9+/shapely 2.0 (geometry), pytest (Python tests), vanilla JS + Leaflet (`engine.js`, no JS test harness). Spec: `docs/superpowers/specs/2026-08-05-provincial-mode-map-clarity-design.md`.

**Branch:** `provincial-mode-map-clarity` (already created off `main`).

**Environment note:** Python tests and the build need the project's Python env (`pip install -r requirements.txt`) — system `python3` lacks pytest/shapely. Python tests import `common.*`, so **run pytest from the `Scripts/` directory**. The build (`python Scripts/build_dashboard.py`) reads geometry from the sibling `BDBV2026-Data` build dir (see README "Building the dashboard"); it must be present for Tasks 3 and 6.

---

## File Structure

- **Modify** `Scripts/common/data_sources.py`
  - Add `set_precision` to the shapely import (line 29).
  - Add three constants after `COORD_DECIMALS` (line 226).
  - Add `_strip_slivers()` helper (near `_round_coords`, ~line 588).
  - Rewrite `build_province_boundaries()` (lines 723–758).
  - Add the new public names to `__all__`.
- **Create** `tests/test_province_boundaries.py` — unit tests for `_strip_slivers` and an end-to-end invariant test for `build_province_boundaries` (monkeypatched `BUILD_GEOJSON`).
- **Create** `Scripts/check_province_geometry.py` — reusable diagnostic: counts interior rings + sub-threshold parts in a built page's payload (post-round validation for §10).
- **Modify** `Scripts/assets/engine.js`
  - `styleFn` (lines 1422–1454): suppress zone stroke in Provincial scope.
  - `geoLayer` `mouseover` (1614–1619) / `mouseout` (1635–1641): route Provincial-scope hover to `setTrendsProvinceHover`.
- **Build artifacts** (regenerated, committed): `output/*.html`, `output/assets/engine.js`, root `*.html`, `assets/engine.js`.

---

## Task 1: `_strip_slivers` helper + constants (Python, TDD)

**Files:**
- Modify: `Scripts/common/data_sources.py` (import line 29; constants after line 226; `__all__` ~lines 53–101; helper after `_round_coords` ~line 588)
- Test: `tests/test_province_boundaries.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_province_boundaries.py`:

```python
import importlib

from shapely.geometry import Polygon, MultiPolygon

ds = importlib.import_module("common.data_sources")


def _square(cx, cy, s):
    """Axis-aligned square of side `s` centred at (cx, cy)."""
    h = s / 2.0
    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]


def test_strip_slivers_drops_small_interior_ring():
    # Big polygon with a tiny hole (area ~1e-6 deg^2) well below the threshold.
    shell = _square(0, 0, 4)                 # area 16
    tiny_hole = _square(0, 0, 0.001)         # area 1e-6
    poly = Polygon(shell, [tiny_hole])
    assert len(poly.interiors) == 1
    cleaned, ring_max, part_max = ds._strip_slivers(poly, ds.PROVINCE_SLIVER_MAX)
    assert cleaned.geom_type == "Polygon"
    assert len(cleaned.interiors) == 0       # hole dropped
    assert abs(ring_max - 1e-6) < 1e-9       # reported the dropped ring area
    assert part_max == 0.0


def test_strip_slivers_keeps_large_interior_ring():
    # A hole above the threshold is a legitimate donut and must be kept.
    shell = _square(0, 0, 10)
    big_hole = _square(0, 0, 1)              # area 1.0 >> threshold
    poly = Polygon(shell, [big_hole])
    cleaned, ring_max, part_max = ds._strip_slivers(poly, ds.PROVINCE_SLIVER_MAX)
    assert len(cleaned.interiors) == 1
    assert ring_max == 0.0


def test_strip_slivers_drops_small_detached_part_and_demotes_to_polygon():
    big = Polygon(_square(0, 0, 5))          # area 25
    sliver = Polygon(_square(100, 100, 0.001))  # area 1e-6, detached
    mp = MultiPolygon([big, sliver])
    cleaned, ring_max, part_max = ds._strip_slivers(mp, ds.PROVINCE_SLIVER_MAX)
    assert cleaned.geom_type == "Polygon"    # only the big part survives
    assert abs(cleaned.area - 25) < 1e-9
    assert abs(part_max - 1e-6) < 1e-9


def test_strip_slivers_keeps_multiple_large_parts():
    a = Polygon(_square(0, 0, 3))            # area 9
    b = Polygon(_square(100, 0, 3))          # area 9, legitimately separate
    mp = MultiPolygon([a, b])
    cleaned, ring_max, part_max = ds._strip_slivers(mp, ds.PROVINCE_SLIVER_MAX)
    assert cleaned.geom_type == "MultiPolygon"
    assert len(cleaned.geoms) == 2
    assert part_max == 0.0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd Scripts && python -m pytest ../tests/test_province_boundaries.py -v`
Expected: FAIL — `AttributeError: module 'common.data_sources' has no attribute '_strip_slivers'` (and `PROVINCE_SLIVER_MAX`).

- [ ] **Step 3: Add `set_precision` to the shapely import**

In `Scripts/common/data_sources.py` line 29, change:

```python
from shapely import STRtree
```
to:
```python
from shapely import STRtree, set_precision
```

- [ ] **Step 4: Add the constants**

After `COORD_DECIMALS = 5` (line 226), insert:

```python
# --- province-outline dissolve cleanup (build_province_boundaries) ---------
# All three are in EPSG:4326 native units (degrees / square degrees), NOT metres.
# 1 deg^2 ~ 12,300 km^2 near the equator.
PROVINCE_SNAP_GRID = 1e-5     # set_precision grid, degrees (~1 m). In
                             # [COORD_DECIMALS quantum, SIMPLIFY_TOL): snaps shared
                             # zone edges together to close seam gaps, without
                             # visibly moving the province outline.
PROVINCE_SLIVER_MAX = 1e-3   # deg^2: drop interior rings AND detached parts below
                             # this. Observed slivers <= ~4e-4 deg^2; the real part
                             # of every province is >= ~0.8 deg^2 -- a >1000x gap.
```

- [ ] **Step 5: Add the helper**

After `_round_coords` (ends line 588), insert:

```python
def _strip_slivers(geom, min_area: float):
    """Drop interior rings and detached parts below ``min_area`` (square degrees).

    ``unary_union`` of imperfectly-aligned zone polygons leaves two kinds of
    artefact: tiny interior rings (holes at seam gaps) and tiny detached exterior
    parts (fragments where edges cross rather than coincide). DRC provinces have
    no legitimate donut holes and no legitimate small island exclaves, so both are
    safe to drop below a threshold that sits in the wide empirical gap between
    sliver and real-part areas.

    Returns ``(cleaned_geom, dropped_ring_max, dropped_part_max)`` -- the largest
    dropped ring/part area seen (0.0 if none), for the caller to log and sanity-check.
    """
    from shapely.geometry import Polygon, MultiPolygon

    dropped_ring_max = 0.0
    dropped_part_max = 0.0

    def clean_polygon(poly):
        nonlocal dropped_ring_max
        keep = []
        for ring in poly.interiors:
            area = Polygon(ring).area
            if area >= min_area:
                keep.append(ring)
            else:
                dropped_ring_max = max(dropped_ring_max, area)
        return Polygon(poly.exterior, keep)

    if geom.geom_type == "Polygon":
        return clean_polygon(geom), dropped_ring_max, dropped_part_max

    if geom.geom_type == "MultiPolygon":
        keep_parts = []
        for part in geom.geoms:
            if part.area >= min_area:
                keep_parts.append(clean_polygon(part))
            else:
                dropped_part_max = max(dropped_part_max, part.area)
        if not keep_parts:
            # Defensive: never drop every part (would erase a province). Keep the
            # largest untouched; the caller's invariant still guards the roster.
            keep_parts = [clean_polygon(max(geom.geoms, key=lambda p: p.area))]
        if len(keep_parts) == 1:
            return keep_parts[0], dropped_ring_max, dropped_part_max
        return MultiPolygon(keep_parts), dropped_ring_max, dropped_part_max

    return geom, dropped_ring_max, dropped_part_max
```

- [ ] **Step 6: Add new names to `__all__`**

In the `__all__` list, alongside `'COORD_DECIMALS'` / `'_clean_coverage'`, add `'PROVINCE_SNAP_GRID'`, `'PROVINCE_SLIVER_MAX'`, and `'_strip_slivers'`. Example — after the line `    'COORD_DECIMALS',` (line 54) add:

```python
    'PROVINCE_SNAP_GRID',
    'PROVINCE_SLIVER_MAX',
```

and after `    '_clean_coverage',` (line 99) add:

```python
    '_strip_slivers',
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `cd Scripts && python -m pytest ../tests/test_province_boundaries.py -v`
Expected: PASS — all four `test_strip_slivers_*` tests green.

- [ ] **Step 8: Commit**

```bash
git add Scripts/common/data_sources.py tests/test_province_boundaries.py
git commit -m "Add _strip_slivers helper + province dissolve-cleanup constants"
```

---

## Task 2: Reusable province-geometry check script (Python)

A standalone diagnostic used to validate the cleanup on the **final built page** (post-round, per spec §10). Create it before the build so Task 6 can run it.

**Files:**
- Create: `Scripts/check_province_geometry.py`

- [ ] **Step 1: Write the script**

Create `Scripts/check_province_geometry.py`:

```python
#!/usr/bin/env python3
"""Report interior rings + sub-threshold detached parts in the province outlines
embedded in a built dashboard page.

Usage:
    python Scripts/check_province_geometry.py [path/to/trends.html]

A clean build (after build_province_boundaries' snap -> union -> strip-slivers)
has 0 interior rings and 0 sub-threshold parts. Run against the FINAL built page
so coordinate rounding is included in what is checked (spec section 10). Exit code
is 0 on PASS, 1 on FAIL, so it can gate CI.
"""
import json
import re
import sys

SLIVER_MAX_DEG2 = 1e-3  # keep in sync with data_sources.PROVINCE_SLIVER_MAX


def ring_area(ring):
    s = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][:2]
        x2, y2 = ring[i + 1][:2]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def main(path):
    html = open(path).read()
    m = re.search(r'<script id="payload" type="application/json">', html)
    if not m:
        print("FAIL: no payload script in", path)
        return 1
    start = m.end()
    end = html.index("</script>", start)
    pb = json.loads(html[start:end]).get("province_boundaries", {})
    feats = pb.get("features", [])

    total_holes = 0
    total_small_parts = 0
    for f in feats:
        g = f["geometry"]
        prov = f["properties"].get("province")
        parts = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        holes = sum(len(p) - 1 for p in parts)
        small_parts = sum(1 for p in parts if ring_area(p[0]) < SLIVER_MAX_DEG2)
        total_holes += holes
        total_small_parts += small_parts
        if holes or small_parts:
            print(f"{prov:24s} holes={holes} small_parts={small_parts}")

    print(f"\n{len(feats)} provinces; interior rings={total_holes}, "
          f"sub-threshold parts={total_small_parts}")
    ok = total_holes == 0 and total_small_parts == 0
    print("PASS" if ok else "FAIL: sliver artefacts remain")
    return 0 if ok else 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "trends.html"
    sys.exit(main(target))
```

- [ ] **Step 2: Smoke-run against the CURRENT (pre-fix) built page to confirm it detects the defect**

Run: `python Scripts/check_province_geometry.py trends.html`
Expected: FAIL — thousands of interior rings reported (e.g. `Kongo-Central holes=715`), ending `FAIL: sliver artefacts remain`. This confirms the checker sees the current defect (it will read PASS after Task 6's rebuild).

- [ ] **Step 3: Commit**

```bash
git add Scripts/check_province_geometry.py
git commit -m "Add province-geometry sliver check script"
```

---

## Task 3: Rewrite `build_province_boundaries()` (snap + strip + invariant)

**Files:**
- Modify: `Scripts/common/data_sources.py:723-758`
- Test: `tests/test_province_boundaries.py` (extend)

- [ ] **Step 1: Write the failing end-to-end test**

Append to `tests/test_province_boundaries.py`:

```python
import json


def _feature(nom, province, square_coords):
    return {
        "type": "Feature",
        "properties": {"nom": nom, "province": province},
        "geometry": {"type": "Polygon", "coordinates": [square_coords + [square_coords[0]]]},
    }


def test_build_province_boundaries_preserves_every_province(tmp_path, monkeypatch):
    # Two provinces, two adjacent zones each. Zones share an edge with a tiny
    # misalignment so the naive union would leave a seam sliver.
    features = [
        _feature("z1", "Alpha", _square(0, 0, 2)),
        _feature("z2", "Alpha", _square(2.0001, 0, 2)),   # ~1e-4 gap at the seam
        _feature("z3", "Beta", _square(0, 10, 2)),
        _feature("z4", "Beta", _square(2.0, 10, 2)),
    ]
    fc = {"type": "FeatureCollection", "features": features}
    path = tmp_path / "zones.geojson"
    path.write_text(json.dumps(fc))
    monkeypatch.setattr(ds, "BUILD_GEOJSON", path)

    out = ds.build_province_boundaries()
    provinces = sorted(f["properties"]["province"] for f in out["features"])
    assert provinces == ["Alpha", "Beta"]          # invariant: 2 in -> 2 out
    for f in out["features"]:
        g = f["geometry"]
        parts = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        assert sum(len(p) - 1 for p in parts) == 0  # no interior-ring slivers


def test_build_province_boundaries_raises_when_a_province_is_lost(tmp_path, monkeypatch):
    # A province whose only zone has non-areal geometry is filtered out before
    # the union; the invariant must catch the silent loss and raise.
    features = [
        _feature("z1", "Alpha", _square(0, 0, 2)),
        {
            "type": "Feature",
            "properties": {"nom": "z2", "province": "Ghost"},
            "geometry": {"type": "LineString", "coordinates": [(0, 0), (1, 1)]},
        },
    ]
    fc = {"type": "FeatureCollection", "features": features}
    path = tmp_path / "zones.geojson"
    path.write_text(json.dumps(fc))
    monkeypatch.setattr(ds, "BUILD_GEOJSON", path)

    import pytest
    with pytest.raises(ValueError, match="Ghost"):
        ds.build_province_boundaries()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd Scripts && python -m pytest ../tests/test_province_boundaries.py -v -k build_province`
Expected: FAIL — specifically `test_build_province_boundaries_raises_when_a_province_is_lost` fails, because the current function has no invariant and silently returns a shrunk collection instead of raising `ValueError`. (`test_..._preserves_every_province` may already pass on this simple clean input — that's fine; it locks in the invariant behaviour going forward. The decisive red test here is the `_raises` one.)

- [ ] **Step 3: Replace the function body**

Replace `build_province_boundaries()` (lines 723–758) with:

```python
def build_province_boundaries() -> dict:
    """Union health-zone polygons into one clean outline per province.

    Also the authoritative province roster: ``payload.py`` derives
    ``province_names`` from these features (plot generation) and ``engine.js``
    builds the Trends search dropdown from them. A dropped province silently
    disappears from plots + search, so the province-count invariant below is
    asserted, not merely hoped for.
    """
    if not BUILD_GEOJSON.exists():
        return {"type": "FeatureCollection", "features": []}

    with open(BUILD_GEOJSON) as f:
        raw = json.load(f)

    # Distinct provinces in the RAW source, before any geometry filtering. The
    # invariant compares output against THIS set (not ``by_province`` keys): a
    # province whose zones are all dropped by the make_valid/geom-type filter
    # would never enter ``by_province``, so the count would still match while the
    # province silently vanished.
    raw_provinces = {
        (feat.get("properties") or {}).get("province")
        for feat in (raw.get("features") or [])
        if (feat.get("properties") or {}).get("province")
    }

    by_province: dict[str, list] = {}
    for feat in raw.get("features") or []:
        prov = (feat.get("properties") or {}).get("province")
        if not prov:
            continue
        # make_valid -> set_precision (snap shared edges together) -> make_valid.
        # Snapping can itself re-introduce invalidity, hence the second repair.
        geom = make_valid(shape(feat["geometry"]))
        geom = make_valid(set_precision(geom, PROVINCE_SNAP_GRID))
        if geom.is_empty or geom.geom_type not in {"Polygon", "MultiPolygon"}:
            continue
        by_province.setdefault(prov, []).append(geom)

    out: list[dict] = []
    max_dropped_ring = 0.0
    max_dropped_part = 0.0
    for prov in sorted(by_province):
        merged = unary_union(by_province[prov])
        if merged.is_empty:
            continue
        merged, ring_max, part_max = _strip_slivers(merged, PROVINCE_SLIVER_MAX)
        max_dropped_ring = max(max_dropped_ring, ring_max)
        max_dropped_part = max(max_dropped_part, part_max)
        if merged.is_empty:
            continue
        if SIMPLIFY_TOL > 0:
            merged = merged.simplify(SIMPLIFY_TOL, preserve_topology=True)
        if merged.is_empty:
            continue
        gdict = mapping(merged)
        if COORD_DECIMALS is not None:
            gdict = _round_coords(gdict, COORD_DECIMALS)
        out.append({
            "type": "Feature",
            "geometry": gdict,
            "properties": {"province": prov},
        })

    # Province-count invariant (the load-bearing guard): every raw province must
    # survive to exactly one output feature. Fail loudly -- a dropped province
    # silently breaks plot generation and Trends search, not just the outline.
    out_provinces = {f["properties"]["province"] for f in out}
    missing = raw_provinces - out_provinces
    if missing:
        raise ValueError(
            f"build_province_boundaries dropped provinces {sorted(missing)}; "
            "the geometry pipeline must preserve every province (plots + search "
            "derive their province list from this output)."
        )
    assert len(out) == len(raw_provinces), (
        f"province count {len(out)} != {len(raw_provinces)} raw provinces"
    )

    # Sliver-cleanup visibility: print the largest ring/part dropped so a
    # shrinking empirical gap (a genuine large hole/island nearing the threshold)
    # is noticeable in the build log, and sanity-check the helper honoured its
    # threshold.
    print(
        f"  province sliver cleanup: largest dropped ring {max_dropped_ring:.2e} "
        f"deg^2, largest dropped part {max_dropped_part:.2e} deg^2 "
        f"(threshold {PROVINCE_SLIVER_MAX:.0e})"
    )
    assert max_dropped_ring < PROVINCE_SLIVER_MAX and max_dropped_part < PROVINCE_SLIVER_MAX

    return {"type": "FeatureCollection", "features": out}
```

- [ ] **Step 4: Run to verify pass**

Run: `cd Scripts && python -m pytest ../tests/test_province_boundaries.py -v`
Expected: PASS — all six tests green (four `_strip_slivers`, two `build_province_boundaries`).

- [ ] **Step 5: Commit**

```bash
git add Scripts/common/data_sources.py tests/test_province_boundaries.py
git commit -m "build_province_boundaries: snap+strip slivers, assert province-count invariant"
```

---

## Task 4: Suppress zone strokes in Provincial scope (`engine.js`)

No JS test harness exists; this task is a precise edit verified visually in Task 6.

**Files:**
- Modify: `Scripts/assets/engine.js:1422-1454` (`styleFn`)

- [ ] **Step 1: Replace `styleFn`**

Replace `styleFn` (lines 1422–1454) with (adds a `prov()` wrapper that zeroes the stroke weight in Provincial scope, applied to every non-epi return):

```js
function styleFn(feature) {
  if (activeView === "epi-trends") return epiTrendsStyleFn(feature);
  const ref = feature.properties.nom;
  const v = currentValues.get(ref);
  const has = v != null && !Number.isNaN(v);
  const layer = getLayer(layerSelect.value);
  // In Provincial scope, suppress ALL zone-level strokes so the province
  // outlines (drawn in the province-outline pane) are the only line work. Fills
  // are untouched, so the choropleth (incl. zero-case muted fills) still reads;
  // the no-data branch never fires in trends (recomputeTrendsMap coalesces
  // missing values to 0), so no zone goes fill-less/invisible.
  const prov = function (s) {
    if (activeView === "trends" && trendsScope === "province") s.weight = 0;
    return s;
  };
  if (isHubZone(ref, layer)) {
    return prov({
      color: "#111", weight: 1.6,
      fillColor: MATRIX_ORIGIN_FILL,
      fillOpacity: 0.92
    });
  }
  if (isEpicenterZone(ref, layer)) {
    return prov({
      color: "#111", weight: zoomWeight(0.5),
      fillColor: EPICENTER_FILL,
      fillOpacity: 0.88
    });
  }
  if (!has) {
    return prov({ color: "#111", weight: zoomWeight(0.35), fillOpacity: 0 });
  }
  const isOutbreak = layer && layer.palette === "outbreak";
  const dataOpacity = isOutbreak ? 0.72 : 0.85;
  const mutedOpacity = isOutbreak ? 0.48 : 0.55;
  const isZero = currentDomain.isLog ? v <= 0 : v === 0;
  return prov({
    color: "#111", weight: zoomWeight(0.35),
    fillColor: valueToColor(v, ref, layer),
    fillOpacity: isZero ? mutedOpacity : dataOpacity
  });
}
```

- [ ] **Step 2: Sanity-check the edit is syntactically consistent**

Run: `node --check Scripts/assets/engine.js` (if Node is available) — Expected: no output (valid). If Node is unavailable, visually confirm the four `return prov({...})` wrappers each balance parentheses/braces. Full visual verification happens in Task 6.

- [ ] **Step 3: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "engine.js: suppress zone strokes in Provincial trends scope"
```

---

## Task 5: Route Provincial-scope hover to the province outline (`engine.js`)

**Files:**
- Modify: `Scripts/assets/engine.js` `mouseover` (1614–1619) and `mouseout` (1635–1641)

- [ ] **Step 1: Update the `mouseover` trends branch**

Replace lines 1614–1619:

```js
        if (activeView === "trends") {
          if (trendsScope === "national") return;
          e.target.setStyle({weight: 1.6, color: "#ffae42"});
          e.target.bringToFront();
          return;
        }
```
with:
```js
        if (activeView === "trends") {
          if (trendsScope === "national") return;
          if (trendsScope === "province") {
            // Highlight the parent province's outline (matches click-to-select),
            // rather than the individual zone. Gated inside setTrendsProvinceHover
            // to no-op once a province is selected.
            setTrendsProvinceHover(feature.properties.province);
            return;
          }
          e.target.setStyle({weight: 1.6, color: "#ffae42"});
          e.target.bringToFront();
          return;
        }
```

- [ ] **Step 2: Update the `mouseout` trends branch**

Replace lines 1635–1641:

```js
        if (activeView === "trends") {
          geoLayer.resetStyle(e.target);
          if (trendsScope === "health_zone" && trendsSelectedKey &&
              feature.properties.nom === trendsSelectedKey) {
            e.target.setStyle({weight: 2, color: "#ffae42"});
          }
          return;
        }
```
with:
```js
        if (activeView === "trends") {
          if (trendsScope === "province") {
            // Zone was never restyled on hover in province scope; just clear the
            // province-outline highlight.
            setTrendsProvinceHover(null);
            return;
          }
          geoLayer.resetStyle(e.target);
          if (trendsScope === "health_zone" && trendsSelectedKey &&
              feature.properties.nom === trendsSelectedKey) {
            e.target.setStyle({weight: 2, color: "#ffae42"});
          }
          return;
        }
```

- [ ] **Step 3: Sanity-check**

Run: `node --check Scripts/assets/engine.js` (if available) — Expected: no output. Confirm `setTrendsProvinceHover` is defined (it is, ~line 2000) and the `health_zone` amber hover path is unchanged.

- [ ] **Step 4: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "engine.js: Provincial-scope hover highlights parent province outline"
```

---

## Task 6: Build, deploy-copy, and verify all success criteria

**Files:**
- Regenerate + commit: `output/*.html`, `output/assets/*`, root `*.html`, `assets/*`

- [ ] **Step 1: Build the dashboard**

Run: `python Scripts/build_dashboard.py`
Expected: completes without error; the log includes the province-boundaries line (`province boundaries: 26 provinces`) and the new `province sliver cleanup: largest dropped ring … part … (threshold 1e-03)` line. **If the run raises `ValueError: build_province_boundaries dropped provinces […]`, stop** — the invariant caught a regression; investigate before proceeding (likely the snap grid is too coarse for some province — reduce `PROVINCE_SNAP_GRID`).

- [ ] **Step 2: Validate the cleaned geometry on the FINAL built page (spec §10, post-round)**

Run: `python Scripts/check_province_geometry.py output/trends.html`
Expected: `26 provinces; interior rings=0, sub-threshold parts=0` then `PASS`.
If it reports residual rings, coordinate rounding reintroduced them — move the `_strip_slivers` call to *after* `_round_coords` in `build_province_boundaries` (operate on the rounded `gdict` via `shape(gdict)`), rebuild, and re-check.

- [ ] **Step 3: Copy the build to the site entry points**

Run:
```bash
cp output/index.html output/spatial-risk.html output/trends.html output/context.html .
rm -rf assets && cp -r output/assets assets
```
Expected: root `trends.html` and `assets/engine.js` now reflect the build.

- [ ] **Step 4: Visual verification — open `trends.html` and check each success criterion**

Open `trends.html` in a browser (or via the `run` skill). Confirm, in the **Provincial** scope:
- [ ] No dark per-zone borders on the map; province outlines are the only line work. Zone choropleth fills (including muted zero-case fills) still render.
- [ ] Hovering the map (no province selected) highlights the **parent province's** outline, not an individual zone.
- [ ] After clicking a province, its outline is red/selected with **no internal sliver lines**; hovering another province now gives no feedback (gate).
- [ ] Clicking a province still selects it (info box / plots update as before).

And confirm no regressions:
- [ ] **National** scope: map unchanged except province outlines are cleaner (no faint internal gold lines) — an intended side effect.
- [ ] **Health zone** scope: per-zone amber hover + zone borders still present, as before.

- [ ] **Step 5: Commit the build artifacts**

```bash
git add output trends.html index.html spatial-risk.html context.html assets
git commit -m "Build: provincial-mode map clarity + clean province outlines"
```

---

## Self-Review (completed during planning)

- **Spec coverage:** §1 zone-stroke suppression → Task 4; §1 no-data behaviour (retracted concern) → comment in Task 4 styleFn; §2 hover→province → Task 5; §2 post-selection gate → Task 5 (relies on existing `setTrendsProvinceHover` gate); §3 snap ordering → Task 3; §3 strip rings **and** parts (§11) → Task 1 `_strip_slivers` + Task 3; §5 largest-dropped logging/sanity → Task 3; §7/§9 province-count invariant on raw set → Task 3; §10 post-round ring validation → Task 2 script + Task 6 step 2; §12 grid bracket → Task 1 constant comment; §13 square-degree units → Task 1 constant comment + script. §4 (`coverage_union_all`) is a documented alternative, not a required task.
- **Placeholder scan:** none — every code/edit step carries complete code.
- **Type/name consistency:** `_strip_slivers(geom, min_area) -> (geom, ring_max, part_max)` defined in Task 1 and consumed with that exact shape in Task 3; `PROVINCE_SNAP_GRID` / `PROVINCE_SLIVER_MAX` defined Task 1, used Task 3; `setTrendsProvinceHover` referenced in Task 5 exists at `engine.js:2000`; `SLIVER_MAX_DEG2` in the check script mirrors `PROVINCE_SLIVER_MAX`.
