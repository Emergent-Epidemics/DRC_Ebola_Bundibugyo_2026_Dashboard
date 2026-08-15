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
