# Harmonised zone state styling on the outbreak map

**Date:** 2026-08-14
**Status:** Design approved, ready for implementation planning

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

## Design decisions

All four were chosen by rendering candidates on the real Ituri geometry with real confirmed-case
fills (mockups preserved under `.superpowers/brainstorm/`, gitignored).

- **Resting border:** off-white `#fdfaf4` at 0.7 opacity.
- **Weight ramp:** "flatter ramp" — 1.7 px at z9, ~1.0 px at the national z5 view, rather than a
  flat 1.7 px everywhere (too heavy nationally) or the current ramp rebased (too faint
  nationally).
- **Hover / selected pair:** hover is a *white lift* of the same border; selection is amber with
  a dark casing. A near-black selection ring was rejected because it disappears into the dark
  end of the OUTBREAK ramp — Bunia, the highest-count zone, fills at `rgb(124,29,29)`.
- **Scope:** full harmonisation, including the genomic tab's multi-zone highlight, the
  epicentre / matrix-origin role markers, hover on the Context tab, and province outlines.

## Token system

Tokens live in `Data/Branding/dashboard-theme.css` alongside the existing `--province-outline-*`
family, and are read through `themeVar()`.

| Token | Value | Role |
|---|---|---|
| `--zone-stroke` | `#fdfaf4` | resting border |
| `--zone-stroke-opacity` | `0.7` | |
| `--zone-stroke-weight-base` | `1.7` | weight at z9 |
| `--zone-stroke-ramp-min` | `0.6` | ramp floor |
| `--zone-stroke-ramp-max` | `1.15` | ramp ceiling |
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
| `--zone-nodata-stroke` | `#6b635a` | no value for the active layer |
| `--zone-nodata-stroke-opacity` | `0.45` | |
| `--zone-role-stroke` | `#111` | epicentre / matrix-origin marker |
| `--zone-role-weight-mult-origin` | `1.6` | × resting |
| `--zone-role-weight-mult-epicenter` | `1.35` | × resting |

The theme layer is optional — `load_theme_css()` skips it when the file is absent — so **every
`themeVar()` call must pass the full value above as its JS fallback**, the way
`themeVar("--province-outline-weight", "1")` already does. The dashboard must render correctly
with no theme file at all.

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

### No-data zones

Zones with no value for the active layer currently draw `#111` over `fillOpacity: 0` — outline
only, no fill. Off-white there vanishes against the CARTO light basemap, so these keep a warm
grey stroke (`--zone-nodata-stroke`). This covers both the `!has` branch in `styleFn` and the
two early-return branches in `epiTrendsStyleFn`.

### Role markers

Epicentre and matrix-origin zones keep `#111` — the darker casing colour was tried and judged
not different enough to be worth the change. Their **weights** are rebased onto the ramp as
multipliers, because their current fixed values (1.6 for the hub, `zoomWeight(0.5)` for the
epicentre) would render *thinner* than the new 1.7 px resting border.

### Province outlines

Provinces keep their gold resting colour so the province layer still reads as distinct from the
zone layer, but adopt the same state grammar:

| State | Now | After |
|---|---|---|
| Resting | `#9b7d4e`, w1.0 (1.4 wide) | unchanged |
| Hover | `#b23b2e`, w1.5 (2.0 wide) | white lift, `#ffffff` × 1.7 |
| Selected | `#b23b2e` (same as hover) | cased amber, as zones |

Province multipliers apply to the **province** resting weight (`--province-outline-weight`, or
`--province-outline-weight-wide` in province scope), not to the zone ramp — province outlines
are not zoom-scaled today and stay that way.

Today a single `trendsHoveredProvince` variable serves both hover and selection, and hover is
suppressed entirely once any province is selected. These separate: hover applies to
non-selected provinces, and the selected province ignores hover — the province-level reading of
requirement 3. This is a deliberate behaviour change.

## Architecture

### Selection rings in a dedicated pane

Selection moves out of the zone polygon and into its own pane, so requirement 4 holds as a
property of the render tree rather than as ordering discipline at eight call sites.

A `SelectionRing(paneName, zIndex)` factory creates a ring layer whose `set(features)` takes
GeoJSON features and draws, per feature, two non-interactive `fill: none` paths — casing first,
inner ring second. It takes features rather than keys so the same factory serves both zones
(keyed by `nom`) and provinces (keyed by province name); resolving a key to its feature stays
with the caller. Two instances:

| Instance | Pane | z-index | Rationale |
|---|---|---|---|
| Zone rings | `zone-selection` | 460 | above zone polygons (400) and epi-links (455) |
| Province rings | `province-selection` | 560 | above province outlines (550) |

Both panes get `pointer-events: none` so clicks fall through to the polygon underneath and
click-to-deselect keeps working.

### Single source of truth for selection

Selection state stays where it is — `mapSelectedNom`, `trendsSelectedKey`, `contextSelectedNom`,
`epiSelectedNom`, `genomicHighlightNoms` — rather than being merged, which would touch every
view's logic. Instead one derived accessor feeds one painter:

```js
currentSelectedNoms()    // reads activeView, returns the active set (array)
refreshZoneSelection()   // = zoneRings.set(currentSelectedNoms())
```

Every site that changes a selection calls `refreshZoneSelection()`. One code path paints
selection for all five tabs, so requirement 2 is enforced structurally. The array signature
covers the genomic tab's multi-zone highlight without a special case.

Province selection is refreshed on its own path, from `applyProvinceOutlineStyles()`, since it
is driven by a different key space and a different pane.

### New API in `Scripts/assets/engine.js`

- `zoneWeight(zoom)` — the ramp above
- `zoneStroke(state)` — style object for `rest` | `hover` | `nodata` | `epicenter` | `origin`
- `SelectionRing(pane, zIndex)` → `{ set(featuresOrNoms), clear(), redraw() }`
- `currentSelectedNoms()` / `refreshZoneSelection()`

### What is removed

- The selection-colour branches in `styleFn` (the selected zone's fill bump to `fillOpacity:
  0.85` stays — only the stroke moves out) and in `epiTrendsStyleFn`
- The nine duplicated `setStyle({… color: "#ffae42"})` sites: three hover
  (`engine.js:1741, 1749, 1754`) collapse into `zoneStroke("hover")`, and six selection
  (`engine.js:1772, 1862, 1867, 2540, 2813, 2987`) disappear entirely into the ring layer
- `contextSelectedLayer` and its `resetStyle` bookkeeping, since Context no longer paints
  selection onto the polygon; this also simplifies `clearSearchHighlight()`, which currently has
  to special-case it

### Hover

Each hover handler gains one early return: if the zone is in `currentSelectedNoms()`, do nothing
(requirement 3). Handlers keep their `bringToFront()` — harmless now that the ring is in a
higher pane.

### Redraw triggers

Ring weights are zoom-dependent, so rings rebuild on `zoomend` alongside
`restyleZonesForActiveView()`, and on view switch.

## Per-view behaviour

| View / scope | Resting | Hover | Selected |
|---|---|---|---|
| Snapshot | token | white lift | cased amber |
| Trends — national | token | — | — |
| Trends — province | suppressed (weight 0, unchanged) | province white lift | province cased amber |
| Trends — health zone | token | white lift | cased amber |
| Spatial risk | token, dimming to 0.12 for non-focus zones retained | white lift | cased amber |
| Context | token | white lift (new) | cased amber |
| Genomic | token | — (unchanged) | cased amber, multi-zone |

Two deliberate asymmetries:

- **Genomic keeps no zone hover.** Its zone interaction stays minimal until the coordinator work
  lands, matching the existing comment at `engine.js:1731`. Its selection still unifies.
- **Trends province scope keeps zone strokes suppressed.** Province outlines are the line work in
  that scope; 519 off-white zone borders underneath would fight them. Hovering a zone there
  continues to highlight its parent province rather than the zone, as it does today — the
  province outline layer is `interactive: false`, so zone mouseover is what drives it.

## Edge cases

- `tearDownHoverDecoration()` on map move must not clear the ring — it lives in another pane and
  is not hover decoration, so it survives naturally. Assert this in review.
- `geoLayer.resetStyle()` on mouseout stops being dangerous: selection colour is no longer in
  `styleFn`, so there is nothing left for it to clobber.
- A zone selected in Spatial risk while `epiZoneVisible()` is false still gets its ring —
  selection is not conditional on layer visibility.
- View switches rebuild the ring; `leaveEpiTrendsView()` and the other leave paths clear it.

## Verification

There is no JS test infrastructure — `tests/` is pytest over the build — so two layers:

1. **Guard test** in `tests/`: assert every token above exists in
   `Data/Branding/dashboard-theme.css`, and that `Scripts/assets/engine.js` contains no residual
   `#ffae42` / `#1a1a1a` / `#9a7a16` zone-styling literals. This encodes requirement 2 directly:
   the tabs cannot silently drift apart again.
2. **Manual pass** on a real build (`python3.9`, sibling `../BDBV2026-Data/build`, served over
   HTTP): five tabs × three zoom levels, checking each requirement — in particular, select a
   zone, hover its neighbour, and confirm the ring is untouched.

## Out of scope

Case markers, flow arcs, genome-count circles, the epi-links overlay, and genomic zone hover.

## Files touched

| File | Change |
|---|---|
| `Data/Branding/dashboard-theme.css` | new token block |
| `Scripts/assets/engine.js` | ramp, `zoneStroke`, `SelectionRing`, derived selection, call-site cleanup |
| `tests/test_zone_state_styling.py` | new guard test |

`assets/` and `output/` at the repo root are CI-generated build artifacts and must not be edited
by hand.
