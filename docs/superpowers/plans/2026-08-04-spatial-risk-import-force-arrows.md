# Spatial-risk import-force arrows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Spatial Risk tab's inflow arrows scale with each origin's Bayesian import-force contribution to the selected zone (per-zone normalized, h=1), instead of the origin's raw confirmed-case count.

**Architecture:** A new Python loader reads `bayes_pairwise_import_force.csv` from the same dated spatiotemporal outputs folder the invasion-risk table already uses, and emits a sparse `{dest_nom: [[origin_nom, foi, share], …]}` map into a new `PAYLOAD.import_force_pairwise` key (page-scoped to the spatial-risk page — see Task 2). `engine.js` draws pairwise-source arrows on the `epi-trends` view, width = `1 + 4·√(foi / max foi for the selected zone)`, sqrt-compressed and normalized against the selected zone's own maximum.

**Width metric note (from spec decision #2):** because normalization is per-zone, the width is mathematically **share-of-destination** — `foi`, `share_of_dest`, and `import_force` produce *identical* widths (they differ only by the destination's constant hazard `H_i = β·Λ_i`, which cancels). `foi` is carried for the **tooltip only** (its "contribution to weekly invasion probability" reading); swapping `foi`→`share` in the width calc would change nothing visually. Both `foi` and `share` stay in each edge triple because the tooltip shows both.

**Width-curve note (from spec decision #3):** the pairwise path uses the sqrt curve (`flowArcWeight`, `1 + 4·√frac`); the confirmed-cases **fallback** keeps its existing *linear* curve (`flowArcWeightNormalized`, `1 + 4·frac`). Endpoints match (frac 0 and 1); only mid-range widths differ, and only in the degraded/data-absent mode. Accepted intentionally — not worth changing the established fallback curve for a path that won't run in production.

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


# H2 regression: a blank horizon cell forces pandas to parse the column as
# float, so horizon 1 reads as 1.0. A stringify-then-compare-to-"1" filter would
# match zero rows and silently return None. The numeric filter must still work.
FLOAT_HORIZON_CSV = (
    "origin_zone,dest_zone,horizon,w_ji,source_origin,import_force,foi,"
    "dest_import_force_total,dest_hazard_week,share_of_dest,origin_province,dest_province\n"
    "Bunia,Aba,1,0.1,10,1.0,0.16,2.0,0.32,0.5,Ituri,Haut-Uele\n"
    "Nizi,Aba,,0.05,4,0.2,0.032,2.0,0.32,0.1,Ituri,Haut-Uele\n"  # blank horizon -> float col
)


def test_loader_handles_float_horizon_column(tmp_path, monkeypatch):
    out = _make_outputs(tmp_path)
    (out / "2026-08-03" / "spatiotemporal" / "reports"
     / "bayes_pairwise_import_force.csv").write_text(FLOAT_HORIZON_CSV)
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)
    result = ds.load_bayes_import_force_pairwise()
    assert result is not None
    assert [e[0] for e in result["in_by_dest"]["Aba"]] == ["Bunia"]  # only the h==1 row


def test_loader_returns_none_on_missing_columns(tmp_path, monkeypatch):
    out = _make_outputs(tmp_path)
    (out / "2026-08-03" / "spatiotemporal" / "reports"
     / "bayes_pairwise_import_force.csv").write_text(
        "origin_zone,dest_zone,horizon\nBunia,Aba,1\n")  # no foi/share
    monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", out)
    assert ds.load_bayes_import_force_pairwise() is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd Scripts && python -m pytest ../tests/test_import_force_pairwise.py -v`
Expected: FAIL — `AttributeError: module 'common.data_sources' has no attribute 'load_bayes_import_force_pairwise'`
(If pytest is missing: `pip install pytest`.)

- [ ] **Step 3: Implement the resolver + loader**

In `Scripts/common/data_sources.py`, immediately after `load_invasion_risk_estimates()`
ends (its `return {…}` closes ~line 1638), just before the `_INVASION_AFFECTED_MASK_FIELDS`
assignment (re-anchor by that symbol, not the raw line number), add:

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

    # Numeric compare (NOT stringified) — a blank cell makes pandas parse the
    # column as float, so "1" would read as "1.0" and a string match would drop
    # every row and silently disable the feature. See test_loader_handles_float_horizon.
    df = df[pd.to_numeric(df["horizon"], errors="coerce") == 1].copy()
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

    # beta = foi / import_force is a single global constant (spec: "derivable
    # from any row"); take the first positive-import_force row rather than a
    # median, so genuine data drift would surface as a wrong value instead of
    # being averaged away. Informational only — engine.js never reads it.
    beta = None
    if "import_force" in df.columns:
        imp = pd.to_numeric(df["import_force"], errors="coerce")
        good = df.loc[imp > 0]
        if not good.empty:
            first = good.iloc[0]
            beta = float(first["foi"] / float(imp.loc[good.index[0]]))

    # Provenance: the dated outputs folder (<date>/spatiotemporal/reports/...),
    # so a maintainer can confirm arrows and the invasion-risk table share a run.
    yyyymmdd = csv_path.parents[2].name

    n_edges = sum(len(v) for v in in_by_dest.values())
    print(f"  import-force pairwise: {len(in_by_dest)} dest zones, "
          f"{n_edges} h=1 edges"
          + (f", beta={beta:.4g}" if beta else ""))
    return {
        "in_by_dest": in_by_dest,
        "horizon": 1,
        "beta": beta,
        "yyyymmdd": yyyymmdd,
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

## Task 2: Wire the loader into the payload (page-scoped)

**Files:**
- Modify: `Scripts/common/payload.py` (call site near line 134; return dict at 152–194)
- Modify: `Scripts/common/chrome.py` (add page-scope filter in `render_page`, line 445)

**Why page-scoping:** `render_page()` (chrome.py:470) serializes the *entire* shared payload
into `<script id="payload">` on **every** page. `import_force_pairwise` is ~130k triples and
is only read on the `epi-trends` (spatial-risk) page, so injecting it into the shared payload
would add multiple MB to all 7 pages. Step 3 strips it from every page except spatial-risk.

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

- [ ] **Step 3: Page-scope the heavy key in `render_page`**

In `Scripts/common/chrome.py`, add a module-level map near the other constants (above
`def render_page`, ~line 445):

```python
# Payload keys only one view reads; stripped from every OTHER page's inline
# payload so a big per-view blob doesn't bloat pages that never use it. Map:
# payload key -> set of view_ids allowed to carry it.
_PAGE_SCOPED_PAYLOAD_KEYS = {
    "import_force_pairwise": {"epi-trends"},
}
```

Then, inside `render_page`, replace the `payload_json = json.dumps(payload, …)` line
(currently line 460–461) with a filtered copy:

```python
    scoped_payload = {
        k: v for k, v in payload.items()
        if k not in _PAGE_SCOPED_PAYLOAD_KEYS or view_id in _PAGE_SCOPED_PAYLOAD_KEYS[k]
    }
    payload_json = json.dumps(scoped_payload, separators=(",", ":"),
                              default=json_default, allow_nan=False)
```

engine.js reads `PAYLOAD.import_force_pairwise || null`, so the other pages (where the key
is absent) simply see `null` — and they never call `renderFlowArcs` on `epi-trends` anyway.

- [ ] **Step 4: Verify the payload key populates (spatial-risk only)**

Requires the pairwise CSV checked out locally (see Task 5, Step 1 for the one-time data
setup). From the repo root:

```bash
cd Scripts && BUILD_DIR=../../BDBV2026-Data/build DATA_ROOT=../Data \
  DASHBOARD_PLOTS_DIR=../../BDBV2026-Processed_Sensitive_Data/outputs \
  INSP_SITREP_FETCH=0 python -c "from common.payload import build_shared_payload; \
  p=build_shared_payload(); ifp=p.get('import_force_pairwise'); \
  print('LOADER None (do Task 5 Step 1 first)' if ifp is None else \
        ('dests: %d' % len(ifp['in_by_dest']))); \
  print('Aba edges:', (ifp or {}).get('in_by_dest', {}).get('Aba', [])[:2])"
```

Expected (data present): a non-zero dest count and a couple of `[origin, foi, share]`
triples for Aba. If it prints `LOADER None`, do Task 5 Step 1 first.

- [ ] **Step 5: Commit**

```bash
git add Scripts/common/payload.py Scripts/common/chrome.py
git commit -m "feat: expose import_force_pairwise in payload, scoped to spatial-risk page"
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
    // Only origins with a centroid are drawable; compute the per-zone max foi
    // over THOSE, so the widest *visible* arrow reaches full width even if a
    // centroid-less origin had a higher foi (L3).
    const drawable = pairwiseEdges
      .map(function(e) {
        return {origin: e[0], foi: e[1], share: e[2], start: zoneCentroid(e[0])};
      })
      .filter(function(e) { return !!e.start; });
    let maxFoi = 0;
    drawable.forEach(function(e) { if (e.foi > maxFoi) maxFoi = e.foi; });
    drawable.forEach(function(e) {
      const pts = quadraticBezierPoints(e.start[0], e.start[1], hub[0], hub[1], 1);
      const line = L.polyline(pts, {
        color: FLOW_OUT_COLOR,
        weight: flowArcWeight(e.foi, maxFoi),      // 1 + 4*sqrt(foi/maxFoi)
        opacity: 0.82,
        pane: "flow-arcs",
      });
      line.bindTooltip(tf("ui.import_force_tooltip", {
        from: hubDisplayName(e.origin),
        to: flowHubDisplayName(),
        foi: e.foi.toPrecision(2),
        share: (e.share != null ? (e.share * 100).toFixed(1) + "%" : "—"),
      }), {direction: "top", sticky: true});
      line.addTo(flowArcLayer);
      addFlowWingMarker(pts, FLOW_OUT_COLOR, {nearEnd: true});
    });
    // inTotal == inShown here (both the drawable pairwise set) so the stats
    // object stays internally consistent (L1); these fields aren't displayed.
    flowArcStats = {
      outTotal: outs.length, outShown: 0,
      inTotal: drawable.length, inShown: drawable.length,
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
instead of the sibling path. **Keep only one dated dir under `/tmp/st-plots/outputs`** —
`_latest_spatiotemporal_key_outputs_dir()` picks the lexicographically newest date, so a
stray extra date folder would silently retarget the build and the awk spot-check below
(L6).

- [ ] **Step 2: Measure payload size and confirm page-scoping (H1)**

After a full build (Task 4 Step 3), confirm the heavy key is on spatial-risk only and note
its cost. The build already prints each page's MB; also measure the key directly:

```bash
cd Scripts && python -c "import json; from common.payload import build_shared_payload" 2>/dev/null || true
# Sizes of the emitted pages (spatial-risk should be the only large one):
ls -lh output/spatial-risk.html output/trends.html output/index.html | awk '{print $5, $9}'
# The heavy key must appear ONLY in spatial-risk.html:
for f in output/*.html; do
  n=$(grep -c '"import_force_pairwise"' "$f");
  echo "$f: import_force_pairwise occurrences=$n";
done
```

Expected: `output/spatial-risk.html` contains the key (occurrences ≥ 1); **every other page
reports 0**. Note spatial-risk.html's size delta vs the other pages — if it is
unreasonably large for a single page (rough guide: > ~2 MB added over `trends.html`),
flag it and revisit the spec's per-zone cap in a follow-up. This is the measurement the
spec deferred the cap decision on.

- [ ] **Step 3: Spot-check rendered widths against the CSV**

For the zone you inspected, confirm the top-3 origins by `foi` in the CSV match the three
widest arrows:

```bash
awk -F, 'NR==1 || ($2=="Aba" && $3==1)' \
  /tmp/st-plots/outputs/2026-08-03/spatiotemporal/reports/bayes_pairwise_import_force.csv \
  | sort -t, -k7 -gr | head -4
```

Expected: header + the three highest-`foi` rows for Aba; their `origin_zone` order matches
the three thickest arrows into Aba on the map.

- [ ] **Step 4: Verify the fallback path**

Temporarily point at a plots dir with no spatiotemporal reports (e.g. an older date), or
rename the CSV, rebuild, and confirm the build log prints
`no bayes_pairwise_import_force.csv found; … fall back to confirmed cases` and the arrows
render via the old confirmed-cases metric (no crash, `spatial-risk.html` still valid).

- [ ] **Step 5: Final commit (if any verification fixups were needed)**

```bash
git add -A && git commit -m "test: verify import-force arrows end-to-end"
```

---

## Self-review notes

- **Spec coverage:** loader + payload key (Task 1–2), pairwise-only arrows h=1 (Task 4),
  per-zone sqrt-normalized width via `flowArcWeight` (Task 4 Step 2), foi+share tooltip
  (Task 3–4), legend update (Task 3), fallback (Task 4 Step 2 + Task 5 Step 4), all-sources
  no-cap (Task 1 Step 3). Covered.
- **Plan-review incorporations:** H1 payload bloat — key page-scoped to `epi-trends` via
  `render_page` filter (Task 2 Step 3) + size/scoping measurement (Task 5 Step 2). H2 — numeric
  horizon compare + float-horizon regression test (Task 1). M1 — width == share-of-destination
  documented (header); `foi`/`share` both retained (tooltip shows both). M2 — linear-fallback vs
  sqrt-pairwise documented as intentional (header). M3 — `beta` from first positive row, not
  median. L1 — `inTotal == inShown` in pairwise branch. L2 — `yyyymmdd` provenance added. L3 —
  `maxFoi` over drawable edges only. L4 — added missing-columns + float-horizon tests; JS render
  is manual-verify-only (Task 4 Step 3). L5 — None-guarded verification one-liner. L6 —
  single-date scratch note. L7 — re-anchored by symbol.
- **`flowArcWeight` reuse:** `flowArcWeight(count, maxCount) = 1 + 4·√(count/maxCount)`
  already exists (engine.js:576) and is the sqrt mapping the spec calls for — reused
  directly with `(foi, maxFoi)`, no new helper.
- **Naming consistency:** payload key `import_force_pairwise`, JS const
  `IMPORT_FORCE_PAIRWISE`, loader `load_bayes_import_force_pairwise`, structure
  `in_by_dest` → `[origin, foi, share]` — used identically across Tasks 1, 2, 4.
- **Out of scope (do not touch):** `build_dashboard_public.py` (superseded),
  `invasion_risk` ingestion, snapshot-view arrows, Analysis/CI pipeline.
