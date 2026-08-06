from __future__ import annotations

import importlib
from pathlib import Path

ds = importlib.import_module("common.data_sources")


def _make_key_outputs(tmp_path: Path, harmonised_csv: str | None) -> Path:
    ko = tmp_path / "2026-08-03" / "spatiotemporal" / "key_outputs"
    ko.mkdir(parents=True)
    (ko / "bayes_risk_scores_all_zones.csv").write_text("health_zone\nRethy\n")
    if harmonised_csv is not None:
        (ko / "harmonised_confirmed_cases.csv").write_text(harmonised_csv)
    return tmp_path


def test_loader_reads_counts_and_normalises_names(tmp_path, monkeypatch):
    csv = (
        "health_zone,cumulative_confirmed_cases\n"
        "Rethy,5\n"
        "Nsona-Pangu,3\n"   # needs _NAME_TO_NOM -> "Nsona Mpangu"
    )
    out = _make_key_outputs(tmp_path, csv)
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)
    result = ds.load_harmonised_confirmed_cases({"Rethy", "Nsona Mpangu"})
    assert result == {"Rethy": 5, "Nsona Mpangu": 3}


def test_loader_returns_empty_when_absent(tmp_path, monkeypatch):
    out = _make_key_outputs(tmp_path, None)
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)
    assert ds.load_harmonised_confirmed_cases({"Rethy"}) == {}


def test_write_effective_defaults_zero_and_takes_max():
    zone_data = {
        "Rethy": {"confirmed_cases": None},        # sitrep null
        "Bunia": {"confirmed_cases": 900},         # sitrep present
        "Ghost": {"confirmed_cases": None},        # in neither
    }
    harmonised = {"Rethy": 5, "Bunia": 10}         # Bunia harmonised < sitrep
    ds.write_effective_confirmed_cases(zone_data, harmonised)
    assert zone_data["Rethy"]["effective_confirmed_cases"] == 5   # harmonised wins
    assert zone_data["Bunia"]["effective_confirmed_cases"] == 900  # sitrep (fresher) wins
    assert zone_data["Ghost"]["effective_confirmed_cases"] == 0    # default 0, no crash
