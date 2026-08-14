# Harmonised zone state styling on the outbreak map

**Date:** 2026-08-14
**Status:** Design approved, revised after review, ready for implementation planning
**Review:** `2026-08-14-map-zone-state-styling-design-review.md` — all blocking items folded in;
three review claims corrected (see §Review dispositions).

## Problem

The outbreak map paints a health zone's resting, hovered and selected states differently on
every tab. Five tabs carry five selection treatments, three of them reusing the same amber as
hover, and the Context tab's selection is pixel-identical to a hover. A selected zone also
reacts to hover, and its highlight is routinely painted over by a hovered neighbour, because
every hover handler calls `bringToFront()` on the zone under the cursor.

Current state, from `Scripts/assets/engine.js`:

| State | Snapshot | Trends (health zone) | Spatial risk | Context | Genomic |
|---|---|---|---|---|---|
| Resting border | `#111` | `#111`, 0 in province scope | `#111` | `#111` | `#111` |
| Hover | `#ffae42` w1.6 | `#ffae42` w1.6 | `#ffae42` w1.6 | none | none |
| Selected | `#1a1a1a` w2.4 | `#ffae42` w2 | `#ffae42` w1.8 | `#ffae42` w1.6 | `#9a7a16` w2.4 |

Resting weight comes from `zoomWeight(0.35)`, which yields 0.18 px at the national z5 view and
0.57 px at z9.

## Requirements

1. Replace the black resting border with a soft off-white.
2. One selection treatment — same colour, same width — across every tab.
3. A selected zone does not react to hover.
4. A selected zone's highlight stays visible; a hovered neighbour cannot override it.

Requirement 3 is about **styling only**. Tooltips, readouts and other hover-driven behaviour on
a selected zone are unaffected — see §Hover.

## Design decisions

Candidates were rendered on the real geometry with real confirmed-case fills (mockups preserved
under `.superpowers/brainstorm/`, gitignored):

- the **colour** comparison used the 9-zone Ituri cluster at z9, where per-zone fills are legible;
- the **weight ramp** comparison used the full national geometry — all 518 zones at z5 — plus a
  60-zone provincial view at z7 and the same z9 cluster, because a heavier border's failure mode
  is a national, many-small-polygons failure mode that a single province cannot show.

Decisions:

- **Resting border:** off-white `#fdfaf4` at 0.7 opacity.
- **Weight ramp:** "flatter ramp" — 1.7 px at z9, ~1.0 px at the national z5 view, rather than a
  flat 1.7 px everywhere (too heavy nationally) or the current ramp rebased (too faint
  nationally).
- **Hover / selected pair:** hover is a *white lift* of the same border; selection is amber with
  a dark casing. A near-black selection ring was rejected because it disappears into the dark
  end of the OUTBREAK ramp — Bunia, the highest-count zone, fills at `rgb(124,29,29)`.
- **Scope:** full harmonisation, including the genomic tab's multi-zone highlight, the
  epicentre / matrix-origin role markers, hover on the Context tab, and province outlines.

**Accepted trade-off at the light end of the ramp.** An off-white border at 0.7 opacity is
weakest over pale fills — `ZERO_FILL` `#c4bfb6`, and the low stops of OUTBREAK / REDS /
RISK_ORANGES. This was surfaced during the colour comparison (Damas and Kilo were called out
explicitly) and accepted: boundaries read less sharply in low-count areas than they do today, in
exchange for the choropleth reading as tiles of colour rather than as a black grid. The
mockups covered OUTBREAK only, so implementation must check the palest stop of every palette in
`PALETTES` — see §Verification.

## Token system

Tokens live in `Data/Branding/dashboard-theme.css` alongside the existing `--province-outline-*`
family, and are read through `themeVar()`.

### Zone strokes

| Token | Value | Role |
|---|---|---|
| `--zone-stroke` | `#fdfaf4` | resting border |
| `--zone-stroke-opacity` | `0.7` | |
| `--zone-stroke-weight-base` | `1.7` | weight at z9 |
| `--zone-stroke-ramp-min` | `0.6` | z5 intercept **and** clamp floor |
| `--zone-stroke-ramp-max` | `1.15` | clamp ceiling |
| `--zone-stroke-ramp-slope` | `0.10` | per zoom level |
| `--zone-hover-stroke` | `#ffffff` | hover lift |
| `--zone-hover-stroke-opacity` | `0.98` | |
| `--zone-hover-weight-mult` | `1.7` | × resting |
| `--zone-selected-stroke` | `#ffae42` | selection inner ring |
| `--zone-selected-stroke-opacity` | `1.0` | |
| `--zone-selected-weight-mult` | `2.2` | × resting |
| `--zone-selected-casing` | `#5c3a12` | dark keyline under the ring |
| `--zone-selected-casing-opacity` | `0.9` | |
| `--zone-selected-casing-mult` | `3.6` | × resting |

`--zone-stroke-ramp-min` does double duty as the z5 intercept and the clamp floor, so editing
the intercept silently moves the floor. Sub-z5 is reachable — the map sets no `minZoom`
(`engine.js:577`) and `setView(..., 5)` at `3837` starts at the floor — so the coupling is
deliberate: below z5 the border stops thinning. Keep them one token.

### Tier strokes

Every weight is a multiplier on the resting ramp, so no tier can invert against the resting
border as zoom changes. Multipliers preserve each tier's *current* relationship to resting
(computed at z8; see §Review dispositions for why the review's figure for the focus tier was
wrong).

| Token | Value | Applies to |
|---|---|---|
| `--zone-nodata-stroke` | `#6b635a` | fill-less zones: `styleFn` `!has` (`1520`), epi-trends hidden (`1324`) |
| `--zone-nodata-stroke-opacity` | `0.45` | |
| `--zone-nodata-weight-mult` | `1.0` | `1520` — matches today's `zoomWeight(0.35)` |
| `--zone-hidden-weight-mult` | `0.7` | `1324` — today's `zoomWeight(0.25)` is 0.71 × resting |
| `--zone-failloud-stroke` | `#111` | epi-trends active-zone-with-no-count (`1352`) |
| `--zone-failloud-stroke-opacity` | `1.0` | |
| `--zone-failloud-weight-mult` | `1.0` | |
| `--zone-focus-weight-mult` | `1.35` | spatial-risk focus tier (`1363`) |
| `--zone-dim-stroke-opacity` | `0.25` | spatial-risk non-focus tier (`1365`) |
| `--zone-role-stroke` | `#111` | epicentre / matrix-origin marker |
| `--zone-role-weight-mult-origin` | `1.6` | × resting |
| `--zone-role-weight-mult-epicenter` | `1.35` | × resting |

### Province strokes

Provinces get their own multipliers rather than borrowing the zone ones. Zone rings are
zoom-scaled and province rings are not, so shared multipliers would make the two ring scales
cross over mid-zoom — whichever reads as "heavier" would flip. Initial values match the zone
family; they are free to diverge.

| Token | Value | Role |
|---|---|---|
| `--province-hover-stroke` | `#ffffff` | hover lift |
| `--province-hover-stroke-opacity` | `0.98` | |
| `--province-hover-weight-mult` | `1.7` | × province resting weight |
| `--province-selected-weight-mult` | `2.2` | × province resting weight |
| `--province-selected-casing-mult` | `3.6` | × province resting weight |

Province rings reuse `--zone-selected-stroke` and `--zone-selected-casing` for colour: a
selection must look the same everywhere (requirement 2), and province and zone selection are
mutually exclusive in Trends.

### Fallbacks are the real spec

The theme layer is optional — `build_dashboard.py:75-76` appends `load_theme_css()` output only
when non-empty — so **every `themeVar()` call must pass the value above as its JS fallback**, the
way `themeVar("--province-outline-weight", "1")` already does. A fallback that drifts from the
CSS produces a dashboard that renders differently with and without branding, silently. This is
statically checkable and is the main guard test (§Verification).

### Weight ramp

```js
zoneWeight(zoom) = base × clamp(rampMin + (zoom − 5) × rampSlope, rampMin, rampMax)
```

| Zoom | Resting | Hover (×1.7) | Selected inner (×2.2) | Casing (×3.6) |
|---|---|---|---|---|
| z5 (national) | 1.02 | 1.73 | 2.24 | 3.67 |
| z7 | 1.36 | 2.31 | 2.99 | 4.90 |
| z8 (default view) | 1.53 | 2.60 | 3.37 | 5.51 |
| z9 | 1.70 | 2.89 | 3.74 | 6.12 |
| z10.5 and above | 1.96 | 3.33 | 4.30 | 7.04 |

The casing is drawn *beneath* the inner ring, so the visible dark keyline is
`(3.6 − 2.2) / 2 = 0.7 ×` resting on each side — about 1.19 px at z9.

### Stroke colour by what it sits on

The stroke is chosen by the lightness of the fill beneath it, not by which branch produced it:

| Branch | Fill | Stroke |
|---|---|---|
| `styleFn` `!has` (`1520`) | none (`fillOpacity: 0`) | warm grey — off-white would vanish against the CARTO light basemap |
| epi-trends hidden (`1324`) | `#222` @ 0.04, effectively transparent | warm grey |
| epi-trends fail-loud (`1352`) | `NODATA_FILL` `#7d7d7d` @ 0.55, solid mid-grey | `#111` @ 1.0 — warm grey at 0.45 over mid-grey is near-invisible, and this state ("an active zone with no count — should never happen", `engine.js:1406`) must stay loud |
| all others | choropleth | off-white |

### Spatial-risk dim tier

`epiTrendsStyleFn` currently drops non-focus zones to `fillOpacity: 0.12` but leaves their
stroke at full resting weight (`1365` sets only `opacity`). Today that stroke is a ~0.5 px
near-black hairline; under the new ramp it becomes a ~1.5 px bright off-white line on *every*
non-focus zone at z8. The dimming is the focus signal, and a bright mesh over the dimmed zones
works against it. The dim tier therefore also drops stroke opacity to
`--zone-dim-stroke-opacity`.

### Role markers

Epicentre and matrix-origin zones keep `#111` — the darker casing colour was tried and judged
not different enough to be worth the change. Their **weights** are rebased as multipliers,
because their current fixed values (1.6 for the hub, `zoomWeight(0.5)` for the epicentre) would
render *thinner* than the new 1.7 px resting border.

### Province outlines

Provinces keep their gold resting colour so the province layer still reads as distinct from the
zone layer, but adopt the same state grammar:

| State | Now | After |
|---|---|---|
| Resting | `#9b7d4e`, w1.0 (1.4 wide) | unchanged |
| Hover | `#b23b2e`, w1.5 (2.0 wide) | white lift, `--province-hover-*` |
| Selected | `#b23b2e` (same as hover) | cased amber ring, base outline **reverts to resting gold** |

`provinceOutlineStyle(selected)` currently returns `#b23b2e`, the heavier `*-hover` weight and
`opacity: 1` for its truthy case (`engine.js:2128-2144`). That branch becomes the *hover* branch
only. A selected province draws a resting gold outline with a cased amber ring above it —
without this, the selected province would show a red base outline under an amber ring.

Today a single `trendsHoveredProvince` variable serves both hover and selection, and
`setTrendsProvinceHover` suppresses hover entirely once any province is selected
(`engine.js:2179`). These separate into two variables: hover applies to non-selected provinces,
and the selected province ignores hover — the province-level reading of requirement 3. This is a
deliberate behaviour change.

The `trends-province-hovered` body class toggled at `engine.js:2158` **has no CSS consumer** —
the only rule on either hover class is `body.view-context.context-zone-hovered #context-hint`
(`dashboard.css:671`). Delete it rather than carefully preserving a phantom.

## Architecture

### Selection rings in a dedicated pane

Selection moves out of the zone polygon and into its own pane, so requirement 4 holds as a
property of the render tree rather than as ordering discipline at nine call sites.

A `SelectionRing(paneName, zIndex)` factory creates a ring layer whose **`set(features)` takes
GeoJSON features** and draws, per feature, two non-interactive `fill: none` paths — casing
first, inner ring second. Features rather than keys, so one factory serves both the `nom` and
province-name key spaces; resolving a key to its feature stays with the caller, reusing the
existing `featureByNom()` linear scan at `engine.js:198-206`. That scan is O(n) over ~500
features per lookup, which is irrelevant for a selection of 1–10 — do not build an index.

Two instances:

| Instance | Pane | z-index | Rationale |
|---|---|---|---|
| Zone rings | `zone-selection` | 445 | above zone polygons (`overlayPane`, 400), **below** flow arcs (450) and epi-links (455) |
| Province rings | `province-selection` | 560 | above province outlines (550) |

**Why 445 and not 460.** Today the selection border lives inside the polygon at 400, i.e. under
flow arcs and epi-links. On the spatial-risk tab, selecting a zone is precisely what renders its
arcs, so a ring above them would occlude every arc terminus at the selected zone — a stacking
change nobody asked for. Zone rings only need to clear the polygons.

Both panes get `pointer-events: none` so clicks fall through to the polygon underneath and
click-to-deselect keeps working.

Requirement 4 is a guarantee against **zones**, not against everything: `markerPane` (600) and
`tooltipPane` (650) are above both ring panes, so case markers, genome-count circles and
tooltips still draw over the ring. That is correct and unchanged.

### Single source of truth for selection

Selection state stays where it is — `mapSelectedNom`, `trendsSelectedKey`, `contextSelectedNom`,
`epiSelectedNom`, `genomicHighlightNoms` — rather than being merged, which would touch every
view's logic. Instead one derived accessor feeds one painter:

```js
currentSelectedNoms()    // reads activeView, returns the active set (array of nom)
refreshZoneSelection()   // resolves via featureByNom(), then zoneRings.set(features)
```

One code path paints selection for all five tabs, so requirement 2 is enforced structurally. The
array return covers the genomic tab's multi-zone highlight without a special case.

`refreshZoneSelection()` is called from **all nine selection mutation sites**:

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

and additionally, as a backstop, from `restyleZonesForActiveView()` (already bound to `zoomend`
at `1880`) and from `setActiveView`. The backstop covers zoom and tab switches; it does **not**
make the explicit calls redundant, because `clearContextSelection` and `selectContextZone` never
trigger a full restyle — they call `geoLayer.resetStyle(oneLayer)` only.

Province selection refreshes on its own path from `applyProvinceOutlineStyles()`, since it is
driven by a different key space and a different pane.

### New API in `Scripts/assets/engine.js`

- `zoneWeight(zoom)` — the ramp above
- `zoneStroke(state)` — style object for `rest` | `hover` | `nodata` | `hidden` | `failloud` |
  `focus` | `dim` | `epicenter` | `origin`
- `SelectionRing(pane, zIndex)` → `{ set(features), clear(), redraw() }`
- `currentSelectedNoms()` / `refreshZoneSelection()`

### What is removed

- The selection-colour branches in `styleFn` and `epiTrendsStyleFn`. Both surviving fill-bump
  branches — snapshot (`1509-1517`) and genomic (`1476-1485`) — keep their `fillOpacity: 0.85`
  bump; once colour and weight are stripped they reduce to "resting style + fill bump" and
  collapse into one helper.
- The nine duplicated `setStyle({… color: "#ffae42"})` sites: three hover
  (`engine.js:1741, 1749, 1754`) collapse into `zoneStroke("hover")`, and six selection
  (`engine.js:1772, 1862, 1867, 2540, 2813, 2987`) disappear entirely into the ring layer.
- `contextSelectedLayer` and its `resetStyle` bookkeeping, since Context no longer paints
  selection onto the polygon.
- **The dead search-highlight machinery.** `searchHighlightLayer` and `searchHighlightTimer`
  (`engine.js:1980-2001`) are never assigned a layer or a timer — the only writes are `= null`.
  They are leftovers from before search switched to persistent focus (see the comment at `2068`).
  Delete both, along with `clearSearchHighlight()` and its call sites. There is no search
  highlight state to place in the grammar.
- The `trends-province-hovered` body class (no CSS consumer).

`recomputeTrendsMap()` re-paints selection at `2984-2991` on every time-slider tick; `2987` is in
the removal list above and nothing replaces it. The ring survives the restyle by construction —
this is one of the design's better payoffs.

### Hover

Each hover handler gains one early return **around the styling only**: if the zone is in
`currentSelectedNoms()`, skip the `setStyle` / `bringToFront` pair. Everything else in those
handlers continues to run for a selected zone:

- **Snapshot** (`1754-1758`): the layer-value tooltip still binds and opens.
- **Spatial risk** (`1748-1752`): `updateEpiFloat(nom, e.latlng)` still fires.
- **Trends province scope** (`1738`): `setTrendsProvinceHover()` still fires.

The `mouseout` counterparts must stay symmetric: `hideEpiFloat()` at `1783` still runs for a
selected zone, or the float readout strands open. `geoLayer.resetStyle()` on a zone that was
never restyled is a harmless no-op, so nothing else changes there.

Suppressing the tooltip and the float readout on the zone the user just clicked — the zone they
are most likely to hover — would be a functional regression, not a styling change.

### Redraw triggers

Ring weights are zoom-dependent, so rings rebuild on `zoomend` alongside
`restyleZonesForActiveView()`, and on view switch. `zoomend` fires after the zoom animation
completes, so the ring keeps its old weight mid-animation — the same behaviour `zoomWeight()`
already has for zone borders, and acceptable for the same reason.

## Per-view behaviour

| View / scope | Resting | Hover | Selected |
|---|---|---|---|
| Snapshot | token | white lift | cased amber |
| Trends — national | token | — | — |
| Trends — province | suppressed (weight 0, unchanged) | province white lift | province cased amber |
| Trends — health zone | token | white lift | cased amber |
| Spatial risk | token, tiered (focus / dim) | white lift | cased amber |
| Context | token | white lift (new) | cased amber |
| Genomic | token | white lift | cased amber, multi-zone |

One deliberate asymmetry:

- **Trends province scope keeps zone strokes suppressed.** Province outlines are the line work in
  that scope; 519 off-white zone borders underneath would fight them. Hovering a zone there
  continues to highlight its parent province rather than the zone, as it does today — the
  province outline layer is `interactive: false`, so zone mouseover is what drives it.

**Adjacent selected zones.** The genomic multi-zone highlight is often a contiguous cluster, so
two casings and two rings stack on a shared border and each casing's outer half lands on the
neighbour's ring. Accepted as-is: it reads as one thicker keyline around the cluster, which is
the correct reading. Interior edges are not dissolved.

## Edge cases

- `tearDownHoverDecoration()` on map move must not clear the ring — it lives in another pane and
  is not hover decoration, so it survives naturally. Assert this in review.
- `geoLayer.resetStyle()` on mouseout stops being dangerous: selection colour is no longer in
  `styleFn`, so there is nothing left for it to clobber.
- A zone selected in Spatial risk while `epiZoneVisible()` is false still gets its ring —
  selection is not conditional on layer visibility.
- View switches rebuild the ring; `leaveEpiTrendsView()` and the other leave paths clear it.

## Verification

There is no JS test infrastructure — `tests/` is pytest over the build — so two layers.

### Guard test (`tests/test_zone_state_styling.py`)

The theme layer is optional, so the JS fallbacks are the real specification. The test asserts
they cannot drift from the CSS:

1. Parse `themeVar\("(--[a-z-]+)",\s*"([^"]+)"\)` out of `Scripts/assets/engine.js`.
2. Parse the `--zone-*` / `--province-*` token block out of `Data/Branding/dashboard-theme.css`.
3. Assert every token in the CSS is referenced at least once; every referenced token exists in
   the CSS; and **every fallback string equals the CSS value**.
4. Assert the ramp constants numerically against the documented z5 and z9 weights, so a slope
   edit that silently changes the national view fails the test.

This covers the existing `--province-outline-*` family for free.

The earlier draft of this spec proposed banning the literals `#ffae42` / `#1a1a1a` / `#9a7a16`
from `engine.js`. That test would fail a *correct* implementation, since
`themeVar("--zone-selected-stroke", "#ffae42")` is required by the fallback rule. Dropped.

### Manual pass

On a real build (`python3.9`, sibling `../BDBV2026-Data/build`, served over HTTP):

1. **No theme file at all** — rename `Data/Branding/dashboard-theme.css`, rebuild, confirm the
   dashboard is visually identical. This is the invariant the whole token system rests on.
2. Five tabs × three zoom levels (z5 / z8 / z9).
3. Select a zone, hover its neighbour — the ring must be untouched (requirement 4).
4. Hover the selected zone on Snapshot and on Spatial risk — tooltip and float readout must
   still appear (§Hover).
5. Select a zone → zoom → the ring rebuilds at the new weight; mid-animation is acceptable.
6. Select a zone → switch tab → switch back → ring state matches the tab's own selection.
7. Trends health zone: select, then drag the time slider through its full range.
8. Spatial risk: select a zone with flow arcs on — check ring/arc stacking.
9. Spatial risk: confirm the dim tier still reads as dimmed at national zoom.
10. Genomic: highlight an adjacent multi-zone set.
11. National z5 with full geometry, side by side against `main`, for total line load.
12. Palest stop of every palette in `PALETTES` (OUTBREAK, REDS, RISK_ORANGES, PURPLES, PLASMA,
    VIRIDIS) plus `ZERO_FILL` — confirm the resting border clears the accepted contrast floor.

## Out of scope

Case markers, genome-count circles, and the epi-links overlay. Flow arcs are unchanged visually,
but their click handling was revised — see §Revisions after manual testing.

## Files touched

| File | Change |
|---|---|
| `Data/Branding/dashboard-theme.css` | new token block |
| `Scripts/assets/engine.js` | ramp, `zoneStroke`, `SelectionRing`, derived selection, call-site cleanup, dead-code removal |
| `tests/test_zone_state_styling.py` | new guard test |

`assets/` and `output/` at the repo root are CI-generated build artifacts and must not be edited
by hand.

`Scripts/build_dashboard_public.py` carries a stale inline copy of these same functions
(`applyProvinceOutlineStyles` at `6097`, and the trends/context handlers below it). It does not
reference `engine.js` and predates the assets split, so it is the legacy monolith and **is not
updated** by this work. The divergence is intentional, not a bug.

## Revisions after manual testing

Four behaviours were changed after walking the built dashboard. Each is implemented and verified;
this section records them so the spec does not assert decisions that were later reversed.

**Genomic zones gain the hover lift** — reversing this spec's original "genomic keeps no zone
hover" asymmetry. The guard that suppressed it dated from before the genomic coordinator existed,
and its stated reason was specifically the layer-value tooltip: those are bound per hover, and the
`tooltipopen` sweep covers marker and arc layers but not zones, so a dropped mouseout on fast
motion strands one open. Zones on that tab are clickable — the click routes to the coordinator — so
they now take the same white lift as every other tab while still binding no tooltip.

**The hover lift survives a pan.** `movestart` tears hover decoration down and restyles. If a drag
starts and ends inside the same polygon the pointer never leaves it, so Leaflet fires no fresh
`mouseover` and the lift stayed gone until the cursor left and re-entered. The pointer position is
now tracked, and on `moveend` the lift is re-applied to whichever zone sits under it. Border only:
re-opening a tooltip on `moveend` is the exact stranding hazard `tearDownHoverDecoration()` exists
to prevent, and the spatial-risk float readout needs a `latlng` that path does not have. Both
return on the next real mouseover. Province outlines have the same gap and are not covered.

**Flow-arc clicks forward to the polygon underneath.** Arcs are annotations, not controls, but they
sit in a pane above the zones with `bubblingMouseEvents: false`, so a click landing on one was
swallowed — making every arc a dead stripe across an otherwise clickable polygon. The per-view
click logic is now a shared `handleZoneClick(feature)` called by both the polygon handler and the
arc forwarder, so the two paths cannot drift. `bubblingMouseEvents` stays `false`: with no zone
beneath the cursor the click must still not reach the map handler, which would clear the selection
and take the arcs with it. Chevron wing markers were already `interactive: false`.

**Role-marker draw order is re-asserted.** Hover calls `bringToFront()`, and `resetStyle()` on
mouseout restores a zone's style but not its DOM order — so a hovered neighbour stayed in front and
clipped the heavier border of an adjacent epicentre or travel-origin zone. Selection is immune
because its ring is in a higher pane; role markers live in the polygon layer, where draw order is
all they have. Order is now re-asserted when a hover ends, after any full restyle, and on layer
change — the last also fixing a pre-existing case where role zones were in front only by accident
of feature order. During a hover the hovered zone still outranks role markers, which is intended.

## Review dispositions

Three claims in the review were checked against the code and not adopted as written:

- **B3's suggested value.** The review proposes `--zone-focus-weight-mult: 0.55` "to preserve
  today's 0.8/1.53 ratio", which divides today's focus weight by *tomorrow's* resting weight.
  Against today's actual resting weight the focus tier is 1.41× (z9), 1.71× (z8) and 4.57× (z5)
  — thicker, never thinner. A sub-1 multiplier would deepen the very inversion the item raises.
  Set to `1.35`, between resting and hover, and distinct from the hover multiplier so a focus
  zone does not read as hovered. Confirm on the live build.
- **N8's remedy.** The item is right that the search highlight has no place in the state grammar,
  but the fix is deletion, not specification: `searchHighlightLayer` / `searchHighlightTimer` are
  never assigned. See §What is removed.
- **N1's justification.** The claim that refreshing from `restyleZonesForActiveView()` alone
  suffices, because every mutation site already ends in a full restyle, holds for seven of the
  nine sites but not for `clearContextSelection` / `selectContextZone`, which only call
  `geoLayer.resetStyle(oneLayer)`. Both the explicit calls and the backstop are specified.

Everything else in the review — B1, B2, B4, B5, N2, N3, N4, N5, N6, N7 and all nits — is adopted.
