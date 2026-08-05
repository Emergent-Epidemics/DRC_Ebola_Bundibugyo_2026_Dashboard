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

## Suggested pre-implementation checklist

1. Fix the national/health_zone "visually unchanged" wording (§1). **Blocking** —
   it's a false guarantee.
2. Specify the no-data-zone appearance and the concrete `styleFn` edit point (§2).
3. Correct the "as today" hover claim and confirm the intended post-selection
   behaviour (§3).
4. Decide `coverage_union_all` vs. snap+strip and record why (§4).
5. Add a max-dropped-ring-area assertion to protect the donut-hole assumption (§5).
6. Pin the `make_valid`/`set_precision` ordering (§6).
