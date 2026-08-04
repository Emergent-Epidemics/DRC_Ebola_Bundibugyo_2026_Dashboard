import importlib
from pathlib import Path
import pytest

ds = importlib.import_module("common.data_sources")

PAIRWISE_CSV = (
    "origin_zone,dest_zone,horizon,w_ji,source_origin,import_force,foi,"
    "dest_import_force_total,dest_hazard_week,share_of_dest,origin_province,dest_province\n"
    "Bunia,Aba,1,0.1,10,1.0,0.16,2.0,0.32,0.5,Ituri,Haut-Uele\n"
    "Nizi,Aba,1,0.05,4,0.2,0.032,2.0,0.32,0.1,Ituri,Haut-Uele\n"
    "Bunia,Aba,2,0.1,12,1.2,0.192,2.4,0.384,0.5,Ituri,Haut-Uele\n"
    "Ghost,Aba,1,0.0,0,0.0,0.0,2.0,0.32,0.0,Ituri,Haut-Uele\n"
)


def _make_outputs(tmp_path: Path) -> Path:
    ko = tmp_path / "2026-08-03" / "spatiotemporal" / "key_outputs"
    ko.mkdir(parents=True)
    (ko / "bayes_risk_scores_all_zones.csv").write_text("health_zone\nAba\n")
    reports = ko.parent / "reports"
    reports.mkdir()
    (reports / "bayes_pairwise_import_force.csv").write_text(PAIRWISE_CSV)
    return tmp_path


def test_loader_builds_sorted_h1_edges(tmp_path, monkeypatch):
    out = _make_outputs(tmp_path)
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)
    result = ds.load_bayes_import_force_pairwise()
    assert result is not None
    assert result["horizon"] == 1
    edges = result["in_by_dest"]["Aba"]
    assert [e[0] for e in edges] == ["Bunia", "Nizi"]
    assert edges[0][1] == pytest.approx(0.16)
    assert edges[0][2] == pytest.approx(0.5)
    assert result["beta"] == pytest.approx(0.16, rel=1e-6)


def test_loader_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", tmp_path)
    assert ds.load_bayes_import_force_pairwise() is None


def test_loader_returns_none_when_report_missing(tmp_path, monkeypatch):
    # key_outputs (risk scores) present but the pairwise reports CSV not yet written
    out = _make_outputs(tmp_path)
    (out / "2026-08-03" / "spatiotemporal" / "reports"
     / "bayes_pairwise_import_force.csv").unlink()
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)
    assert ds.load_bayes_import_force_pairwise() is None


FLOAT_HORIZON_CSV = (
    "origin_zone,dest_zone,horizon,w_ji,source_origin,import_force,foi,"
    "dest_import_force_total,dest_hazard_week,share_of_dest,origin_province,dest_province\n"
    "Bunia,Aba,1,0.1,10,1.0,0.16,2.0,0.32,0.5,Ituri,Haut-Uele\n"
    "Nizi,Aba,,0.05,4,0.2,0.032,2.0,0.32,0.1,Ituri,Haut-Uele\n"
)


def test_loader_handles_float_horizon_column(tmp_path, monkeypatch):
    out = _make_outputs(tmp_path)
    (out / "2026-08-03" / "spatiotemporal" / "reports"
     / "bayes_pairwise_import_force.csv").write_text(FLOAT_HORIZON_CSV)
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)
    result = ds.load_bayes_import_force_pairwise()
    assert result is not None
    assert [e[0] for e in result["in_by_dest"]["Aba"]] == ["Bunia"]


def test_loader_returns_none_on_missing_columns(tmp_path, monkeypatch):
    out = _make_outputs(tmp_path)
    (out / "2026-08-03" / "spatiotemporal" / "reports"
     / "bayes_pairwise_import_force.csv").write_text(
        "origin_zone,dest_zone,horizon\nBunia,Aba,1\n")
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)
    assert ds.load_bayes_import_force_pairwise() is None
