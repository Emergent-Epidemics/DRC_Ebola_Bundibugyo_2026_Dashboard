# Genomic Epidemiology tab — design

**Date:** 2026-08-12
**Status:** Approved design, ready for implementation planning
**Author:** brainstormed with the dashboard maintainer

## Context

The dashboard's **Genomic Epidemiology** tab is currently a "coming soon" stub
(`Scripts/pages/genomic_epidemiology.py` → `render_page`, listed in
`STUB_VIEWS` in `Scripts/common/chrome.py`). A separate standalone application —
`/Users/user/Documents/work/DRC-Ebola-genomic-epi-public` ("ituri-dashboard") —
already implements a rich interactive genomic-epidemiology view: a phylogeny
(PearTree), an effective-population-size panel (SkyGrid + exponential-growth
estimates), a sample-distribution time series, and a linked map. This project
moves that content into the dashboard's genomic tab.

The two codebases are architecturally opposite:

- **Dashboard (target):** a Python static-site generator. One shared hand-written
  `Scripts/assets/engine.js` (~3,900 lines) + `dashboard.css` (~1,150 lines); a
  single inline JSON payload per page parsed synchronously; **no JS build step**;
  dark chrome; Leaflet; en/fr i18n via `data-i18n` + `locales/{en,fr}.yaml`.
- **Source app:** a Vite/ESM app of small modules (`tree-panel.js`,
  `ne-panel.js`, `timeseries-panel.js`, `coordinator.js`, `map-panel.js`, +
  helpers) with vitest tests; fetches JSON/CSV data at runtime; a warm **light**
  theme; an external `peartree.bundle.min.js` (~1.5 MB) phylogeny renderer.

## Goals

- The genomic tab becomes **fully native** to the dashboard: dark chrome, shared
  header/nav/footer, en/fr i18n, and data consistent with the rest of the
  dashboard.
- **Style consistency:** the tab reads as the same product as every other tab; a
  health zone is the same colour everywhere.
- **Data consistency:** case counts, zone geometry/names, and sampling counts
  shown in the tab are the *same numbers* the rest of the dashboard shows.
- **Efficiency:** reuse the dashboard's existing map, rail/splitter, and
  panel-collapse mechanics; port only genuinely genomic rendering logic; do not
  rewrite BEAST/tree parsers.
- Establish a **per-tab separation seam** (genomic is the pilot) that is also the
  stepping stone to a possible future SPA, without committing to SPA now.

## Non-goals

- No client-side router / SPA shell now. The dashboard stays a multi-page static
  site (MPA); the inline-payload synchronous-parse bootstrap is retained.
- No refactoring of the existing tabs (Snapshot, Trends, Spatial Risk, Context,
  …) into the new seam. The seam is additive; existing tabs render exactly as
  today.
- No Python reimplementation of the phylodynamic/tree transforms.
- The standalone `DRC-Ebola-genomic-epi-public` app is not a dependency and is
  not carried along.

## Key decisions (resolved during brainstorming)

1. **Integration goal:** fully native.
2. **Map:** reuse the dashboard's shared Leaflet map; re-wire cross-panel linking
   to the dashboard's selection model. Do **not** port the source app's
   `map-panel.js`.
3. **Genomic data pipeline:** a **new dedicated upstream data-producer repo,
   `BDBV2026-Genomic_Epi`**, holds BEAST inputs + the Node build scripts and
   commits the derived JSON products. The dashboard CI ingests those artifacts
   (same pattern as `dashboard_plots`). No JS reimplementation in Python.
4. **Layout:** right rail (Option A) — phylogeny (top) / Ne / sample-distribution
   stacked, drag-resizable, matching the Trends/Spatial-Risk rails.
5. **JS architecture:** a separate hand-written static `Scripts/assets/genomic.js`
   in `engine.js`'s idiom, loaded only on the genomic page. No JS bundler added.
6. **Separation seam:** an SPA-shaped per-tab contribution interface, **genomic
   only**. The tab module has a `mount(context)`/`unmount()` lifecycle with
   explicit dependencies; existing tabs are untouched.

## Architecture

### 1. Repos & data flow

```
BDBV2026-Genomic_Epi (NEW, data producer, Node)
    BEAST/HIPSTR tree inputs + ported .mjs scripts
    → commits JSON products: tree.ptree, tips, meta, skygrid.json, exponential.json
    → CI rebuilds on a new phylodynamic analysis

BDBV2026-Processed_Sensitive_Data   → case/status aggregates (canonical, 6-hourly)
BDBV2026-Data                        → geometry, zone metadata, genome_sequence_count (canonical)

        │  dashboard CI pulls artifacts (sibling-clone convention, env-overridable)
        ▼
Dashboard build (Python)
    common/payload.py   → shared payload + NEW named "genomic" slice (alias-joined)
    per-page seam       → genomic contributes body HTML + JS + payload keys + assets
    chrome.py           → shared chrome; genomic removed from STUB_VIEWS
        │  emits one static page per tab (as today)
        ▼
genomic-epidemiology.html
    engine.js (shared core + shared map + NEW selection bus + tab-mount hook)
    genomic.js (ported panels, mount/unmount, page-scoped)
    peartree.bundle.js (1.5 MB, page-only)
    page-scoped "genomic" payload slice
```

`BDBV2026-Genomic_Epi` is a producer only — no app, no Pages site. It carries the
BEAST/HIPSTR tree inputs (committed, as the source app does today), the raw MCMC
logs stay git-ignored, and the ported `.mjs` scripts (`build-tree`,
`build-skygrid`, `build-exponential`, and their libs/tests: `tree-lib`,
`skygrid-lib`, `exponential-lib`, `hipstr-parse`, `egc-inline-parse`) produce the
committed JSON products. It does **not** carry the source app's status-sync
workflow — case/status data is the dashboard's job (see consistency model).

Dashboard ingestion mirrors `dashboard_plots`: assume the producer repo is cloned
as a sibling, with an env var (e.g. `GENOMIC_EPI_DIR`) to override. The build
reads the committed JSON directly; no Node runs in the dashboard build.

### 2. Data-consistency model

Two classes of data, sourced deliberately:

- **Canonical / overlapping** — case counts, health-zone geometry and names,
  per-zone genome sampling counts — come **only** from the dashboard's existing
  `payload.py`. The source app's own copies (`status_confirmed.csv`, its
  `health-zones.geojson`, its `timeseries.json`) are dropped.
- **Genuinely genomic** — the tree, Ne/SkyGrid, exponential-growth estimates —
  come from `BDBV2026-Genomic_Epi`.
- **Join:** the source app's `aliases.csv` crosswalk (observed sample zone-name →
  canonical `Nom`) is carried into the producer/build so genomic samples map onto
  the dashboard's canonical zones. **Fail loudly** on an unmatched zone (build
  error, nothing shipped) — same discipline the source app uses today — rather
  than silently dropping samples.

Delivery: the genomic JSON is small (~150 KB total), so it rides in as a
**page-scoped payload slice** via the existing `_PAGE_SCOPED_PAYLOAD_KEYS`
mechanism in `chrome.py` (key: `genomic`) — present only on the genomic page,
zero bloat elsewhere. `peartree.bundle.js` loads as a genomic-page-only script.

Consistency anchor already present: the dashboard payload already carries
`genome_sequence_markers` and per-zone `genomic_sequence_count`, and `engine.js`
already renders a genome-count map layer — the genomic tab builds on the same
canonical sampling data.

### 3. Per-tab contribution seam (Python)

Introduce an **additive** seam in `chrome.py`. A page module may declare:

- `body_html` — its own panel markup, injected into a per-view content slot
  (instead of living in the shared `BODY_TEMPLATE`).
- `scripts` — extra page-only scripts (`genomic.js`, `peartree.bundle.js`).
- `payload_keys` — the page-scoped data slice it needs (`genomic`).
- `styles` — optional page-only CSS (or a namespaced block appended to
  `dashboard.css`).

`render_page()` composes these. Existing tabs declare none and render exactly as
today (no regression surface). `genomic_epidemiology.py` supplies the four items
above and is removed from `STUB_VIEWS`. The genomic panel HTML (right rail:
phylogeny / Ne / sample-distribution, with their toggles) lives in the genomic
page module, not the shared template.

### 4. Genomic tab module: lifecycle + selection bus (JS)

`Scripts/assets/genomic.js` exports a tab module shaped for both MPA-now and
SPA-later:

```
createGenomicTab(context) → { mount(), unmount() }
```

`context` supplies **explicit dependencies** (no reaching for globals):

- `map` — the shared Leaflet map instance from `engine.js`
- `selection` — the shared selection bus (below)
- `i18n` — the translation function `engine.js` already exposes
- `data` — the named `genomic` payload slice

MPA driver: `engine.js` calls `mount()` once after boot when
`data-initial-view === "genomic-epidemiology"`. SPA driver (future): a router
calls `mount()`/`unmount()` on route change. Nothing in `genomic.js` assumes a
fresh page load; `unmount()` tears down listeners, layers, and subscriptions.

**Selection bus** (the one genuinely new hook in shared `engine.js`): a tiny
pub/sub — `selection.get()`, `selection.set(zone, source)`,
`selection.subscribe(fn)`. The shared map publishes/consumes zone selection on it.
`genomic.js` subscribes to drive tree/distribution highlighting and publishes back
when a tip or distribution bar is picked. This replaces the source app's
`coordinator.js` wiring and is reusable by every future tab.

### 5. Ported vs reused

- **Reused (dashboard's own):** the shared Leaflet map; rail + drag-splitter;
  `wirePanelToggles()` panel-collapse; i18n; zone colour scale; header/nav/footer
  chrome; per-browser `localStorage` rail sizing.
- **Ported (rewritten into `engine.js`'s plain-`const`/DOM idiom, dark theme):**
  tree rendering (via PearTree), the Ne/SkyGrid + exponential chart, the
  sample-distribution chart, and small pure helpers (`log-scale`, `time-scale`,
  `tree-band`, `node-info`), plus the coordinator logic re-expressed against the
  selection bus.
- **Dropped:** `map-panel.js`, `splitter.js`, `panel-collapse.js`, the source
  app's data copies and status-sync workflow.

### 6. Layout

Shared map fills the viewport; a drag-resizable **right rail** holds phylogeny
(top, tallest) / Ne / sample-distribution, reusing the `#epi-trends-panel` /
`#trends-panel` rail + split-handle pattern.

- The genomic rail **defaults wider** than the Trends/Spatial-Risk rails (the tree
  needs width as well as height); still user-draggable and remembered per browser.
- Each panel keeps its source-app toggles — tree: Legend / Node Bars / Tip
  Labels; Ne: Exp / SkyGrid / full-extent; distribution: Imputed / CSV /
  beyond-tree — and is collapsible via `wirePanelToggles()`.
- Narrow screens (≤700px): rail stacks under the map, panels auto-collapse to
  title bars — matching every other tab.

### 7. Styling — light→dark port

The biggest visual-consistency task. Do **not** copy the source app's
`style.css`. Re-express the genomic panels using the dashboard's dark panel
tokens/classes (`.panel`, `.panel-header`, legend bars, …), remapping the source
app's semantic accents onto the dashboard's palette:

- Tree tip/legend health-zone colours use the **exact** zone colour scale the
  shared map uses (hard requirement: one zone = one colour everywhere).
- The source app's maroon (deaths/primary) and terracotta (secondary) accents map
  onto the dashboard's existing accent variables.
- Tree/Ne/distribution SVGs get dark-appropriate strokes, grid lines, and tooltip
  styling (the source app assumes light backgrounds).

"Every genomic panel looks native in dark" is an explicit screenshot review
checkpoint before completion.

### 8. i18n

Fully native ⇒ en/fr. The genomic panel chrome is a bounded set of new strings
(panel titles, toggle labels, tooltips, axis labels) added to `locales/en.yaml` +
`fr.yaml` via `data-i18n`. Tree tip labels are health-zone names and already
localise through the dashboard's existing zone-name handling. Author **en and fr
keys together**, but flag the French scientific copy ("effective population
size", "SkyGrid", "exponential growth", …) for a native-speaker pass by the team
rather than shipping unreviewed machine French.

## Testing

- **Producer repo:** the ported `.mjs` libs keep their vitest tests
  (`tree-lib`, `skygrid-lib`, `exponential-lib`, `hipstr-parse`,
  `egc-inline-parse`), guarding the JSON products.
- **Dashboard build:** pytest coverage (run from `Scripts/`, python3.9) for the
  new payload `genomic` slice + alias join, including the fail-loud-on-unmatched
  behaviour and the page-scoping (genomic slice absent from other pages'
  payloads).
- **Front-end:** the pure ported helpers (`log-scale`, `time-scale`,
  `tree-band`, `node-info`) keep unit tests where feasible; the selection-bus
  contract gets a focused test.
- **Review checkpoints:** (a) dark-theme screenshots of every genomic panel;
  (b) same-zone-same-colour check across map and tree; (c) numbers in the tab
  match the canonical dashboard figures; (d) narrow-screen stacking.

## Phased delivery

1. **Upstream repo** `BDBV2026-Genomic_Epi`: move BEAST inputs + `.mjs` build
   scripts + their tests; CI emits committed JSON products. `aliases.csv`
   carried here.
2. **Ingestion + data slice:** dashboard CI pulls the products (sibling
   convention + env override); `payload.py` builds the named `genomic` slice with
   the alias join and fail-loud behaviour; wire the page-scoped payload key.
3. **Seam:** additive per-page contribution interface in `chrome.py`; remove
   genomic from `STUB_VIEWS`; `genomic_epidemiology.py` contributes body
   HTML/scripts/keys/styles.
4. **Shared hooks:** selection bus + tab-mount hook in `engine.js`.
5. **Panels:** `genomic.js` — port panel by panel (phylogeny → Ne →
   sample-distribution), each wired to the shared map via the selection bus.
6. **Style + i18n:** dark-theme port; en/fr keys; French flagged for review.
7. **Polish + review:** narrow-screen behaviour; the four review checkpoints.

## Open items / risks

- **French copy** needs a native-speaker review pass (flagged, not blocking the
  build).
- **PearTree bundle** is a new 1.5 MB page-only dependency — acceptable as a
  genomic-page-only asset; confirm licensing/vendoring is fine to commit into the
  dashboard `assets/`.
- **Tree in a rail** — width pressure; mitigated by a wider default rail + user
  drag, but worth an early layout sanity check with the real tree.
- **New repo bootstrapping** (`BDBV2026-Genomic_Epi`) — CI secrets/tokens and the
  sibling-clone convention in the dashboard's own CI need setup, mirroring the
  existing sensitive-data ingestion.
