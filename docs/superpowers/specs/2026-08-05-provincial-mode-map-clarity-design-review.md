# Critical review — Provincial-mode map clarity + clean province outlines

**Spec reviewed:** `docs/superpowers/specs/2026-08-05-provincial-mode-map-clarity-design.md`
**Reviewer date:** 2026-08-05
**Method:** Spec claims checked against the referenced code
(`Scripts/assets/engine.js`, `Scripts/common/data_sources.py`) and the installed
toolchain.

---

## Summary

The design is sound in intent and mostly lines up with the code it names. The
three moves — suppress zone strokes, redirect hover to the province outline, and
clean the union geometry — are each reasonable and target the stated problems.

However, there are a few concrete gaps between what the spec *claims* and what
the code actually does. The most important is that **the "national / health_zone
scopes are visually unchanged" guarantee is not true as written**, because
province outlines (and their sliver lines) render in those scopes too. There are
also two implementation ambiguities in `styleFn` and one factual slip in the
hover section that should be corrected before this is handed to an implementer.

Severity legend: 🔴 blocking / must resolve · 🟠 should address · 🟡 minor / nit.

> **Second-look addendum (below the original findings)** revises two items after a
> deeper read: it **retracts §2(b)** (no-data zones do *not* go invisible — the
> trends map coalesces missing values to `0`) and adds a **new 🔴 finding** — the
> geometry function doubles as the authoritative province roster, so the change's
> blast radius is wider than the spec's "Files touched" admits. Read the addendum
> alongside the original list.

---

## 🔴 1. The "national / health_zone visually unchanged" criterion is contradicted by the geometry change

**Spec:** Non-goals — *"No change to `national` or `health_zone` scopes"*; Success
criteria — *"`national` / `health_zone` scopes … are visually and behaviourally
unchanged."*

**Reality:** `setTrendsScope()` calls `showProvinceOutlines()` for **every** trends
scope, not just `province`:

```
engine.js:2417  if (activeView === "trends") {
engine.js:2418    geoLayer.setStyle(styleFn);
engine.js:2419    showProvinceOutlines();   // runs for national + health_zone + province
```

In `national` and `health_zone` scopes the outline layer renders with the
non-`provinceMode` style (`provinceOutlineStyle`, `engine.js:1949` — gold
`#9b7d4e`, weight 1, opacity 0.88). Those outlines are drawn from the **same**
`PAYLOAD.province_boundaries` geometry you are cleaning. The ~6,145 interior
sliver rings are currently stroked as faint gold internal lines in those scopes
too — so cleaning them *is* a visible change in `national` and `health_zone`,
not only in `province`.

**Why it matters:** The change is almost certainly an *improvement* everywhere,
but a success criterion that says "visually unchanged" will fail an honest
visual diff of the national/health_zone scopes. An implementer taking the
criterion literally will think they broke something.

**Recommendation:** Reword the non-goal and success criterion to: *"national /
health_zone **behaviour** unchanged; province outlines in those scopes lose the
same internal sliver lines (an intended side effect of the shared cleaned
geometry)."* Don't claim pixel-identity where the shared payload guarantees the
opposite.

---

## 🟠 2. `styleFn` stroke suppression is underspecified — and risks making no-data zones invisible

**Spec (Design §1):** *"In `styleFn`, when `activeView === "trends" &&
trendsScope === "province"`, suppress the per-zone stroke (`weight: 0`). Keep
`fillColor` / `fillOpacity` exactly as computed."*

Two problems:

**(a) There is no single "computed style" to amend.** `styleFn` has *four*
non-epi return points, each hard-coding `color`/`weight`
(`engine.js:1428`–`1453`): hub zone, epicenter zone, no-data zone, data zone. A
literal `weight: 0` requires either an early `province`-scope branch that returns
its own object, or post-processing every branch. The spec's phrasing ("keep
fillColor/fillOpacity as computed") implies a mutation step that doesn't exist
yet. Name the approach explicitly (recommended: compute the style as today, then
`if (activeView === "trends" && trendsScope === "province") style.weight = 0;`
before returning) so the implementer doesn't have to guess.

**(b) The no-data branch becomes fully invisible.** The no-data return is
already `{ color: "#111", weight: zoomWeight(0.35), fillOpacity: 0 }`
(`engine.js:1443`) — it renders as *border only*, no fill. Force `weight: 0` and
such a zone has neither fill nor stroke → it disappears entirely, leaving a blank
gap inside the province where the choropleth used to at least show a hairline
outline. This directly interacts with Goal #2 ("zone fills stay as-is") — fills
of *data* zones stay, but *no-data* zones lose their only visual presence.

**Recommendation:** Decide explicitly what a no-data zone should look like in
Provincial scope. Options: (i) accept the blank gap (fine if no-data zones are
rare/edge), (ii) keep a very faint fill or stroke for no-data zones only. Either
is defensible, but the spec must state it — right now the outcome is an accident
of the `weight: 0` blanket rule.

**(c) Hub / epicenter branches** also get `weight: 0` under a blanket rule. Confirm
whether hub/epicenter highlighting can even occur in trends/province scope
(depends on the active layer's matrix/epicenter config). If it can't, say so; if
it can, decide whether those emphasis borders should survive. Low risk, but
currently unaddressed.

---

## 🟠 3. Hover section makes a factual claim that the current code contradicts

**Spec (Design §2):** *"Once a province is selected, hover gives no feedback, **as
today**."*

**Reality:** Today, the trends `mouseover` handler paints the hovered zone amber
whenever the scope isn't national — **regardless of whether a province is
selected**:

```
engine.js:1614  if (activeView === "trends") {
engine.js:1615    if (trendsScope === "national") return;
engine.js:1616    e.target.setStyle({weight: 1.6, color: "#ffae42"});   // fires even when selected
```

So post-selection you currently *do* get amber zone feedback. The proposed change
(route through `setTrendsProvinceHover`, which is gated by `!trendsSelectedKey`,
`engine.js:2002`) **removes** that feedback. That's arguably the right call — amber
*zone* highlighting undercuts the "provinces are the unit" message — but the spec
sells it as "no change" when it's actually a deliberate behaviour change.

**Recommendation:** Rewrite as: *"Today, hovering a selected-province map still
flashes the amber zone highlight; this change intentionally drops that, so hover
gives no feedback once a province is selected."* Own the change instead of hiding
it under "as today." Also confirm this loss-of-hover-once-selected is genuinely
desired (an alternative is to keep highlighting the *outline* of the hovered
province even when another is selected — a small tweak to the gate).

---

## 🟡 4. Consider `coverage_union_all` as the primary de-sliver mechanism

**Spec (Design §3):** snap (`set_precision`) → `unary_union` → strip small holes.

This works, but note the codebase already contemplates GEOS coverage operations
(the `coverage_simplify` comment at `data_sources.py:705`). The slivers exist
precisely because the health-zone polygons are *meant* to be a coverage but don't
share exact edges. `shapely.coverage_union_all` is built for exactly this and
produces slivers-free unions without a magic hole-area threshold.

Caveats worth stating in the spec rather than discovering at implementation time:
- Installed shapely is **2.0.1** (`coverage_simplify` needs 2.1 per the existing
  comment — but `coverage_union` is available at 2.0). Verify the exact function
  and GEOS version on the build box before committing to it.
- `coverage_union` requires a *valid* coverage; the current gaps mean the input
  likely isn't one — so you may still need the `set_precision` snap *first*, then
  coverage-union. That's fine, but it means snap isn't optional.

**Recommendation:** At minimum, add a sentence acknowledging `coverage_union_all`
was considered and why the snap+union+strip path was chosen instead (e.g.
"input isn't a valid coverage; snap+strip is more robust to that"). If the real
reason is just "didn't know it existed," it's worth a quick spike — it could drop
the entire drop-small-holes helper and its tunable threshold.

---

## 🟡 5. The "no legitimate donut holes in DRC provinces" claim is asserted, not verified

**Spec (Design §3):** *"DRC provinces have no legitimate donut holes, so this is
safe."*

Probably true, but it's the load-bearing assumption behind stripping interior
rings, and it's stated without evidence. The threshold "safety net" mitigates it,
but the threshold is described as a constant "chosen during implementation" with
no stated method for picking it or fallback if a real hole and a large sliver
overlap in area.

**Recommendation:** Add a one-line verification step to the plan: after cleanup,
assert that the *largest* interior ring dropped is below some absolute area (and
log it), so a future geometry/source change that introduces a genuine hole trips
a loud failure instead of silently erasing it. This also gives the threshold a
principled value instead of a hand-tuned one.

---

## 🟡 6. `set_precision` + `make_valid` ordering unstated

The current code does `make_valid(shape(feat["geometry"]))` per zone
(`data_sources.py:736`). `set_precision` can itself yield invalid or empty
geometries. The spec says "snap each source zone geometry … before union" but
doesn't say whether snap happens before or after `make_valid`, or whether a
second validity pass is needed. Snapping an already-validated geometry can
re-introduce invalidity, so the safe order is usually `make_valid → set_precision
→ make_valid`. Worth pinning down so the implementer doesn't ship an occasional
empty/invalid province.

---

## Things the spec gets right (worth keeping)

- Reusing the existing `setTrendsProvinceHover → applyProvinceOutlineStyles`
  path instead of inventing new hover machinery — this genuinely matches click
  behaviour and is the low-risk choice (`engine.js:1977`, `2000`).
- Correctly identifying that `mouseout`/`zoomend` already route through
  `styleFn` / `resetStyle`, so suppressed strokes are inherited (verified at
  `engine.js:1636`, `1720`).
- Keeping a threshold rather than blindly stripping *all* interior rings — the
  right instinct even if the threshold needs a principled value (see §5).
- Scoping the change to `build_dashboard.py` and leaving the legacy
  `build_dashboard_public.py` alone, consistent with its header note.

---

## Second look — corrections and a new finding

A deeper pass through the trends data path (`recomputeTrendsMap` →
`getTrendsConfirmedAt`) and the payload builder (`common/payload.py`) changed my
read on two points.

### 🔴 7. `build_province_boundaries()` is also the authoritative province roster — the change's blast radius is wider than stated

This is the most important thing the first pass missed. The function's output is
not consumed only as map outlines. Its **feature set defines the list of
provinces** used elsewhere:

```
payload.py:103  province_boundaries = build_province_boundaries()
payload.py:107  province_names = sorted({ ...feat.properties.province... })   # <- derived from the features
payload.py:112  onset_trends = load_dashboard_plots(zone_noms=..., provinces=province_names)
```

and on the client:

```
engine.js:1766  (PAYLOAD.province_boundaries.features || []).forEach(...)   # builds TRENDS_LOCATION_INDEX
```

So if the new snap → union → strip pipeline ever drops a province — e.g. a
small province whose zones collapse to empty under `set_precision`, or a union
that `merged.is_empty`-filters out (`data_sources.py:744`) — that province
silently disappears from **plot generation and the Trends search dropdown**, not
just from the map. The spec frames §3 as a cosmetic outline cleanup and its
"Files touched" lists only the outline consumers; the real coupling is broader.

**Recommendation:** Add a hard invariant to the success criteria and to the code:
*"`build_province_boundaries()` returns exactly one feature per input province
(count unchanged, 26 in → 26 out), each retaining its `province` property."*
Assert it in the builder so a geometry regression fails loudly instead of quietly
shrinking the province list. This invariant matters more than the interior-ring
count the spec currently leads with.

### ↩︎ Retraction of §2(b) — no-data zones do *not* become invisible

My first pass warned that forcing `weight: 0` would make no-data zones vanish
(no fill + no stroke). That is **wrong for the trends map.** `recomputeTrendsMap`
fills `currentValues` via `getTrendsConfirmedAt`, which coalesces a missing
series to `0`:

```
engine.js:2743  if (!ts || !ts.by_nom) return 0;
engine.js:2745  if (!series || dateIdx < 0 || dateIdx >= series.length) return 0;
```

So in trends scope every zone has a numeric value, `has` in `styleFn` is always
true, and the `!has` no-data branch (`engine.js:1442`) never executes. Zero-case
zones take the data branch with a muted (but non-zero) fill opacity, so they stay
visible after the stroke is removed. **No invisible holes.** The §2(a) point
(there is no single "computed style" to amend — four hard-coded return branches,
so name the exact edit point) still stands.

### §2(c) refined — hub/epicenter borders *can* structurally fire in trends

Worth confirming rather than dismissing: `styleFn` reads `getLayer(layerSelect
.value)` even in trends view (it only early-returns for `epi-trends`, not
`trends`), and `isHubZone` / `isEpicenterZone` depend solely on that layer's
matrix/epicenter config (`engine.js:104`–`112`) — not on the active view. So if
`layerSelect` is left on an epicenter/matrix layer, those emphasis borders can
appear on the trends map, and a blanket `weight: 0` would strip them. Low
likelihood (trends normally pins confirmed-cases display), but the spec should
state the intended behaviour rather than leave it to a blanket rule.

---

## Third read — verifying the revised spec (commit `120904e`)

The spec now incorporates §§1–7. I re-checked each revision against the code
rather than taking the edits at face value. **Verdict: the revisions are correct
and the spec is essentially implementation-ready.** Every substantive point is
resolved, the §2b retraction is captured accurately, and the new province-count
invariant is framed exactly right (as the primary success gate for §3, above the
ring count). Remaining items are one factual fix and two precision refinements —
none blocking.

### 🟡 8. Three line-number citations in §1 point to the wrong place

The spec's other ~a dozen code citations are accurate (spot-checked: `104`–`113`,
`736`, `744`, `2002`, `2419`, `2741`, `2786`, `1614`–`1616` all land correctly).
But the cluster in §1 that describes `styleFn`'s body is off by ~35–45 lines:

| Spec says | Actually at | What's really at the cited line |
|-----------|-------------|--------------------------------|
| branches "roughly `engine.js:1461`–`1496`" | `styleFn` is **1422–1453** (hub 1428, epicenter 1435, `!has` 1442, data 1449) | 1461–1496 is `fmtLegend`/`fmt`/`updateLayerMeta` |
| "`!has` branch (`engine.js:1486`)" | **1442** | 1486 is inside `updateLayerMeta` |
| "reads `getLayer(layerSelect.value)` … (`engine.js:1460`)" | **1427** | 1460 is `fmtLegend` |

An implementer jumping to those lines lands in unrelated legend code. Likely the
author read a stale copy (or `build_dashboard_public.py`'s embedded engine.js) for
that one cluster. Cheap fix; worth doing so the "single `weight: 0` step" is
attached to the right branches.

### 🟠 9. The province-count invariant has a blind spot in exactly the direction §7 cares about

§3 defines the invariant as "one feature per **input** province," and "input"
means the keys of `by_province` — which is populated *after* the
`make_valid` / `geom_type` filter (`data_sources.py:737`–`738`). So a province
whose zones are **all** dropped by that earlier filter never enters `by_province`,
the assertion sees a matching count, and the province is still silently missing
from plots and search — the precise failure §7 was written to prevent, just
occurring one step upstream of `set_precision`.

**Recommendation:** anchor the invariant to the distinct `province` values in the
**raw source features** (before any geometry filtering), not to `by_province`
keys. Then *any* dropped province — filtered-out geometry or snap-collapsed union
— trips the build. This fully closes §7's loop.

### 🟡 10. Rounding is the last step after drop-holes — confirm the "~0 rings" check runs post-round

The pipeline orders drop-holes *before* the existing `simplify` /
coordinate-round steps (§3 step 3 + "before the existing simplify / coordinate-
round steps"), so `_round_coords(COORD_DECIMALS)` runs **after** holes are
stripped. Coordinate quantization can, in principle, re-introduce a degenerate
sub-threshold interior ring. Low risk, but the "interior-ring count drops to ~0"
criterion should be validated on the **final, post-round** geometry (or move
drop-holes to after rounding) so a quantization artifact can't slip past a check
run on the pre-round geometry.

### Confirmed accurate in the revision

- `requirements.txt:6` is `shapely>=2.0` — the §3 "pins only `shapely>=2.0`,
  coverage semantics vary by version" reasoning checks out.
- §2b retraction (no-data → `0` coalescing) matches `getTrendsConfirmedAt`
  (`engine.js:2743`, `2745`) exactly.
- §1's "hub/epicenter can fire in trends" note is right — `styleFn` reads
  `layerSelect.value` regardless of view; only `epi-trends` early-returns.
- The invariant using a dynamic count ("same count", not a hard-coded `26`) is
  the right call.

---

## Final review (spec commit `c18f8b6`)

**Verdict: the spec is ready to implement.** All ten review points (§§1–10) are
incorporated accurately, and I re-verified *every* code citation in the current
spec against the source — all correct now, including the newly-changed
`styleFn:1422–1454`, hub/epicenter/no-data/data branch lines, `getLayer:1427`,
`setTrendsScope:2378` / `showProvinceOutlines:2385`, `data_sources.py:736/739/744`,
`payload.py:107`, and `COORD_DECIMALS = 5`. The §8 line-number defect is fixed,
the §9 invariant is correctly re-anchored to the raw source province set, and §10
correctly pins the ring check to post-round geometry. No blocking issues remain.

The items below are genuinely new — untouched by the first three passes — and are
polish, not blockers. Only §11 has real teeth.

### 🟠 11. The cleanup strips interior *rings* but not detached sliver *polygons*

Every part of the design targets interior rings (holes). But `unary_union` of the
snapped zones can also leave **tiny detached exterior polygons** — a stray
micro-fragment where two zone edges cross rather than coincide. The strip-holes
helper (§3 step 3) rebuilds "exterior ring + large interior rings" per part, so a
spurious *small part* survives intact: it keeps its own exterior ring and is drawn.

Crucially, this slips **both** existing guards:
- The province-count invariant (§9) counts *features per province*, and a spurious
  part rides inside that province's single MultiPolygon feature — count still
  matches, assertion passes.
- The interior-ring count (§10 / success criteria) is ~0 — a detached part has no
  hole, so the ring check is clean while a visible sliver polygon remains.

**Complication:** small detached parts are not always junk — a province with a
genuine lake island or river-island exclave legitimately unions to a MultiPolygon.
So this can't be a blind "drop all small parts."

**Recommendation:** State explicitly whether the union can produce spurious
exterior slivers. Either (a) confirm empirically it produces none (add a check:
count MultiPolygon parts below the same area threshold and assert 0, logging any),
or (b) if it does, extend the helper to drop sub-threshold *parts* as well as
rings — guarded by the same "no legitimate small islands in DRC provinces"
assumption, made explicit and self-checked the way §5 handles holes.

### 🟡 12. `set_precision` also moves the *exterior* boundary — pin the grid-size relationship

Snapping to a grid perturbs every vertex, including the province's outer edge, by
up to ~half a grid cell — the same operation that closes internal slivers also
nudges the exterior. The "exterior outline unchanged" criterion therefore means
*visually* unchanged at display scale, not byte-identical. To keep that true, the
grid size needs a stated relationship to the existing constants: comfortably below
`SIMPLIFY_TOL = 0.001` (~110 m; else snap fights simplify) and at/above the
`COORD_DECIMALS = 5` quantum (~1 m; else rounding erases the snap). The spec calls
the grid "tunable" but gives no bracket — name the `[1e-5, <1e-3]` window so it
isn't tuned blind.

### 🟡 13. Threshold/bound units are square degrees (EPSG:4326) — say so

Geometry is in lon/lat degrees, so both the sliver-drop threshold and the §5
"absolute bound" on the largest dropped ring are in **square degrees**, not m².
Harmless but easy to mis-set an eyeballed constant by orders of magnitude if an
implementer assumes metric. One clarifying word ("in the layer's native degrees")
prevents it. (DRC straddles the equator, so a degree² is reasonably uniform across
provinces — no reprojection needed.)

### Confirmed strength — hover coverage survives the stroke suppression

Worth recording as a *positive*: setting `weight: 0` removes only the stroke;
zone fills keep `fillOpacity > 0` (data zones use `dataOpacity`, zero-case zones
`mutedOpacity ≈ 0.48–0.55`, and no-data never fires — §1). In Leaflet/SVG a path
with a non-zero fill still receives pointer events, so every province stays fully
covered by hit-testable zone fills and the §2 province-hover works everywhere
inside a province. There is no hover dead-zone. (This would only break if some
trends zone had `fillOpacity: 0` — which the §1 analysis rules out.)

---

## Suggested pre-implementation checklist

1. Fix the national/health_zone "visually unchanged" wording (§1). **Blocking** —
   it's a false guarantee.
2. Add the province-count invariant (26 in → 26 out, `province` property kept) to
   the success criteria and assert it in the builder (§7). **Blocking** — silent
   province loss breaks plots + search, not just outlines.
3. Name the concrete `styleFn` edit point — four hard-coded return branches, no
   single "computed style" to amend (§2a). No-data-invisibility is *not* a
   concern (§2b retracted); hub/epicenter behaviour should be stated (§2c).
4. Correct the "as today" hover claim and confirm the intended post-selection
   behaviour (§3).
5. Decide `coverage_union_all` vs. snap+strip and record why (§4).
6. Add a max-dropped-ring-area assertion to protect the donut-hole assumption (§5).
7. Pin the `make_valid`/`set_precision` ordering (§6).

**After third read (spec now addresses §§1–7; these are the only open items):**

8. Fix the three §1 line-number citations — `1461–1496`/`1486`/`1460` should be
   `~1428–1453`/`1442`/`1427` (§8). Factual, cheap.
9. Anchor the province-count invariant to the raw source province set, not
   `by_province` keys, so a province lost at the earlier geometry filter also
   trips the assertion (§9).
10. Ensure the "~0 interior rings" check runs on the final post-round geometry
    (§10).

**After final read (spec addresses §§1–10; all citations verified correct):**

11. Handle (or rule out) detached sliver *polygons*, which slip both the
    province-count and interior-ring guards (§11). The one item with real teeth.
12. Bracket the `set_precision` grid size against `SIMPLIFY_TOL`/`COORD_DECIMALS`
    (§12).
13. Note that threshold/bound units are square degrees (§13).
