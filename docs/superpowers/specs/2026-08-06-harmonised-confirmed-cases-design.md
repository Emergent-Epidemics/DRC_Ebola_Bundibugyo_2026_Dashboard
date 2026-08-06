# Harmonised confirmed cases — design

**Date:** 2026-08-06
**Status:** Approved (design); implementation plan to follow.
**Repos touched:** `BDBV2026-Analysis` (model), `BDBV2026-Epidemic_Dashboard` (dashboard). Delivery rides existing `BDBV2026-Processed_Sensitive_Data` automation unchanged.

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

Add an export from the same run (`run_all.R`, alongside `invasion_risk_model_estimates.csv`):

```
harmonised_confirmed_cases.csv
  health_zone, cumulative_confirmed_cases      # harmonised; one row per zone; horizon-agnostic
```

- The value is the per-zone cumulative confirmed count from `zone_week` up to the cutoff.
- **Invariant (by construction):** `cumulative_confirmed_cases > 0 ⟺ was_active_before = TRUE`,
  because both derive from the same `zone_week` at the same cutoff. This invariant is what makes
  the "no white" guarantee (§7) hold.

## 6. Delivery path (no new infra)

```
model run → published to BDBV2026-Processed_Sensitive_Data/main   (run-spatiotemporal.yml)
          → trigger-dashboard-rebuild.yml
          → dashboard build reads harmonised_confirmed_cases.csv from DATA_ROOT
            (same route as invasion_risk_model_estimates.csv)
```

## 7. Dashboard build (Python)

- **Loader:** new function in `Scripts/common/data_sources.py` beside
  `load_invasion_risk_estimates()` that reads `harmonised_confirmed_cases.csv` →
  `{nom: harmonised_confirmed}`.
- **Effective count:** in `payload.py`, per zone compute
  **`effective = max(harmonised, sitrep_confirmed)`**, where `sitrep_confirmed` is the current
  `zone_data.confirmed_cases` (the live-fetched INSP sitrep value, WHO epi fallback — often
  *fresher* than the model's snapshot). `max()` preserves both the union semantics and the
  dashboard's freshness.
- **Reconcile:** generalise `reconcile_invasion_active_cases()` (`data_sources.py`, called from
  `payload.py`) to gate on `effective` instead of sitrep-only. Net result:
  `was_active_before ⟺ effective > 0`; invasion outputs masked for exactly those zones;
  `rr_nat` / `rr_nat_rank` / `priority_rank` renormalised over the truly-at-risk set. Its
  one-directional (promote-only) behaviour is unchanged; only its input count widens.
- **Payload:** expose `effective_confirmed_cases` per zone.
- **Marker builder:** `build_active_case_markers` (`Scripts/build_dashboard_public.py`) gates on
  `effective > 0` (instead of `confirmed_cases > 0`) and emits `effective` as the marker's
  confirmed count, so `PAYLOAD.active_case_markers` covers harmonised-only zones.

### Freshness safeguard rationale

The `max()` is **not** the dashboard re-deriving the union. It is an extension of behaviour the
dashboard already ships: `reconcile_invasion_active_cases()` already tops up the active *flag*
from the dashboard's live sitrep. This widens that same top-up to the *count*, covering the
window between the model's sitrep snapshot and the dashboard's live fetch. It is the interim
until the §9 follow-up lands, after which it can retire.

## 8. Dashboard engine (`Scripts/assets/engine.js`)

- **Active-case marker tooltip (all views: map / context / epi-trends).** The shared `caseLayer`
  is built once from `PAYLOAD.active_case_markers` (already gated/populated on `effective` by the
  build, §7). `caseMarkerTooltip` shows **only** the harmonised confirmed number; the suspected
  and confirmed-deaths rows are removed.
- **Spatial-risk polygons (`epiTrendsStyleFn`).** The confirmed-case (orange) path colours by
  `effective` instead of `ZONE_DATA[nom].confirmed_cases`. The branch remains keyed on
  `was_active_before`, which now `⟺ effective > 0`.
- **Spatial-risk in-tab readouts.** The zone hover tooltip and the ranked epi-trends table show
  `effective`, so the number agrees with the polygon colour within the tab.
- **Unchanged:** the Snapshot Total / Confirmed / Suspected / deaths choropleths, the Snapshot
  info box, and every other tab remain sitrep-sourced. On the Snapshot and Context views a
  marker (harmonised) may therefore show a different confirmed number than the sitrep-sourced
  info box for the same zone — an accepted, intentional consequence.

## 9. Edge cases — the "no white" guarantee

| harmonised | sitrep | effective | was_active_before | Spatial-risk render |
|:---:|:---:|:---:|:---:|---|
| > 0 | any | > 0 | TRUE (model) | orange, coloured by `effective` |
| 0 | > 0 | > 0 | TRUE (reconcile) | orange, coloured by `effective` |
| 0 | 0 | 0 | FALSE | purple, coloured by `p_case_invasion` (present, unmasked) |

A zone can never reach the orange path without a count, nor the purple path without an invasion
probability. The transparent/`fillOpacity: 0` state is therefore unreachable. This relies on the
§5 invariant (`harmonised > 0 ⟺ was_active_before`) plus reconcile masking `p_case_invasion`
exactly when `effective > 0`.

## 10. Testing

- **Model:** the artifact is emitted; assert `cumulative_confirmed_cases > 0 ⟺ was_active_before`
  over the run's zones.
- **Build (pytest):** loader parses the CSV; `effective = max(harmonised, sitrep)` per zone;
  reconcile driven by `effective` — a harmonised-only zone (Rethy-like) ends active with masked
  invasion; a fresh-sitrep-only zone ends active; a both-zero zone stays at-risk with
  `p_case_invasion` present.
- **Engine:** a harmonised-only fixture zone renders orange with the harmonised count and a
  marker; a both-zero zone renders purple; Snapshot layers are unaffected; marker tooltip shows
  only the confirmed row.

## 11. Follow-up (documented, not built)

Sitrep-triggered model refresh so the harmonised artifact is always current and the §7 `max()`
top-up can retire. Entry point: `run-spatiotemporal.yml` in `BDBV2026-Processed_Sensitive_Data`
(add a sitrep-update trigger + sitrep ingestion pathway + live-vs-backtest cutoff handling).
Its own spec.
