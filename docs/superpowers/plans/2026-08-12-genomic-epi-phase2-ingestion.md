# Genomic tab Phase 2 — ingestion + payload slice + onset aggregation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest the `BDBV2026-Genomic_Epi` products and a new observed/imputed onset series into a single page-scoped `genomic` payload slice for the Genomic Epidemiology tab.

**Architecture:** Two new loaders in `data_sources.py` (phylo products from the `GENOMIC_DIR` sibling; onset aggregation from the imputed-onset linelist in `DASHBOARD_PLOTS_DIR/<date>/`), assembled into one `"genomic"` key in `build_shared_payload()`, page-scoped to `genomic-epidemiology` in `chrome.py`, with a CI checkout of the (public) producer repo. No engine/UI work — that is Phase 3+.

**Tech Stack:** Python 3.9 (run pytest with `PYTHONPATH=Scripts python3.9 -m pytest`); the dashboard's `common.*` modules; stdlib `csv`/`json`/`re`/`pathlib`.

**Scope guard:** Phase 2 is data plumbing only. Do NOT remove `genomic-epidemiology` from `STUB_VIEWS`, add panel markup, or touch `engine.js` — those are later phases. The slice is produced and page-scoped; the stub page simply carries it unused for now.

**Reference anchors (from research):**
- `paths.py:53-56` `DASHBOARD_PLOTS_DIR` (default `../BDBV2026-Processed_Sensitive_Data/outputs`); `paths.py:21-26` `BUILD_DIR` sibling convention.
- `data_sources.py:1648-1669` `_latest_spatiotemporal_key_outputs_dir()` — the newest-dated-dir scan to mirror.
- `data_sources.py:572-576` `_norm()`/`_NORM_RE` — zone-name normaliser.
- `data_sources.py:2943-2991` `load_metadata` builds `zone_data[nom]` (canonical key is `nom`).
- `payload.py:23` `build_shared_payload()`; `payload.py:117-120` `onset_trends = load_dashboard_plots(...)` (pattern); `payload.py:161-204` the returned dict literal.
- `chrome.py:448-450` `_PAGE_SCOPED_PAYLOAD_KEYS`; `chrome.py:468-473` the strip + `json.dumps`.
- `tests/test_harmonised_confirmed_cases.py` — monkeypatch-`DASHBOARD_PLOTS_DIR` + `tmp_path` test template.
- `.github/workflows/build-dashboard.yml:140-182` (two sibling checkouts + build env); `pr-preview.yml` mirrors it.
- Onset CSV columns: `health_zone`, `date_of_symptom_onset_imputed`, `onset_date_was_imputed` (`"TRUE"`/`"FALSE"`). Tree vintage: `meta.mostRecentDate` (`2026-06-23`), build stamp `meta.updated`.

---

## File structure

- Modify `Scripts/common/paths.py` — add `GENOMIC_DIR`.
- Modify `Scripts/common/data_sources.py` — add `load_genomic_products()`, `_latest_onset_linelist()`, `load_onset_imputed_series()`.
- Modify `Scripts/common/payload.py` — assemble the `"genomic"` key.
- Modify `Scripts/common/chrome.py` — page-scope `"genomic"`.
- Modify `.github/workflows/build-dashboard.yml` and `pr-preview.yml` — checkout the producer repo + set `GENOMIC_DIR`.
- Create `tests/test_genomic_products.py`, `tests/test_onset_imputed_series.py`, `tests/test_genomic_payload_scoping.py`.

---

## Task 1: `GENOMIC_DIR` path constant

**Files:** Modify `Scripts/common/paths.py` (near `DASHBOARD_PLOTS_DIR`, ~`:53-56`)

- [ ] **Step 1: Add the constant**

Add after the `DASHBOARD_PLOTS_DIR` block:
```python
# Genomic-epi phylo products (tree/tips/meta/skygrid/exponential), produced by the
# sibling repo INRB-UMIE/BDBV2026-Genomic_Epi. Default assumes it is cloned as a
# sibling (same convention as BUILD_DIR/DASHBOARD_PLOTS_DIR); override with GENOMIC_DIR.
GENOMIC_DIR = Path(
    os.environ.get("GENOMIC_DIR", str(Path(__file__).resolve().parents[2] / "BDBV2026-Genomic_Epi" / "public" / "data"))
).resolve()
```
Match the exact `os.environ.get(...)`/`Path(...).resolve()` idiom already used for `DASHBOARD_PLOTS_DIR` in this file (read `:53-56` first and mirror it — `parents[2]` should point at the workspace root that holds both repos; adjust the index to match how `BUILD_DIR` resolves the sibling).

- [ ] **Step 2: Verify it imports**

Run: `PYTHONPATH=Scripts python3.9 -c "from common.paths import GENOMIC_DIR; print(GENOMIC_DIR)"`
Expected: prints an absolute path ending `/BDBV2026-Genomic_Epi/public/data`.

- [ ] **Step 3: Commit**

```bash
git add Scripts/common/paths.py
git commit -m "Add GENOMIC_DIR path constant for the genomic-epi producer sibling"
```

---

## Task 2: `load_genomic_products()` loader

**Files:** Modify `Scripts/common/data_sources.py`; Test `tests/test_genomic_products.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_genomic_products.py
import importlib, json
from pathlib import Path

ds = importlib.import_module("common.data_sources")


def _seed(dirpath: Path):
    dirpath.mkdir(parents=True, exist_ok=True)
    (dirpath / "ituri-tree.ptree").write_text("#NEXUS\nBEGIN TREES;\ntree T = ((A,B),C);\nEND;\n")
    (dirpath / "ituri-tips.json").write_text(json.dumps([{"id": "A", "health_zone": "Bunia", "date": "2026-05-01"}]))
    (dirpath / "ituri-meta.json").write_text(json.dumps({"mostRecentDate": "2026-06-23", "updated": "2026-08-12", "tipCount": 1}))
    (dirpath / "skygrid.json").write_text(json.dumps({"time": [1, 2], "ne": [3, 4]}))
    (dirpath / "exponential.json").write_text(json.dumps({"growth": 0.07}))


def test_load_genomic_products_reads_all(tmp_path, monkeypatch):
    d = tmp_path / "gen"
    _seed(d)
    monkeypatch.setattr(ds, "GENOMIC_DIR", d)
    out = ds.load_genomic_products()
    assert out["tree"].startswith("#NEXUS")            # inline NEXUS text (PearTree `tree` key)
    assert out["tips"][0]["health_zone"] == "Bunia"
    assert out["meta"]["mostRecentDate"] == "2026-06-23"
    assert out["data_build_date"] == "2026-08-12"      # meta.updated, surfaced as the tab's vintage
    assert out["skygrid"]["ne"] == [3, 4]
    assert out["exponential"]["growth"] == 0.07


def test_load_genomic_products_absent_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "GENOMIC_DIR", tmp_path / "missing")
    assert ds.load_genomic_products() == {}          # build stays green if the sibling is absent
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/test_genomic_products.py -v`
Expected: FAIL — `AttributeError: module 'common.data_sources' has no attribute 'load_genomic_products'`.

- [ ] **Step 3: Implement the loader**

Add to `Scripts/common/data_sources.py` (ensure `from common.paths import ... GENOMIC_DIR` is included in the existing paths import, and `import json` is present):
```python
def load_genomic_products(genomic_dir=None):
    """Load the BDBV2026-Genomic_Epi products into a payload slice.

    Returns {} when the sibling repo isn't present, so a build without it stays
    green (the genomic tab is a stub until later phases wire it up). The tree is
    returned as inline NEXUS text (PearTree's embed accepts it under the `tree`
    key), so it needs no separate fetched asset.
    """
    d = Path(genomic_dir) if genomic_dir is not None else GENOMIC_DIR
    tree_path = d / "ituri-tree.ptree"
    if not tree_path.exists():
        return {}
    meta = json.loads((d / "ituri-meta.json").read_text(encoding="utf-8"))
    return {
        "tree": tree_path.read_text(encoding="utf-8"),
        "tips": json.loads((d / "ituri-tips.json").read_text(encoding="utf-8")),
        "meta": meta,
        "skygrid": json.loads((d / "skygrid.json").read_text(encoding="utf-8")),
        "exponential": json.loads((d / "exponential.json").read_text(encoding="utf-8")),
        "data_build_date": meta.get("updated"),
    }
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/test_genomic_products.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add Scripts/common/data_sources.py tests/test_genomic_products.py
git commit -m "Add load_genomic_products loader for the genomic phylo products"
```

---

## Task 3: `load_onset_imputed_series()` — observed/imputed onset aggregation

**Files:** Modify `Scripts/common/data_sources.py`; Test `tests/test_onset_imputed_series.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_onset_imputed_series.py
import importlib
from pathlib import Path

ds = importlib.import_module("common.data_sources")

CSV = (
    "health_zone,date_of_symptom_onset_imputed,onset_date_was_imputed\n"
    "Bunia,2026-05-01,FALSE\n"
    "Bunia,2026-05-01,TRUE\n"
    "Nyankunde,2026-07-01,FALSE\n"       # spelling variant of canonical 'Nyakunde'
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

    res = ds.load_onset_imputed_series(known_noms={"Bunia", "Nyakunde"}, tree_most_recent="2026-06-23")

    assert res["source"] == "2026-08-06"                         # newest dated dir
    assert res["national"]["2026-05-01"] == {"observed": 1, "imputed": 1}
    assert res["by_zone"]["Bunia"]["2026-05-01"] == {"observed": 1, "imputed": 1}
    assert res["by_zone"]["Nyakunde"]["2026-07-01"] == {"observed": 1, "imputed": 0}  # normalised
    assert "2026-05-02" not in res["national"]                   # missing-zone row dropped
    assert res["dates"] == ["2026-05-01", "2026-07-01"]
    assert res["beyond_tree_from"] == "2026-06-23"


def test_onset_absent_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", tmp_path / "nope")
    assert ds.load_onset_imputed_series(known_noms=set()) == {}
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/test_onset_imputed_series.py -v`
Expected: FAIL — no `load_onset_imputed_series` / `_latest_onset_linelist`.

- [ ] **Step 3: Implement the resolver + aggregator**

Add to `Scripts/common/data_sources.py` (ensure `import csv` and `import re` are present; reuse the module's existing `_norm`):
```python
_ONSET_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ONSET_CSV_NAME = "dhis2_linelist_with_imputed_onset.csv"


def _latest_onset_linelist(outputs_dir):
    """Newest dated `outputs/<date>/dhis2_linelist_with_imputed_onset.csv`, or None.

    Mirrors _latest_spatiotemporal_key_outputs_dir: pick the newest YYYY-MM-DD dir
    that actually contains the CSV (not manifest.json's date, whose cadence differs).
    """
    base = Path(outputs_dir)
    if not base.exists():
        return None
    dated = sorted(
        (p for p in base.iterdir()
         if p.is_dir() and _ONSET_DATE_RE.match(p.name) and (p / _ONSET_CSV_NAME).exists()),
        key=lambda p: p.name,
    )
    return (dated[-1] / _ONSET_CSV_NAME) if dated else None


def load_onset_imputed_series(outputs_dir=None, known_noms=None, tree_most_recent=None):
    """Aggregate the imputed-onset linelist to per-date/zone observed-vs-imputed
    counts for the genomic tab's sample-distribution panel. Returns {} if absent.

    Zone strings are joined to canonical `nom` via _norm against `known_noms`
    (the payload's zone_data keys); unmatched names pass through unchanged.
    `tree_most_recent` (meta.mostRecentDate) is echoed so the panel can mark the
    "beyond-tree" region (onset dates strictly after it).
    """
    path = _latest_onset_linelist(outputs_dir if outputs_dir is not None else DASHBOARD_PLOTS_DIR)
    if path is None:
        return {}
    nom_by_norm = {_norm(n): n for n in (known_noms or ())}

    def canon(name):
        return nom_by_norm.get(_norm(name), name)

    by_zone, national = {}, {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            d = (row.get("date_of_symptom_onset_imputed") or "").strip()
            z = (row.get("health_zone") or "").strip()
            if not d or not z:
                continue
            bucket = "imputed" if (row.get("onset_date_was_imputed") or "").strip().upper() == "TRUE" else "observed"
            zc = by_zone.setdefault(canon(z), {}).setdefault(d, {"observed": 0, "imputed": 0})
            zc[bucket] += 1
            nc = national.setdefault(d, {"observed": 0, "imputed": 0})
            nc[bucket] += 1
    return {
        "dates": sorted(national),
        "national": national,
        "by_zone": by_zone,
        "beyond_tree_from": tree_most_recent,
        "source": path.parent.name,
    }
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/test_onset_imputed_series.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add Scripts/common/data_sources.py tests/test_onset_imputed_series.py
git commit -m "Add observed/imputed onset aggregation from the canonical linelist"
```

---

## Task 4: Assemble the `genomic` payload key

**Files:** Modify `Scripts/common/payload.py`

- [ ] **Step 1: Add the assembly in `build_shared_payload()`**

Before the returned dict literal (after `zone_data` and `onset_trends` are built, ~`payload.py:130`), add:
```python
    genomic = load_genomic_products()
    if genomic:
        genomic["onset_distribution"] = load_onset_imputed_series(
            known_noms=set(zone_data),
            tree_most_recent=(genomic.get("meta") or {}).get("mostRecentDate"),
        )
```
(`load_genomic_products`/`load_onset_imputed_series` arrive via the existing `from common.data_sources import *` at `payload.py:17`. If `import *` does not re-export them because `data_sources` defines `__all__`, add them to that `__all__`; otherwise no change needed.)

- [ ] **Step 2: Add the key to the returned dict**

In the returned dict literal (`payload.py:161-204`), add a line alongside the other top-level keys:
```python
        "genomic": genomic,
```

- [ ] **Step 3: Verify the payload builds and carries the slice**

Run (with the producer cloned as a sibling at `../BDBV2026-Genomic_Epi`):
```bash
PYTHONPATH=Scripts python3.9 -c "
from common.payload import build_shared_payload
p = build_shared_payload()
g = p.get('genomic', {})
print('has tree:', bool(g.get('tree')), '| tips:', len(g.get('tips', [])), '| build date:', g.get('data_build_date'))
od = g.get('onset_distribution', {})
print('onset dates:', len(od.get('dates', [])), '| source:', od.get('source'), '| beyond_tree_from:', od.get('beyond_tree_from'))
"
```
Expected: `has tree: True | tips: 134 | build date: 2026-...` and a non-zero onset date count with a `source` date. (If the producer sibling is absent, `genomic` is `{}` — that's the intended graceful path; clone it to see the real slice.)

- [ ] **Step 4: Commit**

```bash
git add Scripts/common/payload.py
git commit -m "Assemble the page-scoped genomic payload slice (phylo products + onset)"
```

---

## Task 5: Page-scope `genomic` to the genomic tab

**Files:** Modify `Scripts/common/chrome.py` (`:448-450`); Test `tests/test_genomic_payload_scoping.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_genomic_payload_scoping.py
import importlib, json, re

chrome = importlib.import_module("common.chrome")


def _payload_from_html(html):
    m = re.search(r'<script id="payload" type="application/json">(.*?)</script>', html, re.S)
    assert m, "payload script block not found"
    return json.loads(m.group(1))


def test_genomic_key_only_on_genomic_page():
    payload = {"geometry": {"type": "FeatureCollection", "features": []},
               "zone_data": {}, "layers": [], "genomic": {"tree": "#NEXUS", "tips": []}}
    gen = _payload_from_html(chrome.render_page("genomic-epidemiology", payload))
    assert "genomic" in gen and gen["genomic"]["tree"] == "#NEXUS"
    other = _payload_from_html(chrome.render_page("trends", payload))
    assert "genomic" not in other            # stripped from every other page
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/test_genomic_payload_scoping.py -v`
Expected: FAIL — `genomic` present on the trends page (not yet scoped).

- [ ] **Step 3: Add the scope entry**

In `Scripts/common/chrome.py`, extend `_PAGE_SCOPED_PAYLOAD_KEYS` (`:448-450`):
```python
_PAGE_SCOPED_PAYLOAD_KEYS = {
    "import_force_pairwise": {"epi-trends"},
    "genomic": {"genomic-epidemiology"},
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/test_genomic_payload_scoping.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add Scripts/common/chrome.py tests/test_genomic_payload_scoping.py
git commit -m "Page-scope the genomic payload key to the genomic-epidemiology tab"
```

---

## Task 6: CI — checkout the producer repo and set `GENOMIC_DIR`

**Files:** Modify `.github/workflows/build-dashboard.yml` and `.github/workflows/pr-preview.yml`

- [ ] **Step 1: Add the checkout step (both workflows)**

After the existing "Checkout processed data repo" step (`build-dashboard.yml:148-154`), add — the producer repo is **public**, so no token is needed:
```yaml
      - name: Checkout genomic-epi producer repo
        uses: actions/checkout@v4
        with:
          repository: INRB-UMIE/BDBV2026-Genomic_Epi
          path: BDBV2026-Genomic_Epi
```
Add the identical step to `pr-preview.yml` at the matching point.

- [ ] **Step 2: Set `GENOMIC_DIR` in the build step (both workflows)**

In the build step's env (alongside `BUILD_DIR`/`DASHBOARD_PLOTS_DIR`, `build-dashboard.yml:166-182`), add:
```yaml
          GENOMIC_DIR: ${{ github.workspace }}/BDBV2026-Genomic_Epi/public/data
```
Mirror the exact `${{ github.workspace }}/...` form the neighbouring `BUILD_DIR`/`DASHBOARD_PLOTS_DIR` lines use (read those lines and match). Do the same in `pr-preview.yml`.

- [ ] **Step 3: (Optional) trigger on producer updates**

If the producer should retrigger the dashboard build on new products, note that `build-dashboard.yml` already accepts `repository_dispatch` types `data-updated`/`linelist-updated` (`:21-47`); a follow-up can add a `genomic-updated` type + a dispatch from the producer's CI. Leave a `# TODO(followup)` comment only if you add the type; otherwise record it in the findings, not the workflow.

- [ ] **Step 4: Validate YAML**

Run: `python3.9 -c "import yaml; yaml.safe_load(open('.github/workflows/build-dashboard.yml')); yaml.safe_load(open('.github/workflows/pr-preview.yml')); print('yaml ok')"`
Expected: `yaml ok`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/build-dashboard.yml .github/workflows/pr-preview.yml
git commit -m "CI: checkout the genomic-epi producer and set GENOMIC_DIR"
```

---

## Task 7: Full-build smoke check + suite green

**Files:** none (verification only)

- [ ] **Step 1: Run the whole pytest suite**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/ -q`
Expected: all tests pass (the 3 new files + the pre-existing ones).

- [ ] **Step 2: Build the dashboard and confirm the slice is present/scoped**

Run (producer sibling present):
```bash
cd Scripts && python3.9 build_dashboard.py && cd ..
python3.9 - <<'PY'
import re, json, pathlib
def payload(p):
    h = pathlib.Path(p).read_text()
    return json.loads(re.search(r'<script id="payload" type="application/json">(.*?)</script>', h, re.S).group(1))
g = payload("output/genomic-epidemiology.html").get("genomic", {})
t = payload("output/trends.html")
print("genomic on genomic page:", bool(g.get("tree")), "tips", len(g.get("tips", [])))
print("genomic absent on trends page:", "genomic" not in t)
PY
```
Expected: `genomic on genomic page: True tips 134` and `genomic absent on trends page: True`. (Note the build reads siblings `../BDBV2026-Data/build` and `../BDBV2026-Processed_Sensitive_Data/outputs`; see the build/test env notes.)

- [ ] **Step 3: Commit any incidental fixes, then report**

If Steps 1–2 surfaced fixes, commit them. Otherwise nothing to commit — Phase 2 is complete: the `genomic` slice (phylo products + onset series + data build date) is produced, page-scoped, tested, and wired into CI.

---

## Self-review notes
- **Graceful absence:** both loaders return `{}` when their sibling is missing, so a build without the producer/linelist stays green (matches how the tab is still a stub).
- **No conflation:** the new key is `"genomic"`; the pre-existing `genomic_sequence_count`/`genome_sequence_markers` (build-GeoJSON origin) are untouched.
- **Zone join:** onset zones normalise to canonical `nom` via `_norm` against `zone_data` keys; unmatched names pass through (they will simply not align to a map zone — acceptable for Phase 2, surfaced later if needed).
- **Out of scope (later phases):** removing `genomic-epidemiology` from `STUB_VIEWS`, the contribution seam, `genomic.js`, the panels, i18n.
