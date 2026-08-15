# Restructuring the header headline numbers (`#tracker`)

**Date:** 2026-08-15
**Status:** Design approved, ready for implementation planning
**Mockups:** `.superpowers/brainstorm/62706-1786756437/content/` (gitignored)

## Problem

The outbreak-size block in the top-right of `#site-header` renders two rows of numbers built by
`buildTracker()` (`Scripts/assets/engine.js:368-430`):

```
                          OUTBREAK SIZE (CONFIRMED)
                     4,566          2,128          918
                     CASES          DEATHS         RECOVERED
     DRC  4,566 conf · 270 susp · 2,128 conf deaths · 91 susp deaths
```

Four problems:

1. **Numbers repeat.** 4,566 and 2,128 each appear twice — the big `cases` cell is
   `totals.global_total_cases`, which `_national_totals_from_build_geojson()` sets to the
   confirmed count, and `deaths` is `global_confirmed_deaths`. The lower row genuinely adds only
   two figures (270 suspected cases, 91 suspected deaths). Recovered never repeats, so the two
   rows are not even parallel.

2. **Abbreviations without space pressure.** `conf` / `susp` / `conf deaths` / `susp deaths`
   save roughly 14 characters on a line with room to spare. French renders them `conf.` /
   `décès susp.`, which reads worse.

3. **`DRC` labels a country row for a one-country outbreak.** `totals.per_country` is an array,
   but it is built from the `national_*` fields of the build GeoJSON and can hold exactly one
   entry. The outbreak is DRC-only and will remain so. Meanwhile the big row above is silently
   DRC-only too and says so nowhere.

4. **Colour is inconsistent.** In the live theme (`Data/Branding/dashboard-theme.css:153-193`)
   `--terracotta` is both the big **confirmed** cases number and the small **suspected** cases
   number, while confirmed cases in the small row is `--red`. One swatch, two meanings, four
   inches apart. Suspected deaths uses a hard-coded `#a66b55` rather than a token.

| Element | Base (`dashboard.css`) | Live theme |
|---|---|---|
| `.global-cell.cases .num` | `#ffd166` | `--terracotta` `#9b7d4e` |
| `.global-cell.deaths .num` | `#ff4d4d` | `--maroon` `#7c1d1d` |
| `.global-cell.recovered .num` | `#8CD790` | `--green` `#285943` |
| `.country .conf` | `#ff6b6b` | `--red` `#b23b2e` |
| `.country .susp` | `#ffae42` | `--terracotta` `#9b7d4e` |
| `.country .conf-d` | `#c97a8a` | `--maroon` `#7c1d1d` |
| `.country .susp-d` | `#caa385` | `#a66b55` (hard-coded) |

## Requirements

1. No number appears more than once.
2. No abbreviations at any width the block is actually rendered at.
3. No country label; the block states its own scope once, or not at all.
4. One colour means one thing.
5. Suspected figures stay visible at every breakpoint, subordinate to confirmed.
6. Recovered stays a full-size headline number alongside cases and deaths.

## Target

```
                    CONFIRMED · CUMULATIVE TO 11 AUG 2026
                 4,566          2,128          918
                 CASES          DEATHS         RECOVERED
                 270 suspected  91 suspected
```

Each metric owns a column. Where a suspected count exists it hangs directly beneath that
metric's label, so it can only be read against the right number. Recovered has no qualifier and
simply ends one line earlier.

### Why "confirmed" sits in the eyebrow

Putting it on each label (`Confirmed cases`, `Confirmed deaths`, `Recovered`) states it twice,
leaves recovered visually unqualified, and makes each label roughly twice the width of the
number above it. The eyebrow already exists and is already where the block declares its own
scope, so one mention there covers all three columns, keeps the labels at their current width,
and makes the qualifier read as a direct contrast: *Cases → 4,566, and 270 more suspected.*

### Why "DRC" is deleted rather than moved

The `<h1>` immediately to the left reads "DRC Ebola Bundibugyo — Epidemic Intelligence
Dashboard", and the outbreak is DRC-only by definition. Restating the country adds nothing. The
freed line carries something the block currently never says — the date the totals are as of.

## Colour system

**Hue encodes what is being counted. Neutrality encodes lower confidence.**

Suspected figures are deliberately given no hue of their own: they are not a different thing
being counted, they are the same thing, less certain. Size and neutrality carry that distinction,
so no swatch can mean two things.

| Role | Base (`dashboard.css`) | Live theme |
|---|---|---|
| cases | `#ffd166` | `--terracotta` |
| deaths | `#ff4d4d` | `--maroon` |
| recovered | `#8CD790` | `--green` |
| suspected counts (`.qual .qnum`) | `#ddd` | `--ink` |
| all labels, eyebrow, the word "suspected" | `#bbb` | `--muted` |

Six hues become three plus a neutral. `--red` and the hard-coded `#a66b55` leave the header
entirely.

The theme layer is optional — `build_dashboard.py` appends it only when non-empty
(`Scripts/common/theme.py:load_theme_css`) — so the base dark palette in `dashboard.css` must
remain coherent standalone. Both layers change together.

## Markup

`buildTracker()` emits:

```html
<div class="stats-block">
  <div class="global-title">Confirmed · cumulative to 11 Aug 2026</div>
  <div class="global-row">
    <div class="global-cell cases">
      <div class="num">4,566</div>
      <div class="sub">Cases</div>
      <div class="qual"><span class="qnum">270</span> suspected</div>   <!-- new -->
    </div>
    <div class="global-cell deaths">
      <div class="num">2,128</div>
      <div class="sub">Deaths</div>
      <div class="qual"><span class="qnum">91</span> suspected</div>
    </div>
    <div class="global-cell recovered">                                <!-- no .qual -->
      <div class="num">918</div>
      <div class="sub">Recovered</div>
    </div>
  </div>
</div>
<div class="tracker-footnotes"> … </div>                               <!-- unchanged -->
```

Deleted from `buildTracker()` and from both stylesheets: `.countries-row`, `.country`, `.name`,
`.nums`, `.conf`, `.susp`, `.conf-d`, `.susp-d`, `.dot` — the whole per-country branch, nine CSS
rules in `dashboard.css` and seven in `Data/Branding/dashboard-theme.css`.

`.qual` is omitted entirely when the suspected count is 0; it never renders "0 suspected".

New base rules in `dashboard.css`, matching the existing `.sub` idiom:

```css
#tracker .global-cell .qual {
  font-size: clamp(9.5px, 1.5vw, 10.5px);
  color: #bbb;
  margin-top: 3px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
#tracker .global-cell .qual .qnum { color: #ddd; font-weight: 600; }
```

`.qual` is **not** uppercased or letter-spaced, unlike `.sub` and `.global-title` — it is a
sentence fragment, not a label, and the lowercase reinforces its subordinate role.

Its nominal size is half a pixel *larger* than `.sub`'s, which looks backwards for a subordinate
line and is not. `.sub` is uppercase, so its cap-height carries the reading; `.qual` is lowercase
and rides on a smaller x-height. At 10.5px lowercase (x-height ≈ 5.4px) it still reads smaller
than 10px uppercase (cap-height ≈ 7.2px).

`white-space:nowrap` on `.qual` is safe because `#site-header` sets `flex-wrap:wrap`: a suspected
count long enough to widen its cell pushes `#site-header-right` onto its own row rather than
overflowing the viewport.

### Field read for the headline cases figure

Switches from `totals.global_total_cases` to `totals.global_confirmed_cases`. Both producers set
them to the same value — `data_sources.py:974` and `:3128` each assign the confirmed count to
`global_total_cases` — so nothing changes numerically. But the label now says "confirmed", and a
field named `global_total_cases` reads like it includes suspected. The rename makes the code say
what the UI says.

### `.global-row` alignment

Flips from `align-items:flex-end` to `align-items:flex-start`. With bottoms aligned, the
recovered cell — one line shorter than the other two — would push its big number down out of
line with the others. Top-aligning puts all three big numbers on one baseline and lets the
ragged edge fall harmlessly at the bottom.

### Caveat marks

`countWithMark()` currently decorates per-country numbers only. It moves up to decorate the
headline numbers and the qualifier numbers, keyed by the same metric names, so `Data/caveats.csv`
keeps working untouched. The file is empty today; the machinery stays live.

## Strings

`locales/en.yaml` and `locales/fr.yaml`, under `ui.tracker`:

| key | en | fr | |
|---|---|---|---|
| `eyebrow` | `confirmed · cumulative to {date}` | `confirmés · cumul au {date}` | new |
| `eyebrow_nodate` | `confirmed · cumulative` | `confirmés · cumul` | new |
| `cases` | `cases` | `cas` | unchanged |
| `deaths` | `deaths` | `décès` | unchanged |
| `recovered` | `recovered` | `guéris` | unchanged |
| `suspected_one` | `{n} suspected` | `{n} suspect` | new |
| `suspected_other` | `{n} suspected` | `{n} suspects` | new |
| `outbreak_size` | | | deleted |
| `conf`, `susp`, `conf_deaths`, `susp_deaths` | | | deleted |

`tf(path, vars)` (`engine.js:73`) already performs `{date}` / `{n}` substitution. The
singular/plural pair is load-bearing only in French (`suspect` vs `suspects`); English is
invariant either way, and a count of exactly 1 is plausible enough to justify the two keys.
Selection is `n === 1 ? suspected_one : suspected_other`.

`{date}` is filled from `PAYLOAD.asof`. That value can legitimately be empty —
`ASOF_FALLBACK` is `""` (`data_sources.py:259`) and `detect_asof()` returns it when neither
local sitrep CSVs nor the build GeoJSON yield a date — so a falsy `asof` selects
`eyebrow_nodate` instead, rather than rendering "cumulative to " with nothing after it.

All values are stored lowercase, as `outbreak_size` is today; `#tracker .global-title` already
carries `text-transform:uppercase`, so the eyebrow renders as
`CONFIRMED · CUMULATIVE TO 11 AUG 2026` without the strings themselves shouting.

## Responsive behaviour

Measured at 390px: three columns of full-word labels plus qualifiers occupy roughly 260px of the
~374px available. No abbreviation is needed at any rendered width, which is the whole argument
for not abbreviating at 1400px either.

- **`@media (max-width: 700px)`** — the rule hiding `.countries-row` becomes moot (node deleted).
  The rule hiding `.global-title` is **removed**, so the eyebrow survives onto phones and the
  numbers are no longer undated; the narrow info row carries only "dashboard last updated", a
  different date. `.qual` stays visible with full words.
- **`@media (max-height: 500px)`** — the `.countries-row` line is removed and
  `.qual { font-size:9px; margin-top:1px; }` added alongside the existing `.num` / `.sub` shrink
  rules, so a landscape phone does not grow the header.
- **Both blocks move.** See below — this is a correctness fix, not a tidy-up.

### The media overrides were dead, and had been all along

Every `#tracker` rule in the two media blocks sat **before** the unconditional `#tracker` block in
the file. Media queries add no specificity, so for an equal-specificity selector the cascade falls
through to source order — and the unconditional rule, being later, won every conflicting
declaration:

| Declaration in the media block | Intended | Actually rendered |
|---|---|---|
| `#tracker { padding:0 2px }` (both blocks) | 2px | 4px |
| `.global-row { gap:14px }` / `gap:clamp(8px,3vh,16px)` | tighter | `clamp(14px,6vw,36px)` |
| `.global-title { font-size:9px; margin-bottom:0 }` | 9px | `clamp(9px,1.5vw,10px)` |
| `.global-cell .num { font-size:clamp(16px,4.5vh,22px) }` | ≤22px | `clamp(20px,6vw,30px)` |
| `.global-cell .sub { font-size:9px; margin-top:0 }` | 9px | `clamp(9px,1.5vw,10px)` |

Only the `display:none` that hid the eyebrow ever took effect, because the cascade resolves per
property and no base rule declares `display`.

The file already contained the fix idiom: a third `@media (max-width: 700px)` block placed *after*
the base rules, carrying the narrow-screen centring overrides, with a comment explaining it had to
go there to win. Nobody had applied that to the other two blocks.

**Resolution:** every `#tracker` media rule moves below the unconditional block, merged into two
blocks — `max-width:700px` first, then `max-height:500px`, preserving the original relative order
so a landscape phone matching both still takes the tighter `gap`. Non-`#tracker` rules stay where
they are. The blast radius is `#tracker` only, which is the component this spec already owns.

`tests/test_tracker_headline.py::test_tracker_media_rules_come_after_the_base_rules` makes a
recurrence a build failure, comparing the line index of the last two-space-indented `#tracker`
rule against the first four-space-indented one.

Verified in headless Chrome at `innerHeight` 363px: `.qual` went 10.5px → 9px, `.sub` → 9px,
`.num` → 16.3px; at `innerHeight` 813px the base clamps still apply.

## Not changing

- **The payload.** `totals.per_country` stays in the JSON; only the header stops rendering it.
  No Python is touched, so the change is visible without a rebuild.
- **`#imperial-model-estimates`**, the footnotes block, and the narrow-screen info popup.

## Known limitation (accepted)

The eyebrow states a single as-of date, but the underlying figures do not share one. Each
national metric in the build GeoJSON carries its own `_date`, and they diverge — in the current
build:

```
national_cumulative_confirmed_cases    2026-08-02
national_cumulative_confirmed_deaths   2026-08-02
national_cumulative_recovered_cases    2026-08-02
national_cumulative_suspected_cases    2026-08-02
national_cumulative_suspected_deaths   2026-07-11
```

`_national_totals_from_build_geojson()` (`data_sources.py:920-978`) reads the values and discards
`_date`. `detect_asof()` (`data_sources.py:529-557`) returns the **maximum** date across all
sitrep fields, so `PAYLOAD.asof` is the freshest date in the file — the wrong stamp for the
stalest number.

This was weighed against threading `_date` through the payload and dating stale metrics inline.
The single-date form was chosen for simplicity and readability; the overstatement is accepted.
If it becomes material, `Data/caveats.csv` can already attach a footnote to `suspected_deaths`
without any code change.

Related: the caveat metric alias map (`data_sources.py:986-998`) has no `recovered_cases` entry,
so no footnote can currently be attached to the recovered figure even though it is now a headline
number. Out of scope here — it is a three-line addition if wanted later.

## Verification

- `python3.9 -m pytest` from `Scripts/`. No test currently references `#tracker` or its classes,
  so this is a regression check on the build, not on this change.
- Build and serve over HTTP; confirm at 1280px, 900px, 390px, and at 800×450 (landscape phone):
  no number appears twice, no abbreviation appears, the eyebrow is present at every width, and
  the three big numbers share a baseline.
- Switch language to French and re-check the eyebrow, labels and qualifier agreement.
- Grep both stylesheets and both locale files for `conf`, `susp`, `countries-row`, `outbreak_size`
  to confirm nothing orphaned survives.
- Temporarily add a `suspected_deaths` row to `Data/caveats.csv` and confirm the mark lands on
  the qualifier number and the footnote renders.
