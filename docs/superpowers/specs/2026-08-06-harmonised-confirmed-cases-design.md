# Harmonised confirmed cases — design

**Date:** 2026-08-06
**Status:** Draft — revised through 3 review passes; ready for implementation-plan review.
**Repos touched:** `BDBV2026-Analysis` (model), `BDBV2026-Epidemic_Dashboard` (dashboard), and one config bump in `BDBV2026-Processed_Sensitive_Data` (`ANALYSIS_REF`).
**Revised** 2026-08-06 after three critical-review passes (`…-review.md`). Pass 1 (provenance/delivery): corrected the delivery path (B1), added name-normalisation + coverage assertion (B2), pinned the invariant to the training cutoff (H1), grounded the no-white guarantee empirically + added a defensive fill (H2), kept sitrep suspected/deaths on the shared marker (M3). Pass 2 (engine render pipeline): added the colour **domain** (`recomputeEpiTrends`) to the engine sites (S1) and its global re-shade consequence (S2); corrected the readout claims — the marker is the *only* spatial-risk confirmed readout, so no ranked-table/hover change (S3/S4); and masked the downloadable CSV to match the map (S5). Pass 3 (file targeting / call order): re-pointed every build-side edit from the **dead** `build_dashboard_public.py` monolith to the live `common/data_sources.py` (F1), and pinned the `effective` write to happen **before** `payload.py:97` so `build_active_case_markers` sees it (F2).

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

The model already computes `zone_week` = confirmed cases from line-list ∪ appended sitrep, and
`affected_zones(zone_week, cutoff)` (`spatiotemporal_conditional/15_workhorse.R`) already means
`confirmed > 0` up to the training cutoff.

Add an export from the same run (`run_all.R`) written into the run's
`spatiotemporal/key_outputs/` directory, **beside `bayes_risk_scores_all_zones.csv`** (the file
the dashboard already consumes — see §6):

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
model run writes key_outputs/harmonised_confirmed_cases.csv
  → run-spatiotemporal.yml: analysis/ci/collect_outputs.sh does `cp -R "$KEY/."`
    (copies the WHOLE key_outputs/ bundle wholesale — no allowlist edit needed for key_outputs;
     the strict allowlist only governs the separate reports/ copy)
  → published to BDBV2026-Processed_Sensitive_Data/main
  → trigger-dashboard-rebuild.yml
  → dashboard reads it from the same dated key_outputs/ dir as bayes_risk_scores_all_zones.csv
```

**Required infra step:** bump the pinned `ANALYSIS_REF` in `run-spatiotemporal.yml` to the
`BDBV2026-Analysis` commit that emits the new artifact (inherent to shipping any model change).
No `collect_outputs.sh` change is needed *provided the file is written into `key_outputs/`*; if it
were instead placed under `reports/`, it would need adding to that script's strict allowlist.

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
  - **assert coverage:** warn on any `health_zone` not in the GeoJSON `nom` set, and — given the
    §5 invariant — treat any `was_active_before` zone left without a matched harmonised count as a
    **build error**, not a silent drop (a silent drop reproduces the white-zone bug).
- **Effective count:** in `payload.py`, **before line 97** (F2), per zone compute
  **`effective = max(harmonised, sitrep_confirmed)`** with explicit defaults —
  `harmonised.get(nom, 0)` and sitrep `None → 0` (never call `max(None, …)`) — and write it into
  each `zone_data` rec as **`effective_confirmed_cases`**. `sitrep_confirmed` is the current
  `zone_data.confirmed_cases` (built in `load_metadata`, `data_sources.py:2875-2885` — live-fetched
  INSP sitrep, WHO epi fallback — often *fresher* than the model's snapshot).
  - **Honest framing (M1):** `max()` is a pragmatic **freshness top-up**, a *lower bound* on the
    true current union — not a merge. If the line list contributed cases the fresher sitrep never
    had *and* the sitrep has since grown on other cases, `max` undercounts the true union. This
    never breaks "no white" (`effective ≥ harmonised`), but the displayed count can be lower than
    reality. The §11 follow-up (model always fresh) is what yields the exact union.
- **Reconcile:** generalise `reconcile_invasion_active_cases()` (`data_sources.py`, called from
  `payload.py`) to gate on `effective` instead of sitrep-only. Net result:
  `was_active_before ⟺ effective > 0`; invasion outputs masked for exactly those zones;
  `rr_nat` / `rr_nat_rank` / `priority_rank` renormalised over the truly-at-risk set. Its
  one-directional (promote-only) behaviour is unchanged; only its input count widens. **Note:**
  renormalisation divides by the mean of the *old* `rr_nat` over the cleaned set
  (`data_sources.py:2071-2075`), so widening the promoted set shifts *every* at-risk zone's
  `rr_nat` (~6% in the prior analysis) and rank — not only the promoted zones. Expected, not a bug.
- **Payload:** `effective_confirmed_cases` (written above) rides through in `zone_data`.
- **Downloadable CSV (S5):** `load_invasion_risk_estimates` captures `download_csv` as an
  unfiltered pre-reconcile snapshot (`data_sources.py:1744`), so it already shows `p_case_invasion`
  for zones the map masks — and this change *widens* that masked set. Per decision, **mask the
  download to match the map**: null `p_case_invasion` (and the other `_INVASION_AFFECTED_MASK_FIELDS`)
  in `download_csv` for zones with `effective > 0`, so the downloaded CSV and the rendered map agree.
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

The spatial-risk confirmed-case surface is **three** functions that must all read the **same**
`effective` field, so the colour domain, the fill, and the marker can never disagree. (The second
review confirmed the earlier draft named the fill but not the domain, and mislabelled two readouts
that don't exist — corrected below.)

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
  and number agree, with nothing else to change.

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

## 10. Testing

Note: the current tree has **no** tests for `reconcile_invasion_active_cases`,
`load_invasion_risk_estimates`, or `_compact_ranks`, so this is net-new scaffolding, not an
extension.

- **Model:** the artifact is emitted; assert `cumulative_confirmed_cases > 0 ⟺ was_active_before`
  **evaluated at the run's `training_window_end`** (H1), not over arbitrary horizons.
- **Build (pytest):**
  - loader parses the CSV and resolves it from the dated `key_outputs/` dir;
  - `effective = max(harmonised, sitrep)` per zone, with defaults for missing zones (M2): a zone
    absent from the CSV → `harmonised = 0`; a sitrep `None → 0`; **no crash**;
  - **name-join integrity (B2):** a `health_zone` needing `_NAME_TO_NOM` normalisation still
    joins; an unmatched *active* zone raises a build error;
  - reconcile driven by `effective` — a harmonised-only zone (Rethy-like) ends active with masked
    invasion; a fresh-sitrep-only zone ends active; a both-zero zone stays at-risk with
    `p_case_invasion` present;
  - **download masking (S5):** a zone with `effective > 0` has `p_case_invasion` nulled in
    `download_csv`, matching the map.
- **Engine:**
  - a harmonised-only fixture zone is **included in `epiCasesDomain` `caseVals`** (S1) and renders
    orange with the harmonised count and a marker — not clamped to darkest/lightest;
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
