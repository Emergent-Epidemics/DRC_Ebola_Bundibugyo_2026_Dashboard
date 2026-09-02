# Trends map: confirmed-case recency categories

**Date:** 2026-09-02
**Status:** Approved design, pending implementation plan
**Scope:** `trends.html` (Epidemiological Trends tab) only

## Summary

Add a dedicated segmented toggle to the Trends-tab map that flips its animated
health-zone colouring between the current **continuous cumulative confirmed
cases** view and a new **4-category confirmed-case recency** view. Both views
animate through the *same* existing time slider (`trendsDateIdx`). The category
is a pure transform of data the build already loads
(`PAYLOAD.confirmed_timeseries`) — no new data repo, no new CSV, no new
cross-repo CI dependency.

## Motivation

The Trends map today colours zones by cumulative confirmed cases on a continuous
(reds, log) scale. Public-health readers also want a coarser, at-a-glance view
of **where the outbreak is currently active vs. cooling vs. cold**, and to watch
that pattern evolve over time. The four recency categories provide that, and
because they are derivable from the cumulative time series already in the
payload, they cost almost nothing in new data plumbing.

## Categories

For each zone and each frame date **T** (the sitrep dates already in
`confirmed_timeseries.dates`):

| Category | Condition (from frame date T) | Meaning |
|----------|-------------------------------|---------|
| **Cat 1 — active**  | last new case `d ≤ 14` days before T | case within last 14 days |
| **Cat 2 — recent**  | `15 ≤ d ≤ 42` days | last case 15–42 days ago |
| **Cat 3 — dormant** | `d > 42` days | no new case for more than 42 days |
| **Cat 4 — never**   | `cumulative[T] == 0` | no confirmed case ever (as of T) |

Where `d` = calendar days from the most recent date the zone's cumulative count
increased (its last new confirmed case), up to T. Cutoffs are **14** and **42**
(42 = the WHO 2×21-day end-of-outbreak marker); there is no gap between
categories. "Days ago" is measured **from the current animation frame date T**,
so categories evolve as the slider plays — not from today.

Because the sitrep dates are real ISO dates, the day arithmetic is exact even
though the frames are irregularly spaced.

## Where the category is computed

**Decision: the dashboard Python build**, not `Processed_Sensitive_Data` and not
the frontend.

Rationale: everything needed is already loaded by
`load_confirmed_cases_timeseries()`
(`Scripts/common/data_sources.py:2336`), which ships
`PAYLOAD.confirmed_timeseries = { dates, date_labels, by_nom: { nom → [cumulative
per dateIdx] }, max_confirmed, min_positive }`. Computing in
`Processed_Sensitive_Data` would re-derive data already present and add a
cross-repo CI dependency for a classification that is *coarser* (and so less
sensitive) than the cumulative counts already published on the map. Computing in
Python (rather than client-side JS) keeps the epidemiological definitions +
calendar-day math under the existing pytest harness and keeps the frontend thin,
matching the established "Python computes values, JS colours" pattern.

## Architecture

### Build (Python)

- **New pure function** in `Scripts/common/data_sources.py`, e.g.
  `compute_confirmed_recency_timeseries(confirmed_ts, near_days=14, mid_days=42)`.
  - Input: the already-built `confirmed_timeseries` dict (no CSV re-read).
  - Output: `{ dates, by_nom: { nom → [catInt per dateIdx] }, thresholds:
    {near: 14, mid: 42}, labels }` where `catInt ∈ {1,2,3,4}`.
  - "Last increase" detection: `cumulative[i] > cumulative[i-1]`; a nonzero
    value at the first date counts as a case event on `dates[0]`. Decreases
    (downward data corrections between sitreps) are ignored as case events.
- **Wire into** `build_shared_payload()` (`Scripts/common/payload.py`) directly
  after `load_confirmed_cases_timeseries()`, adding the result to `PAYLOAD` as
  **`confirmed_recency`**. Guard for the case where `confirmed_timeseries` is
  absent (function returns `None`, feature silently unavailable — same posture
  as the slider today).

### Frontend (`Scripts/assets/engine.js`)

- New module state `trendsColorMode` (`'cumulative'` | `'recency'`), default
  `'cumulative'` so current behaviour is unchanged on load.
- A **segmented control** ("Cumulative cases" | "Recency") mounted near the
  Trends slider / legend. Flipping it re-renders the current frame only; it does
  **not** restart or stop the animation.
- `recomputeTrendsMap()` (`engine.js:3518`) branches on `trendsColorMode`:
  - `'cumulative'` — unchanged (existing continuous path via `currentDomain` /
    `valueToColor`).
  - `'recency'` — set each zone's fill from a **discrete 4-colour lookup** keyed
    by `PAYLOAD.confirmed_recency.by_nom[nom][trendsDateIdx]`, bypassing the
    continuous domain. Zones with no entry fall back to the Cat 4 / neutral fill.
- Legend swaps with the mode: existing gradient bar (`initTrendsLegendBar`,
  `engine.js:3481`) ↔ a new **4-swatch discrete legend** with category labels.

### Colours

Ordered "hot → cold → neutral" ramp (finalise exact hexes against the dataviz
skill's palette guidance during implementation, but these are the agreed
values):

| Category | Colour | Hex |
|----------|--------|-----|
| Cat 1 — active  | deep red   | `#b2182b` |
| Cat 2 — recent  | orange     | `#ef8a62` |
| Cat 3 — dormant | pale sand  | `#fddbc7` |
| Cat 4 — never   | neutral grey | `#e0e0e0` |

### Tooltip

In recency mode, the zone tooltip shows the category label plus "last confirmed
case: *d* days ago" (data already available from the same series). In cumulative
mode the tooltip is unchanged. (First-version behaviour; expected to iterate.)

### i18n

New keys in the existing `trends_*` namespace of `locales/en.yaml` and
`locales/fr.yaml`: the two toggle labels, the four category names, the legend
heading, and the tooltip phrasing. The legend description should carry the
caveat below.

## Testing

Pytest unit tests for `compute_confirmed_recency_timeseries`, covering:

- never-affected zone (all zeros → Cat 4 at every frame);
- exact boundary days: 14 (Cat 1), 15 (Cat 2), 42 (Cat 2), 43 (Cat 3);
- carry-forward gaps (no sitrep update on some dates between events);
- first-date baseline (nonzero at `dates[0]` counts as an event on `dates[0]`);
- a downward correction (`cumulative[i] < cumulative[i-1]`) is not treated as a
  new case event;
- a zone that transitions across all four categories as frames advance.

Run from `Scripts/` under `python3.9` (`cd Scripts && python3.9 -m pytest
../tests -v`).

## Known caveat (documented, not fixed)

Categories key off sitrep **report** dates, not symptom onset, so a reporting
gap can delay a zone's transition between categories. This matches how the
cumulative animation already behaves, and should be stated in the recency
legend's description text.

## Out of scope

- The Current Snapshot (`index.html`) and Spatial Risk (`spatial-risk.html`)
  maps — recency is Trends-tab only.
- Any change to `Processed_Sensitive_Data` or `BDBV2026-Data`.
- Changing the cumulative view's palette, domain, or slider behaviour.

## Key references

- Time-series payload builder: `load_confirmed_cases_timeseries()` —
  `Scripts/common/data_sources.py:2336`; source CSV
  `../BDBV2026-Data/build/long/insp_sitrep__cumulative_confirmed_cases.csv`.
- Payload assembly: `build_shared_payload()` — `Scripts/common/payload.py`
  (attaches `confirmed_timeseries` ~line 130 / 220).
- Trends animation: `playTrendsSliderAnimation` / `applyTrendsDateIdx` /
  `getTrendsConfirmedAt` (`engine.js:3473`) / `recomputeTrendsMap`
  (`engine.js:3518`); autoplay in `enterTrendsView` (`engine.js:3576`); legend
  `initTrendsLegendBar` (`engine.js:3481`).
