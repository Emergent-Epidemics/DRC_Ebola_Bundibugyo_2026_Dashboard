# Spatial-risk import-force arrows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Spatial Risk tab's inflow arrows scale with each origin's Bayesian import-force contribution (`foi`, h=1) to the selected zone, instead of the origin's raw confirmed-case count.

**Architecture:** A new Python loader reads `bayes_pairwise_import_force.csv` from the same dated spatiotemporal outputs folder the invasion-risk table already uses, and emits a sparse `{dest_nom: [[origin_nom, foi, share], …]}` map into a new `PAYLOAD.import_force_pairwise` key. `engine.js` draws pairwise-source arrows on the `epi-trends` view, width = `1 + 4·√(foi / max foi for the selected zone)` (per-zone normalized, sqrt-compressed), falling back to the existing confirmed-cases path when the data is absent.

**Tech Stack:** Python 3.10+ (pandas), vanilla JS (Leaflet), YAML locales. Build entry point: `python Scripts/build_dashboard.py`.

**Spec:** `docs/superpowers/specs/2026-08-04-spatial-risk-pairwise-import-force-arrows-design.md`

**Scope note:** `Scripts/build_dashboard_public.py` is SUPERSEDED (not called by CI or anything) — do NOT modify it. Production path is `build_dashboard.py` + `Scripts/common/` + `Scripts/assets/engine.js`.

---

## Task 1: Python loader `load_bayes_import_force_pairwise()`

**Files:**
- Create: `tests/test_import_force_pairwise.py`
- Modify: `Scripts/common/data_sources.py` (add loader + resolver near `load_invasion_risk_estimates` at line 1433; `_latest_spatiotemporal_key_outputs_dir` is at line 1409)

- [ ] **Step 1: Write the failing test**

Create `tests/test_import_force_pairwise.py`. The loader locates the CSV via
`_latest_spatiotemporal_key_outputs_dir()`, so the test monkeypatches that to point at a
temp dir it populates.

```python
import importlib
from pathlib import Path
import pytest

ds = importlib.import_module("common.data_sources")

PAIRWISE_CSV = (
    "origin_zone,dest_zone,horizon,w_ji,source_origin,import_force,foi,"
    "dest_import_force_total,dest_hazard_week,share_of_dest,origin_province,dest_province\n"
    # dest Aba, h=1: two origins, Bunia has higher foi than Nizi
    "Bunia,Aba,1,0.1,10,1.0,0.16,2.0,0.32,0.5,Ituri,Haut-Uele\n"
    "Nizi,Aba,1,0.05,4,0.2,0.032,2.0,0.32,0.1,Ituri,Haut-Uele\n"
    # dest Aba, h=2: must be filtered out
    "Bunia,Aba,2,0.1,12,1.2,0.192,2.4,0.384,0.5,Ituri,Haut-Uele\n"
    # a zero/negative foi edge must be dropped
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
    # h=2 filtered, zero-foi dropped -> exactly two edges
    assert [e[0] for e in edges] == ["Bunia", "Nizi"]        # sorted by foi desc
    assert edges[0][1] == pytest.approx(0.16)                # foi
    assert edges[0][2] == pytest.approx(0.5)                 # share_of_dest
    # beta = foi / import_force = 0.16 / 1.0 = 0.16
    assert result["beta"] == pytest.approx(0.16, rel=1e-6)


def test_loader_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", tmp_path)  # empty
    assert ds.load_bayes_import_force_pairwise() is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd Scripts && python -m pytest ../tests/test_import_force_pairwise.py -v`
Expected: FAIL — `AttributeError: module 'common.data_sources' has no attribute 'load_bayes_import_force_pairwise'`
(If pytest is missing: `pip install pytest`.)

- [ ] **Step 3: Implement the resolver + loader**

In `Scripts/common/data_sources.py`, immediately after `load_invasion_risk_estimates()`
ends (line 1638, before the `_INVASION_AFFECTED_MASK_FIELDS` block at line 1641), add:

```python
def _latest_spatiotemporal_pairwise_csv() -> Path | None:
    """Pairwise import-force CSV from the SAME dated folder as the risk table.

    Reuses _latest_spatiotemporal_key_outputs_dir() so the arrows and the
    invasion-risk table always come from one pipeline run. The reports CSV is
    a sibling of key_outputs: <date>/spatiotemporal/reports/.
    """
    ko = _latest_spatiotemporal_key_outputs_dir()
    if ko is None:
        return None
    csv = ko.parent / "reports" / "bayes_pairwise_import_force.csv"
    return csv if csv.exists() else None


def load_bayes_import_force_pairwise() -> dict | None:
    """Directed pairwise import-force (horizon 1) for spatial-risk arrow widths.

    Emits a sparse ``in_by_dest`` map keyed by health-zone ``nom``; each value
    is a list of ``[origin_nom, foi, share_of_dest]`` triples sorted by ``foi``
    descending. engine.js normalizes width per selected zone
    (``foi / max foi for that zone``). Returns None if the file is absent, so
    the build falls back to the confirmed-cases arrows.
    """
    csv_path = _latest_spatiotemporal_pairwise_csv()
    if csv_path is None:
        print("  NOTE: no bayes_pairwise_import_force.csv found; "
              "spatial-risk arrows fall back to confirmed cases")
        return None
    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"  WARNING: {csv_path.name} is empty")
        return None
    df.columns = [str(c).strip() for c in df.columns]
    required = {"origin_zone", "dest_zone", "horizon", "foi", "share_of_dest"}
    missing = required - set(df.columns)
    if missing:
        print(f"  WARNING: {csv_path.name} missing columns: {sorted(missing)}")
        return None

    df = df[df["horizon"].astype(str).str.strip() == "1"].copy()
    df["foi"] = pd.to_numeric(df["foi"], errors="coerce")
    df["share_of_dest"] = pd.to_numeric(df["share_of_dest"], errors="coerce")
    df = df.dropna(subset=["foi"])
    df = df[df["foi"] > 0]
    if df.empty:
        print(f"  WARNING: {csv_path.name} has no positive horizon==1 rows")
        return None

    in_by_dest: dict[str, list] = {}
    for dest, grp in df.groupby("dest_zone", sort=False):
        dest_nom = str(dest).strip()
        if not dest_nom:
            continue
        grp = grp.sort_values("foi", ascending=False)
        edges = []
        for _, r in grp.iterrows():
            origin = str(r["origin_zone"]).strip()
            if not origin:
                continue
            share = r["share_of_dest"]
            edges.append([
                origin,
                float(r["foi"]),
                float(share) if pd.notna(share) else None,
            ])
        if edges:
            in_by_dest[dest_nom] = edges

    beta = None
    if "import_force" in df.columns:
        imp = pd.to_numeric(df["import_force"], errors="coerce")
        mask = imp > 0
        if bool(mask.any()):
            beta = float((df.loc[mask, "foi"] / imp[mask]).median())

    n_edges = sum(len(v) for v in in_by_dest.values())
    print(f"  import-force pairwise: {len(in_by_dest)} dest zones, "
          f"{n_edges} h=1 edges"
          + (f", beta={beta:.4g}" if beta else ""))
    return {
        "in_by_dest": in_by_dest,
        "horizon": 1,
        "beta": beta,
        "source": csv_path.name,
    }
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd Scripts && python -m pytest ../tests/test_import_force_pairwise.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Register the loader in `__all__`**

In `Scripts/common/data_sources.py`, the `__all__` list starts at line 51 and already
contains `'load_invasion_risk_estimates',` (line 122). Add the new public name next to it:

```python
    'load_invasion_risk_estimates',
    'load_bayes_import_force_pairwise',
```

(`_latest_spatiotemporal_pairwise_csv` is private — leave it out of `__all__`.)

- [ ] **Step 6: Commit**

```bash
git add tests/test_import_force_pairwise.py Scripts/common/data_sources.py
git commit -m "feat: load pairwise import-force CSV for spatial-risk arrows"
```

---

## Task 2: Wire the loader into the payload

**Files:**
- Modify: `Scripts/common/payload.py` (call site near line 134; return dict at 152–194)

- [ ] **Step 1: Call the loader alongside the flow catalog**

In `Scripts/common/payload.py`, right after the flow-catalog block (line 135,
`flow_catalogs = {"flowminder_latest": flow_latest}`), add:

```python
    import_force_pairwise = load_bayes_import_force_pairwise()
```

- [ ] **Step 2: Add the payload key**

In the `return {…}` dict, immediately after the `"invasion_risk": invasion_risk,` line
(line 190), add:

```python
        "import_force_pairwise": import_force_pairwise,
```

- [ ] **Step 3: Verify the payload key populates**

Requires the pairwise CSV checked out locally (see Task 5, Step 1 for the one-time data
setup). From the repo root:

```bash
cd Scripts && BUILD_DIR=../../BDBV2026-Data/build DATA_ROOT=../Data \
  DASHBOARD_PLOTS_DIR=../../BDBV2026-Processed_Sensitive_Data/outputs \
  INSP_SITREP_FETCH=0 python -c "from common.payload import build_shared_payload; \
  p=build_shared_payload(); ifp=p['import_force_pairwise']; \
  print('dests:', len(ifp['in_by_dest'])); \
  print('Aba edges:', ifp['in_by_dest'].get('Aba', [])[:2])"
```

Expected: prints a non-zero dest count and a couple of `[origin, foi, share]` triples for
Aba. If the pairwise CSV isn't checked out, it prints `dests: 0`-style `NoneType` — do
Task 5 Step 1 first.

- [ ] **Step 4: Commit**

```bash
git add Scripts/common/payload.py
git commit -m "feat: expose import_force_pairwise in dashboard payload"
```

---

## Task 3: i18n strings + legend text

**Files:**
- Modify: `locales/en.yaml` (line 101 tooltip; line 211 legend), `locales/fr.yaml` (same lines)
- Modify: `Scripts/common/chrome.py:302` (inline legend default)

- [ ] **Step 1: Add the new tooltip key (en)**

In `locales/en.yaml`, directly below `importation_pressure_tooltip` (line 101), add:

```yaml
  import_force_tooltip: "{from} → {to}: import-force contribution {foi} ({share} of {to}'s importation risk)"
```

- [ ] **Step 2: Add the new tooltip key (fr)**

In `locales/fr.yaml`, directly below `importation_pressure_tooltip` (line 101), add:

```yaml
  import_force_tooltip: "{from} → {to} : contribution à la force d'importation {foi} ({share} du risque d'importation de {to})"
```

- [ ] **Step 3: Update the legend width text (en, line 211)**

Replace the `importation_pressure_width` value in `locales/en.yaml`:

```yaml
    importation_pressure_width: "Red inflows only; line width ∝ each origin's modelled import-force contribution to the selected zone (next-week forecast), scaled 0–1 vs that zone's top source"
```

- [ ] **Step 4: Update the legend width text (fr, line 211)**

Replace the `importation_pressure_width` value in `locales/fr.yaml`:

```yaml
    importation_pressure_width: "Entrées rouges uniquement ; épaisseur ∝ contribution modélisée de chaque origine à la force d'importation de la zone sélectionnée (prévision semaine suivante), échelle 0–1 vs la principale origine de cette zone"
```

- [ ] **Step 5: Update the inline legend default in chrome.py**

In `Scripts/common/chrome.py:302`, replace the inline English fallback text so it matches
the new en.yaml string (the `data-i18n` key is unchanged, so runtime uses the locale, but
keep the hardcoded default in sync):

```python
      <div data-i18n="ui.legend.importation_pressure_width">Red inflows only; line width ∝ each origin's modelled import-force contribution to the selected zone (next-week forecast), scaled 0–1 vs that zone's top source</div>
```

- [ ] **Step 6: Commit**

```bash
git add locales/en.yaml locales/fr.yaml Scripts/common/chrome.py
git commit -m "i18n: import-force arrow tooltip + legend text"
```

---

## Task 4: engine.js — render pairwise import-force arrows

**Files:**
- Modify: `Scripts/assets/engine.js` (payload read near line 12; `renderFlowArcs` at 634–733)

- [ ] **Step 1: Read the new payload key**

In `Scripts/assets/engine.js`, after line 12 (`const FLOW_CATALOGS = PAYLOAD.flow_catalogs || {};`), add:

```javascript
const IMPORT_FORCE_PAIRWISE = PAYLOAD.import_force_pairwise || null;
```

- [ ] **Step 2: Add a pairwise-arrow branch in `renderFlowArcs`**

In `renderFlowArcs`, the `epi-trends` inflow arrows are drawn by the
`inSorted.forEach(...)` loop (lines 686–722), gated by `useImportPressure` (line 647).
Insert a pairwise-source path that runs *instead of* that loop when pairwise data exists
for the hub. Add this block immediately BEFORE `inSorted.forEach(function(pair) {`
(line 686):

```javascript
  const pairwiseEdges = (useImportPressure && IMPORT_FORCE_PAIRWISE
    && IMPORT_FORCE_PAIRWISE.in_by_dest
    && IMPORT_FORCE_PAIRWISE.in_by_dest[hubNom]) || null;
  if (pairwiseEdges) {
    let maxFoi = 0;
    pairwiseEdges.forEach(function(e) { if (e[1] > maxFoi) maxFoi = e[1]; });
    pairwiseEdges.forEach(function(e) {
      const origin = e[0];
      const foi = e[1];
      const share = e[2];
      const start = zoneCentroid(origin);
      if (!start) return;
      const pts = quadraticBezierPoints(start[0], start[1], hub[0], hub[1], 1);
      const line = L.polyline(pts, {
        color: FLOW_OUT_COLOR,
        weight: flowArcWeight(foi, maxFoi),        // 1 + 4*sqrt(foi/maxFoi)
        opacity: 0.82,
        pane: "flow-arcs",
      });
      line.bindTooltip(tf("ui.import_force_tooltip", {
        from: hubDisplayName(origin),
        to: flowHubDisplayName(),
        foi: foi.toPrecision(2),
        share: (share != null ? (share * 100).toFixed(1) + "%" : "—"),
      }), {direction: "top", sticky: true});
      line.addTo(flowArcLayer);
      addFlowWingMarker(pts, FLOW_OUT_COLOR, {nearEnd: true});
    });
    flowArcStats = {
      outTotal: outs.length, outShown: 0,
      inTotal: ins.length, inShown: pairwiseEdges.length,
      metric: "import_force", maxMetric: maxFoi,
    };
    flowArcLayer.addTo(map);
    return;
  }

```

The existing `inSorted.forEach(...)` loop and the `flowArcStats`/`flowArcLayer.addTo(map)`
tail (lines 724–732) remain unchanged and serve as the fallback when `pairwiseEdges` is
null (no data, or hub not in the map).

- [ ] **Step 3: Build and open the page to verify**

Requires Task 5 Step 1 data setup. Build:

```bash
cd Scripts && BUILD_DIR=../../BDBV2026-Data/build DATA_ROOT=../Data \
  DASHBOARD_PLOTS_DIR=../../BDBV2026-Processed_Sensitive_Data/outputs \
  INSP_SITREP_FETCH=0 python build_dashboard.py
```

Expected build log line: `import-force pairwise: <N> dest zones, <M> h=1 edges, beta=…`.
Open `Scripts/output/spatial-risk.html` in a browser, select a zone with known inflows
(e.g. Aba or Mongbwalu): red inflow arrows appear only for pairwise sources, the widest
arrow is the highest-`foi` origin, and hovering shows "import-force contribution … (…% of
…'s importation risk)".

- [ ] **Step 4: Commit**

```bash
git add Scripts/assets/engine.js
git commit -m "feat: spatial-risk arrows scale with pairwise import-force (foi, h=1)"
```

---

## Task 5: End-to-end build verification + CSV spot-check

**Files:** none (verification only)

- [ ] **Step 1: One-time — materialize the pairwise data locally**

The local `BDBV2026-Processed_Sensitive_Data` checkout is on a feature branch without the
`2026-08-03` outputs. Pull just that folder from `origin/main` into a scratch outputs root
so the sibling repo's working tree is left untouched:

```bash
mkdir -p /tmp/st-plots
git -C ../BDBV2026-Processed_Sensitive_Data fetch origin --quiet
git -C ../BDBV2026-Processed_Sensitive_Data archive origin/main outputs/2026-08-03 \
  | tar -x -C /tmp/st-plots
ls /tmp/st-plots/outputs/2026-08-03/spatiotemporal/reports/bayes_pairwise_import_force.csv
```

Then use `DASHBOARD_PLOTS_DIR=/tmp/st-plots/outputs` in the Task 2/4 build commands
instead of the sibling path.

- [ ] **Step 2: Spot-check rendered widths against the CSV**

For the zone you inspected, confirm the top-3 origins by `foi` in the CSV match the three
widest arrows:

```bash
awk -F, 'NR==1 || ($2=="Aba" && $3==1)' \
  /tmp/st-plots/outputs/2026-08-03/spatiotemporal/reports/bayes_pairwise_import_force.csv \
  | sort -t, -k7 -gr | head -4
```

Expected: header + the three highest-`foi` rows for Aba; their `origin_zone` order matches
the three thickest arrows into Aba on the map.

- [ ] **Step 3: Verify the fallback path**

Temporarily point at a plots dir with no spatiotemporal reports (e.g. an older date), or
rename the CSV, rebuild, and confirm the build log prints
`no bayes_pairwise_import_force.csv found; … fall back to confirmed cases` and the arrows
render via the old confirmed-cases metric (no crash, `spatial-risk.html` still valid).

- [ ] **Step 4: Final commit (if any verification fixups were needed)**

```bash
git add -A && git commit -m "test: verify import-force arrows end-to-end"
```

---

## Self-review notes

- **Spec coverage:** loader + payload key (Task 1–2), pairwise-only arrows h=1 (Task 4),
  per-zone sqrt-normalized width via `flowArcWeight` (Task 4 Step 2), foi+share tooltip
  (Task 3–4), legend update (Task 3), fallback (Task 4 Step 2 + Task 5 Step 3), all-sources
  no-cap (Task 1 Step 3). Covered.
- **`flowArcWeight` reuse:** `flowArcWeight(count, maxCount) = 1 + 4·√(count/maxCount)`
  already exists (engine.js:576) and is the sqrt mapping the spec calls for — reused
  directly with `(foi, maxFoi)`, no new helper.
- **Naming consistency:** payload key `import_force_pairwise`, JS const
  `IMPORT_FORCE_PAIRWISE`, loader `load_bayes_import_force_pairwise`, structure
  `in_by_dest` → `[origin, foi, share]` — used identically across Tasks 1, 2, 4.
- **Out of scope (do not touch):** `build_dashboard_public.py` (superseded),
  `invasion_risk` ingestion, snapshot-view arrows, Analysis/CI pipeline.
