# Unified health-zone search — design

Date: 2026-08-14
Branch: `unified-zone-search`

## Problem

Health-zone search exists three times over, with three different behaviours and
two different visual vocabularies, and is missing entirely from two tabs where
it belongs.

| Tab | Element | Lives in | Index | Keyboard | Zooms map | On select |
|---|---|---|---|---|---|---|
| Current Snapshot (`map`) | `#zone-search-wrap` | inside the dark LAYER panel (`#controls`) | health zones | ↑ ↓ Enter Esc | yes, `fitBounds` | focuses zone, keeps name in the input |
| Epi Trends (`trends`) | `#trends-search-wrap` | light right rail; relocated to the map corner only below 700px | provinces + health zones | none | no | switches scope, sets selection, clears input |
| Spatial Risk (`epi-trends`) | `#epi-search-wrap` | light `.epi-controls` in the right rail | health zones | none | no | selects + scrolls the table row, clears input |
| Public Health Context (`context`) | — | `#controls` is `display:none` on this view, so the search is unreachable | — | — | — | — |
| Genomic Epi (`genomic-epidemiology`) | — | none | — | — | — | — |

Consequences: the same task feels different on every tab; only one of the three
supports the keyboard; only one zooms the map, so on Trends and Spatial Risk a
searched zone can stay off-screen; the Context tab has a `selectHealthZone()`
branch that no visible control can reach.

## Goals

1. One search component, one behaviour, one visual treatment, across all five
   non-stub tabs.
2. It stands alone over the map rather than being embedded in a panel or rail.
3. Full keyboard operation: type, `↑`/`↓` through matches, `Enter` to lock in.
4. Selecting a location always zooms the map to it, on every tab.

## Non-goals

- Fuzzy matching, ranking, or diacritic folding. Matching stays the current
  case-insensitive substring test over `name + nom`.
- Any change to what a *selection* means on each tab. The search is a new way to
  reach each tab's existing selection state, not a redefinition of it.
- Clearing a tab's selection from the search box. That stays what it is today —
  clicking empty map (or the tab's own affordance).
- Fixing `#genomic-panel`'s fixed `min(634px, 70vw)` width, which leaves the map
  a sliver on narrow screens. Pre-existing and out of scope.

## Approach

**One DOM node, per-view behaviour table.** Every page ships all views' markup
but activates exactly one (see `common/chrome.py`), so a single `#zone-search`
element — a sibling of `#map` — can serve every tab. CSS positions it per
`body.view-*`; one JS controller owns the index, filtering, keyboard, and
open/close state; a `ZONE_SEARCH_VIEWS` table supplies the per-view differences.

Rejected alternatives:

- *Per-view nodes driven by a shared factory.* Keeps three DOM nodes and three
  positioning contexts while delivering none of goal 2. Only justified if two
  searches could be visible simultaneously, which they cannot.
- *Extract just the keyboard helper.* Cheapest diff, satisfies goal 3 alone, and
  leaves the visual and behavioural divergence — the actual complaint — intact.

## Component

Markup moves out of `#controls` into `#viewport-area`, as a sibling of `#map`:

```html
<div id="zone-search">
  <input type="search" id="zone-search-input" autocomplete="off" spellcheck="false"
         role="combobox" aria-autocomplete="list" aria-controls="zone-search-results"
         aria-expanded="false" aria-activedescendant=""
         data-i18n-placeholder="ui.zone_search_placeholder"
         placeholder="Type a health zone name…"
         data-i18n-aria="ui.zone_search" aria-label="Search health zone" />
  <div id="zone-search-results" role="listbox" hidden></div>
</div>
```

The input and results ids are unchanged, so `ui.zone_search`,
`ui.zone_search_placeholder` and `ui.zone_search_no_matches` carry over as-is.
No new locale keys are needed: Trends keeps using the existing
`ui.trends_search_placeholder` ("Search for a location…"), applied by the
controller at init because that tab alone lists provinces.

Each option gets a real id (`zone-search-opt-<i>`) and `aria-selected`, and the
input's `aria-activedescendant` tracks the active one. Today's code moves an
`.active` class and tells assistive technology nothing.

`L.DomEvent.disableClickPropagation` / `disableScrollPropagation` apply to the
wrapper, as they already do, since it overlays the Leaflet container.

## Styling

The light rail vocabulary wins (it is already used by two of the three
searches). It is promoted out of `.location-search-wrap` / `.location-search-results`
into the component itself:

- input: `#ffffff` on `1px solid #e7e3db`, radius 4, 12px, `#2a2a27` text;
  focus is `border-color:#9b7d4e` plus a `0 0 0 1px rgba(155,125,78,0.35)` ring.
- results: white panel, `1px solid #e7e3db`, radius 4, `max-height:calc(5 * 32px)`
  with `overflow-y:auto`, `z-index:1100`.
- option: full-width left-aligned button, `min-height:32px`, hairline separators.
- active option (keyboard *or* pointer): `background:#f3f1ec; color:#9b7d4e`.
- empty state: `.zone-search-empty`, italic `#9c968b`.

Because the component now floats over a basemap rather than sitting inside a
light rail, the input gains the drop shadow the dropdown already carries, so it
reads as map chrome.

Deleted: the dark `#zone-search-input` / `#zone-search-results` /
`.zone-search-option` block, and the `.location-search-wrap` /
`.location-search-results` block. Nothing else references either.

## Placement

Two new width tokens let the search offset and the panel it sits beside share a
single source of truth instead of repeating the width expression:

```css
--layer-panel-width: min(340px, calc(100vw - 24px));   /* #controls */
--context-panel-width: min(280px, calc(50vw - 24px));  /* #context-national */
--zone-search-height: 32px;                            /* input height */
```

`--zone-search-height` is not a description of the input, it *sets* it: the
input takes `min-height: var(--zone-search-height)`, and the narrow-screen rules
that displace `#controls` / `#epi-trends-legend` offset by it. One value, so the
gap cannot drift open or closed.

Wide screens (≥ 700px):

| View | `#zone-search` position |
|---|---|
| `map` | `top:12px; left:calc(12px + var(--layer-panel-width) + 10px)` — right of LAYER |
| `context` | `top:12px; left:calc(12px + var(--context-panel-width) + 10px)` — right of the National/Provincial Response panel |
| `trends`, `epi-trends`, `genomic-epidemiology` | `top:12px; left:12px` |
| `clinical-symptoms`, `surveillance-testing` | hidden via `body.stub-view` |

Narrow screens (≤ 700px) — the search takes the `12px/12px` corner on every tab,
and whatever already occupied that corner drops below it by
`calc(var(--zone-search-height) + 8px)`:

| View | Corner today | Action |
|---|---|---|
| `map` | `#controls` at `top:12px` | push `#controls` down |
| `epi-trends` | `#epi-trends-legend` is repositioned to `top:12px; left:12px` | push it down |
| `context` | `#context-national` already sits at `top:clamp(128px, 24vh, 200px)` | none needed |
| `trends` | `#trends-legend` moves to `top:12px; right:12px` | none needed |
| `genomic-epidemiology` | nothing | none needed |

Width: `min(240px, calc(100vw - 24px))` on wide screens. On narrow `map`, the
opposite corner holds `#info` collapsed to a title bar capped at
`min(160px, calc(60vw - 18px))`, so the search is additionally clamped to clear
it. Exact clamp to be confirmed against a rendered page during implementation.

The rails narrow `#map` itself (`body.view-trends #map { right: var(--trends-panel-width) }`
and the Spatial Risk equivalent), so `top:12px; left:12px` is the corner of the
*visible* map on those tabs, and `fitBounds` frames zones inside the visible
area, with no extra offset maths.

## Behaviour

`TRENDS_LOCATION_INDEX` is renamed `LOCATION_INDEX` — it is no longer Trends-specific.
It stays what it is: every province plus every health zone, built from
`ZONE_SEARCH_INDEX` and `PAYLOAD.province_boundaries`, sorted by label, each
entry `{id, label, kind, haystack}` with `kind ∈ {province, health_zone}`.

One controller owns query filtering, list rendering, the active index, keyboard
handling, and outside-click dismissal. A per-view table supplies the rest:

```js
const ZONE_SEARCH_VIEWS = {
  "map":                  {kinds: ["health_zone"], placeholder: "ui.zone_search_placeholder",   select: …},
  "context":              {kinds: ["health_zone"], placeholder: "ui.zone_search_placeholder",   select: …},
  "trends":               {kinds: ["province", "health_zone"], placeholder: "ui.trends_search_placeholder", select: …},
  "epi-trends":           {kinds: ["health_zone"], placeholder: "ui.zone_search_placeholder",   select: …},
  "genomic-epidemiology": {kinds: ["health_zone"], placeholder: "ui.zone_search_placeholder",   select: …},
};
```

| View | Lists | `select(entry)` does |
|---|---|---|
| `map` | zones | `setMapSelection(nom)` |
| `context` | zones | `selectContextZone(nom)` |
| `trends` | provinces + zones | sync the scope buttons to `entry.kind`, `setTrendsScope(kind)` if it changed, `setTrendsSelection(id)` |
| `epi-trends` | zones | `setEpiSelected(nom)`, then scroll the matching `tr[data-nom]` into view |
| `genomic-epidemiology` | zones | `genomicMapHooks._emitZoneClick(nom)` |

Then, shared by all five and applied after `select()`:

```js
map.fitBounds(bounds, {padding: [40, 40], maxZoom: 10});
```

with zone bounds from the matching `geoLayer` layer (`findGeoLayerByNom`) and
province bounds from the matching `province_boundaries` feature. If no geometry
is found the selection still applies and the zoom is skipped.

**After a selection the input clears and the dropdown closes**, on every tab.
Focus stays in the input so the next search can start immediately. The box is a
query field, not a state indicator — the selection remains visible where it
already is (zone highlight, info/context panel, highlighted table row, plot
titles). This is today's Trends and Spatial Risk behaviour, generalised.

Keyboard:

| Key | Effect |
|---|---|
| `↓` | opens the list if closed and there is a query; otherwise moves the active option down |
| `↑` | moves the active option up |
| `Enter` | selects the active option |
| `Esc` | closes the list; pressed again (or on a closed list) clears the query text |
| `Tab` | closes the list without selecting |

`↑`/`↓` clamp at the ends rather than wrapping, matching today's Snapshot
behaviour. The first match is active as soon as results render, so `Enter` on a
fresh query picks the top hit. Pointer hover *moves* the active index rather
than painting its own highlight — today a hovered row and the keyboard-active
row can both look selected at once.

Results cap: 40 entries (today's Trends/Spatial Risk cap; Snapshot's 12 was the
odd one out and is the tightest, so it goes).

## Removals

- markup: `#trends-search-wrap`, `#trends-search-slot`, `#epi-search-wrap`, and
  the `.epi-controls` wrapper left empty by the last of these.
- `engine.js`: `wireTrendsSearchSlot()`, `renderTrendsSearchResults()`,
  `renderEpiSearchResults()`, `epiClearSearchUi()`, the `opts.fromSearch`
  branch and parameter of `setTrendsSelection()`, and both duplicate
  input/results/outside-click wiring blocks.
- `dashboard.css`: the dark `#zone-search-*` / `.zone-search-option` block, the
  `.location-search-*` block, `#trends-search-slot`'s base and narrow-screen
  positioning, and `.epi-controls`.

Net effect is negative lines in both `engine.js` and `dashboard.css`.

## Testing

`tests/test_zone_search.py`, in the static-source-guard style of
`tests/test_zone_state_styling.py`:

1. `common/chrome.py` contains exactly one `id="zone-search-input"`, and no
   `trends-search-input`, `epi-search-input`, `trends-search-wrap`,
   `epi-search-wrap`, or `trends-search-slot`.
2. `#zone-search` is a sibling of `#map` in `BODY_TEMPLATE`, not nested inside
   `#controls` or any rail.
3. The `ZONE_SEARCH_VIEWS` keys in `engine.js` equal exactly the non-stub view
   ids in `chrome.NAV_ITEMS` — so a tab added later cannot silently ship without
   a search, and a removed tab cannot leave a dangling entry.
4. No `.location-search-wrap`, `.location-search-results`, or
   `.zone-search-option` selector survives in `dashboard.css`, and none is
   referenced from `engine.js`.
5. `dashboard.css` positions `#zone-search` for every non-stub `body.view-*`.
6. Each of `--layer-panel-width`, `--context-panel-width` and
   `--zone-search-height` is declared once and read by both the search rule and
   the rule for the panel it offsets from — the same token-drift guard the zone
   styling tests apply.

Manual verification, after a build, served over HTTP (see the build/test notes
in the repo memory): all five tabs at a wide and a narrow viewport — type,
arrow, `Enter`, confirm the map zooms and the tab's own selection state updates;
confirm nothing overlaps in the top-left corner at either width.

## Risks

- **Corner collisions.** Two were found by reading the CSS (`#controls` on
  Snapshot, `#epi-trends-legend` on narrow Spatial Risk) and one near-miss
  (`#context-national`). Others may only show up on a rendered page; the manual
  pass at both widths is the check.
- **Narrow Snapshot width.** The clamp that keeps the search clear of the
  collapsed `#info` bar is a guess until measured; tune it against a screenshot.
- **Genomic reach.** `select()` there routes through `genomicMapHooks._emitZoneClick`,
  the same path a map click takes, so no new engine↔page contract is added. A
  selection made inside the phylogeny will not be reflected in the search box,
  which is fine — the box is a query field, not a state indicator.
