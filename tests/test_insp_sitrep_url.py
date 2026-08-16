"""INSP sitrep permalink parsing.

INSP has renamed the sitrep slug at least twice during this outbreak:

    legacy      sitrep-mve-n-031-2026            (shared with other diseases)
    modern v1   sitrep-n072-mvb_25-07-2026       (up to #072, 25 Jul 2026)
    modern v2   sitrep-n092-mvebdb-14-08-2026    (from #073 on)

The v1 -> v2 rename (``mvb_`` -> ``mvebdb-``) went unnoticed for three weeks
because the scraper does not fail when it stops recognising slugs -- it just
keeps returning the newest slug it still understands, so the dashboard header
quietly linked #072 while INSP had published through #092. These tests pin
every shape we have seen so a future rename fails loudly here instead.
"""

import datetime
import importlib

ds = importlib.import_module("common.data_sources")

LEGACY = "sitrep-mve-n-031-2026"
MODERN_V1 = "sitrep-n072-mvb_25-07-2026"
MODERN_V2 = "sitrep-n092-mvebdb-14-08-2026"


def test_sitrep_number_parsed_from_every_known_slug_shape():
    assert ds._sitrep_num_from_slug(LEGACY) == 31
    assert ds._sitrep_num_from_slug(MODERN_V1) == 72
    assert ds._sitrep_num_from_slug(MODERN_V2) == 92


def test_current_slug_shape_is_recognised_as_a_bdbv_sitrep():
    # The v2 shape is what INSP publishes today; if this stops holding, the
    # scraper silently falls back to older sitreps.
    assert ds._is_bdbv_insp_sitrep_slug(MODERN_V2)
    assert ds._is_bdbv_insp_sitrep_slug(MODERN_V1)


def test_low_numbered_legacy_slugs_stay_excluded():
    # Legacy ``sitrep-mve-n-NNN-YYYY`` is shared with other diseases; only the
    # high numbers belong to this outbreak.
    assert not ds._is_bdbv_insp_sitrep_slug("sitrep-mve-n-003-2025")


def test_latest_pick_prefers_the_newest_sitrep_across_a_rename():
    # The real failure: with both naming eras in the candidate set, picking by
    # "slug looks like the naming era I know" returns the stale one. #092 must
    # win over #072 even though only #072 carries the older ``-mvb_`` marker.
    candidates = {
        72: f"{ds.INSP_BASE_URL}{MODERN_V1}/",
        90: f"{ds.INSP_BASE_URL}sitrep-n090-mvebdb-12-08-2026/",
        92: f"{ds.INSP_BASE_URL}{MODERN_V2}/",
    }
    assert ds._pick_latest_sitrep_url(candidates) == candidates[92]


def test_latest_pick_still_ignores_unrelated_high_numbered_legacy():
    # A legacy slug alone still resolves, so the offline/homepage paths that
    # only ever see legacy URLs keep working.
    candidates = {31: f"{ds.INSP_BASE_URL}{LEGACY}/"}
    assert ds._pick_latest_sitrep_url(candidates) == candidates[31]


def _candidates(*pairs):
    return {num: f"{ds.INSP_BASE_URL}{slug}/" for num, slug in pairs}


def test_report_date_parsed_from_modern_slug():
    assert ds._sitrep_date_from_slug(MODERN_V2) == datetime.date(2026, 8, 14)
    assert ds._sitrep_date_from_slug(MODERN_V1) == datetime.date(2026, 7, 25)
    assert ds._sitrep_date_from_slug(LEGACY) is None


def test_link_follows_the_data_not_the_newest_publication():
    # The header renders link and as-of date as one phrase, so the link must be
    # the report the displayed numbers came from. Transcription runs behind
    # publication: data stops at #089 (11 Aug) while INSP is at #092 (14 Aug).
    cands = _candidates(
        (89, "sitrep-n089-mvebdb-11-08-2026"),
        (90, "sitrep-n090-mvebdb-12-08-2026"),
        (91, "sitrep-n091-mvebdb-13-08-2026"),
        (92, MODERN_V2),
    )
    picked = ds._pick_sitrep_url_for_date(cands, datetime.date(2026, 8, 11))
    assert picked == cands[89]


def test_link_never_points_ahead_of_the_data_when_no_exact_match():
    # Date convention drifted or that day's report is missing: take the newest
    # report that is not ahead of the data, never a later one.
    cands = _candidates(
        (89, "sitrep-n089-mvebdb-11-08-2026"),
        (92, MODERN_V2),
    )
    picked = ds._pick_sitrep_url_for_date(cands, datetime.date(2026, 8, 12))
    assert picked == cands[89]


def test_no_link_when_every_candidate_is_newer_than_the_data():
    # Nothing here is the source of the displayed numbers; the caller drops to
    # the INSP index rather than linking a report the dashboard does not show.
    cands = _candidates((92, MODERN_V2))
    assert ds._pick_sitrep_url_for_date(cands, datetime.date(2026, 7, 1)) is None


def test_urls_are_collected_from_page_text_in_the_current_shape():
    html = (
        '<a href="https://insp.cd/sitrep-n091-mvebdb-13-08-2026/">SitRep 91</a>'
        '<a href="/sitrep-n092-mvebdb-14-08-2026/">SitRep 92</a>'
        '<a href="https://insp.cd/ebola-17eme-epidemie/">not a sitrep</a>'
    )
    found = ds._collect_insp_sitrep_urls_from_text(html)
    assert set(found) == {91, 92}
    assert found[92] == f"{ds.INSP_BASE_URL}{MODERN_V2}/"
