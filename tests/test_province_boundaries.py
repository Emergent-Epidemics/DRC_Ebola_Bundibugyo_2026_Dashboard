import importlib
import json

import pytest
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


def test_strip_slivers_keeps_largest_when_all_parts_sub_threshold():
    # Pathological: every part is below threshold. Never erase the province --
    # keep the largest, and report only the genuinely-dropped part.
    big = Polygon(_square(0, 0, 0.02))       # area 4e-4 (< 1e-3 threshold)
    small = Polygon(_square(100, 100, 0.01))  # area 1e-4, actually dropped
    mp = MultiPolygon([big, small])
    cleaned, ring_max, part_max = ds._strip_slivers(mp, ds.PROVINCE_SLIVER_MAX)
    assert cleaned.geom_type == "Polygon"
    assert abs(cleaned.area - 4e-4) < 1e-12
    assert abs(part_max - 1e-4) < 1e-12      # the dropped one, not the kept one


def _feature(nom, province, square_coords):
    return {
        "type": "Feature",
        "properties": {"nom": nom, "province": province},
        "geometry": {"type": "Polygon", "coordinates": [square_coords + [square_coords[0]]]},
    }


def test_build_province_boundaries_preserves_every_province(tmp_path, monkeypatch):
    # Two provinces, two adjacent zones each. Alpha's zones have a SUB-GRID seam
    # gap (3e-6 < PROVINCE_SNAP_GRID = 1e-5): the naive union would leave them as
    # a 2-part MultiPolygon, but the set_precision snap closes the seam so they
    # merge into a single Polygon. That merge is what discriminates the new
    # pipeline from the old.
    features = [
        _feature("z1", "Alpha", _square(0, 0, 2)),
        _feature("z2", "Alpha", _square(2 + 3e-6, 0, 2)),   # sub-grid seam gap
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
    by_prov = {f["properties"]["province"]: f["geometry"] for f in out["features"]}
    # snap closed Alpha's sub-grid seam -> single merged Polygon (not MultiPolygon)
    assert by_prov["Alpha"]["type"] == "Polygon"
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

    with pytest.raises(ValueError, match="Ghost"):
        ds.build_province_boundaries()
