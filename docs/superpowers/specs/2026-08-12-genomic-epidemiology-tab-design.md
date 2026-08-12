# Genomic Epidemiology tab — design

**Date:** 2026-08-12 (revised after two code-grounded review passes)
**Status:** Design revised; **a Phase 0 spike must pass before implementation planning** (see Phase 0 and Open items).
**Review:** `docs/superpowers/specs/2026-08-12-genomic-epidemiology-tab-design-review.md` (rounds 1 & 2)

## Context

The dashboard's **Genomic Epidemiology** tab is currently a "coming soon" stub
(`Scripts/pages/genomic_epidemiology.py`'s `build_page()` delegates to the shared
`render_page()`; genomic is in `STUB_VIEWS` in `Scripts/common/chrome.py`). A
separate standalone app —
`/Users/user/Documents/work/DRC-Ebola-genomic-epi-public`, repo
`github.com/joetsui1994/BDBV2026_genomic_epi`, with a **live GitHub Pages site** —
implements a rich interactive genomic view: a phylogeny (PearTree), an
effective-population-size panel (SkyGrid + exponential-growth estimates), a
sample-distribution time series, and a linked map. This project moves that content
into the dashboard's genomic tab, natively. **The standalone public site stays
live** (see Decision 3).

The two codebases are architecturally opposite:

- **Dashboard (target):** a Python static-site generator. One shared hand-written
  `Scripts/assets/engine.js` (~3,900 lines) + `dashboard.css` (~1,150 lines); a
  single inline JSON payload per page parsed synchronously; **no JS build step**;
  dark chrome; Leaflet; en/fr i18n via `data-i18n` + `locales/{en,fr}.yaml`.
- **Source app:** a Vite/ESM app of small modules (`tree-panel.js`, `ne-panel.js`,
  `timeseries-panel.js`, `coordinator.js`, `map-panel.js`, + helpers) with vitest
  tests (pure helpers + build libs only — the four large UI modules and the
  coordinator have **no tests**); fetches JSON/CSV at runtime; a warm **light**
  theme; an external `peartree.bundle.min.js` (~1.5 MB) phylogeny renderer.

## Goals

- **Fully native** genomic tab: dark chrome, shared header/nav/footer, en/fr i18n,
  data consistent with the rest of the dashboard.
- **Style consistency:** the tab reads as the same product as every other tab. A
  health zone is the same colour across the **map and the SVG panels**. For the
  **tree**, the same zone scale *if* PearTree's embed API allows recolouring;
  otherwise the pre-committed fallback (Phase 0 / §6): the tree keeps its own
  consistent categorical palette plus a visible zone-colour legend. The goal
  carries its own fallback — it is not left contingent on an open question.
- **Data consistency:** case counts, zone geometry/names, and sampling counts
  match the rest of the dashboard, with the tree's **data build date** surfaced so
  stale-vs-fresh is legible.
- **Efficiency:** reuse the dashboard's existing map surface, rail/splitter, and
  panel-collapse mechanics; port only genuinely genomic logic; do not rewrite
  BEAST/tree parsers.
- Establish a **per-tab separation seam** (genomic is the pilot) that is also the
  stepping stone to a possible future SPA, without committing to SPA now.

## Non-goals

- No client-side router / SPA shell now; the dashboard stays MPA; the
  inline-payload synchronous-parse bootstrap is retained.
- No refactoring of the existing tabs into the seam (but see R7: the shared
  zone-click handler gains an `activeView` branch — a small, contained change, not
  a refactor).
- No Python reimplementation of the phylodynamic/tree transforms.
- No shared, cross-tab selection bus in `engine.js` (Decision 6 / §4).

## Key decisions

1. **Integration goal:** fully native.
2. **Map (zone-level linking):** the data is zone-level — `health_area` is `null`
   for all 134 tips and every zone's tips share one centroid coordinate. So reuse
   the dashboard's **existing per-zone genome layer** (`genomeLayer`,
   `engine.js:3301`) and make its markers clickable to select that zone's tip-set
   and highlight the tips; reuse the existing zone-polygon selection for the zone
   path. Do **not** build per-sample or area-level markers. Any area-grouping code
   carried from `map-panel.js` is **dormant, clearly-labelled future-proofing**
   (for if tips ever carry `health_area`), not a live requirement.
3. **Genomic data pipeline:** the standalone public site **stays live**, so create
   a **fresh** `INRB-UMIE/BDBV2026-Genomic_Epi` producer repo by **extracting**
   (cherry-pick, not GitHub-transfer) `scripts/` + `data-raw/` + the committed
   products + `aliases.csv` + the vitest suite from
   `joetsui1994/BDBV2026_genomic_epi`, which is left intact. The dashboard CI
   ingests the producer's products (same pattern as `dashboard_plots`). Cost: two
   repos with the producer logic to keep in sync — accepted.
4. **Layout:** right rail (Option A) — phylogeny (top) / Ne / sample-distribution
   stacked, drag-resizable; genomic rail defaults wider (the tree needs width).
5. **JS architecture:** a separate hand-written static `Scripts/assets/genomic.js`
   in `engine.js`'s idiom, loaded only on the genomic page. No JS bundler.
6. **Coordination:** the cross-panel coordinator lives **inside `genomic.js`**, not
   a shared bus. `engine.js` exposes only generic map hooks. SPA-readiness lives in
   the tab module's `mount/unmount`.
7. **Separation seam:** an additive per-tab contribution interface, **genomic
   only**; existing tabs render unchanged.

## Phase 0 — de-risking spike (gates everything; may amend this spec)

Throwaway code, no new repo, no seam. Each item has an explicit pass bar.

1. **PearTree dark + recolour + delivery (M4/M5) — the critical unknown.**
   Embed the real NEXUS tree in a dark rail and determine:
   - Can its Bootstrap-light theme be forced dark via the embed API / `--pt-*`
     overrides (no bundle fork)?
   - Does the embed API accept a **per-`health_zone` colour map** so tips use the
     dashboard's zone scale?
   - Does `PearTree.embed` accept **inline tree text**, or only a `treeUrl`
     (decides inline-payload-value vs. page-scoped fetched asset; the tree is
     **NEXUS text, not JSON**)?
   - Its head `@import`s Google Fonts — can that request be eliminated (vendor/
     disable)?
   **Pass bar / acceptance artifact:** one dark screenshot of the tree rendered in
   the dashboard's zone colours with **no external font request** in the network
   panel. **Pre-committed fallback** (owner: maintainer): if no per-zone palette
   hook exists, we do **not** fork — the tree keeps its own consistent categorical
   palette + a visible zone-colour legend (Goal #2 fallback), and only dark-theming
   + killing the font request remain required.
2. **Zone-level map linking (M1/R1).** On the real dashboard map, make the existing
   genome markers clickable → select that zone's tip-set → highlight tips, and
   round-trip a zone-polygon click. **Pass bar:** click a genome marker, see the
   zone's tips highlight in the (spike) tree, and click the polygon for the same
   zone with no double-selection glitch. Confirm the `activeView` branch of the
   shared zone-click handler (R7) is the whole shared-code change needed.
3. **Coordinator contract (M2).** Stand up the tip-set-or-zone toggle,
   `tree.onViewChange → timeseries.setTransform` coupling, and date-marker fan-out
   against the real tree + map. **Pass bar:** toggle-deselect works and the
   distribution x-axis tracks tree pan/zoom.
4. **Onset/beyond-tree data availability (S2/R3).** Confirm
   `BDBV2026-Processed_Sensitive_Data/outputs/<date>/dhis2_linelist_with_imputed_onset.csv`
   aggregates to the per-date (and per-zone) observed/imputed counts the
   distribution panel needs, and **define "beyond-tree"** (samples dated after the
   tree's latest tip) as a concrete rule. **Pass bar:** a written mapping from that
   CSV → the panel's series, and a beyond-tree definition. Prevents a Phase-2
   surprise after repo/seam/hooks exist.

**Exit:** all four pass bars met (using fallbacks where pre-committed) → proceed;
otherwise fold the documented design change back here before Phase 1.

## Architecture

### 1. Repos & data flow

```
INRB-UMIE/BDBV2026-Genomic_Epi (NEW producer; extracted/cherry-picked from joetsui1994/BDBV2026_genomic_epi, which stays live)
    BEAST/HIPSTR inputs + .mjs build scripts (+ aliases.csv, + vitest suite)
    → commits products: ituri-tree.ptree (NEXUS), tips.json, meta.json, skygrid.json, exponential.json
    → alias-join + FAIL-LOUD live HERE (tree-lib.mjs:68 throws; build-status.mjs:49 exit 1)
    → CI rebuilds on a new phylodynamic analysis (rare)

BDBV2026-Processed_Sensitive_Data → case/status aggregates (canonical, 6-hourly)
                                     + outputs/<date>/dhis2_linelist_with_imputed_onset.csv (onset source, S2)
BDBV2026-Data                      → geometry, zone metadata, genomic_sequence_count (canonical)

        │  dashboard CI pulls pre-validated products (sibling-clone + env override)
        ▼
Dashboard build (Python) — ingests finished JSON/NEXUS; no Node, no join, no fail-loud here
    common/payload.py → shared payload + page-scoped "genomic" slice
                        + NEW aggregated onset series (from the imputed-onset linelist, S2)
    per-page seam     → genomic contributes body HTML + JS + payload keys + assets
    chrome.py         → shared chrome; genomic removed from STUB_VIEWS
        │  emits one static page per tab (as today)
        ▼
genomic-epidemiology.html  (real page weight ~1.65 MB: ~150 KB data + ~1.5 MB PearTree)
    engine.js (shared core + shared map + GENERIC map hooks: layer-register + zone-select subscribe)
    genomic.js (ported panels + genomic-local coordinator + ALL tip logic; mount/unmount; page-scoped)
    peartree.bundle.js (page-only; pin a versioned, licence-clear build before vendoring)
    page-scoped "genomic" payload slice (+ tree inline value OR fetched asset — Phase 0 decides)
```

**Why a separate producer repo over a `BDBV2026-Data` subdirectory:** it mirrors
the existing `dashboard_plots` ingestion; isolates the Node/BEAST toolchain and its
rare, analyst-driven cadence from `BDBV2026-Data`; and the producer logic already
exists to cherry-pick. Cost: one more CI-secret-bearing repo, and (given we keep
the standalone site) the producer scripts now live in two places — accepted, with a
note to keep them in sync (or later point the standalone app at the producer).

### 2. Data-consistency model

- **Canonical / overlapping** — case counts, zone geometry/names, per-zone sampling
  counts — come **only** from `payload.py`. The source app's own copies
  (`status_confirmed.csv`, its `health-zones.geojson`) are dropped;
  `timeseries.json` is already a dead/orphan file upstream.
- **Genuinely genomic** — tree (NEXUS), tips, Ne/SkyGrid, exponential — come from
  `BDBV2026-Genomic_Epi`.
- **Onset series for the distribution panel** — aggregated in `payload.py` from the
  canonical `dhis2_linelist_with_imputed_onset.csv` (already ingested per-snapshot)
  into per-date/per-zone observed/imputed counts (new payload key). "Beyond-tree"
  is defined against the tree's sampling set. This is **medium new work**, budgeted
  in Phase 2 and validated in Phase 0 (item 4) — not mere wiring.
- **Join + fail-loud stay in the producer** (`tree-lib.mjs:68`,
  `build-status.mjs:49`), so a genomic mismatch fails the *producer's* CI, never
  the dashboard's 6-hourly rebuild. The dashboard ingests only pre-validated
  products.

**Per-zone count authority.** Canonical `genomic_sequence_count`
(`data_sources.py:2989`; `engine.js:1673`, 6-hourly) is authoritative for counts
*shown* in the tab. Tree tips reflect the rarer analysis snapshot and can lag; the
tab **surfaces `meta.json`'s `updated` as the "data build date"** (a build stamp —
`2026-07-28` in current data — distinct from the tree's `mostRecentDate`
`2026-06-23`; not the BEAST-run date, so label it "data build date," not "analysis
date"). Anchor already present: payload carries `genome_sequence_markers`
(`payload.py:195`) and `engine.js` renders a genome-count layer.

**Delivery.** Small JSON products (~150 KB total) ride in as a **page-scoped
payload slice** (`_PAGE_SCOPED_PAYLOAD_KEYS`; key `genomic`). The **tree** (NEXUS)
becomes an inline payload value or a page-scoped fetched asset — Phase 0 item 1
decides. `peartree.bundle.js` is a genomic-page-only script.

### 3. Per-tab contribution seam (Python)

An **additive** seam in `chrome.py`: a page module may declare `body_html`
(injected into a per-view content slot instead of the shared `BODY_TEMPLATE`),
`scripts` (page-only), `payload_keys` (`genomic`), `styles` (page-only CSS).
`render_page()` composes these; existing tabs declare none and render exactly as
today. `genomic_epidemiology.py` supplies the four and leaves `STUB_VIEWS`.

### 4. Genomic tab module: lifecycle + genomic-local coordinator (JS)

`Scripts/assets/genomic.js` exports `createGenomicTab(context) → { mount, unmount }`.
`context` = `map` (shared Leaflet), `mapHooks` (generic; see below), `i18n`, `data`
(the `genomic` slice). MPA: `engine.js` calls `mount()` once when
`data-initial-view === "genomic-epidemiology"`. SPA (future): a router calls
`mount`/`unmount`. `unmount()` tears down listeners, the genomic marker layer, and
subscriptions.

**Genomic-local coordinator** — ports the full `coordinator.js` contract into
`genomic.js` (verified against code): selection is **tip-set or zone**, one
replacing the other; **click-again-to-deselect** (`activeKey`) with re-entrancy
flags (`programmatic`, `zoneSelecting`); a **non-selection** channel
`tree.onViewChange → timeseries.setTransform`; **date-marker fan-out** to timeseries
+ Ne.

**Generic `engine.js` map hooks only (R6).** Shared code exposes: (a) subscribe/
emit for the map's existing **zone** selection, and (b) generic **layer
registration** (add/remove a Leaflet layer + a click callback). **All tip logic —
which zone maps to which tips, tip highlighting, marker styling — lives in
`genomic.js`.** No tip concepts leak into shared code.

**Ownership rule + its mechanism (R7).** On the genomic page only the genomic
coordinator drives selection styling. The shared zone-click handler currently calls
`setMapSelection(feature.properties.nom)` (`engine.js:1803`); making the legacy
paths inert here requires an **`activeView` branch** in that handler (genomic view
routes the click to the genomic hook instead of `setMapSelection`). This is the one
named shared-code change beyond the generic hooks; verified in Phase 0 item 2.

### 5. Ported vs reused

- **Reused:** the shared Leaflet map surface and its **existing per-zone genome
  layer**; rail + drag-splitter; `wirePanelToggles()`; i18n; zone colour scale;
  chrome; per-browser `localStorage` rail sizing.
- **Ported (into `engine.js`'s idiom, dark theme):** clickable-marker → tip-set
  selection + tip highlighting (small; reuses the genome layer, **not** a
  per-sample rebuild); the Ne/SkyGrid + exponential chart; the sample-distribution
  chart (`timeseries-panel.js`, incl. imputed/observed split, beyond-tree, and a
  **CSV export/download modal** — an action, not a view toggle); the coordinator;
  helpers `log-scale`, `time-scale`, `tree-band` (`node-info` is **DOM-touching,
  not pure**). `map-panel.js`'s area-else-zone grouping is carried only as dormant,
  labelled future-proofing (R1).
- **Not ported:** PearTree itself (black-box bundle, embedded); the source
  `splitter.js`/`panel-collapse.js`; the source data copies + status sync.

### 6. Layout, styling, i18n

**Layout.** Shared map fills the viewport; drag-resizable right rail holds
phylogeny (top) / Ne / sample-distribution; genomic rail defaults wider; panels
keep their toggles (tree: Legend / Node Bars / Tip Labels; Ne: Exp / SkyGrid /
full-extent; distribution: Imputed / beyond-tree / CSV-export) and collapse via
`wirePanelToggles()`. Narrow screens (≤700px): rail stacks under the map, panels
auto-collapse.

**Styling (light→dark).** Re-express panels with the dashboard's dark tokens; SVG
panels use the exact zone scale. **PearTree** is the risk (Phase 0): dark-theme it,
recolour to the zone scale **if** the embed API allows, **else the pre-committed
fallback** (own palette + zone legend); eliminate the Google-Fonts request either
way.

**i18n.** en/fr for the bounded panel-chrome strings via `data-i18n`; tree tip
labels are zone names (already localised). Author en+fr together, flag French
scientific copy for a native-speaker pass. **Interim: the tab ships en-only until
French is reviewed — never unreviewed machine French.**

## Testing

- **Producer repo:** vitest for the build libs; the alias-join + fail-loud are
  covered **here** (where they run), not in dashboard pytest.
- **Dashboard build:** pytest for the `genomic` slice **wiring + page-scoping**,
  and for the **new onset aggregation** (per-date/zone observed/imputed from the
  imputed-onset linelist).
- **Front-end:** pure helpers keep unit tests. The hard, untested, being-rewritten
  modules (distribution panel incl. imputation/beyond-tree/export; the re-entrant
  coordinator; the clickable-marker selection) get **characterisation tests and/or
  a scripted manual-QA checklist**; the screenshot gate is necessary-but-
  insufficient.
- **Review checkpoints:** (a) dark-theme screenshots incl. PearTree (with fallback
  legend if taken); (b) same-zone-same-colour across map + panels (+ tree, or its
  legend under the fallback); (c) tab numbers match canonical + data build date
  surfaced; (d) narrow-screen stacking.

## Phased delivery

0. **Spike** (above) — gates the rest; four pass bars; may amend this spec.
1. **Producer repo:** create `INRB-UMIE/BDBV2026-Genomic_Epi` by cherry-pick from
   `joetsui1994/BDBV2026_genomic_epi` (left live); confirm products + alias-join +
   fail-loud + vitest in its CI.
2. **Ingestion + slices:** dashboard CI pulls products (sibling + env override);
   `payload.py` builds the page-scoped `genomic` slice, tree delivery per Phase 0,
   **and the aggregated observed/imputed onset series + beyond-tree** from the
   canonical linelist.
3. **Seam:** additive contribution interface in `chrome.py`; genomic leaves
   `STUB_VIEWS`.
4. **Map hooks:** generic layer-register + zone-select subscribe in `engine.js`, +
   the `activeView` branch of the zone-click handler.
5. **Panels + coordinator:** `genomic.js` — phylogeny → Ne → distribution + the
   genomic-local coordinator + clickable-marker selection.
6. **Style + i18n:** dark port (PearTree per Phase 0 outcome); en/fr keys; ship
   en-only until French reviewed.
7. **Polish + review:** narrow-screen; the four checkpoints + characterisation
   tests/QA checklist.

## Open items / risks

- **PearTree (M4/M5/S4):** dark-theming, per-zone recolour (else the pre-committed
  fallback), inline-vs-URL loading, and the Google-Fonts request resolve in Phase 0.
  Provenance/licence is **unestablished** (no LICENSE/version; bundles `marked`) —
  pin a versioned, licence-clear build before vendoring 1.5 MB.
- **Onset/beyond-tree data (S2/R3):** the numeric series isn't in `payload.py`
  today; the canonical linelist exists, so it's medium aggregation work — validated
  in Phase 0 item 4, built in Phase 2.
- **Two producer copies (R2/S3):** keeping the standalone site live means the
  producer logic lives in both repos; keep in sync, or later repoint the standalone
  app at `BDBV2026-Genomic_Epi`.
- **Shared-code touch (R7):** the `activeView` branch of the zone-click handler is
  expected, contained work — named, not hidden.
- **French copy:** native-speaker review pass (interim: en-only).
- **Data-cadence staleness (S1):** tree (rare) beside case data (6-hourly); the
  "data build date" is surfaced; canonical `genomic_sequence_count` governs shown
  counts.
