# Critical review — Unified health-zone search

**Reviewing:** `docs/superpowers/specs/2026-08-14-unified-zone-search-design.md`
**Date:** 2026-08-14
**Reviewer:** engineering review (code-verified against `Scripts/assets/engine.js`,
`Scripts/assets/genomic.js`, `Scripts/assets/dashboard.css`, `Scripts/common/chrome.py`
@ `unified-zone-search`)

---

## Verdict

The problem statement is accurate — I checked all five rows of the current-state table and every
claim in it holds — and the central call is right: **one DOM node outside the panels, one
controller, a per-view table.** The "every page ships every view's markup, activates one" property
of `chrome.py` genuinely makes a single `#zone-search` node correct here, and the rejected
alternatives are rejected for the right reasons. The removal list is real: `wireTrendsSearchSlot()`
(`engine.js:3510-3536`) and the `opts.fromSearch` branch (`engine.js:2830-2838`) both exist only to
prop up the duplication, and both die cleanly.

Four things would misbehave if implemented literally. **The genomic `select()` path is a toggle,
not a setter (B1)** — searching the zone you already searched deselects it. **On the genomic tab
`#map` is not narrowed by its panel (B2)**, so the shared `fitBounds` frames zones behind the
phylogeny rail, and the narrow-screen placement puts a 240px search box over a ~108px map strip.
**The wide-screen offsets collide between 701px and ~1000px (B3)** on both Snapshot and Context —
the `≥700px` branch is written for desktop widths only. And **the per-view placeholder will not
survive a language switch (B4)** the way it is described, because `applyI18n()` re-reads the
`data-i18n-*` attributes on every toggle.

Separately, the biggest under-specification is the one the spec flags itself and then leaves as a
guess: the narrow-Snapshot clamp — and its stated basis is the wrong element (N2).

---

## What the spec gets right (verified)

- **The three-searches table is accurate in every column.** `#zone-search-wrap` is inside
  `#controls` (`chrome.py:143-150`) with a 12-result cap and full keyboard handling
  (`engine.js:2282-2378`); `#trends-search-wrap` and `#epi-search-wrap` have `input`/`focus`/`click`
  handlers and **no** `keydown` at all (`engine.js:3472-3494`, `4008-4021`); only Snapshot/Context
  call `fitBounds` (`engine.js:2322`, `2328`). The 40-vs-12 cap difference is real
  (`2284` vs `2875`/`4001`).
- **The Context dead-branch claim is correct.** `selectHealthZone()`'s `activeView === "context"`
  branch (`engine.js:2320-2322`) is unreachable, because `body.view-context #controls` is
  `display:none !important` (`dashboard.css:656-658`).
- **Top-left really is free on every tab.** The map is built with `zoomControl: false`
  (`engine.js:605`), so nothing Leaflet-owned competes for `12px/12px`. Worth stating in the spec —
  it is the assumption the whole placement section rests on.
- **The `--layer-panel-width` / `--context-panel-width` values match the live rules.** `#controls`
  is `min(340px, calc(100vw - 24px))` at `dashboard.css:101-105`; `#context-national` is
  `min(280px, calc(50vw - 24px))` at `638-646`.
- **The narrow-screen corner audit is right as far as it goes.** `#controls` is at `top:12px`
  (`898`), `#epi-trends-legend` is repositioned to `top:12px; left:12px` (`868-874`),
  `#context-national` sits at `top:clamp(128px, 24vh, 200px)` (`875-880`), and narrow
  `#trends-legend` moves to `top:12px; right:12px` (`832-838`). All four confirmed.
- **The rails do narrow `#map`** on Trends (`162`) and Spatial Risk (`223-225`), so `left:12px` is
  the corner of the *visible* map on those two tabs and `fitBounds` needs no offset maths. Correct —
  but see B2, this is exactly what is **not** true on the genomic tab.
- **Clearing the input after selection is the right call**, and the reasoning ("query field, not a
  state indicator") is sound. It is also what two of the three searches already do.
- **The a11y gap is real.** Today's options carry `role="option"` but no ids and no
  `aria-selected`, and the input has no `aria-activedescendant` (`engine.js:2293-2312`).

---

## Blocking issues

### B1 — The genomic `select()` routes into a toggle, so searching the same zone twice deselects it

> §Risks: "`select()` there routes through `genomicMapHooks._emitZoneClick`, the same path a map
> click takes, so no new engine↔page contract is added."

The contract is unchanged; the *semantics* are not what the search needs. `genomic.js:631-647`:

```js
function selectZone(nom) {
  var key = "zone:" + up(nom);
  if (key === activeKey) { clearAll(); return; }   // <-- toggle
  ...
}
```

`_emitZoneClick` is deliberately a toggle so that clicking the same polygon twice clears the
selection. Under the spec's design the input is cleared after every selection, so a user who
searches "Bunia", looks away, and searches "Bunia" again gets it **deselected** — while the shared
`fitBounds` still zooms to it. That is the worst possible pairing: the map says "here it is", the
tree and cases panel say "nothing selected", and nothing on screen explains why.

Two further gaps on the same path:

- **The subscription is late.** `hooks.onZoneClick(...)` is registered inside `startCoordinator`
  (`genomic.js:651`), which runs only after the tree/tip data resolves. `_emitZoneClick` no-ops
  until then (`engine.js:3810`), so a search issued during load zooms the map and silently selects
  nothing.
- **It also no-ops permanently** if the genomic payload is absent or the tree fails to mount.

Fix: give the coordinator a non-toggling entry point (`hooks.onZoneSelect`, or an
`_emitZoneClick(nom, {toggle: false})` flag) and have the search use it; and state what the search
does before the coordinator boots — disable the input, or queue the last selection and replay it on
`startCoordinator`. Whichever, say it in the spec; this is not an implementation detail.

### B2 — On the genomic tab the map is not narrowed, so the shared `fitBounds` frames zones behind the panel

`#genomic-panel` is `position:absolute; right:0; width:min(634px, 70vw)` at `dashboard.css:1167-1174`,
and there is **no** `body.view-genomic-epidemiology #map { right: ... }` rule. Unlike Trends and
Spatial Risk, the panel *overlays* a full-width map rather than shrinking it. Consequences:

1. `map.fitBounds(bounds, {padding:[40,40], maxZoom:10})` centres the zone in the full container,
   i.e. roughly under the middle of the phylogeny rail. On a 1440px screen the visible map strip is
   the left ~806px; the fitted centre lands at 720px. Goal 4 ("selecting always zooms the map to
   it") fails on precisely the tab the spec adds the search to last.
   Fix: `paddingBottomRight: [panelWidth, 0]`, and read `panelWidth` from the element — it is a JS
   inline style, not a token (see 2).
2. **The panel width is not CSS-derivable.** `applyWidth()` (`genomic.js:745-751`) writes
   `panel.style.width` in px on drag/arrow-key resize, so no `--genomic-panel-width` token can track
   it. Any offset has to be measured at select time.
3. **Narrow screens are worse.** There is no `max-width:700px` rule for `#genomic-panel` at all, so
   at 360px it is `70vw = 252px` and the map strip is ~108px — the spec's narrow table says
   "genomic-epidemiology | nothing | none needed", but a `min(240px, calc(100vw - 24px))` search box
   would span the map strip *and* most of the panel (which sits at `z-index:500`, below the search).
   Either clamp the search to the visible strip (unusable at that width), hide it on narrow genomic,
   or accept it overlapping and say so.

### B3 — The wide-screen offsets collide between 701px and ~1000px, on two tabs

The `≥700px` table places the search beside the left-hand panel, but the opposite corner is occupied
on both Snapshot and Context, and neither is checked:

| Tab | Search occupies | Opposite panel starts at | Collides below |
|---|---|---|---|
| `map` | `362px … 602px` (12 + 340 + 10, width 240) | `#info`, `right:12px`, content-sized up to `max-width:340px` (`dashboard.css:144`) | ~955px with a full-width `#info` |
| `context` | `302px … 542px` (12 + 280 + 10, width 240) | `#context`, `right:12px`, `width:min(280px, calc(50vw-24px))` (`dashboard.css:647-655`) | ~834px |

The media query boundary is `max-width:700px`, so this whole band (701px–~950px) takes the *wide*
branch — a very common laptop-in-a-split-window width, and the exact width where the tab was
presumably designed. The spec's risk section anticipates "corner collisions" but scopes the check to
"a wide and a narrow viewport"; two widths will not find this. Add a mid-width case, and pick one of:

- clamp the search width to the space actually left (`min(240px, calc(100vw - <left> - <right> - 24px))`);
- move the search **below** the left panel (`top:calc(12px + panel height)`) instead of beside it —
  but panel heights are content-driven, so this needs a token or JS;
- introduce a third breakpoint where the search takes the narrow (corner) treatment.

### B4 — The per-view placeholder as described does not survive a language switch, and the aria-label is wrong on Trends

> §Component: "Trends keeps using the existing `ui.trends_search_placeholder` …, applied by the
> controller at init because that tab alone lists provinces."

`applyI18n()` re-reads the attributes, not the properties, on **every** language toggle:

```js
document.querySelectorAll("[data-i18n-aria]").forEach(el => el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria"))));      // engine.js:276-278
document.querySelectorAll("[data-i18n-placeholder]").forEach(el => el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder"))));  // engine.js:282-284
```

So the controller must rewrite `data-i18n-placeholder` itself (then call `applyI18n()` or `t()`
once), not set `input.placeholder`. Otherwise the Trends box shows "Search for a location…" until
the first EN/FR toggle and "Type a health zone name…" forever after — a bug that only appears in
the French build.

The same applies to the accessible name, which the spec does not mention: the markup hard-codes
`data-i18n-aria="ui.zone_search"` = "Search health zone" / "Rechercher une zone de santé", which is
factually wrong on the one tab that also lists provinces. `ui.trends_search` ("Search" / "Recherche")
already exists (`locales/en.yaml:131`, `fr.yaml:131`) — put an `aria` key alongside `placeholder` in
`ZONE_SEARCH_VIEWS` and swap both. Still no new locale keys, so the spec's claim survives intact.

---

## Should fix

### N1 — `#zone-search` has no z-index, and the one it needs is not obvious

The spec gives `z-index:1100` to the results panel only. The wrapper needs one too: every `.panel`
is `z-index:1000` (`dashboard.css:94`), `#epi-trends-panel` and `#trends-panel` are 1000,
`#epi-split-handle`/`#trends-split-handle` are 1200, `#genomic-panel` is 500, the header is 1300.
As a sibling of `#map` declared before the panels in `BODY_TEMPLATE`, an unstyled `#zone-search`
would paint **under** every panel. Specify it (1200 clears the panels and the split handles without
reaching the header), and note that the dropdown's 1100 ties with `#epi-float` (`dashboard.css:442`)
— on Spatial Risk a hover readout can land on top of an open list; source order currently decides.

### N2 — The narrow-Snapshot clamp cites the wrong element, and the real constraint is worse

> §Placement: "On narrow `map`, the opposite corner holds `#info` collapsed to a title bar capped at
> `min(160px, calc(60vw - 18px))`."

That cap is `#controls.collapsed` (`dashboard.css:907`), not `#info`. `#info` gets
`max-width:60vw` (`795`) and no width cap when collapsed — it is content-sized while collapsed
(~90px for "Zone −"), but `wirePanelToggles()` only auto-collapses it *on load*
(`engine.js:4223-4224`), so the user can expand it back to 60vw at any moment while the search sits
in the same row. A static clamp derived from the collapsed width is therefore wrong half the time.

Options worth naming in the spec: push `#info` down as well as `#controls` (the search then owns the
whole top row, `width:calc(100vw - 24px)`), or make `#info`'s narrow rule `top:calc(12px + var(--zone-search-height) + 8px)`
like `#controls`. Either is a real decision; "tune it against a screenshot" is not.

### N3 — Adding zoom on Trends/Spatial Risk reverses a documented decision; say so

`engine.js:2814-2819` records that selection auto-pan was deliberately **removed** from the Trends
tab because "that auto-pan just made the map jump around distractingly on every click." Goal 4
reinstates a map move on those tabs — for search only, which is defensible (a searched zone can be
offscreen; a clicked one cannot) — but the spec should say that explicitly and note the resulting
asymmetry: on Trends and Spatial Risk, **clicking** a zone does not move the map while **searching**
the same zone does. Otherwise the next reader deletes one or the other for consistency.

Two mechanical notes on the shared call:

- On narrow Trends/Spatial Risk the map is `height:40vh` (`dashboard.css:806`, `849`). `padding:[40,40]`
  costs 80px of a ~192px-tall map on a 480px viewport. Scale the padding, or use a smaller narrow value.
- Trends can select a **province**; the spec says to take bounds "from the matching
  `province_boundaries` feature". `provinceOutlineLayer` already exists (`engine.js:2421`) — reuse its
  layer bounds the way `findGeoLayerByNom` is reused for zones, rather than computing from raw GeoJSON.

### N4 — The Spatial Risk `select()` reaches into a closure the spec is dissolving

`select` for `epi-trends` is "`setEpiSelected(nom)`, then scroll the matching `tr[data-nom]` into
view". `setEpiSelected` is a top-level function (`engine.js:1318`), but the scroll half lives in
`epiApplyHealthZone` inside the `wireEpiTrendsUi` IIFE and uses that closure's `tbody`
(`engine.js:3970-3979`). A module-level `ZONE_SEARCH_VIEWS` must re-query `#epi-trends-tbody`
itself. One line, but say it — otherwise the implementer hoists a chunk of the IIFE.

Also note that `wireEpiTrendsUi` **returns early** when there is no invasion data
(`engine.js:3950-3954`), hiding the tab; the shared controller has no such guard, so state that the
Spatial Risk search is simply inert in that build (harmless — the page is unreachable from the nav).

### N5 — The "no matches" state is invalid inside `role="listbox"`

The spec upgrades ARIA (ids, `aria-selected`, `aria-activedescendant`) and then keeps the empty
state inside the listbox: today `.zone-search-empty` is a `<div>` child of
`#zone-search-results[role=listbox]` (`engine.js:2287-2288`). A listbox may only contain options
(and groups); a bare div there is ignored or mis-announced. Since this section is explicitly about
fixing what "tells assistive technology nothing", fix it too: render the empty message as a sibling
of the listbox with `role="status"`, and keep `aria-expanded="false"` when there is nothing
selectable. A live result count ("12 matches") in the same region is a cheap addition.

### N6 — The `disableClickPropagation` rationale is wrong (the calls are harmless, the reason is not)

> "…apply to the wrapper, as they already do, since it overlays the Leaflet container."

`#zone-search` is a **sibling** of `#map`, not a descendant of the Leaflet container, so its events
never reach Leaflet's container-bound handlers in the first place — nothing propagates, with or
without the calls. (The same is true today: `#zone-search-wrap` lives inside `#controls`, also
outside the container.) Keep the calls as belt-and-braces if you like, but correct the reason, or
someone will later "fix" the placement to be inside the map container on the strength of it.

### N7 — The token story is only half true; the narrow rules use different numbers

`--layer-panel-width` and `--context-panel-width` describe the **wide-screen** panel widths only.
The narrow rules deliberately differ: `body.view-context #context-national` is
`left:6px; width:min(260px, calc(50vw - 12px))` (`dashboard.css:875-880`), and `#controls.collapsed`
overrides its width entirely (`907`). Test 6 ("declared once and read by both the search rule and
the rule for the panel it offsets from") therefore only holds for the wide branch. Either scope the
tokens' documented meaning to wide screens, or redefine them inside the media query so the narrow
rules read them too.

`--zone-search-height` has a different shape from the other two — it is read by the input rule and
by *two* displacement rules (`#controls`, `#epi-trends-legend`), so the test's phrasing ("the rule
for the panel it offsets from", singular) does not fit it. Split the assertion.

### N8 — Removing the search leaves two containers holding one child each

- `#trends-controls` is `display:flex; justify-content:space-between` (`dashboard.css:279-282`) sized
  around scope-row + search. With the search gone it holds only `.trends-scope-row`;
  `space-between` becomes meaningless and the row's spacing should be re-checked.
- `.epi-controls` is deleted outright (correct — it would be empty), which changes the
  `h2` → subtitle → table spacing at the top of `#epi-trends-panel`. Worth one line in §Removals so
  it is a decision rather than a surprise.

### N9 — Keeping focus in the input is the wrong default on touch

"Focus stays in the input so the next search can start immediately" is right on a desktop and wrong
on a phone: the on-screen keyboard stays up, covering roughly half of a map that was just zoomed to
the thing the user asked for. Blur after selection under `(max-width: 700px)` / coarse pointer, or
say the trade-off was considered.

### N10 — On narrow Snapshot, clearing the input removes the only confirmation

`wirePanelToggles()` auto-collapses `#info` on narrow (`engine.js:4223-4224`). After a narrow-Snapshot
search the input clears, the info panel is a collapsed "Zone" title bar, and the only feedback is a
zoom plus a highlight on a map the user may not recognise. Consider expanding `#info` (and, on
Spatial Risk, the legend is already fine) when a selection arrives *via search*. If not, record it
as accepted.

---

## Minor / nits

- **Boundary off by one.** The media query is `max-width:700px`, so 700px takes the *narrow* branch;
  the spec's "Wide screens (≥ 700px)" / "Narrow (≤ 700px)" overlap at exactly 700.
- **Test 1 should also forbid `zone-search-wrap`** and assert `#controls` no longer contains an
  `input[type=search]` — otherwise the old wrapper could survive inside the LAYER panel and pass.
- **No locale-parity test exists** anywhere in `tests/`. Since `ZONE_SEARCH_VIEWS` now names locale
  keys in JS, add an assertion that every `placeholder`/`aria` key it references exists in both
  `locales/en.yaml` and `locales/fr.yaml`. Cheap, and it is the kind of drift nothing else catches.
- **`body.epi-map-exporting`** hides every map-overlay element by id (`dashboard.css:407-416`). The
  JPG capture is scoped to `map.getContainer()` (`engine.js:4119`), and `#zone-search` is outside it,
  so the export is unaffected — but add `#zone-search` to the list anyway for consistency with
  `#epi-trends-legend`, which is in the same position and is hidden.
- **`ZONE_SEARCH_INDEX` becomes a private intermediate** of `LOCATION_INDEX` (nothing else reads it —
  I checked). Either fold it in or note that it stays only as the zone-side builder.
- **Native `type="search"` behaviour vs. the two-stage `Esc`.** Chrome/WebKit clear a search input on
  `Esc` natively and render their own ✕. The spec's "Esc closes the list; pressed again clears the
  query" needs `preventDefault()` on the first press to hold, and the ✕ needs to fire the same
  close-and-clear path.
- **`Enter` on a closed list** is unspecified. Today it does nothing; say so.
- **Dropdown height on narrow.** `max-height:calc(5 * 32px)` = 160px opening from `top:44px` over a
  40vh map (~192px at 480px viewport height) covers essentially the whole map. Acceptable, but it
  will look like a bug in a screenshot — worth a line.
- **`maxZoom:10` for a province** on Trends: fine for Ituri-sized units, but it is a zone-derived
  number applied to a much larger geometry. Confirm on the widest province.
- **Stub views.** `ZONE_SEARCH_VIEWS` has no key for them, so the controller must no-op rather than
  throw on `ZONE_SEARCH_VIEWS[activeView].kinds`. One sentence.
- **`#context-hint`** still reads "Click a health zone to see response context" on a tab that now has
  a search box. Copy is out of scope, but flag it as follow-up rather than leaving it stale.

---

## Suggested additions to §Testing

The manual pass ("five tabs at a wide and a narrow viewport") will not find B3 or B1. Add:

1. **A mid width (~760px and ~900px)** on Snapshot and Context, with `#info` / `#context` expanded —
   this is where the wide-branch offsets collide (B3).
2. **Genomic: search the same zone twice.** Expected: still selected, still zoomed. Today's toggle
   would deselect it (B1).
3. **Genomic: search during load**, before the phylogeny renders (B1).
4. **Genomic: search a zone on the far right of the map** and confirm it is not framed behind the
   panel; repeat after dragging `#genomic-resize` (B2).
5. **Switch EN → FR → EN on Trends** and confirm the placeholder is still the location one and the
   accessible name is still "Search" (B4).
6. **Narrow Snapshot: expand `#info`**, then open the search dropdown (N2).
7. **Spatial Risk: hover a zone with the list open** — check `#epi-float` vs. dropdown stacking (N1).
8. **Narrow Trends/Spatial Risk: select from the search** and confirm `fitBounds` padding does not
   over-zoom the 40vh map (N3).
9. **Keyboard-only pass on one tab**: Tab into the input, type, `↓`/`↑`, `Enter`, `Esc`, `Esc` —
   plus a screen-reader check of the empty state (N5).

---

## Summary of recommended spec edits

| # | Change | Severity |
|---|---|---|
| B1 | Give genomic a non-toggling select path; state the pre-coordinator behaviour | blocking |
| B2 | Offset `fitBounds` by the measured `#genomic-panel` width; decide the narrow-genomic placement | blocking |
| B3 | Clamp/re-place the search for the 701–~1000px band on `map` and `context` | blocking |
| B4 | Swap `data-i18n-placeholder` **and** `data-i18n-aria` attributes per view, not properties | blocking |
| N1 | Specify `#zone-search`'s own z-index; note the 1100 tie with `#epi-float` | should fix |
| N2 | Fix the `#info` / `#controls.collapsed` attribution; decide the narrow-Snapshot layout properly | should fix |
| N3 | Acknowledge the reversal of the Trends auto-pan removal; scale padding; reuse `provinceOutlineLayer` | should fix |
| N4 | Re-query `#epi-trends-tbody` in the shared table; note the no-invasion-data early return | should fix |
| N5 | Move the empty state out of `role="listbox"`; add a status/live region | should fix |
| N6 | Correct the `disableClickPropagation` rationale (sibling, not overlay child) | should fix |
| N7 | Scope the width tokens to the wide branch (or redefine in the media query); split test 6 | should fix |
| N8 | Note the `#trends-controls` / `#epi-trends-panel` spacing fallout of the removals | should fix |
| N9 | Blur after selection on touch/narrow | should fix |
| N10 | Expand `#info` on a search selection on narrow Snapshot, or accept it explicitly | should fix |
