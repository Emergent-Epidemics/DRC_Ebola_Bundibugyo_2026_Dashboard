# Genomic Epidemiology tab — Phase 0 spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De-risk the three design-invalidating unknowns (PearTree dark+recolour+delivery, zone-level map linking, coordinator contract) plus the onset-data availability check, before any repo/seam/panel work.

**Architecture:** A single throwaway, self-contained spike under `spike/genomic-phase0/` (git-ignored) — a static HTML page loading the real PearTree bundle, the real genomic data products, Leaflet, and the real health-zone geometry. It answers each Phase-0 pass bar from the spec by observation, and records the verdicts + folded-back design changes in a committed findings doc. **No production code, no new repo, no build-system change.**

**Tech Stack:** static HTML/JS/CSS; PearTree `window.PearTreeEmbed` global (1.5 MB bundle); Leaflet (CDN, spike-only); `python3.9 -m http.server` to serve; `python3.9` for the CSV aggregation check.

**Spike nature (read first):** This is exploratory. Tasks are *build-to-learn*, not TDD — each ends by writing a verdict against a written pass bar. The only committed artifact is the findings doc; all `spike/` code is throwaway and git-ignored. Where the spike adapts existing source-app logic, read the reference file rather than reinventing:
- Tree embed config: `/Users/user/Documents/work/DRC-Ebola-genomic-epi-public/src/tree-panel.js`
- Map markers/linking: `.../src/map-panel.js`
- Coordinator contract: `.../src/coordinator.js`
- Distribution series shape: `.../src/timeseries-panel.js`

**Reference paths (constants used throughout):**
- `SRC_DIST=/Users/user/Documents/work/DRC-Ebola-genomic-epi-public/dist`
- `SENS=/Users/user/Documents/work/BDBV2026-Processed_Sensitive_Data` (sibling; latest onset snapshot `outputs/2026-08-06/`)
- Spike root: `/Users/user/Documents/work/BDBV2026-Epidemic_Dashboard/spike/genomic-phase0`

---

## File structure

Everything under `spike/genomic-phase0/` (git-ignored), except the findings doc:

- `spike/genomic-phase0/index.html` — the spike page: dark right rail (tree / stub-Ne / stub-distribution) + a Leaflet map, loads the bundle + data.
- `spike/genomic-phase0/spike.js` — all spike logic: embed the tree, apply dark + zone palette, wire map↔tree linking, the coordinator state machine, the view-transform coupling.
- `spike/genomic-phase0/spike.css` — dark rail styling + `--pt-*` override attempts.
- `spike/genomic-phase0/zone-colours.json` — generated categorical `health_zone → hex` palette (the shared identity palette the dashboard lacks).
- `spike/genomic-phase0/vendor/peartree.bundle.min.js` — copied bundle.
- `spike/genomic-phase0/data/*` — copied real products + geometry.
- `spike/genomic-phase0/onset_check.py` — the S2/R3 CSV-availability probe.
- `docs/superpowers/specs/2026-08-12-genomic-epidemiology-tab-phase0-findings.md` — **committed** verdicts + design changes to fold into the spec.

Task order: **Task 8 (onset data) is independent** and can run any time. Tasks 1→7 are sequential (each builds on the spike page). Task 9 consolidates.

---

## Task 1: Scaffold the spike page and render the real tree (baseline)

**Files:**
- Create: `spike/genomic-phase0/` (dir), `.gitignore` entry
- Create: `spike/genomic-phase0/index.html`, `spike/genomic-phase0/spike.js`, `spike/genomic-phase0/spike.css`
- Create (copied): `spike/genomic-phase0/vendor/peartree.bundle.min.js`, `spike/genomic-phase0/data/*`
- Create (generated): `spike/genomic-phase0/zone-colours.json`

- [ ] **Step 1: Create the dir and git-ignore the spike tree**

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard
mkdir -p spike/genomic-phase0/vendor spike/genomic-phase0/data
printf '\n# Throwaway Phase-0 spike (see docs/superpowers/plans/2026-08-12-genomic-epi-phase0-spike.md)\nspike/\n' >> .gitignore
```

- [ ] **Step 2: Copy the real bundle, data products, and geometry into the spike**

```bash
SRC_DIST=/Users/user/Documents/work/DRC-Ebola-genomic-epi-public/dist
cp "$SRC_DIST/peartree.bundle.min.js" spike/genomic-phase0/vendor/
cp "$SRC_DIST"/data/ituri-tree.ptree "$SRC_DIST"/data/ituri-tips.json \
   "$SRC_DIST"/data/ituri-meta.json "$SRC_DIST"/data/skygrid.json \
   "$SRC_DIST"/data/exponential.json "$SRC_DIST"/data/health-zones.geojson \
   spike/genomic-phase0/data/
ls -la spike/genomic-phase0/data spike/genomic-phase0/vendor
```
Expected: 6 data files + the bundle present.

- [ ] **Step 3: Generate the categorical zone→colour palette**

Run:
```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard/spike/genomic-phase0
python3.9 - <<'PY'
import json
tips=json.load(open('data/ituri-tips.json'))
zones=sorted({t['health_zone'] for t in tips if t.get('health_zone')})
# 16 distinct zones; a fixed categorical palette (colour-blind-friendly, extend if needed)
PAL=["#4E79A7","#F28E2B","#E15759","#76B7B2","#59A14F","#EDC948","#B07AA1","#FF9DA7",
     "#9C755F","#BAB0AC","#8CD17D","#B6992D","#86BCB6","#D37295","#FABFD2","#79706E"]
cmap={z:PAL[i%len(PAL)] for i,z in enumerate(zones)}
json.dump(cmap, open('zone-colours.json','w'), indent=2, ensure_ascii=False)
print("zones:",len(zones)); print(json.dumps(cmap,ensure_ascii=False,indent=2))
PY
```
Expected: `zones: 16` and a written `zone-colours.json`.

- [ ] **Step 4: Write the minimal spike page (`index.html`)**

```html
<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Genomic Phase-0 spike</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<link rel="stylesheet" href="spike.css">
<!-- PearTree bundle: exposes window.PearTreeEmbed before the module runs -->
<script src="vendor/peartree.bundle.min.js"></script>
</head><body>
<div id="app">
  <div id="map"></div>
  <div id="rail">
    <section id="tree-card"><h3>Phylogeny</h3><div id="tree" class="body"></div></section>
    <section id="ne-card"><h3>Effective population size (stub)</h3><div id="ne" class="body"></div></section>
    <section id="dist-card"><h3>Sample distribution (stub)</h3><div id="dist" class="body"></div></section>
  </div>
</div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script type="module" src="spike.js"></script>
</body></html>
```

- [ ] **Step 5: Write the dark rail CSS (`spike.css`)**

```css
:root { --bg:#161616; --panel:#1f1f1f; --ink:#e8e8e8; --muted:#9a9a9a; --border:#333; }
* { box-sizing:border-box; }
html,body,#app { height:100%; margin:0; }
body { background:var(--bg); color:var(--ink); font:13px/1.4 system-ui, sans-serif; }
#app { display:flex; }
#map { flex:1; min-width:0; }
#rail { width:420px; background:var(--bg); border-left:1px solid var(--border);
        display:flex; flex-direction:column; overflow:auto; }
#rail section { border-bottom:1px solid var(--border); display:flex; flex-direction:column; }
#rail h3 { margin:0; padding:6px 10px; font-size:12px; color:var(--muted);
           background:var(--panel); border-bottom:1px solid var(--border); }
#rail .body { padding:0; min-height:180px; }
#tree-card { flex:2; } #tree { flex:1; min-height:320px; }
#ne-card, #dist-card { flex:1; }
/* Attempt to retint PearTree's interface variables toward dark (Task 2 refines). */
#tree { --pt-bg:#1b1b1b; --pt-fg:#e8e8e8; }
```

- [ ] **Step 6: Write the baseline embed (`spike.js`) — render the tree only**

Read `tree-panel.js` for the full option set; baseline mirrors its embed call:
```js
const cmap = await fetch('zone-colours.json').then(r => r.json());
const meta = await fetch('data/ituri-meta.json').then(r => r.json());

if (!window.PearTreeEmbed) throw new Error('PearTreeEmbed missing — bundle not loaded');
const tree = await window.PearTreeEmbed.embed({
  container: 'tree',
  treeUrl: 'data/ituri-tree.ptree',   // Task 5 tests inline instead
  filename: 'Ituri.ptree',
  height: '100%',
  ui: { theme: 'light', toolbarSections: ['fileOps','nodeInfo','zoom','filter','panels'] },
  settings: {
    theme: "O'Toole",
    tipLabelShow: 'health_zone',
    tipColourBy: 'health_zone',
    axisShow: 'time', axisDateAnnotation: 'date', axisDateFormat: 'dd MMM yyyy',
    axisMajorInterval: 'auto', axisMinorInterval: 'auto',
    axisMajorLabelFormat: 'component', axisMinorLabelFormat: 'component',
    paddingLeft: '20', paddingRight: '20', rootStubLength: '0', rootStemPct: '0',
  },
});
tree.onTreeLoad(() => tree.fitToWindow());
window.__spikeTree = tree;      // expose for console probing in later tasks
console.log('[spike] tree embedded');
```

- [ ] **Step 7: Serve and confirm the tree renders**

Run:
```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard/spike/genomic-phase0
python3.9 -m http.server 8099
```
Open `http://localhost:8099/`. **Pass bar:** the phylogeny renders in the right rail with time axis and zone tip-labels; console shows `[spike] tree embedded` and no bundle-load error. Record the result (screenshot `baseline.png`).

- [ ] **Step 8: Start the findings doc (verdict log)**

Create `docs/superpowers/specs/2026-08-12-genomic-epidemiology-tab-phase0-findings.md` with a heading per Phase-0 item and a "Task 1: baseline — PASS/FAIL + note" line. (Committed at the end, Task 9.)

---

## Task 2: PearTree dark theme without forking

**Files:** Modify `spike/genomic-phase0/spike.js`, `spike.css`

- [ ] **Step 1: Enumerate what the embed API exposes for theming**

In the browser console (with the spike page open):
```js
const t = window.__spikeTree;
console.log('applySettings?', typeof t.applySettings, 'applyTheme?', typeof t.applyTheme);
// Probe for a dark built-in theme and settable interface colours:
console.log(Object.keys(t));
```
Record the available theme/appearance hooks (e.g. a dark built-in `theme`, or settable `--pt-*` vars / background/foreground settings).

- [ ] **Step 2: Attempt dark via the API + CSS variables**

Try, in order, whichever the API supports (adapt from Step-1 findings):
```js
// (a) a built-in dark theme if one exists:
try { t.applyTheme && t.applyTheme('Nord'); } catch(e){ console.log('no dark builtin', e); }
// (b) settable interface colours:
try { t.applySettings({ backgroundColor:'#1b1b1b', axisColor:'#c9c9c9', tipLabelColor:'#e8e8e8' }); } catch(e){ console.log(e); }
```
And in `spike.css`, push the `#tree { --pt-* }` overrides toward dark for anything the API can't reach.

- [ ] **Step 3: Verdict**

**Pass bar:** the tree canvas background + axis + labels read as dark and legible **without editing the bundle**. Record in findings: `dark = ACHIEVABLE_VIA_API | ACHIEVABLE_VIA_CSS | REQUIRES_FORK`, with the exact hooks used. If REQUIRES_FORK, note it (the fallback is not to fork — see Goal #2 — so a partial-dark + documented compromise is the outcome).

---

## Task 3: Recolour tips to the categorical zone palette (or invoke the fallback)

**Files:** Modify `spike/genomic-phase0/spike.js`

- [ ] **Step 1: Probe for a per-category colour-map hook**

In console:
```js
const t = window.__spikeTree;
// Look for an annotation-palette setter (names vary): try the likely candidates.
['setAnnotationPalette','setColourMap','setColorMap','setCategoryColours','applyPalette']
  .forEach(fn => console.log(fn, typeof t[fn]));
```
Record which (if any) exists.

- [ ] **Step 2: If a hook exists — apply `zone-colours.json`**

```js
const cmap = await fetch('zone-colours.json').then(r => r.json());
// Use whichever setter Step 1 found, e.g.:
t.setAnnotationPalette && t.setAnnotationPalette('health_zone', cmap);
```
**Pass bar (goal met):** tips show the dashboard-side categorical palette (a given zone is its `zone-colours.json` colour). Screenshot `recolour-pass.png`.

- [ ] **Step 3: If NO hook exists — invoke the pre-committed fallback**

Do NOT fork. Leave PearTree's own categorical palette on the tips, and render an **external zone-colour legend** in the tree card from `zone-colours.json` for the *panels'* use (Ne/distribution will use `zone-colours.json`; the tree keeps its own but stays internally consistent):
```js
const cmap = await fetch('zone-colours.json').then(r => r.json());
const legend = document.createElement('div'); legend.className='zone-legend';
legend.innerHTML = Object.entries(cmap)
  .map(([z,c]) => `<span><i style="background:${c}"></i>${z}</span>`).join('');
document.getElementById('tree-card').appendChild(legend);
```
**Pass bar (fallback):** a legible zone legend accompanies the tree; the SVG panels can consume `zone-colours.json`. Screenshot `recolour-fallback.png`.

- [ ] **Step 4: Verdict**

Record: `recolour = PER_ZONE_MAP_SUPPORTED | FALLBACK_LEGEND`, with the hook name if supported. This decides the Goal #2 wording in the spec.

---

## Task 4: Eliminate the external Google-Fonts request

**Files:** Modify `spike/genomic-phase0/index.html` and/or a small `vendor/` tweak

- [ ] **Step 1: Confirm the request exists**

With the spike page open, in DevTools Network panel filter `fonts.googleapis` / `fonts.gstatic`. Record whether the bundle fires it. (The review found a `@import` in the bundle head.)

- [ ] **Step 2: Neutralize it without forking the bundle**

Add a spike-level guard in `index.html` `<head>` BEFORE the bundle script — a `<style>` cannot block an `@import` inside injected CSS, so test the CSP approach:
```html
<meta http-equiv="Content-Security-Policy" content="font-src 'self' data:; style-src 'self' 'unsafe-inline'">
```
Reload; re-check Network. If the CSP blocks the font fetch and the tree still renders acceptably with a system fallback, that is the production posture (the dashboard page can carry the same `font-src`).

- [ ] **Step 3: Verdict**

**Pass bar:** no request to `fonts.googleapis.com` / `fonts.gstatic.com` in Network, tree still legible. Record: `google_fonts = BLOCKED_VIA_CSP | NEEDS_BUNDLE_PATCH | NOT_PRESENT`.

---

## Task 5: Tree delivery — inline text vs URL

**Files:** Modify `spike/genomic-phase0/spike.js`

- [ ] **Step 1: Try embedding from an inline string**

```js
const nexus = await fetch('data/ituri-tree.ptree').then(r => r.text());
// Probe the documented inputs the embed accepts besides treeUrl:
const t2 = await window.PearTreeEmbed.embed({
  container: 'tree', filename: 'Ituri.ptree', height: '100%',
  treeText: nexus,             // candidate 1
  // tree: nexus,              // candidate 2 (try if treeText ignored)
  ui:{theme:'light'}, settings:{ theme:"O'Toole", tipColourBy:'health_zone' },
}).catch(e => (console.log('inline failed:', e), null));
console.log('inline embed:', !!t2);
```
Try the alternate key names if the first is ignored (read the bundle's `embed` signature via `window.PearTreeEmbed.embed.toString().slice(0,600)` for hints).

- [ ] **Step 2: Verdict**

**Pass bar:** determine `tree_delivery = INLINE_TEXT_OK | URL_ONLY`. If INLINE_TEXT_OK → the tree can be an inline payload value; if URL_ONLY → it must ship as a page-scoped fetched asset. Record; this fixes the §2 "Delivery" open choice in the spec.

---

## Task 6: Zone-level map linking on a real Leaflet map

**Files:** Modify `spike/genomic-phase0/spike.js`

- [ ] **Step 1: Draw the map with zone polygons + per-zone genome markers**

Read `map-panel.js` for reference. Group tips by `health_zone` (all at one centroid — confirmed), one marker per zone sized by count:
```js
const tips = await fetch('data/ituri-tips.json').then(r => r.json());
const geo  = await fetch('data/health-zones.geojson').then(r => r.json());
const map = L.map('map', { zoomControl:false }).setView([1.6, 29.8], 7);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
  {subdomains:'abcd', maxZoom:19}).addTo(map);

const byZone = new Map();                       // zone -> {lat,lon,ids:[]}
for (const t of tips) {
  if (t.lat==null || t.lon==null) continue;
  const g = byZone.get(t.health_zone) || {lat:t.lat, lon:t.lon, ids:[]};
  g.ids.push(t.id); byZone.set(t.health_zone, g);
}
const markers = new Map();
for (const [zone,g] of byZone) {
  const m = L.circleMarker([g.lat,g.lon],
    {radius:5+2*Math.sqrt(g.ids.length), color:'#f2c84b', weight:1, fillOpacity:.6})
    .addTo(map).bindTooltip(`${zone} · ${g.ids.length}`);
  m.on('click', () => selectZone(zone));
  markers.set(zone, m);
}
```

- [ ] **Step 2: Wire marker/polygon click → highlight that zone's tips in the tree**

```js
function highlightTips(ids){ (ids||[]).forEach((nm,i)=>window.__spikeTree.selectByAnnotation('accession', nm, {additive:i>0})); }
function clearTree(){ window.__spikeTree.setSelection([]); }
function selectZone(zone){
  clearTree();
  const g = byZone.get(zone);
  if (g) highlightTips(g.ids);
  console.log('[spike] selected zone', zone, g ? g.ids.length : 0, 'tips');
}
```
Add zone polygons from `geo` (match `properties.Nom` to the tip zones) with a click that calls `selectZone(Nom)` — proving the polygon path works even for zones with no tips.

- [ ] **Step 3: Verdict**

**Pass bar:** clicking a genome marker highlights that zone's tips in the tree; clicking the matching polygon does the same; re-click clears (Task 7 adds toggle). Confirm this needed only: clickable markers + `selectByAnnotation` + a polygon click handler — i.e. an `activeView`-style branch, no per-sample geometry. Screenshot `map-link.png`. Record `map_linking = ZONE_LEVEL_OK | ISSUES(...)`.

---

## Task 7: The coordinator contract (toggle + view-transform + date markers)

**Files:** Modify `spike/genomic-phase0/spike.js`

- [ ] **Step 1: Port the state machine (tip-set OR zone, click-again-to-deselect)**

Read `coordinator.js`; reproduce its `activeKey` + `programmatic`/`zoneSelecting` logic in the spike:
```js
let activeKey=null, programmatic=false;
function clearAll(){ activeKey=null; programmatic=true; clearTree(); programmatic=false; distMarkers([]); }
function selectZone(zone){                    // replaces Task 6's simpler version
  const key='zone:'+zone.toUpperCase();
  if (key===activeKey){ clearAll(); return; } // click-again-to-deselect
  activeKey=key; const g=byZone.get(zone);
  programmatic=true; clearTree(); if(g) highlightTips(g.ids); programmatic=false;
}
window.__spikeTree.onNodeSelect(({selected})=>{  // tree click → date markers + (if direct) drop toggle target
  if(!programmatic) activeKey=null;
  const dates=[...new Set(selected.map(n=>n.annotations?.date).filter(Boolean))];
  distMarkers(dates);
});
```

- [ ] **Step 2: Couple tree view-transform → distribution x-axis (non-selection channel)**

```js
function setDistTransform(vt){ /* draw an x-axis in #dist that maps root..mostRecent using vt.offsetX/scaleX/maxX */
  document.getElementById('dist').dataset.vt = JSON.stringify(vt||{}); }
const seed = window.__spikeTree.getViewTransform?.(); if (seed) setDistTransform(seed);
window.__spikeTree.onViewChange(vt => setDistTransform(vt));
```
Render a trivial tick strip in `#dist` that visibly shifts when you pan/zoom the tree, to prove the coupling fires.

- [ ] **Step 3: Date-marker fan-out stub**

```js
function distMarkers(dates){ document.getElementById('dist').dataset.marks = (dates||[]).join(','); /* draw vertical ticks */ }
```

- [ ] **Step 4: Verdict**

**Pass bar:** (a) clicking the same zone/marker twice deselects; (b) panning/zooming the tree visibly moves the distribution x-axis strip; (c) a tree selection writes sequence-date markers to the stub. Screenshot/screencap `coordinator.gif` or note. Record `coordinator = REPRODUCIBLE_LOCALLY | ISSUES(...)`.

---

## Task 8: Onset / beyond-tree data availability (independent)

**Files:** Create `spike/genomic-phase0/onset_check.py`

- [ ] **Step 1: Inspect the canonical imputed-onset linelist**

```bash
SENS=/Users/user/Documents/work/BDBV2026-Processed_Sensitive_Data
head -3 "$SENS/outputs/2026-08-06/dhis2_linelist_with_imputed_onset.csv"
python3.9 -c "import csv,sys; r=csv.DictReader(open('$SENS/outputs/2026-08-06/dhis2_linelist_with_imputed_onset.csv')); print(r.fieldnames)"
```
Record the columns (need: a date-of-onset field, an imputed-flag or imputed-vs-observed distinction, and a health-zone field).

- [ ] **Step 2: Aggregate to the panel's series and check resolution**

Write `onset_check.py` that produces per-date, per-zone `{observed, imputed}` counts and prints coverage (date range, zones, any rows missing zone/date):
```python
import csv, collections, sys
PATH="/Users/user/Documents/work/BDBV2026-Processed_Sensitive_Data/outputs/2026-08-06/dhis2_linelist_with_imputed_onset.csv"
rows=list(csv.DictReader(open(PATH)))
print("cols:", rows[0].keys()); 
# EDIT the field names below to match Step-1 output:
DATE, ZONE, IMPUTED = "onset_date", "health_zone", "onset_imputed"
agg=collections.defaultdict(lambda:{"observed":0,"imputed":0})
miss=0
for r in rows:
    d, z = r.get(DATE), r.get(ZONE)
    if not d or not z: miss+=1; continue
    agg[(d,z)]["imputed" if str(r.get(IMPUTED,"")).lower() in ("1","true","yes") else "observed"]+=1
print("rows:",len(rows),"missing date/zone:",miss,"date×zone cells:",len(agg))
print("sample:", list(agg.items())[:3])
```
Run: `python3.9 spike/genomic-phase0/onset_check.py`

- [ ] **Step 3: Define "beyond-tree" concretely**

Beyond-tree = samples/cases dated after the tree's latest tip (`meta.json.mostRecentDate`, `2026-06-23`). Write the rule down (e.g. "onset series beyond `mostRecentDate` is drawn in the beyond-tree strip"). Confirm the linelist has rows past that date.

- [ ] **Step 4: Verdict**

**Pass bar:** a written mapping `dhis2_linelist_with_imputed_onset.csv → per-date/zone {observed,imputed}` at daily resolution, plus a beyond-tree definition. Record `onset_data = AVAILABLE(mapping...) | GAP(...)`. If GAP, that reshapes Phase 2.

---

## Task 9: Consolidate findings and decide go/no-go

**Files:** Modify `docs/superpowers/specs/2026-08-12-genomic-epidemiology-tab-phase0-findings.md`; possibly modify the spec

- [ ] **Step 1: Fill the findings doc**

For each of the four Phase-0 items, write the verdict + evidence (screenshots under `spike/genomic-phase0/`), using the recorded flags: `dark=…`, `recolour=…`, `google_fonts=…`, `tree_delivery=…`, `map_linking=…`, `coordinator=…`, `onset_data=…`.

- [ ] **Step 2: List the spec changes each verdict forces**

Concretely, e.g.: Goal #2 wording per `recolour`; §2 Delivery per `tree_delivery`; the CSP `font-src` posture per `google_fonts`; the zone-identity-palette clarification (the dashboard has none — a new shared categorical palette is introduced); any onset reshaping.

- [ ] **Step 3: Go/no-go**

State the decision: **proceed to Phase 1** (all pass bars met, using pre-committed fallbacks) **or** a named design change to fold into the spec first.

- [ ] **Step 4: Commit only the findings doc (spike stays git-ignored)**

```bash
cd /Users/user/Documents/work/BDBV2026-Epidemic_Dashboard
git add docs/superpowers/specs/2026-08-12-genomic-epidemiology-tab-phase0-findings.md
git status --short          # confirm nothing under spike/ is staged
git commit -m "Genomic tab Phase 0 spike: findings and go/no-go"
```

- [ ] **Step 5: If the spec needs changes, apply them and commit separately**

If Step 2 forces spec edits, make them in `2026-08-12-genomic-epidemiology-tab-design.md` and commit as `Update genomic tab spec from Phase 0 findings`.

---

## Notes / expected outcomes

- The single riskiest verdict is **Task 3 (recolour)**; the plan pre-commits the no-fork fallback, so a `FALLBACK_LEGEND` result is still a PASS for proceeding — it only softens Goal #2.
- **Task 4 (fonts)** and **Task 5 (delivery)** are cheap and decide the page's CSP/offline posture and the tree-payload mechanism, respectively — both needed before Phase 2/3.
- **Task 8** is independent; run it first if the browser tasks stall, so the onset reshaping (the likeliest Phase-2 surprise) is known early.
