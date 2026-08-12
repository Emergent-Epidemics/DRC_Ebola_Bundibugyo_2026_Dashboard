# Genomic Epidemiology tab — design

**Date:** 2026-08-12 (revised after code-grounded review)
**Status:** Design revised in response to review; **a Phase 0 spike must pass before implementation planning** (see Phase 0 and Open items).
**Review:** `docs/superpowers/specs/2026-08-12-genomic-epidemiology-tab-design-review.md`

## Context

The dashboard's **Genomic Epidemiology** tab is currently a "coming soon" stub
(`Scripts/pages/genomic_epidemiology.py`'s `build_page()` delegates to the shared
`render_page()`; genomic is in `STUB_VIEWS` in `Scripts/common/chrome.py`). A
separate standalone app —
`/Users/user/Documents/work/DRC-Ebola-genomic-epi-public` ("ituri-dashboard") —
implements a rich interactive genomic view: a phylogeny (PearTree), an
effective-population-size panel (SkyGrid + exponential-growth estimates), a
sample-distribution time series, and a linked map. This project moves that
content into the dashboard's genomic tab, natively.

The two codebases are architecturally opposite:

- **Dashboard (target):** a Python static-site generator. One shared hand-written
  `Scripts/assets/engine.js` (~3,900 lines) + `dashboard.css` (~1,150 lines); a
  single inline JSON payload per page parsed synchronously; **no JS build step**;
  dark chrome; Leaflet; en/fr i18n via `data-i18n` + `locales/{en,fr}.yaml`.
- **Source app:** a Vite/ESM app of small modules (`tree-panel.js`,
  `ne-panel.js`, `timeseries-panel.js`, `coordinator.js`, `map-panel.js`, +
  helpers) with vitest tests (pure helpers + build libs only — the four large UI
  modules and the coordinator have **no tests**); fetches JSON/CSV at runtime; a
  warm **light** theme; an external `peartree.bundle.min.js` (~1.5 MB) phylogeny
  renderer.

## Goals

- The genomic tab becomes **fully native** to the dashboard: dark chrome, shared
  header/nav/footer, en/fr i18n, and data consistent with the rest of the
  dashboard.
- **Style consistency:** the tab reads as the same product as every other tab; a
  health zone is the same colour everywhere (subject to the PearTree spike, M4).
- **Data consistency:** case counts, zone geometry/names, and sampling counts
  shown in the tab are the *same numbers* the rest of the dashboard shows, with
  the tree's analysis vintage surfaced so stale-vs-fresh is legible.
- **Efficiency:** reuse the dashboard's existing map surface, rail/splitter, and
  panel-collapse mechanics; port only genuinely genomic logic; do not rewrite
  BEAST/tree parsers.
- Establish a **per-tab separation seam** (genomic is the pilot) that is also the
  stepping stone to a possible future SPA, without committing to SPA now.

## Non-goals

- No client-side router / SPA shell now; the dashboard stays a multi-page static
  site (MPA); the inline-payload synchronous-parse bootstrap is retained.
- No refactoring of the existing tabs into the new seam. The seam is additive.
- No Python reimplementation of the phylodynamic/tree transforms.
- No shared, cross-tab selection bus in `engine.js` (see Decision 6 / §4).

## Key decisions

1. **Integration goal:** fully native.
2. **Map:** reuse the dashboard's shared Leaflet map *surface*, but **port the
   source `map-panel.js` marker/grouping logic** into a genomic-only tip-marker
   layer on that map (this is real new work — see §4/§5; the earlier "don't port
   map-panel.js" framing was wrong). Tip/area-level linking is preserved because
   `tips.json` carries per-tip `lat`/`lon`/`health_zone`/`health_area`.
3. **Genomic data pipeline:** **transfer the existing producer repo
   `github.com/joetsui1994/BDBV2026_genomic_epi` into the org as
   `INRB-UMIE/BDBV2026-Genomic_Epi`** (extraction + org move + CI wiring, *not*
   greenfield; resolves the underscore-vs-hyphen naming collision). It holds BEAST
   inputs + the Node build scripts and commits the derived data products. The
   dashboard CI ingests those artifacts (same pattern as `dashboard_plots`).
4. **Layout:** right rail (Option A) — phylogeny (top) / Ne / sample-distribution
   stacked, drag-resizable, matching the Trends/Spatial-Risk rails; genomic rail
   defaults wider (the tree needs width).
5. **JS architecture:** a separate hand-written static `Scripts/assets/genomic.js`
   in `engine.js`'s idiom, loaded only on the genomic page. No JS bundler added.
6. **Coordination:** the cross-panel coordinator lives **inside `genomic.js`**
   (genomic-local), not as a shared bus in `engine.js`. `engine.js` exposes only
   minimal map hooks. SPA-readiness lives in the tab module's `mount/unmount`.
7. **Separation seam:** an SPA-shaped per-tab contribution interface, **genomic
   only**; existing tabs untouched.

## Phase 0 — de-risking spike (gates everything else)

Throwaway code, no new repo, no seam. Prove the three unknowns the review flagged
as design-invalidating **before** standing up `BDBV2026-Genomic_Epi` and the seam:

1. **PearTree dark + recolour + delivery (M4/M5).** Embed the *real* NEXUS tree in
   a *dark* rail and answer:
   - Can its Bootstrap-light theme be forced dark via the embed API / `--pt-*`
     overrides, or does it require forking the 1.5 MB bundle?
   - Does the embed API accept a **custom per-`health_zone` colour map** so tips
     use the dashboard's exact zone scale ("one zone = one colour")? If not, that
     hard requirement is unsatisfiable without a fork — decide fork vs. relax.
   - Does `PearTree.embed` accept **inline tree text**, or only a `treeUrl`? This
     decides whether the tree is an inline payload value or a page-scoped fetched
     asset. It is **NEXUS text, not JSON**.
   - Its head `@import`s Google Fonts over the network — reconcile with the page's
     offline/CSP posture (vendor the font or accept the request).
2. **Tip-level map linking (M1).** Add a genomic tip-marker layer to the *real*
   dashboard map from tip `lat`/`lon`, click a marker → highlight its tips, and
   round-trip a zone-polygon click. Confirm the effort and that it doesn't fight
   the map's existing per-view selection paths.
3. **Coordinator contract (M2).** Stand up the tip-set-or-zone toggle,
   view-transform→timeseries coupling, and date-marker fan-out against the real
   tree + map, to validate the genomic-local coordinator shape.

**Exit criteria:** either "all three feasible as designed" → proceed; or a
documented design change (e.g. fork PearTree; relax to zone-level colouring;
tree-as-fetched-asset) folded back into this spec before Phase 1.

## Architecture

### 1. Repos & data flow

```
INRB-UMIE/BDBV2026-Genomic_Epi (producer; transferred from joetsui1994/BDBV2026_genomic_epi)
    BEAST/HIPSTR tree inputs + .mjs build scripts (+ aliases.csv, + vitest suite)
    → commits products: ituri-tree.ptree (NEXUS), tips.json, meta.json, skygrid.json, exponential.json
    → alias-join + FAIL-LOUD live HERE (tree-lib.mjs:68 throws; build-status.mjs:49 exit 1)
    → CI rebuilds on a new phylodynamic analysis (rare)

BDBV2026-Processed_Sensitive_Data → case/status aggregates (canonical, 6-hourly)
BDBV2026-Data                      → geometry, zone metadata, genomic_sequence_count (canonical)

        │  dashboard CI pulls pre-validated products (sibling-clone + env override)
        ▼
Dashboard build (Python) — ingests finished JSON/NEXUS; no Node, no join, no fail-loud here
    common/payload.py → shared payload + page-scoped "genomic" slice
    per-page seam     → genomic contributes body HTML + JS + payload keys + assets
    chrome.py         → shared chrome; genomic removed from STUB_VIEWS
        │  emits one static page per tab (as today)
        ▼
genomic-epidemiology.html  (real page weight ~1.65 MB: ~150 KB data + ~1.5 MB PearTree)
    engine.js (shared core + shared map + minimal genomic map hooks)
    genomic.js (ported panels + genomic-local coordinator; mount/unmount; page-scoped)
    peartree.bundle.js (page-only; pin a versioned, licence-clear build before vendoring)
    page-scoped "genomic" payload slice (+ tree as inline value or fetched asset — Phase 0 decides)
```

`BDBV2026-Genomic_Epi` is a producer only (no app/Pages site). Raw MCMC logs stay
git-ignored (as today); committed products are the derived data. It does **not**
carry a status-sync workflow — case/status is the dashboard's job (see §2).

**Why a separate repo over a `BDBV2026-Data` subdirectory:** it mirrors the
existing `dashboard_plots` ingestion pattern; keeps the Node/BEAST toolchain and
its rare, analyst-driven release cadence isolated from `BDBV2026-Data`'s cadence;
and it already exists as a standalone repo (transfer, not greenfield). Cost: one
more CI-secret-bearing repo to maintain — accepted.

### 2. Data-consistency model

Two classes of data, sourced deliberately:

- **Canonical / overlapping** — case counts, zone geometry and names, per-zone
  sampling counts — come **only** from the dashboard's `payload.py`. The source
  app's own copies (`status_confirmed.csv`, its `health-zones.geojson`) are
  dropped. (`timeseries.json` is already a dead/orphan file upstream — nothing
  fetches it.)
- **Genuinely genomic** — tree (NEXUS), tips, Ne/SkyGrid, exponential — come from
  `BDBV2026-Genomic_Epi`.
- **Join + fail-loud stay in the producer.** The `aliases.csv` crosswalk and the
  unknown-zone hard failure run in the producer's build (where they already live),
  so the dashboard ingests only pre-validated products. A genomic zone-name
  mismatch fails the *producer's* CI, never the dashboard's 6-hourly case
  rebuild. The dashboard runtime must not silently pass unknown zones (the source
  runtime does — we rely on producer validation instead).

**Per-zone sequence counts — one authority.** The canonical
`genomic_sequence_count` (from `BDBV2026-Data`, rebuilt 6-hourly;
`data_sources.py:2989`, `engine.js:1673`) is authoritative for any count *shown*
in the tab. The tree's tips reflect the (rarer) analysis snapshot and can lag; the
tab must **surface the analysis/tree date** so the tree's vintage is visible and
a tips-vs-canonical mismatch is explicable rather than a silent contradiction of
Goal #3. (Consistency anchor already present: the payload carries
`genome_sequence_markers` — `payload.py:195` — and `engine.js` renders a
genome-count map layer.)

**Delivery.** The small JSON products (~150 KB total) ride in as a **page-scoped
payload slice** via the existing `_PAGE_SCOPED_PAYLOAD_KEYS` mechanism
(`chrome.py`; key `genomic`). The **tree** is NEXUS loaded by PearTree from a URL
today; Phase 0 decides whether it becomes an inline payload value (if `embed`
accepts inline text) or a **page-scoped fetched asset** like the bundle.
`peartree.bundle.js` loads as a genomic-page-only script.

### 3. Per-tab contribution seam (Python)

An **additive** seam in `chrome.py`. A page module may declare: `body_html` (its
own panel markup, injected into a per-view content slot instead of the shared
`BODY_TEMPLATE`), `scripts` (page-only: `genomic.js`, `peartree.bundle.js`),
`payload_keys` (`genomic`), `styles` (page-only CSS). `render_page()` composes
these; existing tabs declare none and render exactly as today.
`genomic_epidemiology.py` supplies the four and leaves `STUB_VIEWS`.

### 4. Genomic tab module: lifecycle + genomic-local coordinator (JS)

`Scripts/assets/genomic.js` exports a tab module for MPA-now / SPA-later:

```
createGenomicTab(context) → { mount(), unmount() }
```

`context` supplies explicit deps: `map` (shared Leaflet instance), `mapHooks`
(minimal genomic map API from `engine.js` — see below), `i18n`, `data` (the
`genomic` slice). MPA: `engine.js` calls `mount()` once when
`data-initial-view === "genomic-epidemiology"`. SPA (future): a router calls
`mount()`/`unmount()`. `unmount()` tears down listeners, the tip-marker layer, and
subscriptions.

**Genomic-local coordinator.** The full `coordinator.js` contract is ported *into*
`genomic.js` (not a shared bus). It must reproduce, verified against the code:
- selection is **either a tip-set** (tree/marker click) **or a zone** (polygon),
  one replacing the other;
- **click-again-to-deselect** (`activeKey`) with re-entrancy flags
  (`programmatic`, `zoneSelecting`);
- a **non-selection** channel: `tree.onViewChange → timeseries.setTransform`
  (tree pan/zoom drives the distribution x-axis);
- **date-marker fan-out** to the timeseries and Ne panels.

**Minimal `engine.js` map hooks** (the only shared-code change): expose the shared
map's existing zone-selection as subscribe/emit, plus an API to add/remove a
genomic tip-marker layer and highlight tips. **Ownership rule (M3):** on the
genomic page only the genomic coordinator drives selection styling; the other
tabs' selection paths (`epiSelectedNom`, `contextSelectedNom`, trends) are inert
here, so there is no contention — this is asserted and must be checked in Phase 0.

### 5. Ported vs reused

- **Reused (dashboard's own):** the shared Leaflet map surface; rail +
  drag-splitter; `wirePanelToggles()` collapse; i18n; zone colour scale;
  header/nav/footer chrome; per-browser `localStorage` rail sizing.
- **Ported (rewritten into `engine.js`'s idiom, dark theme):** the
  `map-panel.js` **marker/grouping/linking** logic → a genomic tip-marker layer on
  the shared map; the Ne/SkyGrid + exponential chart; the sample-distribution
  chart (the 658-line `timeseries-panel.js`, incl. imputation split, beyond-tree,
  and a **CSV export/download modal** — an action, not a view toggle); the
  coordinator; small helpers (`log-scale`, `time-scale`, `tree-band`; `node-info`
  is **DOM-touching, not pure** — no unit test parity with the pure helpers).
- **Not ported:** PearTree itself (black-box bundle, embedded, not rewritten — the
  earlier "rewrite tree rendering" wording was wrong); the source `splitter.js` /
  `panel-collapse.js` (dashboard has its own); the source data copies + status
  sync.

### 6. Layout, styling, i18n

**Layout.** Shared map fills the viewport; drag-resizable right rail holds
phylogeny (top) / Ne / sample-distribution, reusing the `#epi-trends-panel` /
`#trends-panel` rail pattern; genomic rail defaults wider; panels keep their
toggles (tree: Legend / Node Bars / Tip Labels; Ne: Exp / SkyGrid / full-extent;
distribution: Imputed / beyond-tree / CSV-export) and collapse via
`wirePanelToggles()`. Narrow screens (≤700px): rail stacks under the map, panels
auto-collapse.

**Styling (light→dark).** Do not copy the source `style.css`; re-express panels
with the dashboard's dark tokens/classes. Health-zone colours on the SVG panels
use the dashboard's exact zone scale. **PearTree is the exception and the risk**
(M4, Phase 0): darkening it and forcing its palette onto the zone scale depend on
its embed API — may require a fork; the Google-Fonts `@import` must be reconciled.

**i18n.** en/fr for the bounded panel-chrome strings via `data-i18n`; tree tip
labels are zone names (already localised). Author en+fr keys together, but flag
French scientific copy for a native-speaker pass. **Interim state (explicit): the
tab ships en-only until French is reviewed — never unreviewed machine French.**

## Testing

- **Producer repo:** keep the vitest suite for the build libs (`tree-lib`,
  `skygrid-lib`, `exponential-lib`, `hipstr-parse`, `egc-inline-parse`); the
  alias-join + fail-loud are covered **here** (where they run), not in dashboard
  pytest.
- **Dashboard build:** pytest for the `genomic` slice **wiring and page-scoping**
  (slice present only on the genomic page) — not the join.
- **Front-end:** the pure helpers keep unit tests. The hard, being-rewritten,
  untested modules (timeseries 658 lines incl. imputation/beyond-tree/export; the
  re-entrant coordinator; the map marker layer) get **characterisation tests
  and/or a scripted manual-QA checklist** — the screenshot gate is
  necessary-but-insufficient here.
- **Review checkpoints:** (a) dark-theme screenshots of every panel incl.
  PearTree; (b) same-zone-same-colour across map and tree; (c) tab numbers match
  canonical figures and the tree date is surfaced; (d) narrow-screen stacking.

## Phased delivery

0. **Spike** (above) — gates the rest; may amend this spec.
1. **Producer repo:** transfer `joetsui1994/BDBV2026_genomic_epi` →
   `INRB-UMIE/BDBV2026-Genomic_Epi`; confirm products + alias-join + fail-loud +
   vitest run in its CI.
2. **Ingestion + slice:** dashboard CI pulls products (sibling + env override);
   `payload.py` builds the page-scoped `genomic` slice; wire tree delivery per
   Phase 0's finding; **establish the canonical source for the distribution
   panel's observed/imputed onset + beyond-tree series** (a new `payload.py`
   input — see S2; currently absent).
3. **Seam:** additive contribution interface in `chrome.py`; genomic leaves
   `STUB_VIEWS`; page module contributes HTML/scripts/keys/styles.
4. **Map hooks:** minimal genomic map API in `engine.js`.
5. **Panels + coordinator:** `genomic.js` — port panel by panel (phylogeny → Ne →
   distribution) + the genomic-local coordinator + tip-marker layer.
6. **Style + i18n:** dark port (incl. PearTree resolution from Phase 0); en/fr
   keys; ship en-only until French reviewed.
7. **Polish + review:** narrow-screen; the four checkpoints + characterisation
   tests/QA checklist.

## Open items / risks

- **PearTree (M4/M5/S4):** dark theming, custom zone-colour map, inline-vs-URL
  tree loading, and Google-Fonts request are all **unresolved until Phase 0**.
  Provenance/licence is currently **unestablished** (no LICENSE/version in the
  bundle; it also bundles `marked`) — pin a versioned, licence-clear build before
  vendoring 1.5 MB into the dashboard.
- **Distribution panel data (S2):** the observed/imputed onset split and
  beyond-tree series the 658-line panel needs are **not established** in
  `payload.py`; Phase 2 must source them or the panel is blocked.
- **Data-cadence staleness (S1):** tree (rare) beside case data (6-hourly);
  surface the analysis date; canonical `genomic_sequence_count` governs shown
  counts.
- **Map contention (M3):** the ownership rule must be verified in Phase 0.
- **Producer transfer (S3):** org transfer + CI secrets/token + dashboard
  sibling-clone wiring, mirroring the sensitive-data ingestion.
- **French copy:** native-speaker review pass (interim: en-only).
