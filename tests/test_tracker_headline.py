"""Static guards for the header headline-numbers block (#tracker).

The block is assembled by buildTracker() in Scripts/assets/engine.js from i18n
keys in locales/*.yaml, and painted by two stylesheets: Scripts/assets/
dashboard.css plus the optional brand layer Data/Branding/dashboard-theme.css.
Nothing at runtime checks that the four stay in agreement -- a locale key that
survives a rename, or a CSS rule left pointing at a deleted class, fails
silently and only in one of the two themes. These tests make that a build
failure.

See docs/superpowers/specs/2026-08-15-tracker-headline-numbers-design.md.
"""
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]

# ENGINE/CSS/THEME are read by the markup and stylesheet guards below; the
# locale guards above need only LOCALES.
ENGINE = REPO / "Scripts" / "assets" / "engine.js"
CSS = REPO / "Scripts" / "assets" / "dashboard.css"
THEME = REPO / "Data" / "Branding" / "dashboard-theme.css"
LOCALES = REPO / "locales"

LANGS = ("en", "fr")

# The abbreviations and the per-country row's labels. Removing them is the
# whole point of the redesign, so none may come back.
RETIRED_KEYS = ("outbreak_size", "conf", "susp", "conf_deaths", "susp_deaths")

REQUIRED_KEYS = (
    "eyebrow",
    "eyebrow_nodate",
    "cases",
    "deaths",
    "recovered",
    "suspected_one",
    "suspected_other",
)


def _tracker_strings(lang):
    data = yaml.safe_load((LOCALES / f"{lang}.yaml").read_text(encoding="utf-8"))
    return data["ui"]["tracker"]


def test_retired_tracker_keys_are_gone():
    for lang in LANGS:
        present = set(_tracker_strings(lang)) & set(RETIRED_KEYS)
        assert not present, (
            f"{lang}.yaml still defines retired ui.tracker keys: {sorted(present)}"
        )


def test_required_tracker_keys_present():
    for lang in LANGS:
        missing = set(REQUIRED_KEYS) - set(_tracker_strings(lang))
        assert not missing, (
            f"{lang}.yaml is missing ui.tracker keys: {sorted(missing)}"
        )


def test_tracker_keys_match_across_locales():
    en = set(_tracker_strings("en"))
    fr = set(_tracker_strings("fr"))
    assert en == fr, (
        f"ui.tracker keys differ: en-only={sorted(en - fr)}, "
        f"fr-only={sorted(fr - en)}"
    )


def test_eyebrow_placeholders():
    for lang in LANGS:
        tr = _tracker_strings(lang)
        assert "{date}" in tr["eyebrow"], (
            f"{lang} ui.tracker.eyebrow must interpolate {{date}}"
        )
        # eyebrow_nodate is what renders when PAYLOAD.asof is empty --
        # ASOF_FALLBACK is "" (data_sources.py:259) -- so it must not leave a
        # dangling "cumulative to ".
        assert "{date}" not in tr["eyebrow_nodate"], (
            f"{lang} ui.tracker.eyebrow_nodate must not interpolate {{date}}"
        )


def test_suspected_strings_interpolate_the_count():
    for lang in LANGS:
        tr = _tracker_strings(lang)
        for key in ("suspected_one", "suspected_other"):
            assert "{n}" in tr[key], (
                f"{lang} ui.tracker.{key} must interpolate {{n}}"
            )


def test_tracker_strings_are_lowercase():
    """#tracker .global-title and .global-cell .sub apply text-transform:
    uppercase, so a capitalised value renders doubly shouted -- or worse, looks
    deliberate. Store lowercase and let the CSS decide."""
    for lang in LANGS:
        for key, value in _tracker_strings(lang).items():
            assert value == value.lower(), (
                f"{lang} ui.tracker.{key} is not lowercase: {value!r}"
            )


def _build_tracker_source():
    """The body of buildTracker(), from its declaration to the next top-level
    function. Scoping the assertions this way keeps them from tripping over
    unrelated uses of the same words elsewhere in a 4000-line file."""
    src = ENGINE.read_text(encoding="utf-8")
    start = src.index("function buildTracker()")
    end = src.index("\nfunction ", start + 1)
    body = src[start:end]
    # The slice ends at the first column-0 "function", so a nested helper
    # declared flush-left would cut it short mid-function -- and every guard
    # below would then pass or fail for the wrong reason, silently. These two
    # assertions turn that into a loud failure instead.
    assert "tracker.innerHTML" in body, "buildTracker() source slice is truncated"
    assert body.rstrip().endswith("}"), "buildTracker() source slice is truncated"
    return body


def test_build_tracker_has_no_per_country_branch():
    body = _build_tracker_source()
    for token in ("countries-row", "tracker-countries", "per_country",
                  "conf-d", "susp-d"):
        assert token not in body, (
            f"buildTracker() still references {token!r}; the per-country row "
            f"was removed (totals.per_country stays in the payload, it is "
            f"only no longer rendered)"
        )
    # Word-boundary so a future countryCode/countrySelector is not a false
    # positive -- only the bare identifier the retired row used.
    assert not re.search(r"\bcountry\b", body), (
        "buildTracker() still references a bare `country` identifier; the "
        "per-country row was removed"
    )


def test_build_tracker_renders_the_qualifier():
    body = _build_tracker_source()
    for token in ("class='qual'", "class='qnum'",
                  "ui.tracker.suspected_one", "ui.tracker.suspected_other",
                  "ui.tracker.eyebrow", "ui.tracker.eyebrow_nodate"):
        assert token in body, f"buildTracker() should emit {token!r}"
    # The tokens above all live inside qualifier()'s own body, so they are
    # present whether or not it is ever called. Assert the two call sites too,
    # and that each is wired to the suspected field matching the confirmed
    # number it sits under.
    for call in ('qualifier(totals.global_suspected_cases, "suspected_cases")',
                 'qualifier(totals.global_suspected_deaths, "suspected_deaths")'):
        assert call in body, f"buildTracker() should call {call}"


def test_build_tracker_reads_confirmed_cases_not_total():
    body = _build_tracker_source()
    assert "global_confirmed_cases" in body
    assert "global_total_cases" not in body, (
        "the headline figure is labelled 'confirmed', so it reads "
        "totals.global_confirmed_cases; global_total_cases is an alias for the "
        "same number whose name no longer matches the label"
    )


def _tracker_lines(path):
    """Every line of the stylesheet that names a selector under #tracker.

    Comments are stripped first so a commented-out rule cannot satisfy or trip
    an assertion. Assumes each rule sits on one line, as dashboard.css does --
    for a stylesheet that splits selectors from declarations, this returns the
    selector lines only and sees no declarations at all.
    """
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    return "\n".join(ln for ln in text.splitlines() if "#tracker" in ln)


def _hex_luma(value):
    """Rough perceived brightness of a #rgb or #rrggbb colour, 0-255."""
    h = value.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def test_base_stylesheet_styles_the_qualifier():
    lines = _tracker_lines(CSS)
    assert "#tracker .global-cell .qual {" in lines
    assert "#tracker .global-cell .qual .qnum {" in lines
    # Hue is reserved for what is being counted, so a suspected figure gets
    # none -- its lower confidence is carried by tone alone. If these two
    # collapse to one colour, nothing in the block encodes that distinction.
    # The number is the brighter of the pair here because this is the dark
    # base layer; the brand layer inverts both, since its background does too.
    qual = re.search(r"#tracker \.global-cell \.qual \{[^}]*color:(#[0-9a-fA-F]{3,6})", lines)
    qnum = re.search(r"#tracker \.global-cell \.qual \.qnum \{[^}]*color:(#[0-9a-fA-F]{3,6})", lines)
    assert qual and qnum, "both .qual and .qual .qnum must declare a colour"
    assert _hex_luma(qnum.group(1)) > _hex_luma(qual.group(1)), (
        f"the suspected count ({qnum.group(1)}) must read brighter than the "
        f"word beside it ({qual.group(1)}) on the dark base layer"
    )


def test_global_row_is_top_aligned():
    # Three rules select .global-row (base plus two media queries); only the
    # base one declares alignment, so assert on the declaration rather than on
    # whichever rule happens to come first in the file.
    lines = [ln for ln in _tracker_lines(CSS).splitlines()
             if "#tracker .global-row" in ln]
    assert lines, "no #tracker .global-row rule found"
    assert any("align-items:flex-start" in ln for ln in lines), (
        "the recovered cell carries no .qual line, so aligning bottoms would "
        "drop its big number out of line with the other two"
    )
    assert not any("align-items:flex-end" in ln for ln in lines)


# Selectors the per-country row owned. Matched only against lines that already
# mention #tracker, so an unrelated .name or .dot elsewhere in the file is not
# our business. \.conf\b also matches .conf-d, which is retired too.
RETIRED_SELECTORS = (
    r"\.countries-row\b",
    r"\.country\b",
    r"\.conf\b",
    r"\.susp\b",
    r"\.dot\b",
    r"\.nums\b",
    r"\.name\b",
)

RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _rule_blocks(path):
    """(selector, declarations) for every brace-delimited rule in the file.
    @media openers do not match, because their bodies contain braces."""
    text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    return [(m.group(1).strip(), m.group(2)) for m in RULE.finditer(text)]


def test_base_stylesheet_has_no_country_row_rules():
    lines = _tracker_lines(CSS)
    for pattern in RETIRED_SELECTORS:
        assert not re.search(pattern, lines), (
            f"dashboard.css still styles {pattern} under #tracker"
        )


def test_no_rule_hides_the_eyebrow():
    # The eyebrow is the only place the block states its as-of date. Hiding it
    # on phones, as the old max-width:700px rule did, leaves three undated
    # numbers -- #header-narrow-row carries only the dashboard build time,
    # which is a different date.
    for selector, body in _rule_blocks(CSS):
        if "#tracker .global-title" in selector:
            assert "display:none" not in body.replace(" ", ""), (
                f"rule {selector!r} hides the eyebrow"
            )


def test_short_viewport_shrinks_the_qualifier():
    """A landscape phone must shrink .qual alongside .num and .sub, or the
    header grows taller than it did before. Asserting the selector is present
    is not enough -- an override no smaller than the base clamp's floor would
    satisfy that while shrinking nothing."""
    text = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    blocks = re.findall(r"@media \(max-height: 500px\) \{(.*?)\n  \}", text, re.DOTALL)
    assert blocks, "could not locate any @media (max-height: 500px) block"
    overrides = [m for m in
                 (re.search(r"#tracker \.global-cell \.qual \{([^}]*)\}", b) for b in blocks)
                 if m]
    assert overrides, "no short-viewport override for #tracker .global-cell .qual"
    shrunk = re.search(r"font-size:\s*([\d.]+)px", overrides[0].group(1))
    assert shrunk, "the short-viewport .qual rule must declare a font-size"
    # Two-space indent picks out the unconditional rule, not the nested one.
    base = re.search(r"^  #tracker \.global-cell \.qual \{([^}]*)\}", text, re.M)
    assert base, "no unconditional #tracker .global-cell .qual rule found"
    floor = re.search(r"font-size:\s*clamp\(\s*([\d.]+)px", base.group(1))
    assert floor, "the base .qual rule must declare a clamp() font-size"
    assert float(shrunk.group(1)) < float(floor.group(1)), (
        f"the short-viewport override ({shrunk.group(1)}px) is not smaller than "
        f"the base clamp's floor ({floor.group(1)}px), so it shrinks nothing"
    )


def _tracker_declarations(path):
    """The declaration bodies of every rule selecting under #tracker. The theme
    layer puts selectors and declarations on separate lines, so _tracker_lines()
    sees no colours at all -- this is the one that does."""
    return "\n".join(body for sel, body in _rule_blocks(path) if "#tracker" in sel)


def test_theme_layer_has_no_country_row_rules():
    lines = _tracker_lines(THEME)
    for pattern in RETIRED_SELECTORS:
        assert not re.search(pattern, lines), (
            f"dashboard-theme.css still styles {pattern} under #tracker"
        )


def test_theme_layer_drops_the_hardcoded_rust():
    assert "#a66b55" not in THEME.read_text(encoding="utf-8"), (
        "the suspected-deaths colour was the one hard-coded hex in the tracker "
        "theme rules; it leaves with the row it painted"
    )


def test_theme_layer_styles_the_qualifier():
    lines = _tracker_lines(THEME)
    assert "#tracker .global-cell .qual" in lines
    assert "#tracker .global-cell .qual .qnum" in lines


def test_tracker_hues_are_one_meaning_each():
    """Each headline hue names exactly one thing. The collision this redesign
    removes was --terracotta painting both confirmed cases and suspected
    cases."""
    decls = _tracker_declarations(THEME)
    for token in ("var(--maroon)", "var(--green)"):
        assert decls.count(token) == 1, (
            f"{token} is used {decls.count(token)} times under #tracker; each "
            f"hue must name exactly one thing"
        )
    # --terracotta is the cases hue and also the caveat mark, which annotates a
    # number rather than being one. Two uses, no more.
    assert decls.count("var(--terracotta)") == 2
    assert "var(--red)" not in decls


def test_tracker_media_rules_come_after_the_base_rules():
    """Media queries add no specificity. An equal-specificity #tracker rule in
    an @media block that sits EARLIER in the file therefore loses the
    source-order tiebreak to the unconditional rule below it, and silently does
    nothing -- no warning, no visible error, it just never applies. Every
    #tracker media override has to sit after the base block."""
    text = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    lines = text.splitlines()
    base, nested = [], []
    for i, ln in enumerate(lines):
        m = re.match(r"( *)#tracker\b", ln)
        if not m:
            continue
        # Bucket on the measured indent rather than two fixed widths: an
        # oddly-indented rule then lands in a bucket instead of disappearing
        # from both, which would hide exactly the bug this test exists to catch.
        (base if len(m.group(1)) <= 2 else nested).append(i)
    assert base, "no unconditional #tracker rules found"
    assert nested, "no @media #tracker rules found"
    assert min(nested) > max(base), (
        f"an @media #tracker rule at line {min(nested) + 1} sits before the "
        f"last unconditional rule at line {max(base) + 1}; it loses the "
        f"source-order tiebreak and will silently never apply"
    )
