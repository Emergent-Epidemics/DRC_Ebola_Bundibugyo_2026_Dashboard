import importlib
import json
from pathlib import Path

ds = importlib.import_module("common.data_sources")

# The genomic "Confirmed positive cases" panel reads status_aggregated.csv --
# the SAME pre-aggregated table the Trends "Daily Cases by Symptom Onset" SVG is
# rendered from -- and counts ONLY its confirmed_case column. The big blank /
# not_a_case counts below MUST be ignored (that inclusion was the old bug). Rows
# are pre-summed per (date, onset_date_was_imputed, spatial_scale); the national
# series comes from spatial_scale=national, by_zone from spatial_scale=healthzone.
#
# The zone join only needs case/whitespace/punctuation folding (_norm): 'BUNIA '
# normalises to canonical 'Bunia'; a genuinely foreign name passes through.
CSV = (
    "date_of_symptom_onset_imputed,onset_date_was_imputed,confirmed_case,"
    "blank,not_a_case,spatial_scale,province,health_zone\n"
    "2026-05-01,FALSE,1,100,50,national,NA,NA\n"
    "2026-05-01,TRUE,1,0,0,national,NA,NA\n"
    "2026-07-01,FALSE,2,0,0,national,NA,NA\n"
    "2026-08-01,FALSE,0,80,80,national,NA,NA\n"      # dropped: 0 confirmed
    ",FALSE,3,0,0,national,NA,NA\n"                  # dropped: no date
    "2026-05-01,FALSE,9,0,0,province,Ituri,NA\n"     # ignored: province scale
    "2026-05-01,FALSE,1,0,0,healthzone,NA,Bunia\n"
    "2026-05-01,TRUE,1,0,0,healthzone,NA,Bunia\n"
    "2026-07-01,FALSE,1,0,0,healthzone,NA,  BUNIA \n"   # case/space -> 'Bunia'
    "2026-07-01,FALSE,1,0,0,healthzone,NA,Zzz Unknown\n"  # foreign -> passes through
)

# A decoy snapshot that would break every assertion if it were picked instead of
# the manifest-selected one -- guards the "same snapshot as the SVG" resolution.
DECOY_CSV = (
    "date_of_symptom_onset_imputed,onset_date_was_imputed,confirmed_case,"
    "spatial_scale,province,health_zone\n"
    "2026-05-01,FALSE,999,national,NA,NA\n"
)


def _seed(base: Path, date: str, csv_text: str):
    d = base / date
    d.mkdir(parents=True, exist_ok=True)
    (d / "status_aggregated.csv").write_text(csv_text)
    return d


def test_onset_counts_confirmed_only_by_date_zone_and_normalises(tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    _seed(out, "2026-08-05", CSV)          # manifest snapshot (the SVG's dir)
    _seed(out, "2026-08-06", DECOY_CSV)    # newer, but NOT the manifest date
    # manifest.json points the onset SVGs (and now this panel) at 2026-08-05,
    # not the newest dir -- so the decoy must be ignored.
    (out / "manifest.json").write_text(json.dumps({"date": "2026-08-05"}))
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)

    res = ds.load_onset_imputed_series(known_noms={"Bunia"}, tree_most_recent="2026-06-23")

    assert res["source"] == "2026-08-05"                         # manifest snapshot, not newest
    # confirmed_case only: the 100/50 blank/not_a_case counts are ignored.
    assert res["national"]["2026-05-01"] == {"observed": 1, "imputed": 1}
    assert res["national"]["2026-07-01"] == {"observed": 2, "imputed": 0}
    assert "2026-08-01" not in res["national"]                   # 0 confirmed dropped
    assert "2026-05-02" not in res["national"]                   # (no such date)
    assert res["by_zone"]["Bunia"]["2026-05-01"] == {"observed": 1, "imputed": 1}
    assert res["by_zone"]["Bunia"]["2026-07-01"] == {"observed": 1, "imputed": 0}  # normalised
    assert "Zzz Unknown" in res["by_zone"]                        # foreign zone passes through
    assert set(res["by_zone"]) == {"Bunia", "Zzz Unknown"}       # province scale not counted
    assert res["dates"] == ["2026-05-01", "2026-07-01"]
    assert res["beyond_tree_from"] == "2026-06-23"


def test_onset_falls_back_to_newest_dir_without_manifest(tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    _seed(out, "2026-08-05", DECOY_CSV)
    _seed(out, "2026-08-06", CSV)          # newest; no manifest -> picked
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)

    res = ds.load_onset_imputed_series(known_noms={"Bunia"})

    assert res["source"] == "2026-08-06"
    assert res["national"]["2026-05-01"] == {"observed": 1, "imputed": 1}


def test_onset_absent_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", tmp_path / "nope")
    assert ds.load_onset_imputed_series(known_noms=set()) == {}
