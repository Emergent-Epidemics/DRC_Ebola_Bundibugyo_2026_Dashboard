# Critical review — Snapshot selection-driven info box + reworked hover tooltips

**Reviewing:** `docs/superpowers/specs/2026-08-05-snapshot-selection-hover-tooltips-design.md`
**Date:** 2026-08-05
**Method:** Claims cross-checked against `Scripts/assets/engine.js`, `Scripts/common/chrome.py`, `locales/{en,fr}.yaml`.

## Verdict

Solid, well-structured spec: scope is fenced tightly, edge cases and i18n are called out, and the decision to encode selection in `styleFn` is the *right* call — it matches the existing epi-trends pattern and gets zoom-persistence for free via the `zoomend` restyle (engine.js:1719-1732). But there are two **blocking omissions** (matrix-layer origin; flow-hub default) and several **factual/scoping gaps** that will surface as bugs if the plan phase inherits the spec as-is. Details below, ordered by severity.

---

## Major — must resolve before planning

### M1. The matrix-layer click branch is never reconciled with `mapSelectedNom`

The spec models the map-view click handler as two states: flow-arrows-on (`setFlowHub`) and everything-else (`fitBounds` fallback, to be removed). But the real handler has **three** branches (engine.js:1688-1701, mirrored in `handleCaseMarkerClick` at 3237-3246 and search-select at 1869-1873):

1. `flowArcsOverlayActive()` → `setFlowHub`
2. `layerUsesMatrix(layer)` → `setMatrixOrigin` ← **spec never mentions this**
3. else → `map.fitBounds` (the zoom the spec removes)

On matrix layers (travel time, road distance), clicking a zone sets `matrixOriginNom`, which drives (a) the choropleth values — `currentValues` come from `matrixValue(..., matrixOriginNom, ...)` (engine.js:521-522), (b) the origin highlight fill `MATRIX_ORIGIN_FILL` in `styleFn`/`isHubZone` (1428-1434, 107-109), and (c) the info box's travel-time / road-distance rows, which are computed **from the origin** (`infoHTML` lines 1596-1597).

Unanswered questions the spec must settle:
- On a matrix layer, does a click set the **origin**, the **selection**, or **both**? "Click any zone to select it" contradicts the current "click sets the matrix origin."
- If selection and origin can differ, the info box shows zone A while its travel-time rows are measured *from* zone B (the still-standing origin). Is that intended, or should selection follow the origin on matrix layers?
- `setMatrixOrigin` **cannot be cleared** — it guards `if (!nom || nom === matrixOriginNom) return` (179-181) and a matrix choropleth needs an origin. So "click empty map clears selection" has no matrix-origin analogue; selection and origin have different lifecycles. Which wins?
- The "Affected code" list omits `setMatrixOrigin` / `layerUsesMatrix` / the matrix click branch entirely.

**Recommendation:** Add a subsection to §1/§2 defining click behavior per layer family (choropleth vs. flow-arc vs. matrix), or explicitly scope matrix layers out. Right now the largest interaction in the file is invisible to the spec.

### M2. "Clearing selection clears the flow hub" regresses the default-arcs behavior

Spec §1 says: *"Setting `mapSelectedNom` also sets `flowHubNom`; clearing it clears the hub."* But `flowArcsOverlayActive()` on the map view is **independent of the hub** — it returns true whenever the toggle is checked (engine.js:76-81), regardless of `flowHubNom`. And the toggle defaults to **on** (`showFlowArcsBox.checked = true`, line 3294) with `flowHubNom` defaulting to `"Mongbwalu"` (line 15).

So today, on load, arcs render from the default Mongbwalu hub. Under the new rule, "nothing selected" ⇒ `flowHubNom = null` ⇒ `renderFlowArcs(null)` on load and whenever the user turns the toggle on without a selection. That is a visible change to arrow behavior, which directly contradicts the spec's repeated promise that *"arrows behavior stays the same"* / *"Mobility-arrow behavior is otherwise unchanged."*

**Recommendation:** Specify the no-selection arc state explicitly. Either (a) initialize `mapSelectedNom` to the default hub so arcs still render on load, or (b) keep the Mongbwalu fallback in the arc-render path when no zone is selected, and state that "clear selection" clears the *info box + highlight* but the hub falls back to default. Decide and write it down.

---

## Medium — will bite during implementation

### D1. "The info box empties on mouseout" is factually wrong

Motivation bullet 1 claims the info box *"empties again on `mouseout`, so it never reflects a persistent choice."* It doesn't. The map-view `mouseout` handler only calls `geoLayer.resetStyle` (engine.js:1654) — it never touches `#info-body`. And `info-empty` is **only ever removed** (`className = ""` at 1631/1880/3684), never re-added anywhere. So the current behavior is *sticky last-hover*: after the first hover the box shows that zone forever, until you hover another.

This isn't just pedantic — the "before" picture is the premise for the whole change. The real motivation is "driven by last-hover (accidental) instead of an explicit, cleared-on-deselect choice," which is still a valid reason to do the work. Fix the framing so reviewers and the plan phase don't code against a false baseline.

### D2. Language-switch re-render of the *selected* zone needs new code the spec says already works

Spec §1 and the edge-cases section claim the `info-empty` restore paths *"keep working since they key off the `info-empty` class"* and that on language switch *"the selected zone's info box … re-render[s] in the new language."* These two are in tension:

- `applyStaticI18n` **early-returns for a non-empty info box** (`if (el.id === "info-body" && !el.classList.contains("info-empty")) return;`, line 205). So when a zone *is* selected, this path deliberately does **not** re-render it.
- The only other info-body refresh (lines 462-467) re-renders a **hard-coded Mongbwalu/`TRAVEL_FROM`** zone, not an arbitrary selection.

So the placeholder re-renders fine (correct), but re-rendering the *selected* zone in the new language requires **new** wiring that the spec frames as pre-existing. The "Affected code" note does mention a helper that renders from `mapSelectedNom` and a layer-change refresh — extend that to explicitly cover the language-switch path, and correct the claim that i18n "keeps working" (it only does for the empty state).

### D3. Search-to-select is more entangled than "leave as-is"

The edge-cases section punts search-select as out of scope "unless trivial." It isn't trivial: the map-view search handler (engine.js:1868-1885) already (a) calls `setFlowHub`/`setMatrixOrigin`, (b) fills `#info-body` via `infoHTML`, and (c) applies a **temporary** `#ffae42` highlight that a `setTimeout` clears (1884-1886). After the new change, a search will leave the info box populated for a zone that is **not** in `mapSelectedNom`, and the transient search highlight won't match the new persistent selection highlight. So the two mechanisms *do* fight — a searched zone looks half-selected. This needs a decision now (make search set `mapSelectedNom`, or explicitly document the divergence), not a "confirm later."

### D4. Selection highlight vs. existing highlights — precedence and colour collisions undefined

`styleFn` already paints hub/epicenter/matrix-origin states (distinct fills + weights, 1428-1441), and hover uses `weight:1.6, color:"#ffae42"` (1629). Adding a selection border needs:
- **A colour distinct from hover** (`#ffae42`). If selection reuses `#ffae42` (as trends/context selection does) you can't tell selected from hovered.
- **Defined precedence** when the selected zone is *also* the flow hub or matrix origin (which set their own fill/weight). Which border wins?
- The spec says "hover highlight remains a separate, transient effect on top" — but if hover paints *over* the selection border, hovering the selected zone visually hides that it's selected. Confirm that's acceptable, or have hover preserve the selection colour on the selected zone (as the trends `mouseout` already special-cases at 1637-1640).

### D5. Dropping the combined deaths line removes suspected-death info entirely

Spec §3 frames row 3 as a cleanup: `confirmed_deaths` replaces the combined `totalDeaths`. But the current line is `confirmed_deaths + suspected_deaths` (engine.js:3193). The new layout shows **only confirmed deaths**, silently dropping suspected deaths from the UI. That's a product/data decision, not a layout tidy-up — confirm stakeholders are fine losing suspected-death visibility on the marker tooltip (and on Spatial Risk, via the shared function).

---

## Minor — worth a line in the plan

- **N1. `handleCaseMarkerClick` not in "Affected code."** Marker clicks route through it (engine.js:3223-3249); it must also set/clear `mapSelectedNom`, and its matrix branch (3243-3245) inherits M1. List it.
- **N2. i18n keys already partly exist.** `ui.info.confirmed_deaths` exists in both locales (en/fr:225) and `case_tooltip` currently has `confirmed`/`suspected`/`deaths` (en:216-218). Fine — just reuse/rename deliberately rather than adding parallel near-duplicate keys.
- **N3. Zoom-to-zone becomes inconsistent.** Removing single- and custom-double-click zoom is stated as intended, but **search-select still `fitBounds`** (1874). So one path frames a zone and the other doesn't. Confirm that's acceptable, or align them.
- **N4. Genome markers.** `refreshMarkerTooltips` also refreshes genome tooltips (3213-3215) and genome markers sit in the same pane. The "only one tooltip shows at a time" claim (§4) should be verified against genome-vs-polygon overlap too, not just case-vs-polygon.

---

## What's good (keep)

- Encoding selection in `styleFn` rather than an out-of-band highlight — consistent with epi-trends and free zoom-persistence via `zoomend` (1719-1732). This is the correct architectural choice.
- Explicit "confirmed decision A/B" markers and the marker-only vs. polygon-tooltip separation.
- Tight, honest "Out of scope" fence and a concrete manual-test checklist.
- Reusing the shared `caseMarkerTooltip` so Spatial Risk stays in sync (modulo the D5 product decision).
