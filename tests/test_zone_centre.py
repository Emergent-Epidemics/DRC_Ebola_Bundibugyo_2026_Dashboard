import importlib

from shapely.geometry import MultiPolygon, Polygon

ds = importlib.import_module("common.data_sources")


def test_centre_inside_concave_polygon():
    # C-shape: the area-weighted centroid falls in the concavity, outside the
    # polygon; _zone_centre() must return an interior point.
    c_shape = Polygon([(0, 0), (4, 0), (4, 1), (1, 1), (1, 3), (4, 3), (4, 4), (0, 4)])
    assert not c_shape.contains(c_shape.centroid)  # guard: the case we care about
    pt = ds._zone_centre(c_shape)
    assert c_shape.contains(pt)


def test_centre_inside_multipolygon():
    # Two disjoint squares: the centroid lands in the empty gap between them.
    mp = MultiPolygon([
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(5, 0), (7, 0), (7, 2), (5, 2)]),  # larger part
    ])
    assert not mp.contains(mp.centroid)  # guard
    pt = ds._zone_centre(mp)
    assert mp.contains(pt)
    # anchors on the largest-area part
    largest = max(mp.geoms, key=lambda p: p.area)
    assert largest.contains(pt)


def test_centre_falls_back_to_interior_point(monkeypatch):
    # If polylabel raises, _zone_centre() must still return an interior point
    # via the representative_point() fallback.
    def boom(*args, **kwargs):
        raise RuntimeError("polylabel unavailable")

    monkeypatch.setattr(ds, "polylabel", boom)
    c_shape = Polygon([(0, 0), (4, 0), (4, 1), (1, 1), (1, 3), (4, 3), (4, 4), (0, 4)])
    pt = ds._zone_centre(c_shape)
    assert c_shape.contains(pt)
