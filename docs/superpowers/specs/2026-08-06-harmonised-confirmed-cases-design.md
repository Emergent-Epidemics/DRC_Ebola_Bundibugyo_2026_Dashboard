# Harmonised confirmed cases — design

**Date:** 2026-08-06
**Status:** Draft — revised through 3 review passes; ready for implementation-plan review.
**Repos touched:** `BDBV2026-Analysis` (model), `BDBV2026-Epidemic_Dashboard` (dashboard), and one config bump in `BDBV2026-Processed_Sensitive_Data` (`ANALYSIS_REF`).
**Revised** 2026-08-06 after four critical-review passes (`…-review.md`). Pass 1 (provenance/delivery): corrected the delivery path (B1), added name-normalisation + coverage assertion (B2), pinned the invariant to the training cutoff (H1), grounded the no-white guarantee empirically + added a defensive fill (H2), kept sitrep suspected/deaths on the shared marker (M3). Pass 2 (engine render pipeline): added the colour **domain** (`recomputeEpiTrends`) to the engine sites (S1) and its global re-shade consequence (S2); corrected the readout claims — the marker is the *only* spatial-risk confirmed readout, so no ranked-table/hover change (S3/S4); and masked the downloadable CSV to match the map (S5). Pass 3 (file targeting / call order): re-pointed every build-side edit from the **dead** `build_dashboard_public.py` monolith to the live `common/data_sources.py` (F1), and pinned the `effective` write to happen **before** `payload.py:97` so `build_active_case_markers` sees it (F2). Pass 4 (fresh-context, incl. model repo): re-pointed §5 from the **dead** `spatiotemporal_conditional/` tree to the live `spatiotemporal/` (FP-1) and added the `run_all.R` key_outputs gather step; deferred the active-zone assertion past `payload.py:116` (FP-2); added the epi-trends **arrows** as a fourth engine consumer (FP-3); reframed reconcile as a no-op — the fix is the default-0 `effective` write + engine reads (FP-4); documented the download-mask plumbing + its reversal of a documented invariant (FP-5); required a default-0 `effective` write for **all** zones (FP-6); and flagged the mixed-source marker `total` + empirical re-verification (FP-7).

---

## 1. Motivation

On the spatial-risk map, two health zones (Rethy and Bafwasende, in the live build
`origin/main@5648ee5`) render **transparent / near-white** despite the recently updated
colour scheme. Root cause, verified by simulating `epiTrendsStyleFn` over the live payload:

- The spatial-risk map colours each zone by one of two variables chosen by `was_active_before`:
  active → confirmed cases (orange ramp); not-active → `p_case_invasion` (purple ramp).
- A zone flagged `was_active_before = true` whose `confirmed_cases` is **null** falls through
  to `fillOpacity: 0` (transparent → basemap shows through → reads white). The colour ramp is
  never reached.
- These zones are `was_active_before = true` (from the invasion model) but have **no per-zone
  confirmed count** in the data the dashboard renders from.

The deeper cause is a **provenance split between two case datasets**:

| Field | Pipeline | Case source |
|-------|----------|-------------|
| `was_active_before` (+ `p_case_invasion`) | invasion **model** (`Bayes-M10-med`) | **line list ∪ sitrep** (harmonised) |
| `confirmed_cases` / active-case markers / all observed-case surfaces | dashboard | **INSP sitrep** only (WHO epi fallback) |

The model's `affected_zones()` already means "confirmed > 0 in line-list ∪ appended sitrep"
(`15_workhorse.R`), so it correctly marks Rethy/Bafwasende active — but that per-zone
**count** is aggregated away before the dashboard's geojson (which carries per-zone counts
only from `insp_sitrep`; the `aggregated_insp_linelist` block is national/provincial `NA`).
So the dashboard has `active = true` with no number to render.

Confirmed across all 519 zones in the geojson: per-zone confirmed counts exist for **54**
zones via `insp_sitrep`, **7** via WHO `epi`, and **0** via line-list (national aggregates only).

## 2. Goal

Surface the model's **harmonised** (line-list ∪ sitrep) per-zone confirmed counts to the
dashboard, so that:

1. Zones confirmed by the line list but absent from the sitrep stop rendering white on the
   spatial-risk map and appear as active-case zones.
2. Active-case **markers** everywhere reflect the harmonised picture.
3. The change is contained: only the spatial-risk polygon colouring and the shared markers
   use the harmonised data; every other tab's polygon colouring is untouched.

## 3. Non-goals / out of scope

- **Triggering the model on sitrep updates.** The entire model/processing chain is line-list
  triggered today (`run-processing-code-pipeline.yml` fires on Linelist_Processing syncs;
  `run-spatiotemporal.yml` chains off it). Sitrep reaches the pipeline only via the model's
  synced snapshot and the dashboard's live insp.cd fetch. Making the model always-fresh
  w.r.t. sitrep is a separate infrastructure project (see §9).
- Changing the invasion model's statistical machinery, kernels, or CV.
- Changing any observed-case surface outside the spatial-risk polygon + shared markers.

## 4. Design overview

Four moving parts:

1. **Model** emits a new per-zone harmonised confirmed-cases artifact (data it already
   computes internally).
2. **Delivery** reuses the existing sensitive-data → dashboard automation.
3. **Dashboard build** ingests it, computes an `effective` count (harmonised topped up with
   the dashboard's fresher live sitrep), and routes it through the existing reconcile.
4. **Dashboard engine** uses `effective` for the shared markers, the spatial-risk orange
   colouring, and the spatial-risk in-tab readouts — nothing else.

## 5. Model side — new artifact (`BDBV2026-Analysis`)

> **Live path only (FP-1).** The shipped pipeline is **`spatiotemporal/`**, *not*
> `spatiotemporal_conditional/`: `run_spatiotemporal.sh:55` defaults `PIPELINE=spatiotemporal/run_all.R`,
> and CI collects `analysis/spatiotemporal/outputs` (`run-spatiotemporal.yml:145`). The two trees
> **differ** (not copies) and `_conditional/` ships nothing. **Every model edit below targets
> `spatiotemporal/…`** — editing `spatiotemporal_conditional/` is the model-side mirror of the F1
> dead-file trap.

The model already computes `zone_week` = confirmed cases from line-list ∪ appended sitrep, and
`affected_zones(zone_week, cutoff)` (`spatiotemporal/15_workhorse.R:75`) already means
`confirmed > 0` up to the training cutoff. `bayes_risk_scores_all_zones.csv` (carrying
`was_active_before`) is written to `OUT_REPORTS` (`spatiotemporal/run_all.R:898`).

Add an export from the same run, in two steps that mirror how `bayes_risk_scores_all_zones.csv`
already flows:

1. **Write** `harmonised_confirmed_cases.csv` to `OUT_REPORTS` (as at `run_all.R:898`).
2. **Add it to the `key_outputs/` gather list** (`run_all.R:1453-1481`, which `file.copy`s a
   fixed set of report files into `key_outputs/`) — otherwise it never reaches `key_outputs/`
   and the dashboard never sees it. This is the model-side allowlist (B1 refinement).

```
key_outputs/harmonised_confirmed_cases.csv
  health_zone, cumulative_confirmed_cases      # one row per zone (not per forecast horizon)
```

- The value is the per-zone **cumulative confirmed count from `zone_week`, evaluated at the same
  `training_window_end` that drives `was_active_before`** (i.e. `affected_zones(zone_week, cutoff)`
  and this count use one cutoff). It is *not* cumulated over all weeks — a first case landing
  after the cutoff must not appear here, or the invariant below breaks.
- **Invariant (by construction, at that cutoff):**
  `cumulative_confirmed_cases > 0 ⟺ was_active_before = TRUE`, because both derive from the same
  `zone_week` at the same `training_window_end`. This invariant underpins the "no white"
  guarantee (§9); the §10 model test asserts it *at the cutoff*, not over arbitrary horizons.
- `health_zone` is emitted in the **same spelling** as `bayes_risk_scores_all_zones.csv` (so it
  joins to the dashboard exactly as the invasion table does); the loader normalises regardless
  (§7, B2).

## 6. Delivery path (minimal infra — one `ANALYSIS_REF` bump)

Correcting the earlier draft (B1): the dashboard's **live** invasion data does *not* come from
`DATA_ROOT`. `load_invasion_risk_estimates()` resolves the newest
`<outputs>/<date>/spatiotemporal/key_outputs/bayes_risk_scores_all_zones.csv` under
`DASHBOARD_PLOTS_DIR` (via `_latest_spatiotemporal_key_outputs_dir()`,
`data_sources.py:1645`); the committed `Data/invasion_risk_model_estimates.csv` is only a legacy
fallback. So the new artifact must land in that dated `key_outputs/` dir, and the new loader must
resolve it from there too.

```
run_all.R writes reports/harmonised_confirmed_cases.csv AND gathers it into key_outputs/ (§5)
  → run-spatiotemporal.yml: analysis/ci/collect_outputs.sh does `cp -R "$KEY/."`
    (copies the WHOLE key_outputs/ bundle wholesale — no collect_outputs.sh edit needed;
     its strict allowlist only governs the separate reports/ copy)
  → published to BDBV2026-Processed_Sensitive_Data/main
  → trigger-dashboard-rebuild.yml
  → dashboard reads it from the same dated key_outputs/ dir as bayes_risk_scores_all_zones.csv
```

**Required steps (all inherent to shipping the model change, no standalone infra):**
1. `run_all.R`: write the CSV **and** add it to the `key_outputs/` gather list (§5) — the
   model-side allowlist. Miss this and the file never leaves the model repo.
2. Bump the pinned `ANALYSIS_REF` in `run-spatiotemporal.yml` to the `BDBV2026-Analysis` commit
   that emits it.
3. `collect_outputs.sh` needs **no** change *because the file is in `key_outputs/`* (wholesale
   `cp -R`); it would only need an allowlist edit if placed under `reports/` alone.

## 7. Dashboard build (Python)

> **Live path only (F1).** CI ships `Scripts/build_dashboard.py` → `common/payload.py`
> (`build_shared_payload`) → `common/data_sources.py`. **`Scripts/build_dashboard_public.py` is
> the dead pre-refactor monolith** — not imported, not referenced by CI (only mentioned in
> `common/*.py` docstrings as the file this code "moved out of"). It contains stale *duplicates*
> of `build_active_case_markers`, the case-field construction, etc. **All edits below target
> `common/data_sources.py` / `common/payload.py`; the monolith must not be edited** (editing it
> changes nothing shipped, and the fix would look done while markers stay broken). Whether to
> delete the monolith is a separate cleanup, out of scope here.

**Call-order constraint (F2).** In `payload.py` the sequence is fixed: `load_metadata` (`:34`) →
`build_active_case_markers` (`:97`) → `load_invasion_risk_estimates` (`:116`) →
`reconcile_invasion_active_cases` (`:121`). Markers are built at **line 97**, *before* the invasion
machinery. Therefore the **harmonised load and the per-zone `effective` write into `zone_data` must
happen before line 97** — not alongside the invasion load at 116–121 — or the markers never see
`effective` and the harmonised-only-markers goal (§2) silently fails.

- **Loader:** new function in `Scripts/common/data_sources.py` beside
  `load_invasion_risk_estimates()` that reads `harmonised_confirmed_cases.csv` from the dated
  `key_outputs/` dir (via `_latest_spatiotemporal_key_outputs_dir()`, **not** `DATA_ROOT`) →
  `{nom: harmonised_confirmed}`. It **must** (B2):
  - apply `_NAME_TO_NOM` normalisation (`data_sources.py:277`) to the `health_zone` key — unlike
    `load_invasion_risk_estimates()` today, which keys by the raw string (`data_sources.py:1806`)
    and is the odd loader out; `load_confirmed_cases_timeseries` and others already normalise
    (`data_sources.py:2152`). (Worth fixing the invasion loader the same way while here.)
  - **`nom`-coverage warning (in the loader):** the GeoJSON `nom` set is available early, so the
    loader can warn on any `health_zone` not matching a `nom`.
  - **active-zone hard check (deferred, FP-2):** the invariant-backed "any `was_active_before` zone
    with no matched harmonised count is a **build error**" check **cannot** live in the loader —
    F2 runs the loader before line 97, but `was_active_before` is only known after
    `load_invasion_risk_estimates()` at `:116`. Run this assertion **after line 116** (or inside
    `reconcile`), where both fields exist. A silent drop here reproduces the white-zone bug.
- **Effective count:** in `payload.py`, **before line 97** (F2), per zone compute
  **`effective = max(harmonised, sitrep_confirmed)`** with explicit defaults —
  `harmonised.get(nom, 0)` and sitrep `None → 0` (never call `max(None, …)`) — and write it into
  **every** `zone_data` rec as **`effective_confirmed_cases`**, **defaulting to 0 for all zones**
  (FP-6). A zone left `undefined` (e.g. one only in the GeoJSON, not the CSV) re-triggers the white
  state in the engine (`v != null` false → transparent), so the default-0 write for *all* zones —
  not only CSV-listed ones — is load-bearing. `sitrep_confirmed` is the current
  `zone_data.confirmed_cases` (built in `load_metadata`, `data_sources.py:2875-2885` — live-fetched
  INSP sitrep, WHO epi fallback — often *fresher* than the model's snapshot).
  - **Honest framing (M1):** `max()` is a pragmatic **freshness top-up**, a *lower bound* on the
    true current union — not a merge. If the line list contributed cases the fresher sitrep never
    had *and* the sitrep has since grown on other cases, `max` undercounts the true union. This
    never breaks "no white" (`effective ≥ harmonised`), but the displayed count can be lower than
    reality. The §11 follow-up (model always fresh) is what yields the exact union.
- **Reconcile: leave unchanged (FP-4).** The earlier draft proposed generalising
  `reconcile_invasion_active_cases()` to gate on `effective`. This is a **no-op** and should be
  dropped to avoid implying that's where the fix lives: reconcile only inspects *non-active* zones
  (`if row.was_active_before: continue`), and by the §5 invariant those all have `harmonised = 0`,
  so `effective = max(0, sitrep) = sitrep` — identical to what it already reads
  (`data_sources.py:2051`). Reconcile keeps its existing, orthogonal role (promote at-risk zones on
  fresh sitrep, mask their invasion outputs, renormalise ranks). **The white-zone fix is entirely
  (a) the default-0 `effective_confirmed_cases` write into `zone_data` and (b) the engine reading
  it (§8)** — not reconcile.
- **Payload:** `effective_confirmed_cases` (written above) rides through in `zone_data`.
- **Downloadable CSV (S5), with the plumbing FP-5 surfaces.** Per decision, **mask the download to
  match the map**: null `p_case_invasion` (and the other `_INVASION_AFFECTED_MASK_FIELDS`) for zones
  with `effective > 0`. Two non-trivial facts the one-liner hid:
  - `download_csv` is captured as a **serialized all-horizons/all-zones string inside the loader**
    (`data_sources.py:1744`), *before* reconcile and before `effective` exists. Masking it means
    either computing `effective` early enough to pass into the loader, or masking the DataFrame
    (every horizon row per zone) after `effective` is known and re-serialising — real cross-function
    wiring, not a one-line filter.
  - It **reverses a documented invariant**: `reconcile`'s docstring states "The raw `download_csv`
    is left untouched" (`data_sources.py:2036`). That line must be updated and the reversal called
    out, so the change is a conscious decision rather than a silent contradiction.
- **Marker builder:** `build_active_case_markers` (**live copy `common/data_sources.py:3049`**,
  not the monolith) gates on `effective_confirmed_cases > 0` (instead of `confirmed_cases > 0`) and
  emits it as the marker's `confirmed` count, while **still emitting the existing sitrep-sourced
  `suspected` and `confirmed_deaths` fields** (`data_sources.py:3068-3072`) — see §8/M3. Because
  `effective_confirmed_cases` is written to `zone_data` before line 97 (F2), this call sees it.

### Freshness safeguard rationale

The `max()` is **not** the dashboard re-deriving the union. It is an extension of behaviour the
dashboard already ships: `reconcile_invasion_active_cases()` already tops up the active *flag*
from the dashboard's live sitrep. This widens that same top-up to the *count*, covering the
window between the model's sitrep snapshot and the dashboard's live fetch. It is the interim
until the §11 follow-up lands, after which it can retire.

## 8. Dashboard engine (`Scripts/assets/engine.js`)

The spatial-risk confirmed-case surface is **four** functions that must all read the **same**
`effective` field, so the colour domain, the fill, the marker, and the arrows can never disagree.
(Line numbers below are approximate and drift between builds — resolve against the current tree at
implementation, FP-7.)

- **Colour domain — `recomputeEpiTrends` (`engine.js:1259-1268`) [S1, was missing].** The orange
  scale `epiCasesDomain` is built by pushing active zones' **`ZONE_DATA[nom].confirmed_cases`**
  into `caseVals` (gated `> 0`). This **must switch to `effective`** in lockstep with the style
  fn — otherwise a harmonised-only zone (null `confirmed_cases`, `effective > 0`) is excluded from
  the domain, and the style fn then scales its `effective` against a range that doesn't contain it
  → clamps to darkest/lightest, mis-colouring the very zones this change adds.
- **Fill — `epiTrendsStyleFn` (`engine.js:1310`).** The confirmed-case (orange) path colours by
  `effective` instead of `ZONE_DATA[nom].confirmed_cases`. The branch stays keyed on
  `was_active_before`, which now `⟺ effective > 0`.
- **Marker tooltip — `caseMarkerTooltip` (`engine.js:3322`), all views.** The shared `caseLayer`
  is built once from `PAYLOAD.active_case_markers` (gated/populated on `effective` by the build,
  §7). Shows the **harmonised confirmed** number for the Confirmed row, and **keeps the existing
  sitrep-sourced Suspected and Confirmed-deaths rows** (M3). This is the **only** per-zone
  confirmed readout in the spatial-risk view — so `effective` on the marker already makes colour
  and number agree, with nothing else to change. (Note the build's marker `total = conf + susp`
  (`data_sources.py:3074`) becomes mixed-source once `conf → effective`; fold into the M4 note.)
- **Arrows — `zoneConfirmedCases` (`engine.js:635`) → `importationPressure` (`:642`) [FP-3].** In
  epi-trends (`useImportPressure = activeView === "epi-trends"`, `:710`), the confirmed-cases
  spatial-risk **arrows** are weighted by origin-zone `ZONE_DATA[nom].confirmed_cases`. Left
  unchanged, a harmonised-only origin (e.g. Rethy) contributes **0** importation pressure while
  being newly rendered as an active orange zone — an internal contradiction in this very view.
  `zoneConfirmedCases` should read `effective_confirmed_cases`. (Impact is bounded: this path is
  **superseded when `IMPORT_FORCE_PAIRWISE` is present** (`:753`), and is the documented fallback —
  see [[spatial-risk-arrow-width-source]] — but the fallback should still be consistent.)

**No other spatial-risk readout shows a confirmed count (verified — corrects the earlier draft,
S3/S4):** the ranked table (`renderEpiTrendsTable:1223`) has **no confirmed column** (province /
zone / p_inv / CI / rr / rr-rank / priority / priority-rank; active zones show "—" for the masked
invasion metrics); the epi hover float (`updateEpiFloat:1086`) shows only surveillance / access /
social-vulnerability gaps; and the `confirmed_cases` info panel (`infoHTML:1635`) is wired **only**
to the Snapshot `#info-body` (`renderMapInfoBox`, `mapSelectedNom`), **not** epi-trends. Per the
decision, **no confirmed column is added to the ranked table** — the marker suffices. `infoHTML`
is left untouched (editing it would change the out-of-scope Snapshot panel).

- **Global re-shade is expected, not per-zone-local [S2].** Because `epiCasesDomain.max` is
  `max(caseVals)` (`engine.js:1287`), admitting harmonised-only zones can **raise the domain max
  and re-shade every orange zone** (the log scale compresses the previously-known zones lighter).
  This is a correct consequence of a correct fix, but it is a *visible* change to zones §9's table
  otherwise reads as untouched — call it out in review so the rebuilt map isn't mistaken for a
  regression.
- **Defensive no-data fill (H2).** Replace the `epiTrendsStyleFn` `{fillOpacity: 0}` fall-through
  (`engine.js:1341`) with a visible "no-data" fill, so that if the invariant is ever violated the
  map fails **loud** (a clearly flagged no-data zone) rather than **silent** (transparent/white).
  This makes the §9 guarantee structural rather than only empirical; it should never trigger in
  practice.
- **Unchanged:** the Snapshot Total / Confirmed / Suspected / deaths choropleths, the Snapshot
  info box, and every other tab remain sitrep-sourced. On the Snapshot and Context views a
  marker (harmonised confirmed) may therefore show a different confirmed number than the
  sitrep-sourced info box for the same zone — an accepted, intentional consequence. **Document
  this** in a support note (and consider a one-line tooltip caveat) so it reads as a conscious
  two-source design, not a bug, to dashboard users and INSP (M4).

## 9. Edge cases — the "no white" guarantee

| harmonised | sitrep | effective | was_active_before | Spatial-risk render |
|:---:|:---:|:---:|:---:|---|
| > 0 | any | > 0 | TRUE (model) | orange, coloured by `effective` |
| 0 | > 0 | > 0 | TRUE (reconcile) | orange, coloured by `effective` |
| 0 | 0 | 0 | FALSE | purple, coloured by `p_case_invasion` (present, unmasked) |

This table describes each zone's *path* (which ramp), which is per-zone-local. The orange *shade*
is **not** — it depends on the shared `epiCasesDomain`, so admitting new counts re-shades all
orange zones (§8, S2).

A zone can never reach the orange path without a count, nor the purple path without an invasion
probability. This relies on:

1. the §5 invariant (`harmonised > 0 ⟺ was_active_before`, at the cutoff) — so no active zone
   lacks a count;
2. reconcile masking `p_case_invasion` exactly when `effective > 0`;
3. **the purple branch never hitting a null `p_case_invasion`.** Verified empirically on the live
   build (`origin/main@5648ee5`): **all 466 non-active zones have a non-null `p_case_invasion`**
   (zero exceptions). GeoJSON zones the model does not score at all have no invasion row, so they
   hit the separate `!row` branch (`engine.js:1307`, dark grey `fillOpacity 0.04`), not the
   transparent path — they are not on the purple branch.

Because that third condition is *empirical* (a future run could in principle score a zone with a
null probability), the **defensive no-data fill** in §8 replaces the `fillOpacity: 0` fall-through
so any violation surfaces as a visible flagged zone, never silent white. The guarantee is then
structural, not merely observed.

> **Re-verify before pinning (FP-7).** The empirical counts here (519 / 54 / 7 / 0; "all 466
> non-active zones have non-null `p_case_invasion`"; the Rethy/Bafwasende specifics) were measured
> from the `origin/main@5648ee5` payload. `origin/main` moves and local branches lag, so re-run the
> measurement against the current built payload before pinning the §10 regression fixture to a SHA.

## 10. Testing

Note: the current tree has **no** tests for `reconcile_invasion_active_cases`,
`load_invasion_risk_estimates`, or `_compact_ranks`, so this is net-new scaffolding, not an
extension.

- **Model:** the artifact is emitted; assert `cumulative_confirmed_cases > 0 ⟺ was_active_before`
  **evaluated at the run's `training_window_end`** (H1), not over arbitrary horizons.
- **Build (pytest):**
  - loader parses the CSV and resolves it from the dated `key_outputs/` dir;
  - **`effective_confirmed_cases` written for *every* zone, default 0 (FP-6)** — a GeoJSON zone
    absent from the CSV gets `0`, never `undefined`; a sitrep `None → 0`; `max(None, …)` never
    called; **no crash**;
  - **name-join integrity (B2):** a `health_zone` needing `_NAME_TO_NOM` normalisation still joins;
  - **active-zone coverage assertion runs after `load_invasion_risk_estimates` (FP-2):** a
    `was_active_before` zone with no matched harmonised count fails the build *there*, not in the
    loader (where `was_active_before` isn't known yet);
  - reconcile behaviour is **unchanged (FP-4)** — a fresh-sitrep-only zone still promotes to active;
    a both-zero zone stays at-risk with `p_case_invasion` present (no test asserts reconcile reads
    `effective`, since it doesn't);
  - **download masking (S5):** a zone with `effective > 0` has `p_case_invasion` nulled across
    **all its horizon rows** in `download_csv`, matching the map.
- **Engine:**
  - a harmonised-only fixture zone is **included in `epiCasesDomain` `caseVals`** (S1) and renders
    orange with the harmonised count and a marker — not clamped to darkest/lightest;
  - the same zone's **importation-pressure arrow is non-zero** in epi-trends (FP-3);
  - a both-zero zone renders purple;
  - **null-`p_case_invasion` non-active zone** renders the defensive no-data fill, **not**
    transparent (H2);
  - marker tooltip shows harmonised confirmed **plus** the sitrep suspected/deaths rows (M3);
  - Snapshot layers, the ranked table, the epi hover float, and `infoHTML` are unaffected
    (S3/S4 — none carries a spatial-risk confirmed number).
- **End-to-end regression:** pin the build **SHA** (`origin/main@5648ee5`) — not the zone names,
  which drift per sitrep run — and assert Rethy and Bafwasende render as active-case zones with a
  count in that payload.

## 11. Follow-up (documented, not built)

Sitrep-triggered model refresh so the harmonised artifact is always current and the §7 `max()`
top-up can retire. Entry point: `run-spatiotemporal.yml` in `BDBV2026-Processed_Sensitive_Data`
(add a sitrep-update trigger + sitrep ingestion pathway + live-vs-backtest cutoff handling).
Its own spec.
