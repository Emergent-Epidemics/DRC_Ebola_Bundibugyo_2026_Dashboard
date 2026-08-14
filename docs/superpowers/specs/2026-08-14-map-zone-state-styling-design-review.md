# Critical review — Harmonised zone state styling on the outbreak map

**Reviewing:** `docs/superpowers/specs/2026-08-14-map-zone-state-styling-design.md`
**Date:** 2026-08-14
**Reviewer:** engineering review (code-verified against `Scripts/assets/engine.js` @ `soft-nav-cached-payload`)

---

## Verdict

The problem statement is accurate and the central architectural call — **move selection out of
`styleFn` and into its own pane** — is the right one. It converts requirement 4 from an ordering
invariant maintained at nine call sites into a property of the render tree, and it makes
requirement 2 structurally true rather than aspirational. I verified every line reference in the
spec; all nine `#ffae42` sites, the three `styleFn` selection branches and the pane z-indices are
as described. The weight-ramp arithmetic checks out exactly.

Two things are wrong as written and would produce regressions if implemented literally:
**the hover early-return kills the tooltip and the spatial-risk float readout on the selected
zone (B1)**, and **the guard test forbids a literal that the token system itself requires (B5)**.
Three more are under-specification serious enough to block a clean implementation: the
`SelectionRing` signature is given three incompatible ways (B2), three of `epiTrendsStyleFn`'s
weight tiers are never mapped onto the new ramp (B3), and the no-data stroke rationale only holds
for one of the three branches it is applied to (B4).

Separately, the biggest *design* risk is not discussed at all: the resting border gets **3–5.7×
heavier** everywhere, and the candidates were rendered on Ituri geometry only (N5).

---

## What the spec gets right (verified)

- **The current-state table is accurate.** `#1a1a1a` w2.4 at `engine.js:1517` (snapshot),
  `#ffae42` w2 at `1772`/`1862`/`2540`/`2987` (trends health-zone), `#ffae42` w1.8 via
  `weight = 1.8` at `1360` + `color` at `1369` (spatial risk), `#ffae42` w1.6 at `2813`
  (context — pixel-identical to the hover at `1754`, as claimed), `#9a7a16` w2.4 at `1484`
  (genomic). Five treatments, three sharing hover's amber. Confirmed.
- **The `bringToFront()` diagnosis is correct.** All three hover handlers
  (`1742`, `1750`, `1755`) front the hovered zone unconditionally, and nothing re-fronts the
  selected one until the next `restyleZonesForActiveView()`. Requirement 4 genuinely cannot be
  met by ordering discipline in the current design.
- **Resting weight numbers are right.** `zoomWeight(0.35)` with
  `f = clamp(0.5 + (zoom−5)×0.28, 0.5, 2.1)` (`engine.js:587-590`) gives 0.175 px at z5 and
  0.567 px at z9.
- **The ramp table is arithmetically exact.** `1.7 × clamp(0.6 + (z−5)×0.10, 0.6, 1.15)` yields
  1.02 / 1.36 / 1.53 / 1.70 / 1.955 at z5 / z7 / z8 / z9 / z10.5. The ceiling is first reached at
  z10.5, as stated. The keyline derivation `(3.6 − 2.2)/2 = 0.7×` → 1.19 px at z9 is correct.
- **Rejecting a near-black selection ring is well-founded.** The OUTBREAK dark end really is
  near-black at the top zone, so a dark ring would vanish exactly where selection matters most.
- **`themeVar()` fallback discipline is the right instinct.** `themeVar()`
  (`engine.js:2124-2127`) returns the fallback on an empty computed value, and the theme layer is
  genuinely optional — `build_dashboard.py:75-76` appends `load_theme_css()` output only when
  non-empty. `Data/Branding/dashboard-theme.css` *is* git-tracked, so a guard test over it is
  viable in CI.
- **Keeping the five selection variables and deriving from them** (rather than merging state) is
  the correct minimal-blast-radius call.
- **The two asymmetries are honestly labelled**, and the genomic one matches the live comment at
  `engine.js:1725-1731`.

---

## Blocking issues

### B1 — The hover early-return silently removes the tooltip and the spatial-risk float readout

> §Hover: "Each hover handler gains one early return: if the zone is in `currentSelectedNoms()`,
> do nothing (requirement 3)."

The hover handlers do not only restyle. In one block they also:

- **Snapshot** (`engine.js:1754-1758`): `setStyle` → `bringToFront` → `bindTooltip(layerHoverTooltipHTML(...)).openTooltip()`
- **Spatial risk** (`engine.js:1748-1752`): `setStyle` → `bringToFront` → `updateEpiFloat(nom, e.latlng)`

"Do nothing" therefore means the **selected** zone stops showing its layer-value tooltip on the
snapshot tab and stops showing the floating readout on the spatial-risk tab. That is the zone the
user just clicked and is most likely to hover — a clear functional regression, and it is not
listed anywhere as an intended behaviour change.

Requirement 3 is about *styling*, not about interaction. Restate it as such and be explicit:

> Skip only the `setStyle`/`bringToFront` pair. Tooltips, the epi float readout and the
> province-hover call continue to fire for selected zones.

Also specify the `mouseout` counterpart: `hideEpiFloat()` at `1783` must still run for a selected
zone even though `mouseover` skipped the restyle, or the float strands open. (`geoLayer.resetStyle`
on a zone that was never restyled is a harmless no-op, so no other change is needed there.)

### B2 — `SelectionRing.set()` is specified three incompatible ways

Within two sections the spec says all of:

1. "`set(features)` **takes GeoJSON features** and draws, per feature, two … paths"
2. "It takes features **rather than keys**" (with the rationale that this lets one factory serve
   both the `nom` and province key spaces)
3. `SelectionRing(pane, zIndex) → { set(featuresOrNoms), clear(), redraw() }`
4. `refreshZoneSelection() // = zoneRings.set(currentSelectedNoms())` — which by name passes
   **noms**

Pick one. Given the rationale in (2), features is the right choice, in which case:

- rename `currentSelectedNoms()` → `currentSelectedFeatures()` (or keep both, with the accessor
  returning noms and `refreshZoneSelection` doing the resolve);
- drop `featuresOrNoms` from the API listing;
- note that the resolver already exists — there is a `nom → feature` linear scan over
  `PAYLOAD.geometry.features` at `engine.js:200-205`. Reuse it rather than adding a second.
  (It is O(n) per lookup over ~500 features; irrelevant for a selection of 1–10, but worth naming
  so nobody builds an index "for safety".)

### B3 — Three of `epiTrendsStyleFn`'s weight tiers are never mapped onto the new ramp

The spec correctly identifies that role-marker weights must be rebased as multipliers, "because
their current fixed values … would render *thinner* than the new 1.7 px resting border." The same
defect exists in three places the spec does not cover:

| Site | Current weight | After? |
|---|---|---|
| `engine.js:1324` — zone not visible for the active epi layer | `zoomWeight(0.25)` | unspecified |
| `engine.js:1352` — active zone, no value ("fail-loud") | `zoomWeight(0.35)` | unspecified |
| `engine.js:1363` — spatial-risk **focus** tier (flow-connected neighbours) | fixed `0.8` | unspecified |

The token table gives `--zone-nodata-stroke` a colour and an opacity but **no weight multiplier**,
and the spatial-risk focus tier gets no token at all. Left as-is, the focus tier's fixed 0.8 px
renders thinner than the 1.53 px resting border at the default z8 view — the exact inversion the
spec calls out for role markers. Add:

```
--zone-nodata-weight-mult      (for 1352)
--zone-hidden-weight-mult      (for 1324)
--zone-focus-weight-mult       (for 1363; < 1, e.g. 0.55 to preserve today's 0.8/1.53 ratio)
```

Also state what happens to the **non-focus dim tier** (`1365`): it currently drops only
`fillOpacity` to 0.12 and keeps a full-weight stroke. See N5 — this is where the heavier ramp
does the most damage.

### B4 — The no-data stroke rationale holds for one of the three branches it is applied to

> §No-data zones: "Zones with no value … currently draw `#111` over `fillOpacity: 0` — outline
> only, no fill. Off-white there vanishes against the CARTO light basemap … This covers both the
> `!has` branch in `styleFn` and the two early-return branches in `epiTrendsStyleFn`."

Only the `styleFn` branch (`1520`) is fill-less. The two `epiTrendsStyleFn` branches have fills:

- `1324`: `fillColor: "#222"`, `fillOpacity: 0.04` — effectively transparent, so the rationale
  transfers. Fine.
- `1352`: `fillColor: NODATA_FILL` = `#7d7d7d` at `fillOpacity: 0.55` — a solid mid-grey. A
  `#6b635a` stroke at 0.45 opacity over that is close to invisible.

`1352` is explicitly the fail-loud state ("an active zone with no count — should never happen",
`engine.js:1406`). Making it fail-*quiet* is the wrong direction. Choose the stroke by the
lightness of what it sits on, not by which branch produced it: warm grey where there is no fill,
and something with actual contrast against `#7d7d7d` for the fail-loud branch (the off-white at
full opacity would work there, or keep `#111`).

### B5 — The guard test as specified fails a correct implementation, and misses the invariant that matters

> "assert … `Scripts/assets/engine.js` contains no residual `#ffae42` / `#1a1a1a` / `#9a7a16`
> zone-styling literals."

`--zone-selected-stroke` **is** `#ffae42`, and §Token system requires that "every `themeVar()`
call must pass the full value above as its JS fallback." So a compliant implementation contains
`themeVar("--zone-selected-stroke", "#ffae42")` and the guard test red-flags it. There is also a
legitimate mention in the comment at `engine.js:1510` (which the change should delete, but the
test would be asserting on prose). Scope the assertion to `setStyle(`/style-literal contexts, or
drop it.

More importantly, the test as written does not check the invariant the design actually leans on.
The theme layer is optional, so **the fallbacks are the real spec** — a fallback that drifts from
the CSS produces a dashboard that looks different with and without branding, silently. That is
statically checkable and is the test worth writing:

1. Parse `themeVar\("(--[a-z-]+)",\s*"([^"]+)"\)` out of `engine.js`.
2. Parse the `--zone-*` token block out of `Data/Branding/dashboard-theme.css`.
3. Assert: every `--zone-*` token in the CSS is referenced at least once; every referenced token
   exists; and **every fallback string equals the CSS value**.
4. Assert the ramp constants numerically against the documented z5 / z9 values, so a slope edit
   that silently changes the national view fails the test.

This also catches the existing `--province-outline-*` family for free.

---

## Should fix

### N1 — "Every site that changes a selection calls `refreshZoneSelection()`" is the same discipline the design claims to remove

The pane architecture is justified as removing "ordering discipline at eight call sites" — and
then reintroduces it as refresh discipline at nine. The verified mutation sites are:

| Site | Line |
|---|---|
| `setMapSelection` | `212` |
| `setEpiSelected` (both branches) | `1133`, `1138` |
| `leaveEpiTrendsView` | `1397` |
| `setTrendsSelection` | `2525` |
| `setTrendsScope` | `2559` |
| `clearContextSelection` | `2802` |
| `selectContextZone` | `2811` |
| `leaveTrendsView` | `3060` |
| `genomicMapHooks.highlightZones` | `3535` |

Nothing in the guard test can catch a missed one; the symptom is a stale ring on one tab only.
Cheaper structural fix: call `refreshZoneSelection()` from **`restyleZonesForActiveView()`**
(already bound to `zoomend` at `1880`) and from `setActiveView`, and route the three bare
`= null` clears in the leave paths through their setters. That reduces the discipline to "any
path that changes selection ends in a restyle" — which is already true today, since every one of
those sites calls `geoLayer.setStyle(styleFn)` or a `recompute*()` that does.

Either way, put the enumerated list in the spec so the implementation plan is checkable.

### N2 — The zone-ring pane at 460 flips today's arc/border stacking

Verified panes: `flow-arcs` = 450 (`engine.js:593`), `epi-links` = 455 (`595`),
`province-outline` = 550 (`2147`); zone polygons are in Leaflet's default `overlayPane` (400).
Today the selection border lives in the polygon at 400, i.e. **under** flow arcs and epi-links.
At 460 the ring is drawn **over** them. On the spatial-risk tab, selecting a zone is exactly what
renders its arcs, so the new 5.5 px cased ring at z8 will occlude every arc terminus at the
selected zone — a stacking change that is a side effect, not a decision.

Zone rings only need to clear the polygons (400). Placing them at **445** keeps them above zone
borders and preserves today's arcs-over-borders reading. If 460 is deliberate, say why.

Related, and worth stating explicitly: `markerPane` is 600 and `tooltipPane` 650, so case markers,
genome-count circles and tooltips still draw over the ring at any of these values. Requirement 4
is a guarantee against *zones*, not against markers.

### N3 — The province hover/selection split leaves `trendsHoveredProvince` and its body class undefined

`applyProvinceOutlineStyles(selectedProvince)` writes both `trendsHoveredProvince` and the
`trends-province-hovered` body class (`engine.js:2157-2158`), and `setTrendsProvinceHover`
(`2179`) routes through the same function with a `!trendsSelectedKey` gate. Once hover and
selection separate, that single variable has to become two, and the spec must say which one drives
the body class.

Useful finding for the implementer: **`trends-province-hovered` has no CSS consumer.** The only
rule on either class is `body.view-context.context-zone-hovered #context-hint`
(`dashboard.css:671`). So `trends-province-hovered` is dead and can be deleted rather than
carefully preserved — worth stating so nobody preserves a phantom.

### N4 — The selected province's own outline is not addressed

`provinceOutlineStyle(selected)` (`engine.js:2128-2144`) returns `#b23b2e`, the heavier
`*-hover` weight, and `opacity: 1` for the selected case. The per-view table says province
selection becomes "cased amber, as zones", but does not say that the underlying outline reverts to
its **resting** gold. Without that, the selected province gets a red base outline under an amber
ring. State that `provinceOutlineStyle(true)` collapses into the hover branch and that the
selected province's base outline is resting.

### N5 — The resting border gets 3–5.7× heavier, and that was only mocked on Ituri

This is the largest visual change in the spec and it is presented as a sub-bullet of a colour
decision. Verified deltas: **0.175 → 1.02 px at z5 (5.8×)**, **0.567 → 1.70 px at z9 (3.0×)**,
across every zone in the national geometry. §Design decisions says candidates were rendered "on
the real Ituri geometry" — a single province. The failure mode of a heavier border is a
*national*, many-small-polygons failure mode; Ituri cannot show it. The spec even names the risk
("too heavy nationally") and then resolves it against evidence that does not cover that case.

The worst case is the spatial-risk dim tier (`engine.js:1365`): non-focus zones drop to
`fillOpacity: 0.12` but keep a full-weight stroke. Today that stroke is a 0.5 px near-black
hairline; after the change it is a ~1.5 px bright off-white line at z8, on *every* non-focus zone,
while the focus zones' own borders are thinner (B3). The dimming is supposed to be the focus
signal, and a bright mesh over the dimmed zones works directly against it.

Before locking `--zone-stroke-weight-base`:

- render one national z5 / z6 mockup with the full geometry, not a province subset;
- add a stroke-opacity drop for the dim tier (e.g. `--zone-dim-stroke-opacity: 0.25`) rather than
  leaving stroke weight untouched while the fill fades.

### N6 — Contrast was checked at the dark end of the ramp, not the light end

The selection-ring rejection reasoning is good — it checks `rgb(124,29,29)` at Bunia. The
*resting* border needs the mirror check and does not get one. `#fdfaf4` at 0.7 opacity sits on:
`ZERO_FILL` `#c4bfb6` at 0.48–0.55 (`engine.js:1405`, `1523-1525`), and the pale ends of REDS /
RISK_ORANGES / OUTBREAK. On those, an off-white border at 0.7 is close to no border at all — so
zone boundaries would read *worst* in the low-count areas, which is where they are currently
clearest (dark on light). Record the contrast floor the design accepts and check the palest fill
in each palette, the same way the dark end was checked.

### N7 — The genomic `styleFn` branch's fate is ambiguous

"the selection-colour branches in `styleFn` (the selected zone's fill bump to `fillOpacity: 0.85`
stays — only the stroke moves out)" is written in the singular and reads as being about the `map`
branch at `1509-1517`. The genomic branch at `1476-1485` has the identical shape and must survive
for its own fill bump. Say so — and note that once colour and weight are stripped, both branches
reduce to "resting style + fill bump" and can collapse into one helper, which is a real
simplification worth banking.

### N8 — The search highlight is a sixth state and is not in the grammar

`searchHighlightLayer` (`engine.js:1980-2001`) paints a transient highlight via `setStyle` and its
cleanup special-cases `contextSelectedLayer` at `1998`. The spec correctly notes that removing
`contextSelectedLayer` simplifies `clearSearchHighlight()`, but never says what the search
highlight looks like under the new grammar — hover lift? its own treatment? a temporary ring? Given
requirement 2 is "one selection treatment across every tab", a search hit that lands on a
differently-styled highlight is the next drift. Add it to the state table or explicitly scope it
out.

---

## Minor / nits

- **`--zone-*` tokens applied to provinces.** §Province outlines reuses `--zone-hover-weight-mult`
  and the selection multipliers against province base weights. Beyond the naming smell, the two
  ring scales cross over: the province ring is fixed (3.6 × 1.4 = 5.0 px in province scope) while
  the zone ring is zoom-scaled (3.67 px at z5 → 7.04 px at z10.5), so which one reads as "heavier"
  flips mid-zoom. Give provinces their own `--province-*-mult` tokens, even if the initial values
  are identical.
- **`--zone-stroke-ramp-min` does double duty** as both the z5 intercept and the clamp floor, so
  editing the intercept silently moves the floor. Not dead code — the map sets no `minZoom`
  (`engine.js:577`) and one path calls `setView(..., 5)` (`3837`), so sub-z5 is reachable by pinch.
  Worth one sentence.
- **Adjacent selected zones** (genomic multi-highlight, which in Ituri is often a contiguous
  cluster) stack two casings and two rings on the shared border, and each casing's outer half lands
  on the neighbour's ring. Either accept it (it reads as one thicker keyline) or dissolve interior
  edges. Just name the choice.
- **`zoomend` fires after the zoom animation**, so the ring keeps its old weight mid-animation.
  Same as today's `zoomWeight` behaviour, so acceptable — but the spec's "rings rebuild on
  `zoomend`" is worth one clause acknowledging it.
- **`recomputeTrendsMap()` fires on every time-slider tick** and re-paints selection at
  `2984-2991`. `2987` is correctly in the removal list; add a note that no `refreshZoneSelection()`
  replaces it — the ring survives the restyle by construction. That is one of the design's better
  payoffs and is currently invisible in the write-up.
- **`Scripts/build_dashboard_public.py` carries a stale inline copy** of these same functions
  (`applyProvinceOutlineStyles` at `6099`, `renderContextPanel` at `6586`). It does not reference
  `engine.js` and predates the assets split, so it is the legacy monolith and should **not** be
  updated. Say so in §Files touched, so the divergence is not later read as a bug.
- **§Out of scope lists "genomic zone hover"**, which is also §Per-view behaviour's first
  deliberate asymmetry. Keep one.

---

## Suggested additions to §Verification

The manual pass ("five tabs × three zoom levels") misses the states that actually broke. Add:

1. **No theme file at all** — rename `Data/Branding/dashboard-theme.css`, rebuild, confirm the
   dashboard is visually identical. This is the one invariant the whole token system rests on and
   nothing else tests it end-to-end.
2. Select a zone → zoom → confirm the ring rebuilds at the new weight (and mid-animation looks
   acceptable).
3. Select a zone → switch tab → switch back → confirm the ring state matches the tab's own
   selection, not the previous tab's.
4. Trends health-zone: select, then drag the time slider through its full range.
5. Spatial risk: select a zone with flow arcs on, and check the ring/arc stacking (N2).
6. Spatial risk: confirm the dim tier still reads as dimmed at national zoom (N5).
7. Genomic: highlight an adjacent multi-zone set (N9).
8. Hover the selected zone on Snapshot and on Spatial risk — tooltip and float readout must still
   appear (B1).
9. National z5 with the full geometry, side by side against `main`, for total line load (N5).

---

## Summary of recommended spec edits

| # | Change | Severity |
|---|---|---|
| B1 | Requirement 3 suppresses the restyle only; tooltips/float readout survive; specify `mouseout` | blocking |
| B2 | Fix the `SelectionRing.set()` signature to one form; reuse the existing `nom → feature` scan | blocking |
| B3 | Add weight multipliers for the two no-data branches and the spatial-risk focus tier | blocking |
| B4 | Pick the no-data stroke by fill lightness; keep `1352` fail-loud | blocking |
| B5 | Replace the literal-ban test with a fallback-vs-CSS equality test + a ramp arithmetic check | blocking |
| N1 | Enumerate the nine refresh sites; prefer refreshing from `restyleZonesForActiveView()` | should fix |
| N2 | Move zone rings to 445, or justify 460; note markers/tooltips still draw over the ring | should fix |
| N3 | Split `trendsHoveredProvince`; delete the dead `trends-province-hovered` class | should fix |
| N4 | State that the selected province's base outline reverts to resting gold | should fix |
| N5 | Mock the ramp at national z5/z6; add a stroke-opacity drop for the spatial-risk dim tier | should fix |
| N6 | Check resting-border contrast against the palest fills, not just the darkest | should fix |
| N7 | Say the genomic `styleFn` branch survives for its fill; collapse both into one helper | should fix |
| N8 | Place the search highlight in the state grammar, or scope it out explicitly | should fix |
