# Harmonised Confirmed Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface the invasion model's harmonised (line-list ∪ sitrep) per-zone confirmed counts to the dashboard so zones confirmed by the line list but absent from the sitrep (e.g. Rethy, Bafwasende) render as active-case zones instead of white on the spatial-risk map.

**Architecture:** The R model emits a new `harmonised_confirmed_cases.csv` into its `key_outputs/`. The dashboard build loads it, computes `effective = max(harmonised, sitrep)` into every `zone_data` rec **before** markers are built, and the engine reads `effective` for the spatial-risk colour domain, fill, markers, and arrows. All other tabs stay sitrep-sourced. Freshness is handled by the `max()` top-up (interim) until an upstream sitrep-trigger lands (out of scope).

**Tech Stack:** Python 3.9 (build: `Scripts/common/*.py`, pandas), pytest (`cd Scripts && python3.9 -m pytest ../tests -v`), vanilla JS + Leaflet (`Scripts/assets/engine.js`), R (`BDBV2026-Analysis/spatiotemporal/`).

**Spec:** `docs/superpowers/specs/2026-08-06-harmonised-confirmed-cases-design.md`

---

## File Structure

**Part A — Dashboard build (Python), this repo — TDD with pytest:**
- Modify `Scripts/common/data_sources.py` — new `load_harmonised_confirmed_cases()` loader; `build_active_case_markers` gate switch (`:3049`); `load_invasion_risk_estimates` download-mask (`:1669`); `__all__` (`:130`). **Do NOT edit `Scripts/build_dashboard_public.py` (dead monolith).**
- Modify `Scripts/common/payload.py` — compute+write `effective_confirmed_cases` before line 97; call coverage assertion after line 116.
- Create `tests/test_harmonised_confirmed_cases.py` — loader + effective + coverage + download-mask tests.

**Part B — Dashboard engine (JS), this repo — implement + build + browser-verify:**
- Modify `Scripts/assets/engine.js` — `recomputeEpiTrends` domain (`:1259`), `epiTrendsStyleFn` fill + defensive no-data fill (`:1304`), `zoneConfirmedCases` (`:635`). Marker tooltip needs **no** change (build populates `confirmed=effective`; suspected/deaths kept per M3).

**Part C — Upstream delivery (separate repos):**
- Modify `BDBV2026-Analysis/spatiotemporal/run_all.R` — write CSV + add to key_outputs gather list.
- Modify `BDBV2026-Processed_Sensitive_Data/.github/workflows/run-spatiotemporal.yml` — `ANALYSIS_REF` bump.
- *(Different toolchain/repos; may be run as its own plan session. Part A is developed and tested against a fixture CSV and does not block on Part C.)*

---

## Part A — Dashboard build (Python)

### Task 1: Harmonised loader `load_harmonised_confirmed_cases`

**Files:**
- Modify: `Scripts/common/data_sources.py` (add function after `load_invasion_risk_estimates` ends; add name to `__all__` near `:131`)
- Test: `tests/test_harmonised_confirmed_cases.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_harmonised_confirmed_cases.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py -v`
Expected: FAIL with `AttributeError: module 'common.data_sources' has no attribute 'load_harmonised_confirmed_cases'`

- [ ] **Step 3: Add the loader**

In `Scripts/common/data_sources.py`, add to the `__all__` list (right after `'load_bayes_import_force_pairwise',` at `:131`):

```python
    'load_harmonised_confirmed_cases',
```

Add the function immediately after `load_bayes_import_force_pairwise()` ends (before `reconcile_invasion_active_cases`):

```python
def load_harmonised_confirmed_cases(valid_noms: set[str]) -> dict[str, int]:
    """Per-zone harmonised (line-list ∪ sitrep) cumulative confirmed cases.

    Read from the newest dated
    ``spatiotemporal/key_outputs/harmonised_confirmed_cases.csv`` (same dir as
    ``bayes_risk_scores_all_zones.csv``). Keys are GeoJSON ``nom`` after
    ``_NAME_TO_NOM`` normalisation. Returns {} when the file is absent (the
    dashboard then falls back to sitrep-only ``effective``). Warns on any
    ``health_zone`` that does not match a GeoJSON ``nom``.
    """
    ko = _latest_spatiotemporal_key_outputs_dir()
    if ko is None:
        print("  NOTE: no spatiotemporal key_outputs dir; "
              "harmonised confirmed cases unavailable")
        return {}
    csv_path = ko / "harmonised_confirmed_cases.csv"
    if not csv_path.exists():
        print(f"  NOTE: {csv_path.name} not found; "
              "harmonised confirmed cases unavailable")
        return {}
    df = pd.read_csv(csv_path)
    df.columns = [str(c).strip() for c in df.columns]
    required = {"health_zone", "cumulative_confirmed_cases"}
    missing = required - set(df.columns)
    if missing:
        print(f"  WARNING: {csv_path.name} missing columns: {sorted(missing)}")
        return {}
    out: dict[str, int] = {}
    for _, row in df.iterrows():
        raw = str(row.get("health_zone") or "").strip()
        if not raw:
            continue
        nom = _NAME_TO_NOM.get(raw, raw)
        val = pd.to_numeric(row.get("cumulative_confirmed_cases"), errors="coerce")
        if pd.isna(val):
            continue
        out[nom] = int(val)
        if nom not in valid_noms:
            print(f"  WARNING: harmonised zone '{raw}'->'{nom}' "
                  "not in GeoJSON nom set (dropped from map)")
    print(f"  harmonised confirmed cases: {len(out)} zones")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add Scripts/common/data_sources.py tests/test_harmonised_confirmed_cases.py
git commit -m "Add harmonised confirmed-cases loader"
```

---

### Task 2: Write `effective_confirmed_cases` into every zone (default 0), before markers

**Files:**
- Modify: `Scripts/common/payload.py` (insert after `load_metadata` at `:34`, before `build_active_case_markers` at `:97`)
- Test: `tests/test_harmonised_confirmed_cases.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_harmonised_confirmed_cases.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py::test_write_effective_defaults_zero_and_takes_max -v`
Expected: FAIL with `AttributeError: ... has no attribute 'write_effective_confirmed_cases'`

- [ ] **Step 3: Add the helper in `data_sources.py`**

Add near `build_active_case_markers` in `Scripts/common/data_sources.py`, and add `'write_effective_confirmed_cases',` to `__all__`:

```python
def write_effective_confirmed_cases(zone_data: dict[str, dict],
                                    harmonised: dict[str, int]) -> None:
    """Write ``effective_confirmed_cases = max(harmonised, sitrep)`` into EVERY
    zone rec, defaulting to 0. Must run before build_active_case_markers so the
    markers (and later the engine) read it. A zone left undefined re-triggers the
    white-zone bug in the engine, so the default-0 write for all zones is required.
    """
    for nom, rec in zone_data.items():
        h = harmonised.get(nom, 0) or 0
        s = rec.get("confirmed_cases") or 0
        rec["effective_confirmed_cases"] = max(int(h), int(s))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py::test_write_effective_defaults_zero_and_takes_max -v`
Expected: PASS

- [ ] **Step 5: Wire it into `payload.py` before line 97**

In `Scripts/common/payload.py`, immediately after `zone_data, case_totals = load_metadata(...)` (`:34`) and before `build_active_case_markers(...)` (`:97`), add:

```python
    # Harmonised (line-list ∪ sitrep) confirmed counts from the model, topped up
    # with the dashboard's (fresher) live sitrep. MUST precede build_active_case_markers.
    harmonised_confirmed = load_harmonised_confirmed_cases(set(zone_data))
    write_effective_confirmed_cases(zone_data, harmonised_confirmed)
```

- [ ] **Step 6: Run the full suite + commit**

Run: `cd Scripts && python3.9 -m pytest ../tests -v`
Expected: PASS (no regressions)

```bash
git add Scripts/common/data_sources.py Scripts/common/payload.py tests/test_harmonised_confirmed_cases.py
git commit -m "Compute effective confirmed cases into zone_data before markers"
```

---

### Task 3: Gate active-case markers on `effective_confirmed_cases`

**Files:**
- Modify: `Scripts/common/data_sources.py` `build_active_case_markers` (`:3049`, the live copy — NOT the monolith)
- Test: `tests/test_harmonised_confirmed_cases.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_harmonised_confirmed_cases.py`:

```python
def test_markers_use_effective_and_keep_sitrep_suspected():
    zone_data = {
        "Rethy": {"confirmed_cases": None, "suspected_cases": 0,
                  "confirmed_deaths": 0, "effective_confirmed_cases": 5},
        "Empty": {"confirmed_cases": None, "suspected_cases": 0,
                  "confirmed_deaths": 0, "effective_confirmed_cases": 0},
    }
    centroids = {"Rethy": (30.5, 2.0), "Empty": (25.0, 1.0)}
    markers = ds.build_active_case_markers(zone_data, centroids)
    by_nom = {m["nom"]: m for m in markers}
    assert "Rethy" in by_nom              # harmonised-only zone now gets a marker
    assert by_nom["Rethy"]["confirmed"] == 5
    assert by_nom["Rethy"]["suspected"] == 0   # sitrep field still emitted
    assert "Empty" not in by_nom          # effective 0 -> no marker
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py::test_markers_use_effective_and_keep_sitrep_suspected -v`
Expected: FAIL — `Rethy` missing (gated on `confirmed_cases`, which is None) and/or `confirmed` == 0.

- [ ] **Step 3: Switch the gate + emitted count to effective**

In `build_active_case_markers` (`Scripts/common/data_sources.py:3049`), change the two lines that read `confirmed_cases`:

```python
        conf = int(rec.get("effective_confirmed_cases") or 0)
        if conf <= 0:
            continue
```

Leave `susp`, `confirmed_deaths`, `suspected_deaths`, and `total = conf + susp` as-is (suspected/deaths stay sitrep-sourced per M3; note `total` is now mixed-source — covered by the M4 support note).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add Scripts/common/data_sources.py tests/test_harmonised_confirmed_cases.py
git commit -m "Gate active-case markers on effective confirmed cases"
```

---

### Task 4: Active-zone coverage assertion (after invasion load)

**Files:**
- Modify: `Scripts/common/data_sources.py` (new `assert_harmonised_coverage`), `Scripts/common/payload.py` (call after `:116`/`:121`)
- Test: `tests/test_harmonised_confirmed_cases.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
import pytest

def test_coverage_assertion_flags_active_zone_without_count():
    invasion_risk = {"zones": {
        "Rethy": {"was_active_before": True},
        "Aba":   {"was_active_before": False},
    }}
    ok = {"Rethy": {"effective_confirmed_cases": 5},
          "Aba":   {"effective_confirmed_cases": 0}}
    ds.assert_harmonised_coverage(invasion_risk, ok)     # no raise

    bad = {"Rethy": {"effective_confirmed_cases": 0},     # active but 0 -> invariant broken
           "Aba":   {"effective_confirmed_cases": 0}}
    with pytest.raises(ValueError, match="Rethy"):
        ds.assert_harmonised_coverage(invasion_risk, bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py::test_coverage_assertion_flags_active_zone_without_count -v`
Expected: FAIL — `has no attribute 'assert_harmonised_coverage'`

- [ ] **Step 3: Add the assertion** (in `data_sources.py`, add to `__all__`)

```python
def assert_harmonised_coverage(invasion_risk: dict | None,
                               zone_data: dict) -> None:
    """Build-time guard for the §5 invariant: every ``was_active_before`` zone
    must carry effective_confirmed_cases > 0. A silent gap here re-creates the
    white-zone bug, so fail the build loudly. Runs AFTER load_invasion_risk_estimates
    (that's when was_active_before is known)."""
    if not invasion_risk:
        return
    broken = [
        nom for nom, row in (invasion_risk.get("zones") or {}).items()
        if row.get("was_active_before")
        and int((zone_data.get(nom) or {}).get("effective_confirmed_cases") or 0) <= 0
    ]
    if broken:
        raise ValueError(
            "Active-before zones with no harmonised/effective count "
            f"(invariant broken, would render white): {sorted(broken)}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py::test_coverage_assertion_flags_active_zone_without_count -v`
Expected: PASS

- [ ] **Step 5: Wire into `payload.py`** after `reconcile_invasion_active_cases(...)` (`:121`):

```python
    assert_harmonised_coverage(invasion_risk, zone_data)
```

- [ ] **Step 6: Run suite + commit**

Run: `cd Scripts && python3.9 -m pytest ../tests -v` → PASS

```bash
git add Scripts/common/data_sources.py Scripts/common/payload.py tests/test_harmonised_confirmed_cases.py
git commit -m "Assert active-zone harmonised coverage at build time"
```

---

### Task 5: Mask the downloadable invasion CSV to match the map (S5)

**Files:**
- Modify: `Scripts/common/data_sources.py` `load_invasion_risk_estimates` (`:1669`; `download_csv` capture `:1744`; reconcile docstring `:2036`)
- Modify: `Scripts/common/payload.py` (pass effective-active noms into the loader)
- Test: `tests/test_harmonised_confirmed_cases.py`

- [ ] **Step 1: Write the failing test**

Append (extend `_make_key_outputs` to also write a risk-scores CSV with rows):

```python
def test_download_csv_masked_for_effective_active(tmp_path, monkeypatch):
    ko = tmp_path / "2026-08-03" / "spatiotemporal" / "key_outputs"
    ko.mkdir(parents=True)
    (ko / "bayes_risk_scores_all_zones.csv").write_text(
        "health_zone,horizon,was_active_before,p_case_invasion\n"
        "Rethy,1,False,0.34\n"
        "Rethy,2,False,0.53\n"
        "Aba,1,False,0.10\n"
    )
    (ko / "run_info.json").write_text('{"training_window_end": "2026-07-20"}')
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", tmp_path)
    result = ds.load_invasion_risk_estimates(effective_active_noms={"Rethy"})
    dl = result["download_csv"]
    # every Rethy row (all horizons) has p_case_invasion blanked; Aba untouched
    assert ",0.34" not in dl and ",0.53" not in dl
    assert "0.10" in dl
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py::test_download_csv_masked_for_effective_active -v`
Expected: FAIL — `load_invasion_risk_estimates() got an unexpected keyword argument 'effective_active_noms'`

- [ ] **Step 3: Add the parameter + mask before `download_csv` capture**

In `load_invasion_risk_estimates` change the signature to:

```python
def load_invasion_risk_estimates(effective_active_noms: set[str] | None = None) -> dict | None:
```

Immediately before the `download_csv = df.to_csv(index=False)` line (`:1744`), insert:

```python
    # S5: mask the downloadable CSV to match the map — null the invasion fields
    # for zones the dashboard renders as active (effective>0), across ALL horizon
    # rows. Reverses the old "download_csv left untouched" behaviour, by decision.
    if effective_active_noms:
        _norm = df["health_zone"].astype(str).str.strip().map(
            lambda n: _NAME_TO_NOM.get(n, n))
        mask = _norm.isin(effective_active_noms)
        for col in _INVASION_AFFECTED_MASK_FIELDS:
            if col in df.columns:
                df.loc[mask, col] = None
```

Update the `reconcile_invasion_active_cases` docstring line (`:2036`) from "The raw `download_csv` is left untouched." to:

```python
    left untouched here; download masking now happens in load_invasion_risk_estimates
    (S5) so the downloaded CSV matches the reconciled map.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_harmonised_confirmed_cases.py::test_download_csv_masked_for_effective_active -v`
Expected: PASS

- [ ] **Step 5: Pass the noms from `payload.py`**

In `Scripts/common/payload.py`, change the `load_invasion_risk_estimates()` call (`:116`) to:

```python
    _eff_active = {n for n, r in zone_data.items()
                   if int(r.get("effective_confirmed_cases") or 0) > 0}
    invasion_risk = load_invasion_risk_estimates(effective_active_noms=_eff_active)
```

- [ ] **Step 6: Run suite + commit**

Run: `cd Scripts && python3.9 -m pytest ../tests -v` → PASS

```bash
git add Scripts/common/data_sources.py Scripts/common/payload.py tests/test_harmonised_confirmed_cases.py
git commit -m "Mask downloadable invasion CSV to match reconciled map"
```

---

## Part B — Dashboard engine (JS)

> No JS unit-test harness exists. Each engine task: implement, run the build, then verify in the browser. Build needs the sibling data repo present at `../BDBV2026-Data/build`.
> **Build:** `python3.9 Scripts/build_dashboard.py` then `cp output/spatial-risk.html spatial-risk.html && rm -rf assets && cp -r output/assets assets`.
> **Serve/view:** `python3.9 -m http.server 8000` in repo root, open `http://localhost:8000/spatial-risk.html` (the Chrome extension blocks `file://`).

### Task 6: Colour domain reads `effective` (S1)

**Files:**
- Modify: `Scripts/assets/engine.js` `recomputeEpiTrends` (`~:1259-1268`)

- [ ] **Step 1: Switch the domain source**

In `recomputeEpiTrends`, the active-zone branch that fills `caseVals` currently reads `z.confirmed_cases`. Change it to `effective_confirmed_cases`:

```javascript
    if (row.was_active_before) {
      const z = ZONE_DATA[nom] || {};
      const c = z.effective_confirmed_cases;
      if (c != null && !Number.isNaN(Number(c)) && Number(c) > 0) caseVals.push(Number(c));
    } else if (row.p_case_invasion != null && !Number.isNaN(row.p_case_invasion)) {
      invasionVals.push(row.p_case_invasion);
    }
```

- [ ] **Step 2: Build**

Run: `python3.9 Scripts/build_dashboard.py`
Expected: build completes; console prints `harmonised confirmed cases: N zones` and `active-case markers: M zones`.

- [ ] **Step 3: Verify the payload carries the field**

Run: `python3.9 -c "import re,json; h=open('output/spatial-risk.html').read(); p=json.loads(re.search(r'<script id=\"payload\" type=\"application/json\">(.*?)</script>',h,re.S).group(1)); z=p['zone_data']; print('Rethy eff=', z.get('Rethy',{}).get('effective_confirmed_cases'), 'Bafwasende eff=', z.get('Bafwasende',{}).get('effective_confirmed_cases'))"`
Expected: both print a non-null number (0 or positive; positive if the live harmonised artifact is present — otherwise sitrep-only until Part C ships).

- [ ] **Step 4: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "Spatial-risk colour domain reads effective confirmed cases"
```

### Task 7: Fill by `effective` + defensive no-data fill (H2)

**Files:**
- Modify: `Scripts/assets/engine.js` `epiTrendsStyleFn` (`~:1304-1337`)

- [ ] **Step 1: Colour the orange path by effective**

In `epiTrendsStyleFn`, the `was_active_before` branch reads `z.confirmed_cases`. Change the value source to `effective_confirmed_cases`:

```javascript
  if (row.was_active_before) {
    const z = ZONE_DATA[ref] || {};
    const v = z.effective_confirmed_cases;
    if (v != null && !Number.isNaN(Number(v))) {
      has = true;
      const num = Number(v);
      if (num <= 0) fill = ZERO_FILL;
      else {
        let t = (Math.log(num) - Math.log(epiCasesDomain.min)) /
          (Math.log(epiCasesDomain.max) - Math.log(epiCasesDomain.min) || 1);
        if (!isFinite(t)) t = 0;
        t = Math.max(0, Math.min(1, t));
        fill = rgb(lerpColor(epiCasesDomain.palette, t));
      }
    }
  } else if (row.p_case_invasion != null && !Number.isNaN(row.p_case_invasion)) {
    ...unchanged...
  }
```

- [ ] **Step 2: Replace the transparent fall-through with a visible no-data fill**

Add a module-level constant near `ZERO_FILL` (`~:1389`):

```javascript
const NODATA_FILL = "#7d7d7d";   // fail-loud: an active zone with no count (should never happen)
```

Change the `if (!has)` return (`~:1335-1337`) from `fillOpacity: 0` to a visible fill:

```javascript
  if (!has) {
    return {color: "#111", weight: zoomWeight(0.35), fillColor: NODATA_FILL, fillOpacity: 0.55};
  }
```

- [ ] **Step 3: Build + browser-verify**

Run: `python3.9 Scripts/build_dashboard.py && cp output/spatial-risk.html spatial-risk.html && rm -rf assets && cp -r output/assets assets`
Then serve (`python3.9 -m http.server 8000`) and open `http://localhost:8000/spatial-risk.html`.
Expected (with the live harmonised artifact present): Rethy and Bafwasende render **orange** (not white/grey). With no artifact yet: they render either orange (if sitrep has them) or the grey `NODATA_FILL` if truly countless — never transparent.

- [ ] **Step 4: Commit**

```bash
git add Scripts/assets/engine.js spatial-risk.html assets/engine.js
git commit -m "Spatial-risk fill reads effective; defensive no-data fill replaces transparent"
```

### Task 8: Arrows read `effective` (FP-3)

**Files:**
- Modify: `Scripts/assets/engine.js` `zoneConfirmedCases` (`~:635`)

- [ ] **Step 1: Switch the arrow weight source**

`zoneConfirmedCases` (`engine.js:635-640`) currently reads `z.confirmed_cases`. Change that one line to `z.effective_confirmed_cases`; the function is otherwise unchanged:

```javascript
function zoneConfirmedCases(nom) {
  const z = ZONE_DATA[nom];
  if (!z) return 0;
  const c = Number(z.effective_confirmed_cases);
  return (isFinite(c) && c > 0) ? c : 0;
}
```

- [ ] **Step 2: Build + verify**

Run: `python3.9 Scripts/build_dashboard.py && cp output/spatial-risk.html spatial-risk.html && rm -rf assets && cp -r output/assets assets`
Serve, open spatial-risk, select a harmonised-only zone (Rethy) as a flow hub: confirmed-cases-based arrows into it are non-zero (when `IMPORT_FORCE_PAIRWISE` is absent; otherwise pairwise arrows show and this path is superseded).

- [ ] **Step 3: Commit**

```bash
git add Scripts/assets/engine.js spatial-risk.html assets/engine.js
git commit -m "Spatial-risk arrows weight by effective confirmed cases"
```

---

## Part C — Upstream delivery (separate repos)

> Different repos/toolchain. Part A/B are fully developed and tested against a fixture and do not block on this. Recommend running Part C as its own short plan session in `BDBV2026-Analysis`. Tasks captured here so nothing is lost.

### Task 9: Emit `harmonised_confirmed_cases.csv` from the live model tree

**Files:**
- Modify: `BDBV2026-Analysis/spatiotemporal/run_all.R` (write near `:898` where `bayes_risk_scores_all_zones.csv` is written; gather list `:1453-1481`)

- [ ] **Step 1:** Compute the per-zone cumulative confirmed count from `zone_week` at `training_window_end` (the same cutoff `affected_zones(zone_week, cutoff)` uses), one row per zone: columns `health_zone, cumulative_confirmed_cases`.
- [ ] **Step 2:** Write it to `OUT_REPORTS` (mirror the `.write_risk_csv(...)` call at `:898`).
- [ ] **Step 3:** Add `"reports/harmonised_confirmed_cases.csv"` to the `key_outputs/` gather list (`:1453-1481`) so it is copied into `key_outputs/`.
- [ ] **Step 4:** Run the pipeline (or a targeted step) on a sample extract; assert in R that `cumulative_confirmed_cases > 0` ⟺ the zone is in `affected_now` (the §5 invariant, at the cutoff).
- [ ] **Step 5:** Commit in `BDBV2026-Analysis`.

### Task 10: Bump `ANALYSIS_REF` so the artifact ships

**Files:**
- Modify: `BDBV2026-Processed_Sensitive_Data/.github/workflows/run-spatiotemporal.yml` (`ANALYSIS_REF` default, `~:49`)

- [ ] **Step 1:** Set `ANALYSIS_REF` to the `BDBV2026-Analysis` commit from Task 9.
- [ ] **Step 2:** Trigger `run-spatiotemporal.yml` (or let the line-list chain fire); confirm `collect_outputs.sh` publishes `key_outputs/harmonised_confirmed_cases.csv` into `outputs/<date>/spatiotemporal/key_outputs/` on `main`.
- [ ] **Step 3:** Confirm `trigger-dashboard-rebuild.yml` rebuilds and the live spatial-risk map shows Rethy/Bafwasende orange with a count.

---

## Final verification

- [ ] **Full test suite:** `cd Scripts && python3.9 -m pytest ../tests -v` → all PASS.
- [ ] **Clean build:** `python3.9 Scripts/build_dashboard.py` → completes; coverage assertion does not raise.
- [ ] **Browser regression:** serve and confirm on `spatial-risk.html` that no health zone renders transparent/white; Rethy and Bafwasende (or the current run's harmonised-only zones) render as orange active-case zones; the Snapshot tab's Total/Confirmed/Suspected layers are unchanged.
- [ ] **Support note (M4):** add a short note (README or the methods doc) that active-case markers use harmonised confirmed counts while the Snapshot info box uses sitrep, so the two can differ per zone.
