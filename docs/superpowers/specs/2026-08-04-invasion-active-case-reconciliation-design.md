# Spatial Risk — reconcile invasion risk against latest active cases

**Date:** 2026-08-04
**Status:** approved (design)
**Scope:** dashboard build only (`Scripts/common/`). No model / Analysis-repo change.

## Problem

The invasion-risk model (`BDBV2026-Analysis`) excludes health zones that already
have confirmed cases ("affected") and estimates an invasion probability only for
the remaining at-risk zones. `was_active_before = TRUE` zones are masked to `NA`.

The model runs on the **line-list cadence** (`ANALYSIS_DATE` = line-list
`processed_at`) and consumes a sitrep snapshot bundled at run time. Because the
sitrep is processed/ingested with a 1–3 day lag, a zone whose first confirmed
case is only days old can be absent from the sitrep the model saw. The model
then correctly (given its inputs) leaves that zone at-risk with an invasion
probability.

The **dashboard builds later** and re-builds on every data update, so at build
time its geojson already carries `confirmed_cases > 0` for such a zone. The
shipped payload is then self-contradictory: the zone appears in the ranked
at-risk table with an invasion probability while the same payload's `zone_data`
says it already has a case.

Confirmed instance (cutoff 2026-08-03 run): **Lubero** (rr_nat rank 4, p=0.227)
and **Wanierukula** (rank 24) — each with 1 confirmed case that reached the
committed sitrep only on 08-03 18:29 / 08-04 10:35, after the model's snapshot.

### Why this contaminates other zones (not just the two)

Relative risk is normalised across the at-risk set
(`compute_risk_scores`, `15_workhorse.R:674-676`):
`rr_nat = mu / mean(mu over at-risk)`, `rr_nat_rank = min_rank(desc(mu))`.
A wrongly-included high-risk zone therefore inflates the mean (every other
zone's `rr_nat` shifts ~+6% when the two are removed) and occupies a rank slot
(464 zones ranked one position too low behind Lubero). Per-zone
`p_case_invasion` is **not** affected (it is `beta·Lambda_i`, independent per
zone; `beta` is fit on historical weeks).

## Approach (option 1b)

Reconcile + recompute at **dashboard build time**, the freshest-data layer.
This is chosen over a model-side fix because the model cannot exclude a case it
has not ingested and re-runs less often than the sitrep updates; the dashboard
has the freshest per-zone case counts and no `ANALYSIS_DATE` clamp.

### Reconciliation (one-directional)

For each zone the model left at-risk (`was_active_before == False`) whose
freshest `zone_data[nom].confirmed_cases > 0`:

- set `was_active_before = True`
- set to `None` the invasion outputs, matching the model's own affected mask:
  `p_case_invasion`, `p_case_lo`, `p_case_hi`, `rr_nat`, `rr_nat_rank`,
  `priority`, `priority_rank`, and the provincial `rr_{ituri,nordkivu,hautuele}`
  (+ their `_rank`).

Only at-risk → affected, never the reverse (matches the model's "affected once a
case appears" definition; `confirmed_cases` is the same signal the map already
uses to paint active zones red).

### Recompute over the cleaned at-risk set

- `rr_nat` → renormalise: `rr_nat / mean(rr_nat over cleaned set)`. Exact,
  since `rr_nat ∝ mu`.
- `rr_nat_rank`, `priority_rank` → **compact the model's original ranks**:
  `new_rank = 1 + count(original rank strictly smaller)` over the cleaned set.
  This closes the gaps left by the removed zones while preserving the model's
  exact ordering and ties. It deliberately re-ranks from the *original rank*, not
  from the stored `rr_nat` / `priority` values: the payload rounds `priority` to
  4dp (162 distinct of 468), and re-ranking off that rounded value diverges from
  the model's unrounded ranking for ~300 zones.
- `priority` **value** → left as the model's (exact recompute needs the model's
  `rr01×vulnerability` internals; removing two non-extreme zones barely moves a
  min-max index).

### What needs no work

The table's "Relative risk (norm.)" column is `norm_rr`, computed in `engine.js`
as *ratio to the max visible row* — it self-corrects once the two zones leave the
ranked list, and sort order (by `rr_nat`) is invariant to the renormalisation.
**No JS change.** Reconciled zones then behave exactly like the other ~51
already-affected zones: they drop out of the ranking and are painted
red-by-case-count on the map.

## Location

- New `reconcile_invasion_active_cases(invasion_risk, zone_data)` in
  `Scripts/common/data_sources.py` (+ export in `__all__`), with a small
  `_rerank` helper.
- Called from `Scripts/common/payload.py` immediately after
  `load_invasion_risk_estimates()` (zone_data is already built above it).
- Logs the reconciled zones at build time, e.g.
  `reconciled 2 zone(s) at-risk->affected from latest confirmed cases: Lubero, Wanierukula`.
- Always on; no config flag.

## Explicitly out of scope

- The **CSV download** (`invasion_risk.download_csv`) stays the raw model
  artifact; only the on-screen table/map reflect reconciliation.
- No change to `BDBV2026-Analysis`. The model-side lag is a known, separate
  concern (sitrep ingestion cadence / re-run frequency).

## Verification

- Unit-level: run the function over the current live payload and assert Lubero &
  Wanierukula become `was_active_before = True` with NA outputs, and that
  `rr_nat_rank` is contiguous `1..N` with no gap at 4.
- End-to-end: rebuild the dashboard and confirm the two zones leave the Spatial
  Risk ranked table and render red on the map.
