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
