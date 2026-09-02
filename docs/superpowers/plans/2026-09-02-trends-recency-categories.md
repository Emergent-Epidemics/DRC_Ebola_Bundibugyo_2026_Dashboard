# Trends Recency Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a segmented toggle to the Trends-tab map that flips its animated colouring between continuous cumulative confirmed cases and a 4-category confirmed-case *recency* view, both driven by the existing time slider.

**Architecture:** A pure Python function derives a per-zone, per-frame recency category (and days-since-last-case) from the `confirmed_timeseries` dict the build already loads, and attaches it to `PAYLOAD.confirmed_recency`. `engine.js` gains a `trendsColorMode` state, a discrete 4-colour fill path in `styleFn`, a swatch legend, a tooltip branch, and a segmented control in the Trends legend panel. New EN/FR i18n strings. Scope is `trends.html` only.

**Tech Stack:** Python 3.9 (pandas), pytest; vanilla JS (`Scripts/assets/engine.js`); Python-generated HTML chrome (`Scripts/common/chrome.py`); YAML i18n (`locales/en.yaml`, `locales/fr.yaml`).

---

## Environment notes (read once)

- All Python runs under **`python3.9`** (system `python3` lacks shapely/pytest).
- Run tests **from `Scripts/`** (imports resolve `common.*` via cwd):
  `cd Scripts && python3.9 -m pytest ../tests -v`
- The runtime JS source of truth is **`Scripts/assets/engine.js`** (the copies
  under `assets/` and `output/assets/` are build artifacts — never edit those).
- Rebuild the dashboard with: `python3.9 Scripts/build_dashboard.py`
  (needs sibling `../BDBV2026-Data/build/` present).
- Serve for eyeballing: `python3.9 -m http.server` in repo root (Chrome
  extension blocks `file://`).
- Commit messages: plain, **no** `Co-Authored-By` / Claude trailer (repo rule).

## File structure

- **Modify** `Scripts/common/data_sources.py` — add pure function
  `compute_confirmed_recency_timeseries(...)` near the existing
  `load_confirmed_cases_timeseries` (~line 2409).
- **Modify** `Scripts/common/payload.py` — compute + attach `confirmed_recency`
  (compute after line 130; attach in the dict after line 220).
- **Create** `tests/test_confirmed_recency.py` — unit tests for the pure function.
- **Modify** `Scripts/common/chrome.py` — add the segmented toggle + swatch
  legend markup inside `#trends-legend` (~lines 207-219).
- **Modify** `Scripts/assets/engine.js` — state, fill path, legend swap, tooltip,
  toggle wiring.
- **Modify** `locales/en.yaml`, `locales/fr.yaml` — new `trends_*` / category keys.

---

## Task 1: Python — `compute_confirmed_recency_timeseries` (pure function)

**Files:**
- Create: `tests/test_confirmed_recency.py`
- Modify: `Scripts/common/data_sources.py` (add after `load_confirmed_cases_timeseries`, ~line 2409)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_confirmed_recency.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_confirmed_recency.py -v`
Expected: FAIL — `AttributeError: module 'common.data_sources' has no attribute 'compute_confirmed_recency_timeseries'`.

- [ ] **Step 3: Write the implementation**

In `Scripts/common/data_sources.py`, immediately after `load_confirmed_cases_timeseries` (the function ending ~line 2409), add:

```python
# ---------------------------------------------------------------------------
# INSP confirmed-case recency categories (Trends tab "Recency" toggle)
# ---------------------------------------------------------------------------

# Category integers used across the payload / engine.js:
#   1 active  (<= near_days since last case)
#   2 recent  (near_days < d <= mid_days)
#   3 dormant (d > mid_days)
#   4 never   (no confirmed case yet as of the frame)
_RECENCY_LABELS = {
    "1": "active",
    "2": "recent",
    "3": "dormant",
    "4": "never",
}


def compute_confirmed_recency_timeseries(
    confirmed_ts: dict | None,
    near_days: int = 14,
    mid_days: int = 42,
) -> dict | None:
    """Derive per-zone, per-frame confirmed-case *recency* categories.

    Pure transform of the ``confirmed_timeseries`` dict produced by
    ``load_confirmed_cases_timeseries`` -- no I/O. For each zone and each frame
    date, classify by days since the zone's most recent *new* confirmed case
    (the last date its carry-forward cumulative count increased), measured from
    that frame's date. Returns ``None`` when the input is missing/empty so the
    Trends toggle silently stays unavailable, matching the slider's posture.
    """
    if not confirmed_ts:
        return None
    dates = confirmed_ts.get("dates") or []
    by_nom_cum = confirmed_ts.get("by_nom") or {}
    if not dates or not by_nom_cum:
        return None

    # Parse frame dates once; day arithmetic is exact even for irregular frames.
    parsed: list[date] = []
    for iso in dates:
        d = _parse_sitrep_date(iso)
        if d is None:
            return None
        parsed.append(d)

    by_nom: dict[str, list[int]] = {}
    days_by_nom: dict[str, list[int]] = {}
    for nom, series in by_nom_cum.items():
        cats: list[int] = []
        days: list[int] = []
        last_event_idx: int | None = None
        prev = 0
        for i, raw in enumerate(series):
            cum = int(raw or 0)
            # A *new* case = the cumulative count went up since the previous
            # frame. A nonzero value at the first frame is a baseline event.
            if cum > prev:
                last_event_idx = i
            prev = cum
            if last_event_idx is None:
                cats.append(4)
                days.append(-1)
            else:
                d = (parsed[i] - parsed[last_event_idx]).days
                days.append(d)
                if d <= near_days:
                    cats.append(1)
                elif d <= mid_days:
                    cats.append(2)
                else:
                    cats.append(3)
        by_nom[nom] = cats
        days_by_nom[nom] = days

    return {
        "dates": list(dates),
        "by_nom": by_nom,
        "days_by_nom": days_by_nom,
        "thresholds": {"near": near_days, "mid": mid_days},
        "labels": dict(_RECENCY_LABELS),
    }
```

Note: `date` and `_parse_sitrep_date` are already imported/defined in this
module (used by `load_confirmed_cases_timeseries`); no new imports needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd Scripts && python3.9 -m pytest ../tests/test_confirmed_recency.py -v`
Expected: PASS (all 9 tests).

- [ ] **Step 5: Commit**

```bash
git add Scripts/common/data_sources.py tests/test_confirmed_recency.py
git commit -m "Add confirmed-case recency category computation for Trends map"
```

---

## Task 2: Python — attach `confirmed_recency` to the payload

**Files:**
- Modify: `Scripts/common/payload.py:130` (compute) and `:220` (attach)
- Test: `tests/test_confirmed_recency.py` (add a wiring assertion — optional, kept light)

- [ ] **Step 1: Add the compute call**

In `Scripts/common/payload.py`, the line at 130 is:

```python
    confirmed_timeseries = load_confirmed_cases_timeseries(set(zone_data.keys()))
```

Change it to add the recency derivation immediately after:

```python
    confirmed_timeseries = load_confirmed_cases_timeseries(set(zone_data.keys()))
    confirmed_recency = compute_confirmed_recency_timeseries(confirmed_timeseries)
```

- [ ] **Step 2: Attach to the returned payload dict**

In the returned dict (the `return { ... }` block), find line ~220:

```python
        "confirmed_timeseries": confirmed_timeseries,
```

Add directly below it:

```python
        "confirmed_timeseries": confirmed_timeseries,
        "confirmed_recency": confirmed_recency,
```

- [ ] **Step 3: Verify the import resolves**

`compute_confirmed_recency_timeseries` must be importable in `payload.py`. Check
how `load_confirmed_cases_timeseries` is imported at the top of `payload.py`:

Run: `grep -n "load_confirmed_cases_timeseries\|from common.data_sources\|from .data_sources\|import data_sources" Scripts/common/payload.py`

If `load_confirmed_cases_timeseries` is imported by name (e.g.
`from common.data_sources import (... load_confirmed_cases_timeseries ...)`),
add `compute_confirmed_recency_timeseries` to that same import list. If the
module imports `data_sources` as a namespace and calls
`data_sources.load_confirmed_cases_timeseries(...)`, instead write
`data_sources.compute_confirmed_recency_timeseries(...)` in Step 1. Match the
existing style exactly.

- [ ] **Step 4: Run a real build to confirm the key lands**

Run:
```bash
python3.9 Scripts/build_dashboard.py
python3.9 - <<'PY'
import re, pathlib
html = pathlib.Path("output/trends.html").read_text()
print("confirmed_recency present:", '"confirmed_recency"' in html)
PY
```
Expected: build completes; prints `confirmed_recency present: True`.

- [ ] **Step 5: Run the full Python test suite (no regressions)**

Run: `cd Scripts && python3.9 -m pytest ../tests -q`
Expected: PASS (existing suite green + the 9 new tests).

- [ ] **Step 6: Commit**

```bash
git add Scripts/common/payload.py
git commit -m "Attach confirmed_recency to shared dashboard payload"
```

---

## Task 3: i18n strings for the toggle, categories, legend, tooltip

**Files:**
- Modify: `locales/en.yaml`, `locales/fr.yaml`

- [ ] **Step 1: Add English keys**

In `locales/en.yaml`, inside the `ui:` mapping alongside the existing
`trends_*` keys (near `trends_confirmed_title`), add:

```yaml
  trends_mode_cumulative: "Cumulative cases"
  trends_mode_recency: "Recency"
  trends_recency_title: "Confirmed-case recency"
  trends_recency_desc: "Health zones coloured by time since their most recent confirmed case, based on INSP sitrep report dates (not symptom onset), as of the slider date."
  trends_recency_cat1: "Case in last 14 days"
  trends_recency_cat2: "Case 15–42 days ago"
  trends_recency_cat3: "No case for >42 days"
  trends_recency_cat4: "No confirmed case"
  trends_recency_tooltip_days: "Last confirmed case: {days} days ago"
  trends_recency_tooltip_never: "No confirmed case yet"
  trends_mode_aria: "Map colouring mode"
```

- [ ] **Step 2: Add French keys**

In `locales/fr.yaml`, at the matching location in the `ui:` mapping, add:

```yaml
  trends_mode_cumulative: "Cas cumulés"
  trends_mode_recency: "Récence"
  trends_recency_title: "Récence des cas confirmés"
  trends_recency_desc: "Zones de santé colorées selon le temps écoulé depuis leur dernier cas confirmé, d'après les dates des sitreps INSP (et non la date d'apparition des symptômes), à la date du curseur."
  trends_recency_cat1: "Cas dans les 14 derniers jours"
  trends_recency_cat2: "Cas il y a 15 à 42 jours"
  trends_recency_cat3: "Aucun cas depuis >42 jours"
  trends_recency_cat4: "Aucun cas confirmé"
  trends_recency_tooltip_days: "Dernier cas confirmé : il y a {days} jours"
  trends_recency_tooltip_never: "Aucun cas confirmé à ce jour"
  trends_mode_aria: "Mode de coloration de la carte"
```

- [ ] **Step 3: Verify YAML parses and keys are present in both**

Run:
```bash
python3.9 - <<'PY'
import yaml
for lang in ("en", "fr"):
    d = yaml.safe_load(open(f"locales/{lang}.yaml"))
    ui = d["ui"]
    need = ["trends_mode_cumulative","trends_mode_recency","trends_recency_title",
            "trends_recency_desc","trends_recency_cat1","trends_recency_cat2",
            "trends_recency_cat3","trends_recency_cat4","trends_recency_tooltip_days",
            "trends_recency_tooltip_never","trends_mode_aria"]
    missing = [k for k in need if k not in ui]
    print(lang, "OK" if not missing else f"MISSING {missing}")
PY
```
Expected: `en OK` and `fr OK`.

- [ ] **Step 4: Commit**

```bash
git add locales/en.yaml locales/fr.yaml
git commit -m "Add i18n strings for Trends recency toggle, legend and tooltip"
```

---

## Task 4: Chrome markup — segmented toggle + swatch legend in the Trends panel

**Files:**
- Modify: `Scripts/common/chrome.py:207-219` (the `#trends-legend` panel)

- [ ] **Step 1: Add the toggle and recency-legend markup**

In `Scripts/common/chrome.py`, the `#trends-legend` block currently reads
(lines 207-219):

```python
<div id="trends-legend" class="panel">
  <div id="trends-legend-title"><strong data-i18n="ui.trends_confirmed_title">Confirmed cases (cumulative)</strong></div>
  <p id="trends-legend-desc" data-i18n="ui.trends_legend_desc">Transcribed from INSP sitreps. Cases are sometimes revised downwards in consecutive sitreps.</p>
  <div class="legend-bar" id="trends-legend-bar"></div>
  <div class="legend-ticks" id="trends-legend-ticks"></div>
  <div class="legend-scale" id="trends-legend-scale" data-i18n="ui.trends_scale_log">(log scale)</div>
  <div id="trends-play-row">
    <button type="button" id="trends-play-btn" data-i18n-aria="ui.trends_play" aria-label="Play">▶</button>
    <input type="range" id="trends-date-slider" min="0" max="0" value="0"
           data-i18n-aria="ui.trends_slider_aria" aria-label="SitRep date for confirmed cases map" />
  </div>
  <span id="trends-date-label" data-i18n="ui.trends_as_of">As of —</span>
</div>
```

Replace that whole block with (adds the segmented toggle after the title, wraps
the continuous legend in `#trends-cumulative-legend`, and adds a hidden
`#trends-recency-legend` with four swatches):

```python
<div id="trends-legend" class="panel">
  <div id="trends-legend-title"><strong data-i18n="ui.trends_confirmed_title">Confirmed cases (cumulative)</strong></div>
  <div id="trends-mode-toggle" role="group" data-i18n-aria="ui.trends_mode_aria" aria-label="Map colouring mode">
    <button type="button" class="trends-mode-btn active" data-mode="cumulative" data-i18n="ui.trends_mode_cumulative">Cumulative cases</button>
    <button type="button" class="trends-mode-btn" data-mode="recency" data-i18n="ui.trends_mode_recency">Recency</button>
  </div>
  <div id="trends-cumulative-legend">
    <p id="trends-legend-desc" data-i18n="ui.trends_legend_desc">Transcribed from INSP sitreps. Cases are sometimes revised downwards in consecutive sitreps.</p>
    <div class="legend-bar" id="trends-legend-bar"></div>
    <div class="legend-ticks" id="trends-legend-ticks"></div>
    <div class="legend-scale" id="trends-legend-scale" data-i18n="ui.trends_scale_log">(log scale)</div>
  </div>
  <div id="trends-recency-legend" style="display:none">
    <p id="trends-recency-desc" data-i18n="ui.trends_recency_desc">Health zones coloured by time since their most recent confirmed case.</p>
    <div class="recency-swatches">
      <div class="recency-swatch"><span class="recency-chip" style="background:#b2182b"></span><span data-i18n="ui.trends_recency_cat1">Case in last 14 days</span></div>
      <div class="recency-swatch"><span class="recency-chip" style="background:#ef8a62"></span><span data-i18n="ui.trends_recency_cat2">Case 15–42 days ago</span></div>
      <div class="recency-swatch"><span class="recency-chip" style="background:#fddbc7"></span><span data-i18n="ui.trends_recency_cat3">No case for &gt;42 days</span></div>
      <div class="recency-swatch"><span class="recency-chip" style="background:#e0e0e0"></span><span data-i18n="ui.trends_recency_cat4">No confirmed case</span></div>
    </div>
  </div>
  <div id="trends-play-row">
    <button type="button" id="trends-play-btn" data-i18n-aria="ui.trends_play" aria-label="Play">▶</button>
    <input type="range" id="trends-date-slider" min="0" max="0" value="0"
           data-i18n-aria="ui.trends_slider_aria" aria-label="SitRep date for confirmed cases map" />
  </div>
  <span id="trends-date-label" data-i18n="ui.trends_as_of">As of —</span>
</div>
```

- [ ] **Step 2: Add minimal styling for the toggle + swatches**

Find the stylesheet block in `chrome.py` (search for an existing Trends rule to
locate the right `<style>` string):

Run: `grep -n "#trends-legend\|#trends-play-row\|trends-legend-bar {" Scripts/common/chrome.py`

Add these rules near the other `#trends-*` CSS (inside the same `<style>` string):

```css
#trends-mode-toggle { display:flex; gap:0; margin:6px 0 8px; border:1px solid #cfcac1; border-radius:6px; overflow:hidden; width:fit-content; }
.trends-mode-btn { appearance:none; border:0; background:#f4f1ec; color:#555; font:inherit; font-size:12px; padding:4px 10px; cursor:pointer; }
.trends-mode-btn + .trends-mode-btn { border-left:1px solid #cfcac1; }
.trends-mode-btn.active { background:#6b6257; color:#fff; }
.recency-swatches { display:flex; flex-direction:column; gap:3px; margin-top:4px; }
.recency-swatch { display:flex; align-items:center; gap:6px; font-size:12px; }
.recency-chip { display:inline-block; width:14px; height:14px; border-radius:3px; border:1px solid rgba(0,0,0,0.25); flex:0 0 auto; }
```

(If the surrounding CSS uses different colour tokens/spacing, match those; the
values above are safe neutral defaults consistent with the existing panels.)

- [ ] **Step 3: Rebuild and verify the markup renders**

Run:
```bash
python3.9 Scripts/build_dashboard.py
python3.9 - <<'PY'
html = open("output/trends.html").read_text()
for marker in ('id="trends-mode-toggle"', 'data-mode="recency"',
               'id="trends-recency-legend"', 'recency-chip'):
    print(marker, marker in html)
PY
```
Expected: all four print `True`.

- [ ] **Step 4: Commit**

```bash
git add Scripts/common/chrome.py
git commit -m "Add Trends recency toggle and swatch legend markup"
```

---

## Task 5: engine.js — recency state, fill path, and tooltip

**Files:**
- Modify: `Scripts/assets/engine.js` (state near `let trendsScope`, ~line 2663; `styleFn` ~1752; `layerHoverTooltipHTML` ~1962)

- [ ] **Step 1: Add module state + colour lookup + accessors**

Near the other trends state (just after `let trendsScope = "national";` at
`engine.js:2663`), add:

```javascript
let trendsColorMode = "cumulative"; // "cumulative" | "recency"

// Confirmed-case recency category fills (see docs spec 2026-09-02). Index by
// category int 1..4; 0 / missing -> no-data neutral.
const RECENCY_FILL = {1: "#b2182b", 2: "#ef8a62", 3: "#fddbc7", 4: "#e0e0e0"};
const RECENCY_NODATA_FILL = "#e0e0e0";

function getTrendsRecencyAt(nom, dateIdx) {
  const rc = PAYLOAD.confirmed_recency;
  if (!rc || !rc.by_nom) return 0;
  const series = rc.by_nom[nom];
  if (!series || dateIdx < 0 || dateIdx >= series.length) return 0;
  return series[dateIdx];
}

function getTrendsRecencyDaysAt(nom, dateIdx) {
  const rc = PAYLOAD.confirmed_recency;
  if (!rc || !rc.days_by_nom) return -1;
  const series = rc.days_by_nom[nom];
  if (!series || dateIdx < 0 || dateIdx >= series.length) return -1;
  return series[dateIdx];
}

function trendsRecencyAvailable() {
  const rc = PAYLOAD.confirmed_recency;
  return !!(rc && rc.by_nom && rc.dates && rc.dates.length);
}
```

- [ ] **Step 2: Add the categorical fill branch in `styleFn`**

`styleFn` begins at `engine.js:1752`:

```javascript
function styleFn(feature) {
  if (activeView === "epi-trends") return epiTrendsStyleFn(feature);
  const ref = feature.properties.nom;
```

Insert the recency branch right after the `epi-trends` line, so it becomes:

```javascript
function styleFn(feature) {
  if (activeView === "epi-trends") return epiTrendsStyleFn(feature);
  if (activeView === "trends" && trendsColorMode === "recency") {
    return trendsRecencyStyle(feature.properties.nom);
  }
  const ref = feature.properties.nom;
```

Then add the helper immediately above `styleFn` (before line 1752):

```javascript
function trendsRecencyStyle(ref) {
  const cat = getTrendsRecencyAt(ref, trendsDateIdx);
  const fillColor = RECENCY_FILL[cat] || RECENCY_NODATA_FILL;
  // Category 4 ("never") is a muted neutral; give it a slightly lower opacity
  // so the active categories read as the foreground.
  const fillOpacity = cat === 4 || !cat ? 0.55 : 0.85;
  const style = Object.assign({}, zoneStroke("rest"), {fillColor, fillOpacity});
  // Mirror the cumulative view: suppress zone strokes in Provincial scope so the
  // province outlines are the only line work.
  if (trendsScope === "province") style.weight = 0;
  return style;
}
```

- [ ] **Step 3: Add the tooltip branch in `layerHoverTooltipHTML`**

`layerHoverTooltipHTML` is at `engine.js:1962`. Insert a recency branch at the
top of the function body, right after `const name = ...` (line 1964):

```javascript
function layerHoverTooltipHTML(feature) {
  const ref = feature.properties.nom;
  const name = feature.properties.name || t("ui.case_tooltip.unnamed");
  if (activeView === "trends" && trendsColorMode === "recency") {
    const cat = getTrendsRecencyAt(ref, trendsDateIdx);
    const rc = PAYLOAD.confirmed_recency || {};
    const catLabel = t("ui.trends_recency_cat" + (cat || 4));
    let line2;
    if (!cat || cat === 4) {
      line2 = t("ui.trends_recency_tooltip_never");
    } else {
      const days = getTrendsRecencyDaysAt(ref, trendsDateIdx);
      line2 = tf("ui.trends_recency_tooltip_days", {days: days});
    }
    return "<strong>" + name + "</strong><br/>" + catLabel + "<br/>" + line2;
  }
  const layer = getLayer(layerSelect.value);
```

Leave the remainder of the function unchanged.

Note: `t(...)` (lookup) and `tf(key, params)` (interpolated `{...}`) are the
existing i18n helpers — `tf` is already used elsewhere in this file (e.g.
`engine.js:1013`).

- [ ] **Step 4: Manual verification (deferred to Task 6)**

No isolated test here; the fill + tooltip are verified together with the toggle
wiring in Task 6, Step 4. Do not commit yet — commit at the end of Task 6 so the
feature lands as one working unit. (If you prefer a checkpoint commit, it is
safe to commit now since the branch is not yet reachable from the UI.)

---

## Task 6: engine.js — toggle wiring + legend swap

**Files:**
- Modify: `Scripts/assets/engine.js` (`enterTrendsView` ~3576; add `setTrendsColorMode`, `syncTrendsModeToggle`, `initTrendsRecencyLegendVisibility`; wire the toggle buttons in the init/event-binding area)

- [ ] **Step 1: Add mode-setting + legend-swap functions**

Add these near the other trends legend functions (e.g. after
`initTrendsLegendBar`, ~`engine.js:3507`):

```javascript
function syncTrendsModeToggle() {
  const btns = document.querySelectorAll(".trends-mode-btn");
  btns.forEach(function (b) {
    b.classList.toggle("active", b.getAttribute("data-mode") === trendsColorMode);
  });
  const title = document.getElementById("trends-legend-title");
  const cumu = document.getElementById("trends-cumulative-legend");
  const rec = document.getElementById("trends-recency-legend");
  const recency = trendsColorMode === "recency";
  if (cumu) cumu.style.display = recency ? "none" : "";
  if (rec) rec.style.display = recency ? "" : "none";
  if (title) {
    const strong = title.querySelector("strong");
    if (strong) {
      strong.setAttribute("data-i18n", recency ? "ui.trends_recency_title" : "ui.trends_confirmed_title");
      strong.textContent = t(recency ? "ui.trends_recency_title" : "ui.trends_confirmed_title");
    }
  }
}

function setTrendsColorMode(mode) {
  const next = mode === "recency" && trendsRecencyAvailable() ? "recency" : "cumulative";
  if (next === trendsColorMode) { syncTrendsModeToggle(); return; }
  trendsColorMode = next;
  syncTrendsModeToggle();
  // Re-paint the current frame without restarting the animation.
  if (activeView === "trends") geoLayer.setStyle(styleFn);
}
```

- [ ] **Step 2: Wire the toggle buttons**

Find where other Trends controls are wired at init (search for the play button
handler):

Run: `grep -n "trends-play-btn\|trends-date-slider\").addEventListener\|trends-scope-btn" Scripts/assets/engine.js`

At that same init location (where `trends-play-btn` / scope buttons get their
listeners), add:

```javascript
document.querySelectorAll(".trends-mode-btn").forEach(function (btn) {
  btn.addEventListener("click", function () {
    setTrendsColorMode(btn.getAttribute("data-mode"));
  });
});
```

- [ ] **Step 3: Reset + sync on entering / hide toggle when unavailable**

In `enterTrendsView` (`engine.js:3576`), the block that runs when the time
series exists currently is (lines 3588-3596):

```javascript
  } else {
    if (legendPanel) legendPanel.style.display = "";
    initTrendsLegendBar();
    const slider = document.getElementById("trends-date-slider");
    if (slider) slider.max = String(ts.dates.length - 1);
    // Auto-play from the start every time the tab is opened, rather than
    // jumping straight to the latest sitrep and waiting for a manual Play click.
    playTrendsSliderAnimation();
  }
```

Replace it with (default back to cumulative on entry; hide the toggle if the
recency payload is absent):

```javascript
  } else {
    if (legendPanel) legendPanel.style.display = "";
    // Always enter in the cumulative view; the toggle opts into recency.
    trendsColorMode = "cumulative";
    const toggle = document.getElementById("trends-mode-toggle");
    if (toggle) toggle.style.display = trendsRecencyAvailable() ? "" : "none";
    syncTrendsModeToggle();
    initTrendsLegendBar();
    const slider = document.getElementById("trends-date-slider");
    if (slider) slider.max = String(ts.dates.length - 1);
    // Auto-play from the start every time the tab is opened, rather than
    // jumping straight to the latest sitrep and waiting for a manual Play click.
    playTrendsSliderAnimation();
  }
```

- [ ] **Step 4: Rebuild, serve, and verify in the browser**

```bash
python3.9 Scripts/build_dashboard.py
# copy build outputs to repo root so the served page uses the fresh engine.js
cp output/*.html . && rm -rf assets && cp -r output/assets assets
python3.9 -m http.server
```

Then load `http://localhost:8000/trends.html` and confirm:
- The map autoplays the cumulative view as before (unchanged default).
- Clicking **Recency** recolours zones into the 4 categories; the legend swaps
  to the four swatches and the title becomes "Confirmed-case recency".
- Dragging/playing the slider re-buckets zones over time (a zone that had a
  recent case goes red → orange → sand as frames advance; never-affected zones
  stay grey).
- Hovering a zone in Recency mode shows the category + "Last confirmed case: N
  days ago" (or "No confirmed case yet" for grey zones).
- Switching to **French** keeps all labels translated.
- Clicking **Cumulative cases** restores the original gradient legend + colours.

- [ ] **Step 5: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "Wire Trends recency toggle: fill path, legend swap and tooltip"
```

---

## Task 7: Final regression + build-artifact sync

**Files:**
- No new edits; verify + sync build outputs.

- [ ] **Step 1: Full Python test suite**

Run: `cd Scripts && python3.9 -m pytest ../tests -q`
Expected: PASS (all existing + `test_confirmed_recency.py`).

- [ ] **Step 2: Confirm the built root pages carry the change**

The deployed pages at repo root are build artifacts. Confirm they were refreshed
in Task 6 Step 4 (or refresh again):

```bash
python3.9 Scripts/build_dashboard.py
cp output/*.html . && rm -rf assets && cp -r output/assets assets
grep -c "trends-mode-toggle" trends.html   # expect >= 1
grep -c "getTrendsRecencyAt" assets/engine.js  # expect >= 1
```
Expected: both counts ≥ 1.

- [ ] **Step 3: Commit the rebuilt artifacts**

```bash
git add trends.html index.html context.html clinical-symptoms.html \
        genomic-epidemiology.html spatial-risk.html surveillance-testing.html assets
git commit -m "Rebuild dashboard with Trends recency categories"
```

(Only add the files that actually changed — `git status` first; the shared
`engine.js`/chrome markup means every page's HTML may change.)

- [ ] **Step 4: Hand off**

Serve and hand the URL to the user for review (per repo convention: build,
serve, hand over, wait — before offering merge/PR). Note the two agreed
iteration points: the 4 category colours and the tooltip wording.

---

## Self-review notes (author)

- **Spec coverage:** category math + thresholds (Task 1) ✓; Python compute
  location + payload attach (Task 2) ✓; segmented toggle (Tasks 4, 6) ✓; discrete
  fill + legend swap (Tasks 5, 6) ✓; tooltip (Task 5) ✓; i18n EN/FR (Task 3) ✓;
  pytest coverage incl. boundaries/gaps/first-date/correction/transitions
  (Task 1) ✓; caveat in legend desc (Task 3 `trends_recency_desc`) ✓; Trends-only
  scope (branch guards on `activeView === "trends"`) ✓.
- **Type consistency:** category ints `1..4` and fill keys `RECENCY_FILL{1..4}`
  match; `by_nom` / `days_by_nom` / `thresholds` / `labels` keys identical across
  Python output, tests, and JS accessors; i18n keys `trends_recency_cat1..4`
  match the tooltip's `"ui.trends_recency_cat" + cat` and the legend swatches.
- **Known deferrals:** exact hex values and tooltip wording flagged for iteration
  after first version (user's call).
```
