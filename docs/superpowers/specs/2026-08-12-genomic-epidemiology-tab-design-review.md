# Critical review — Genomic Epidemiology tab design

**Reviews:** `docs/superpowers/specs/2026-08-12-genomic-epidemiology-tab-design.md`
**Date:** 2026-08-12
**Method:** claims cross-checked against the live dashboard code
(`Scripts/…`) and the source app (`/Users/user/Documents/work/DRC-Ebola-genomic-epi-public`).

## Verdict

The overall shape is sound and the big decisions are defensible: fully-native
integration, a producer repo mirroring `dashboard_plots`, reusing the rail/splitter/
panel-collapse mechanics, and a page-scoped payload slice. The seam is genuinely
additive and low-regression.

But the spec is labelled *"Approved design, ready for implementation planning,"* and
that is premature. Three **load-bearing** questions are asserted as solved when the
code says they are not: (1) reusing the dashboard map for tip-level linking, (2) the
selection-bus API actually being able to express the behaviour it replaces, and
(3) whether PearTree can be darkened *and* forced onto the dashboard's zone colours —
a black-box renderer that currently controls both. Each can invalidate parts of the
plan. They should be de-risked with a spike **before** the repo/seam/bus scaffolding
is built, not in phases 5–7 as currently sequenced.

Findings below are ordered by severity. Factual corrections are collected at the end.

---

## Major concerns

### M1. "Reuse the dashboard map" hides real new map work; today's map can't do tip-level linking

The spec (Decision 2, §5) says reuse the shared Leaflet map and *do not* port
`map-panel.js`, re-wiring linking "to the dashboard's selection model." The code shows
the two maps operate at **different granularities**:

- **Source app** (`map-panel.js:100–115`) groups tips by **`health_area`** (falling back
  to `health_zone`), places a `circleMarker` per group at the area/zone centroid, and on
  click **emits that group's individual tip IDs** (`onMarkerClick`). `map.highlight(tipIds)`
  then highlights individual samples. Linking is **tip/area-level**.
- **Dashboard map** exposes only per-*zone* selection (`mapSelectedNom`, `setMapSelection`
  at `engine.js:203`) and a genome layer that is **aggregate per-zone count icons**
  (`genomeLayer`, `genomeIcon(count)` at `engine.js:3301/3331`) — not clickable
  per-sample markers, and there is no `health_area` marker concept.

To reproduce the source app's map↔tree linking on the dashboard map you must add:
clickable tip-group markers, individual-sample highlight, and (if you want to keep the
current fidelity) `health_area` centroids the dashboard may not carry. That is real map
work the "don't port `map-panel.js`" decision quietly signs up for.

**Decide explicitly:** does the dashboard have `health_area` geometry/centroids? If not,
map linking degrades to zone-level — a **functional regression** from the source app that
should be a conscious, documented trade, not a silent one.

### M2. The proposed selection bus can't express the behaviour it's meant to replace

The spec (§4) proposes `selection.get()`, `selection.set(zone, source)`,
`selection.subscribe(fn)` and says the coordinator logic is "re-expressed against the
selection bus." The real `coordinator.js` (105 lines, read in full) is a **stateful
machine**, not a zone pub/sub:

- Selection is **either a TIP-SET or a ZONE** (two kinds) — a `set(zone, source)` signature
  can't represent "these 12 tips are selected" from a marker or tree-node click.
- **Click-again-to-deselect** toggling via `activeKey`; **re-entrancy flags**
  (`programmatic`, `zoneSelecting`) to distinguish direct tree clicks from programmatic
  mutation. Subtle, easy to get wrong.
- A **separate synchronisation channel that is not selection at all**: the tree's
  pan/zoom view-transform drives the timeseries x-axis (`tree.onViewChange → ts.setTransform`).
- **Per-sequence date markers** fanned out to the timeseries and Ne panels
  (`ts.setMarkers`, `nePanel.setMarkers`).

Either the bus API must grow well beyond `set(zone, source)`, or the coordinator can't be
"re-expressed against" it. Risk: designing the wrong primitive, then discovering it during
the panel port (phase 5) when the repo/seam are already committed to it. **Design the bus
against the full coordinator contract first.**

### M3. A new bus coexisting with four legacy selection paths — on the same shared map

Non-goal: don't refactor existing tabs. So `engine.js` keeps `mapSelectedNom`,
`epiSelectedNom` (`:1124`), `contextSelectedNom` (`:2751`), and the trends selection
(`setTrendsSelection`, `:2480`) **and** gains a new selection bus. On the shared map, two
selection notions now coexist. Which governs on the genomic page, and how do they avoid
fighting over polygon styling/click handlers? This needs a stated ownership rule.

Corollary: the bus is justified partly as "reusable by every future tab," but that reuse
**requires touching the existing tabs**, which the non-goals forbid. So the reuse benefit
is hypothetical today — the bus is, for now, a genomic-only primitive. That's fine, but it
weakens the "shared engine.js hook" framing; consider whether a genomic-local coordinator
(no `engine.js` change) would be smaller and equally future-proof.

### M4. PearTree is a black box that controls its own theme *and* its own colours — colliding with two hard requirements

The spec (§5) lists "tree rendering (via PearTree)" under **"Ported (rewritten into
engine.js's idiom, dark theme)."** You cannot rewrite PearTree — it's a **1.5 MB minified
bundle** (`public/peartree.bundle.min.js`) consumed as a global (`window.PearTreeEmbed.embed`,
`tree-panel.js:24`). Two stated **hard requirements** run straight into it:

- **Dark-native (§7):** the bundle injects its own **Bootstrap light-theme CSS**
  (`:root,[data-bs-theme=light]{…}` in the bundle head, Solarized-ish palette) and
  `@import`s **Google Fonts over the network** (`fonts.googleapis.com`). Darkening a
  black-box renderer, and doing it while the rest of the dashboard is self-contained, may
  require forking the bundle. The Google-Fonts `@import` is also an external request to
  reconcile with the page's CSP/offline posture.
- **"One zone = one colour everywhere" (§7, called a hard requirement):** the tree today
  is coloured by **PearTree's built-in "O'Toole" palette** (`tree-panel.js:48` — "drives
  branch/tip/… colours"), *not* by any shared scale. Meeting the requirement means
  overriding PearTree's internal palette with the dashboard's exact zone scale — only
  possible if the embed API exposes a per-category colour map. **If it doesn't, this hard
  requirement is unsatisfiable without forking PearTree.**

This is arguably the single riskiest unknown in the project, and it sits on the critical
path for the "looks native in dark" review gate. **Spike it first** (see M8).

### M5. `.ptree` is NEXUS text, not JSON, and PearTree reads it from a URL — so "rides in as a payload slice" needs verification

The spec (§1 diagram, §2) calls the tree a JSON product and delivers it as the inline
`genomic` payload slice. But `ituri-tree.ptree` is a **NEXUS file**
(`#NEXUS / BEGIN TREES; tree TREE1 = [&R] ((((PP_0075Z74[&date=…`), 108 KB, and the source
app **fetches it as text from a URL** and hands the URL/filename to `PearTree.embed`
(`tree-panel.js:7,24–27`). Two things to confirm before relying on the payload-slice plan:

1. Can `PearTree.embed` consume an **inline string** rather than a URL? If it only takes a
   URL, the tree can't be a payload key and should instead be a **page-scoped fetched asset**
   (like `peartree.bundle.js`), which is a different delivery path than the spec describes.
2. Embedding 108 KB of NEXUS (full of `[&…]` annotations and quotes) as a JSON string is
   feasible (`json.dumps` escapes it), but "commits JSON products: tree.ptree" is a
   mischaracterisation — it's NEXUS, not JSON.

### M6. Where does the alias-join + fail-loud live? The spec implies the dashboard build — that couples genomic failures to the 6-hourly case rebuild

The spec is ambiguous. §2 says the crosswalk is "carried into the producer/build," and the
Testing section asks for **pytest** covering "the alias join … including the
fail-loud-on-unmatched behaviour" — implying the join runs in `payload.py`. But in the
source, the fail-loud already lives **in the producer build** (`tree-lib.mjs:68` throws on
an unknown zone; `build-status.mjs:45–49` collects unmatched zones and `process.exit(1)`),
and the **runtime silently passes unknown names through** (not fail-loud at all).

If the join+fail-loud is re-implemented in `payload.py`, a single new genomic sample with
an unrecognised zone spelling fails the **entire dashboard build** — genomic data (rebuilt
rarely) taking down the **6-hourly case rebuild**. Prefer keeping the join+fail-loud in the
**producer** (where it already is), so the dashboard only ever ingests pre-validated JSON
and a genomic mismatch fails only the producer's CI. Blast radius should be a deliberate
decision, and the current ambiguity leans the wrong way.

### M7. The hard, coupled, being-rewritten modules are exactly the ones with no tests

The four largest runtime modules — `timeseries-panel.js` (658), `map-panel.js` (543),
`ne-panel.js` (263), `tree-panel.js` (250) — plus `coordinator.js` (105) have **no tests**.
The vitest suite covers only pure helpers (`log-scale`, `time-scale`, `tree-band`, …) and
build libs. That's ~1,800 lines of DOM/Leaflet/PearTree UI being **ported, re-themed to
dark, and re-wired to a new selection bus and a different map — with no regression net.**

The spec's Testing section promises tests for the pure helpers, the selection-bus contract,
and the payload slice — i.e. it tests the easy parts and the new seam, and leaves the hard,
being-rewritten parts untested, precisely where porting bugs will concentrate (the 658-line
timeseries panel with its imputation / beyond-tree / export logic, and the re-entrant
coordinator). Consider characterisation tests or at least a scripted manual-QA checklist for
these panels, and treat the screenshot gate as necessary-but-insufficient.

### M8. Sequencing defers every real unknown to the end

Phases 1–4 build all the infrastructure (new repo, ingestion, seam, bus). The genuine
unknowns — M1 (tip-level map linking), M2 (bus adequacy), M4 (PearTree dark + colours),
tree-in-a-narrow-rail layout — surface only in phases 5–7. The spec itself admits "worth an
early layout sanity check with the real tree" but the plan doesn't act on it.

**Recommend a Phase 0 spike:** render the *real* tree via PearTree in a *dark* rail, forced
onto the dashboard zone palette, wired to the *real* dashboard map at tip level — throwaway
code, no new repo. If PearTree can't be darkened/re-coloured, or the map can't link at tip
level, the design changes shape, and you want to learn that before standing up
`BDBV2026-Genomic_Epi` and the seam.

---

## Secondary concerns

### S1. Data-cadence staleness undercuts the "same numbers" goal

Case data rebuilds **6-hourly**; the genomic analysis rebuilds only "on a new phylodynamic
analysis" (rare). The tab will routinely show a tree from an **old** analysis beside fresh
case counts. Worse, per-zone sequence counts now have **two sources at different cadences**:
the tips baked into the (stale) tree vs. the canonical `genomic_sequence_count`
(`data_sources.py:2989`, rebuilt 6-hourly). These can visibly disagree — directly denting
Goal #3 ("same numbers"). Decide which source is authoritative for counts shown in the tab,
and **surface the analysis date** so users can see the tree's vintage.

### S2. The sample-distribution panel needs more than "canonical counts"

The distribution panel is the 658-line `timeseries-panel.js`; its "Imputed" toggle consumes
**onset-imputed linelist summaries** (`ituri_onset_imputed_summary.csv` etc.), not a simple
count. The spec asserts all case/status data comes "only" from `payload.py` and treats
"sampling counts" as solved — but it's not established that the payload carries the
onset-imputation series this panel needs. Confirm the canonical source for the "Imputed"
and "beyond-tree" series, or this panel is blocked on a new `payload.py` input the spec
doesn't budget for.

### S3. A whole new repo for ~150 KB of rarely-changing JSON — and a name collision

The producer scripts already live in a git repo:
`github.com/joetsui1994/BDBV2026_genomic_epi`. So the "new repo bootstrapping" risk is
**overstated** — this is extraction + move-to-`INRB-UMIE`-org + CI wiring, not greenfield.
But two things to fix:

- **Naming near-collision:** existing `BDBV2026_genomic_epi` (underscore, personal) vs
  proposed `BDBV2026-Genomic_Epi` (hyphen, org). Confusing; pick one and retire the other.
- The spec asserts the separate-repo decision ("mirrors `dashboard_plots`") without weighing
  the lighter alternative of a subdirectory in `BDBV2026-Data`. A new CI-secret-bearing repo
  is real ongoing maintenance; at least record why it beats a subdirectory.

### S4. PearTree provenance/licence is genuinely undocumented

The bundle self-describes as "peartree **dev** — single-file bundle," contains `mit` strings,
but there is **no LICENSE file, no version, and no attribution** anywhere in the source repo,
and it also bundles third-party code (e.g. `marked`). The open item "confirm licensing/
vendoring is fine to commit" is correct to raise — but note the provenance is currently
**unestablished**, which could block committing a 1.5 MB "dev" build into the dashboard.
Pin a versioned, licence-clear build before vendoring.

### S5. i18n interim state is ambiguous

The spec says don't ship "unreviewed machine French," but phase 6 shells `fr` keys and the
open item only "flags" French for review without blocking. So what ships between build and
native-speaker review — machine French, or an en-only tab? State the interim explicitly.

---

## Factual corrections (spec says X; code says Y)

1. **§Context:** the genomic page's entry point is **`build_page(payload)`**
   (`Scripts/pages/genomic_epidemiology.py:15`), not `render_page`. `render_page` is the
   shared chrome helper it delegates to (`chrome.py:453`).
2. **§2 / §Consistency anchor:** the per-zone key is **`genomic_sequence_count`**
   (`data_sources.py:2989`, `engine.js:1673`). The spec also writes **`genome_sequence_count`**
   — **no such key exists.** (`genome_sequence_markers` *is* correct, `payload.py:195`.)
3. **§4:** the "one genuinely new hook" framing oversells novelty — substantial per-view
   selection machinery already exists (`mapSelectedNom`, `epiSelectedNom`,
   `contextSelectedNom`, trends selection). What's absent is a *unified* bus. True but
   narrower than "new hook" implies (see M3).
4. **§2 delivery / §1 diagram:** "~150 KB total" is accurate for the five JSON/NEXUS products
   (~148 KB measured), but the tab also ships the **1.5 MB PearTree bundle**; the geojson is
   dropped in favour of the dashboard's canonical geometry. Frame the real page weight as
   ~1.65 MB, not 150 KB.
5. **§5 "Dropped":** `timeseries.json` is listed among the source app's data copies to drop —
   it's already a **dead/orphan file** (nothing fetches it; live series come from
   `status_confirmed.csv`). Harmless, but shows the data inventory wasn't fully walked.
6. **§5 "Ported … small pure helpers":** `node-info.js` is **not pure** — it calls
   `document.createElement`/`getElementById` (`node-info.js:15–19`). Its "keep unit tests
   where feasible" line won't apply the way the pure helpers do.
7. **§6 toggles:** the distribution panel's **"CSV"** control is a **CSV export/download
   modal** (`timeseries-panel.js:280–358`), not a data-source view mode. Minor, but the
   layout section presents it as a view toggle.
8. **§2 "Fail loudly … same discipline the source app uses today":** the *runtime* app does
   **not** fail loud — it silently passes unknown zones through; the fail-loud is a
   **build/CI** behaviour (`tree-lib.mjs:68`, `build-status.mjs:45–49`). Relevant to M6.

---

## Questions to resolve before "ready for implementation"

1. Does the dashboard carry `health_area` geometry/centroids? If not, is zone-level map
   linking an accepted regression? (M1)
2. What is the full selection-bus contract — tip-sets, toggle/deselect, view-transform
   coupling, date markers — and does it live in `engine.js` or stay genomic-local? (M2, M3)
3. Does `PearTree.embed` accept (a) inline tree text and (b) a custom per-zone colour map,
   and can its theme be forced dark without forking? (M4, M5)
4. Where does the alias-join + fail-loud run — producer or dashboard — and what is the
   intended build blast radius on an unmatched zone? (M6)
5. Which source is authoritative for per-zone sequence counts in the tab, and will the
   analysis date be surfaced? (S1)
6. Does `payload.py` already carry the onset-imputation series the distribution panel needs?
   (S2)
7. Is there a versioned, licence-clear PearTree build to vendor? (S4)

---

# Second pass — review of the revised spec (2026-08-12)

The spec was revised in direct response to the first pass. This pass reviews the
revision, re-checks its **new** claims against code/data, and revisits the two soft
spots called out at the end of round one. New evidence gathered: `tips.json`,
`meta.json`, the dashboard's onset data path, and the source app's deploy workflow.

## Verdict on the revision

A clear improvement. The Phase-0 gate is the right instinct, and most first-pass
findings are genuinely closed: M1 acknowledged (map port), M2/M3 (genomic-local
coordinator, no shared bus), M6 (join+fail-loud stay in producer), S1 (surface the
tree date), S3 (transfer not greenfield), S4/S5, and all eight factual corrections
are reflected. What remains is (a) a couple of new claims that the *data* undercuts,
(b) an internal contradiction in Decision 3, and (c) the two soft spots still soft.

## New findings (introduced or exposed by the revision)

### R1. Decision 2 over-corrected — the data is zone-level, so the map port it now commits to is largely unnecessary

Decision 2 (lines 59–63) swings from "don't port `map-panel.js`" to "**port** the
marker/grouping/linking logic … tip/area-level linking is preserved because
`tips.json` carries per-tip `lat`/`lon`/`health_zone`/`health_area`." The data says
otherwise:

- **`health_area` is populated 0 / 134 tips** (empty field) — the area branch of the
  source grouping is dead on current data.
- **Coordinates are zone-centroids**, not per-sample: every `health_zone` has exactly
  **one** distinct `(lat,lon)` across its tips. So markers are one-per-zone at the
  zone centroid.

So map linking is **entirely zone-level** in reality. Porting `map-panel.js`'s
area-else-zone grouping preserves granularity that the data does not contain. This
also corrects the first pass: my M1 framing ("you must port area-level markers")
was too strong — the honest conclusion from the data is that the gap is *narrower*
than either the original spec or my round-one review implied. The dashboard already
has a per-zone genome layer (`genomeLayer`, `engine.js:3301`) and zone selection;
the real work is small — make those markers clickable to select that zone's tip-set
and highlight tips. **Recommend:** reframe Decision 2 as zone-level linking reusing
the existing genome layer, and keep the area-grouping code only as clearly-labelled
dormant future-proofing (for if/when `tips` ever carry areas), not as a live
requirement.

### R2. Decision 3 contradicts itself: "transfer the repo" vs "producer-only" vs a live Pages site

The revision says both "**transfer** `joetsui1994/BDBV2026_genomic_epi` →
`INRB-UMIE/BDBV2026-Genomic_Epi`" (line 283) and "producer only (no app/Pages site)"
(line 139), and elsewhere "**extraction** + org move" (line 66). These are different
operations. The existing repo *is* the full standalone app — `src/`, `index.html`,
`dist/`, and an **active GitHub Pages deployment** (`.github/workflows/deploy.yml`,
`actions/deploy-pages`). A GitHub *transfer* moves the entire repo + history and
vacates the old location; you cannot transfer it and also keep it producer-only or
keep the public site alive. There's an unstated prerequisite decision:

- **Is the standalone public dashboard being retired?** If yes → transfer, then strip
  to producer (app + `deploy.yml` deleted). If no → leave the app repo intact and
  create a **fresh** producer repo cherry-picking `scripts/` + `data-raw/` + products
  (an *extraction*, not a transfer). Pick one; the spec currently reads as both.

### R3. S2 belongs in Phase 0 — but is more tractable than the spec fears

The spec parks the distribution panel's data as a Phase-2 task (lines 288–290) and a
blocking risk (lines 308–310: "not established … Phase 2 must source them or the panel
is blocked"). Two corrections:

- **It's not merely wiring.** The dashboard has onset data only as **pre-rendered
  SVGs** (`daily_onset_*.svg` via `onset_trends`, `payload.py:198`) and a
  report-date cumulative series (`confirmed_timeseries`) — neither is the numeric,
  splittable per-date onset series the interactive panel needs. "Beyond-tree" has no
  hook anywhere in `Scripts/`.
- **But the hard part already exists canonically.** The imputed-onset numeric data
  lands per-snapshot in the ingested repo:
  `BDBV2026-Processed_Sensitive_Data/outputs/<date>/dhis2_linelist_with_imputed_onset.csv`.
  So the imputation producer effectively already runs; the remaining work is
  **aggregate that linelist → per-date/per-zone counts in `payload.py`** + a new
  payload key + define/implement the **beyond-tree** join against the tree's sampling
  set (the one genuinely unhooked piece). Medium, not "stand up a new producer."

So the spec is slightly too pessimistic on availability, and slightly too relaxed on
timing. **Recommend:** add a Phase-0 data-availability checkpoint — does
`dhis2_linelist_with_imputed_onset.csv` give per-date/zone counts at the resolution
the panel needs, and how is "beyond-tree" defined? — so the third panel isn't found
blocked in Phase 2 after the repo/seam/hooks are already built.

## The two soft spots from round one — still soft

### R4. Phase 0 exit criteria have no written pass bar or pre-committed fallback

"Either all three feasible → proceed; or a documented design change folded back"
(lines 106–108) is still subjective. The sharpest case is PearTree: "decide fork vs.
relax" (line 92) defers a *scope-defining* choice — forking a 1.5 MB minified,
licence-unclear "dev" bundle vs. abandoning the flagship "one zone = one colour"
goal — to mid-spike. These have wildly different cost. **Pre-commit the fallback now**
(e.g. "if `embed` exposes no per-zone palette map, we relax to [tree keeps its own
palette + a documented legend], owner = X"), and give the spike an explicit
acceptance artifact (one dark screenshot: tree in the dashboard's zone colours, no
external font request). Then Phase 0 is genuinely go/no-go rather than "gather info,
re-decide later."

### R5. Goal #2 is now contingent on that unresolved spike

"A health zone is the same colour everywhere (subject to the PearTree spike, M4)"
(lines 37–38) makes a headline goal conditional on an open question. A goal that may
be unachievable should carry its fallback *in the goal*, not a parenthetical — tie it
to R4's pre-committed relaxation.

## Smaller / new

- **R6. "Minimal engine.js hooks / the only shared-code change" is optimistic**
  (lines 218–223). It's three capabilities — zone-selection subscribe/emit, add/remove
  an external layer, and **highlight-tips** — and highlight-tips leaks genomic marker
  styling into shared code, in tension with the "genomic-local coordinator" decision.
  Nail the boundary in Phase 0: `engine.js` exposes the raw map + generic
  layer-registration + a zone-select subscribe; *all* tip logic stays in `genomic.js`.
- **R7. The M3 ownership rule states the outcome, not the mechanism** (lines 220–223).
  Making the legacy per-view selection paths "inert here" likely requires branching the
  shared zone-polygon click handler on `activeView` (`engine.js` currently calls
  `setMapSelection` on zone click) — itself a shared-code change beyond "minimal," and
  adjacent to (though not breaking) the "existing tabs untouched" non-goal. Good that
  Phase 0 must verify it; the design should name the handler branch as expected work.
- **R8. S1 is well-supported (positive).** `meta.json` already carries `updated`
  (2026-07-28) distinct from `mostRecentDate` (2026-06-23) and `sourceTree`, and
  `build-tree.mjs` stamps it — so surfacing the tree's vintage is cheap. Minor:
  `updated` is a manually-stamped *build* date (defaults to today), not the BEAST-run
  date; label it "data build date," not "analysis date," to avoid overclaiming.

## Net

The revision is a real step forward and the Phase-0 gate is right. To make it a true
gate: (1) give the spike a written pass/fallback bar, especially the PearTree
fork-vs-relax decision (R4/R5); (2) fold two cheap reality-checks into Phase 0 — the
onset/beyond-tree data availability (R3) and the zone-level-vs-area map reality (R1);
and (3) resolve the Decision 3 transfer-vs-extract + standalone-site-retirement
question before Phase 1 (R2).
