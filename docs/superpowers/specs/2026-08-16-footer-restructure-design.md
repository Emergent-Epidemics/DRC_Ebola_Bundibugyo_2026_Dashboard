# Footer restructure — design

Date: 2026-08-16
Branch: `footer-restructure`
Revision: 1

## Problem

`#view-switcher` is a fixed-height bar pinned across the bottom of every view
holding four things: the EN/FR toggle, a "Contributors, Data, and Methods"
button, a "Terms of Use" button, and the partner-logo strip. It is a leftover
container — the view tabs it was built around moved up to `#page-tabs`
(`dashboard.css:622-624` still explains the move) — and each of the four
occupants has a problem.

1. **The language control uses the wrong metaphor.** `.lang-toggle-track` /
   `.lang-toggle-thumb` (`dashboard.css:1167-1220`) is a 92px sliding pill with
   an animated thumb — the vocabulary of an on/off switch, and the only
   switch-styled control in the UI. Language is a choice between two peers, not
   a state you enable. It also sits at the bottom of the page, furthest from the
   title it changes.

2. **Methods and Terms are over-weighted.** They render as filled `.link-btn`
   buttons in the same terracotta family as the active tab, so three
   button-like objects compete at bottom-left for what are two once-a-visit
   reference links.

3. **The bar cannot hold its own contents.** `#partners` is
   `flex-wrap:nowrap; flex-shrink:0`, so the links column is the only thing that
   can yield; when it wraps, the extra row spills out of the bar because the
   height is `var(--view-chrome-height)`, not `auto`. Measured in an iframe at
   real widths: with the original five logos the bar already overflowed by ~10px
   between 700 and 780px; adding three partner logos moved the onset to ~880px
   in EN and ~980px in FR (French button labels are longer). A
   `@media (max-width: 999.98px)` logo step-down patched the symptom; the cause
   is untouched.

4. **The bar taxes every view 44px.** `#map`, `#info`, `#legend`,
   `#trends-panel` and `#epi-trends-panel` all subtract
   `--view-chrome-height`.

5. **Two code paths for the same two links.** Below 700px the footer hides
   Methods/Terms and `#header-info-popup-links` shows its own copies
   (`chrome.py:92-95`), so the buttons, their wiring and their i18n exist twice.

Separately, the logo strip itself reads as one object rather than eight
organisations: eight marks at 2px gaps inside a hairline box
(`dashboard-theme.css:303-307`, `#partners` again at `389-393`).

## Goals

1. Move the language control into the header, as text rather than a switch.
2. Give the footer bar contents that fit at every width, structurally — no new
   breakpoint patches.
3. Quiet the two reference links so they stop competing with the tabs.
4. Make the logo strip read as eight distinct partners, grouped by affiliation.
5. Give some of the 44px back to the map.

## Non-goals

- Removing the footer bar entirely (option B3 in the mockups). The partner
  logos stay visible on load; whether that is a funder commitment was not
  established, so the bar stays.
- Any change to the modals themselves, to `.link-btn` outside `#footer-links`,
  or to the `#header-info-popup-links` copies of Methods/Terms — the duplicate
  path stays for now, since only the language control is moving.
- Retranslating or renaming the partner `alt`/`title` text (still
  `Path(fname).stem.upper()`).
- Replacing any logo artwork. The Oxford navy tile is used as supplied; see
  §Open question.

## Design

### A · Language control moves into the header metadata line

Two text links, **English** and **Français**, each written in its own language
so neither needs translating. Active one in `--ink` at `font-weight:700` with a
2px `--terracotta` underline; inactive in `--link`.

Placement follows what is already there at each width:

| Width | Location |
|---|---|
| > 700px | End of the "Dashboard last updated: …" line inside `#title-sub` |
| ≤ 700px | Inside `#header-narrow-row`, beside the ⓘ button, wrapping to its own line if needed |

`#title-sub` is rebuilt by `buildTitleSub()` on every language switch, so the
wide copy is rendered *by* `buildTitleSub()` (which knows `currentLang` and can
mark the active one inline). The narrow copy is static markup in
`chrome.py`, never rebuilt.

Because the wide copy's nodes are replaced on each switch, the click handler
moves from per-node binding (`engine.js:549-551`) to one delegated listener:

```js
document.addEventListener("click", function(e) {
  const btn = e.target.closest(".lang-btn");
  if (btn) setLang(btn.dataset.lang || "en");
});
```

`applyStaticI18n()` keeps toggling `.active` / `aria-pressed` across all
`.lang-btn` nodes for the static copy. The `#lang-switcher` id and its
`.lang-fr` thumb-position toggle (`engine.js:301-302`) are deleted along with
the pill CSS — with no thumb there is no position to track.

`role="group"` moves onto a `.lang-switch` class (two nodes now, so no id), and
gains `data-i18n-aria="ui.aria.language"` with a new key in `locales/en.yaml`
("Language") and `locales/fr.yaml` ("Langue").

### B · The footer bar

`#footer-links` keeps only Methods and Terms, restyled as quiet text links
scoped to the footer so the `#header-info-popup-links` copies are untouched:

```css
#footer-links .link-btn {
  padding:0; background:none; border:none; border-radius:0;
  font-size:12px; font-weight:400; color:#ffd28a;
  text-decoration:underline; text-underline-offset:2px;
}
```

The color is a literal here, not `var(--link)`: `--link` is defined only in
`dashboard-theme.css`, so a `var()` would resolve to nothing on the un-themed
fallback path. The theme layer re-colors these to `var(--link)` alongside its
other overrides. The same rule applies to `.lang-switch`: literal
`#ffd28a`/`#bbb` in the base sheet, theme tokens in the theme layer.

`--view-chrome-height` drops **44px → 32px** wide. Below 700px the bar holds
only the logo strip (Methods/Terms are already hidden there and the language
control has moved to the header), so it drops **54px → 36px** and the strip
centres instead of right-aligning. The `max-height:500px` band goes 46px → 28px.

The structural fix is that `#partners` is allowed to give ground:

```css
#view-switcher #partners { flex-shrink:1; min-width:0; }
```

with a single `--partner-h` variable driving logo height per band (replacing
both the unconditional `clamp(18px, 3vmin, 28px)` and the
`@media (max-width: 999.98px)` patch added when the three logos landed):

| Band | `--partner-h` | `--partner-gap` |
|---|---|---|
| default | 22px | 24px |
| ≤ 999.98px | 18px | 18px |
| ≤ 799.98px | 15px | 10px |
| `max-height: 500px` | 16px | 11px |

The 799.98px step is set by French, and by arithmetic rather than taste:
"Contributeurs, données et méthodes" plus "Conditions d'utilisation" measure
327px on one line, and the bar spends 32px on its own padding and the column
gap, so the strip must fit in `W − 359` — 342px at the bottom of the band.
`flex-shrink` alone does not achieve this: shrinking the flex *container* does
not scale the images inside it, so the strip has to actually be told to get
smaller.

### C · The logo strip

**Unboxed.** The `background` + `border` come off `#partners` in
`dashboard-theme.css` — both the `#view-switcher #partners` rule and the bare
`#partners` rule. They stay in `dashboard.css`: the base stylesheet's footer is
`rgba(20,20,20,0.96)` and the white plate is what keeps color-on-white logos
legible there (`northeastern.png` is RGBA with a transparent ground and would
vanish outright). The theme file is optional in the build
(`common/theme.py:22-23`), so that fallback has to keep working.

**Uniformly spaced.** One `--partner-gap` sets the separation between every
pair of neighbouring logos — the same value between affiliations as within one.

Grouped spacing (a tighter gap within an affiliation than between) was built
first and rejected on sight: with marks this varied in shape and internal
padding, the two gap sizes read as accidental unevenness rather than as
structure. The `.partner-group` wrappers stay in the markup, so restoring it is
a matter of giving `#partners` a larger gap than `.partner-group`; the group
data below is what those wrappers are built from.

| Group | Members |
|---|---|
| 0 · DRC national | `INSP.png`, `inrb.png`, `UMIE.jpeg` |
| 1 · continental & global | `africa-cdc.png`, `WHO.jpg` |
| 2 · academic | `northeastern.png`, `psi.jpg`, `oxford.jpg` |

**Optically balanced.** Equal pixel height is not equal visual weight: a solid
square tile or a heavy letterform outweighs a thin wordmark at the same height
— the box used to conceal that. Each logo carries a scale factor:

| Logo | Factor | Why |
|---|---|---|
| `INSP.png`, `inrb.png`, `WHO.jpg` | 1.00 | thin wordmarks, full height |
| `UMIE.jpeg`, `africa-cdc.png` | 0.95 | wordmark with a compact mark |
| `psi.jpg` | 0.90 | dense mark plus wordmark |
| `northeastern.png` | 0.85 | large black letterform |
| `oxford.jpg` | 0.82 | solid navy tile, heaviest mark in the row |

### Data flow

`load_partners()` (`common/data_sources.py:3420`) gains two constants beside
`PARTNER_ORDER`: `PARTNER_GROUPS` (filename → group index) and `PARTNER_SCALE`
(filename → factor). Each payload entry grows two keys:

```python
{"alt": …, "href": …, "data_uri": …, "group": 2, "scale": 0.82}
```

`buildPartners()` (`assets/engine.js:479-490`) walks the flat list and opens a
new `<span class="partner-group">` whenever `group` changes, sizing each image
`height: calc(var(--partner-h) * <scale>)`. Group gap lives on `#partners`
(30px), within-group gap on `.partner-group` (12px). The payload stays a flat
list so nothing else has to learn a new shape — `common/payload.py:70-71` only
prints `alt`s.

## Files touched

| File | Change |
|---|---|
| `Scripts/common/chrome.py` | remove `#lang-switcher` from `#footer-links`; add static `.lang-switch` to `#header-narrow-row` |
| `Scripts/assets/engine.js` | `buildTitleSub()` renders the wide language pair; delegated `.lang-btn` click; drop `#lang-switcher` `.lang-fr` toggle; `buildPartners()` emits groups + per-logo scale |
| `Scripts/assets/dashboard.css` | delete pill CSS; add `.lang-switch` text styling; quiet `#footer-links .link-btn`; `--view-chrome-height` 44→32 / 54→36 / 46→34; `--partner-h` bands replacing the 999.98px patch; `#partners` shrink + `.partner-group` |
| `Data/Branding/dashboard-theme.css` | drop `background`/`border` from both `#partners` rules; theme colors for `.lang-switch` and the quiet footer links |
| `Scripts/common/data_sources.py` | `PARTNER_GROUPS`, `PARTNER_SCALE`, `group`/`scale` in `load_partners()` |
| `locales/en.yaml`, `locales/fr.yaml` | `ui.aria.language` |

## Testing

Existing `pytest ../tests` (89 tests) must stay green; none cover partners
today. Add one test asserting `load_partners()` returns a `group` and `scale`
for every entry and that every `PARTNER_ORDER` filename appears in both new
constants — that is the failure mode a future logo addition would hit silently.

Layout verification uses the same-origin iframe harness used to measure the
current breakage (`resize_window` does not work in this environment): for each
of {1512, 1200, 1000, 940, 870, 820, 740, 690, 500, 390} px × {EN, FR}, assert
`#partners`'s bottom does not exceed `#view-switcher`'s and that
`#footer-links` stays one row high. The 700–780px band that overflowed *before*
this work must come back clean too.

## Open question

The Oxford mark is supplied as a solid navy square, which once unboxed is the
darkest object in the footer even at 0.82. Their blue-on-white variant would
sit better in this palette. Not blocking — the factor handles it — but worth
requesting.
