import importlib

from shapely import STRtree
from shapely.geometry import Polygon

ds = importlib.import_module("common.data_sources")


def _overlapping_pairs(geoms):
    tree = STRtree(geoms)
    n = 0
    for i, a in enumerate(geoms):
        for j in tree.query(a):
            if j > i and a.intersects(geoms[j]) and a.intersection(geoms[j]).area > 1e-12:
                n += 1
    return n


def test_clean_coverage_removes_overlap():
    # Two zones that overlap in a shared strip (the source-data defect): each
    # would otherwise stroke a different border along the seam.
    a = Polygon([(0, 0), (5.2, 0), (5.2, 4), (0, 4)])   # extends past x=5
    b = Polygon([(4.8, 0), (10, 0), (10, 4), (4.8, 4)])  # starts before x=5
    assert a.intersection(b).area > 0  # guard: they really do overlap
    cleaned = ds._clean_coverage([a, b])
    assert len(cleaned) == 2
    assert _overlapping_pairs(cleaned) == 0
    # nothing is lost outside the original footprint, and both zones survive
    assert all(not g.is_empty for g in cleaned)
    assert all(g.geom_type in {"Polygon", "MultiPolygon"} for g in cleaned)


def test_clean_coverage_preserves_disjoint_zones():
    # Non-overlapping zones must pass through essentially unchanged.
    a = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    b = Polygon([(5, 0), (6, 0), (6, 1), (5, 1)])
    cleaned = ds._clean_coverage([a, b])
    assert _overlapping_pairs(cleaned) == 0
    assert cleaned[0].area == a.area
    assert cleaned[1].area == b.area
