# Critical review — Spatial-risk import-force arrows plan

**Reviewed doc:** `docs/superpowers/plans/2026-08-04-spatial-risk-import-force-arrows.md`
**Against spec:** `docs/superpowers/specs/2026-08-04-spatial-risk-pairwise-import-force-arrows-design.md`
**Branch:** `spatial-risk-import-force-arrows`
**Date:** 2026-08-04 (re-reviewed same day after plan revision)

---

## Re-review (round 2) — after plan revision

The revised plan addresses **every** item from round 1. I re-verified the new material
against source; it holds up. Status per item:

| Item | Status | Notes |
|------|--------|-------|
| H1 payload bloat | **Resolved** | Key page-scoped via `_PAGE_SCOPED_PAYLOAD_KEYS` filter in `render_page` (Task 2 Step 3) + explicit size/occurrence measurement (Task 5 Step 2). |
| H2 horizon filter | **Resolved** | Now `pd.to_numeric(df["horizon"], errors="coerce") == 1`; added `test_loader_handles_float_horizon_column` locking in the `1.0` case. |
| M1 width == share | **Resolved** | Documented in the new "Width metric note" header; `foi`/`share` kept for the tooltip only, stated explicitly. |
| M2 linear vs sqrt curves | **Resolved** | "Width-curve note" header accepts it intentionally (see nit N3 on wording). |
| M3 beta median | **Resolved** | Now takes the first positive-`import_force` row, so drift surfaces instead of averaging away. |
| L1 stats inTotal | **Resolved** | `inTotal == inShown == drawable.length` in the pairwise branch. |
| L2 provenance | **Resolved** | `yyyymmdd` added to the return dict (`csv_path.parents[2].name`, verified correct). |
| L3 maxFoi over drawable | **Resolved** | New `drawable` filter computes `maxFoi` over centroid-having origins only. |
| L4 test gaps | **Resolved** | Added missing-columns + float-horizon tests; JS render noted manual-verify-only. |
| L5 verify one-liner | **Resolved** | Now `p.get(...)` + None-guarded print. |
| L6 single-date scratch | **Resolved** | Warning added to Task 5 Step 1. |
| L7 line anchoring | **Resolved** | Re-anchored by `_INVASION_AFFECTED_MASK_FIELDS` symbol. |

**New material verified against source (the risky parts of the revision):**

- **Page-scoping is correct and load-bearing-safe.** `render_page(view_id, payload, …)`
  exists at `chrome.py:445`; the `json.dumps(payload, separators=(",",":"),
  default=json_default, allow_nan=False)` line the plan replaces is verbatim at
  `chrome.py:460–461`; `json_default` is imported at `chrome.py:18` (in scope for the
  replacement). Critically, `spatial_risk.py` passes `VIEW_ID = "epi-trends"` and that view
  renders `spatial-risk.html` — so the scope-map key `"epi-trends"` keeps the blob on
  exactly the page that reads it and strips it from the other six. If the key had been
  wrong (e.g. `"spatial-risk"`), the feature would have silently self-disabled; it's right.
- **The float-horizon test genuinely exercises H2:** a blank `horizon` cell forces pandas
  to a float column, `pd.to_numeric(...) == 1` keeps only the `1.0` row — the numeric
  filter is what makes this pass where the old stringify-vs-`"1"` compare would have
  returned `None`.
- **`yyyymmdd = csv_path.parents[2].name`** resolves to the date folder
  (`reports`→`spatiotemporal`→`<date>`) — correct.
- **Task 5 Step 2 grep** works as intended: the minified payload is one line, so
  `grep -c '"import_force_pairwise"'` yields 1 on spatial-risk.html and 0 elsewhere.

### Remaining nits (all trivial, non-blocking)

- **N1.** Task 1 Step 4 still says "Expected: PASS (**2 passed**)" — there are now **4**
  tests. Update the count.
- **N2.** Task 5 Step 2's first command,
  `python -c "import json; from common.payload import build_shared_payload" 2>/dev/null || true`,
  is a no-op (imports, does nothing, swallows errors) — it neither builds nor measures.
  Drop it; the `ls -lh` and the per-file `grep` beneath it are what actually verify scoping.
- **N3.** The "Width-curve note" header says the fallback "won't run in production." It runs
  whenever the CSV is absent — normally not, but on an older build or a CI publish failure
  it *does* run in prod. The reasoning (not worth changing the established curve) still
  holds; just soften "won't run in production" to "rarely runs in production."
- **N4.** (Carried, still fine) If a hub has pairwise edges but *no* origin has a centroid,
  `drawable` is empty and the branch draws nothing and returns rather than falling through
  to confirmed-cases. Near-impossible given the spec's 0-mismatch name check; acceptable as
  is — noting only so it's a conscious choice.

**Round-2 verdict:** ready to implement. Address N1–N3 opportunistically (doc-only). No
code-logic concerns remain.

---

## Verdict (round 1 — original review, retained for history)

The plan is well-anchored and mostly implementable as written — I verified every
file/line reference and helper-function dependency against the current source and they
hold up (details in "Anchor verification" below). The TDD flow is sound and the fallback
design is safe. **But it silently drops the one risk the spec explicitly flagged (payload
size), and it has a real robustness bug in the horizon filter that can turn the whole
feature into a silent no-op.** Recommend addressing H1 and H2 before implementing; the
rest are worth folding in but not blocking.

---

## High / should-fix before implementing

### H1. Payload bloat is unmeasured, and the key lands in the *shared* payload (every page)

The spec called this out directly:

> "Note payload size: with all h=1 sources this is ~130k edge triples. Check the resulting
> page size during testing; if it's a problem, revisit (per-zone cap, or scope the key to
> the spatial-risk page only)."

The plan **has no step that measures the payload or `spatial-risk.html` size.** Task 5
verifies edge counts, width ordering, and the fallback path, but never the size concern.

Worse, Task 2 injects `import_force_pairwise` into `build_shared_payload()`'s return dict
(`Scripts/common/payload.py:152`), i.e. the payload shared across **all** pages, not just
spatial-risk. If ~130k `[origin, foi, share]` triples serialize into every HTML page, that
is a multi-MB regression on pages that never draw these arrows. The spec's own suggested
mitigation ("scope the key to the spatial-risk page only") is not carried into the plan.

Also note `engine.js` only ever reads `in_by_dest`; `horizon`, `beta`, and `source` are
dead weight in the payload (tiny, but they confirm nobody's watching size).

**Fix:** add a Task-5 step that prints `len(json.dumps(payload['import_force_pairwise']))`
and the on-disk size of `Scripts/output/spatial-risk.html` before/after, with a stated
threshold. If it's large, apply the spec's fallback (per-zone cap or page-scoped key)
rather than deferring — the spec deferred it *conditional on measuring*, and the plan
skips the measurement.

### H2. Horizon filter compares a stringified value to `"1"` — fragile to `1.0`

Task 1 Step 3:

```python
df = df[df["horizon"].astype(str).str.strip() == "1"].copy()
```

If pandas parses the `horizon` column as float (which it will if any cell is blank or the
column is otherwise non-integer — a common CSV reality), `astype(str)` yields `"1.0"`, the
filter matches **zero** rows, the loader returns `None`, and the build **silently falls
back to confirmed cases** with only a benign-looking log line. The feature would appear
"done" and shipped but never actually render.

The unit test doesn't catch this: its inline CSV has clean integer `horizon` values, so
the column reads as int64 and stringifies to `"1"`.

**Fix:** compare numerically —
`df[pd.to_numeric(df["horizon"], errors="coerce") == 1]` — and add a test case with a
float-typed horizon column (e.g. a row with a blank horizon that forces float parsing) to
lock it in. Bonus: check how `load_invasion_risk_estimates()` compares horizon and match
it, since the spec's whole premise is that the two stay in sync on h=1.

---

## Medium

### M1. Per-zone normalization makes `foi` and `share` produce *identical* widths — the "import-force-scaled" framing oversells what the eye sees

The spec is explicit (Design decision #2): under per-zone normalization, `foi`,
`share_of_dest`, and `import_force` yield identical arrow widths, because they differ only
by a per-destination constant that cancels. So despite the loader machinery around `foi`,
**the visual is mathematically "each origin's share of the selected zone's total import
force,"** and `foi` matters *only* for the tooltip number.

This is a legitimate, accepted design choice, but the plan's Goal/Architecture prose
("arrows scale with each origin's Bayesian import-force contribution") reads as if `foi`
drives the width. Anyone maintaining this later will be confused that swapping `foi`→`share`
changes nothing visually. Two consequences worth deciding on:

- The loader carries **both** `foi` and `share` per edge (payload weight, see H1) when the
  width needs neither beyond ordering. Consider carrying only what the tooltip shows.
- State plainly in the plan that width == share-of-destination; `foi` is tooltip-only.

### M2. Fallback path stays *linear*; pairwise path is *sqrt* — two different width curves

Existing epi-trends inflows use `flowArcWeightNormalized(frac) = 1 + 4·frac` (**linear**,
`engine.js:581`). The plan's new pairwise block uses `flowArcWeight(foi, maxFoi) =
1 + 4·√(frac)` (**sqrt**, `engine.js:576`). The spec does ask for sqrt (decision #3), so
the pairwise curve is intentional — but the plan never notes that the **fallback** (data
absent) still renders with the *linear* curve. So the same page can look meaningfully
different in mid-range widths depending only on whether the CSV was present. Endpoints
match (frac 0→1.2/1.0, frac 1→5), so it's a mid-range shape difference, not a max mismatch.

**Fix:** either accept and document it, or switch the pairwise path to
`flowArcWeightNormalized` for curve-consistency with the fallback (and drop the sqrt
requirement), or migrate the fallback to sqrt too. Pick one deliberately.

### M3. `beta` uses the median across rows; spec says it's a single global constant

Loader computes `beta = median(foi / import_force)` over positive rows. The spec says
`beta = foi / import_force` is "a single global constant … derivable from any row." If it
truly is constant, median == any row (fine). If it *isn't* (data-quality drift), the median
silently papers over it instead of surfacing it. Since `beta` is informational only and
never read by `engine.js`, this is low-stakes — but if you keep it, consider asserting
near-constancy (or just take the first row and note the assumption) rather than hiding
variance behind a median.

---

## Low / nits

### L1. `flowArcStats.inTotal = ins.length` is semantically wrong in the pairwise branch

In the new block, `inShown = pairwiseEdges.length` (the pairwise set) but
`inTotal = ins.length` (the *Flowminder* inflow set) — two different data sources. For a
pairwise-only zone these diverge (e.g. inShown 5, inTotal 0). **Harmless in practice**:
the `flow_arc_summary` i18n template (`en.yaml:108`) only interpolates `{outShown}` and
`{inShown}`, so `inTotal`/`outTotal` are never displayed. Still, set
`inTotal: pairwiseEdges.length` so the stats object isn't internally contradictory if a
future HUD starts showing totals. (`clearFlowArcs()` at line 550 nulls the object, so no
stale-state risk.)

### L2. Return-dict diverges from spec (`cutoff_date`/`yyyymmdd` dropped)

Spec return shape: `{in_by_dest, horizon, beta, cutoff_date, yyyymmdd}`. Plan return:
`{in_by_dest, horizon, beta, source}`. The plan drops the date provenance the spec included
(which would let the UI confirm arrows and the invasion-risk table came from the same run
date) and adds `source` (filename), which `engine.js` never reads. If the "arrows and table
always come from one pipeline run" guarantee is meant to be *visible/auditable*, keep the
date fields; otherwise note the intentional drop.

### L3. `zoneCentroid(origin)` miss is silently skipped but still counts toward `maxFoi`

The pairwise block computes `maxFoi` over **all** edges, then `if (!start) return;` skips
any origin lacking a centroid. If the true max-`foi` origin has no geometry, the widest
*visible* arrow won't reach full width. The spec verified 0 name mismatches against 519
`nom` keys, so this is near-zero risk today — but a defensive note (or computing `maxFoi`
only over drawable edges) would harden it against future CSV drift.

### L4. Test coverage gaps

The two tests cover the happy path, h=2 filtering, zero/negative `foi` drop, `beta`, and
the None-when-absent case — good. Not exercised:
- the missing-required-columns branch (returns `None` with a warning),
- the `share_of_dest` NaN → `None` fallback (`float(share) if pd.notna(share) else None`),
- empty `origin_zone`/`dest_zone` skip branches,
- the float-horizon case from **H2** (the important one).

The `engine.js` pairwise rendering has no automated test at all — only manual verification
in Task 4 Step 3. That's consistent with the codebase's untested-JS convention, so it's
acceptable, but worth stating that the render path is manual-verify-only.

### L5. Verification one-liner traceback when data absent

Task 2 Step 3's one-liner does `ifp = p['import_force_pairwise']; ... ifp['in_by_dest']`.
When the loader returns `None`, this raises `TypeError: 'NoneType' object is not
subscriptable` — a traceback, not the "prints `dests: 0`-style `NoneType`" the plan
describes. Minor, and the plan does tell you to run Task 5 Step 1 first, but the guard
wording is inaccurate.

### L6. Task 5 data setup is pinned to `2026-08-03` and to "newest date wins"

Task 5 Step 1 archives `origin/main outputs/2026-08-03`. `_latest_spatiotemporal_key_
outputs_dir()` selects the **lexicographically newest** dated dir under
`DASHBOARD_PLOTS_DIR`. If the pipeline advances past that date (or `/tmp/st-plots` picks up
other dated dirs), the manual commands and the awk spot-check silently target a different
run than the one you extracted. Operational nit — note that only one date should live under
the scratch outputs root.

### L7. Trivial line-number drift

Task 1 Step 3 says the loader goes "before the `_INVASION_AFFECTED_MASK_FIELDS` block at
line 1641." The assignment is actually at **1643** (1641 is the start of its comment).
`load_invasion_risk_estimates()` does end at 1638 as stated. Immaterial, but re-anchor by
symbol, not raw line, when implementing.

---

## What checks out (so implementers don't re-verify)

**Anchor verification — all confirmed against current source:**

- `flowArcWeight` at `engine.js:576` is exactly `1 + 4·√(count/maxCount)` ✓
- `renderFlowArcs` spans 634–733; `useImportPressure` at 647; `inSorted.forEach` at 686 ✓
- Every helper the new block calls exists and matches the plan's usage: `zoneCentroid`,
  `quadraticBezierPoints(...,1)`, `addFlowWingMarker(pts, color, {nearEnd:true})`,
  `hubDisplayName(origin)`, `flowHubDisplayName()`, `tf`, `FLOW_OUT_COLOR` ✓
- **Color is correct:** epi-trends inflows already draw with `FLOW_OUT_COLOR`
  (`engine.js:696`), so the plan's `FLOW_OUT_COLOR` (not `FLOW_IN_COLOR`) is right despite
  the "red inflow" naming ✓
- The new block's variables (`outs`, `ins`, `hub`, `hubNom`, `useImportPressure`) are all
  in scope at the insertion point (defined 638–647) ✓
- `_latest_spatiotemporal_key_outputs_dir` at 1409 reads the module-global
  `DASHBOARD_PLOTS_DIR` (imported at `data_sources.py:38`), so the test's
  `monkeypatch.setattr(ds, "DASHBOARD_PLOTS_DIR", ...)` will take effect ✓
- The resolver requires `bayes_risk_scores_all_zones.csv` to exist (line 1425); the test's
  `_make_outputs` creates it ✓
- **Import is covered:** `payload.py:17` is `from common.data_sources import *`, and Task 1
  Step 5 adds the loader to `__all__`, so the star-import picks it up (no explicit import
  step needed) — *but this makes Step 5 load-bearing: skip it and payload.py NameErrors* ✓
- payload anchors: `flow_catalogs = {...}` at line 135, `"invasion_risk": invasion_risk,`
  at line 190 ✓
- locale anchors: `importation_pressure_tooltip` at `en.yaml:101`,
  `importation_pressure_width` at `en.yaml:211`, `chrome.py:302` legend div ✓
- The unit test's numeric expectations are self-consistent (sorted `[Bunia, Nizi]`,
  `foi=0.16`, `share=0.5`, `beta=0.16`) ✓
- Fallback safety: pairwise block is gated on `useImportPressure` and early-returns, so the
  snapshot (`current-snapshot`) view and the confirmed-cases path are genuinely untouched ✓

**Design/process strengths:** proper red→green TDD, explicit "do not touch
`build_dashboard_public.py` (superseded)" scope guard, fallback preserves no-regression on
old builds, naming is internally consistent (`import_force_pairwise` /
`IMPORT_FORCE_PAIRWISE` / `load_bayes_import_force_pairwise` / `in_by_dest`).

---

## Suggested priority order

1. **H2** (horizon filter) — silent-no-op bug; cheap fix + one test.
2. **H1** (payload size measurement + page-scoping decision) — the spec's explicit ask.
3. **M1/M2** — decide and document the width-metric equivalence and the linear-vs-sqrt
   curve split.
4. Fold in L1, L4 (float-horizon test) opportunistically; L2/L3/L5/L6/L7 are optional.
