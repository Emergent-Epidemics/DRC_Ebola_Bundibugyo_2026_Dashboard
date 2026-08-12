# Genomic Epidemiology tab — Phase 0 spike findings

**Date:** 2026-08-12
**Plan:** `docs/superpowers/plans/2026-08-12-genomic-epi-phase0-spike.md`
**Spec:** `docs/superpowers/specs/2026-08-12-genomic-epidemiology-tab-design.md`
**Method:** a throwaway static spike under `spike/genomic-phase0/` (git-ignored) loading the real PearTree bundle + real genomic data + real health-zone geometry, driven/observed in Chrome; plus a scripted onset-data check against the canonical linelist. Screenshots live beside the spike code (`dark-recolour.png`, `map-link.png`, `coordinator.png`).

## Verdict: GO

All seven pass bars are met. No design-invalidating blocker was found; the riskiest unknown (recolouring the tree to a chosen zone palette) resolved **in favour** of the full goal. Two corrections to the spec came out of the spike (theme; colour semantics) and are already folded in.

## Pass-bar results

| Item | Verdict | Evidence |
|---|---|---|
| Baseline render | **PASS** | Real bundle renders the real 134-tip Ituri phylogeny (correct topology, Apr–Jun axis, health-zone tip labels). |
| PearTree theme | `dark = ACHIEVABLE_VIA_API(applySettings({theme:'BEAST'}))` | `applyTheme()` is broken in the bundle (calls a missing `_applyTheme`); `applySettings({theme})` works. Built-in dark themes: ARTIC/BEAST/MCM. **Not used** — see theme correction. |
| Recolour to zone palette | `PER_ZONE_MAP_SUPPORTED(settings.annotationPalettes, embed-init)` | No runtime palette setter on the public API. The real hook is `settings.annotationPalettes = { health_zone: {Zone: '#hex'} }` passed at `embed()` init (init-only, like `tipColourBy`). Proven: mapping every zone to magenta turned the whole tip cluster magenta. |
| Google Fonts | `BLOCKED_VIA_CSP(font-src 'self' data:)` | The bundle injects a `@import` to `fonts.googleapis.com` (+ `gstatic`). A `font-src 'self' data:` CSP meta blocks it (503, no font fetch); tree stays legible on the system fallback stack. |
| Tree delivery | `INLINE_TEXT_OK(key: 'tree')` | `embed()` reads an inline NEXUS string under key `tree`, only falling back to `treeUrl`. Verified render with no extra HTTP request → **the tree can ride inline in the page-scoped payload slice**. |
| Zone-level map linking | `ZONE_LEVEL_OK` | Marker + polygon click route to one handler → `clearTree()` + `highlightTips(zone.ids)`. Clicking Mongbwalu's marker selected exactly its 8 tips (verified via `getSelection()`); a 0-tip zone's polygon highlights with no error. |
| Coordinator contract | `REPRODUCIBLE_LOCALLY` | `activeKey`/`programmatic`/`zoneSelecting` state machine reproduced: toggle-deselect works; `onViewChange` shifts the distribution x-axis strip; selection fans out deduped date ticks; a direct tree click resets the toggle. |
| Onset / beyond-tree data | `AVAILABLE` | `dhis2_linelist_with_imputed_onset.csv` → per-(date, zone) `{observed, imputed}` via `date_of_symptom_onset_imputed` × `health_zone`, split by the `onset_date_was_imputed` flag. 22,566 rows, 0 dropped, 2026-03-31→2026-08-05, 109 zones. Beyond-tree (onset > 2026-06-23) = 14,085 rows. |

## Corrections folded back into the spec

1. **Theme: the genomic rail is LIGHT, not dark.** The dashboard is a *dark shell*
   (header/nav/floating map panels `#111`/`#222`) over a **light** CARTO `light_all`
   basemap, with **light content rails** — Trends `#f6f5f2` / Spatial-Risk `#ffffff`,
   dark ink `#2a2a27`, terracotta/maroon accents `#9b7d4e`/`#7c1d1d`. The source app
   already uses that **identical** palette, so the genomic panels stay light and the
   styling is *token alignment, not a light→dark port*. The tree stays in its light
   theme; the dark-BEAST capability is documented but unused. (Spec Context, Goals,
   §5, §6, Phase 0, Testing, Open items updated.)

2. **Colour semantics: no "one zone = one colour everywhere."** The dashboard has no
   per-zone identity colour (its map is a metric choropleth via `valueToColor`). We
   define a **new shared categorical zone palette** used across the zone-coloured
   genomic panels (tree tips + zone-split Ne/distribution) with a **legend**; the map
   stays metric-driven. (Spec Goal #2 updated.)

## Real-implementation notes (from the spike)

- Apply `applySettings({nodeSize:'3', tipSize:'4', fontSize:'10'})` after embed — at
  the compact rail height the default marker sizes crowd 134 tips into a pill.
- The tree has a harmless first-paint squash that self-corrects after a redraw.
- `onViewChange` fires as a tweened sequence during zoom animations — throttle/debounce
  the distribution x-axis coupling in the real implementation.
- Tips are selected via `selectByAnnotation('accession', tipId, {additive})`; clear via
  `setSelection([])`.

## Outstanding (carried to the spec, not blockers)

- PearTree provenance/licence unestablished — pin a versioned, licence-clear build
  before vendoring the 1.5 MB bundle.
- Phase 2 still owns building the onset aggregation into `payload.py` (the data is
  proven available; the code isn't written).

## Next step

Proceed to Phase 1 (create `INRB-UMIE/BDBV2026-Genomic_Epi` by extraction) per the
spec's phased delivery. The spike code under `spike/genomic-phase0/` is throwaway and
git-ignored; nothing from it ships.
