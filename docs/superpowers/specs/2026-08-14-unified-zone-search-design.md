# Unified health-zone search — design

Date: 2026-08-14
Branch: `unified-zone-search`
Revision: 3 — incorporates both passes of
`2026-08-14-unified-zone-search-design-review.md` (see §Review dispositions).

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
branch (`engine.js:2320-2322`) that no visible control can reach.

## Goals

1. One search component, one behaviour, one visual treatment, across all five
   non-stub tabs — with one deliberate exception: the search is hidden on the
   Genomic tab below 700px (see §Known gaps).
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
- Making the Genomic tab responsive. `#genomic-panel` has no `max-width:700px`
  rule at all, so at 360px it is `70vw = 252px` and the map is a ~108px strip.
  Pre-existing; this spec works around it rather than fixing it.

## Known gaps

- **No search on the Genomic tab below 700px.** The map strip is ~108px wide
  there, so any usable box would float over the phylogeny and any zone selected
  from it would be framed in that strip. Blocked on the non-goal above; a
  phone-sized Genomic tab without a search box is intended, not a regression.

## Standing assumption

The map is constructed with `zoomControl: false` (`engine.js:605`), and the
comment there records that the top-left corner was freed precisely because
"every view either relocates a search box into that corner or expects touch
users to pinch-zoom". Nothing Leaflet-owned competes for `12px/12px`. The whole
placement section rests on this; if a zoom control is ever restored, placement
must be revisited.

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
  <div id="zone-search-empty" hidden></div>
  <div id="zone-search-live" role="status" aria-live="polite" class="visually-hidden"></div>
</div>
```

The input and results ids are unchanged, so `ui.zone_search`,
`ui.zone_search_placeholder` and `ui.zone_search_no_matches` carry over as-is.
One new key pair is needed after all: `ui.zone_search_matches` = `"{n} matches"`
/ `"{n} résultats"`, for the live region below. `tf(path, vars)`
(`engine.js:62-70`) already does `{n}` interpolation, so no new machinery comes
with it. Every per-view key in `ZONE_SEARCH_VIEWS` still resolves to a string
that already exists.

**Three elements, three jobs.** Today `.zone-search-empty` is a bare `<div>`
child of `#zone-search-results[role=listbox]` (`engine.js:2287-2288`), which is
invalid — a listbox may contain only options and groups — and is ignored or
mis-announced. Splitting it:

- `#zone-search-results` — the listbox. Options only.
- `#zone-search-empty` — the **visible** no-matches panel, absolutely positioned
  exactly like `#zone-search-results` and shown *in its place*, never below it.
  This is the position today's message occupies; only its parentage changes.
- `#zone-search-live` — **visually hidden**, announcement only: the match count
  on each render, and the no-matches text. A visible per-keystroke count would
  be a new UI element no existing search has, sitting between the input and the
  list; it belongs to assistive tech alone.

Exactly one of the results panel and the empty panel is ever visible.
`aria-expanded` tracks the listbox only, so it stays `"false"` when there is
nothing selectable.

Each option gets a real id (`zone-search-opt-<i>`) and `aria-selected`, and the
input's `aria-activedescendant` tracks the active one. Today's code moves an
`.active` class and tells assistive technology nothing (`engine.js:2293-2312`).

**No `L.DomEvent.disableClickPropagation` / `disableScrollPropagation`.**
`#zone-search` is a *sibling* of `#map`, not a descendant of the Leaflet
container, so its events never reach Leaflet's container-bound handlers and
there is nothing to suppress. Today's calls on `#zone-search-wrap`
(`engine.js:2336-2339`) are already no-ops for the same reason (`#controls` is
likewise outside the container); they are dropped rather than carried forward
with a corrected comment, and the CSS carries a note saying why none are needed.

## Styling

The light rail vocabulary wins (it is already used by two of the three
searches). It is promoted out of `.location-search-wrap` / `.location-search-results`
into the component itself:

- input: `#ffffff` on `1px solid #e7e3db`, radius 4, 12px, `#2a2a27` text,
  `min-height: var(--zone-search-height)`; focus is `border-color:#9b7d4e` plus
  a `0 0 0 1px rgba(155,125,78,0.35)` ring.
- results **and** empty panel share one positioning rule: `position:absolute;
  left:0; right:0; top:100%`, white, `1px solid #e7e3db`, radius 4, drop shadow.
  Results additionally take `max-height: min(calc(5 * 32px), 30vh)` with
  `overflow-y:auto`. The `30vh` arm matters on narrow Trends/Spatial Risk, where
  the map is `height:40vh` (`dashboard.css:808`, `852`) — an unclamped 160px
  list opens over essentially the entire map.
- option: full-width left-aligned button, `min-height:32px`, hairline separators.
- active option (keyboard *or* pointer): `background:#f3f1ec; color:#9b7d4e`.
- empty panel text: italic `#9c968b`, as today's `.zone-search-empty`.
- `.visually-hidden`: the standard 1px-clip idiom. New utility class; nothing in
  the stylesheet has one yet.

Because the component now floats over a basemap rather than sitting inside a
light rail, the input gains the drop shadow the dropdown already carries, so it
reads as map chrome.

**Stacking.** `#zone-search` takes `z-index:1200` on the wrapper. Without one it
would paint under every panel: `.panel` is `z-index:1000` (`dashboard.css:94`),
as are `#trends-panel` and `#epi-trends-panel`, and `#zone-search` is declared
before them in `BODY_TEMPLATE`. 1200 clears the panels without reaching the
header (1300). A positioned element with a z-index forms a stacking context, so
the dropdown's own `z-index` is resolved *inside* the component — which settles
the otherwise-ambiguous tie with `#epi-float` (also 1100, `dashboard.css:442`):
the whole component paints at 1200, so an open list is above a Spatial Risk
hover readout regardless of source order. 1200 also ties with
`#epi-split-handle` / `#trends-split-handle` (`172`, `247`); they sit at the rail
edge, spatially disjoint from the top-left corner, so the tie never surfaces and
source order (handles later, therefore on top) is harmless.

`body.epi-map-exporting` gains `#zone-search` alongside the overlays it already
hides (`dashboard.css:407-416`). Not for the JPG — that is scoped to
`map.getContainer()` (`engine.js:4119`) and `#zone-search` is outside it — but
because `body.epi-map-exporting #map` goes full-bleed (`418-421`) and every
overlay in that list is hidden to keep it off the screen during the export.

Deleted: the dark `#zone-search-input` / `#zone-search-results` /
`.zone-search-option` block, and the `.location-search-wrap` /
`.location-search-results` block. Nothing else references either.

## Placement

Three bands. **Band A is the unqualified default; bands B and C are carved out
with `max-width` queries only**, in that order, so no viewport width can fall
between two rules. (A `max-width:999px` / `min-width:1000px` pair would leave a
999.5px viewport — browser zoom, fractional DPR — matching neither.) This is
also how the file already handles its 700px boundary, which is inclusive: 700px
itself is band C.

### Tokens

All three are declared once in `:root`, alongside `--epi-panel-width: 50%` and
`--trends-panel-width: 40%` (`dashboard.css:3-7`):

```css
--layer-panel-width: min(340px, calc(100vw - 24px));   /* #controls, dashboard.css:101-105 */
--context-panel-width: min(280px, calc(50vw - 24px));  /* #context-national, 638-646 */
--zone-search-height: 32px;
```

`--layer-panel-width` and `--context-panel-width` are read by two consumers
each: the panel's own width rule, which is unconditional and applies in all
three bands, and the **search-offset rule, which may read them only inside band
A**. The constraint is on the search, not on the panel — see test 6.

`--zone-search-height` is not a description of the input, it *sets* it: the
input takes `min-height: var(--zone-search-height)`, and every displacement rule
in bands B and C offsets by `calc(var(--zone-search-height) + 8px)`. One value,
so the gap cannot drift open or closed.

### Band A — default (≳1000px)

| View | `#zone-search` |
|---|---|
| `map` | `top:12px; left:calc(12px + var(--layer-panel-width) + 10px)` — right of LAYER |
| `context` | `top:12px; left:calc(12px + var(--context-panel-width) + 10px)` — right of the National/Provincial Response panel |
| `trends`, `epi-trends`, `genomic-epidemiology` | `top:12px; left:12px` |
| `clinical-symptoms`, `surveillance-testing` | hidden via `body.stub-view` |

Base width `min(240px, calc(100vw - 24px))`, further clamped on the rail tabs —
see §Rail clamp. No displacement in this band.

### Band B — `@media (max-width: 999.98px)`

The beside-the-panel layout cannot be used here. On `map` the search would span
362–602px while `#info` (`right:12px; max-width:340px`, `dashboard.css:144`)
starts at `100vw − 352`, so they meet at ~954px; on `context` the figures are
302–542px against `#context` at `100vw − 292`, meeting at ~834px.

`#info` is content-sized under a bare `max-width`, so on `map` the space
actually available is not derivable in CSS — clamping there would need JS
measurement on every resize, and a "below the panel" placement would need panel
heights, which are content-driven. `#context` *does* carry a definite
`width:min(280px, calc(50vw - 24px))` (`647-655`), so the Context tab alone
could be clamped in pure CSS; it follows `map` anyway so the two tabs do not
diverge. A third breakpoint costs one media query and reuses the displacement
machinery band C needs regardless.

So in band B the search takes the corner on **every** tab, and the two views
with something already at `top:12px; left:12px` displace it downward:

| View | Displaced |
|---|---|
| `map` | `#controls` |
| `context` | `#context-national` |
| `trends`, `epi-trends`, `genomic-epidemiology` | nothing — their top-left is empty in this band |

`#info` needs no displacement here: at ≥701px it starts at `100vw − 352 ≥ 349`,
clear of the search's 252px right edge.

### Band C — `@media (max-width: 700px)`

The search owns the whole top row: `top:12px; left:12px; width:calc(100vw - 24px)`,
and the rail clamp is switched off (the rails stack below a full-width map at
this width). Everything positioned at `top:12px` in this band drops by
`calc(var(--zone-search-height) + 8px)`:

| View | Displaced | Currently at |
|---|---|---|
| `map` | `#controls`, `#info` | `top:12px` (`898`, `899`) |
| `trends` | `#trends-legend` | `top:12px; right:12px` (`832-838`) |
| `epi-trends` | `#epi-trends-legend` | `top:12px; left:12px` (`868-874`) |
| `context` | nothing | `#context-national` / `#context` already at `top:clamp(128px, 24vh, 200px)` (`875-886`) |
| `genomic-epidemiology` | — | search is hidden here (§Known gaps) |

A full-width search removes the clamp problem entirely. The earlier draft tried
to size the search to clear a collapsed `#info`, citing a
`min(160px, calc(60vw - 18px))` cap — that cap is `#controls.collapsed`
(`dashboard.css:907`), not `#info`. `#info` gets only `max-width:60vw` (`795`)
and `wirePanelToggles()` collapses it *on load* (`engine.js:4223-4224`), so the
user can expand it back to 60vw at any moment. No static clamp derived from a
collapsed width could have been correct.

**Displacement costs height.** Where a displaced panel carries a `max-height`,
the same rule reduces it by the same offset, so the panel's bottom edge does not
move toward the footer chrome. That is `#context-national` in band B and `#info`
in band C (both `max-height:80vh`, tightened again under `@media (max-height:500px)`
at `923` — a landscape phone is band C). `#controls`, `#trends-legend` and
`#epi-trends-legend` carry none and need no adjustment.

### Rail clamp

Band B fixes collisions with *floating panels*; the rail tabs need a separate
clamp, because a rail can be narrower than the search and `#zone-search` at
z-index 1200 floats over it rather than being clipped. `TRENDS_SPLIT_MAX` and
`EPI_SPLIT_MAX` are both 72 (`engine.js:3544`, `3861`), so the visible map can
be 28% — 196px at 701px against a 252px right edge — and the widths persist in
`localStorage`, so a user who once dragged the split wide meets it on every
later visit. Genomic needs no user action at all: `min(634px, 70vw)` leaves a
210px strip at 701px, and the search overflows from 701px until `30vw` reaches
252px at ~840px.

`#zone-search` is positioned within `#viewport-area`, and the rail widths are
percentages, so the clamp is pure CSS and tracks a live drag for free:

```css
body.view-trends     #zone-search { width: min(240px, calc(100% - var(--trends-panel-width) - 24px)); }
body.view-epi-trends #zone-search { width: min(240px, calc(100% - var(--epi-panel-width) - 24px)); }
body.view-genomic-epidemiology #zone-search { width: min(240px, calc(100% - var(--genomic-panel-width, 70vw) - 24px)); }
```

`--genomic-panel-width` is new and is published by `genomic.js`: `applyWidth()`
(`genomic.js:745-751`) is already the single writer of `panel.style.width`, so
it also sets the custom property on `:root`, and the module sets it once at init
for the CSS default. They cannot drift, being one assignment apart. Without it
the genomic clamp would fall back to the `70vw` default and stop tracking drags
(`maxW()` is `0.7 * innerWidth`, `genomic.js:739`).

The clamp applies in bands A and B and is disabled in band C.

### Visible-map framing

On Trends and Spatial Risk the rails narrow `#map` itself
(`dashboard.css:162`, `223-225`), so `left:12px` is the corner of the *visible*
map and `fitBounds` needs no offset. **The Genomic tab is the exception**: there
is no `body.view-genomic-epidemiology #map { right: … }` rule, so
`#genomic-panel` (`1167-1174`) overlays a full-width map. See §The shared zoom.

## Behaviour

`TRENDS_LOCATION_INDEX` is renamed `LOCATION_INDEX` — it is no longer
Trends-specific. It stays what it is: every province plus every health zone,
built from `ZONE_SEARCH_INDEX` and `PAYLOAD.province_boundaries`, sorted by
label, each entry `{id, label, kind, haystack}` with
`kind ∈ {province, health_zone}`. `ZONE_SEARCH_INDEX` becomes a private
intermediate — nothing else reads it once `renderZoneSearchResults()` is gone —
and stays only as the zone-side builder.

One controller owns query filtering, list rendering, the active index, keyboard
handling, and outside-click dismissal. A per-view table supplies the rest:

```js
const ZONE_SEARCH_VIEWS = {
  "map":                  {kinds: ["health_zone"], placeholder: "ui.zone_search_placeholder", aria: "ui.zone_search",   select: …},
  "context":              {kinds: ["health_zone"], placeholder: "ui.zone_search_placeholder", aria: "ui.zone_search",   select: …},
  "trends":               {kinds: ["province", "health_zone"], placeholder: "ui.trends_search_placeholder", aria: "ui.trends_search", select: …},
  "epi-trends":           {kinds: ["health_zone"], placeholder: "ui.zone_search_placeholder", aria: "ui.zone_search",   select: …},
  "genomic-epidemiology": {kinds: ["health_zone"], placeholder: "ui.zone_search_placeholder", aria: "ui.zone_search",   select: …},
};
```

Stub views have no entry; the controller no-ops on a missing entry rather than
dereferencing `.kinds`.

**The active view is read from `document.body.dataset.initialView`, not from
`activeView`.** `bootstrapInitialView()` runs at the very bottom of `engine.js`
(`4288-4293`), long after the search block, so `activeView` is still its `"map"`
default when the controller initialises — keying off it would give every page
the Snapshot behaviour. Every page is a single view (the nav is real cross-page
`<a>` links, and `setActiveView()` is called exactly once, from that
bootstrap), so one read at init is sufficient and no re-keying is needed.

### Per-view i18n must be applied to attributes, not properties

`applyStaticI18n()` re-reads `data-i18n-aria` and `data-i18n-placeholder` from the DOM
on **every** language toggle (`engine.js:276-284`). Setting `input.placeholder`
or `input.setAttribute("aria-label", …)` directly would therefore survive only
until the first EN/FR switch — the Trends box would show "Search for a
location…" until the user toggles language and "Type a health zone name…"
forever after, a bug visible only in the French build. The controller rewrites
the **`data-i18n-*` attributes** at init from the view's entry, then calls
`applyStaticI18n()`.

The `aria` key is per-view for the same reason the placeholder is: the markup's
`ui.zone_search` = "Search health zone" / "Rechercher une zone de santé" is
factually wrong on Trends, the one tab that also lists provinces. `ui.trends_search`
("Search" / "Recherche") already exists in both locales
(`locales/en.yaml:131`, `fr.yaml:131`), so this still adds no keys.

### What `select(entry)` does

| View | Lists | `select(entry)` |
|---|---|---|
| `map` | zones | `setMapSelection(nom)` |
| `context` | zones | `selectContextZone(nom)` |
| `trends` | provinces + zones | sync the scope buttons to `entry.kind`, `setTrendsScope(kind)` if it changed, then `setTrendsSelection(id)` — in that order, since `setTrendsScope()` nulls the selection |
| `epi-trends` | zones | `setEpiSelected(nom)`, then scroll the matching `tr[data-nom]` into view |
| `genomic-epidemiology` | zones | `genomicMapHooks._emitZoneClick(nom, {toggle: false})` |

`setEpiSelected` is top-level (`engine.js:1318`), but the scroll half currently
lives in `epiApplyHealthZone` inside the `wireEpiTrendsUi` IIFE and uses that
closure's `tbody` (`3970-3979`). The module-level table re-queries
`#epi-trends-tbody` itself rather than hoisting a chunk of the IIFE. Note also
that `wireEpiTrendsUi` returns early when there is no invasion data
(`3950-3954`) and hides the tab; the shared controller has no such guard, so in
that build the Spatial Risk search is simply inert — harmless, since the page is
unreachable from the nav.

### The genomic path is a toggle and must not be

`genomic.js:633` is `if (key === activeKey) { clearAll(); return; }` —
`_emitZoneClick` deliberately toggles so that clicking the same polygon twice
clears. Under this design the input clears after every selection, so a user who
searches "Bunia", looks away, and searches "Bunia" again would **deselect** it
while the shared `fitBounds` still zoomed to it: the map says "here it is", the
tree and cases panel say "nothing selected", and nothing on screen explains why.

Fix: thread an options argument along the existing path rather than adding a
hook name — `_emitZoneClick(nom, opts)` → `onZoneClickCb(nom, opts)` →
`selectZone(nom, opts)`, where `opts.toggle === false` skips the early return.
Toggling stays the default, so real map clicks are unchanged.

**Readiness.** `hooks.onZoneClick(...)` is registered inside `startCoordinator`
(`genomic.js:651`), which runs only once the tree/tip data resolves, and
`_emitZoneClick` no-ops until then (`engine.js:3810`). A search issued during
load would zoom the map and silently select nothing — and would do so
permanently if the genomic payload is absent or the tree fails to mount. So
**registration is the readiness signal**: on this view `#zone-search` starts
hidden, and `onZoneClick(cb)` reveals it. Hiding rather than disabling covers
the never-mounts case with no timer and without leaving a permanently disabled
box that reads as broken. `_emitMarkerClick` shares the same coordinator, so
this one gate covers every genomic entry point.

This is the single place the design reaches back into `genomicMapHooks`, whose
own comment calls it "deliberately tip-agnostic" (`engine.js:3798-3807`). It is
one call from `onZoneClick(cb)` into the search controller, and it is recorded
here so it is a decision rather than a smell.

### The shared zoom

After `select()`, on every tab:

```js
map.fitBounds(bounds, {
  paddingTopLeft: pad,
  paddingBottomRight: [pad[0] + insetX, pad[1]],
  maxZoom: 10,
});
```

**Never pass `padding` alongside either directional key.** Leaflet 1.9.4 —
the build `chrome.py:47` pins — resolves them as
`options.paddingBottomRight || options.padding || [0, 0]`, so a directional key
*replaces* `padding` on that side rather than adding to it, and `[0, 0]` is an
array and therefore truthy. `{padding: pad, paddingBottomRight: [0,0]}` silently
yields zero bottom-right padding on every tab, which is invisible in a
screenshot unless the zone happens to sit near an edge. Test 9 guards it.

- **Zone bounds** come from the matching `geoLayer` layer (`findGeoLayerByNom`).
- **Province bounds** come from the matching `provinceOutlineLayer` layer
  (`engine.js:2421`), reusing the live layer the way `findGeoLayerByNom` does
  rather than recomputing from raw GeoJSON.
- **`pad`** is `[40, 40]` on wide screens and `[16, 16]` at ≤700px, where the
  Trends and Spatial Risk maps are `height:40vh` — ~192px on a 480px viewport,
  of which `[40,40]` would consume 80px.
- **`insetX`** is `0` everywhere except `genomic-epidemiology`, where it is
  `panel.offsetWidth` measured at select time. The panel width is an inline
  style written by `applyWidth()`, so it is read from the element rather than
  parsed back out of the CSS custom property the same function publishes for the
  rail clamp — one quantity, two consumers, each reading it the way its own
  language can.
- `maxZoom: 10` binds only when a geometry is small enough that fitting it would
  zoom past z10 — a large province fits at z6–7 and never reaches the cap — so
  it is a floor on zooming into small units, not a ceiling that distorts large
  ones.
- If no geometry is found, the selection still applies and the zoom is skipped.

**This reverses a documented decision on two tabs.** `engine.js:2813-2819`
records that `fitMapToTrendsSelection()` was removed because, once the map and
plots became separate non-overlapping columns, "that auto-pan just made the map
jump around distractingly on every click". Goal 4 reinstates a map move on
Trends and Spatial Risk **for search only**, which is defensible — a searched
zone can be offscreen, a clicked one cannot — but it produces a deliberate
asymmetry: on those tabs, *clicking* a zone does not move the map while
*searching* the same zone does. That comment must be updated in the same change
to say so, or the next reader deletes one side for consistency.

### After a selection

The input clears, both panels close, and the live region is emptied — on every
tab. The box is a query field, not a state indicator; the selection stays
visible where it already is (zone highlight, info/context panel, highlighted
table row, plot titles). This is today's Trends and Spatial Risk behaviour,
generalised.

Focus stays in the input on wide screens so the next search can start
immediately, but is **blurred at ≤700px** (same `matchMedia("(max-width: 700px)")`
the file already uses): keeping the on-screen keyboard up would cover roughly
half of a map that was just zoomed to the thing the user asked for.

At ≤700px a search-driven selection also **expands the tab's collapsed detail
panel** — `#info` on `map`, `#context` on `context`. `wirePanelToggles()`
auto-collapses every `.panel-toggle` panel on load at that width
(`engine.js:4223-4224`), so without this the only feedback from a narrow search
is a zoom and a highlight on a map the user may not recognise.

This must go through the toggle, not the class. `setCollapsed()`
(`engine.js:4200-4208`) is private to the `wirePanelToggles()` IIFE and owns
both the `.collapsed` class **and** the `+`/`−` glyph on the button; stripping
the class alone leaves an open panel showing `+`, whose next tap collapses
nothing. `wirePanelToggles()` exports a module-level `expandPanel(panelId)` —
the same discipline the `#epi-trends-tbody` re-query applies above.
`#context-national` is also auto-collapsed at that width and is deliberately
left collapsed; the search selects a *zone*, and `#context` is where zone
context appears.

### Keyboard

| Key | Effect |
|---|---|
| `↓` | opens the list if closed and there is a query; otherwise moves the active option down |
| `↑` | moves the active option up |
| `Enter` | selects the active option; no-op when the list is closed |
| `Esc` | closes the list; pressed again, or on a closed list, clears the query |
| `Tab` | closes the list without selecting |

`↑`/`↓` clamp at the ends rather than wrapping, matching today's Snapshot
behaviour. The first match is active as soon as results render, so `Enter` on a
fresh query picks the top hit. Pointer hover *moves* the active index rather
than painting its own highlight — today a hovered row and the keyboard-active
row can both look selected at once.

The first `Esc` calls `preventDefault()`. Chrome and WebKit clear an
`input[type=search]` natively on `Esc`, which would otherwise pre-empt the
two-stage behaviour. WebKit's native ✕ needs no special handling: it fires an
`input` event, which the existing handler already treats as "empty query →
close".

Results cap: 40 entries (today's Trends/Spatial Risk cap; Snapshot's 12 was the
odd one out and is the tightest, so it goes).

## Removals

Markup:

- `#trends-search-wrap`, `#trends-search-slot`, `#epi-search-wrap`, and the
  `.epi-controls` wrapper left empty by the last of these.

`engine.js` — the Snapshot controller is replaced just as fully as the other two,
and is named here because §Removals is the checklist the diff gets read against:

- Snapshot: `closeZoneSearchResults()` (`2266`), `renderZoneSearchResults()`
  (`2275`), `setZoneSearchActive()` (`2303`), `selectHealthZone()` (`2314`), the
  `zoneSearchMatches` / `zoneSearchActiveIdx` / `zoneSearchWrap` module state
  (`2252-2254`), the wiring block (`2341-2378`), and the two
  `L.DomEvent.disable*Propagation` calls (`2336-2339`).
- Trends: `wireTrendsSearchSlot()`, `renderTrendsSearchResults()`, the
  `opts.fromSearch` branch and parameter of `setTrendsSelection()`, and the
  search half of `wireTrendsPanelUi()`.
- Spatial Risk: `renderEpiSearchResults()`, `epiClearSearchUi()`,
  `epiApplyHealthZone()`, and the search half of `wireEpiTrendsUi()`.

`dashboard.css`: the dark `#zone-search-*` block and the dark `.zone-search-option`
rules (the class name is retained by the new component — only its styling is
replaced), the `.location-search-*` block, `#trends-search-slot`'s base and
narrow-screen positioning, and `.epi-controls`.

Two layout consequences to decide rather than discover:

- `#trends-controls` is `display:flex; justify-content:space-between`
  (`dashboard.css:279-282`), sized around scope-row **plus** search. With one
  child left, `space-between` is inert and the row's spacing needs re-checking.
- Deleting `.epi-controls` changes the `h2` → subtitle → table spacing at the
  top of `#epi-trends-panel`.

Net effect is negative lines in both `engine.js` and `dashboard.css`.

## Testing

`tests/test_zone_search.py`, in the static-source-guard style of
`tests/test_zone_state_styling.py`:

1. `common/chrome.py` contains exactly one `id="zone-search-input"`, and no
   `trends-search-input`, `epi-search-input`, `zone-search-wrap`,
   `trends-search-wrap`, `epi-search-wrap`, or `trends-search-slot`; and
   `#controls` contains no `input[type="search"]`.
2. `#zone-search` is a sibling of `#map` in `BODY_TEMPLATE`, not nested inside
   `#controls` or any rail.
3. The `ZONE_SEARCH_VIEWS` keys in `engine.js` equal exactly the non-stub view
   ids in `chrome.NAV_ITEMS` — so a tab added later cannot silently ship without
   a search, and a removed tab cannot leave a dangling entry.
4. No `.location-search-wrap` or `.location-search-results` selector survives in
   `dashboard.css`, and neither is referenced from `engine.js`.
   (`.zone-search-option` is *retained* — it is the option class of the new
   component. Only its dark styling is replaced.)
5. `dashboard.css` carries a `#zone-search` rule for every non-stub
   `body.view-*` **in every band it is meant to appear in** — a view positioned
   in band A only must fail. It is hidden for `body.stub-view`, and for
   `body.view-genomic-epidemiology` in band C.
6. `--layer-panel-width`, `--context-panel-width` and `--zone-search-height` are
   each declared exactly once, in `:root`. The **search-offset** rules that read
   `--layer-panel-width` / `--context-panel-width` appear only outside any
   `max-width` media query (band A). The panels' own width rules are
   unconditional by design and are not constrained by this test.
7. `--zone-search-height` is read by the input's `min-height` and by every
   displacement rule (`#controls`, `#info`, `#trends-legend`,
   `#epi-trends-legend`, `#context-national`).
8. Every locale key named in `ZONE_SEARCH_VIEWS` exists in both
   `locales/en.yaml` and `locales/fr.yaml`. No locale-parity test exists
   anywhere in `tests/` today, and this is the first place JS names locale keys
   from a data table — nothing else would catch the drift.
9. No `fitBounds` call in `engine.js` passes `padding` together with
   `paddingTopLeft` or `paddingBottomRight`. This is the guard for the silent
   Leaflet override described in §The shared zoom.

Manual pass, after a build, served over HTTP (see the build/serve notes in the
repo memory):

1. **Mid width (~760px and ~900px)** on Snapshot and Context, with `#info` /
   `#context` expanded — the band that motivated band B.
2. **Drag the Trends and Spatial Risk splits to maximum (72%)** at ~760px and
   confirm the search stays inside the visible map; repeat on Genomic by
   dragging `#genomic-resize`.
3. **Genomic: search the same zone twice.** Expected: still selected, still
   zoomed.
4. **Genomic: search during load** — the box should be absent, then appear.
5. **Genomic: search a zone on the far right of the map**, confirm it is not
   framed behind the panel; repeat after a resize drag.
6. **Zoom to a zone in the bottom-right corner** of the map on Snapshot and on
   Trends — the visual check for the padding bug behind test 9.
7. **EN → FR → EN on Trends**: placeholder is still the location one, accessible
   name is still "Search".
8. **Narrow Snapshot: expand `#info`**, then open the dropdown; and confirm a
   search-driven selection expands it with a `−` on the toggle, not a `+`.
9. **Spatial Risk: hover a zone with the list open** — dropdown must sit above
   `#epi-float`.
10. **Narrow Trends/Spatial Risk: select from the search** — padding must not
    over-zoom the 40vh map, and the dropdown must not swallow it.
11. **Landscape phone (≤500px tall)**: displaced `#info` must not run under the
    footer chrome.
12. **Keyboard-only pass** on one tab: Tab in, type, `↓`/`↑`, `Enter`, `Esc`,
    `Esc`; plus a screen-reader check of the empty state and the live count.
13. **All five tabs** at a wide and a narrow viewport, confirming each tab's own
    selection state updates and nothing overlaps in the top-left corner.

## Risks

- **Corner collisions.** Those found by reading the CSS are handled by the band
  tables and the rail clamp. Others may only appear on a rendered page; the
  thirteen-case manual pass is the check.
- **Band-B threshold.** 1000px is chosen to clear the worst case (~954px on
  Snapshot with a full-width `#info`). If `#info`'s content grows, the threshold
  needs revisiting — it is a single number in one media query.
- **Genomic coupling.** The `{toggle:false}` option, the reveal-on-registration
  signal, and the `--genomic-panel-width` publication all touch `genomic.js`,
  which is page-scoped and otherwise independent of the search. Kept to a
  handful of lines and no new hook names.

## Review dispositions

Both review passes are folded in above, with these exceptions and corrections,
recorded so the questions do not recur:

- **`maxZoom:10` on provinces — no change** (pass 1). `fitBounds`' `maxZoom`
  binds only when fitting a geometry would zoom *past* the cap, which happens
  for small geometries; a large province fits well below z10 and never reaches
  it. Withdrawn by the reviewer in pass 2.
- **Genomic overflow band** (pass 2, B2′). The review gives 701–905px; `30vw`
  reaches the search's 252px right edge at 840px, so the actual band is
  701–840px. The fix is unaffected.
- **Sub-pixel band gap** (pass 2, N6′) described a defect in media queries this
  spec had not yet written. Adopted as guidance: band A is the unqualified
  default and B/C are carved with `max-width` only.
- **Mirroring §Standing assumption into the zone-styling spec** (pass 2, nit) is
  a change to a different document and is left as optional follow-up.

Follow-up, not in scope: `#context-hint` still reads "Click a health zone to see
response context" on a tab that now also has a search box. Not wrong, but
incomplete.
