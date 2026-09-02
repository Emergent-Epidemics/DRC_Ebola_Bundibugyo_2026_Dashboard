from __future__ import annotations

import importlib

ds = importlib.import_module("common.data_sources")


def _ts(dates, by_nom):
    """Minimal confirmed_timeseries dict (only the keys the function reads)."""
    return {"dates": list(dates), "by_nom": {k: list(v) for k, v in by_nom.items()}}


def test_returns_none_when_input_none():
    assert ds.compute_confirmed_recency_timeseries(None) is None


def test_never_affected_is_category_4_every_frame():
    ts = _ts(["2026-05-01", "2026-06-01", "2026-07-01"], {"Z": [0, 0, 0]})
    out = ds.compute_confirmed_recency_timeseries(ts)
    assert out["by_nom"]["Z"] == [4, 4, 4]
    assert out["days_by_nom"]["Z"] == [-1, -1, -1]


def test_first_date_nonzero_counts_as_event_on_first_date():
    ts = _ts(["2026-05-01"], {"Z": [3]})
    out = ds.compute_confirmed_recency_timeseries(ts)
    assert out["by_nom"]["Z"] == [1]        # 0 days since -> active
    assert out["days_by_nom"]["Z"] == [0]


def test_boundary_days_14_15_42_43():
    # Case appears on day 0; frames probe the zone at 14, 15, 42, 43 days later.
    dates = ["2026-05-01", "2026-05-15", "2026-05-16", "2026-06-12", "2026-06-13"]
    #          d=0(event)    d=14          d=15          d=42          d=43
    ts = _ts(dates, {"Z": [1, 1, 1, 1, 1]})  # cumulative flat after the event
    out = ds.compute_confirmed_recency_timeseries(ts)
    assert out["days_by_nom"]["Z"] == [0, 14, 15, 42, 43]
    assert out["by_nom"]["Z"] == [1, 1, 2, 2, 3]  # <=14:1, 15-42:2, >42:3


def test_carry_forward_gap_uses_last_increase_date():
    # Increase on frame idx 1; a later frame with no increase keeps counting days.
    dates = ["2026-05-01", "2026-05-10", "2026-06-30"]
    ts = _ts(dates, {"Z": [0, 5, 5]})
    out = ds.compute_confirmed_recency_timeseries(ts)
    assert out["by_nom"]["Z"] == [4, 1, 3]           # never, active, dormant
    assert out["days_by_nom"]["Z"] == [-1, 0, 51]


def test_downward_correction_is_not_a_new_event():
    # cumulative drops between frames 1 and 2; that drop must not reset the clock.
    dates = ["2026-05-01", "2026-05-02", "2026-05-30"]
    ts = _ts(dates, {"Z": [5, 4, 4]})
    out = ds.compute_confirmed_recency_timeseries(ts)
    # Only event is the day-0 baseline (5 > 0). Day 29 from start -> category 2.
    assert out["days_by_nom"]["Z"] == [0, 1, 29]
    assert out["by_nom"]["Z"] == [1, 1, 2]


def test_transitions_across_all_four_categories():
    dates = ["2026-05-01", "2026-05-05", "2026-05-25", "2026-07-01"]
    ts = _ts(dates, {"Z": [0, 2, 2, 2]})
    out = ds.compute_confirmed_recency_timeseries(ts)
    # never(0) -> active(0d) -> recent(20d) -> dormant(57d)
    assert out["by_nom"]["Z"] == [4, 1, 2, 3]


def test_custom_thresholds_respected():
    dates = ["2026-05-01", "2026-05-08"]
    ts = _ts(dates, {"Z": [1, 1]})
    out = ds.compute_confirmed_recency_timeseries(ts, near_days=5, mid_days=10)
    assert out["thresholds"] == {"near": 5, "mid": 10}
    assert out["by_nom"]["Z"] == [1, 2]  # day 7 > near(5), <= mid(10) -> cat 2


def test_passthrough_metadata():
    dates = ["2026-05-01", "2026-05-02"]
    ts = _ts(dates, {"Z": [0, 1]})
    out = ds.compute_confirmed_recency_timeseries(ts)
    assert out["dates"] == dates
    assert set(out["labels"].keys()) == {"1", "2", "3", "4"}
