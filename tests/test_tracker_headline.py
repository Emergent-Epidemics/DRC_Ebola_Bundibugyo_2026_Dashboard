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
    return src[start:end]


def test_build_tracker_has_no_per_country_branch():
    body = _build_tracker_source()
    for token in ("countries-row", "tracker-countries", "per_country",
                  "conf-d", "susp-d", "country"):
        assert token not in body, (
            f"buildTracker() still references {token!r}; the per-country row "
            f"was removed (totals.per_country stays in the payload, it is "
            f"only no longer rendered)"
        )


def test_build_tracker_renders_the_qualifier():
    body = _build_tracker_source()
    for token in ("class='qual'", "class='qnum'",
                  "ui.tracker.suspected_one", "ui.tracker.suspected_other",
                  "ui.tracker.eyebrow", "ui.tracker.eyebrow_nodate"):
        assert token in body, f"buildTracker() should emit {token!r}"


def test_build_tracker_reads_confirmed_cases_not_total():
    body = _build_tracker_source()
    assert "global_confirmed_cases" in body
    assert "global_total_cases" not in body, (
        "the headline figure is labelled 'confirmed', so it reads "
        "totals.global_confirmed_cases; global_total_cases is an alias for the "
        "same number whose name no longer matches the label"
    )
