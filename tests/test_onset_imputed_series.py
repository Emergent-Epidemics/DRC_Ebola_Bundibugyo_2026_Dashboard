import importlib
from pathlib import Path

ds = importlib.import_module("common.data_sources")

# Real onset linelists carry canonical-ish zone names; the join only needs
# case/whitespace/punctuation folding (_norm), verified against live data to
# match every one of the 109 real zones. So the normalisation case here is a
# case/space variant of a canonical nom (not a letter-level alias, which _norm
# neither does nor needs to). A genuinely foreign name passes through unmatched.
CSV = (
    "health_zone,date_of_symptom_onset_imputed,onset_date_was_imputed\n"
    "Bunia,2026-05-01,FALSE\n"
    "Bunia,2026-05-01,TRUE\n"
    "  BUNIA ,2026-07-01,FALSE\n"        # case/space variant → normalises to 'Bunia'
    "Zzz Unknown,2026-07-01,FALSE\n"     # not canonical → passes through as-is
    "Bunia,,FALSE\n"                      # dropped: no date
    ",2026-05-02,FALSE\n"                # dropped: no zone
)


def _seed_outputs(base: Path, date: str):
    d = base / date
    d.mkdir(parents=True, exist_ok=True)
    (d / "dhis2_linelist_with_imputed_onset.csv").write_text(CSV)
    return d


def test_onset_aggregates_by_date_zone_and_normalises(tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    _seed_outputs(out, "2026-08-05")
    _seed_outputs(out, "2026-08-06")   # newer — must be the one picked
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)

    res = ds.load_onset_imputed_series(known_noms={"Bunia"}, tree_most_recent="2026-06-23")

    assert res["source"] == "2026-08-06"                         # newest dated dir
    assert res["national"]["2026-05-01"] == {"observed": 1, "imputed": 1}
    assert res["national"]["2026-07-01"] == {"observed": 2, "imputed": 0}
    assert res["by_zone"]["Bunia"]["2026-05-01"] == {"observed": 1, "imputed": 1}
    assert res["by_zone"]["Bunia"]["2026-07-01"] == {"observed": 1, "imputed": 0}  # normalised
    assert "Zzz Unknown" in res["by_zone"]                        # foreign zone passes through
    assert "2026-05-02" not in res["national"]                   # missing-zone row dropped
    assert res["dates"] == ["2026-05-01", "2026-07-01"]
    assert res["beyond_tree_from"] == "2026-06-23"


def test_onset_absent_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", tmp_path / "nope")
    assert ds.load_onset_imputed_series(known_noms=set()) == {}
