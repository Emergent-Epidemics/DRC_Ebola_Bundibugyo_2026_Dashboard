#!/usr/bin/env python3
"""
SUPERSEDED -- kept only for reference during the multi-page migration.

This single-file build script has been replaced by Scripts/build_dashboard.py
(the new master/orchestrator) plus Scripts/common/, Scripts/pages/, and
Scripts/assets/ (see README "Multi-page structure"). Every function here was
moved, not rewritten, into the new module layout. This file is no longer
called by CI or by anything else in this repo.

Safe to delete once you've confirmed the new build matches this one; it is
left in place (rather than deleted) only because this sandbox could not
remove the file -- please delete it manually (along with Scripts/__pycache__)
when convenient.

Original docstring follows unchanged below.
---------------------------------------------------------------------------
Build the DRC Ebola Bundibugyo 2026 dashboard as a single self-contained
HTML file from publicly available inputs.

Usage
-----
    python build_dashboard.py

Layout
------
The script reads everything from a single ``Data/`` directory that lives at
the project root, alongside the ``Scripts/`` folder containing this file::

    project_root/
    ├── Scripts/
    │   └── build_dashboard_public.py    (this file)
    ├── Data/
    │   ├── health_zone_metadata.csv         per-zone metrics (one row per zone)
    │   ├── caveats.csv                      optional tracker footnotes (metric + warning)
    │   ├── DRC Health Zones/<*.shp,*.dbf,*.shx,*.prj,...>
    │   │                                    OMS/DSNIS administrative boundaries
    │   ├── Epidemiological Data/<YYYY-MM-DD>.csv
    │   │                                    INSP situation-report CSVs (one per date;
    │   │                                    most recent is used for the header banner)
    │   ├── Methods/Contributors_Methods_Data_website.docx
    │   │                                    Contributors / Data / Methods text shown
    │   │                                    inside the "Contributors, Data, and Methods"
    │   │                                    modal. Hyperlinks and headings in the docx
    │   │                                    are preserved.
    │   ├── ToS/Terms of Use.txt             plain-text Terms of Use
    │   ├── Branding/                        partner logos + URLs map
    │   │   ├── urls.txt                     "<filename>, <https url>" per line
    │   │   ├── inrb.png
    │   │   ├── INSP.jpeg
    │   │   ├── UMIE.jpeg
    │   │   └── WHO.jpg
    │   └── Refugee_IDP sites/<*.geojson>    (optional; the dashboard exposes only
    │                                         per-zone aggregates, never coordinates)
    └── output/
        └── dashboard.html                   build artefact

Set the ``DATA_ROOT`` environment variable to override the default Data/
location (useful when testing from a different working directory).

Inputs are tolerated when missing: the corresponding layers / sections are
hidden and a warning is printed.
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import ssl
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid


# ---------------------------------------------------------------------------
# paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("DATA_ROOT") or (SCRIPT_DIR.parent / "Data")).resolve()
OUTPUT_DIR = SCRIPT_DIR.parent / "output"
OUTPUT_PATH = OUTPUT_DIR / "dashboard.html"

BUILD_DIR = Path(os.environ.get("BUILD_DIR") or
                 (SCRIPT_DIR.parent.parent / "BDBV2026-Data" / "build")).resolve()
BUILD_GEOJSON    = BUILD_DIR / "drc_health_zones.geojson"
BUILD_MANIFEST   = BUILD_DIR / "manifest.json"
BUILD_LONG_DIR   = BUILD_DIR / "long"
EXTERNAL_DATA    = BUILD_DIR.parent / "data"
FLOWMINDER_PROCESSED = (
    Path(os.environ["FLOWMINDER_DIR"]).resolve()
    if os.environ.get("FLOWMINDER_DIR")
    else (BUILD_DIR.parent / "data" / "flowminder" / "processed")
)
FLOWMINDER_SHORT_TRIPS_PROCESSED = (
    EXTERNAL_DATA / "flowminder_short_trips" / "processed"
)
# NOTE: read directly from data/osrm/processed/, not build/long/. Matrices are
# deliberately excluded from tools.build_geojson (see that script's docstring),
# so build/long/osrm__*.csv is never regenerated and goes stale silently.
OSRM_PROCESSED   = EXTERNAL_DATA / "osrm" / "processed"
OSRM_TRAVEL_TIME_CSV = OSRM_PROCESSED / "osrm__travel_time__static.matrix.csv"
OSRM_ROAD_DISTANCE_CSV = OSRM_PROCESSED / "osrm__road_distance__static.matrix.csv"
DATA_REPO        = os.environ.get("DATA_REPO", "INRB-UMIE/BDBV2026-Data").strip()

METADATA_CSV     = DATA_ROOT / "health_zone_metadata.csv"
IC_MODEL_CSV     = DATA_ROOT / "ic_model_estimates.csv"
CAVEATS_CSV      = DATA_ROOT / "caveats.csv"
INVASION_RISK_CSV = DATA_ROOT / "invasion_risk_model_estimates.csv"
DASHBOARD_PLOTS_DIR = DATA_ROOT / "dashboard_plots"
SIT_REPS_DIR     = DATA_ROOT / "Epidemiological Data"
METHODS_DOCX     = DATA_ROOT / "Methods" / "Contributors_Methods_Data_website.docx"
METHODS_DOCX_FR  = DATA_ROOT / "Methods" / "Contributors_Methods_Data_website_fr.docx"
METHODS_HTML_FR  = DATA_ROOT / "Methods" / "Contributors_Methods_Data_website_fr.html"
TERMS_TXT        = DATA_ROOT / "ToS" / "Terms of Use.txt"
TERMS_TXT_FR     = DATA_ROOT / "ToS" / "Terms of Use_fr.txt"
BRANDING_DIR     = DATA_ROOT / "Branding"
BRANDING_URLS    = BRANDING_DIR / "urls.txt"
THEME_CSS        = BRANDING_DIR / "dashboard-theme.css"
LOCALES_DIR      = SCRIPT_DIR.parent / "locales"
SUPPORTED_LANGS  = ("en", "fr")


# ---------------------------------------------------------------------------
# visual constants
# ---------------------------------------------------------------------------

SIMPLIFY_TOL = 0.001     # ~110 m at the equator; ~10× fewer vertices than raw
COORD_DECIMALS = 5
TRAVEL_FROM_ZONE = "Mongbwalu"
# Canonical ``nom`` values for outbreak epicentres (Flowminder outflow sources).
EPICENTER_ITURI_SINGLE = ("Bunia", "Mongbwalu", "Rwampara")
EPICENTER_ITURI_COHORT = ("Bunia", "Mongbwalu", "Rwampara", "Nyankunde")
EPICENTER_NK_COHORT = ("Beni", "Butembo", "Katwa")
EPICENTER_SOURCE_NOMS = EPICENTER_ITURI_SINGLE
EPICENTER_FILL = "#7695E1"
ASOF_FALLBACK = ""
INSP_BASE_URL = "https://insp.cd/"
INSP_FALLBACK_URL = INSP_BASE_URL
LATEST_SITREP_JSON = SIT_REPS_DIR / "latest_sitrep.json"
INSP_FETCH_TIMEOUT_S = float(os.environ.get("INSP_FETCH_TIMEOUT", "25"))
INSP_FETCH_USER_AGENT = "BDBV2026-Dashboard-Build/1.0"
# Set INSP_SITREP_FETCH=0 to skip live INSP requests (offline / reproducible builds).
INSP_SITREP_FETCH = os.environ.get("INSP_SITREP_FETCH", "1").strip().lower() not in (
    "0", "false", "no", "off",
)

# Slugs for the Bundibugyo Ebola sitrep series on insp.cd (not generic MVE carousel pages).
_SITREP_SLUG_MODERN_RE = re.compile(r"sitrep-n(\d{1,3})-(mvb|mve)_", re.I)
_SITREP_SLUG_LEGACY_RE = re.compile(r"sitrep-mve-n-(\d{1,3})-(\d{4})", re.I)
_INSP_SITREP_PATH_RE = re.compile(
    r"(?:https?://(?:www\.)?insp\.cd)?(/sitrep-[\w-]+/?)",
    re.I,
)

# Maps metadata CSV names → build GeoJSON nom values where they differ.
# NOTE: the 2026-07 shapefile update renamed 13 zones to match what this
# metadata CSV already called them (e.g. "Mongbwalu" was an alias for the old
# canonical "Mongbalu"; the shapefile switch made "Mongbwalu" canonical), so
# those entries were removed as redundant. The remaining entries are either
# unrelated metadata-CSV spelling variants, or (Nsona-Pangu, Pendjua) updated
# to point at the new canonical noms.
_NAME_TO_NOM = {
    "Gungu (Secteur)": "Gungu",
    "Idiofa (Secteur)": "Idiofa",
    "Kabondo-Dianda": "Kabondo Dianda",
    "Kasongo-Lunda": "Kasongo Lunda",
    "Lubunga": "Lubunga (Tshopo)",
    "Nsona-Pangu": "Nsona Mpangu",
    "Nyirangongo": "Nyiragongo",
    "Pendjua": "Pendjwa",
}
_NOM_TO_NAME = {v: k for k, v in _NAME_TO_NOM.items()}

PARTNER_ORDER = ["INSP.png", "inrb.png", "UMIE.jpeg", "africa-cdc.png", "WHO.jpg"]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _parse_sitrep_date(value) -> datetime.date | None:
    """Parse INSP sitrep ``_date`` strings from build GeoJSON.

    Supports ISO (``2026-05-28``), day-first (``28/05/2026``), and month-first
    short US-style (``5/28/26``) as used in the data pipeline.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    if "/" not in s:
        return None
    parts = s.split("/")
    if len(parts) != 3:
        return None
    try:
        a, b, y = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None
    year = y + 2000 if y < 100 else y
    if a > 12:
        try:
            return datetime(year, b, a).date()
        except ValueError:
            return None
    if b > 12:
        try:
            return datetime(year, a, b).date()
        except ValueError:
            return None
    # Ambiguous d/m vs m/d: prefer day-first (INSP DRC convention).
    for month, day in ((b, a), (a, b)):
        try:
            return datetime(year, month, day).date()
        except ValueError:
            continue
    return None


def _format_asof(d: datetime.date) -> str:
    return d.strftime("%d %b %Y").lstrip("0")


def _parse_csv_stem_date(stem: str) -> datetime.date | None:
    """Parse ``YYYY-MM-DD`` from Epidemiological Data CSV filenames."""
    try:
        return datetime.strptime(stem, "%Y-%m-%d").date()
    except ValueError:
        return None


def _insp_live_fetch_enabled() -> bool:
    return INSP_SITREP_FETCH


def _insp_http_get(url: str) -> str | None:
    """GET *url*; return response body text or None on failure."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": INSP_FETCH_USER_AGENT, "Accept": "*/*"},
    )
    try:
        with urllib.request.urlopen(
            req, timeout=INSP_FETCH_TIMEOUT_S, context=ssl.create_default_context(),
        ) as resp:
            encoding = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(encoding, errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"  NOTE: INSP fetch failed for {url}: {exc}")
        return None


def _normalize_insp_sitrep_url(path_or_url: str) -> str | None:
    """Return a canonical https://insp.cd/.../ URL for a sitrep path or slug."""
    s = path_or_url.strip()
    if not s:
        return None
    if s.startswith("http"):
        base = s.rstrip("/") + "/"
        if "insp.cd" not in base.lower():
            return None
        return base
    if not s.startswith("/"):
        s = "/" + s
    slug = s.strip("/").split("?")[0].split("#")[0]
    if not slug.lower().startswith("sitrep-"):
        return None
    return f"{INSP_BASE_URL}{slug}/"


def _sitrep_num_from_slug(slug: str) -> int | None:
    slug = slug.strip("/").lower()
    m = _SITREP_SLUG_MODERN_RE.search(slug)
    if m:
        return int(m.group(1))
    m = _SITREP_SLUG_LEGACY_RE.search(slug)
    if m:
        return int(m.group(1))
    return None


def _is_bdbv_insp_sitrep_slug(slug: str) -> bool:
    """True for Bundibugyo Ebola sitrep permalinks (excludes unrelated MVE pages)."""
    s = slug.strip("/").lower()
    if _SITREP_SLUG_MODERN_RE.search(s):
        return True
    m = _SITREP_SLUG_LEGACY_RE.search(s)
    # Legacy ``sitrep-mve-n-NNN-YYYY`` is shared with other diseases; keep high numbers.
    return m is not None and int(m.group(1)) >= 8


def _collect_insp_sitrep_urls_from_text(text: str) -> dict[int, str]:
    """Extract sitrep URLs keyed by sitrep number (highest wins per number)."""
    found: dict[int, str] = {}
    for m in _INSP_SITREP_PATH_RE.finditer(text):
        url = _normalize_insp_sitrep_url(m.group(1))
        if not url:
            continue
        slug = url[len(INSP_BASE_URL):].strip("/")
        if not _is_bdbv_insp_sitrep_slug(slug):
            continue
        num = _sitrep_num_from_slug(slug)
        if num is None:
            continue
        found[num] = url
    return found


def _fetch_insp_sitrep_urls_wp() -> dict[int, str]:
    """WordPress REST API: recent posts whose slug matches the Ebola sitrep series."""
    urls = (
        f"{INSP_BASE_URL}wp-json/wp/v2/posts"
        f"?search=SitRep&per_page=50&orderby=date&order=desc",
        f"{INSP_BASE_URL}wp-json/wp/v2/posts"
        f"?search=MVB&per_page=30&orderby=date&order=desc",
    )
    found: dict[int, str] = {}
    for api_url in urls:
        body = _insp_http_get(api_url)
        if not body:
            continue
        try:
            posts = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(posts, list):
            continue
        for post in posts:
            if not isinstance(post, dict):
                continue
            slug = str(post.get("slug") or "")
            link = post.get("link")
            if not _is_bdbv_insp_sitrep_slug(slug):
                continue
            num = _sitrep_num_from_slug(slug)
            if num is None:
                continue
            url = _normalize_insp_sitrep_url(str(link) if link else slug)
            if url:
                found[num] = url
    return found


def _fetch_insp_sitrep_urls_homepage() -> dict[int, str]:
    body = _insp_http_get(INSP_BASE_URL)
    if not body:
        return {}
    return _collect_insp_sitrep_urls_from_text(body)


def _pick_latest_sitrep_url(candidates: dict[int, str]) -> str | None:
    if not candidates:
        return None
    # Prefer MVB (current Bundibugyo naming); else highest sitrep number.
    for num in sorted(candidates, reverse=True):
        slug = candidates[num][len(INSP_BASE_URL):].strip("/").lower()
        if "-mvb_" in slug:
            return candidates[num]
    best_num = max(candidates)
    return candidates[best_num]


def fetch_latest_insp_sitrep_url() -> str | None:
    """Live INSP lookup: WordPress API, then homepage HTML scrape."""
    merged: dict[int, str] = {}
    for source, fetcher in (
        ("wp-json", _fetch_insp_sitrep_urls_wp),
        ("homepage", _fetch_insp_sitrep_urls_homepage),
    ):
        found = fetcher()
        if found:
            print(f"  INSP sitrep fetch ({source}): "
                  f"#{max(found)} among {len(found)} candidate(s)")
            merged.update(found)
    return _pick_latest_sitrep_url(merged)


def _latest_insp_url_from_local() -> str | None:
    """Offline fallbacks: optional pointer file, then raw PDF filenames."""
    if LATEST_SITREP_JSON.exists():
        try:
            url = json.loads(LATEST_SITREP_JSON.read_text()).get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
        except Exception:
            pass
    raw_dir = EXTERNAL_DATA / "insp_sitrep" / "raw"
    if raw_dir.exists():
        nums = []
        for p in raw_dir.glob("SitRep_MVE_*-*.pdf"):
            m = re.search(r"SitRep_MVE_(\d+)-(\d+)", p.stem)
            if m:
                nums.append((int(m.group(1)), int(m.group(2))))
        if nums:
            num, year = max(nums)
            return f"{INSP_BASE_URL}sitrep-mve-n-{num:03d}-{year}/"
    return None


def detect_asof() -> str:
    """Derive the 'latest case report' date.
    Checks local sit-rep CSVs first, then falls back to _date fields in the
    build GeoJSON."""
    if SIT_REPS_DIR.exists():
        dated = []
        for p in SIT_REPS_DIR.iterdir():
            if not p.is_file() or p.suffix.lower() != ".csv":
                continue
            d = _parse_csv_stem_date(p.stem)
            if d is not None:
                dated.append((d, p))
        if dated:
            d, _ = max(dated)
            return _format_asof(d)
    if BUILD_GEOJSON.exists():
        with open(BUILD_GEOJSON) as f:
            raw = json.load(f)
        dates = set()
        for feat in raw["features"]:
            insp = feat["properties"].get("insp_sitrep") or {}
            for v in insp.values():
                if isinstance(v, dict) and "_date" in v:
                    parsed = _parse_sitrep_date(v["_date"])
                    if parsed is not None:
                        dates.add(parsed)
        if dates:
            return _format_asof(max(dates))
    return ASOF_FALLBACK


def latest_insp_url() -> str:
    """Latest INSP sitrep permalink: live fetch, then local overrides, then INSP home."""
    if _insp_live_fetch_enabled():
        live = fetch_latest_insp_sitrep_url()
        if live:
            print(f"  insp sitrep URL (live): {live}")
            return live
        print("  WARNING: live INSP sitrep fetch found no URL; using local fallbacks")
    else:
        print("  NOTE: INSP live sitrep fetch disabled (INSP_SITREP_FETCH=0)")
    local = _latest_insp_url_from_local()
    if local:
        print(f"  insp sitrep URL (local): {local}")
        return local
    return INSP_FALLBACK_URL


_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm(s) -> str:
    return _NORM_RE.sub("", str(s).lower()) if s else ""


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(v) else v


def _i(x):
    v = _f(x)
    return None if v is None else int(round(v))


def _round_coords(geom_dict: dict, ndigits: int) -> dict:
    def _walk(o):
        if isinstance(o, (list, tuple)):
            if o and isinstance(o[0], (int, float)):
                return [round(float(c), ndigits) for c in o]
            return [_walk(x) for x in o]
        return o

    g = dict(geom_dict)
    g["coordinates"] = _walk(g.get("coordinates"))
    return g


# ---------------------------------------------------------------------------
# geometry: read DRC health-zone polygons, match per-zone metadata rows
# ---------------------------------------------------------------------------

def load_features_from_geojson() -> tuple[list[dict], dict[str, tuple[float, float]]]:
    """Load zone polygons from the build GeoJSON, keyed by nom."""
    with open(BUILD_GEOJSON) as f:
        raw = json.load(f)

    feats: list[dict] = []
    centroids: dict[str, tuple[float, float]] = {}
    for feat in raw["features"]:
        nom = feat["properties"]["nom"]
        geom = make_valid(shape(feat["geometry"]))
        if geom.is_empty or geom.geom_type not in {"Polygon", "MultiPolygon"}:
            continue
        orig_centroid = geom.centroid
        if SIMPLIFY_TOL > 0:
            geom = geom.simplify(SIMPLIFY_TOL, preserve_topology=True)
        if geom.is_empty:
            continue
        gdict = mapping(geom)
        if COORD_DECIMALS is not None:
            gdict = _round_coords(gdict, COORD_DECIMALS)
        province = feat["properties"].get("province")
        props = {"nom": nom, "name": _NOM_TO_NAME.get(nom, nom)}
        if province:
            props["province"] = province
        feats.append({
            "type": "Feature",
            "geometry": gdict,
            "properties": props,
        })
        centroids[nom] = (float(orig_centroid.x), float(orig_centroid.y))
    return feats, centroids


def build_province_boundaries() -> dict:
    """Union health-zone polygons into one outline per province."""
    if not BUILD_GEOJSON.exists():
        return {"type": "FeatureCollection", "features": []}

    with open(BUILD_GEOJSON) as f:
        raw = json.load(f)

    by_province: dict[str, list] = {}
    for feat in raw.get("features") or []:
        prov = (feat.get("properties") or {}).get("province")
        if not prov:
            continue
        geom = make_valid(shape(feat["geometry"]))
        if geom.is_empty or geom.geom_type not in {"Polygon", "MultiPolygon"}:
            continue
        by_province.setdefault(prov, []).append(geom)

    out: list[dict] = []
    for prov in sorted(by_province):
        merged = unary_union(by_province[prov])
        if merged.is_empty:
            continue
        if SIMPLIFY_TOL > 0:
            merged = merged.simplify(SIMPLIFY_TOL, preserve_topology=True)
        if merged.is_empty:
            continue
        gdict = mapping(merged)
        if COORD_DECIMALS is not None:
            gdict = _round_coords(gdict, COORD_DECIMALS)
        out.append({
            "type": "Feature",
            "geometry": gdict,
            "properties": {"province": prov},
        })
    return {"type": "FeatureCollection", "features": out}


def _load_build_geojson_properties() -> dict[str, dict]:
    """Return {nom: properties_dict} from the build GeoJSON."""
    with open(BUILD_GEOJSON) as f:
        raw = json.load(f)
    return {feat["properties"]["nom"]: feat["properties"]
            for feat in raw["features"]}


# Tracker / sitrep field name → insp_sitrep block key in drc_health_zones.geojson.
_NATIONAL_INSP_KEYS = (
    ("confirmed_cases", "national_cumulative_confirmed_cases"),
    ("suspected_cases", "national_cumulative_suspected_cases"),
    ("confirmed_deaths", "national_cumulative_confirmed_deaths"),
    ("suspected_deaths", "national_cumulative_suspected_deaths"),
    ("recovered_cases", "national_cumulative_recovered_cases"),
)


def _national_totals_from_build_geojson() -> dict | None:
    """DRC national INSP totals from the build GeoJSON (same shape as sitrep dict)."""
    # Abort if the build artefact path is missing (no national figures available).
    if not BUILD_GEOJSON.exists():
        return None
    # Open the zone polygon file that also carries insp_sitrep properties.
    with open(BUILD_GEOJSON) as f:
        raw = json.load(f)
    # Pull the Feature array; an empty file cannot supply totals.
    features = raw.get("features") or []
    if not features:
        return None
    # National metrics are copied onto every zone; any one feature is sufficient.
    props = features[0].get("properties") or {}
    # INSP sitrep blocks (zone + national) live under this nested dict.
    insp = props.get("insp_sitrep") or {}
    if not isinstance(insp, dict):
        return None
    # Will hold snake_case keys used by the tracker (confirmed_cases, etc.).
    metrics: dict[str, int | None] = {}
    for dst, insp_key in _NATIONAL_INSP_KEYS:
        # Each national metric is a small dict: {metric_name: value, _date: ...}.
        block = insp.get(insp_key)
        if not isinstance(block, dict):
            metrics[dst] = None
            continue
        # Inner key repeats the block name (same pattern as zone cumulative_*).
        metrics[dst] = _i(block.get(insp_key))
    # If every national field is missing, do not pretend we have a sitrep.
    if not any(v is not None for v in metrics.values()):
        return None
    # Coerce None → 0 for arithmetic and JSON output (tracker expects integers).
    conf = int(metrics.get("confirmed_cases") or 0)
    susp = int(metrics.get("suspected_cases") or 0)
    conf_d = int(metrics.get("confirmed_deaths") or 0)
    susp_d = int(metrics.get("suspected_deaths") or 0)
    rec = int(metrics.get("recovered_cases") or 0)
    # Single-country row: national_* in GeoJSON are DRC-only aggregates.
    per_country = [{
        "country": "DRC",
        "confirmed_cases": conf,
        "suspected_cases": susp,
        "confirmed_deaths": conf_d,
        "suspected_deaths": susp_d,
        "recovered_cases": rec,
        "total": conf + susp,
    }]
    # Match compute_global_sitrep_totals() so build_payload can merge blindly.
    return {
        "global_confirmed_cases": conf,
        "global_suspected_cases": susp,
        "global_confirmed_deaths": conf_d,
        "global_suspected_deaths": susp_d,
        "global_recovered_cases": rec,
        "global_total_cases": conf,
        "affected_countries": ["DRC"],
        "affected_country_count": 1,
        "per_country": per_country,
    }


# ---------------------------------------------------------------------------
# Tracker caveats (optional CSV beside national totals in the title panel)
# ---------------------------------------------------------------------------

_TRACKER_CAVEAT_METRIC_ALIASES = {
    "confirmed_cases": (
        "confirmed_cases", "confirmed cases", "confirmed", "conf", "conf_cases",
    ),
    "suspected_cases": (
        "suspected_cases", "suspected cases", "suspected", "susp", "susp_cases",
    ),
    "confirmed_deaths": (
        "confirmed_deaths", "confirmed deaths", "conf_deaths", "conf deaths",
    ),
    "suspected_deaths": (
        "suspected_deaths", "suspected deaths", "susp_deaths", "susp deaths",
    ),
}

_TRACKER_CAVEAT_MARKS = ("*", "†", "‡", "§")

_TRACKER_CAVEAT_WARNING_COLS = (
    "warning", "warnings", "caveat", "caveats", "message", "text", "note",
)


def _normalize_tracker_caveat_metric(raw: str) -> str | None:
    key = re.sub(r"[\s\-]+", "_", str(raw).strip().lower())
    for canonical, aliases in _TRACKER_CAVEAT_METRIC_ALIASES.items():
        if key in aliases:
            return canonical
    return None


def load_tracker_caveats(lang: str = "en") -> list[dict]:
    """Load tracker footnotes from Data/caveats.csv.

    Each row adds an asterisk (or †, ‡, § for further rows) beside the matching
    national metric in the per-country tracker line and a footnote below.

    Expected CSV::

        metric,warning[,warning_fr]
        suspected_cases,National suspected counts include contacts under surveillance.

    ``metric`` must resolve to one of: confirmed_cases, suspected_cases,
    confirmed_deaths, suspected_deaths (aliases like ``susp`` are accepted).
    """
    if not CAVEATS_CSV.exists():
        return []
    df = pd.read_csv(CAVEATS_CSV)
    if df.empty:
        print(f"  WARNING: {CAVEATS_CSV.name} is empty")
        return []
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "metric" not in df.columns:
        print(f"  WARNING: {CAVEATS_CSV.name} needs a 'metric' column")
        return []
    warn_col = next((c for c in _TRACKER_CAVEAT_WARNING_COLS if c in df.columns), None)
    if warn_col is None:
        print(f"  WARNING: {CAVEATS_CSV.name} needs a warning column "
              f"(e.g. warning, message, caveat)")
        return []
    fr_col = "warning_fr" if "warning_fr" in df.columns else None
    out: list[dict] = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        metric = _normalize_tracker_caveat_metric(row["metric"])
        if metric is None:
            print(f"  WARNING: unknown tracker caveat metric {row['metric']!r}")
            continue
        if metric in seen:
            print(f"  WARNING: duplicate caveat for {metric}; keeping first row")
            continue
        warning = ""
        if lang == "fr" and fr_col:
            warning = str(row[fr_col]).strip()
        if not warning or warning.lower() in ("nan", "none"):
            warning = str(row[warn_col]).strip()
        if not warning or warning.lower() in ("nan", "none"):
            continue
        mark = _TRACKER_CAVEAT_MARKS[len(out)] if len(out) < len(_TRACKER_CAVEAT_MARKS) else "*"
        out.append({"metric": metric, "mark": mark, "warning": warning})
        seen.add(metric)
    if out and lang == "en":
        print(f"  tracker caveats: {[c['metric'] for c in out]}")
    return out


# ---------------------------------------------------------------------------
# Imperial College model estimates (separate from INSP sitreps)
# ---------------------------------------------------------------------------

_IC_MODEL_DEFAULTS = {
    "ic_model_date": None,
    "ic_model_lowerbound": None,
    "ic_model_upperbound": None,
}

_IC_MODEL_COL_ALIASES = {
    "ic_model_date": ("ic_model_date", "date", "as_of", "asof"),
    "ic_model_lowerbound": (
        "ic_model_lowerbound", "lowerbound", "lower_bound", "lower"),
    "ic_model_upperbound": (
        "ic_model_upperbound", "upperbound", "upper_bound", "upper"),
}


def _resolve_ic_model_column(df: pd.DataFrame, field: str) -> str | None:
    """Return the actual CSV column name for a payload field, if present."""
    for alias in _IC_MODEL_COL_ALIASES[field]:
        if alias in df.columns:
            return alias
    return None


def _parse_ic_model_scalar(value) -> str | int | float | None:
    """Normalize one CSV cell for JSON payload (None → NA in the dashboard)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    # Prefer integers for bounds when whole numbers.
    num = pd.to_numeric(value, errors="coerce")
    if pd.notna(num):
        rounded = float(num)
        if rounded == int(rounded):
            return int(rounded)
        return rounded
    return str(value).strip()


def load_ic_model_estimates(country: str = "DRC") -> dict:
    """Load Imperial College bounds from Data/ic_model_estimates.csv.

    Not tied to sit-rep CSVs or GeoJSON. Exposed as PAYLOAD.ic_model with keys
    ic_model_date, ic_model_lowerbound, ic_model_upperbound (null if missing).

    Expected CSV (column names flexible via aliases):
        country,ic_model_date,ic_model_lowerbound,ic_model_upperbound
        DRC,2026-05-26,500,1200

    If ``country`` is omitted, the first data row is used.
    """
    out = dict(_IC_MODEL_DEFAULTS)
    if not IC_MODEL_CSV.exists():
        print(f"  NOTE: {IC_MODEL_CSV.name} not found; ic_model defaults to NA in UI")
        return out
    df = pd.read_csv(IC_MODEL_CSV)
    if df.empty:
        print(f"  WARNING: {IC_MODEL_CSV.name} is empty")
        return out
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    work = df
    if "country" in df.columns:
        mask = df["country"].astype(str).str.strip().str.upper() == country.upper()
        if mask.any():
            work = df[mask]
        else:
            print(f"  WARNING: no row for country={country!r} in {IC_MODEL_CSV.name}")
    row = work.iloc[0]
    for field in _IC_MODEL_DEFAULTS:
        col = _resolve_ic_model_column(df, field)
        if col is None:
            continue
        parsed = _parse_ic_model_scalar(row[col])
        if field == "ic_model_date" and parsed is not None:
            # Pretty-print ISO dates for the tooltip; leave other strings as-is.
            try:
                d = datetime.strptime(str(parsed)[:10], "%Y-%m-%d").date()
                parsed = d.strftime("%d %b %Y").lstrip("0")
            except ValueError:
                parsed = str(parsed)
        out[field] = parsed
    print(f"  ic_model: date={out['ic_model_date']!r}, "
          f"bounds={out['ic_model_lowerbound']!r}–{out['ic_model_upperbound']!r}")
    return out


def _slugify_plot_key(text: str) -> str:
    """Normalize labels for matching plot filenames (e.g. Kasaï → kasai)."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def _read_plot_svg(path: Path) -> str | None:
    if not path.exists():
        return None
    svg = path.read_text(encoding="utf-8").strip()
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[-1].strip()
    return svg or None


def _svg_plot_title(svg: str, fallback: str) -> str:
    match = re.search(
        r">\s*(Daily Cases by Symptom Onset[^<]*?)\s*<",
        svg,
        flags=re.I,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    match = re.search(
        r">\s*(5-day Rolling Test Positivity[^<]*?)\s*<",
        svg,
        flags=re.I,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    return fallback


def _load_lab_name_map() -> dict[str, str]:
    """Map lab plot keys / codes to display labels."""
    path = DASHBOARD_PLOTS_DIR / "lab_name_map.csv"
    out: dict[str, str] = {}
    if not path.exists():
        return out
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        print(f"  WARNING: could not read {path.name}: {exc}")
        return out
    if df.shape[1] < 2:
        return out
    key_col, val_col = df.columns[0], df.columns[1]
    for _, row in df.iterrows():
        key = str(row.get(key_col) or "").strip()
        val = str(row.get(val_col) or "").strip()
        if not key or not val:
            continue
        out[_slugify_plot_key(key)] = val
        out[_slugify_plot_key(key.replace(" ", ""))] = val
        out[key.upper()] = val
    return out


def _lab_label_from_stem(stem: str, name_map: dict[str, str]) -> str:
    raw = stem[4:] if stem.lower().startswith("lab_") else stem
    slug = _slugify_plot_key(raw)
    if slug in name_map:
        return name_map[slug]
    compact = slug.replace("-", "")
    if compact in name_map:
        return name_map[compact]
    upper = raw.upper().replace("_", "-")
    if upper in name_map:
        return name_map[upper]
    # Fall back to the plot-name token (e.g. inrbk → INRBK).
    return re.sub(r"[-_]+", "-", raw).upper()


# Pre-built onset / lab plots for the Epidemiological trends panel.
def load_dashboard_plots(
    zone_noms: list[str] | None = None,
    provinces: list[str] | None = None,
) -> dict | None:
    """Load national, province, health-zone, and lab SVG plots.

    Supports the Processed_Sensitive_Data layout::

        dashboard_plots/
          daily_onset_<province>.svg
          national/daily_onset_national.svg
          healthzone/daily_onset_<zone>.svg
          lab/lab_<code>.svg
          lab_name_map.csv   (optional)
          manifest.json      (optional; series metadata)
    """
    if not DASHBOARD_PLOTS_DIR.exists():
        print(f"  NOTE: {DASHBOARD_PLOTS_DIR} not found; trends plots unavailable")
        return None

    manifest: dict = {}
    manifest_path = DASHBOARD_PLOTS_DIR / "manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  WARNING: invalid {manifest_path.name}: {exc}")

    zone_noms = list(zone_noms or [])
    provinces = list(provinces or [])
    nom_by_slug = {_slugify_plot_key(n): n for n in zone_noms if n}
    province_by_slug = {_slugify_plot_key(p): p for p in provinces if p}

    national = None
    national_path = DASHBOARD_PLOTS_DIR / "national" / "daily_onset_national.svg"
    if not national_path.exists():
        national_path = DASHBOARD_PLOTS_DIR / "daily_onset_national.svg"
    nat_svg = _read_plot_svg(national_path)
    if nat_svg:
        national = {
            "id": "national",
            "label": "National",
            "file": str(national_path.relative_to(DASHBOARD_PLOTS_DIR)),
            "title": _svg_plot_title(nat_svg, "Daily Cases by Symptom Onset - National"),
            "caption": "",
            "svg": nat_svg,
        }

    province_plots: dict[str, dict] = {}
    for svg_path in sorted(DASHBOARD_PLOTS_DIR.glob("daily_onset_*.svg")):
        stem = svg_path.stem  # daily_onset_ituri
        slug = stem.removeprefix("daily_onset_")
        if slug == "national":
            continue
        svg = _read_plot_svg(svg_path)
        if not svg:
            continue
        label = province_by_slug.get(slug) or slug.replace("-", " ").title()
        province_plots[label] = {
            "id": label,
            "label": label,
            "slug": slug,
            "file": svg_path.name,
            "title": _svg_plot_title(svg, f"Daily Cases by Symptom Onset - {label}"),
            "caption": "",
            "svg": svg,
        }

    # Legacy manifest province entries (fill gaps only).
    for province, meta in (manifest.get("plots") or {}).items():
        if not isinstance(meta, dict) or province in province_plots:
            continue
        filename = meta.get("file")
        if not filename:
            continue
        svg_path = DASHBOARD_PLOTS_DIR / filename
        svg = _read_plot_svg(svg_path)
        if not svg:
            continue
        province_plots[province] = {
            "id": province,
            "label": province,
            "slug": _slugify_plot_key(province),
            "file": filename,
            "title": meta.get("title") or f"Daily onset — {province}",
            "caption": meta.get("caption") or "",
            "svg": svg,
        }

    hz_plots: dict[str, dict] = {}
    hz_dir = DASHBOARD_PLOTS_DIR / "healthzone"
    if hz_dir.exists():
        for svg_path in sorted(hz_dir.glob("daily_onset_*.svg")):
            slug = svg_path.stem.removeprefix("daily_onset_")
            svg = _read_plot_svg(svg_path)
            if not svg:
                continue
            nom = nom_by_slug.get(slug) or slug.replace("-", " ").title()
            hz_plots[nom] = {
                "id": nom,
                "label": nom,
                "slug": slug,
                "file": f"healthzone/{svg_path.name}",
                "title": _svg_plot_title(svg, f"Daily Cases by Symptom Onset - {nom}"),
                "caption": "",
                "svg": svg,
            }

    lab_name_map = _load_lab_name_map()
    labs: list[dict] = []
    lab_dir = DASHBOARD_PLOTS_DIR / "lab"
    if lab_dir.exists():
        for svg_path in sorted(lab_dir.glob("lab_*.svg")):
            svg = _read_plot_svg(svg_path)
            if not svg:
                continue
            lab_id = svg_path.stem  # lab_inrbk
            label = _lab_label_from_stem(lab_id, lab_name_map)
            labs.append({
                "id": lab_id,
                "label": label,
                "slug": _slugify_plot_key(lab_id.removeprefix("lab_")),
                "file": f"lab/{svg_path.name}",
                "title": _svg_plot_title(svg, f"Lab positivity — {label}"),
                "caption": "",
                "svg": svg,
            })
        labs.sort(key=lambda x: str(x["label"]).lower())

    if not national and not province_plots and not hz_plots and not labs:
        print(f"  WARNING: no loadable plots under {DASHBOARD_PLOTS_DIR.name}/")
        return None

    print(
        "  dashboard plots: "
        + f"national={'yes' if national else 'no'}"
        + f", {len(province_plots)} province(s)"
        + f", {len(hz_plots)} health zone(s)"
        + f", {len(labs)} lab(s)"
        + f" from {DASHBOARD_PLOTS_DIR.name}/"
    )
    return {
        "series": manifest.get("series") or [],
        "incomplete_styling": manifest.get("incomplete_styling") or {},
        "national": national,
        "provinces": province_plots,
        # Backward-compatible alias used by older panel code.
        "plots": province_plots,
        "health_zones": hz_plots,
        "labs": labs,
    }


def _parse_optional_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return float(value)
    text = str(value).strip()
    if not text or text.upper() in {"NA", "NAN", "NULL", "NONE", "."}:
        return None
    try:
        out = float(text)
    except ValueError:
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def _parse_optional_int(value) -> int | None:
    num = _parse_optional_float(value)
    if num is None:
        return None
    return int(round(num))


def _parse_boolish(value) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().upper()
    return text in {"TRUE", "T", "1", "YES", "Y"}


def _parse_flexible_date(value):
    """Parse cutoff dates from CSV (DD/MM/YYYY, YYYY-MM-DD, etc.)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if hasattr(value, "date") and callable(getattr(value, "date", None)):
        try:
            return value.date() if hasattr(value, "hour") else value
        except Exception:
            pass
    text = str(value).strip()
    if not text or text.upper() in {"NA", "NAN", "NULL", "NONE", "."}:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text[:32], fmt).date()
        except ValueError:
            continue
    try:
        parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
        if pd.notna(parsed):
            return parsed.date()
    except Exception:
        pass
    return None


def load_invasion_risk_estimates() -> dict | None:
    """Load Bayesian invasion-risk scores for the Epidemiological trends tab.

    Prefers ``horizon == 1`` (next forecast window). Zone names are expected to
    match GeoJSON ``nom`` values.
    """
    if not INVASION_RISK_CSV.exists():
        print(
            f"  NOTE: {INVASION_RISK_CSV.name} not found; "
            "Epidemiological trends tab unavailable"
        )
        return None

    df = pd.read_csv(INVASION_RISK_CSV)
    if df.empty:
        print(f"  WARNING: {INVASION_RISK_CSV.name} is empty")
        return None
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if "health_zone" not in df.columns:
        print(f"  WARNING: {INVASION_RISK_CSV.name} missing health_zone column")
        return None

    # Keep a full-file snapshot for CSV download (all horizons / columns).
    download_csv = df.to_csv(index=False)

    horizon_used = None
    if "horizon" in df.columns:
        as_str = df["horizon"].astype(str).str.strip()
        for candidate in ("1", "2"):
            subset = df[as_str == candidate]
            if not subset.empty:
                df = subset
                horizon_used = int(candidate)
                break

    cutoff_dates = []
    if "cutoff_date" in df.columns:
        for raw in df["cutoff_date"].tolist():
            parsed = _parse_flexible_date(raw)
            if parsed is not None:
                cutoff_dates.append(parsed)
    cutoff_date = max(cutoff_dates) if cutoff_dates else None

    horizon_windows = []
    window_col = next(
        (c for c in ("forecasting_window", "horizon_window") if c in df.columns),
        None,
    )
    if window_col is not None:
        for raw in df[window_col].tolist():
            hw = _parse_optional_float(raw)
            if hw is not None:
                horizon_windows.append(hw)
    elif horizon_used is not None:
        horizon_windows.append(float(horizon_used))
    horizon_window = None
    if horizon_windows:
        # Prefer the modal / first unique value for the filtered horizon slice.
        uniq = sorted({int(round(x)) for x in horizon_windows})
        horizon_window = uniq[0]

    forecast_end_date = None
    if cutoff_date is not None and horizon_window is not None:
        forecast_end_date = cutoff_date + timedelta(weeks=int(horizon_window))

    zones: dict[str, dict] = {}
    for _, row in df.iterrows():
        nom = str(row.get("health_zone") or "").strip()
        if not nom:
            continue
        zones[nom] = {
            "health_zone": nom,
            "province": str(row.get("province") or "").strip(),
            "was_active_before": _parse_boolish(row.get("was_active_before")),
            "p_case_invasion": _parse_optional_float(row.get("p_case_invasion")),
            "p_case_lo": _parse_optional_float(row.get("p_case_lo")),
            "p_case_hi": _parse_optional_float(
                row["p_case_hi"] if "p_case_hi" in df.columns else row.get("p_case_high")
            ),
            "rr_nat": _parse_optional_float(row.get("rr_nat")),
            "rr_nat_rank": _parse_optional_int(row.get("rr_nat_rank")),
            "rr_ituri": _parse_optional_float(row.get("rr_ituri")),
            "rr_ituri_rank": _parse_optional_int(row.get("rr_ituri_rank")),
            "rr_nordkivu": _parse_optional_float(row.get("rr_nordkivu")),
            "rr_nordkivu_rank": _parse_optional_int(row.get("rr_nordkivu_rank")),
            "rr_hautuele": _parse_optional_float(row.get("rr_hautuele")),
            "rr_hautuele_rank": _parse_optional_int(row.get("rr_hautuele_rank")),
            "priority": _parse_optional_float(row.get("priority")),
            "priority_rank": _parse_optional_int(row.get("priority_rank")),
            "surveillance_gap": _parse_optional_float(row.get("surveillance_gap")),
            "access_gap": _parse_optional_float(row.get("access_gap")),
            "social_vulnerability": _parse_optional_float(
                row.get("social_vulnerability")
            ),
            "method": str(row.get("method") or "").strip(),
        }

    methods = sorted({z["method"] for z in zones.values() if z.get("method")})
    method_note = methods[0] if len(methods) == 1 else "; ".join(methods)
    print(
        f"  invasion risk: {len(zones)} zones"
        + (f" (horizon={horizon_used})" if horizon_used is not None else "")
        + (f", cutoff={cutoff_date.isoformat()}" if cutoff_date else "")
        + (f", horizon_window={horizon_window}w" if horizon_window is not None else "")
        + (f", method={method_note!r}" if method_note else "")
    )
    return {
        "horizon": horizon_used,
        "horizon_window": horizon_window,
        "forecasting_window": horizon_window,
        "cutoff_date": cutoff_date.isoformat() if cutoff_date else None,
        "forecast_end_date": (
            forecast_end_date.isoformat() if forecast_end_date else None
        ),
        "method": method_note,
        "method_label": "Mobility-epidemiological model of risk",
        "method_url": (
            "https://www.epidemiological.org/t/"
            "real-time-spatiotemporal-risk-modelling-of-the-bundibugyo-ebola-virus-outbreak-2026/16"
        ),
        "download_csv": download_csv,
        "p_case_invasion_label": (
            "Probability of invasion (defined as the probability of observing "
            "one new case within the next forecast window)"
        ),
        "scopes": [
            {"id": "national", "label": "National", "rr": "rr_nat", "rank": "rr_nat_rank", "province": None},
            {"id": "ituri", "label": "Ituri", "rr": "rr_ituri", "rank": "rr_ituri_rank", "province": "Ituri"},
            {"id": "nordkivu", "label": "Nord-Kivu", "rr": "rr_nordkivu", "rank": "rr_nordkivu_rank", "province": "Nord-Kivu"},
            {"id": "hautuele", "label": "Haut-Uele", "rr": "rr_hautuele", "rank": "rr_hautuele_rank", "province": "Haut-Uele"},
        ],
        "zones": zones,
    }


# ---------------------------------------------------------------------------
# INSP cumulative confirmed time series (Trends tab map slider)
# ---------------------------------------------------------------------------

_CONFIRMED_TS_LONG = (
    BUILD_LONG_DIR / "insp_sitrep__cumulative_confirmed_cases.csv"
)
_CONFIRMED_TS_PROCESSED = (
    EXTERNAL_DATA / "insp_sitrep" / "processed"
    / "insp_sitrep__cumulative_confirmed_cases__daily.csv"
)
_CONFIRMED_TS_SKIP_NOMS = frozenset({"DRC", "NA", "Sans Fiche", ""})


def _read_insp_cumulative_confirmed_df() -> pd.DataFrame | None:
    """Load long-format INSP cumulative confirmed cases (build/long or processed)."""
    for path in (_CONFIRMED_TS_LONG, _CONFIRMED_TS_PROCESSED):
        if not path.exists():
            continue
        df = pd.read_csv(path)
        lower = {str(c).strip().lower(): c for c in df.columns}
        if "nom" in lower and "date" in lower:
            nom_col = lower["nom"]
            date_col = lower["date"]
            val_col = next(
                (lower[k] for k in lower if k not in ("nom", "date")),
                None,
            )
            if val_col is None:
                continue
        else:
            df = pd.read_csv(path, header=None, names=["nom", "date", "value"])
            nom_col, date_col, val_col = "nom", "date", "value"
        out = df[[nom_col, date_col, val_col]].copy()
        out.columns = ["nom", "date", "value"]
        return out
    return None


def _parse_confirmed_count(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s or s.upper() in ("NA", "ND", "NAN", "NONE"):
        return None
    num = pd.to_numeric(s, errors="coerce")
    if pd.isna(num):
        return None
    return int(round(float(num)))


def load_confirmed_cases_timeseries(valid_noms: set[str]) -> dict | None:
    """Build carry-forward cumulative confirmed series for the Trends tab slider.

    Untracked zones (no row before a date) are 0. Tracked zones carry forward
    the last known cumulative count when a sitrep date has no update (or ND).
    """
    df = _read_insp_cumulative_confirmed_df()
    if df is None or df.empty:
        print("  NOTE: INSP cumulative confirmed time series not found; "
              "Trends map slider unavailable")
        return None

    df = df.copy()
    df["nom"] = df["nom"].astype(str).str.strip()
    df["nom"] = df["nom"].map(lambda n: _NAME_TO_NOM.get(n, n))
    df = df[~df["nom"].isin(_CONFIRMED_TS_SKIP_NOMS)]
    df = df[df["nom"].isin(valid_noms)]

    parsed_dates: list[tuple[date, str]] = []
    for raw in df["date"].astype(str).str.strip().unique():
        d = _parse_sitrep_date(raw)
        if d is not None:
            parsed_dates.append((d, raw))
    if not parsed_dates:
        print("  WARNING: no parseable dates in cumulative confirmed series")
        return None

    parsed_dates.sort(key=lambda x: x[0])
    iso_dates = [d.isoformat() for d, _ in parsed_dates]
    raw_by_iso = {d.isoformat(): raw for d, raw in parsed_dates}

    by_nom_date: dict[str, dict[str, int]] = {}
    for _, row in df.iterrows():
        d = _parse_sitrep_date(row["date"])
        if d is None:
            continue
        v = _parse_confirmed_count(row["value"])
        if v is None:
            continue
        by_nom_date.setdefault(row["nom"], {})[d.isoformat()] = v

    by_nom: dict[str, list[int]] = {}
    max_confirmed = 0
    min_positive: int | None = None
    for nom, date_vals in sorted(by_nom_date.items()):
        series: list[int] = []
        last: int | None = None
        for iso in iso_dates:
            if iso in date_vals:
                last = date_vals[iso]
            if last is None:
                series.append(0)
            else:
                series.append(last)
                max_confirmed = max(max_confirmed, last)
                if last > 0:
                    min_positive = (
                        last if min_positive is None else min(min_positive, last)
                    )
        by_nom[nom] = series

    if not by_nom:
        print("  WARNING: cumulative confirmed series has no zone-level rows")
        return None

    print(f"  confirmed time series: {len(iso_dates)} date(s), "
          f"{len(by_nom)} zone(s), max={max_confirmed}")
    return {
        "dates": iso_dates,
        "date_labels": {iso: raw_by_iso[iso] for iso in iso_dates},
        "by_nom": by_nom,
        "max_confirmed": max_confirmed,
        "min_positive": min_positive or 1,
    }


# ---------------------------------------------------------------------------
# Public health response context (INSP SitRep pillars → Context tab)
# ---------------------------------------------------------------------------

_PHR_DATASET = "public_health_response"
_PHR_NON_TEXT = {"ND", "NA", ""}

_PHR_ZONE_METRICS = (
    "epidemiological_coordination",
    "epidemiological_monitoring",
    "epidemiological_management",
    "epidemiological_laboratory",
    "epidemiological_infection_prevention_controle",
    "epidemiological_logistics",
    "epidemiological_security",
    "epidemiological_community_engagement",
    "epidemiological_protection_sexual_exploitation_abuse",
)

_PHR_METRIC_LABELS: dict[str, str] = {
    "epidemiological_coordination": "Coordination",
    "epidemiological_monitoring": "Surveillance & monitoring",
    "epidemiological_management": "Case management",
    "epidemiological_laboratory": "Laboratory",
    "epidemiological_infection_prevention_controle": "Infection prevention & control",
    "epidemiological_logistics": "Logistics",
    "epidemiological_security": "Security",
    "epidemiological_community_engagement": "Community engagement",
    "epidemiological_protection_sexual_exploitation_abuse": (
        "Protection from sexual exploitation & abuse"
    ),
}


def _phr_metric_label(metric: str) -> str:
    key = metric.removeprefix("national_").removeprefix("provincial_")
    return _PHR_METRIC_LABELS.get(key, _prettify_label(key))


def _phr_category(metric: str) -> str:
    """Stable pillar slug for CSS category styling (strip roll-up prefixes)."""
    return metric.removeprefix("national_").removeprefix("provincial_")


def _phr_scope_tag(scope: str, province: str | None = None) -> str:
    if scope == "national":
        return "NATIONAL"
    if scope == "provincial" and province:
        return province.upper()
    return scope.upper()


def _parse_phr_date(value) -> datetime.date | None:
    """Parse PHR ``_date`` values (ISO, slash forms, and INSP ``DD-MM-YYYY``)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if len(s) >= 10 and s[2:3] == "-" and s[5:6] == "-":
        try:
            return datetime.strptime(s[:10], "%d-%m-%Y").date()
        except ValueError:
            pass
    return _parse_sitrep_date(s)


def _sort_phr_pillars(pillars: list[dict]) -> list[dict]:
    """Newest ``date`` first; pillar label breaks ties. Ignores pillar metric order."""
    return sorted(
        pillars,
        key=lambda p: (
            _parse_phr_date(p.get("date")) or date.min,
            p.get("label") or "",
        ),
        reverse=True,
    )


def _extract_phr_block(block: object) -> tuple[str | None, str | None]:
    """Return (narrative text, date string) from one GeoJSON metric object."""
    if not isinstance(block, dict):
        return None, None
    date_raw = block.get("_date")
    date = str(date_raw).strip() if date_raw not in (None, "") else None
    text = None
    for key, val in block.items():
        if key == "_date":
            continue
        if val is None:
            continue
        s = str(val).strip()
        if s and s not in _PHR_NON_TEXT:
            text = s
            break
    return text, date


def _phr_metric_candidates(base_metric: str, scope: str, lang: str) -> list[str]:
    """GeoJSON metric keys to try: bilingual ``_{lang}`` first, then legacy unsuffixed."""
    if scope == "national":
        return [f"national_{base_metric}_{lang}", f"national_{base_metric}"]
    if scope == "provincial":
        return [f"provincial_{base_metric}_{lang}", f"provincial_{base_metric}"]
    return [f"{base_metric}_{lang}", base_metric]


def _phr_extract_from_phr(phr: dict, base_metric: str, scope: str, lang: str) -> tuple[str | None, str | None]:
    for metric in _phr_metric_candidates(base_metric, scope, lang):
        text, date = _extract_phr_block(phr.get(metric))
        if text:
            return text, date
    return None, None


def _load_public_health_context_for_lang(
    props_by_nom: dict[str, dict],
    sample_phr: dict,
    lang: str,
) -> dict:
    rollups: list[dict] = []
    for base_metric in _PHR_ZONE_METRICS:
        text, date = _phr_extract_from_phr(sample_phr, base_metric, "national", lang)
        if not text:
            continue
        parsed = _parse_phr_date(date)
        rollups.append({
            "metric": base_metric,
            "category": _phr_category(base_metric),
            "label": _phr_metric_label(base_metric),
            "text": text,
            "date": date,
            "date_iso": parsed.isoformat() if parsed else None,
            "scope": "national",
            "scope_tag": _phr_scope_tag("national"),
        })

    seen_provincial: set[tuple[str, str]] = set()
    for nom in sorted(props_by_nom):
        props = props_by_nom[nom]
        province = props.get("province")
        if not province:
            continue
        phr = props.get(_PHR_DATASET) or {}
        if not isinstance(phr, dict):
            continue
        for base_metric in _PHR_ZONE_METRICS:
            key = (province, base_metric)
            if key in seen_provincial:
                continue
            text, date = _phr_extract_from_phr(phr, base_metric, "provincial", lang)
            if not text:
                continue
            seen_provincial.add(key)
            parsed = _parse_phr_date(date)
            rollups.append({
                "metric": base_metric,
                "category": _phr_category(base_metric),
                "label": _phr_metric_label(base_metric),
                "text": text,
                "date": date,
                "date_iso": parsed.isoformat() if parsed else None,
                "scope": "provincial",
                "scope_tag": _phr_scope_tag("provincial", province),
                "province": province,
            })

    rollups = _sort_phr_pillars(rollups)

    by_nom: dict[str, list[dict]] = {}
    for nom, props in props_by_nom.items():
        phr = props.get(_PHR_DATASET) or {}
        if not isinstance(phr, dict):
            continue
        pillars: list[dict] = []
        for base_metric in _PHR_ZONE_METRICS:
            text, date = _phr_extract_from_phr(phr, base_metric, "zone", lang)
            if not text:
                continue
            parsed = _parse_phr_date(date)
            pillars.append({
                "metric": base_metric,
                "category": _phr_category(base_metric),
                "label": _phr_metric_label(base_metric),
                "text": text,
                "date": date,
                "date_iso": parsed.isoformat() if parsed else None,
                "scope": "zone",
            })
        if pillars:
            by_nom[nom] = _sort_phr_pillars(pillars)

    return {"national": rollups, "by_nom": by_nom}


def load_public_health_context() -> dict[str, dict]:
    """Extract INSP pillar narratives from the build GeoJSON for the Context tab.

    Returns per-language payloads keyed by ``en`` / ``fr``. GeoJSON metrics use
    bilingual keys (e.g. ``epidemiological_coordination_en``); legacy unsuffixed
    keys are still accepted as a fallback.
    """
    empty = {lang: {"national": [], "by_nom": {}} for lang in SUPPORTED_LANGS}
    if not BUILD_GEOJSON.exists():
        print(f"  NOTE: {BUILD_GEOJSON.name} not found; context tab unavailable")
        return empty

    props_by_nom = _load_build_geojson_properties()
    if not props_by_nom:
        return empty

    sample_phr = (next(iter(props_by_nom.values())).get(_PHR_DATASET) or {})
    if not isinstance(sample_phr, dict) or not sample_phr:
        print(f"  NOTE: no {_PHR_DATASET} block in build GeoJSON; context tab empty")
        return empty

    by_lang: dict[str, dict] = {}
    for lang in SUPPORTED_LANGS:
        ctx = _load_public_health_context_for_lang(props_by_nom, sample_phr, lang)
        by_lang[lang] = ctx
        n_national = sum(1 for p in ctx["national"] if p.get("scope") == "national")
        n_provincial = sum(1 for p in ctx["national"] if p.get("scope") == "provincial")
        print(
            f"  public health context ({lang}): {n_national} national + "
            f"{n_provincial} provincial pillar(s), "
            f"{len(ctx['by_nom'])} zone(s) with local narrative"
        )
    return by_lang


# ---------------------------------------------------------------------------
# per-zone payload
# ---------------------------------------------------------------------------

def _load_local_csv_fields() -> dict[str, dict]:
    """Load fields only available in the local metadata CSV (not in the build),
    keyed by nom (using _NAME_TO_NOM to translate CSV name → build nom)."""
    if not METADATA_CSV.exists():
        print(f"  WARNING: {METADATA_CSV} not found, local-only fields unavailable")
        return {}
    df = pd.read_csv(METADATA_CSV)
    df = df.dropna(subset=["ref_dhis2"]).copy()
    df["name"] = df["name"].astype(str)

    if "relative_risk" not in df.columns and "projected_true_infections" in df.columns:
        proj = pd.to_numeric(df["projected_true_infections"], errors="coerce")
        proj_max = proj.max()
        if pd.notna(proj_max) and proj_max > 0:
            df["relative_risk"] = np.log1p(proj.fillna(0)) / np.log1p(proj_max)
        else:
            df["relative_risk"] = np.nan

    fields_f = [
        "relative_risk",
    ]
    fields_i: list[str] = []
    out: dict[str, dict] = {}
    for _, row in df.iterrows():
        name = row["name"]
        nom = _NAME_TO_NOM.get(name, name)
        rec: dict = {}
        for c in fields_f:
            if c in df.columns:
                rec[c] = _f(row.get(c))
        for c in fields_i:
            if c in df.columns:
                rec[c] = _i(row.get(c))
        out[nom] = rec
    return out


def _extract_matrix_column(csv_path: Path, target_col: str) -> dict[str, float | None]:
    """Extract a single named column from a zone-to-zone matrix CSV.
    Returns {nom: value}."""
    if not csv_path.exists():
        print(f"  WARNING: {csv_path} not found")
        return {}
    df = pd.read_csv(csv_path)
    nom_col = "nom" if "nom" in df.columns else df.columns[1]
    col = None
    target_dotted = target_col.replace(" ", ".")
    for c in df.columns:
        if c == target_col or c == target_dotted:
            col = c
            break
    if col is None:
        print(f"  WARNING: column {target_col!r} not found in {csv_path.name}")
        return {}
    return {str(row[nom_col]): _f(row[col]) for _, row in df.iterrows()}


def _extract_matrix_row_sums(csv_path: Path) -> dict[str, float | None]:
    """Sum each row of a zone-to-zone matrix (excluding the nom column).
    Returns {nom: row_sum}."""
    if not csv_path.exists():
        print(f"  WARNING: {csv_path} not found")
        return {}
    df = pd.read_csv(csv_path)
    if "nom" in df.columns:
        noms = df["nom"].astype(str)
        numeric = df.drop(columns=["nom"]).apply(pd.to_numeric, errors="coerce")
    else:
        noms = df.iloc[:, 1].astype(str)
        numeric = df.iloc[:, 2:].apply(pd.to_numeric, errors="coerce")
    sums = numeric.sum(axis=1)
    return {noms.iloc[i]: _f(sums.iloc[i]) for i in range(len(df))}


def _load_flowminder_short_trips_vector(
    csv_path: Path,
    flat_field: str,
) -> dict[str, float | None]:
    """Load a long-format flowminder_short_trips vector into {nom: value}."""
    if not csv_path.exists():
        print(f"  WARNING: {csv_path} not found")
        return {}
    df = pd.read_csv(csv_path)
    if "nom" not in df.columns:
        print(f"  WARNING: {csv_path.name} missing nom column")
        return {}
    value_cols = [c for c in df.columns if c != "nom"]
    if len(value_cols) != 1:
        print(f"  WARNING: {csv_path.name} expected one value column, got {value_cols}")
        return {}
    value_col = value_cols[0]
    out: dict[str, float | None] = {}
    for _, row in df.iterrows():
        raw_nom = str(row["nom"]).strip()
        nom = _NAME_TO_NOM.get(raw_nom, raw_nom)
        out[nom] = _f(row[value_col])
    return out


def _build_matrix_zone_aliases(zones: list[str]) -> dict[str, str]:
    """Map matrix CSV row/column labels to canonical GeoJSON ``nom`` values."""
    aliases: dict[str, str] = {}
    for nom in zones:
        aliases[nom] = nom
        aliases[nom.replace(" ", ".")] = nom
        aliases[nom.replace("-", ".")] = nom
    for meta_name, nom in _NAME_TO_NOM.items():
        aliases[meta_name] = nom
        aliases[meta_name.replace(" ", ".")] = nom
    return aliases


def _matrix_header_to_nom(header: str, aliases: dict[str, str]) -> str | None:
    if header in aliases:
        return aliases[header]
    dotted = header.replace(".", " ")
    if dotted in aliases:
        return aliases[dotted]
    return None


def _read_matrix_zone_order(csv_path: Path) -> list[str]:
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path)
    nom_col = "nom" if "nom" in df.columns else df.columns[1]
    return [str(v) for v in df[nom_col].tolist()]


def _load_square_matrix_csv(
    csv_path: Path,
    zones: list[str],
) -> list[list[float | None]]:
    """Load a zone×zone matrix aligned to ``zones`` (rows = origin, cols = dest)."""
    n = len(zones)
    empty = [[None] * n for _ in range(n)]
    if not csv_path.exists():
        print(f"  WARNING: {csv_path} not found")
        return empty
    df = pd.read_csv(csv_path)
    nom_col = "nom" if "nom" in df.columns else df.columns[1]
    skip_cols = {df.columns[0], nom_col}
    aliases = _build_matrix_zone_aliases(zones)
    zone_idx = {z: i for i, z in enumerate(zones)}

    col_to_zone_idx: dict[str, int] = {}
    for col in df.columns:
        if col in skip_cols:
            continue
        dest = _matrix_header_to_nom(str(col), aliases)
        if dest and dest in zone_idx:
            col_to_zone_idx[str(col)] = zone_idx[dest]

    out = [[None] * n for _ in range(n)]
    for _, row in df.iterrows():
        origin = str(row[nom_col])
        oi = zone_idx.get(origin)
        if oi is None:
            resolved = aliases.get(origin) or aliases.get(origin.replace(".", " "))
            oi = zone_idx.get(resolved) if resolved else None
        if oi is None:
            continue
        for col_name, di in col_to_zone_idx.items():
            out[oi][di] = _f(row[col_name])
    return out


def load_zone_matrices(zones: list[str]) -> dict:
    """Square zone matrices for client-side origin switching (rows = from, cols = to)."""
    travel = _load_square_matrix_csv(OSRM_TRAVEL_TIME_CSV, zones)
    road = _load_square_matrix_csv(OSRM_ROAD_DISTANCE_CSV, zones)
    return {
        "zones": zones,
        "default_origin": "Mongbwalu",
        "datasets": {
            "osrm__travel_time": {"values": travel, "scale": 60},
            "osrm__road_distance": {"values": road, "scale": 1},
        },
    }


def _flowminder_processed_dir() -> Path:
    """Resolve Flowminder processed matrices (env override, data/, or legacy path)."""
    for candidate in (
        FLOWMINDER_PROCESSED,
        EXTERNAL_DATA / "flowminder" / "processed",
        BUILD_DIR.parent / "Data" / "Flowminder" / "Processed",
    ):
        if candidate.is_dir():
            return candidate.resolve()
    return FLOWMINDER_PROCESSED.resolve()


def _matrix_count_value(v: float | None) -> int | float | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if float(v) <= 0:
        return None
    fv = float(v)
    return int(fv) if fv == int(fv) else round(fv, 2)


def _sparse_out_by_origin(
    matrix: list[list[float | None]],
    zones: list[str],
) -> dict[str, list[list]]:
    """Non-zero OD pairs per origin row: {origin: [[dest, count], ...]}."""
    out: dict[str, list[list]] = {}
    for oi, origin in enumerate(zones):
        pairs: list[list] = []
        for di, dest in enumerate(zones):
            if oi == di:
                continue
            v = _matrix_count_value(matrix[oi][di])
            if v is not None:
                pairs.append([dest, v])
        if pairs:
            out[origin] = pairs
    return out


def _sparse_in_by_dest(
    matrix: list[list[float | None]],
    zones: list[str],
) -> dict[str, list[list]]:
    """Non-zero OD pairs per destination column: {dest: [[origin, count], ...]}."""
    out: dict[str, list[list]] = {}
    for di, dest in enumerate(zones):
        pairs: list[list] = []
        for oi, origin in enumerate(zones):
            if oi == di:
                continue
            v = _matrix_count_value(matrix[oi][di])
            if v is not None:
                pairs.append([origin, v])
        if pairs:
            out[dest] = pairs
    return out


_FLOWMINDER_DATED_MATRIX_RE = re.compile(
    r"^flowminder__(inflow|outflow)_(\d{6})__static\.matrix\.csv$"
)
_MONTH_NAME_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_MONTH_NAME_FR = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def _yyyymm_prev(yyyymm: str) -> tuple[int, int]:
    year = int(yyyymm[:4])
    month = int(yyyymm[4:6])
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _format_month_en(year: int, month: int) -> str:
    return f"{_MONTH_NAME_EN[month - 1]} {year}"


def _format_month_fr(year: int, month: int) -> str:
    return f"{_MONTH_NAME_FR[month - 1]} {year}"


def _flowminder_period_labels(yyyymm: str) -> dict[str, str]:
    """Human labels for a Flowminder ``_YYYYMM`` snapshot (window end month)."""
    end_y, end_m = int(yyyymm[:4]), int(yyyymm[4:6])
    start_y, start_m = _yyyymm_prev(yyyymm)
    start_en = _format_month_en(start_y, start_m)
    end_en = _format_month_en(end_y, end_m)
    start_fr = _format_month_fr(start_y, start_m)
    end_fr = _format_month_fr(end_y, end_m)
    return {
        "yyyymm": yyyymm,
        "choropleth_en": (
            f"Relocated persons between {start_en} and {end_en} (Flowminder)"
        ),
        "choropleth_fr": (
            f"Personnes relocalisées entre {start_fr} et {end_fr} (Flowminder)"
        ),
        "info_en": f"relocated persons {start_en}–{end_en} (Flowminder)",
        "info_fr": f"personnes relocalisées {start_fr}–{end_fr} (Flowminder)",
        "arcs_en": f"Flowminder in- and out-flow ({end_en})",
        "arcs_fr": f"Flux Flowminder entrants et sortants ({end_fr})",
        "end_month_en": end_en,
        "end_month_fr": end_fr,
    }


def discover_latest_flowminder_yyyymm(proc: Path | None = None) -> str | None:
    """Return the latest ``YYYYMM`` that has both inflow and outflow matrices."""
    directory = proc or _flowminder_processed_dir()
    if not directory.is_dir():
        return None
    by_tag: dict[str, set[str]] = {}
    for path in directory.iterdir():
        m = _FLOWMINDER_DATED_MATRIX_RE.match(path.name)
        if not m:
            continue
        direction, yyyymm = m.group(1), m.group(2)
        by_tag.setdefault(yyyymm, set()).add(direction)
    complete = [tag for tag, dirs in by_tag.items() if {"inflow", "outflow"} <= dirs]
    return max(complete) if complete else None


def flowminder_dated_matrix_paths(yyyymm: str, proc: Path | None = None) -> tuple[Path, Path]:
    directory = proc or _flowminder_processed_dir()
    return (
        directory / f"flowminder__inflow_{yyyymm}__static.matrix.csv",
        directory / f"flowminder__outflow_{yyyymm}__static.matrix.csv",
    )


def load_flowminder_sparse_from_paths(
    in_path: Path,
    out_path: Path,
    *,
    label: str = "flowminder",
) -> dict:
    """Sparse in/out catalogs for arc rendering from a pair of OD matrices."""
    zones = _read_matrix_zone_order(in_path) or _read_matrix_zone_order(out_path)
    if not zones:
        print(f"  WARNING: Flowminder matrices not found ({label})")
        return {
            "zones": [],
            "default_hub": "Mongbwalu",
            "out_by_origin": {},
            "in_by_dest": {},
            "yyyymm": None,
        }
    in_matrix = _load_square_matrix_csv(in_path, zones)
    out_matrix = _load_square_matrix_csv(out_path, zones)
    out_by_origin = _sparse_out_by_origin(out_matrix, zones)
    in_by_dest = _sparse_in_by_dest(in_matrix, zones)
    n_out = sum(len(v) for v in out_by_origin.values())
    n_in = sum(len(v) for v in in_by_dest.values())
    print(
        f"  flowminder sparse ({label}): {len(zones)} zones, "
        f"{n_out} out-pairs, {n_in} in-pairs"
    )
    return {
        "zones": zones,
        "default_hub": "Mongbwalu",
        "out_by_origin": out_by_origin,
        "in_by_dest": in_by_dest,
    }


def load_flowminder_mar_sparse() -> dict:
    """Sparse March 2026 Flowminder in/out matrices (undated ``__static`` pair)."""
    proc = _flowminder_processed_dir()
    return load_flowminder_sparse_from_paths(
        proc / "flowminder__inflow__static.matrix.csv",
        proc / "flowminder__outflow__static.matrix.csv",
        label="mar2026/undated",
    )


def load_flowminder_latest_sparse() -> tuple[dict, str | None]:
    """Load the newest ``_YYYYMM`` Flowminder inflow/outflow pair for flow arcs."""
    proc = _flowminder_processed_dir()
    yyyymm = discover_latest_flowminder_yyyymm(proc)
    if not yyyymm:
        print(f"  WARNING: no dated Flowminder matrices under {proc}")
        return (
            {
                "zones": [],
                "default_hub": "Mongbwalu",
                "out_by_origin": {},
                "in_by_dest": {},
            },
            None,
        )
    in_path, out_path = flowminder_dated_matrix_paths(yyyymm, proc)
    catalog = load_flowminder_sparse_from_paths(
        in_path, out_path, label=f"latest/{yyyymm}"
    )
    catalog["yyyymm"] = yyyymm
    return catalog, yyyymm


def load_metadata(
    centroids: dict[str, tuple[float, float]],
    field_paths: dict[str, list[str]],
) -> tuple[dict[str, dict], dict]:
    """Assemble per-zone metadata from build GeoJSON properties (auto-discovered),
    OSRM matrices, IDP/Flowminder matrices, and local CSV fallback fields."""
    build_props = _load_build_geojson_properties()
    local_fields = _load_local_csv_fields()

    # OSRM matrices
    travel_times = _extract_matrix_column(OSRM_TRAVEL_TIME_CSV, "Mongbwalu")
    road_dists = _extract_matrix_column(OSRM_ROAD_DISTANCE_CSV, "Mongbwalu")

    # IDP and Flowminder matrices (row sums = incoming totals)
    idp_incoming = _extract_matrix_row_sums(
        EXTERNAL_DATA / "IDP" / "processed" / "idp__individuals__static.matrix.csv")
    flowminder_proc = _flowminder_processed_dir()
    flowminder_incoming_mar = _extract_matrix_row_sums(
        flowminder_proc / "flowminder__inflow__static.matrix.csv"
    )
    flowminder_incoming_202604 = _extract_matrix_row_sums(
        flowminder_proc / "flowminder__inflow_202604__static.matrix.csv"
    )

    zone_data: dict[str, dict] = {}
    for nom, props in build_props.items():
        rec: dict = {"name": nom}

        # Centroids
        if nom in centroids:
            lon, lat = centroids[nom]
            rec["centroid_lon"] = lon
            rec["centroid_lat"] = lat

        # Auto-discovered GeoJSON fields
        rec.update(extract_geojson_fields(props, field_paths))

        # Epi: prefer INSP sitrep cumulative (more recent) over WHO epi snapshot.
        # Use explicit None checks — `or` would treat 0 as falsy.
        insp = props.get("insp_sitrep", {})
        epi = props.get("epi", {}).get("cases", {})
        for dst, insp_key, epi_key in (
            ("confirmed_cases",  "cumulative_confirmed_cases",  "confirmed_cases"),
            ("confirmed_deaths", "cumulative_confirmed_deaths", "confirmed_deaths"),
            ("suspected_cases",  "cumulative_suspected_cases",  "suspected_cases"),
            ("suspected_deaths", "cumulative_suspected_deaths", "suspected_deaths"),
        ):
            v = _i(insp.get(insp_key, {}).get(insp_key))
            if v is None:
                v = _i(epi.get(epi_key))
            rec[dst] = v
        rec["total_cases"] = (rec.get("confirmed_cases") or 0) + (rec.get("suspected_cases") or 0)

        # OSRM (travel time is in minutes in the matrix → convert to hours)
        tt = travel_times.get(nom)
        rec["travel_time_to_mongbwalu_h"] = round(tt / 60, 2) if tt else None
        rec["geodesic_to_mongbwalu_km"] = road_dists.get(nom)

        # IDP / Flowminder
        rec["displaced_in_individuals_12mo"] = _i(idp_incoming.get(nom))
        rec["flowminder_in_mar2026"] = _i(flowminder_incoming_mar.get(nom))
        rec["flowminder_in_202604"] = _i(flowminder_incoming_202604.get(nom))

        # Genomic surveillance (embedded per-zone in the build GeoJSON).
        seq_count = _i(
            props.get("genomic_surveillance", {})
            .get("sequence_count", {})
            .get("sequence_count")
        )
        if seq_count and seq_count > 0:
            rec["genomic_sequence_count"] = seq_count

        zone_data[nom] = rec

    # HDX cohort subscriber-day vectors (not yet in build GeoJSON).
    _SHORT_TRIPS_VECTOR_FILES = (
        (
            "flowminder_short_trips__ituri_subscriber_days_followup_20260608__ituri_subscriber_days_followup_20260608",
            "flowminder_short_trips__ituri_subscriber_days_followup_20260608__static.csv",
        ),
        (
            "flowminder_short_trips__ituri_subscriber_days_prior_20260503__ituri_subscriber_days_prior_20260503",
            "flowminder_short_trips__ituri_subscriber_days_prior_20260503__static.csv",
        ),
        (
            "flowminder_short_trips__nk_subscriber_days_followup_20260608__nk_subscriber_days_followup_20260608",
            "flowminder_short_trips__nk_subscriber_days_followup_20260608__static.csv",
        ),
        (
            "flowminder_short_trips__nk_subscriber_days_prior_20260503__nk_subscriber_days_prior_20260503",
            "flowminder_short_trips__nk_subscriber_days_prior_20260503__static.csv",
        ),
    )
    for flat_field, filename in _SHORT_TRIPS_VECTOR_FILES:
        values = _load_flowminder_short_trips_vector(
            FLOWMINDER_SHORT_TRIPS_PROCESSED / filename,
            flat_field,
        )
        for nom, value in values.items():
            zone_data.setdefault(nom, {"name": nom})
            zone_data[nom][flat_field] = value

    # Local-CSV-only fields (applied after zone_data loop for zones only in build_props)
    for nom, rec in zone_data.items():
        local = local_fields.get(nom, {})
        rec["relative_risk"] = local.get("relative_risk")

    # Case totals
    totals: dict = {}
    for col in ("confirmed_cases", "confirmed_deaths",
                "suspected_cases", "suspected_deaths"):
        totals[col] = sum(int(r.get(col) or 0) for r in zone_data.values())
    totals["affected_zones"] = sum(
        1 for r in zone_data.values()
        if (int(r.get("confirmed_cases") or 0) + int(r.get("suspected_cases") or 0)) > 0)

    return zone_data, totals


def compute_global_sitrep_totals() -> dict | None:
    """Tracker outbreak totals: sit-rep CSV if present, else GeoJSON national_*.

    Primary source is the newest dated CSV in Data/Epidemiological Data/ (supports
    multiple countries). When that is unavailable, uses INSP national cumulative
    fields from drc_health_zones.geojson (DRC only; not summed from zones).

    When a sit-rep's Total row underreports relative to per-country rows, we credit
    the excess to the largest country (CSV path only).
    """
    # Template merged at the end of the CSV path; unused on GeoJSON fallback.
    out = {
        "global_confirmed_cases": 0, "global_suspected_cases": 0,
        "global_confirmed_deaths": 0, "global_suspected_deaths": 0,
        "global_recovered_cases": 0,
        "global_total_cases": 0,
        "affected_countries": [], "affected_country_count": 0,
        "per_country": [],
    }
    # No local sit-rep folder → skip CSV and use build GeoJSON national totals.
    if not SIT_REPS_DIR.exists():
        return _national_totals_from_build_geojson()
    # Collect paths whose filenames parse as YYYY-MM-DD.csv.
    dated = []
    for p in SIT_REPS_DIR.iterdir():
        if not p.is_file() or p.suffix.lower() != ".csv":
            continue
        try:
            dated.append((datetime.strptime(p.stem, "%Y-%m-%d").date(), p))
        except ValueError:
            continue
    # Folder exists but has no dated CSVs → national totals from GeoJSON.
    if not dated:
        return _national_totals_from_build_geojson()
    _, path = max(dated)
    sr_all = pd.read_csv(path)
    sr_all.columns = [c.strip().lower() for c in sr_all.columns]
    total_mask = sr_all["country"].astype(str).str.strip().str.lower() == "total"
    total_row = sr_all[total_mask].iloc[0] if total_mask.any() else None
    sr = sr_all[~total_mask].copy()
    sr["country"] = sr["country"].astype(str).str.strip()
    metric_cols = ["confirmed cases", "suspected cases", "confirmed deaths", "suspected deaths"]
    for c in metric_cols:
        sr[c] = pd.to_numeric(sr[c], errors="coerce").fillna(0).astype(int)
    grouped = sr.groupby("country", as_index=False)[metric_cols].sum()
    grouped["total"] = grouped["confirmed cases"]
    grouped = grouped[grouped["total"] > 0].sort_values("total", ascending=False)

    def total_metric(col):
        if total_row is None:
            return None
        v = pd.to_numeric(total_row[col], errors="coerce")
        return None if pd.isna(v) else int(v)

    def credit_excess(col):
        per_zone_sum = int(grouped[col].sum())
        total_val = total_metric(col)
        if total_val is None or grouped.empty:
            return per_zone_sum if total_val is None else total_val
        if total_val <= per_zone_sum:
            return per_zone_sum
        primary = grouped["total"].idxmax()
        grouped.loc[primary, col] += (total_val - per_zone_sum)
        return total_val

    final_conf   = credit_excess("confirmed cases")
    final_susp   = credit_excess("suspected cases")
    final_conf_d = credit_excess("confirmed deaths")
    final_susp_d = credit_excess("suspected deaths")

    per_country = []
    for _, r in grouped.iterrows():
        per_country.append({
            "country": str(r["country"]),
            "confirmed_cases": int(r["confirmed cases"]),
            "suspected_cases": int(r["suspected cases"]),
            "confirmed_deaths": int(r["confirmed deaths"]),
            "suspected_deaths": int(r["suspected deaths"]),
            "total": int(r["confirmed cases"]) + int(r["suspected cases"]),
        })
    out.update({
        "global_confirmed_cases":  final_conf,
        "global_suspected_cases":  final_susp,
        "global_confirmed_deaths": final_conf_d,
        "global_suspected_deaths": final_susp_d,
        "global_total_cases":      final_conf,
        "affected_countries":      [c["country"] for c in per_country],
        "affected_country_count":  len(per_country),
        "per_country":             per_country,
    })
    geo_nat = _national_totals_from_build_geojson()
    if geo_nat is not None:
        out["global_recovered_cases"] = geo_nat.get("global_recovered_cases", 0)
    return out


def build_active_case_markers(zone_data: dict[str, dict],
                              centroids: dict[str, tuple[float, float]]
                              ) -> list[dict]:
    """One marker per zone with ≥1 confirmed case (from GeoJSON-derived fields).

    Suspected-only zones are excluded — markers track confirmed burden only.
    """
    out: list[dict] = []
    for nom, rec in zone_data.items():
        if nom not in centroids:
            continue
        conf = int(rec.get("confirmed_cases") or 0)
        if conf <= 0:
            continue
        susp = int(rec.get("suspected_cases") or 0)
        lon, lat = centroids[nom]
        out.append({
            "nom": nom,
            "name": _NOM_TO_NAME.get(nom, nom),
            "lat": lat,
            "lon": lon,
            "confirmed": conf,
            "suspected": susp,
            "confirmed_deaths": int(rec.get("confirmed_deaths") or 0),
            "suspected_deaths": int(rec.get("suspected_deaths") or 0),
            "total": conf + susp,
        })
    return out


def build_genome_sequence_markers(
    zone_data: dict[str, dict],
    centroids: dict[str, tuple[float, float]],
) -> list[dict]:
    """One marker per zone with at least one genome sequence.

    Reads ``genomic_sequence_count`` from ``zone_data``, which load_metadata()
    already populates from the build GeoJSON's embedded genomic_surveillance
    properties (no separate CSV read needed)."""
    out: list[dict] = []
    for nom, rec in zone_data.items():
        if nom not in centroids:
            continue
        count = rec.get("genomic_sequence_count")
        if not count or count <= 0:
            continue
        lon, lat = centroids[nom]
        out.append({
            "nom": nom,
            "name": _NOM_TO_NAME.get(nom, nom),
            "lat": lat,
            "lon": lon,
            "count": count,
        })
    return out


# ---------------------------------------------------------------------------
# methods + terms text
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
_BULLET_PREFIXES = ("•", "•", "−", "—", "-")


def _strip_bullet(s: str) -> str:
    for prefix in _BULLET_PREFIXES:
        if s.startswith(prefix):
            return s[len(prefix):].lstrip()
    return s.lstrip()


def load_methods_html(path: Path | None = None) -> str:
    """Render Contributors_Methods_Data_website.docx as an HTML snippet.

    Headings 1/2/3 -> h2/h3/h4. Bold-only paragraphs are promoted to h2 as a
    fallback for documents that mark sections with bold runs only. Bullet
    glyphs (•, −, —) at the start of a paragraph are folded into a <ul>.
    Hyperlinks are preserved with target=_blank. Email addresses become
    mailto: links.
    """
    docx_path = path or METHODS_DOCX
    if not docx_path.exists():
        return ""
    try:
        from docx import Document
        from docx.oxml.ns import qn
        from docx.text.paragraph import Paragraph
    except Exception:
        return ("<p style='color:#c66'>python-docx not installed; cannot render "
                f"{docx_path.name}.</p>")
    d = Document(docx_path)
    rid_to_url: dict[str, str] = {}
    for rid, rel in d.part.rels.items():
        if "hyperlink" in rel.reltype.lower():
            rid_to_url[rid] = getattr(rel, "target_ref", None) or rel._target

    def _linkify(html: str) -> str:
        return _EMAIL_RE.sub(
            lambda m: f'<a href="mailto:{m.group(1)}">{m.group(1)}</a>',
            html,
        )

    def _runs_to_html(node) -> str:
        out: list[str] = []
        for child in node.iterchildren():
            tag = child.tag
            if tag == qn("w:r"):
                txt = "".join(t.text or "" for t in child.iter(qn("w:t")))
                if txt:
                    out.append(_linkify(_html_escape(txt)))
            elif tag == qn("w:hyperlink"):
                rid = child.get(qn("r:id")) or child.get(
                    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
                )
                txt = "".join(t.text or "" for t in child.iter(qn("w:t")))
                url = rid_to_url.get(rid, "")
                if txt and url:
                    out.append(
                        f'<a href="{_html_escape(url)}" target="_blank" rel="noopener">'
                        f"{_html_escape(txt)}</a>"
                    )
                elif txt:
                    out.append(_linkify(_html_escape(txt)))
        return "".join(out)

    def _table_html(tbl_el) -> str:
        rows_html: list[str] = []
        for ri, tr in enumerate(tbl_el.iterfind(qn("w:tr"))):
            cells_html: list[str] = []
            for tc in tr.iterfind(qn("w:tc")):
                pieces = []
                for p in tc.iterfind(qn("w:p")):
                    s = _runs_to_html(p)
                    if s:
                        pieces.append(s)
                cells_html.append("<br/>".join(pieces))
            tag = "th" if ri == 0 else "td"
            rows_html.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells_html) + "</tr>")
        return "<table class='methods-table'>" + "".join(rows_html) + "</table>"

    def _is_bold_heading(p) -> bool:
        runs = [r for r in p.runs if (r.text or "").strip()]
        return bool(runs) and all(bool(r.bold) for r in runs)

    parts: list[str] = []
    in_ul = False
    for child in d.element.body.iterchildren():
        tag = child.tag
        if tag == qn("w:tbl"):
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            parts.append(_table_html(child))
            continue
        if tag != qn("w:p"):
            continue
        para = Paragraph(child, d.part)
        txt = (para.text or "").strip()
        style = para.style.name if para.style else "Normal"
        if not txt:
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            continue
        html_body = _runs_to_html(child)
        is_bullet = any(txt.startswith(p) for p in _BULLET_PREFIXES[:-1])
        if is_bullet:
            if not in_ul:
                parts.append("<ul>")
                in_ul = True
            parts.append(f"<li>{_strip_bullet(html_body)}</li>")
            continue
        if in_ul:
            parts.append("</ul>")
            in_ul = False
        if style.startswith("Title") or style.startswith("Heading 1"):
            parts.append(f"<h2>{html_body}</h2>")
        elif style.startswith("Heading 2"):
            parts.append(f"<h3>{html_body}</h3>")
        elif style.startswith("Heading 3"):
            parts.append(f"<h4>{html_body}</h4>")
        elif _is_bold_heading(para):
            parts.append(f"<h2>{html_body}</h2>")
        else:
            parts.append(f"<p>{html_body}</p>")
    if in_ul:
        parts.append("</ul>")
    return "\n".join(parts)


_TERMS_SECTION_RE = re.compile(r"^(\d+)\.\s+(.+)$")
_TERMS_LASTUPDATED_RE = re.compile(r"^Last updated:\s*(.+)$", re.IGNORECASE)
_TERMS_LASTUPDATED_FR_RE = re.compile(r"^Dernière mise à jour\s*:\s*(.+)$", re.IGNORECASE)
_TERMS_HEADER_SKIP_RE = re.compile(
    r"^(terms of use|conditions d'utilisation)$", re.IGNORECASE,
)


def load_methods_html_lang(lang: str = "en") -> str:
    """Load methods content for ``lang`` (docx preferred; French HTML fallback)."""
    if lang == "fr":
        if METHODS_DOCX_FR.exists():
            return load_methods_html(METHODS_DOCX_FR)
        if METHODS_HTML_FR.exists():
            print(f"  methods HTML (fr): {METHODS_HTML_FR.name}")
            return METHODS_HTML_FR.read_text(encoding="utf-8").strip()
        print("  WARNING: no French methods document; falling back to English")
    return load_methods_html(METHODS_DOCX)


def load_terms_html(path: Path | None = None) -> tuple[str, str]:
    terms_path = path or TERMS_TXT
    if not terms_path.exists():
        return "", ""
    last_updated = ""
    parts: list[str] = []
    for line in terms_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or _TERMS_HEADER_SKIP_RE.match(line):
            continue
        m = _TERMS_LASTUPDATED_RE.match(line) or _TERMS_LASTUPDATED_FR_RE.match(line)
        if m:
            last_updated = m.group(1).strip()
            continue
        m = _TERMS_SECTION_RE.match(line)
        if m:
            parts.append(f"<h3>{_html_escape(m.group(1))}. {_html_escape(m.group(2))}</h3>")
            continue
        text = _html_escape(line)
        text = _EMAIL_RE.sub(
            lambda mm: f"<a href='mailto:{mm.group(1)}'>{mm.group(1)}</a>",
            text,
        )
        parts.append(f"<p>{text}</p>")
    return "\n".join(parts), last_updated


def load_terms_html_lang(lang: str = "en") -> tuple[str, str]:
    if lang == "fr" and TERMS_TXT_FR.exists():
        return load_terms_html(TERMS_TXT_FR)
    if lang == "fr":
        print("  WARNING: no French terms document; falling back to English")
    return load_terms_html(TERMS_TXT)


# ---------------------------------------------------------------------------
# partner logos
# ---------------------------------------------------------------------------

_LOGO_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def load_logo_data_uri(filename: str) -> str:
    path = BRANDING_DIR / filename
    if not path.exists():
        return ""
    mime = _LOGO_MIME.get(path.suffix.lower(), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def load_partners() -> list[dict]:
    if not BRANDING_DIR.exists():
        return []
    url_map: dict[str, str] = {}
    if BRANDING_URLS.exists():
        for line in BRANDING_URLS.read_text(encoding="utf-8").splitlines():
            if "," not in line:
                continue
            fname, url = line.split(",", 1)
            url_map[fname.strip()] = url.strip()
    out: list[dict] = []
    for fname in PARTNER_ORDER:
        uri = load_logo_data_uri(fname)
        if uri:
            out.append({
                "alt": Path(fname).stem.upper(),
                "href": url_map.get(fname, ""),
                "data_uri": uri,
            })
    return out


# ---------------------------------------------------------------------------
# layer auto-discovery from GeoJSON properties
# ---------------------------------------------------------------------------

# Keys in GeoJSON properties that are metadata, not data layers.
_SKIP_PROPERTY_KEYS = {"nom", "zscode", "province"}

# Leaf values that are non-numeric strings to treat as missing.
_NON_NUMERIC_STRINGS = {"ND", "NA", ""}

# Leaf keys that are always excluded (non-numeric identifiers).
_EXCLUDE_LEAVES = {"poe_names"}

LAYER_CONFIG_YAML = SCRIPT_DIR.parent / "layer_config.yaml"


def _load_layer_config() -> dict:
    """Load layer_config.yaml. Returns empty-ish defaults if missing."""
    if not LAYER_CONFIG_YAML.exists():
        print(f"  WARNING: {LAYER_CONFIG_YAML} not found, using defaults")
        return {}
    try:
        import yaml
    except ImportError:
        print("  WARNING: PyYAML not installed, layer_config.yaml ignored")
        return {}
    with open(LAYER_CONFIG_YAML) as f:
        return yaml.safe_load(f) or {}


def _prettify_label(s: str) -> str:
    """Turn a snake_case key into a human-readable label."""
    return s.replace("_", " ").strip().capitalize()


def discover_geojson_layers(
    geojson_path: Path,
) -> tuple[list[dict], dict[str, list[str]]]:
    """Scan a GeoJSON file and return (layer_defs, field_paths).

    layer_defs: list of {"group", "id", "label", "field", "palette", "scale"}
    field_paths: {flat_field_name: [group_key, metric_key, leaf_key]} mapping
                 so load_metadata can extract values generically.

    Reads Data/layer_config.yaml for exclusions, group display names,
    palettes, scales, and ordering.
    """
    cfg = _load_layer_config()
    excludes = set(cfg.get("exclude", []) or [])
    group_cfg = cfg.get("groups", {}) or {}
    group_order = cfg.get("group_order", []) or []

    with open(geojson_path) as f:
        raw = json.load(f)

    # Pass 1: discover all group.metric.leaf paths with at least one numeric value
    numeric_paths: dict[str, tuple[str, str, str]] = {}
    for feat in raw["features"]:
        props = feat["properties"]
        for gkey, gval in props.items():
            if gkey in _SKIP_PROPERTY_KEYS or not isinstance(gval, dict):
                continue
            if gkey in excludes:
                continue
            for mkey, mval in gval.items():
                if not isinstance(mval, dict):
                    continue
                metric_key = f"{gkey}__{mkey}"
                if metric_key in excludes:
                    continue
                for lkey, lval in mval.items():
                    if lkey == "_date" or lkey in _EXCLUDE_LEAVES:
                        continue
                    flat = f"{gkey}__{mkey}__{lkey}"
                    if flat in excludes:
                        continue
                    if flat in numeric_paths:
                        continue
                    if isinstance(lval, (int, float)):
                        numeric_paths[flat] = (gkey, mkey, lkey)
                    elif isinstance(lval, str) and lval not in _NON_NUMERIC_STRINGS:
                        try:
                            float(lval)
                            numeric_paths[flat] = (gkey, mkey, lkey)
                        except ValueError:
                            pass

    # Pass 2: organise into groups, build layer defs
    groups: dict[str, list[tuple[str, str, str, str]]] = {}
    for flat, (gkey, mkey, lkey) in numeric_paths.items():
        label = _prettify_label(lkey)
        groups.setdefault(gkey, []).append((flat, mkey, lkey, label))
    for g in groups:
        groups[g].sort(key=lambda t: t[3])

    # Order groups
    ordered_groups: list[str] = []
    for g in group_order:
        if g in groups:
            ordered_groups.append(g)
    for g in sorted(groups):
        if g not in ordered_groups:
            ordered_groups.append(g)

    layer_defs: list[dict] = []
    field_paths: dict[str, list[str]] = {}
    for gkey in ordered_groups:
        gcfg = group_cfg.get(gkey, {}) or {}
        group_name = gcfg.get("label", gkey.replace("_", " ").title())
        palette = gcfg.get("palette", "viridis")
        scale = gcfg.get("scale", "log")
        legend_round = gcfg.get("legend_round", "int")
        epicenter_highlight = bool(gcfg.get("epicenter_highlight", False))
        for flat, mkey, lkey, label in groups[gkey]:
            layer_id = f"{gkey}::{mkey}"
            if lkey != mkey:
                layer_id = f"{gkey}::{mkey}::{lkey}"
            layer_defs.append({
                "group": group_name,
                "id": layer_id,
                "label": label,
                "field": flat,
                "palette": palette,
                "scale": scale,
                "source": "",
                "legend_round": legend_round,
                "epicenter_highlight": epicenter_highlight,
            })
            field_paths[flat] = [gkey, mkey, lkey]

    return layer_defs, field_paths


def extract_geojson_fields(
    props: dict,
    field_paths: dict[str, list[str]],
) -> dict[str, float | int | None]:
    """Given a single feature's properties and the field_paths mapping,
    extract all discovered numeric values into a flat dict."""
    rec: dict[str, float | int | None] = {}
    for flat, (gkey, mkey, lkey) in field_paths.items():
        raw_val = props.get(gkey, {}).get(mkey, {}).get(lkey)
        if isinstance(raw_val, str):
            if raw_val in _NON_NUMERIC_STRINGS:
                rec[flat] = None
                continue
            try:
                raw_val = float(raw_val)
            except ValueError:
                rec[flat] = None
                continue
        rec[flat] = _f(raw_val)
    return rec


# ---------------------------------------------------------------------------
# extra (non-GeoJSON) layers: matrices, local CSV, computed fields
# ---------------------------------------------------------------------------

EXTRA_LAYER_DEFS_TRAVEL = [
    ("Travel distance (OSRM)", "d::travel", "Travel time from {origin} (hours)",   "", "plasma_r", "linear", 1, False, "osrm__travel_time", 60, True),
    ("Travel distance (OSRM)", "d::geo",    "Road distance from {origin} (km)",    "", "plasma_r", "linear", "int", False, "osrm__road_distance", 1, True),
]


def _make_layer_def(
    group: str,
    layer_id: str,
    label: str,
    field: str,
    palette: str,
    scale: str,
    legend_round,
    epicenter_highlight: bool = False,
    source: str = "",
    matrix_id: str = "",
    matrix_scale: float | int | None = None,
    origin_highlight: bool = False,
    viz: str = "",
    flow_catalog: str = "",
    epicenter_noms: list[str] | None = None,
    legend_caption: str = "",
) -> dict:
    layer = {
        "group": group,
        "id": layer_id,
        "label": label,
        "field": field,
        "palette": palette,
        "scale": scale,
        "source": source,
        "legend_round": legend_round,
        "epicenter_highlight": epicenter_highlight,
    }
    if epicenter_noms:
        layer["epicenter_noms"] = list(epicenter_noms)
    if legend_caption:
        layer["legend_caption"] = legend_caption
    if matrix_id:
        layer["matrix_id"] = matrix_id
        layer["matrix_scale"] = 1 if matrix_scale is None else matrix_scale
        layer["origin_highlight"] = origin_highlight
    elif viz:
        layer["viz"] = viz
        if flow_catalog:
            layer["flow_catalog"] = flow_catalog
        if origin_highlight:
            layer["origin_highlight"] = True
    return layer


# Flowminder short-trip layers (Annex A proportions + HDX cohort subscriber-days).
_FLOWMINDER_SHORT_TRIPS_GROUP = "Movements from epicentres (Flowminder)"
_FLOWMINDER_SHORT_TRIPS_LAYER_DEFS = [
    _make_layer_def(
        _FLOWMINDER_SHORT_TRIPS_GROUP,
        "fmst::20260430",
        "Percentage of persons from Ituri epicentre* observed in new health zone by April 30",
        "flowminder_short_trips__outflow_20260430__outflow_20260430",
        "reds", "log", 1,
        epicenter_highlight=True,
        epicenter_noms=list(EPICENTER_ITURI_SINGLE),
        legend_caption="Persons detected in new health zones",
    ),
    _make_layer_def(
        _FLOWMINDER_SHORT_TRIPS_GROUP,
        "fmst::20260507",
        "Percentage of persons from Ituri epicentre* observed in new health zone by May 7",
        "flowminder_short_trips__outflow_20260507__outflow_20260507",
        "reds", "log", 1,
        epicenter_highlight=True,
        epicenter_noms=list(EPICENTER_ITURI_SINGLE),
        legend_caption="Persons detected in new health zones",
    ),
    _make_layer_def(
        _FLOWMINDER_SHORT_TRIPS_GROUP,
        "fmst::20260514",
        "Percentage of persons from Ituri epicentre* observed in new health zone by May 14",
        "flowminder_short_trips__outflow_20260514__outflow_20260514",
        "reds", "log", 1,
        epicenter_highlight=True,
        epicenter_noms=list(EPICENTER_ITURI_SINGLE),
        legend_caption="Persons detected in new health zones",
    ),
    _make_layer_def(
        _FLOWMINDER_SHORT_TRIPS_GROUP,
        "fmst::20260521",
        "Percentage of persons from Ituri epicentre* observed in new health zone by May 21",
        "flowminder_short_trips__outflow_20260521__outflow_20260521",
        "reds", "log", 1,
        epicenter_highlight=True,
        epicenter_noms=list(EPICENTER_ITURI_SINGLE),
        legend_caption="Persons detected in new health zones",
    ),
    _make_layer_def(
        _FLOWMINDER_SHORT_TRIPS_GROUP,
        "fmst::20260524",
        "Percentage of persons from Ituri epicentre* observed in new health zone by May 24",
        "flowminder_short_trips__outflow_20260524__outflow_20260524",
        "reds", "log", 1,
        epicenter_highlight=True,
        epicenter_noms=list(EPICENTER_ITURI_SINGLE),
        legend_caption="Persons detected in new health zones",
    ),
    _make_layer_def(
        _FLOWMINDER_SHORT_TRIPS_GROUP,
        "fmst::ituri_followup",
        "Avg subscriber-days of Ituri epicentre** persons spent in new health zone by June 8",
        "flowminder_short_trips__ituri_subscriber_days_followup_20260608__ituri_subscriber_days_followup_20260608",
        "reds", "log", 2,
        epicenter_highlight=True,
        epicenter_noms=list(EPICENTER_ITURI_COHORT),
        legend_caption="Average subscriber-days",
    ),
    _make_layer_def(
        _FLOWMINDER_SHORT_TRIPS_GROUP,
        "fmst::ituri_prior",
        "Avg subscriber-days of Ituri epicentre** persons spent in new health zone by May 3",
        "flowminder_short_trips__ituri_subscriber_days_prior_20260503__ituri_subscriber_days_prior_20260503",
        "reds", "log", 2,
        epicenter_highlight=True,
        epicenter_noms=list(EPICENTER_ITURI_COHORT),
        legend_caption="Average subscriber-days",
    ),
    _make_layer_def(
        _FLOWMINDER_SHORT_TRIPS_GROUP,
        "fmst::nk_followup",
        "Avg subscriber-days of Nord-Kivu epicentre** persons spent in new health zone by June 8",
        "flowminder_short_trips__nk_subscriber_days_followup_20260608__nk_subscriber_days_followup_20260608",
        "reds", "log", 2,
        epicenter_highlight=True,
        epicenter_noms=list(EPICENTER_NK_COHORT),
        legend_caption="Average subscriber-days",
    ),
    _make_layer_def(
        _FLOWMINDER_SHORT_TRIPS_GROUP,
        "fmst::nk_prior",
        "Avg subscriber-days of Nord-Kivu epicentre** persons spent in new health zone by May 3",
        "flowminder_short_trips__nk_subscriber_days_prior_20260503__nk_subscriber_days_prior_20260503",
        "reds", "log", 2,
        epicenter_highlight=True,
        epicenter_noms=list(EPICENTER_NK_COHORT),
        legend_caption="Average subscriber-days",
    ),
]


FLOW_ARC_LAYER_DEF = _make_layer_def(
    "Incoming Mobility",
    "flow::od",
    "Flowminder in- and out-flow",
    "",
    "reds",
    "linear",
    "int",
    origin_highlight=True,
    viz="flow_arcs",
    flow_catalog="flowminder_latest",
)

EXTRA_LAYER_DEFS = [
    ("Observed (epi update)", "obs::total",     "Total cases (confirmed + suspected)", "total_cases",      "reds", "log", "int", False),
    ("Observed (epi update)", "obs::confirmed", "Confirmed cases",                     "confirmed_cases",  "reds", "log", "int", False),
    ("Observed (epi update)", "obs::suspected", "Suspected cases",                     "suspected_cases",  "reds", "log", "int", False),
    ("Observed (epi update)", "obs::conf_d",    "Confirmed deaths",                    "confirmed_deaths", "reds", "log", "int", False),
    ("Observed (epi update)", "obs::susp_d",    "Suspected deaths",                    "suspected_deaths", "reds", "log", "int", False),
    ("Modeled projection",    "cal::true",      "Relative risk",                       "relative_risk",    "outbreak", "log", 2, False),
    _make_layer_def(
        "Incoming Mobility",
        "disp::in",
        "Internally displaced persons (IOM)",
        "displaced_in_individuals_12mo",
        "reds", "log", "int",
    ),
    _make_layer_def(
        "Incoming Mobility",
        "flow::in",
        "Relocated persons between Feb 2026 and Mar 2026 (Flowminder)",
        "flowminder_in_mar2026",
        "reds", "log", "int",
        legend_caption="Number of relocated persons",
    ),
    _make_layer_def(
        "Incoming Mobility",
        "flow::in_apr",
        "Relocated persons between March 2026 and April 2026 (Flowminder)",
        "flowminder_in_202604",
        "reds", "log", "int",
        legend_caption="Number of relocated persons",
    ),
    *EXTRA_LAYER_DEFS_TRAVEL,
    *_FLOWMINDER_SHORT_TRIPS_LAYER_DEFS,
]


def _extra_layer_from_def(defn: tuple | dict) -> dict:
    if isinstance(defn, dict):
        return dict(defn)
    (group, lid, label, field, palette, scale, legend_round, epicenter_highlight) = defn[:8]
    kwargs: dict = {}
    if len(defn) > 8 and defn[8]:
        kwargs = {
            "matrix_id": defn[8],
            "matrix_scale": defn[9] if len(defn) > 9 else 1,
            "origin_highlight": defn[10] if len(defn) > 10 else True,
        }
    return _make_layer_def(
        group, lid, label, field, palette, scale, legend_round, epicenter_highlight, **kwargs)

PROJECTION_MASK_LAYERS = {"cal::true"}
PROJECTION_MASK_FIELD = "relative_risk"
PROJECTION_MASK_MIN = 0.005

# Dropdown optgroup order (display names). Unlisted groups keep their relative
# order after these entries.
LAYER_GROUP_ORDER = [
    "Observed (epi update)",
    "Testing capacity",
    "Incoming Mobility",
    "Movements from epicentres (Flowminder)",
]


def _sort_layers_for_dropdown(layers: list[dict]) -> list[dict]:
    rank = {name: i for i, name in enumerate(LAYER_GROUP_ORDER)}
    default_rank = len(LAYER_GROUP_ORDER)
    indexed = sorted(
        enumerate(layers),
        key=lambda item: (rank.get(item[1]["group"], default_rank), item[0]),
    )
    return [layer for _, layer in indexed]


# ---------------------------------------------------------------------------
# i18n (locale YAML + per-language layers / legal text)
# ---------------------------------------------------------------------------

def _load_locale_yaml(lang: str) -> dict:
    path = LOCALES_DIR / f"{lang}.yaml"
    if not path.exists():
        print(f"  WARNING: locale file missing: {path.name}")
        return {}
    try:
        import yaml
    except ImportError:
        print("  WARNING: PyYAML not installed; locale files ignored")
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_locales() -> dict[str, dict]:
    locales = {lang: _load_locale_yaml(lang) for lang in SUPPORTED_LANGS}
    for lang, data in locales.items():
        if data:
            print(f"  locale {lang}: loaded")
    return locales


def localize_layers(layers: list[dict], locale: dict) -> list[dict]:
    """Return a copy of ``layers`` with group/label text from a locale bundle."""
    group_map = locale.get("layer_groups") or {}
    label_map = locale.get("layer_labels") or {}
    out: list[dict] = []
    for layer in layers:
        localized = dict(layer)
        en_group = layer["group"]
        if en_group in group_map:
            localized["group"] = group_map[en_group]
        layer_id = layer["id"]
        label_template = None
        if layer_id in label_map:
            label_template = label_map[layer_id]
        elif "{origin}" in layer.get("label", ""):
            label_template = layer["label"]
        if label_template:
            localized["label_template"] = label_template
            localized["label"] = label_template.replace("{origin}", TRAVEL_FROM_ZONE)
        caption_map = locale.get("layer_legend_captions") or {}
        if layer_id in caption_map:
            localized["legend_caption"] = caption_map[layer_id]
        out.append(localized)
    return out


def build_i18n_payload(layers_en: list[dict], phr_context: dict[str, dict]) -> dict:
    locales = load_locales()
    layers_by_lang = {
        lang: localize_layers(layers_en, locales.get(lang, {}))
        for lang in SUPPORTED_LANGS
    }
    methods_html = {lang: load_methods_html_lang(lang) for lang in SUPPORTED_LANGS}
    terms_html: dict[str, str] = {}
    terms_updated: dict[str, str] = {}
    tracker_caveats: dict[str, list] = {}
    for lang in SUPPORTED_LANGS:
        html, updated = load_terms_html_lang(lang)
        terms_html[lang] = html
        terms_updated[lang] = updated
        tracker_caveats[lang] = load_tracker_caveats(lang)
    print(f"  i18n: {', '.join(SUPPORTED_LANGS)} "
          f"(methods fr={len(methods_html.get('fr', ''))} chars)")
    return {
        "default": "en",
        "langs": list(SUPPORTED_LANGS),
        "strings": locales,
        "layers": layers_by_lang,
        "phr_context": phr_context,
        "methods_html": methods_html,
        "terms_html": terms_html,
        "terms_updated": terms_updated,
        "tracker_caveats": tracker_caveats,
    }


# ---------------------------------------------------------------------------
# payload assembly
# ---------------------------------------------------------------------------

def load_data_build_info() -> dict | None:
    """Data-repo release tag/URL from build/manifest.json (same tag as GitHub Releases)."""
    if not BUILD_MANIFEST.exists():
        print(f"  NOTE: {BUILD_MANIFEST} not found; data_build omitted from payload")
        return None
    try:
        manifest = json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"  WARNING: could not read {BUILD_MANIFEST.name}: {e}")
        return None
    built_at = manifest.get("built_at")
    commit = manifest.get("commit")
    if not built_at or not commit:
        print(f"  WARNING: {BUILD_MANIFEST.name} missing built_at or commit")
        return None
    date_part = str(built_at).split("T", 1)[0]
    tag = f"build-{date_part}-{commit}"
    url = f"https://github.com/{DATA_REPO}/releases/tag/{tag}"
    print(f"  data_build: {tag}")
    return {
        "repo": DATA_REPO,
        "tag": tag,
        "url": url,
        "built_at": str(built_at),
        "commit": str(commit),
    }


def build_payload() -> dict:
    print(f"BUILD_DIR  = {BUILD_DIR}")
    print(f"DATA_ROOT  = {DATA_ROOT}")

    features, centroids_by_nom = load_features_from_geojson()
    print(f"  loaded {len(features)} zone polygons from {BUILD_GEOJSON.name}")

    # Auto-discover layers from GeoJSON properties
    discovered_layers, field_paths = discover_geojson_layers(BUILD_GEOJSON)
    print(f"  auto-discovered {len(discovered_layers)} layers from GeoJSON")

    zone_data, case_totals = load_metadata(centroids_by_nom, field_paths)
    print(f"  assembled metadata for {len(zone_data)} zones")

    initial_view = None
    if "Bunia" in centroids_by_nom:
        lon, lat = centroids_by_nom["Bunia"]
        initial_view = {"lat": lat, "lon": lon, "zoom": 8}

    # Extra layers (computed fields, matrices, local CSV) go first,
    # then auto-discovered GeoJSON layers. Extra defs override discovery labels
    # for the same flat field (e.g. Flowminder short-trip outflow snapshots).
    extra_layers = [_extra_layer_from_def(defn) for defn in EXTRA_LAYER_DEFS]
    extra_fields = {layer["field"] for layer in extra_layers if layer.get("field")}
    discovered_layers = [
        layer for layer in discovered_layers if layer["field"] not in extra_fields
    ]
    layers = _sort_layers_for_dropdown(extra_layers + discovered_layers)
    for layer in layers:
        if layer.get("label_template"):
            continue
        if "{origin}" in layer.get("label", ""):
            layer["label_template"] = layer["label"]
            layer["label"] = layer["label"].replace("{origin}", TRAVEL_FROM_ZONE)

    phr_context_by_lang = load_public_health_context()
    i18n = build_i18n_payload(layers, phr_context_by_lang)
    methods_html = i18n["methods_html"]["en"]
    print(f"  methods HTML: {len(methods_html)} chars")
    terms_html = i18n["terms_html"]["en"]
    terms_updated = i18n["terms_updated"]["en"]
    print(f"  terms HTML: {len(terms_html)} chars (updated {terms_updated!r})")
    partners = load_partners()
    print(f"  partner logos: {[p['alt'] for p in partners]}")
    # Tracker totals: CSV → GeoJSON national_* (inside compute_global_sitrep_totals).
    sitrep = compute_global_sitrep_totals()
    # Last resort only if CSV and GeoJSON national blocks are both unavailable.
    if sitrep is None:
        sitrep = {
            "global_confirmed_cases":  case_totals.get("confirmed_cases", 0),
            "global_suspected_cases":  case_totals.get("suspected_cases", 0),
            "global_confirmed_deaths": case_totals.get("confirmed_deaths", 0),
            "global_suspected_deaths": case_totals.get("suspected_deaths", 0),
            "global_recovered_cases":  0,
            "global_total_cases":      case_totals.get("confirmed_cases", 0),
            "affected_countries": ["DRC"],
            "affected_country_count": 1,
            "per_country": [{
                "country": "DRC",
                "confirmed_cases":  case_totals.get("confirmed_cases", 0),
                "suspected_cases":  case_totals.get("suspected_cases", 0),
                "confirmed_deaths": case_totals.get("confirmed_deaths", 0),
                "suspected_deaths": case_totals.get("suspected_deaths", 0),
                "recovered_cases":  0,
                "total": case_totals.get("confirmed_cases", 0)
                         + case_totals.get("suspected_cases", 0),
            }],
        }
    totals = {**case_totals, **sitrep}
    ic_model = load_ic_model_estimates()
    tracker_caveats = i18n["tracker_caveats"]["en"]
    print(f"  case totals: confirmed={totals.get('confirmed_cases', 0)}, "
          f"suspected={totals.get('suspected_cases', 0)}, "
          f"affected zones={totals.get('affected_zones', 0)}")
    active_case_markers = build_active_case_markers(zone_data, centroids_by_nom)
    print(f"  active-case markers: {len(active_case_markers)} zones "
          f"(confirmed ≥ 1 from GeoJSON)")
    genome_sequence_markers = build_genome_sequence_markers(zone_data, centroids_by_nom)
    print(f"  genome-sequence markers: {len(genome_sequence_markers)} zones")

    province_boundaries = build_province_boundaries()
    print(f"  province boundaries: {len(province_boundaries['features'])} provinces")

    zone_noms = sorted(zone_data.keys())
    province_names = sorted({
        str((feat.get("properties") or {}).get("province") or "").strip()
        for feat in (province_boundaries.get("features") or [])
        if (feat.get("properties") or {}).get("province")
    })
    onset_trends = load_dashboard_plots(
        zone_noms=zone_noms,
        provinces=province_names,
    )
    invasion_risk = load_invasion_risk_estimates()
    confirmed_timeseries = load_confirmed_cases_timeseries(set(zone_data.keys()))

    asof = detect_asof()
    print(f"  asof: {asof}")
    data_build = load_data_build_info()

    matrix_zones = _read_matrix_zone_order(OSRM_TRAVEL_TIME_CSV)
    if not matrix_zones:
        matrix_zones = sorted(zone_data.keys())
    matrices = load_zone_matrices(matrix_zones)
    print(f"  zone matrices: {len(matrix_zones)} zones, "
          f"{len(matrices['datasets'])} datasets")
    flow_latest, flow_yyyymm = load_flowminder_latest_sparse()
    flow_catalogs = {"flowminder_latest": flow_latest}
    flow_arc_layer = _extra_layer_from_def(FLOW_ARC_LAYER_DEF)
    if flow_yyyymm:
        period = _flowminder_period_labels(flow_yyyymm)
        flow_arc_layer["label"] = period["arcs_en"]
        flow_arc_layer["yyyymm"] = flow_yyyymm
        # Keep EN/FR layer label maps in sync with whichever _YYYYMM is latest.
        for lang, key in (("en", "arcs_en"), ("fr", "arcs_fr")):
            locale = i18n["strings"].setdefault(lang, {})
            labels = locale.setdefault("layer_labels", {})
            labels["flow::od"] = period[key]

    return {
        "asof": asof,
        "travel_from": TRAVEL_FROM_ZONE,
        "matrices": matrices,
        "matrix_default_origin": matrices.get("default_origin", "Mongbwalu"),
        "flow_catalogs": flow_catalogs,
        "flow_arc_layer": flow_arc_layer,
        "flow_arcs_available": bool(flow_catalogs["flowminder_latest"].get("zones")),
        "flow_default_hub": flow_catalogs["flowminder_latest"].get(
            "default_hub", "Mongbwalu"),
        "flowminder_latest_yyyymm": flow_yyyymm,
        "initial_view": initial_view,
        "insp_sitrep_url": latest_insp_url(),
        "data_build": data_build,
        "geometry": {"type": "FeatureCollection", "features": features},
        "zone_data": zone_data,
        "layers": layers,
        "epicenter_noms": list(EPICENTER_SOURCE_NOMS),
        "epicenter_fill": EPICENTER_FILL,
        "projection_mask": {
            "layers": sorted(PROJECTION_MASK_LAYERS),
            "field": PROJECTION_MASK_FIELD,
            "min": PROJECTION_MASK_MIN,
        },
        "methods_html": methods_html,
        "terms_html": terms_html,
        "terms_updated": terms_updated,
        "i18n": i18n,
        "partners": partners,
        "totals": totals,
        "ic_model": ic_model,
        "tracker_caveats": tracker_caveats,
        "active_case_markers": active_case_markers,
        "genome_sequence_markers": genome_sequence_markers,
        "genome_markers_available": bool(genome_sequence_markers),
        "province_boundaries": province_boundaries,
        "onset_trends": onset_trends,
        "invasion_risk": invasion_risk,
        "phr_context": phr_context_by_lang.get("en", {"national": [], "by_nom": {}}),
        "phr_context_by_lang": phr_context_by_lang,
        "confirmed_timeseries": confirmed_timeseries,
    }


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>DRC Ebola Bundibugyo 2026 — interactive dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  html, body { margin:0; padding:0; height:100%; font-family: -apple-system, system-ui, "Segoe UI", Helvetica, Arial, sans-serif; background:#111; color:#eee; }
  :root {
    --view-chrome-height: 52px;
    --epi-panel-width: 50%;
  }
  #map { position:absolute; top:0; right:0; bottom:var(--view-chrome-height); left:0; }
  .panel {
    position:absolute; z-index:1000;
    background:rgba(20,20,20,0.92); color:#f4f4f4;
    padding:12px 14px; border-radius:8px;
    box-shadow:0 2px 10px rgba(0,0,0,0.4);
    font-size:13px; line-height:1.4;
    box-sizing:border-box;
  }
  #controls     {
    top:12px; left:12px;
    width:min(340px, calc(100vw - 24px));
    max-width:min(340px, calc(100vw - 24px));
  }
  #controls .panel-body { min-width:0; }
  #controls select {
    display:block;
    width:100%;
    max-width:100%;
    box-sizing:border-box;
  }
  #zone-search-wrap { position:relative; margin-top:2px; }
  #zone-search-input {
    display:block; width:100%; max-width:100%; box-sizing:border-box;
    background:#222; color:#eee; border:1px solid #444; padding:5px 8px;
    border-radius:4px; font-size:12px;
  }
  #zone-search-input:focus {
    outline:none; border-color:#9b7d4e; box-shadow:0 0 0 1px rgba(155,125,78,0.35);
  }
  #zone-search-results {
    position:absolute; left:0; right:0; top:100%;
    margin-top:2px; max-height:220px; overflow-y:auto;
    background:#1a1a1a; border:1px solid #444; border-radius:4px;
    box-shadow:0 4px 14px rgba(0,0,0,0.45); z-index:1100;
  }
  #zone-search-results[hidden] { display:none !important; }
  .zone-search-option {
    display:block; width:100%; text-align:left;
    background:transparent; color:#eee; border:none; border-bottom:1px solid #2a2a2a;
    padding:7px 8px; font-size:12px; cursor:pointer; border-radius:0;
  }
  .zone-search-option:last-child { border-bottom:none; }
  .zone-search-option:hover,
  .zone-search-option.active { background:#2a2a2a; color:#ffd28a; }
  .zone-search-empty {
    padding:8px; font-size:12px; color:#888; font-style:italic;
  }
  #legend       { bottom:calc(var(--view-chrome-height) + 12px); left:12px; max-width:300px; }
  #info         { top:12px; right:12px; max-width:340px; max-height:80vh; overflow-y:auto; }
  #trends {
    display:none;
    top:auto; right:8px;
    bottom:calc(var(--view-chrome-height) + 12px);
    /* Match the former province-selected panel size for every scope. */
    width:min(480px, calc(100vw - 16px));
    max-width:min(480px, calc(100vw - 16px));
    max-height:min(78vh, calc(100vh - 200px));
    overflow-y:auto;
    box-sizing:border-box;
  }
  @media (min-width: 1024px) {
    #trends {
      width:min(720px, calc(100vw - 24px));
      max-width:min(720px, calc(100vw - 24px));
    }
  }
  @media (min-width: 1400px) {
    #trends {
      width:min(760px, calc(100vw - 24px));
      max-width:min(760px, calc(100vw - 24px));
    }
  }
  #trends-controls {
    display:none;
    top:12px; right:12px;
    width:min(320px, calc(100vw - 24px));
    max-width:min(320px, calc(100vw - 24px));
    max-height:80vh;
    overflow-y:auto;
  }
  body.view-trends #controls,
  body.view-trends #legend,
  body.view-trends #info { display:none !important; }
  body.view-trends #trends { display:block; }
  body.view-trends #trends-controls { display:block; }
  body.view-epi-trends #controls,
  body.view-epi-trends #legend,
  body.view-epi-trends #info,
  body.view-epi-trends #trends,
  body.view-epi-trends #trends-controls,
  body.view-epi-trends #trends-legend,
  body.view-epi-trends #context,
  body.view-epi-trends #context-national { display:none !important; }
  body.view-epi-trends #map {
    right: var(--epi-panel-width);
  }
  /* Keep title centred in the map half. */
  body.view-epi-trends #title {
    left: calc((100% - var(--epi-panel-width)) / 2);
    transform: translateX(-50%);
    min-width: unset;
    max-width: min(520px, calc(100% - var(--epi-panel-width) - 24px));
    width: max-content;
  }
  #epi-trends-panel {
    display:none;
    position:absolute; z-index:1000;
    top:0; right:0; bottom:var(--view-chrome-height);
    width:var(--epi-panel-width);
    background:#ffffff; color:#2a2a27;
    border-left:1px solid #e7e3db;
    box-shadow:-2px 0 12px rgba(42,42,39,0.06);
    box-sizing:border-box;
    padding:12px 14px 16px;
    overflow:auto;
    font-size:13px; line-height:1.4;
  }
  #epi-split-handle {
    display:none;
    position:absolute;
    top:0;
    right:var(--epi-panel-width);
    bottom:var(--view-chrome-height);
    width:10px;
    margin-right:-5px;
    z-index:1200;
    cursor:col-resize;
    touch-action:none;
    background:transparent;
  }
  #epi-split-handle::before {
    content:"";
    position:absolute;
    top:0; bottom:0;
    left:50%;
    width:2px;
    transform:translateX(-50%);
    background:#d8d3c9;
    transition:background .12s ease, width .12s ease;
  }
  #epi-split-handle:hover::before,
  body.epi-splitting #epi-split-handle::before {
    width:3px;
    background:#9b7d4e;
  }
  body.view-epi-trends #epi-split-handle { display:block; }
  body.epi-splitting { cursor:col-resize; user-select:none; }
  body.epi-splitting #map,
  body.epi-splitting #epi-trends-panel { pointer-events:none; }
  body.view-epi-trends #epi-trends-panel { display:flex; flex-direction:column; gap:8px; }
  body.view-trends #epi-trends-panel,
  body.view-trends #epi-split-handle,
  body.view-trends #epi-trends-legend,
  body.view-trends #epi-float { display:none !important; }
  #trends-controls.collapsed #trends-controls-body { display:none; }
  #trends-controls .trends-controls {
    display:flex; flex-direction:column; gap:8px;
  }
  #trends-controls .trends-controls label {
    display:flex; flex-direction:column; gap:3px; font-size:11px; color:#bbb; margin:0;
  }
  #trends-controls select,
  #trends-controls input[type="search"] {
    background:#222; color:#eee; border:1px solid #444; border-radius:4px;
    padding:6px 8px; font-size:12px; width:100%; box-sizing:border-box;
  }
  #trends-controls select:focus,
  #trends-controls input[type="search"]:focus {
    outline:none; border-color:#9b7d4e; box-shadow:0 0 0 1px rgba(155,125,78,0.35);
  }
  #trends-search-wrap { position:relative; }
  /* In-flow results so the Scope panel grows (absolute dropdowns were clipped
     by #trends-controls { overflow-y:auto }). Tall enough for ≥5 hits. */
  #trends-search-results {
    display:none;
    position:static;
    margin-top:6px;
    max-height:calc(5 * 32px);
    overflow-y:auto;
    background:#1a1a1a; border:1px solid #444; border-radius:4px;
  }
  #trends-search-results.open { display:block; }
  #trends-search-results button {
    display:block; width:100%; text-align:left; border:none; border-bottom:1px solid #2a2a2a;
    background:#1a1a1a; color:#eee; padding:7px 8px; font-size:12px; line-height:1.35;
    min-height:32px; box-sizing:border-box; cursor:pointer;
  }
  #trends-search-results button:hover,
  #trends-search-results button.active { background:#2a2a2a; color:#ffd28a; }
  #trends-search-results .zone-search-empty {
    padding:8px; font-size:12px; color:#888; font-style:italic;
  }
  #trends-lab-list {
    display:none; max-height:160px; overflow:auto;
    border:1px solid #444; border-radius:4px; background:#1a1a1a;
  }
  #trends-lab-list.visible { display:block; }
  #trends-lab-list button {
    display:block; width:100%; text-align:left; border:none; border-bottom:1px solid #2a2a2a;
    background:#1a1a1a; color:#eee; padding:7px 8px; font-size:12px; cursor:pointer;
  }
  #trends-lab-list button:hover { background:#2a2a2a; }
  #trends-lab-list button.active {
    background:rgba(155,125,78,0.22); color:#ffd28a; font-weight:600;
  }
  #epi-trends-panel h2 {
    margin:0; font-size:14px; color:#2a2a27; font-weight:700;
  }
  #epi-trends-panel .epi-controls {
    display:flex; flex-wrap:nowrap; gap:8px; align-items:flex-end;
  }
  #epi-trends-panel .epi-controls label {
    display:flex; flex-direction:column; gap:3px; font-size:11px; color:#9c968b; margin:0;
    flex:1 1 0; min-width:0;
  }
  #epi-trends-panel select, #epi-trends-panel button.epi-rank-btn {
    background:#ffffff; color:#2a2a27; border:1px solid #e7e3db; border-radius:4px;
    padding:6px 8px; font-size:12px; width:100%;
    box-sizing:border-box;
  }
  #epi-trends-panel button.epi-rank-btn {
    flex:1 1 0; min-width:0; cursor:pointer; font-weight:600;
    white-space:normal; line-height:1.25; height:auto; min-height:34px;
    color:#9b7d4e;
  }
  #epi-trends-panel button.epi-rank-btn:hover {
    background:rgba(155,125,78,0.08); color:#7c1d1d; border-color:#9b7d4e;
  }
  #epi-trends-panel button.epi-rank-btn.active {
    color:#7c1d1d; background:rgba(155,125,78,0.12); border-color:#9b7d4e;
  }
  #epi-trends-table-wrap {
    flex:1 1 auto; overflow:auto; border:1px solid #e7e3db; border-radius:6px;
    min-height:180px; background:#ffffff;
  }
  #epi-trends-table {
    width:100%; border-collapse:collapse; font-size:12px; color:#2a2a27;
  }
  #epi-trends-table th, #epi-trends-table td {
    padding:6px 8px; border-bottom:1px solid #e7e3db; text-align:left;
    white-space:nowrap;
  }
  #epi-trends-table th {
    position:sticky; top:0; background:#faf9f7; color:#9c968b; font-weight:600;
    z-index:1;
  }
  #epi-trends-table tr { cursor:pointer; }
  #epi-trends-table tr:hover td { background:#f3f1ec; }
  #epi-trends-table tr.selected td {
    background:rgba(155,125,78,0.12); color:#7c1d1d;
  }
  #epi-trends-table .num { font-variant-numeric:tabular-nums; text-align:center; }
  #epi-trends-method {
    font-size:11px; color:#9c968b; margin-top:4px; line-height:1.35;
  }
  #epi-trends-method a { color:#7c4a12; text-decoration:underline; }
  #epi-trends-method a:hover { color:#7c1d1d; }
  #epi-trends-subtitle {
    margin:2px 0 0 0; font-size:12px; color:#9c968b; line-height:1.35;
  }
  #epi-trends-downloads {
    display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;
  }
  #epi-trends-downloads button {
    background:#ffffff; color:#2a2a27; border:1px solid #e7e3db; border-radius:4px;
    padding:6px 10px; font-size:12px; cursor:pointer; font-weight:600; color:#9b7d4e;
  }
  #epi-trends-downloads button:hover {
    background:rgba(155,125,78,0.08); color:#7c1d1d; border-color:#9b7d4e;
  }
  body.epi-map-exporting #epi-trends-legend,
  body.epi-map-exporting #epi-float,
  body.epi-map-exporting #epi-split-handle,
  body.epi-map-exporting #epi-trends-panel,
  body.epi-map-exporting #view-switcher,
  body.epi-map-exporting #title,
  body.epi-map-exporting .leaflet-control-container {
    display:none !important;
  }
  /* Full-bleed map framed on DRC for JPG export. */
  body.epi-map-exporting #map {
    right:0 !important;
    bottom:0 !important;
  }
  #epi-trends-legend {
    display:none;
    position:absolute; z-index:1000;
    bottom:calc(var(--view-chrome-height) + 12px); left:12px; max-width:min(340px, calc(100vw - 36px));
    background:#ffffff; color:#2a2a27;
    padding:12px 14px; border-radius:8px;
    border:1px solid #e7e3db;
    box-shadow:0 2px 10px rgba(42,42,39,0.08);
    font-size:13px; line-height:1.4;
  }
  body.view-epi-trends #epi-trends-legend { display:block; }
  #epi-trends-legend .legend-row { margin-top:6px; color:#9c968b; }
  #epi-trends-legend .checkbox-row label { color:#2a2a27 !important; }
  #epi-float {
    display:none;
    position:absolute; z-index:1100;
    min-width:200px; max-width:280px;
    background:#ffffff; color:#2a2a27;
    border:1px solid #e7e3db; border-radius:8px;
    padding:10px 12px; box-shadow:0 4px 16px rgba(42,42,39,0.12);
    font-size:12px; pointer-events:none;
  }
  body.view-epi-trends #epi-float.visible { display:block; }
  #epi-float strong { color:#2a2a27; }
  #epi-float table { width:100%; border-collapse:collapse; margin-top:6px; }
  #epi-float td { padding:2px 0; color:#2a2a27; }
  #epi-float td:first-child { color:#9c968b; }
  #epi-float td:last-child { text-align:right; font-variant-numeric:tabular-nums; }
  #trends-legend {
    position:absolute; z-index:1000;
    bottom:calc(var(--view-chrome-height) + 12px); left:12px; max-width:300px;
    background:rgba(20,20,20,0.92); color:#f4f4f4;
    padding:12px 14px; border-radius:8px;
    box-shadow:0 2px 10px rgba(0,0,0,0.4);
    font-size:13px; line-height:1.4;
    display:none;
  }
  body.view-trends #trends-legend { display:block; }
  #trends-date-slider {
    width:100%; margin-top:4px;
    accent-color:#5b86b3;
    -webkit-appearance:none;
    appearance:none;
    height:6px;
    background:#444;
    border-radius:3px;
    outline:none;
  }
  #trends-date-slider::-webkit-slider-runnable-track {
    height:6px;
    background:#444;
    border-radius:3px;
  }
  #trends-date-slider::-webkit-slider-thumb {
    -webkit-appearance:none;
    appearance:none;
    width:16px;
    height:16px;
    margin-top:-5px;
    border-radius:50%;
    background:#5b86b3;
    border:2px solid #fff;
    box-shadow:0 0 0 1px #5b86b3;
    cursor:pointer;
  }
  #trends-date-slider::-moz-range-track {
    height:6px;
    background:#444;
    border-radius:3px;
  }
  #trends-date-slider::-moz-range-thumb {
    width:16px;
    height:16px;
    border-radius:50%;
    background:#5b86b3;
    border:2px solid #fff;
    box-shadow:0 0 0 1px #5b86b3;
    cursor:pointer;
  }
  #trends-date-label {
    display:block; margin-top:8px; font-size:12px; color:#bbb;
  }
  #trends-time-caption {
    display:block; margin-top:10px; font-size:12px; color:#ddd; line-height:1.35;
  }
  #trends-play-row {
    display:flex; gap:8px; align-items:center; margin-top:8px;
  }
  #trends-play-btn {
    background:#5b86b3; color:#fff; border:1px solid #6f98c0; border-radius:4px;
    padding:5px 10px; font-size:12px; cursor:pointer; font-weight:600;
  }
  #trends-play-btn:hover { background:#4d769f; }
  #trends-play-btn.playing { background:#9b7d4e; border-color:#9b7d4e; }
  #trends-legend-desc {
    font-size:10px; color:#888; line-height:1.35; margin:4px 0 8px 0;
  }
  body.view-trends #imperial-model-estimates,
  body.view-context #imperial-model-estimates,
  body.view-trends .tracker-countries,
  body.view-context .tracker-countries,
  body.view-trends .tracker-footnotes,
  body.view-context .tracker-footnotes { display:none !important; }
  body.view-trends #title,
  body.view-context #title {
    padding:8px 12px;
    min-width:min(420px, calc(100vw - 24px));
  }
  body.view-trends #title h1,
  body.view-context #title h1 { margin-bottom:2px; font-size:clamp(15px, 2.8vw, 20px); }
  body.view-trends #title .sub,
  body.view-context #title .sub { font-size:10px; }
  body.view-trends #tracker,
  body.view-context #tracker {
    margin-top:4px;
    padding-top:4px;
    border-top-width:1px;
  }
  body.view-trends #tracker .global-row,
  body.view-context #tracker .global-row { gap:clamp(12px, 4vw, 28px); }
  body.view-trends #tracker .global-cell .num,
  body.view-context #tracker .global-cell .num { font-size:clamp(18px, 4.5vw, 26px); }
  /* Full-width bottom chrome: tabs centered in remaining space, partners right. */
  #view-switcher {
    position:absolute; left:0; right:0; bottom:0;
    height:var(--view-chrome-height);
    z-index:1100;
    display:grid;
    grid-template-columns:minmax(0, 1fr) auto;
    align-items:center;
    gap:10px;
    box-sizing:border-box;
    padding:6px 10px 6px 12px;
    background:rgba(20,20,20,0.96); color:#f4f4f4;
    border-radius:0;
    border-top:1px solid #333;
    box-shadow:0 -2px 10px rgba(0,0,0,0.35);
  }
  #view-switcher .view-tabs-wrap {
    min-width:0;
    display:flex;
    justify-content:center;
    align-items:center;
  }
  .view-tabs {
    display:flex; justify-content:center; align-items:center;
    flex-wrap:wrap; gap:6px;
  }
  .view-tab {
    background:#222; color:#ccc; border:1px solid #555; border-radius:4px;
    padding:4px 14px; font-size:12px; cursor:pointer; line-height:1.3;
    white-space:nowrap;
  }
  .view-tab:hover { background:#333; color:#eee; }
  .view-tab.active { color:#ffd28a; border-color:#ffae42; background:#2a2418; }
  #view-switcher #partners {
    position:static;
    z-index:auto;
    justify-self:end;
    flex-shrink:0;
    max-width:none;
    margin:0;
    padding:2px 4px;
    background:#ffffff;
    border-radius:4px;
    box-shadow:none;
    display:flex; flex-wrap:nowrap; align-items:center;
    justify-content:center; gap:2px;
  }
  #view-switcher #partners a { display:inline-flex; align-items:center; transition:opacity .15s ease; }
  #view-switcher #partners a:hover { opacity:0.78; }
  #view-switcher #partners img {
    height:clamp(20px, 3.6vmin, 36px); width:auto;
    max-width:min(14vmin, 110px); display:block; object-fit:contain;
  }
  #context-hint,
  #travel-hint,
  #flow-hint,
  #flow-empty-hint {
    position:absolute; z-index:900;
    top:50%; left:50%; transform:translate(-50%, -50%);
    pointer-events:none; color:#aaa;
    font-size:clamp(14px, 2.5vw, 18px);
    text-align:center; padding:14px 22px;
    display:none; align-items:center; justify-content:center;
    background:rgba(20,20,20,0.82);
    border-radius:14px;
    box-shadow:0 2px 10px rgba(0,0,0,0.35);
    max-width:min(420px, calc(100vw - 48px));
    line-height:1.4;
  }
  body.view-map.matrix-layer-active #travel-hint { display:flex; }
  body.view-map.flow-layer-active #flow-hint { display:flex; }
  body.view-map.flow-layer-active.flow-hub-selected #flow-hint { display:none; }
  body.view-map.flow-layer-active.flow-hub-no-data #flow-empty-hint { display:flex; }
  .flow-wing-icon {
    background: transparent !important;
    border: none !important;
  }
  .flow-wing-icon svg {
    display: block;
    overflow: visible;
  }
  #trends-body.trends-empty { color:#888; font-size:12px; }
  #context-national {
    top:12px; left:12px; bottom:auto; right:auto;
    width:min(280px, calc(50vw - 24px));
    max-width:280px;
    max-height:80vh;
    overflow:hidden; display:none;
    flex-direction:column;
    box-sizing:border-box;
  }
  #context {
    top:12px; right:12px; bottom:auto; left:auto;
    width:min(280px, calc(50vw - 24px));
    max-width:280px;
    max-height:80vh;
    overflow:hidden; display:none;
    flex-direction:column;
    box-sizing:border-box;
  }
  body.view-context #controls,
  body.view-context #legend,
  body.view-context #info { display:none !important; }
  body.view-context #context-national,
  body.view-context #context { display:flex; }
  #context-national .panel-header,
  #context .panel-header { flex:0 0 auto; }
  #context-national-body,
  #context-body {
    flex:1 1 auto;
    min-height:0;
    overflow-y:auto;
    -webkit-overflow-scrolling:touch;
  }
  body.view-context #context-hint { display:flex; }
  body.view-context.context-zone-hovered #context-hint { display:none; }
  #context-body.context-empty,
  #context-national-body.context-empty { color:#888; font-size:12px; }
  .context-pillar { margin:0 0 12px 0; padding-left:10px; border-left:3px solid #555; }
  .context-pillar h4 { margin:0 0 4px 0; color:#c4c4c4; }
  .context-pillar .context-meta { font-size:10px; color:#6e6e6e; margin-bottom:4px; }
  .context-pillar .context-meta .scope-tag {
    display:inline-block; margin-right:6px; padding:1px 5px;
    border-radius:3px; background:#2a2a2a; color:#999; text-transform:uppercase;
    letter-spacing:0.4px; font-size:9px;
  }
  .context-pillar p { margin:0; color:#959595; line-height:1.45; font-size:12px; }
  .context-pillar.pillar-epidemiological-coordination { border-left-color:#9fcdfb; }
  .context-pillar.pillar-epidemiological-monitoring { border-left-color:#5dade2; }
  .context-pillar.pillar-epidemiological-management { border-left-color:#ffae42; }
  .context-pillar.pillar-epidemiological-laboratory { border-left-color:#bb8fce; }
  .context-pillar.pillar-epidemiological-infection-prevention-controle { border-left-color:#48c9b0; }
  .context-pillar.pillar-epidemiological-logistics { border-left-color:#e67e22; }
  .context-pillar.pillar-epidemiological-security { border-left-color:#ec7063; }
  .context-pillar.pillar-epidemiological-community-engagement { border-left-color:#58d68d; }
  .context-pillar.pillar-epidemiological-protection-sexual-exploitation-abuse { border-left-color:#c39bd3; }
  .onset-chart-wrap { width:100%; margin-top:4px; }
  .onset-chart-wrap svg { width:100%; max-width:100%; height:auto; display:block; }

    /* Style du header du panneau title */
  #title .panel-header {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
  }

  /* Le titre est centré */
  #title .panel-header h1 {
    margin: 0;
    text-align: center;
    flex: 1;
    font-size: clamp(16px, 3.4vw, 22px);
    font-weight: 700;
    letter-spacing: 0.3px;
  }

  /* Le bouton toggle garde sa taille et ne pousse pas le titre */
  #title .panel-toggle {
    flex-shrink: 0;
    background: transparent;
    color: #ffd28a;
    border: 1px solid #555;
    border-radius: 4px;
    width: 22px;
    height: 22px;
    padding: 0;
    cursor: pointer;
    font-size: 14px;
    line-height: 1;
  }

  #title .panel-toggle:hover {
    background: #333;
    color: #ffae42;
  }

  /* Cacher le contenu quand réduit */
  .panel.collapsed .panel-body {
    display: none;
  }

  /* S'assurer que le header reste visible */
  #title.collapsed .panel-header {
    display: flex !important;
  }

  /* Ajustement pour le titre en mode trends/context */
  body.view-trends #title,
  body.view-context #title {
    padding: 8px 12px;
    min-width: min(420px, calc(100vw - 24px));
  }

  body.view-trends #title h1,
  body.view-context #title h1 {
    margin-bottom: 2px;
    font-size: clamp(15px, 2.8vw, 20px);
  }

  body.view-trends #title .sub,
  body.view-context #title .sub {
    font-size: 10px;
  }

  /* Pour les petits écrans */
  @media (max-width: 700px) {
    #title {
      min-width: unset;
      max-width: calc(100vw - 24px);
      padding: 6px 8px;
    }
    #title h1 {
      margin-bottom: 2px;
    }
    #title .sub {
      font-size: 10px;
    }
    /* Ajuster le gap sur mobile */
    #title .panel-header {
      gap: 8px;
    }
  }
  
  #info-header,
  #trends-controls-header,
  .panel-header { display:flex; align-items:center; justify-content:space-between; gap:8px; }
  #info-toggle,
  .panel-toggle { background:transparent; color:#ffd28a; border:1px solid #555; border-radius:4px;
                  width:22px; height:22px; padding:0; cursor:pointer; font-size:14px; line-height:1; }
  #info-toggle:hover,
  .panel-toggle:hover { background:#333; color:#ffae42; }
  #info.collapsed #info-body,
  .panel.collapsed .panel-body { display:none; }
  @media (max-width: 700px) {
    :root { --view-chrome-height: 72px; }
    .panel          { font-size:12px; padding:6px 8px; }
    #title          { min-width:unset; max-width:calc(100vw - 24px); padding:6px 8px; }
    #view-switcher { padding:4px 8px; gap:6px; }
    .view-tab { padding:3px 9px; font-size:11px; }
    #view-switcher #partners img {
      height:clamp(16px, 4vmin, 26px);
      max-width:min(12vmin, 80px);
    }
    #title h1       { margin-bottom:2px; }
    #title .sub     { font-size:10px; }
    #tracker        { margin-top:4px; padding:4px 2px 0; }
    #tracker .global-row { gap:14px; }
    #tracker .countries-row { gap:2px; margin-top:6px; }
    #tracker .country { gap:3px 6px; }
    #info           { max-width:60vw; }
    #trends-controls { width:min(280px, calc(100vw - 24px)); max-width:min(280px, calc(100vw - 24px));
                       top:clamp(150px, 28vh, 240px); }
    #trends         { width:min(520px, calc(100vw - 12px)); max-width:min(520px, calc(100vw - 12px));
                      right:6px;
                      bottom:calc(var(--view-chrome-height) + 8px); }
    body.view-context #context-national {
      top:clamp(128px, 24vh, 200px);
      left:6px; bottom:auto;
      width:min(260px, calc(50vw - 12px));
      max-width:min(260px, 46vw);
    }
    body.view-context #context {
      top:clamp(128px, 24vh, 200px);
      right:6px; bottom:auto;
      width:min(260px, calc(50vw - 12px));
      max-width:min(260px, 46vw);
    }
    #legend         { max-width:60vw; }
    #controls       { top:clamp(150px, 28vh, 240px); }
    #info           { top:clamp(150px, 28vh, 240px); }
  }
  @media (max-height: 500px) {
    .panel          { font-size:11px; padding:5px 7px; }
    #title          { padding:4px 8px; }
    #title h1       { font-size:clamp(14px, 4vh, 18px); margin-bottom:1px; letter-spacing:0.2px; }
    #title .sub     { font-size:9px; }
    #title .link-btn { padding:1px 6px; font-size:10px; }
    #tracker        { margin-top:2px; padding:3px 2px 0; }
    #tracker .global-title { font-size:9px; margin-bottom:0; }
    #tracker .global-row { gap:clamp(8px, 3vh, 16px); }
    #tracker .global-cell .num { font-size:clamp(16px, 4.5vh, 22px); }
    #tracker .global-cell .sub { font-size:9px; margin-top:0; }
    #tracker .countries-row { margin-top:3px; font-size:10px; gap:1px; }
    #info           { max-height:70vh; }
    #legend         { max-height:60vh; bottom:calc(var(--view-chrome-height) + 8px); }
    #trends         { max-height:min(55vh, calc(100vh - 180px)); }
    body.view-context #context-national { max-height:min(28vh, calc(50vh - 80px)); }
    body.view-context #context { max-height:min(55vh, calc(100vh - 200px)); }
    :root { --view-chrome-height: 58px; }
    #view-switcher { padding:4px 8px; gap:6px; }
    #view-switcher #partners { padding:1px 2px; gap:1px; }
    #view-switcher #partners img {
      max-height:clamp(16px, 4vh, 24px); height:clamp(16px, 4vh, 24px);
      max-width:min(12vmin, 72px);
    }
    .view-tab { padding:3px 8px; font-size:11px; }
  }
  #title        { top:12px; left:50%; transform:translateX(-50%); text-align:center; min-width:min(520px, calc(100vw - 24px)); max-width:calc(100vw - 24px); box-sizing:border-box; }
  #title .title-row { display:flex; align-items:center; justify-content:center; gap:14px; }
  /* Tracker stack (all rows centered relative to the panel). */
  #tracker { display:flex; flex-direction:column; align-items:center; margin-top:6px; padding:6px 4px 0; border-top:1px solid #333; }
  #tracker .stats-block  { display:flex; flex-direction:column; align-items:center; }
  #tracker .global-title { font-size:clamp(9px, 1.5vw, 10px); color:#bbb; text-transform:uppercase; letter-spacing:0.6px; margin-bottom:2px; text-align:center; }
  #tracker .global-row { display:flex; align-items:flex-end; gap:clamp(14px, 6vw, 36px); line-height:1.05; }
  #tracker .global-cell { display:flex; flex-direction:column; align-items:center; }
  #tracker .global-cell .num { font-size:clamp(20px, 6vw, 30px); font-weight:700; font-variant-numeric: tabular-nums; line-height:1; }
  #tracker .global-cell .sub { font-size:clamp(9px, 1.5vw, 10px); color:#bbb; text-transform:uppercase; letter-spacing:0.6px; margin-top:2px; }
  #tracker .global-cell.cases  .num { color:#ffd166; }
  #tracker .global-cell.deaths .num { color:#ff4d4d; }
  #tracker .global-cell.recovered .num { color:#8CD790; }
  #tracker .countries-row { display:flex; flex-direction:column; align-items:center; gap:3px; margin-top:8px; font-size:clamp(10px, 1.6vw, 11px); color:#ddd; }
  #tracker .country { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 8px; justify-content:center; }
  #tracker .country .name { color:#9fcdfb; font-weight:600; }
  #tracker .country .nums { font-variant-numeric: tabular-nums; }
  #tracker .country .conf   { color:#ff6b6b; font-weight:600; }
  #tracker .country .susp   { color:#ffae42; font-weight:600; }
  #tracker .country .conf-d { color:#c97a8a; font-weight:600; }
  #tracker .country .susp-d { color:#caa385; font-weight:600; }
  #tracker .country .dot { color:#444; }
  #tracker .country .sub { font-size:10px; color:#888; }
  #tracker .caveat-mark { font-size:0.85em; color:#ffae42; font-weight:700; margin-left:1px; vertical-align:super; line-height:0; }
  #tracker .tracker-footnotes { margin-top:8px; max-width:min(480px, 92vw); font-size:10px; color:#aaa; line-height:1.4; text-align:left; }
  #tracker .tracker-footnotes p { margin:0 0 4px; }
  #tracker .tracker-footnotes p:last-child { margin-bottom:0; }
  #tracker .tracker-footnotes .mark { color:#ffae42; font-weight:700; margin-right:3px; }
  #imperial-model-estimates {
    margin-top:6px;
    font-size:11px;
    color:#bbb;
    line-height:1.35;
    text-align:center;
  }
  #imperial-model-estimates .note-wrap {
    display:inline-flex;
    align-items:center;
    justify-content:center;
    gap:6px;
    flex-wrap:wrap;
  }
  #imperial-model-estimates .info-wrap { position:relative; display:inline-flex; align-items:center; }
  #imperial-model-estimates .info-icon {
    width:16px; height:16px; border-radius:50%;
    border:1px solid #666; background:#222; color:#ffd28a;
    font-size:11px; font-weight:700; line-height:1;
    display:inline-flex; align-items:center; justify-content:center;
    padding:0; cursor:help;
  }
  #imperial-model-estimates .info-icon:hover,
  #imperial-model-estimates .info-icon:focus-visible {
    border-color:#ffae42; color:#ffae42; outline:none;
  }
  #imperial-model-estimates .info-tooltip {
    display:none;
    position:absolute;
    left:50%;
    top:calc(100% + 6px);
    transform:translateX(-50%);
    width:max-content;
    max-width:min(280px, 70vw);
    background:#1f1f1f;
    border:1px solid #444;
    border-radius:6px;
    padding:8px 10px;
    box-shadow:0 4px 16px rgba(0,0,0,0.45);
    color:#ddd;
    font-size:10px;
    line-height:1.4;
    z-index:1200;
  }
  #imperial-model-estimates .info-tooltip a {
    color:#9fcdfb; text-decoration:underline;
  }
  #imperial-model-estimates .info-tooltip a:hover { color:#ffae42; }
  #imperial-model-estimates .info-wrap:hover .info-tooltip,
  #imperial-model-estimates .info-wrap:focus-within .info-tooltip { display:block; }
  #title h1 { margin:0 0 4px 0; font-size:clamp(16px, 3.4vw, 22px); font-weight:700; letter-spacing:0.3px; }
  #title .sub { font-size:11px; opacity:0.8; }
  #lang-switcher {
    display:flex; justify-content:center;
    margin-top:6px; margin-bottom:14px;
  }
  .lang-toggle-track {
    position:relative;
    display:inline-grid;
    grid-template-columns:1fr 1fr;
    align-items:stretch;
    background:#9b7d4e;
    border:1px solid #9b7d4e;
    border-radius:999px;
    padding:2px;
    min-width:92px;
    box-shadow:inset 0 1px 2px rgba(0,0,0,0.15);
  }
  .lang-toggle-thumb {
    position:absolute;
    top:2px; bottom:2px; left:2px;
    width:calc(50% - 2px);
    border-radius:999px;
    background:#e7e3db;
    border:none;
    box-shadow:0 1px 3px rgba(0,0,0,0.2);
    transition:transform 0.22s ease;
    pointer-events:none;
    z-index:0;
  }
  #lang-switcher.lang-fr .lang-toggle-thumb {
    transform:translateX(100%);
  }
  select, button { background:#222; color:#eee; border:1px solid #444; padding:4px 6px; border-radius:4px; font-size:12px; box-sizing:border-box; }
  #lang-switcher .lang-btn {
    position:relative; z-index:1;
    border:none !important; border-radius:999px; box-sizing:border-box;
    padding:4px 16px; font-size:11px; font-weight:600;
    cursor:pointer; line-height:1.3; letter-spacing:0.4px;
    min-width:44px;
  }
  #lang-switcher .lang-btn:not(.active) {
    color:#e7e3db !important;
    background:#9b7d4e !important;
  }
  #lang-switcher .lang-btn:not(.active):hover {
    color:#fff !important;
    background:#9b7d4e !important;
  }
  #lang-switcher .lang-btn.active {
    color:#9b7d4e !important;
    background:transparent !important;
  }
  #lang-switcher .lang-btn.active:hover {
    color:#9b7d4e !important;
    background:transparent !important;
  }
  select { max-width:100%; }
  label { display:block; margin-top:6px; font-size:12px; color:#bbb; }
  .swatch { display:inline-block; width:18px; height:12px; margin-right:6px; vertical-align:middle; border:1px solid #444; }
  .swatch-no-data { background:transparent !important; border:1px dashed #888; }
  .legend-bar { display:block; width:240px; height:12px; }
  .legend-ticks { display:flex; justify-content:space-between; font-size:10px; color:#aaa; width:240px; margin-top:2px; }
  .legend-ticks span { display:inline-block; white-space:nowrap; }
  .legend-ticks span:nth-child(1) { text-align:left;   flex:1; }
  .legend-ticks span:nth-child(2) { text-align:center; flex:1; }
  .legend-ticks span:nth-child(3) { text-align:right;  flex:1; }
  .legend-scale { font-size:10px; color:#888; margin-top:2px; }
  table { border-collapse:collapse; font-size:12px; width:100%; }
  table td { padding:2px 6px; vertical-align:top; }
  table td:first-child { color:#aaa; white-space:nowrap; }
  .info-empty { color:#888; font-style:italic; }
  .footer { font-size:10px; color:#888; margin-top:8px; }
  .checkbox-row { display:flex; align-items:center; margin-top:6px; gap:6px; }
  .case-icon { width:14px; height:14px; border-radius:50%; background:rgba(91,134,179,0.85); border:1.5px solid #fff; box-shadow:0 0 6px rgba(91,134,179,0.45); }
  .genome-icon { border-radius:50%; background:rgba(91,134,179,0.42); border:1.5px solid rgba(255,255,255,0.75); box-shadow:0 0 4px rgba(91,134,179,0.25); box-sizing:border-box; }
  /* Trends / Context: marker dots must not steal pointer events from the map. */
  body.view-trends .leaflet-marker-pane .leaflet-marker-icon,
  body.view-context .leaflet-marker-pane .leaflet-marker-icon { pointer-events: none !important; }
  h4 { margin: 8px 0 2px 0; font-size: 12px; color: #ffd28a; font-weight: 600; }
  .link-btn {
    display:inline-block; margin-top:4px; padding:2px 8px;
    background:#222; color:#ffd28a; text-decoration:none;
    border:1px solid #555; border-radius:4px; font-size:11px;
    cursor:pointer;
  }
  .link-btn:hover { background:#333; color:#ffae42; border-color:#ffae42; }
  .modal {
    display:none; position:fixed; z-index:5000;
    top:0; left:0; right:0; bottom:0;
    background:rgba(0,0,0,0.6);
    align-items:flex-start; justify-content:center;
    padding:40px 20px; overflow-y:auto;
  }
  .modal.open { display:flex; }
  .modal .sheet {
    background:#1a1a1a; color:#eee;
    max-width:780px; width:100%;
    padding:28px 32px; border-radius:8px;
    box-shadow:0 6px 24px rgba(0,0,0,0.6);
    line-height:1.55; font-size:14px;
  }
  .modal .close {
    float:right; cursor:pointer; font-size:18px; color:#aaa;
    background:none; border:none; padding:0;
  }
  .modal .close:hover { color:#ffae42; }
  .modal h2 { margin:0 0 4px 0; font-size:18px; color:#ffd28a; }
  .modal h3 { margin:18px 0 4px 0; font-size:15px; color:#ffd28a; }
  .modal h4 { margin:12px 0 4px 0; font-size:13px; color:#ffd28a; }
  .modal p, .modal li { margin:6px 0; }
  .modal ul { margin:6px 0 6px 20px; }
  .modal a { color:#9fcdfb; text-decoration:underline; }
  .modal a:hover { color:#ffae42; }
  .modal .methods-table { border-collapse:collapse; margin:10px 0; font-size:12px; width:100%; }
  .modal .methods-table th, .modal .methods-table td {
    border:1px solid #3a3a3a; padding:4px 8px; text-align:left; vertical-align:top;
  }
  .modal .methods-table th { background:#262626; color:#ffd28a; font-weight:600; }
  .modal .methods-table tr:nth-child(even) td { background:#1f1f1f; }
</style>
</head>
<body class="view-map">
<div id="map"></div>
<div id="context-hint" data-i18n="ui.hints.context">Click a health zone to see response context</div>
<div id="travel-hint" data-i18n="ui.hints.travel">Click a health zone to set travel origin (double-click to zoom)</div>
<div id="flow-hint" data-i18n="ui.hints.flow">Click a health zone to show movement flows (double-click to zoom)</div>
<div id="flow-empty-hint" data-i18n="ui.hints.flow_no_data">No movement data available for this health zone.</div>
<div id="title" class="panel">
  <div class="panel-header">
    <h1 id="page-heading" style="margin:0; font-size:clamp(16px, 3.4vw, 22px); font-weight:700; letter-spacing:0.3px;">DRC Ebola Bundibugyo 2026</h1>
    <button class="panel-toggle" data-target="title" type="button" 
            data-i18n-aria="ui.aria.toggle_title" 
            data-i18n-title="ui.aria.collapse_title" 
            aria-label="Toggle title panel" 
            title="Collapse / expand title panel">−</button>
  </div>
  <div class="panel-body">
    <div id="lang-switcher" class="lang-switcher" role="group" aria-label="Language">
      <div class="lang-toggle-track">
        <span class="lang-toggle-thumb" aria-hidden="true"></span>
        <button type="button" class="lang-btn active" data-lang="en" aria-pressed="true">EN</button>
        <button type="button" class="lang-btn" data-lang="fr" aria-pressed="false">FR</button>
      </div>
    </div>
    <div class="sub" id="title-sub"></div>
    <div id="tracker"></div>
    <div class="sub" id="imperial-model-estimates"></div>
    <div style="margin-top:4px">
      <button id="methods-btn" class="link-btn" type="button" data-i18n="ui.methods_btn">Contributors, Data, and Methods</button>
      <button id="terms-btn"   class="link-btn" type="button" data-i18n="ui.terms_btn">Terms of Use</button>
    </div>
  </div>
</div>
</div>
<div id="methods-modal" class="modal" role="dialog" aria-label="Contributors, Data, and Methods" aria-modal="true">
  <div class="sheet">
    <button class="close" id="methods-close" aria-label="Close">✕</button>
    <h2 id="methods-modal-title" data-i18n="ui.methods_modal_title">Contributors, Data, and Methods</h2>
    <div id="methods-content"></div>
  </div>
</div>
<div id="terms-modal" class="modal" role="dialog" aria-label="Terms of Use" aria-modal="true">
  <div class="sheet">
    <button class="close" id="terms-close" aria-label="Close">✕</button>
    <h2 id="terms-modal-title" data-i18n="ui.terms_modal_title">Terms of Use</h2>
    <div id="terms-updated" style="font-size:11px;color:#888;margin-bottom:10px"></div>
    <div id="terms-content"></div>
  </div>
</div>
<div id="controls" class="panel">
  <div class="panel-header">
    <strong data-i18n="ui.layer">Layer</strong>
    <button class="panel-toggle" data-target="controls" type="button" data-i18n-aria="ui.aria.toggle_layer" data-i18n-title="ui.aria.collapse_layer" aria-label="Toggle layer controls" title="Collapse / expand layer controls">−</button>
  </div>
  <div class="panel-body">
    <label for="zone-search-input" data-i18n="ui.zone_search">Search health zone</label>
    <div id="zone-search-wrap">
      <input type="search" id="zone-search-input" autocomplete="off" spellcheck="false"
             data-i18n-placeholder="ui.zone_search_placeholder"
             placeholder="Type a health zone name…"
             aria-autocomplete="list" aria-controls="zone-search-results" aria-expanded="false" />
      <div id="zone-search-results" role="listbox" hidden></div>
    </div>
    <label for="layer-select" data-i18n="ui.source">Source</label>
    <select id="layer-select"></select>
    <label for="scale-select" data-i18n="ui.color_scale">Color scale</label>
    <select id="scale-select">
      <option value="log" data-i18n="ui.scale_log">log</option>
      <option value="linear" data-i18n="ui.scale_linear">linear</option>
    </select>
    <div class="checkbox-row">
      <input type="checkbox" id="show-cases" />
      <label for="show-cases" style="margin:0;color:#eee" data-i18n="ui.show_cases">Show active-case markers</label>
    </div>
    <div class="checkbox-row" id="show-genomes-row">
      <input type="checkbox" id="show-genomes" />
      <label for="show-genomes" style="margin:0;color:#eee" data-i18n="ui.show_genomes">Show numbers of genome sequences</label>
    </div>
    <div class="checkbox-row" id="show-flow-arcs-row">
      <input type="checkbox" id="show-flow-arcs" />
      <label for="show-flow-arcs" style="margin:0;color:#eee" data-i18n="ui.show_flow_arcs">Show Flowminder in- and out-flow</label>
    </div>
    <div class="footer" id="layer-meta"></div>
  </div>
</div>
<div id="legend" class="panel">
  <div class="panel-header">
    <div id="legend-title"><strong data-i18n="ui.legend">Legend</strong></div>
    <button class="panel-toggle" data-target="legend" type="button" data-i18n-aria="ui.aria.toggle_legend" data-i18n-title="ui.aria.collapse_legend" aria-label="Toggle legend" title="Collapse / expand legend">−</button>
  </div>
  <div class="panel-body">
    <div class="legend-bar" id="legend-bar"></div>
    <div class="legend-ticks" id="legend-ticks"></div>
    <div class="legend-scale" id="legend-scale"></div>
    <div id="legend-gray" style="font-size:11px;color:#bbb;margin-top:4px"></div>
  </div>
</div>
<div id="trends-legend" class="panel">
  <div id="trends-legend-title"><strong data-i18n="ui.trends_confirmed_title">Confirmed cases (cumulative)</strong></div>
  <p id="trends-legend-desc" data-i18n="ui.trends_legend_desc">Transcribed from INSP sitreps. Cases are sometimes revised downwards in consecutive sitreps.</p>
  <div class="legend-bar" id="trends-legend-bar"></div>
  <div class="legend-ticks" id="trends-legend-ticks"></div>
  <div class="legend-scale" id="trends-legend-scale" data-i18n="ui.trends_scale_log">(log scale)</div>
  <div id="trends-time-caption" data-i18n="ui.trends_time_caption">Time representation of health zones reporting cases</div>
  <div id="trends-play-row">
    <button type="button" id="trends-play-btn" data-i18n="ui.trends_play">Play</button>
    <span id="trends-date-label" data-i18n="ui.trends_as_of">As of —</span>
  </div>
  <input type="range" id="trends-date-slider" min="0" max="0" value="0"
         data-i18n-aria="ui.trends_slider_aria" aria-label="SitRep date for confirmed cases map" />
</div>
<div id="info" class="panel">
  <div id="info-header">
    <strong data-i18n="ui.zone">Zone</strong>
    <button id="info-toggle" type="button" data-i18n-aria="ui.aria.toggle_zone" data-i18n-title="ui.aria.collapse_zone" aria-label="Toggle zone details" title="Collapse / expand zone details">−</button>
  </div>
  <div id="info-body" class="info-empty" data-i18n="ui.hover_zone">Hover a health zone.</div>
</div>
<div id="view-switcher">
  <div class="view-tabs-wrap">
    <div id="view-tabs" class="view-tabs">
      <button type="button" class="view-tab active" data-view="map" data-i18n="ui.view_map">Current snapshot</button>
      <button type="button" class="view-tab" data-view="trends" data-i18n="ui.view_trends">Epidemiological trends</button>
      <button type="button" class="view-tab" data-view="epi-trends" data-i18n="ui.view_epi_trends">Spatial risk</button>
      <button type="button" class="view-tab" data-view="context" data-i18n="ui.view_context">Context</button>
    </div>
  </div>
  <div id="partners"></div>
</div>
<div id="epi-split-handle" role="separator" aria-orientation="vertical"
     data-i18n-aria="ui.aria.epi_split" aria-label="Resize map and table panels"
     tabindex="0"></div>
<div id="epi-trends-panel">
  <h2 id="epi-trends-title" data-i18n="ui.epi_trends_title">Health zones ranked by national relative risk of invasion</h2>
  <p id="epi-trends-subtitle"></p>
  <div class="epi-controls">
    <label for="epi-scope-select">
      <span data-i18n="ui.epi_scope">Geographic scope</span>
      <select id="epi-scope-select"></select>
    </label>
    <button type="button" class="epi-rank-btn active" id="epi-rank-rr" data-rank="rr" data-i18n="ui.epi_rank_rr">Rank by relative risk</button>
    <button type="button" class="epi-rank-btn" id="epi-rank-priority" data-rank="priority" data-i18n="ui.epi_rank_priority">Rank by vulnerability-based priority</button>
  </div>
  <div id="epi-trends-table-wrap">
    <table id="epi-trends-table">
      <thead>
        <tr>
          <th data-i18n="ui.epi_col_province">Province</th>
          <th data-i18n="ui.epi_col_zone">Health zone</th>
          <th class="num" data-i18n="ui.epi_col_p_invasion">Invasion probability</th>
          <th class="num" data-i18n="ui.epi_col_p_ci">95% CI</th>
          <th class="num" data-i18n="ui.epi_col_norm_rr">Normalised Relative Risk</th>
          <th class="num" data-i18n="ui.epi_col_rr">Relative risk</th>
          <th class="num" data-i18n="ui.epi_col_rr_rank">Rank</th>
          <th class="num" data-i18n="ui.epi_col_priority">Vulnerability-based priority</th>
          <th class="num" data-i18n="ui.epi_col_priority_rank">Rank of vulnerability-based priority</th>
        </tr>
      </thead>
      <tbody id="epi-trends-tbody"></tbody>
    </table>
  </div>
  <p id="epi-trends-method"></p>
  <div id="epi-trends-downloads">
    <button type="button" id="epi-download-map" data-i18n="ui.epi_download_map">Download map (JPG)</button>
    <button type="button" id="epi-download-csv" data-i18n="ui.epi_download_csv">Download data (CSV)</button>
  </div>
</div>
<div id="epi-trends-legend" class="panel">
  <div><strong data-i18n="ui.epi_map_legend">Map colouring</strong></div>
  <div class="legend-row" id="epi-legend-invasion-label"></div>
  <div class="legend-bar" id="epi-legend-invasion-bar"></div>
  <div class="legend-ticks" id="epi-legend-invasion-ticks"></div>
  <div class="legend-row" style="margin-top:10px" data-i18n="ui.epi_legend_active">Confirmed cases</div>
  <div class="legend-bar" id="epi-legend-cases-bar"></div>
  <div class="legend-ticks" id="epi-legend-cases-ticks"></div>
  <div class="checkbox-row" style="margin-top:10px">
    <input type="checkbox" id="epi-show-cases" />
    <label for="epi-show-cases" style="margin:0" data-i18n="ui.show_cases">Show active-case markers</label>
  </div>
  <div id="epi-flow-legend" style="margin-top:10px;font-size:11px;color:#5c574f;line-height:1.35">
    <div style="margin-bottom:4px">
      <span class="swatch" style="background:#b23b2e"></span>
      <span data-i18n="ui.legend.flow_in">inflow to hub</span>
    </div>
    <div data-i18n="ui.legend.importation_pressure_width">Line width ∝ confirmed cases in the external origin zone (Flowminder inflows only), 0–1 vs max for selected zone</div>
  </div>
</div>
<div id="trends-controls" class="panel">
  <div id="trends-controls-header">
    <strong data-i18n="ui.trends_controls_title">Scope</strong>
    <button class="panel-toggle" data-target="trends-controls" type="button"
            data-i18n-aria="ui.aria.toggle_trends" data-i18n-title="ui.aria.collapse_trends"
            aria-label="Toggle trends scope panel" title="Collapse / expand trends scope">−</button>
  </div>
  <div id="trends-controls-body" class="panel-body">
    <div class="trends-controls">
      <label for="trends-scope-select">
        <span data-i18n="ui.trends_scope">Geographic scope</span>
        <select id="trends-scope-select">
          <option value="national" data-i18n="ui.trends_scope_national">National</option>
          <option value="province" data-i18n="ui.trends_scope_province">Province</option>
          <option value="health_zone" data-i18n="ui.trends_scope_health_zone">Health zone</option>
          <option value="lab" data-i18n="ui.trends_scope_lab">Laboratory</option>
        </select>
      </label>
      <label for="trends-search-input">
        <span data-i18n="ui.trends_search">Search</span>
        <div id="trends-search-wrap">
          <input type="search" id="trends-search-input" autocomplete="off"
                 data-i18n-placeholder="ui.trends_search_placeholder" placeholder="Search…" />
          <div id="trends-search-results" role="listbox"></div>
        </div>
      </label>
    </div>
    <div id="trends-lab-list" aria-label="Laboratories" style="margin-top:8px"></div>
  </div>
</div>
<div id="epi-float" class="panel"></div>
<div id="trends" class="panel">
  <div class="panel-header">
    <strong id="trends-title" data-i18n="ui.trends_panel">Trends</strong>
    <button class="panel-toggle" data-target="trends" type="button"
            data-i18n-aria="ui.aria.toggle_trends" data-i18n-title="ui.aria.collapse_trends"
            aria-label="Toggle trends panel" title="Collapse / expand trends">−</button>
  </div>
  <div id="trends-body" class="panel-body trends-empty"></div>
</div>
<div id="context-national" class="panel">
  <div class="panel-header">
    <strong data-i18n="ui.context_national">National and Provincial Response</strong>
    <button class="panel-toggle" data-target="context-national" type="button" data-i18n-aria="ui.aria.toggle_context_national" data-i18n-title="ui.aria.collapse_context_national" aria-label="Toggle national and provincial context panel" title="Collapse / expand national and provincial context">−</button>
  </div>
  <div id="context-national-body" class="panel-body context-empty"></div>
</div>
<div id="context" class="panel">
  <div class="panel-header">
    <strong id="context-title" data-i18n="ui.context_zone">Health zone context</strong>
    <button class="panel-toggle" data-target="context" type="button" data-i18n-aria="ui.aria.toggle_context_zone" data-i18n-title="ui.aria.collapse_context_zone" aria-label="Toggle health zone context panel" title="Collapse / expand zone context">−</button>
  </div>
  <div id="context-body" class="panel-body context-empty" data-i18n="ui.context_click_zone">Click a health zone on the map.</div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
const PAYLOAD = JSON.parse(document.getElementById("payload").textContent);
const ZONE_DATA = PAYLOAD.zone_data;
const I18N = PAYLOAD.i18n || {};
let LAYERS = PAYLOAD.layers;
const TRAVEL_FROM = PAYLOAD.travel_from || "Mongbwalu";
const MATRICES = PAYLOAD.matrices || {};
const MATRIX_INDEX = {};
(function buildMatrixIndex() {
  (MATRICES.zones || []).forEach(function(nom, i) { MATRIX_INDEX[nom] = i; });
})();
let matrixOriginNom = PAYLOAD.matrix_default_origin || "Mongbwalu";
const FLOW_CATALOGS = PAYLOAD.flow_catalogs || {};
const FLOW_ARC_LAYER = PAYLOAD.flow_arc_layer || null;
let flowHubNom = PAYLOAD.flow_default_hub || "Mongbwalu";
let flowHubUserSelected = !!(PAYLOAD.flow_arcs_available && FLOW_ARC_LAYER);
let flowArcStats = null;
let activeView = "map";
const MATRIX_ORIGIN_FILL = "#5b9bd5";
const FLOW_OUT_COLOR = "#b23b2e";
const FLOW_IN_COLOR = "#5b86b3";
const FLOW_MUTED_FILL = "#e8e4dc";
const EPICENTER_NOMS = new Set(PAYLOAD.epicenter_noms || []);
const EPICENTER_FILL = PAYLOAD.epicenter_fill || "#9b7d4e";
let currentLang = (function resolveLang() {
  const stored = localStorage.getItem("bdbv-dashboard-lang");
  if (stored && I18N.strings && I18N.strings[stored]) return stored;
  const nav = (navigator.language || "").slice(0, 2).toLowerCase();
  if (nav === "fr" && I18N.strings && I18N.strings.fr) return "fr";
  return I18N.default || "en";
})();

function t(path) {
  const parts = String(path).split(".");
  let node = (I18N.strings && I18N.strings[currentLang]) || (I18N.strings && I18N.strings.en) || {};
  for (let i = 0; i < parts.length; i++) {
    if (node == null || typeof node !== "object") return path;
    node = node[parts[i]];
  }
  return node != null ? node : path;
}

function tf(path, vars) {
  let s = String(t(path));
  if (vars) {
    Object.keys(vars).forEach(function(k) {
      s = s.split("{" + k + "}").join(String(vars[k]));
    });
  }
  return s;
}

function localeTag() {
  return currentLang === "fr" ? "fr-FR" : "en-US";
}

function fmtLocale(v) {
  return (v == null ? 0 : v).toLocaleString(localeTag());
}

function trackerCaveats() {
  const byLang = (I18N.tracker_caveats || {})[currentLang];
  if (byLang && byLang.length) return byLang;
  return PAYLOAD.tracker_caveats || [];
}

function layerEpicenterHighlight(layer) {
  return !!(layer && layer.epicenter_highlight);
}
function layerUsesMatrix(layer) {
  return !!(layer && layer.matrix_id);
}
function layerUsesFlowArcs(layer) {
  return !!(layer && layer.viz === "flow_arcs");
}
function flowArcsOverlayActive() {
  if (!FLOW_ARC_LAYER) return false;
  if (activeView === "map") {
    const box = document.getElementById("show-flow-arcs");
    return !!(box && box.checked);
  }
  // Epidemiological trends: same curved Flowminder arcs as snapshot, only while a zone is selected.
  if (activeView === "epi-trends") {
    return !!epiSelectedNom;
  }
  return false;
}
function flowArcLayerDef() {
  return FLOW_ARC_LAYER;
}
function layerOriginHighlight(layer) {
  return !!(layer && layer.origin_highlight);
}
function flowCatalogForLayer(layer) {
  if (!layer || !layer.flow_catalog) return null;
  return FLOW_CATALOGS[layer.flow_catalog] || null;
}
function layerEpicenterNoms(layer) {
  if (layer && layer.epicenter_noms && layer.epicenter_noms.length) {
    return new Set(layer.epicenter_noms);
  }
  return EPICENTER_NOMS;
}
function isEpicenterZone(ref, layer) {
  return layerEpicenterHighlight(layer) && layerEpicenterNoms(layer).has(ref);
}
function isHubZone(ref, layer) {
  if (layerUsesMatrix(layer) && layerOriginHighlight(layer)) {
    return !!(matrixOriginNom && ref === matrixOriginNom);
  }
  return false;
}
function isMatrixOriginZone(ref, layer) {
  return isHubZone(ref, layer);
}
function hubDisplayName(nom) {
  return zoneDisplayName(nom) || TRAVEL_FROM;
}
function matrixOriginDisplayName() {
  return hubDisplayName(matrixOriginNom);
}
function flowHubDisplayName() {
  return hubDisplayName(flowHubNom);
}
function matrixValue(matrixId, originNom, destNom, scaleOverride) {
  const ds = MATRICES.datasets && MATRICES.datasets[matrixId];
  if (!ds || !ds.values) return null;
  const oi = MATRIX_INDEX[originNom];
  const di = MATRIX_INDEX[destNom];
  if (oi == null || di == null) return null;
  const raw = ds.values[oi][di];
  if (raw == null || Number.isNaN(raw)) return null;
  const scale = scaleOverride != null ? scaleOverride : (ds.scale || 1);
  return raw / scale;
}
function applyMatrixOriginToLayers() {
  const origin = matrixOriginDisplayName();
  LAYERS.forEach(function(L) {
    if (!L.label_template) return;
    L.label = L.label_template.split("{origin}").join(origin);
  });
}
function flowHubHasData(nom, layer) {
  const cat = flowCatalogForLayer(layer);
  if (!cat || !nom) return false;
  const outs = (cat.out_by_origin && cat.out_by_origin[nom]) || [];
  const ins = (cat.in_by_dest && cat.in_by_dest[nom]) || [];
  return outs.length > 0 || ins.length > 0;
}
function syncFlowHintPanels() {
  const flowLayer = flowArcLayerDef();
  const flowActive = flowArcsOverlayActive();
  const selected = flowActive && flowHubUserSelected;
  const noData = selected && !flowHubHasData(flowHubNom, flowLayer);
  document.body.classList.toggle("flow-hub-selected", selected);
  document.body.classList.toggle("flow-hub-no-data", noData);
  const emptyHint = document.getElementById("flow-empty-hint");
  if (emptyHint) {
    emptyHint.textContent = noData
      ? tf("ui.hints.flow_no_data", {zone: flowHubDisplayName()})
      : t("ui.hints.flow_no_data");
  }
}
function syncMatrixUi() {
  const layer = getLayer(layerSelect.value);
  const travelActive = !!(layer && layerUsesMatrix(layer) && activeView === "map");
  const flowActive = flowArcsOverlayActive();
  document.body.classList.toggle("matrix-layer-active", travelActive);
  document.body.classList.toggle("flow-layer-active", flowActive);
  if (!flowActive) {
    document.body.classList.remove("flow-hub-selected", "flow-hub-no-data");
  }
  syncFlowHintPanels();
  if (layer && (layerUsesMatrix(layer) || flowActive)) {
    updateLayerMeta(layer);
    updateLegend(layer);
  }
}
function setMatrixOrigin(nom) {
  if (!nom || nom === matrixOriginNom) return;
  matrixOriginNom = nom;
  applyMatrixOriginToLayers();
  rebuildLayerSelect();
  recompute();
  syncMatrixUi();
}
function setFlowHub(nom) {
  if (!nom) return;
  flowHubNom = nom;
  flowHubUserSelected = true;
  recompute();
  syncMatrixUi();
}

function applyStaticI18n() {
  document.documentElement.lang = currentLang;
  document.title = t("meta.title");
  const heading = document.getElementById("page-heading");
  if (heading) heading.textContent = t("meta.heading");
  document.querySelectorAll("[data-i18n]").forEach(function(el) {
    const key = el.getAttribute("data-i18n");
    const val = t(key);
    if (el.id === "info-body" && !el.classList.contains("info-empty")) return;
    if (el.id === "context-body" && contextSelectedNom) return;
    el.textContent = val;
  });
  document.querySelectorAll("[data-i18n-aria]").forEach(function(el) {
    el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
  });
  document.querySelectorAll("[data-i18n-title]").forEach(function(el) {
    el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(function(el) {
    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
  });
  document.querySelectorAll(".lang-btn").forEach(function(btn) {
    const on = btn.dataset.lang === currentLang;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
  const langSwitcher = document.getElementById("lang-switcher");
  if (langSwitcher) langSwitcher.classList.toggle("lang-fr", currentLang === "fr");
  const methodsModal = document.getElementById("methods-modal");
  const termsModal = document.getElementById("terms-modal");
  if (methodsModal) methodsModal.setAttribute("aria-label", t("ui.methods_modal_title"));
  if (termsModal) termsModal.setAttribute("aria-label", t("ui.terms_modal_title"));
}

function updateLegalContent() {
  const methods = (I18N.methods_html || {})[currentLang] || PAYLOAD.methods_html || "";
  const terms = (I18N.terms_html || {})[currentLang] || PAYLOAD.terms_html || "";
  const updated = ((I18N.terms_updated || {})[currentLang]) || PAYLOAD.terms_updated || "";
  document.getElementById("methods-content").innerHTML =
    methods || "<p style='color:#888'>" + t("ui.methods_missing") + "</p>";
  document.getElementById("terms-content").innerHTML =
    terms || "<p style='color:#888'>" + t("ui.terms_missing") + "</p>";
  const termsUpdatedEl = document.getElementById("terms-updated");
  if (termsUpdatedEl) {
    termsUpdatedEl.textContent = updated ? (t("ui.terms_updated") + " " + updated) : "";
  }
}

function buildTitleSub() {
  const linkStyle = "color:#9fcdfb;text-decoration:underline";
  let html =
    t("ui.title_sub.latest") + " " +
    "<a href='" + (PAYLOAD.insp_sitrep_url || "https://insp.cd/") + "' target='_blank' rel='noopener' " +
    "style='" + linkStyle + "'>" + t("ui.title_sub.insp_sitrep") + "</a>" +
    " - " + PAYLOAD.asof;
  const db = PAYLOAD.data_build;
  if (db && db.url && db.tag) {
    html +=
      " · " + t("ui.title_sub.built_on") + " <a href='" + db.url + "' target='_blank' rel='noopener' style='" + linkStyle + "'>" +
       db.tag + "</a>";
  }
  document.getElementById("title-sub").innerHTML = html;
}

function buildTracker() {
  const totals = PAYLOAD.totals || {};
  const tracker = document.getElementById("tracker");
  const caveats = trackerCaveats();
  const caveatByMetric = {};
  caveats.forEach(function(c) { caveatByMetric[c.metric] = c.mark; });
  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function countWithMark(v, metric) {
    const base = fmtLocale(v);
    const mark = caveatByMetric[metric];
    return mark
      ? base + "<span class='caveat-mark' aria-hidden='true'>" + esc(mark) + "</span>"
      : base;
  }
  const tr = t("ui.tracker");
  const per = (totals.per_country || []);
  const countryHTML = per.map(function(c) {
    return "<div class='country'>" +
             "<span class='name'>" + esc(c.country) + "</span>" +
             "<span class='nums'>" +
               "<span class='conf'>"   + countWithMark(c.confirmed_cases,  "confirmed_cases")  + "</span> " + tr.conf + " · " +
               "<span class='susp'>"   + countWithMark(c.suspected_cases,  "suspected_cases")  + "</span> " + tr.susp + " · " +
               "<span class='conf-d'>" + countWithMark(c.confirmed_deaths, "confirmed_deaths") + "</span> " + tr.conf_deaths + " · " +
               "<span class='susp-d'>" + countWithMark(c.suspected_deaths, "suspected_deaths") + "</span> " + tr.susp_deaths +
             "</span>" +
           "</div>";
  }).join("");
  const footnotesHTML = caveats.length
    ? "<div class='tracker-footnotes'>" +
        caveats.map(function(c) {
          return "<p><span class='mark'>" + esc(c.mark) + "</span>" + esc(c.warning) + "</p>";
        }).join("") +
      "</div>"
    : "";
  const globalDeaths = (totals.global_confirmed_deaths || 0);
  const globalRecovered = (totals.global_recovered_cases || 0);
  tracker.innerHTML =
    "<div class='stats-block'>" +
      "<div class='global-title'>" + tr.outbreak_size + "</div>" +
      "<div class='global-row'>" +
        "<div class='global-cell cases'>" +
          "<div class='num'>" + fmtLocale(totals.global_total_cases) + "</div>" +
          "<div class='sub'>" + tr.cases + "</div>" +
        "</div>" +
        "<div class='global-cell deaths'>" +
          "<div class='num'>" + fmtLocale(globalDeaths) + "</div>" +
          "<div class='sub'>" + tr.deaths + "</div>" +
        "</div>" +
        "<div class='global-cell recovered'>" +
          "<div class='num'>" + fmtLocale(globalRecovered) + "</div>" +
          "<div class='sub'>" + tr.recovered + "</div>" +
        "</div>" +
      "</div>" +
    "</div>" +
    "<div class='countries-row tracker-countries'>" + (countryHTML || "<span class='sub'>—</span>") + "</div>" +
    footnotesHTML;
}

function buildModeledEstimateNote() {
  const root = document.getElementById("imperial-model-estimates");
  if (!root) return;
  root.innerHTML = "";
  root.style.display = "none";
}

// --- partners strip ---
(function buildPartners() {
  const partners = PAYLOAD.partners || [];
  const root = document.getElementById("partners");
  if (!partners.length || !root) { if (root) root.style.display="none"; return; }
  root.innerHTML = partners.map(function(p) {
    const img = "<img src='" + p.data_uri + "' alt='" + p.alt + "' title='" + p.alt + "' />";
    return p.href
      ? "<a href='" + p.href + "' target='_blank' rel='noopener'>" + img + "</a>"
      : img;
  }).join("");
})();

const layerSelect = document.getElementById("layer-select");
const scaleSelect = document.getElementById("scale-select");
const layerMeta = document.getElementById("layer-meta");

function rebuildLayerSelect() {
  const selected = layerSelect.value;
  layerSelect.innerHTML = "";
  const groups = {};
  for (const L of LAYERS) {
    if (!groups[L.group]) {
      const og = document.createElement("optgroup");
      og.label = L.group;
      layerSelect.appendChild(og);
      groups[L.group] = og;
    }
    const o = document.createElement("option");
    o.value = L.id; o.textContent = L.label;
    groups[L.group].appendChild(o);
  }
  if (selected && getLayer(selected)) layerSelect.value = selected;
  else if (LAYERS.length) layerSelect.value = LAYERS[0].id;
}

function setLang(lang) {
  if (!I18N.strings || !I18N.strings[lang]) return;
  currentLang = lang;
  localStorage.setItem("bdbv-dashboard-lang", lang);
  LAYERS = (I18N.layers && I18N.layers[lang]) || PAYLOAD.layers;
  applyStaticI18n();
  rebuildLayerSelect();
  buildTitleSub();
  buildTracker();
  buildModeledEstimateNote();
  updateLegalContent();
  applyMatrixOriginToLayers();
  rebuildLayerSelect();
  recompute();
  syncMatrixUi();
  refreshMarkerTooltips();
  if (zoneSearchInput && zoneSearchResults && !zoneSearchResults.hidden) {
    renderZoneSearchResults(zoneSearchInput.value);
  }
  if (activeView === "trends") {
    updateTrendsDateLabel();
    syncTrendsPlayButton();
    renderTrendsPlot();
  } else if (activeView === "context") {
    renderContextPanel(contextSelectedNom);
  } else if (activeView === "epi-trends") {
    updateEpiTitle();
    updateEpiMetaNotes();
    renderEpiLegendBars();
    renderEpiTrendsTable();
  } else {
    const infoBody = document.getElementById("info-body");
    if (infoBody && !infoBody.classList.contains("info-empty")) {
      for (const feat of PAYLOAD.geometry.features) {
        if ((feat.properties.name || "").toLowerCase() === (TRAVEL_FROM || "Mongbwalu").toLowerCase() ||
            (feat.properties.nom || "").toLowerCase() === "mongbalu") {
          infoBody.innerHTML = infoHTML(feat);
          break;
        }
      }
    }
  }
}

document.querySelectorAll(".lang-btn").forEach(function(btn) {
  btn.addEventListener("click", function() { setLang(btn.dataset.lang || "en"); });
});

function getLayer(id) { return LAYERS.find(L => L.id === id); }

// color palettes
const PLASMA = [
  [13,8,135],[75,3,161],[125,3,168],[168,34,150],[203,70,121],
  [229,107,93],[248,148,65],[253,195,40],[240,249,33]];
const REDS = [
  [255,245,235],[254,217,181],[253,173,118],[252,127,73],[239,77,55],
  [205,32,32],[140,17,17]];
// Brand sequential ramp: #f6e3df → #e8b3a6 → #d08163 → #aa4a32 → #7c1d1d
const OUTBREAK = [
  [246,227,223],[232,179,166],[208,129,99],[170,74,50],[124,29,29]];
const VIRIDIS = [
  [68,1,84],[72,40,120],[62,73,137],[49,104,142],[38,130,142],[31,158,137],
  [53,183,121],[109,206,89],[180,222,44],[253,231,37]];
// Darker, subdued purple ramp for invasion probability.
const PURPLES = [
  [236,230,242],[214,201,224],[184,164,201],[150,124,171],[117,90,140],
  [91,68,112],[72,52,90],[55,40,72],[42,30,56]];
const PALETTES = {
  plasma:PLASMA, plasma_r:[...PLASMA].reverse(),
  reds:REDS, outbreak:OUTBREAK, viridis:VIRIDIS, purples:PURPLES,
};

function lerpColor(stops, t) {
  if (t <= 0) return stops[0];
  if (t >= 1) return stops[stops.length - 1];
  const s = t * (stops.length - 1);
  const i = Math.floor(s), f = s - i;
  const a = stops[i], b = stops[i + 1];
  return [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f];
}
function rgb(c) { return "rgb(" + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) + ")"; }

const PROJ_MASK = PAYLOAD.projection_mask || null;
const PROJ_MASK_LAYERS = new Set((PROJ_MASK && PROJ_MASK.layers) || []);

function valueForZone(ref, zone, layer) {
  if (PROJ_MASK && PROJ_MASK_LAYERS.has(layer.id)) {
    const m = zone[PROJ_MASK.field];
    if (m == null || Number.isNaN(m) || Number(m) < PROJ_MASK.min) return null;
  }
  if (layerUsesMatrix(layer)) {
    return matrixValue(layer.matrix_id, matrixOriginNom, ref, layer.matrix_scale);
  }
  const v = zone[layer.field];
  return (v == null || Number.isNaN(v)) ? null : Number(v);
}

// --- map setup ---
const INITIAL_VIEW = PAYLOAD.initial_view || {lat: -2.5, lon: 22.5, zoom: 5};
const map = L.map("map").setView([INITIAL_VIEW.lat, INITIAL_VIEW.lon], INITIAL_VIEW.zoom);
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>, &copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains: "abcd", maxZoom: 19
}).addTo(map);

map.createPane("flow-arcs");
map.getPane("flow-arcs").style.zIndex = "450";
map.createPane("epi-links");
map.getPane("epi-links").style.zIndex = "455";
const flowArcLayer = L.layerGroup();
const epiLinkLayer = L.layerGroup();

function zoneCentroid(nom) {
  const z = ZONE_DATA[nom];
  if (!z || z.centroid_lat == null || z.centroid_lon == null) return null;
  if (!isFinite(z.centroid_lat) || !isFinite(z.centroid_lon)) return null;
  return [z.centroid_lat, z.centroid_lon];
}

function clearFlowArcs() {
  flowArcLayer.clearLayers();
  if (map.hasLayer(flowArcLayer)) map.removeLayer(flowArcLayer);
  flowArcStats = null;
}

function quadraticBezierPoints(lat1, lon1, lat2, lon2, bend) {
  const steps = 24;
  const midLat = (lat1 + lat2) / 2;
  const midLon = (lon1 + lon2) / 2;
  const dlat = lat2 - lat1;
  const dlon = lon2 - lon1;
  const len = Math.sqrt(dlat * dlat + dlon * dlon) || 1;
  const sign = bend >= 0 ? 1 : -1;
  const offset = 0.18 * len * sign;
  // Counterclockwise bow from (lat1,lon1) toward (lat2,lon2) in the map plane.
  const cpLat = midLat + (dlon / len) * offset;
  const cpLon = midLon + (-dlat / len) * offset;
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const u = 1 - t;
    const lat = u * u * lat1 + 2 * u * t * cpLat + t * t * lat2;
    const lon = u * u * lon1 + 2 * u * t * cpLon + t * t * lon2;
    pts.push([lat, lon]);
  }
  return pts;
}

function flowArcWeight(count, maxCount) {
  if (!maxCount || maxCount <= 0) return 1.5;
  return 1 + 4 * Math.sqrt(count / maxCount);
}

function flowArcWeightNormalized(frac) {
  if (frac == null || !isFinite(frac) || frac <= 0) return 1.2;
  return 1 + 4 * Math.max(0, Math.min(1, frac));
}

function zoneConfirmedCases(nom) {
  const z = ZONE_DATA[nom];
  if (!z) return 0;
  const c = Number(z.confirmed_cases);
  return (isFinite(c) && c > 0) ? c : 0;
}

function importationPressure(sourceNom, movers) {
  // Spatial risk: Flowminder inflow edges weighted by confirmed cases in the
  // external (origin) health zone. No movement → no pressure.
  const n = Number(movers);
  if (!isFinite(n) || n <= 0) return 0;
  return zoneConfirmedCases(sourceNom);
}

function addFlowWingMarker(pts, color, opts) {
  opts = opts || {};
  if (!pts || pts.length < 2) return;
  // Place near the destination for inward (import) arrows so they read as
  // pointing into the selected health zone; otherwise mid-arc.
  const frac = opts.nearEnd ? 0.78 : 0.5;
  const midIdx = Math.max(1, Math.min(pts.length - 2, Math.floor((pts.length - 1) * frac)));
  const mid = pts[midIdx];
  const prev = pts[Math.max(0, midIdx - 1)];
  const next = pts[Math.min(pts.length - 1, midIdx + 1)];
  // Screen-space bearing so the chevron follows the drawn path (toward hub
  // for inflow polylines that run origin → selected zone).
  const p0 = map.latLngToLayerPoint(L.latLng(prev[0], prev[1]));
  const p1 = map.latLngToLayerPoint(L.latLng(next[0], next[1]));
  const angle = Math.atan2(p1.y - p0.y, p1.x - p0.x) * 180 / Math.PI;
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" ' +
    'style="transform:rotate(' + angle + 'deg)">' +
    '<line x1="2" y1="3.5" x2="11" y2="8" stroke="' + color + '" stroke-width="1.7" stroke-linecap="round"/>' +
    '<line x1="2" y1="12.5" x2="11" y2="8" stroke="' + color + '" stroke-width="1.7" stroke-linecap="round"/>' +
    '</svg>';
  L.marker([mid[0], mid[1]], {
    icon: L.divIcon({
      className: "flow-wing-icon",
      html: svg,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    }),
    interactive: false,
    pane: "flow-arcs",
  }).addTo(flowArcLayer);
}

function renderFlowArcs(hubNom, layer) {
  clearFlowArcs();
  const cat = flowCatalogForLayer(layer);
  if (!cat || !hubNom) return;
  const hub = zoneCentroid(hubNom);
  if (!hub) return;

  const outs = (cat.out_by_origin && cat.out_by_origin[hubNom]) || [];
  const ins = (cat.in_by_dest && cat.in_by_dest[hubNom]) || [];
  const outSorted = outs.slice().sort(function(a, b) { return b[1] - a[1]; });
  const inSorted = ins.slice().sort(function(a, b) { return b[1] - a[1]; });
  // Spatial risk: only inflows into the selected zone (drawn in red),
  // weighted by confirmed cases in each external origin zone.
  const useImportPressure = activeView === "epi-trends";

  let maxMetric = 0;
  if (useImportPressure) {
    inSorted.forEach(function(p) {
      const m = importationPressure(p[0], p[1]);
      if (m > maxMetric) maxMetric = m;
    });
  } else {
    outSorted.concat(inSorted).forEach(function(p) {
      const m = Number(p[1]) || 0;
      if (m > maxMetric) maxMetric = m;
    });
    if (maxMetric < 1) maxMetric = 1;
  }

  if (!useImportPressure) {
    outSorted.forEach(function(pair) {
      const dest = pair[0];
      const count = pair[1];
      const end = zoneCentroid(dest);
      if (!end) return;
      const pts = quadraticBezierPoints(hub[0], hub[1], end[0], end[1], 1);
      const line = L.polyline(pts, {
        color: FLOW_OUT_COLOR,
        weight: flowArcWeight(count, maxMetric),
        opacity: 0.82,
        pane: "flow-arcs",
      });
      line.bindTooltip(tf("ui.flow_arc_tooltip", {
        from: flowHubDisplayName(),
        to: hubDisplayName(dest),
        count: fmt(count),
      }), {direction: "top", sticky: true});
      line.addTo(flowArcLayer);
      addFlowWingMarker(pts, FLOW_OUT_COLOR);
    });
  }

  inSorted.forEach(function(pair) {
    const origin = pair[0];
    const count = pair[1];
    const start = zoneCentroid(origin);
    if (!start) return;
    const cases = zoneConfirmedCases(origin);
    const pressure = useImportPressure ? importationPressure(origin, count) : count;
    const weight = useImportPressure
      ? flowArcWeightNormalized(maxMetric > 0 ? pressure / maxMetric : 0)
      : flowArcWeight(count, maxMetric);
    const color = useImportPressure ? FLOW_OUT_COLOR : FLOW_IN_COLOR;
    // Always draw origin → selected hub so chevrons point inward.
    const pts = quadraticBezierPoints(start[0], start[1], hub[0], hub[1], 1);
    const line = L.polyline(pts, {
      color: color,
      weight: weight,
      opacity: 0.82,
      pane: "flow-arcs",
    });
    if (useImportPressure) {
      line.bindTooltip(tf("ui.importation_pressure_tooltip", {
        from: hubDisplayName(origin),
        to: flowHubDisplayName(),
        pressure: (maxMetric > 0 ? pressure / maxMetric : 0).toFixed(3),
        cases: fmt(cases),
        count: fmt(count),
      }), {direction: "top", sticky: true});
    } else {
      line.bindTooltip(tf("ui.flow_arc_tooltip", {
        from: hubDisplayName(origin),
        to: flowHubDisplayName(),
        count: fmt(count),
      }), {direction: "top", sticky: true});
    }
    line.addTo(flowArcLayer);
    addFlowWingMarker(pts, color, useImportPressure ? {nearEnd: true} : null);
  });

  flowArcStats = {
    outTotal: outs.length,
    outShown: useImportPressure ? 0 : outSorted.length,
    inTotal: ins.length,
    inShown: inSorted.length,
    metric: useImportPressure ? "importation_pressure" : "persons",
    maxMetric: maxMetric,
  };
  flowArcLayer.addTo(map);
}

// --- Epidemiological trends (invasion risk) ---
const INVASION_RISK = PAYLOAD.invasion_risk || null;
const INVASION_ZONES = (INVASION_RISK && INVASION_RISK.zones) || {};
const INVASION_SCOPES = (INVASION_RISK && INVASION_RISK.scopes) || [];
let epiScopeId = "national";
let epiRankMode = "rr"; // "rr" | "priority"
let epiSelectedNom = null;
let epiFocusNoms = null; // Set of noms to keep vivid when a zone is selected
let epiInvasionDomain = {min: 0, max: 1, palette: PURPLES};
let epiCasesDomain = {min: 0, max: 1, isLog: true, palette: REDS};

function clearEpiLinks() {
  epiLinkLayer.clearLayers();
  if (map.hasLayer(epiLinkLayer)) map.removeLayer(epiLinkLayer);
}

function renderEpiStraightLinks(hubNom) {
  clearEpiLinks();
  if (!hubNom) return;
  const hub = zoneCentroid(hubNom);
  if (!hub) return;
  const cat = flowCatalogForLayer(FLOW_ARC_LAYER);
  if (!cat) return;

  const edges = [];
  const outs = (cat.out_by_origin && cat.out_by_origin[hubNom]) || [];
  const ins = (cat.in_by_dest && cat.in_by_dest[hubNom]) || [];
  outs.forEach(function(pair) {
    if (pair && pair[0] && Number(pair[1]) > 0) edges.push({nom: pair[0], count: Number(pair[1]), dir: "out"});
  });
  ins.forEach(function(pair) {
    if (pair && pair[0] && Number(pair[1]) > 0) edges.push({nom: pair[0], count: Number(pair[1]), dir: "in"});
  });
  if (!edges.length) return;

  let maxCount = 1;
  edges.forEach(function(e) { if (e.count > maxCount) maxCount = e.count; });

  edges.forEach(function(e) {
    const end = zoneCentroid(e.nom);
    if (!end) return;
    const color = e.dir === "out" ? FLOW_OUT_COLOR : FLOW_IN_COLOR;
    const line = L.polyline([hub, end], {
      color: color,
      weight: 1.2 + 3.5 * Math.sqrt(e.count / maxCount),
      opacity: 0.85,
      pane: "epi-links",
      interactive: false,
    });
    line.bindTooltip(tf("ui.flow_arc_tooltip", {
      from: e.dir === "out" ? hubDisplayName(hubNom) : hubDisplayName(e.nom),
      to: e.dir === "out" ? hubDisplayName(e.nom) : hubDisplayName(hubNom),
      count: fmt(e.count),
    }), {direction: "top", sticky: true});
    line.addTo(epiLinkLayer);
  });
  epiLinkLayer.addTo(map);
}

function epiCurrentScope() {
  return INVASION_SCOPES.find(function(s) { return s.id === epiScopeId; }) || INVASION_SCOPES[0] || null;
}

function epiZoneVisible(row) {
  const scope = epiCurrentScope();
  if (!scope || !scope.province) return true;
  return row && row.province === scope.province;
}

function epiFlowConnectedNoms(hubNom) {
  const out = new Set([hubNom]);
  const layer = FLOW_ARC_LAYER;
  const cat = flowCatalogForLayer(layer);
  if (!cat || !hubNom) return out;
  // Spatial risk focuses on inflows into the selected zone.
  const ins = (cat.in_by_dest && cat.in_by_dest[hubNom]) || [];
  ins.forEach(function(p) { if (p && p[0]) out.add(p[0]); });
  return out;
}

function epiFmtProb(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString(undefined, {minimumFractionDigits: 3, maximumFractionDigits: 3});
}

function epiFmtNum(v, digits) {
  if (v == null || Number.isNaN(v)) return "—";
  if (digits == null) return Number(v).toLocaleString(undefined, {maximumFractionDigits: 2});
  return Number(v).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}

function updateEpiTitle() {
  const el = document.getElementById("epi-trends-title");
  if (!el) return;
  const scope = epiCurrentScope();
  if (!scope || scope.id === "national") {
    el.textContent = t("ui.epi_trends_title");
  } else {
    el.textContent = tf("ui.epi_trends_title_province", {province: scope.label});
  }
}

function epiCapitalizeFirst(text) {
  const s = String(text || "");
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function epiParseIsoDate(iso) {
  if (!iso) return null;
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

function epiOrdinalDay(n) {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return n + "th";
  const rem10 = n % 10;
  if (rem10 === 1) return n + "st";
  if (rem10 === 2) return n + "nd";
  if (rem10 === 3) return n + "rd";
  return n + "th";
}

function epiFormatLongDate(iso) {
  const d = epiParseIsoDate(iso);
  if (!d || Number.isNaN(d.getTime())) return "";
  const monthsEn = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  const monthsFr = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"];
  if (currentLang === "fr") {
    return d.getDate() + " " + monthsFr[d.getMonth()] + " " + d.getFullYear();
  }
  return monthsEn[d.getMonth()] + " " + epiOrdinalDay(d.getDate());
}

function epiForecastEndIso() {
  if (INVASION_RISK && INVASION_RISK.forecast_end_date) {
    return INVASION_RISK.forecast_end_date;
  }
  const cutoff = INVASION_RISK && INVASION_RISK.cutoff_date;
  const weeks = INVASION_RISK && INVASION_RISK.horizon_window;
  const d = epiParseIsoDate(cutoff);
  if (!d || weeks == null || Number.isNaN(Number(weeks))) return null;
  d.setDate(d.getDate() + Math.round(Number(weeks)) * 7);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return yyyy + "-" + mm + "-" + dd;
}

function updateEpiMetaNotes() {
  const sub = document.getElementById("epi-trends-subtitle");
  if (sub) {
    const startIso = INVASION_RISK && INVASION_RISK.cutoff_date;
    const weeksRaw = INVASION_RISK && (
      INVASION_RISK.forecasting_window != null
        ? INVASION_RISK.forecasting_window
        : INVASION_RISK.horizon_window
    );
    const weeks = (weeksRaw == null || Number.isNaN(Number(weeksRaw)))
      ? null
      : Math.round(Number(weeksRaw));
    const endIso = epiForecastEndIso();
    const startLabel = epiFormatLongDate(startIso);
    const endLabel = epiFormatLongDate(endIso);
    if (startLabel && endLabel && weeks != null) {
      sub.textContent = tf("ui.epi_forecast_subtitle", {
        start: startLabel,
        weeks: String(weeks),
        week_unit: weeks === 1 ? t("ui.epi_week_one") : t("ui.epi_week_other"),
        end: endLabel,
      });
    } else {
      sub.textContent = "";
    }
  }
  const methodEl = document.getElementById("epi-trends-method");
  if (!methodEl) return;
  if (!INVASION_RISK) {
    methodEl.textContent = t("ui.epi_no_data");
    return;
  }
  const label = (INVASION_RISK.method_label) || t("ui.epi_method_label");
  const url = INVASION_RISK.method_url || t("ui.epi_method_url");
  const cutoffLabel = epiFormatLongDate(INVASION_RISK.cutoff_date);
  let html = escHtml(t("ui.epi_method_prefix")) + " " +
    "<a href='" + escHtml(url) + "' target='_blank' rel='noopener'>" +
    escHtml(label) + "</a>";
  if (cutoffLabel) {
    html += " · " + escHtml(tf("ui.epi_data_up_to", {date: cutoffLabel}));
  }
  methodEl.innerHTML = html;
}

function renderEpiLegendBars() {
  function fillBar(barId, ticksId, domain, round) {
    const bar = document.getElementById(barId);
    const ticks = document.getElementById(ticksId);
    if (!bar || !ticks) return;
    const stops = [];
    for (let i = 0; i <= 10; i++) {
      const tt = i / 10;
      stops.push(rgb(lerpColor(domain.palette, tt)) + " " + Math.round(tt * 100) + "%");
    }
    bar.style.background = "linear-gradient(to right, " + stops.join(", ") + ")";
    const lo = domain.min, hi = domain.max;
    const mid = domain.isLog ? Math.sqrt(Math.max(lo, 1e-9) * Math.max(hi, 1e-9)) : (lo + hi) / 2;
    ticks.innerHTML =
      "<span>" + fmtLegend(lo, round) + "</span>" +
      "<span>" + fmtLegend(mid, round) + "</span>" +
      "<span>" + fmtLegend(hi, round) + "</span>";
  }
  const invLabel = document.getElementById("epi-legend-invasion-label");
  if (invLabel) {
    const raw = (INVASION_RISK && INVASION_RISK.p_case_invasion_label) ||
      t("ui.epi_p_invasion");
    invLabel.textContent = epiCapitalizeFirst(raw);
  }
  const activeLabel = document.querySelector('#epi-trends-legend [data-i18n="ui.epi_legend_active"]');
  if (activeLabel) {
    activeLabel.textContent = epiCapitalizeFirst(t("ui.epi_legend_active"));
  }
  fillBar("epi-legend-invasion-bar", "epi-legend-invasion-ticks", epiInvasionDomain, 2);
  fillBar("epi-legend-cases-bar", "epi-legend-cases-ticks", epiCasesDomain, "int");
}

function updateEpiFloat(nom, latlng) {
  const box = document.getElementById("epi-float");
  if (!box) return;
  const row = INVASION_ZONES[nom];
  if (!row || !epiZoneVisible(row)) {
    box.classList.remove("visible");
    return;
  }
  const name = zoneDisplayName(nom) || nom;
  box.innerHTML =
    "<strong>" + escHtml(name) + "</strong>" +
    "<table>" +
    "<tr><td>" + escHtml(t("ui.epi_surveillance_gap")) + "</td><td>" + epiFmtNum(row.surveillance_gap, 3) + "</td></tr>" +
    "<tr><td>" + escHtml(t("ui.epi_access_gap")) + "</td><td>" + epiFmtNum(row.access_gap, 3) + "</td></tr>" +
    "<tr><td>" + escHtml(t("ui.epi_social_vuln")) + "</td><td>" + epiFmtNum(row.social_vulnerability, 3) + "</td></tr>" +
    "</table>";
  const c = latlng
    ? [latlng.lat, latlng.lng]
    : zoneCentroid(nom);
  if (c) {
    const pt = map.latLngToContainerPoint(L.latLng(c[0], c[1]));
    const mapEl = map.getContainer();
    const x = Math.min(Math.max(12, pt.x + 14), mapEl.clientWidth - 220);
    const y = Math.min(Math.max(12, pt.y - 20), mapEl.clientHeight - 120);
    box.style.left = x + "px";
    box.style.top = y + "px";
  }
  box.classList.add("visible");
}

function hideEpiFloat() {
  const box = document.getElementById("epi-float");
  if (box) box.classList.remove("visible");
}

function setEpiSelected(nom) {
  if (!nom || !INVASION_ZONES[nom] || !epiZoneVisible(INVASION_ZONES[nom])) {
    epiSelectedNom = null;
    epiFocusNoms = null;
    clearEpiLinks();
    clearFlowArcs();
  } else {
    epiSelectedNom = nom;
    epiFocusNoms = epiFlowConnectedNoms(nom);
    flowHubNom = nom;
    clearEpiLinks();
    renderFlowArcs(nom, flowArcLayerDef());
  }
  renderEpiTrendsTable();
  recomputeEpiTrends();
}

function epiSortedRows() {
  const scope = epiCurrentScope();
  if (!scope) return [];
  const rows = [];
  Object.keys(INVASION_ZONES).forEach(function(nom) {
    const row = INVASION_ZONES[nom];
    if (!epiZoneVisible(row)) return;
    const rr = row[scope.rr];
    const rrRank = row[scope.rank];
    // Province scopes only include zones with a non-null provincial RR when ranking by RR.
    if (scope.province && epiRankMode === "rr" && (rr == null || Number.isNaN(rr))) return;
    rows.push({
      nom: nom,
      row: row,
      rr: rr,
      rrRank: rrRank,
      priority: row.priority,
      priorityRank: row.priority_rank,
    });
  });
  rows.sort(function(a, b) {
    if (epiRankMode === "priority") {
      const pa = a.priorityRank, pb = b.priorityRank;
      if (pa == null && pb == null) return String(a.nom).localeCompare(String(b.nom));
      if (pa == null) return 1;
      if (pb == null) return -1;
      if (pa !== pb) return pa - pb;
      return String(a.nom).localeCompare(String(b.nom));
    }
    const ra = a.rrRank, rb = b.rrRank;
    if (ra == null && rb == null) {
      const va = a.rr, vb = b.rr;
      if (va == null && vb == null) return String(a.nom).localeCompare(String(b.nom));
      if (va == null) return 1;
      if (vb == null) return -1;
      return vb - va;
    }
    if (ra == null) return 1;
    if (rb == null) return -1;
    if (ra !== rb) return ra - rb;
    return String(a.nom).localeCompare(String(b.nom));
  });
  return rows;
}

function epiFmtCi(lo, hi, digits) {
  const a = epiFmtNum(lo, digits);
  const b = epiFmtNum(hi, digits);
  if (a === "—" && b === "—") return "—";
  return a + " - " + b;
}

function renderEpiTrendsTable() {
  const tbody = document.getElementById("epi-trends-tbody");
  if (!tbody) return;
  const rows = epiSortedRows();
  let maxRr = 0;
  rows.forEach(function(item) {
    if (item.rr != null && !Number.isNaN(item.rr) && item.rr > maxRr) maxRr = item.rr;
  });
  tbody.innerHTML = rows.map(function(item) {
    const sel = item.nom === epiSelectedNom ? " selected" : "";
    const norm = (item.rr == null || Number.isNaN(item.rr) || maxRr <= 0)
      ? null
      : (item.rr / maxRr);
    const pInv = item.row.p_case_invasion;
    const pLo = item.row.p_case_lo;
    const pHi = item.row.p_case_hi != null ? item.row.p_case_hi : item.row.p_case_high;
    return "<tr class='" + sel + "' data-nom='" + escHtml(item.nom) + "'>" +
      "<td>" + escHtml(item.row.province || "—") + "</td>" +
      "<td>" + escHtml(zoneDisplayName(item.nom) || item.nom) + "</td>" +
      "<td class='num'>" + epiFmtNum(pInv, 3) + "</td>" +
      "<td class='num'>" + epiFmtCi(pLo, pHi, 3) + "</td>" +
      "<td class='num'>" + epiFmtNum(norm, 3) + "</td>" +
      "<td class='num'>" + epiFmtNum(item.rr, 2) + "</td>" +
      "<td class='num'>" + (item.rrRank == null ? "—" : item.rrRank) + "</td>" +
      "<td class='num'>" + epiFmtNum(item.priority, 3) + "</td>" +
      "<td class='num'>" + (item.priorityRank == null ? "—" : item.priorityRank) + "</td>" +
      "</tr>";
  }).join("");
}

function recomputeEpiTrends() {
  if (!INVASION_RISK) return;
  const invasionVals = [];
  const caseVals = [];
  Object.keys(INVASION_ZONES).forEach(function(nom) {
    const row = INVASION_ZONES[nom];
    if (!epiZoneVisible(row)) return;
    if (row.was_active_before) {
      const z = ZONE_DATA[nom] || {};
      const c = z.confirmed_cases;
      if (c != null && !Number.isNaN(Number(c)) && Number(c) > 0) caseVals.push(Number(c));
    } else if (row.p_case_invasion != null && !Number.isNaN(row.p_case_invasion)) {
      invasionVals.push(row.p_case_invasion);
    }
  });
  if (invasionVals.length) {
    epiInvasionDomain = {
      min: Math.min.apply(null, invasionVals),
      max: Math.max.apply(null, invasionVals),
      palette: PURPLES,
    };
    if (epiInvasionDomain.max === epiInvasionDomain.min) {
      epiInvasionDomain.max = epiInvasionDomain.min + 0.01;
    }
  } else {
    epiInvasionDomain = {min: 0, max: 1, palette: PURPLES};
  }
  if (caseVals.length) {
    const lo = Math.min.apply(null, caseVals);
    const hi = Math.max.apply(null, caseVals);
    epiCasesDomain = {
      min: lo,
      max: hi === lo ? lo * 10 : hi,
      isLog: true,
      palette: REDS,
    };
  } else {
    epiCasesDomain = {min: 1, max: 10, isLog: true, palette: REDS};
  }
  updateEpiTitle();
  updateEpiMetaNotes();
  renderEpiLegendBars();
  renderEpiTrendsTable();
  geoLayer.setStyle(styleFn);
  clearEpiLinks();
  if (flowArcsOverlayActive()) {
    renderFlowArcs(flowHubNom || epiSelectedNom, flowArcLayerDef());
  } else {
    clearFlowArcs();
  }
}

function epiTrendsStyleFn(feature) {
  const ref = feature.properties.nom;
  const row = INVASION_ZONES[ref];
  if (!row || !epiZoneVisible(row)) {
    return {color: "#111", weight: 0.25, fillOpacity: 0.04, fillColor: "#222"};
  }
  let fill = ZERO_FILL;
  let has = false;
  if (row.was_active_before) {
    const z = ZONE_DATA[ref] || {};
    const v = z.confirmed_cases;
    if (v != null && !Number.isNaN(Number(v))) {
      has = true;
      const num = Number(v);
      if (num <= 0) fill = ZERO_FILL;
      else {
        let t = (Math.log(num) - Math.log(epiCasesDomain.min)) /
          (Math.log(epiCasesDomain.max) - Math.log(epiCasesDomain.min) || 1);
        if (!isFinite(t)) t = 0;
        t = Math.max(0, Math.min(1, t));
        fill = rgb(lerpColor(epiCasesDomain.palette, t));
      }
    }
  } else if (row.p_case_invasion != null && !Number.isNaN(row.p_case_invasion)) {
    has = true;
    let t = (row.p_case_invasion - epiInvasionDomain.min) /
      (epiInvasionDomain.max - epiInvasionDomain.min || 1);
    if (!isFinite(t)) t = 0;
    t = Math.max(0, Math.min(1, t));
    fill = rgb(lerpColor(epiInvasionDomain.palette, t));
  }
  if (!has) {
    return {color: "#111", weight: 0.35, fillOpacity: 0};
  }
  let opacity = 0.82;
  let weight = 0.35;
  if (epiSelectedNom) {
    const focus = epiFocusNoms && epiFocusNoms.has(ref);
    if (ref === epiSelectedNom) {
      opacity = 0.95;
      weight = 1.8;
    } else if (focus) {
      opacity = 0.78;
      weight = 0.8;
    } else {
      opacity = 0.12;
    }
  }
  return {
    color: ref === epiSelectedNom ? "#ffae42" : "#111",
    weight: weight,
    fillColor: fill,
    fillOpacity: opacity,
  };
}

function enterEpiTrendsView() {
  if (!INVASION_RISK || !Object.keys(INVASION_ZONES).length) {
    const methodEl = document.getElementById("epi-trends-method");
    if (methodEl) methodEl.textContent = t("ui.epi_no_data");
  }
  hideProvinceOutlines();
  clearContextSelection();
  clearEpiLinks();
  const epiCases = document.getElementById("epi-show-cases");
  if (epiCases && showCasesBox) epiCases.checked = !!showCasesBox.checked;
  if (!epiSelectedNom) {
    flowHubNom = PAYLOAD.flow_default_hub || flowHubNom;
    clearFlowArcs();
  } else {
    flowHubNom = epiSelectedNom;
    renderFlowArcs(epiSelectedNom, flowArcLayerDef());
  }
  updateEpiMetaNotes();
}

function leaveEpiTrendsView() {
  epiSelectedNom = null;
  epiFocusNoms = null;
  hideEpiFloat();
  clearEpiLinks();
  clearFlowArcs();
  document.body.classList.remove("view-epi-trends", "epi-splitting");
}

const ZERO_FILL    = "#c4bfb6";
let currentValues = new Map();
let currentDomain = {min:0, max:1, isLog:true, palette:OUTBREAK};

function recompute() {
  const layer = getLayer(layerSelect.value);
  const highlightEpicenter = layerEpicenterHighlight(layer);
  currentValues.clear();
  const positives = [];
  let lo = Infinity, hi = -Infinity;
  for (const feat of PAYLOAD.geometry.features) {
    const ref = feat.properties.nom;
    const zone = ZONE_DATA[ref];
    if (!zone) continue;
    const v = valueForZone(ref, zone, layer);
    if (v == null || Number.isNaN(v)) {
      if (!highlightEpicenter || !isEpicenterZone(ref, layer)) continue;
      currentValues.set(ref, v);
      continue;
    }
    currentValues.set(ref, v);
    if (highlightEpicenter && isEpicenterZone(ref, layer)) continue;
    if (layerOriginHighlight(layer) && isMatrixOriginZone(ref, layer)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
    if (v > 0) positives.push(v);
  }
  if (!isFinite(lo)) { lo = 0; hi = 1; }
  const useLog = scaleSelect.value === "log" && positives.length > 0;
  let dlo, dhi;
  if (useLog) {
    dlo = Math.min.apply(null, positives);
    dhi = Math.max.apply(null, positives);
    if (dhi === dlo) dhi = dlo * 10;
  } else {
    dlo = Math.min(0, lo);
    dhi = (hi === dlo) ? dlo + 1 : hi;
  }
  currentDomain = {min:dlo, max:dhi, isLog:useLog, palette:PALETTES[layer.palette] || PLASMA};
  geoLayer.setStyle(styleFn);
  if (flowArcsOverlayActive()) {
    renderFlowArcs(flowHubNom, flowArcLayerDef());
  } else {
    clearFlowArcs();
  }
  updateLegend(layer);
  updateLayerMeta(layer);
}

function valueToColor(v, ref, layer) {
  if (isHubZone(ref, layer)) return MATRIX_ORIGIN_FILL;
  if (isEpicenterZone(ref, layer)) return EPICENTER_FILL;
  const d = currentDomain;
  if (d.isLog && v <= 0) return ZERO_FILL;
  let t;
  if (d.isLog) t = (Math.log(v) - Math.log(d.min)) / (Math.log(d.max) - Math.log(d.min));
  else t = (v - d.min) / (d.max - d.min || 1);
  if (!isFinite(t)) t = 0;
  t = Math.max(0, Math.min(1, t));
  return rgb(lerpColor(d.palette, t));
}

function styleFn(feature) {
  if (activeView === "epi-trends") return epiTrendsStyleFn(feature);
  const ref = feature.properties.nom;
  const v = currentValues.get(ref);
  const has = v != null && !Number.isNaN(v);
  const layer = getLayer(layerSelect.value);
  if (isHubZone(ref, layer)) {
    return {
      color: "#111", weight: 1.6,
      fillColor: MATRIX_ORIGIN_FILL,
      fillOpacity: 0.92
    };
  }
  if (isEpicenterZone(ref, layer)) {
    return {
      color: "#111", weight: 0.5,
      fillColor: EPICENTER_FILL,
      fillOpacity: 0.88
    };
  }
  if (!has) {
    return { color: "#111", weight: 0.35, fillOpacity: 0 };
  }
  const isOutbreak = layer && layer.palette === "outbreak";
  const dataOpacity = isOutbreak ? 0.72 : 0.85;
  const mutedOpacity = isOutbreak ? 0.48 : 0.55;
  const isZero = currentDomain.isLog ? v <= 0 : v === 0;
  return {
    color:"#111", weight:0.35,
    fillColor: valueToColor(v, ref, layer),
    fillOpacity: isZero ? mutedOpacity : dataOpacity
  };
}

function fmtLegend(v, round) {
  if (v == null || Number.isNaN(v)) return "—";
  if (typeof v !== "number") return String(v);
  if (round === "int" || round == null) return Math.round(v).toLocaleString();
  var d = Number(round);
  if (!isFinite(d)) return Math.round(v).toLocaleString();
  return v.toLocaleString(undefined, {minimumFractionDigits: d, maximumFractionDigits: d});
}

function fmt(v, kind) {
  if (v == null || Number.isNaN(v)) return "—";
  if (typeof v !== "number") return String(v);
  if (kind === "rel") return v.toFixed(2);
  if (kind === "cal") {
    if (Math.abs(v) < 1) return v.toFixed(1);
    return Math.round(v).toLocaleString();
  }
  return Math.round(v).toLocaleString();
}

function updateLayerMeta(layer) {
  let html = layer.source || "";
  if (layerUsesMatrix(layer)) {
    const originLine = tf("ui.matrix_origin", {origin: matrixOriginDisplayName()});
    html = (html ? html + "<br>" : "") + originLine;
  }
  if (flowArcsOverlayActive()) {
    const flowLayer = flowArcLayerDef();
    const hubLine = tf("ui.flow_hub", {hub: flowHubDisplayName()});
    html = (html ? html + "<br>" : "") + hubLine;
    if (flowArcStats) {
      html += "<br>" + tf("ui.flow_arc_summary", {
        outShown: flowArcStats.outShown,
        outTotal: flowArcStats.outTotal,
        inShown: flowArcStats.inShown,
        inTotal: flowArcStats.inTotal,
      });
    } else {
      const cat = flowCatalogForLayer(flowLayer);
      const hasHub = cat && (
        (cat.out_by_origin && cat.out_by_origin[flowHubNom]) ||
        (cat.in_by_dest && cat.in_by_dest[flowHubNom])
      );
      if (!hasHub) {
        html += "<br>" + t("ui.flow_no_data");
      }
    }
  }
  layerMeta.innerHTML = html;
}

function updateLegend(layer) {
  document.getElementById("legend-title").innerHTML = "<strong>" + layer.label + "</strong>";
  const stops = [];
  const N = 32;
  for (let i = 0; i < N; i++) {
    const t = i / (N - 1);
    stops.push(rgb(lerpColor(currentDomain.palette, t)) + " " + Math.round(t * 100) + "%");
  }
  document.getElementById("legend-bar").style.background = "linear-gradient(to right, " + stops.join(", ") + ")";
  const ticks = document.getElementById("legend-ticks");
  const lo = currentDomain.min, hi = currentDomain.max;
  const mid = currentDomain.isLog ? Math.sqrt(lo * hi) : (lo + hi) / 2;
  var lr = layer.legend_round != null ? layer.legend_round : "int";
  ticks.innerHTML =
    "<span>" + fmtLegend(lo,  lr) + "</span>" +
    "<span>" + fmtLegend(mid, lr) + "</span>" +
    "<span>" + fmtLegend(hi,  lr) + "</span>";
  document.getElementById("legend-scale").textContent =
    layer.legend_caption
      ? layer.legend_caption
      : (currentDomain.isLog ? t("ui.legend.log_scale") : t("ui.legend.linear_scale"));
  var grayParts = [
    "<span class='swatch' style='background:" + ZERO_FILL + "'></span>" + t("ui.legend.zero"),
    "<span class='swatch swatch-no-data'></span>" + t("ui.legend.no_data")
  ];
  if (layerEpicenterHighlight(layer)) {
    grayParts.push(
      "<span class='swatch' style='background:" + EPICENTER_FILL + "'></span>" + t("ui.legend.epicenter")
    );
  }
  if (layerUsesMatrix(layer) && layerOriginHighlight(layer)) {
    grayParts.push(
      "<span class='swatch' style='background:" + MATRIX_ORIGIN_FILL + "'></span>" + t("ui.legend.matrix_origin")
    );
  }
  if (flowArcsOverlayActive()) {
    grayParts.push(
      "<span class='swatch' style='background:" + FLOW_OUT_COLOR + "'></span>" + t("ui.legend.flow_out"),
      "<span class='swatch' style='background:" + FLOW_IN_COLOR + "'></span>" + t("ui.legend.flow_in")
    );
    const scaleEl = document.getElementById("legend-scale");
    scaleEl.textContent = (scaleEl.textContent || "") + " · " + t("ui.legend.flow_width");
  }
  document.getElementById("legend-gray").innerHTML = grayParts.join(" · ");
}

function infoHTML(feature) {
  const ref = feature.properties.nom;
  const z = ZONE_DATA[ref] || {};
  const name = feature.properties.name || t("ui.case_tooltip.unnamed");
  const info = t("ui.info");
  let h = "<div><strong>" + name + "</strong></div>";
  h += "<div style='color:#aaa;font-size:11px;margin-bottom:6px'>" + (ref || "—") + "</div>";

  h += "<h4>" + info.observed_cases + " (" + PAYLOAD.asof + ")</h4>";
  h += "<table>";
  h += "<tr><td>" + info.total + "</td><td>" + fmt(z.total_cases) + "</td></tr>";
  h += "<tr><td>" + info.confirmed + "</td><td>" + fmt(z.confirmed_cases) + "</td></tr>";
  h += "<tr><td>" + info.confirmed_deaths + "</td><td>" + fmt(z.confirmed_deaths) + "</td></tr>";
  h += "<tr><td>" + info.suspected + "</td><td>" + fmt(z.suspected_cases) + "</td></tr>";
  h += "<tr><td>" + info.suspected_deaths + "</td><td>" + fmt(z.suspected_deaths) + "</td></tr>";
  h += "</table>";

  h += "<h4>" + info.population + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.pop_count + "</td><td>" + fmt(z.worldpop__pop_count__pop_count) + "</td></tr>";
  h += "</table>";

  h += "<h4>" + info.health_facilities_grid3 + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.healthsite_count + "</td><td>" + fmt(z.grid3_healthsites__healthsite_count__healthsite_count) + "</td></tr>";
  h += "</table>";

  h += "<h4>" + info.contact_tracing + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.contacts_traced + "</td><td>" + fmt(z.insp_sitrep__cumulative_contacts_traced__cumulative_contacts_traced) + "</td></tr>";
  h += "<tr><td>" + info.contacts_isolated + "</td><td>" + fmt(z.insp_sitrep__cumulative_contacts_isolated__cumulative_contacts_isolated) + "</td></tr>";
  h += "</table>";

  h += "<h4>" + info.testing_capacity + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.pcr_machines + "</td><td>" + fmt(z.testing_capacity__pcr_machines__pcr_machines) + "</td></tr>";
  h += "<tr><td>" + info.pcr_tests + "</td><td>" + fmt(z.testing_capacity__pcr_tests__pcr_tests) + "</td></tr>";
  h += "</table>";

  h += "<h4>" + info.modeled_projection + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.relative_risk + "</td><td>" + fmt(z.relative_risk, "rel") + "</td></tr>";
  h += "</table>";

  h += "<h4>" + info.incoming_mobility + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.displaced_12mo + "</td><td>" + fmt(z.displaced_in_individuals_12mo) + "</td></tr>";
  h += "<tr><td>" + info.flowminder_mar + "</td><td>" + fmt(z.flowminder_in_mar2026) + "</td></tr>";
  h += "<tr><td>" + info.flowminder_apr + "</td><td>" + fmt(z.flowminder_in_202604) + "</td></tr>";
  h += "<tr><td>" + info.flowminder_may + "</td><td>" + fmt(z.flowminder_short_trips__outflow_20260524__outflow_20260524, "cal") + "</td></tr>";
  h += "</table>";

  if (z.genomic_sequence_count) {
    h += "<h4>" + info.genomic_surveillance + "</h4>";
    h += "<table>";
    h += "<tr><td>" + info.genome_sequences + "</td><td>" + fmt(z.genomic_sequence_count) + "</td></tr>";
    h += "</table>";
  }

  h += "<h4>" + tf("ui.info.distance_from", {origin: matrixOriginDisplayName()}) + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.travel_time_h + "</td><td>" + fmt(matrixValue("osrm__travel_time", matrixOriginNom, ref, 60)) + "</td></tr>";
  h += "<tr><td>" + info.road_distance_km + "</td><td>" + fmt(matrixValue("osrm__road_distance", matrixOriginNom, ref, 1)) + "</td></tr>";
  h += "</table>";
  return h;
}

const geoLayer = L.geoJSON(PAYLOAD.geometry, {
  style: styleFn,
  onEachFeature: function (feature, layer) {
    layer.on({
      mouseover: function(e) {
        if (activeView === "trends") {
          if (trendsScope === "lab" || trendsScope === "national") return;
          e.target.setStyle({weight: 1.6, color: "#ffae42"});
          e.target.bringToFront();
          return;
        }
        if (activeView === "context") {
          return;
        }
        if (activeView === "epi-trends") {
          e.target.setStyle({weight: 1.6, color: "#ffae42"});
          e.target.bringToFront();
          updateEpiFloat(feature.properties.nom, e.latlng);
          return;
        }
        e.target.setStyle({weight: 1.6, color: "#ffae42"});
        e.target.bringToFront();
        document.getElementById("info-body").className = "";
        document.getElementById("info-body").innerHTML = infoHTML(feature);
      },
      mouseout: function(e) {
        if (activeView === "trends") {
          geoLayer.resetStyle(e.target);
          if (trendsScope === "health_zone" && trendsSelectedKey &&
              feature.properties.nom === trendsSelectedKey) {
            e.target.setStyle({weight: 2, color: "#ffae42"});
          }
          return;
        }
        if (activeView === "context") {
          if (e.target !== contextSelectedLayer) {
            geoLayer.resetStyle(e.target);
          }
          return;
        }
        if (activeView === "epi-trends") {
          hideEpiFloat();
          geoLayer.resetStyle(e.target);
          return;
        }
        geoLayer.resetStyle(e.target);
      },
      click: function(e) {
        if (activeView === "trends") {
          L.DomEvent.stop(e);
          if (trendsScope === "lab" || trendsScope === "national") return;
          if (trendsScope === "province") {
            setTrendsSelection(feature.properties.province || null);
            return;
          }
          if (trendsScope === "health_zone") {
            setTrendsSelection(feature.properties.nom || null);
            return;
          }
          return;
        }
        if (activeView === "context") {
          L.DomEvent.stop(e);
          selectContextZone(feature.properties.nom, e.target);
          return;
        }
        if (activeView === "epi-trends") {
          L.DomEvent.stop(e);
          setEpiSelected(feature.properties.nom);
          return;
        }
        const layer = getLayer(layerSelect.value);
        if (activeView === "map" && flowArcsOverlayActive()) {
          L.DomEvent.stop(e);
          setFlowHub(feature.properties.nom);
          return;
        }
        if (activeView === "map" && layerUsesMatrix(layer)) {
          L.DomEvent.stop(e);
          setMatrixOrigin(feature.properties.nom);
          return;
        }
        map.fitBounds(e.target.getBounds(), {padding:[40,40]});
      },
      dblclick: function(e) {
        if (activeView === "context") return;
        if (activeView === "trends" && (trendsScope === "lab" || trendsScope === "national")) {
          return;
        }
        L.DomEvent.stop(e);
        map.fitBounds(e.target.getBounds(), {padding:[40,40]});
      }
    });
  }
}).addTo(map);

map.on("click", function() {
  if (activeView === "context") clearContextSelection();
  if (activeView === "epi-trends") setEpiSelected(null);
});

// --- health-zone search ---
const ZONE_SEARCH_INDEX = (PAYLOAD.geometry.features || []).map(function(feat) {
  const props = feat.properties || {};
  const name = props.name || props.nom || "";
  const nom = props.nom || "";
  return {
    nom: nom,
    name: name,
    label: name,
    haystack: (name + " " + nom).toLowerCase(),
  };
}).filter(function(z) { return !!z.nom; })
  .sort(function(a, b) {
    return String(a.name).localeCompare(String(b.name), undefined, {sensitivity: "base"});
  });

const zoneSearchInput = document.getElementById("zone-search-input");
const zoneSearchResults = document.getElementById("zone-search-results");
const zoneSearchWrap = document.getElementById("zone-search-wrap");
let zoneSearchMatches = [];
let zoneSearchActiveIdx = -1;
let searchHighlightLayer = null;
let searchHighlightTimer = null;

function findGeoLayerByNom(nom) {
  let found = null;
  geoLayer.eachLayer(function(layer) {
    if (!found && layer.feature && layer.feature.properties && layer.feature.properties.nom === nom) {
      found = layer;
    }
  });
  return found;
}

function clearSearchHighlight() {
  if (searchHighlightTimer) {
    clearTimeout(searchHighlightTimer);
    searchHighlightTimer = null;
  }
  if (searchHighlightLayer && searchHighlightLayer !== contextSelectedLayer) {
    geoLayer.resetStyle(searchHighlightLayer);
  }
  searchHighlightLayer = null;
}

function closeZoneSearchResults() {
  if (!zoneSearchResults) return;
  zoneSearchResults.hidden = true;
  zoneSearchResults.innerHTML = "";
  zoneSearchMatches = [];
  zoneSearchActiveIdx = -1;
  if (zoneSearchInput) zoneSearchInput.setAttribute("aria-expanded", "false");
}

function renderZoneSearchResults(query) {
  if (!zoneSearchResults) return;
  const q = String(query || "").trim().toLowerCase();
  if (!q) {
    closeZoneSearchResults();
    return;
  }
  zoneSearchMatches = ZONE_SEARCH_INDEX.filter(function(z) {
    return z.haystack.indexOf(q) !== -1;
  }).slice(0, 12);
  zoneSearchActiveIdx = zoneSearchMatches.length ? 0 : -1;
  if (!zoneSearchMatches.length) {
    zoneSearchResults.innerHTML =
      "<div class='zone-search-empty' data-i18n-live='1'>" + t("ui.zone_search_no_matches") + "</div>";
    zoneSearchResults.hidden = false;
    if (zoneSearchInput) zoneSearchInput.setAttribute("aria-expanded", "true");
    return;
  }
  zoneSearchResults.innerHTML = zoneSearchMatches.map(function(z, i) {
    return (
      "<button type='button' class='zone-search-option" + (i === 0 ? " active" : "") +
      "' role='option' data-nom='" + escHtml(z.nom) + "'>" + escHtml(z.label) + "</button>"
    );
  }).join("");
  zoneSearchResults.hidden = false;
  if (zoneSearchInput) zoneSearchInput.setAttribute("aria-expanded", "true");
}

function setZoneSearchActive(idx) {
  if (!zoneSearchMatches.length) return;
  zoneSearchActiveIdx = Math.max(0, Math.min(idx, zoneSearchMatches.length - 1));
  const opts = zoneSearchResults.querySelectorAll(".zone-search-option");
  opts.forEach(function(el, i) {
    el.classList.toggle("active", i === zoneSearchActiveIdx);
  });
  const active = opts[zoneSearchActiveIdx];
  if (active && active.scrollIntoView) active.scrollIntoView({block: "nearest"});
}

function selectHealthZone(nom) {
  const layer = findGeoLayerByNom(nom);
  if (!layer || !layer.feature) return;
  const feature = layer.feature;
  const displayName = feature.properties.name || nom;

  if (activeView === "context") {
    selectContextZone(nom, layer);
    map.fitBounds(layer.getBounds(), {padding: [40, 40], maxZoom: 10});
  } else if (activeView === "map") {
    clearSearchHighlight();
    if (flowArcsOverlayActive()) {
      setFlowHub(nom);
    } else if (layerUsesMatrix(getLayer(layerSelect.value))) {
      setMatrixOrigin(nom);
    }
    map.fitBounds(layer.getBounds(), {padding: [40, 40], maxZoom: 10});
    layer.setStyle({weight: 1.6, color: "#ffae42"});
    layer.bringToFront();
    searchHighlightLayer = layer;
    const infoBody = document.getElementById("info-body");
    if (infoBody) {
      infoBody.className = "";
      infoBody.innerHTML = infoHTML(feature);
    }
    searchHighlightTimer = setTimeout(function() {
      if (searchHighlightLayer === layer && layer !== contextSelectedLayer) {
        geoLayer.resetStyle(layer);
      }
      searchHighlightLayer = null;
      searchHighlightTimer = null;
    }, 2500);
  }

  if (zoneSearchInput) zoneSearchInput.value = displayName;
  closeZoneSearchResults();
}

if (zoneSearchWrap) {
  L.DomEvent.disableClickPropagation(zoneSearchWrap);
  L.DomEvent.disableScrollPropagation(zoneSearchWrap);
}

if (zoneSearchInput && zoneSearchResults) {
  zoneSearchInput.addEventListener("input", function() {
    renderZoneSearchResults(zoneSearchInput.value);
  });
  zoneSearchInput.addEventListener("focus", function() {
    if (zoneSearchInput.value.trim()) renderZoneSearchResults(zoneSearchInput.value);
  });
  zoneSearchInput.addEventListener("keydown", function(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (zoneSearchResults.hidden) renderZoneSearchResults(zoneSearchInput.value);
      setZoneSearchActive(zoneSearchActiveIdx + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setZoneSearchActive(zoneSearchActiveIdx - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (zoneSearchActiveIdx >= 0 && zoneSearchMatches[zoneSearchActiveIdx]) {
        selectHealthZone(zoneSearchMatches[zoneSearchActiveIdx].nom);
      } else if (!zoneSearchResults.hidden && zoneSearchMatches[0]) {
        selectHealthZone(zoneSearchMatches[0].nom);
      }
    } else if (e.key === "Escape") {
      closeZoneSearchResults();
      zoneSearchInput.blur();
    }
  });
  zoneSearchResults.addEventListener("mousedown", function(e) {
    const btn = e.target.closest(".zone-search-option");
    if (!btn) return;
    e.preventDefault();
    selectHealthZone(btn.getAttribute("data-nom"));
  });
  document.addEventListener("click", function(e) {
    if (!zoneSearchWrap) return;
    if (!zoneSearchWrap.contains(e.target)) closeZoneSearchResults();
  });
}

// --- province outlines (Trends view) ---
let trendsScope = "national";
let trendsSelectedKey = null;
let trendsHoverTimer = null;
let trendsHoveredProvince = null;
function themeVar(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}
function provinceOutlineStyle(selected) {
  const provinceMode = activeView === "trends" && trendsScope === "province";
  const baseWeight = provinceMode
    ? parseFloat(themeVar("--province-outline-weight-wide", "2.4"))
    : parseFloat(themeVar("--province-outline-weight", "1"));
  const selWeight = provinceMode
    ? parseFloat(themeVar("--province-outline-weight-wide-hover", "3.6"))
    : parseFloat(themeVar("--province-outline-weight-hover", "1.5"));
  return {
    color: selected
      ? themeVar("--province-outline-hover", "#b23b2e")
      : themeVar("--province-outline", "#9b7d4e"),
    weight: selected ? selWeight : baseWeight,
    opacity: selected ? 1 : (provinceMode ? 0.95 : 0.88),
    fillOpacity: 0,
  };
}

map.createPane("province-outline");
map.getPane("province-outline").style.zIndex = 550;
const provinceOutlineLayer = L.geoJSON(PAYLOAD.province_boundaries || {type:"FeatureCollection", features:[]}, {
  pane: "province-outline",
  interactive: false,
  style: function() {
    return provinceOutlineStyle(false);
  },
});

function applyProvinceOutlineStyles(selectedProvince) {
  trendsHoveredProvince = selectedProvince || null;
  document.body.classList.toggle("trends-province-hovered", !!trendsHoveredProvince);
  provinceOutlineLayer.eachLayer(function(layer) {
    const match = trendsHoveredProvince &&
      layer.feature.properties.province === trendsHoveredProvince;
    layer.setStyle(provinceOutlineStyle(!!match));
    if (match) layer.bringToFront();
  });
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderTrendsPanel(_unused) {
  renderTrendsPlot();
}

function setTrendsProvinceHover(province) {
  // Kept for compatibility; selection-driven plots replace hover plots.
  if (activeView === "trends" && trendsScope === "province" && !trendsSelectedKey) {
    applyProvinceOutlineStyles(province || null);
  }
}

function trendsPlotData() {
  return PAYLOAD.onset_trends || null;
}

function trendsEntityList() {
  const data = trendsPlotData();
  if (!data) return [];
  if (trendsScope === "province") {
    return Object.keys(data.provinces || data.plots || {}).sort(function(a, b) {
      return String(a).localeCompare(String(b), undefined, {sensitivity: "base"});
    }).map(function(id) {
      return {id: id, label: id, kind: "province"};
    });
  }
  if (trendsScope === "health_zone") {
    return Object.keys(data.health_zones || {}).sort(function(a, b) {
      return String(a).localeCompare(String(b), undefined, {sensitivity: "base"});
    }).map(function(id) {
      return {id: id, label: zoneDisplayName(id) || id, kind: "health_zone"};
    });
  }
  if (trendsScope === "lab") {
    return (data.labs || []).map(function(lab) {
      return {id: lab.id, label: lab.label || lab.id, kind: "lab"};
    });
  }
  return [{id: "national", label: t("ui.trends_scope_national"), kind: "national"}];
}

function findTrendsLab(id) {
  const labs = (trendsPlotData() && trendsPlotData().labs) || [];
  for (let i = 0; i < labs.length; i++) {
    if (labs[i].id === id) return labs[i];
  }
  return null;
}

function resolveTrendsPlot() {
  const data = trendsPlotData();
  if (!data) return null;
  if (trendsScope === "national") return data.national || null;
  if (trendsScope === "province") {
    if (!trendsSelectedKey) return null;
    return (data.provinces && data.provinces[trendsSelectedKey]) ||
      (data.plots && data.plots[trendsSelectedKey]) || null;
  }
  if (trendsScope === "health_zone") {
    if (!trendsSelectedKey) return null;
    return (data.health_zones && data.health_zones[trendsSelectedKey]) || null;
  }
  if (trendsScope === "lab") {
    if (!trendsSelectedKey) return null;
    return findTrendsLab(trendsSelectedKey);
  }
  return null;
}

function renderTrendsPlot() {
  const titleEl = document.getElementById("trends-title");
  const body = document.getElementById("trends-body");
  if (!body) return;
  const plot = resolveTrendsPlot();
  if (plot && plot.svg) {
    if (titleEl) titleEl.textContent = plot.title || plot.label || t("ui.trends_panel");
    body.className = "panel-body";
    body.innerHTML = "<div class='onset-chart-wrap'>" + plot.svg + "</div>";
    return;
  }
  if (titleEl) titleEl.textContent = t("ui.trends_panel");
  body.className = "panel-body trends-empty";
  if (trendsScope === "national") {
    body.innerHTML = "<p>" + escHtml(t("ui.trends_no_plot").replace("{name}", t("ui.trends_scope_national"))) + "</p>";
  } else if (trendsScope === "province") {
    body.innerHTML = "<p>" + escHtml(
      trendsSelectedKey
        ? tf("ui.trends_no_plot", {name: trendsSelectedKey})
        : t("ui.trends_select_province")
    ) + "</p>";
  } else if (trendsScope === "health_zone") {
    body.innerHTML = "<p>" + escHtml(
      trendsSelectedKey
        ? tf("ui.trends_no_plot", {name: zoneDisplayName(trendsSelectedKey) || trendsSelectedKey})
        : t("ui.trends_select_health_zone")
    ) + "</p>";
  } else {
    body.innerHTML = "<p>" + escHtml(
      trendsSelectedKey
        ? tf("ui.trends_no_plot", {name: (findTrendsLab(trendsSelectedKey) || {}).label || trendsSelectedKey})
        : t("ui.trends_select_lab")
    ) + "</p>";
  }
}

function fitMapToTrendsSelection(key) {
  if (!key || activeView !== "trends") return;
  if (trendsScope === "health_zone") {
    const layer = findGeoLayerByNom(key);
    if (!layer) return;
    map.fitBounds(layer.getBounds(), {
      paddingTopLeft: [40, 80],
      paddingBottomRight: [Math.min(420, Math.round(window.innerWidth * 0.42)), 160],
      maxZoom: 10,
    });
    return;
  }
  if (trendsScope !== "province") return;
  let bounds = null;
  provinceOutlineLayer.eachLayer(function(layer) {
    if (layer.feature && layer.feature.properties.province === key) {
      bounds = layer.getBounds();
    }
  });
  if (!bounds || !bounds.isValid()) {
    const layers = [];
    geoLayer.eachLayer(function(layer) {
      if (layer.feature && layer.feature.properties.province === key) {
        layers.push(layer);
      }
    });
    if (!layers.length) return;
    bounds = L.featureGroup(layers).getBounds();
  }
  if (!bounds || !bounds.isValid()) return;
  map.fitBounds(bounds, {
    paddingTopLeft: [40, 80],
    paddingBottomRight: [Math.min(420, Math.round(window.innerWidth * 0.42)), 160],
    maxZoom: 8,
  });
}

function setTrendsSelection(key, opts) {
  opts = opts || {};
  trendsSelectedKey = key || null;
  if (trendsScope === "province") {
    applyProvinceOutlineStyles(trendsSelectedKey);
  } else if (trendsScope === "health_zone") {
    applyProvinceOutlineStyles(null);
  } else {
    applyProvinceOutlineStyles(null);
  }
  renderTrendsLabList();
  renderTrendsPlot();
  if (activeView === "trends") {
    // Restyle health-zone polygons to emphasize selection.
    geoLayer.setStyle(styleFn);
    if (trendsScope === "health_zone" && trendsSelectedKey) {
      geoLayer.eachLayer(function(layer) {
        if (layer.feature && layer.feature.properties.nom === trendsSelectedKey) {
          layer.setStyle({weight: 2, color: "#ffae42"});
          layer.bringToFront();
        }
      });
    }
    if (trendsSelectedKey &&
        (trendsScope === "province" || trendsScope === "health_zone")) {
      fitMapToTrendsSelection(trendsSelectedKey);
    }
  }
  if (opts.fromSearch) {
    const input = document.getElementById("trends-search-input");
    const results = document.getElementById("trends-search-results");
    if (input) input.value = "";
    if (results) {
      results.classList.remove("open");
      results.innerHTML = "";
    }
  }
}

function setTrendsScope(scope) {
  trendsScope = scope || "national";
  trendsSelectedKey = null;
  const labList = document.getElementById("trends-lab-list");
  if (labList) labList.classList.toggle("visible", trendsScope === "lab");
  document.body.classList.toggle("trends-lab-mode", trendsScope === "lab");
  applyProvinceOutlineStyles(null);
  renderTrendsLabList();
  renderTrendsPlot();
  if (activeView === "trends") {
    geoLayer.setStyle(styleFn);
    showProvinceOutlines();
  }
}

function renderTrendsLabList() {
  const root = document.getElementById("trends-lab-list");
  if (!root) return;
  if (trendsScope !== "lab") {
    root.innerHTML = "";
    return;
  }
  const labs = (trendsPlotData() && trendsPlotData().labs) || [];
  const q = ((document.getElementById("trends-search-input") || {}).value || "").trim().toLowerCase();
  root.innerHTML = labs.filter(function(lab) {
    if (!q) return true;
    return String(lab.label || "").toLowerCase().indexOf(q) >= 0 ||
      String(lab.id || "").toLowerCase().indexOf(q) >= 0;
  }).map(function(lab) {
    const active = lab.id === trendsSelectedKey ? " active" : "";
    return "<button type='button' class='" + active + "' data-lab-id='" + escHtml(lab.id) + "'>" +
      escHtml(lab.label || lab.id) + "</button>";
  }).join("");
}

function renderTrendsSearchResults(query) {
  const root = document.getElementById("trends-search-results");
  if (!root) return;
  if (trendsScope === "national") {
    root.classList.remove("open");
    root.innerHTML = "";
    return;
  }
  const q = String(query || "").trim().toLowerCase();
  // Only open the match list once the user starts typing.
  if (!q) {
    root.classList.remove("open");
    root.innerHTML = "";
    return;
  }
  let items = trendsEntityList().filter(function(it) {
    return String(it.label).toLowerCase().indexOf(q) >= 0 ||
      String(it.id).toLowerCase().indexOf(q) >= 0;
  });
  if (!items.length) {
    root.innerHTML = "<div class='zone-search-empty'>" + escHtml(t("ui.zone_search_no_matches") || "No matches") + "</div>";
    root.classList.add("open");
    return;
  }
  // Keep enough matches that the expanded panel can fill its ≥5-hit capacity.
  root.innerHTML = items.slice(0, 40).map(function(it) {
    return "<button type='button' role='option' data-id='" + escHtml(it.id) + "'>" +
      escHtml(it.label) + "</button>";
  }).join("");
  root.classList.add("open");
}

function syncTrendsPlayButton() {
  const btn = document.getElementById("trends-play-btn");
  if (!btn) return;
  btn.classList.toggle("playing", !!trendsSliderAnimating);
  btn.textContent = trendsSliderAnimating ? t("ui.trends_pause") : t("ui.trends_play");
}

function formatContextDate(raw) {
  if (!raw) return "";
  const s = String(raw).trim();
  if (!s) return "";
  if (s.length >= 10 && s[2] === "-" && s[5] === "-") {
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const d = parseInt(s.slice(0, 2), 10);
    const m = parseInt(s.slice(3, 5), 10);
    const y = s.slice(6, 10);
    if (m >= 1 && m <= 12 && d >= 1) {
      return String(d) + " " + months[m - 1] + " " + y;
    }
  }
  if (s.length >= 10 && s[4] === "-" && s[7] === "-") {
    const parts = s.slice(0, 10).split("-");
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const m = parseInt(parts[1], 10);
    const d = parseInt(parts[2], 10);
    if (m >= 1 && m <= 12 && d >= 1) {
      return String(d) + " " + months[m - 1] + " " + parts[0];
    }
  }
  if (s.indexOf("/") >= 0) {
    const bits = s.split("/");
    if (bits.length === 3) {
      const a = parseInt(bits[0], 10), b = parseInt(bits[1], 10);
      let y = parseInt(bits[2], 10);
      if (y < 100) y += 2000;
      const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
      const day = a > 12 ? a : b;
      const month = a > 12 ? b : a;
      if (month >= 1 && month <= 12) {
        return String(day) + " " + months[month - 1] + " " + y;
      }
    }
  }
  return s;
}

function contextDateSortKey(pillar) {
  if (pillar && pillar.date_iso) {
    const t = Date.parse(pillar.date_iso);
    if (!isNaN(t)) return t;
  }
  const raw = pillar ? pillar.date : null;
  if (raw == null) return Number.NEGATIVE_INFINITY;
  const s = String(raw).trim();
  if (!s) return Number.NEGATIVE_INFINITY;
  if (s.length >= 10 && s[2] === "-" && s[5] === "-") {
    const d = parseInt(s.slice(0, 2), 10);
    const m = parseInt(s.slice(3, 5), 10) - 1;
    const y = parseInt(s.slice(6, 10), 10);
    const t = Date.UTC(y, m, d);
    if (!isNaN(t)) return t;
  }
  if (s.length >= 10 && s[4] === "-" && s[7] === "-") {
    const t = Date.parse(s.slice(0, 10));
    if (!isNaN(t)) return t;
  }
  if (s.indexOf("/") >= 0) {
    const bits = s.split("/");
    if (bits.length === 3) {
      const a = parseInt(bits[0], 10), b = parseInt(bits[1], 10);
      let y = parseInt(bits[2], 10);
      if (y < 100) y += 2000;
      const day = a > 12 ? a : b;
      const month = (a > 12 ? b : a) - 1;
      const t = Date.UTC(y, month, day);
      if (!isNaN(t)) return t;
    }
  }
  return Number.NEGATIVE_INFINITY;
}

function sortContextPillarsByDate(pillars) {
  return pillars.slice().sort(function(a, b) {
    const diff = contextDateSortKey(b) - contextDateSortKey(a);
    if (diff !== 0) return diff;
    return phrLabel(a).localeCompare(phrLabel(b));
  });
}

function phrPillarCategoryClass(pillar) {
  const cat = pillar.category || (pillar.metric || "").replace(/^national_/, "").replace(/^provincial_/, "");
  if (!cat) return "";
  return "pillar-" + cat.replace(/_/g, "-");
}

function phrLabel(pillar) {
  const key = (pillar.metric || "").replace(/^national_/, "").replace(/^provincial_/, "");
  const labels = t("phr");
  if (labels && typeof labels === "object" && labels[key]) return labels[key];
  return pillar.label || key;
}

function phrScopeStamp(pillar) {
  if (pillar && pillar.scope_tag && pillar.scope !== "national" && pillar.scope !== "zone") {
    return pillar.scope_tag;
  }
  if (!pillar) return "";
  if (pillar.scope === "national") return t("scope_tags.national");
  if (pillar.scope === "provincial" && pillar.province) {
    return String(pillar.province).toUpperCase();
  }
  if (pillar.scope === "zone") return t("scope_tags.health_zone");
  return pillar.scope_tag || "";
}

function renderContextPillarHtml(pillar, opts) {
  opts = opts || {};
  const catClass = phrPillarCategoryClass(pillar);
  let meta = "";
  if (!opts.hideScopeTag) {
    const stamp = phrScopeStamp(pillar);
    if (stamp) meta = "<span class='scope-tag'>" + escHtml(stamp) + "</span>";
  }
  const dateStr = formatContextDate(pillar.date);
  if (dateStr) meta += "<span>" + t("ui.context_as_of") + " " + escHtml(dateStr) + "</span>";
  const metaBlock = meta ? "<div class='context-meta'>" + meta + "</div>" : "";
  return (
    "<div class='context-pillar " + catClass + "'>" +
      "<h4>" + escHtml(phrLabel(pillar)) + "</h4>" +
      metaBlock +
      "<p>" + escHtml(pillar.text) + "</p>" +
    "</div>"
  );
}

function zoneFeatureProps(nom) {
  for (const feat of PAYLOAD.geometry.features) {
    if (feat.properties.nom === nom) {
      return feat.properties;
    }
  }
  return null;
}

function zoneDisplayName(nom) {
  const props = zoneFeatureProps(nom);
  return props ? (props.name || nom) : nom;
}

function zoneProvince(nom) {
  const props = zoneFeatureProps(nom);
  return props ? (props.province || null) : null;
}

function phrContext() {
  const byLang = (I18N.phr_context || PAYLOAD.phr_context_by_lang || null);
  if (byLang && (byLang.en || byLang.fr)) {
    return byLang[currentLang] || byLang.en || {national: [], by_nom: {}};
  }
  const legacy = PAYLOAD.phr_context || {};
  if (legacy.national || legacy.by_nom) return legacy;
  return {national: [], by_nom: {}};
}

function filterRollupsForContext(nom) {
  const allRollups = phrContext().national || [];
  if (!nom) {
    return allRollups.filter(function(p) { return p.scope === "national"; });
  }
  const province = zoneProvince(nom);
  return allRollups.filter(function(p) {
    if (p.scope === "national") return true;
    if (p.scope === "provincial" && province && p.province === province) return true;
    return false;
  });
}

function renderNationalContextPanel(nom) {
  const body = document.getElementById("context-national-body");
  if (!body) return;
  body.scrollTop = 0;
  const rollups = filterRollupsForContext(nom);
  if (!rollups.length) {
    body.className = "panel-body context-empty";
    body.innerHTML = nom
      ? "<p>" + t("ui.context_no_national_area") + "</p>"
      : "<p>" + t("ui.context_no_national") + "</p>";
    return;
  }
  body.className = "panel-body";
  body.innerHTML = sortContextPillarsByDate(rollups).map(function(p) {
    return renderContextPillarHtml(p);
  }).join("");
}

let contextSelectedNom = null;
let contextSelectedLayer = null;

function clearContextSelection() {
  if (contextSelectedLayer) {
    geoLayer.resetStyle(contextSelectedLayer);
    contextSelectedLayer = null;
  }
  contextSelectedNom = null;
  renderContextPanel(null);
}

function selectContextZone(nom, layer) {
  if (!nom || !layer) return;
  if (contextSelectedLayer && contextSelectedLayer !== layer) {
    geoLayer.resetStyle(contextSelectedLayer);
  }
  contextSelectedNom = nom;
  contextSelectedLayer = layer;
  layer.setStyle({weight: 1.6, color: "#ffae42"});
  layer.bringToFront();
  renderContextPanel(nom);
}

function renderContextPanel(nom) {
  const body = document.getElementById("context-body");
  const title = document.getElementById("context-title");
  if (!body) return;
  document.body.classList.toggle("context-zone-hovered", !!nom);
  renderNationalContextPanel(nom);
  body.scrollTop = 0;
  if (!nom) {
    if (title) title.textContent = t("ui.context_zone");
    body.className = "panel-body context-empty";
    body.innerHTML = "<p>" + t("ui.context_click_zone") + "</p>";
    return;
  }
  const zonePillars = (phrContext().by_nom || {})[nom] || [];
  const displayName = zoneDisplayName(nom);
  if (title) title.textContent = displayName;
  if (!zonePillars.length) {
    body.className = "panel-body context-empty";
    body.innerHTML = "<p>" + tf("ui.context_no_zone", {zone: escHtml(displayName)}) + "</p>";
    return;
  }
  body.className = "panel-body";
  body.innerHTML = sortContextPillarsByDate(zonePillars).map(function(p) {
    return renderContextPillarHtml(p, {hideScopeTag: true});
  }).join("");
}

function showProvinceOutlines() {
  if (!map.hasLayer(provinceOutlineLayer)) {
    provinceOutlineLayer.addTo(map);
  }
  provinceOutlineLayer.bringToFront();
  applyProvinceOutlineStyles(null);
}

function hideProvinceOutlines() {
  if (map.hasLayer(provinceOutlineLayer)) {
    map.removeLayer(provinceOutlineLayer);
  }
  applyProvinceOutlineStyles(null);
}

// --- Map / Trends / Context tab switching ---
let savedMapLayerId = null;
let trendsDateIdx = 0;
let trendsSliderTimer = null;
let trendsSliderAnimating = false;
let trendsSliderPointerDown = false;
const TRENDS_SLIDER_STEP_MS = 300;

function setTrendsSliderBusy(busy) {
  document.body.classList.toggle("trends-slider-busy", !!busy);
}

function syncTrendsSliderBusy() {
  setTrendsSliderBusy(trendsSliderAnimating || trendsSliderPointerDown);
}

function stopTrendsSliderAnimation() {
  if (trendsSliderTimer != null) {
    clearInterval(trendsSliderTimer);
    trendsSliderTimer = null;
  }
  trendsSliderAnimating = false;
  syncTrendsSliderBusy();
  syncTrendsPlayButton();
}

function applyTrendsDateIdx(idx) {
  const ts = PAYLOAD.confirmed_timeseries;
  const slider = document.getElementById("trends-date-slider");
  if (!ts || !ts.dates || !ts.dates.length) return;
  trendsDateIdx = Math.max(0, Math.min(idx, ts.dates.length - 1));
  if (slider) slider.value = String(trendsDateIdx);
  updateTrendsDateLabel();
  recomputeTrendsMap();
}

function playTrendsSliderAnimation() {
  stopTrendsSliderAnimation();
  const ts = PAYLOAD.confirmed_timeseries;
  if (!ts || !ts.dates || ts.dates.length < 2) return;
  trendsSliderAnimating = true;
  syncTrendsSliderBusy();
  syncTrendsPlayButton();
  let idx = 0;
  applyTrendsDateIdx(0);
  trendsSliderTimer = setInterval(function() {
    if (activeView !== "trends") {
      stopTrendsSliderAnimation();
      return;
    }
    idx += 1;
    if (idx >= ts.dates.length) {
      applyTrendsDateIdx(ts.dates.length - 1);
      stopTrendsSliderAnimation();
      return;
    }
    applyTrendsDateIdx(idx);
  }, TRENDS_SLIDER_STEP_MS);
}

function getTrendsConfirmedAt(nom, dateIdx) {
  const ts = PAYLOAD.confirmed_timeseries;
  if (!ts || !ts.by_nom) return 0;
  const series = ts.by_nom[nom];
  if (!series || dateIdx < 0 || dateIdx >= series.length) return 0;
  return series[dateIdx];
}

function initTrendsLegendBar() {
  const ts = PAYLOAD.confirmed_timeseries;
  if (!ts) return;
  const layer = getLayer("obs::confirmed");
  const palette = PALETTES[(layer && layer.palette) || "reds"] || REDS;
  const bar = document.getElementById("trends-legend-bar");
  if (!bar) return;
  const stops = [];
  const N = 32;
  for (let i = 0; i < N; i++) {
    const t = i / (N - 1);
    stops.push(rgb(lerpColor(palette, t)) + " " + Math.round(t * 100) + "%");
  }
  bar.style.background = "linear-gradient(to right, " + stops.join(", ") + ")";
  const lo = ts.min_positive || 1;
  const hi = ts.max_confirmed || 1;
  const mid = Math.sqrt(lo * hi);
  const ticks = document.getElementById("trends-legend-ticks");
  if (ticks) {
    ticks.innerHTML =
      "<span>" + fmtLegend(lo, "int") + "</span>" +
      "<span>" + fmtLegend(mid, "int") + "</span>" +
      "<span>" + fmtLegend(hi, "int") + "</span>";
  }
  const scaleEl = document.getElementById("trends-legend-scale");
  if (scaleEl) scaleEl.textContent = t("ui.trends_scale_log");
}

function updateTrendsDateLabel() {
  const ts = PAYLOAD.confirmed_timeseries;
  const label = document.getElementById("trends-date-label");
  if (!label || !ts || !ts.dates || !ts.dates.length) return;
  const iso = ts.dates[trendsDateIdx];
  const raw = (ts.date_labels && ts.date_labels[iso]) || iso;
  label.textContent = t("ui.trends_as_of").replace("—", formatContextDate(raw));
}

function recomputeTrendsMap() {
  const ts = PAYLOAD.confirmed_timeseries;
  if (!ts || !ts.dates || !ts.dates.length) return;
  const layer = getLayer("obs::confirmed") || { palette: "reds" };
  currentValues.clear();
  for (const feat of PAYLOAD.geometry.features) {
    const ref = feat.properties.nom;
    currentValues.set(ref, getTrendsConfirmedAt(ref, trendsDateIdx));
  }
  const lo = ts.min_positive || 1;
  let hi = ts.max_confirmed || 1;
  if (hi <= lo) hi = lo + 1;
  currentDomain = {
    min: lo,
    max: hi,
    isLog: true,
    palette: PALETTES[layer.palette] || REDS,
  };
  geoLayer.setStyle(styleFn);
  if (activeView === "trends" && trendsScope === "health_zone" && trendsSelectedKey) {
    geoLayer.eachLayer(function(layer) {
      if (layer.feature && layer.feature.properties.nom === trendsSelectedKey) {
        layer.setStyle({weight: 2, color: "#ffae42"});
        layer.bringToFront();
      }
    });
  }
}

function restoreCaseMarkersForView(view) {
  if (view === "trends") {
    map.removeLayer(caseLayer);
    return;
  }
  if (view === "epi-trends") {
    const epiCases = document.getElementById("epi-show-cases");
    const on = epiCases ? epiCases.checked : (showCasesBox && showCasesBox.checked);
    if (on) caseLayer.addTo(map);
    else map.removeLayer(caseLayer);
    return;
  }
  if (showCasesBox.checked) caseLayer.addTo(map);
  else map.removeLayer(caseLayer);
}

function restoreFlowArcsForView(view) {
  if (view !== "map" && view !== "epi-trends") {
    clearFlowArcs();
    return;
  }
  if (flowArcsOverlayActive()) {
    renderFlowArcs(flowHubNom, flowArcLayerDef());
  } else {
    clearFlowArcs();
  }
}

function enterTrendsView() {
  savedMapLayerId = layerSelect.value;
  clearFlowArcs();
  layerSelect.value = "obs::confirmed";
  map.removeLayer(caseLayer);
  showProvinceOutlines();
  clearContextSelection();
  const ts = PAYLOAD.confirmed_timeseries;
  const legendPanel = document.getElementById("trends-legend");
  if (!ts || !ts.dates || !ts.dates.length) {
    if (legendPanel) legendPanel.style.display = "none";
    recompute();
  } else {
    if (legendPanel) legendPanel.style.display = "";
    initTrendsLegendBar();
    const slider = document.getElementById("trends-date-slider");
    if (slider) slider.max = String(ts.dates.length - 1);
    // Latest sitrep values on open; animation only via Play.
    applyTrendsDateIdx(ts.dates.length - 1);
  }
  const scopeSelect = document.getElementById("trends-scope-select");
  if (scopeSelect) setTrendsScope(scopeSelect.value || "national");
  else setTrendsScope("national");
  map.invalidateSize({animate: false});
}

function leaveTrendsView() {
  stopTrendsSliderAnimation();
  trendsSliderPointerDown = false;
  setTrendsSliderBusy(false);
  hideProvinceOutlines();
  trendsSelectedKey = null;
  document.body.classList.remove("trends-lab-mode");
  renderTrendsPlot();
  if (savedMapLayerId) {
    layerSelect.value = savedMapLayerId;
    recompute();
  }
}

function setActiveView(view) {
  if (view === activeView) return;
  if (view === "trends") {
    enterTrendsView();
  } else if (view === "epi-trends") {
    if (activeView === "trends") leaveTrendsView();
    else {
      hideProvinceOutlines();
      clearContextSelection();
    }
    enterEpiTrendsView();
  } else if (view === "context") {
    clearFlowArcs();
    if (activeView === "trends") leaveTrendsView();
    else if (activeView === "epi-trends") leaveEpiTrendsView();
    else {
      hideProvinceOutlines();
      renderTrendsPanel(null);
    }
    clearContextSelection();
  } else {
    if (activeView === "trends") leaveTrendsView();
    else if (activeView === "epi-trends") leaveEpiTrendsView();
    else {
      hideProvinceOutlines();
      clearContextSelection();
    }
  }
  activeView = view;
  restoreCaseMarkersForView(view);
  restoreFlowArcsForView(view);
  document.body.classList.toggle("view-map", view === "map");
  document.body.classList.toggle("view-trends", view === "trends");
  document.body.classList.toggle("view-epi-trends", view === "epi-trends");
  document.body.classList.toggle("view-context", view === "context");
  syncMatrixUi();
  document.querySelectorAll(".view-tab").forEach(function(btn) {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  if (view === "epi-trends") {
    map.invalidateSize();
    recomputeEpiTrends();
  } else if (view === "trends") {
    map.invalidateSize();
  } else if (view === "map") {
    map.invalidateSize();
    recompute();
  }
}

document.querySelectorAll(".view-tab").forEach(function(btn) {
  btn.addEventListener("click", function() {
    setActiveView(btn.dataset.view || "map");
  });
});

(function wireTrendsDateSlider() {
  const slider = document.getElementById("trends-date-slider");
  if (!slider) return;
  function onUserSliderChange() {
    if (activeView !== "trends") return;
    stopTrendsSliderAnimation();
    applyTrendsDateIdx(parseInt(slider.value, 10) || 0);
  }
  function onSliderPointerDown() {
    trendsSliderPointerDown = true;
    syncTrendsSliderBusy();
    stopTrendsSliderAnimation();
  }
  function onSliderPointerUp() {
    trendsSliderPointerDown = false;
    syncTrendsSliderBusy();
  }
  slider.addEventListener("input", onUserSliderChange);
  slider.addEventListener("pointerdown", onSliderPointerDown);
  slider.addEventListener("pointerup", onSliderPointerUp);
  slider.addEventListener("pointercancel", onSliderPointerUp);
  const playBtn = document.getElementById("trends-play-btn");
  if (playBtn) {
    playBtn.addEventListener("click", function() {
      if (activeView !== "trends") return;
      if (trendsSliderAnimating) stopTrendsSliderAnimation();
      else playTrendsSliderAnimation();
    });
  }
  syncTrendsPlayButton();
})();

(function wireTrendsPanelUi() {
  const scopeSelect = document.getElementById("trends-scope-select");
  const searchInput = document.getElementById("trends-search-input");
  const searchResults = document.getElementById("trends-search-results");
  const labList = document.getElementById("trends-lab-list");

  if (scopeSelect) {
    scopeSelect.addEventListener("change", function() {
      setTrendsScope(scopeSelect.value || "national");
      if (searchInput) searchInput.value = "";
      if (searchResults) {
        searchResults.classList.remove("open");
        searchResults.innerHTML = "";
      }
    });
  }
  if (searchInput) {
    searchInput.addEventListener("input", function() {
      if (trendsScope === "lab") renderTrendsLabList();
      renderTrendsSearchResults(searchInput.value);
    });
    searchInput.addEventListener("focus", function() {
      renderTrendsSearchResults(searchInput.value);
    });
  }
  if (searchResults) {
    searchResults.addEventListener("click", function(e) {
      const btn = e.target.closest("button[data-id]");
      if (!btn) return;
      setTrendsSelection(btn.getAttribute("data-id"), {fromSearch: true});
    });
  }
  if (labList) {
    labList.addEventListener("click", function(e) {
      const btn = e.target.closest("button[data-lab-id]");
      if (!btn) return;
      setTrendsSelection(btn.getAttribute("data-lab-id"));
    });
  }
  document.addEventListener("click", function(e) {
    if (!searchResults || !searchResults.classList.contains("open")) return;
    if (e.target.closest("#trends-search-wrap")) return;
    searchResults.classList.remove("open");
  });
  setTrendsScope("national");
})();

// --- active-case markers ---
const ACTIVE_CASES = PAYLOAD.active_case_markers || [];
const GENOME_SEQUENCES = PAYLOAD.genome_sequence_markers || [];
const GENOME_MAX_COUNT = GENOME_SEQUENCES.reduce(function(max, g) {
  return Math.max(max, g.count || 0);
}, 1);
const caseIcon = L.divIcon({className:"", html:"<div class='case-icon'></div>", iconSize:[14,14]});
const caseLayer = L.layerGroup();
const genomeLayer = L.layerGroup();
const showCasesBox = document.getElementById("show-cases");
const showGenomesBox = document.getElementById("show-genomes");
const showGenomesRow = document.getElementById("show-genomes-row");

function genomeIcon(count) {
  const minD = 10;
  const maxD = 38;
  const t = GENOME_MAX_COUNT > 1 ? (count - 1) / (GENOME_MAX_COUNT - 1) : 1;
  const d = Math.round(minD + t * (maxD - minD));
  return L.divIcon({
    className: "",
    html: "<div class='genome-icon' style='width:" + d + "px;height:" + d + "px;'></div>",
    iconSize: [d, d],
    iconAnchor: [d / 2, d / 2],
  });
}

function syncMarkerToggles(from) {
  if (from === "cases" && showCasesBox.checked) {
    showGenomesBox.checked = false;
    map.removeLayer(genomeLayer);
    caseLayer.addTo(map);
    return;
  }
  if (from === "genomes" && showGenomesBox.checked) {
    showCasesBox.checked = false;
    map.removeLayer(caseLayer);
    genomeLayer.addTo(map);
    return;
  }
  if (from === "cases") map.removeLayer(caseLayer);
  if (from === "genomes") map.removeLayer(genomeLayer);
}

function caseMarkerTooltip(c) {
  const totalDeaths = (c.confirmed_deaths || 0) + (c.suspected_deaths || 0);
  return (
    "<strong>" + (c.name || t("ui.case_tooltip.unnamed")) + "</strong><br/>" +
    t("ui.case_tooltip.confirmed") + ": " + c.confirmed + "  ·  " +
    t("ui.case_tooltip.suspected") + ": " + c.suspected +
    (totalDeaths > 0 ? "<br/>" + t("ui.case_tooltip.deaths") + ": " + totalDeaths : "")
  );
}

function genomeMarkerTooltip(g) {
  return (
    "<strong>" + (g.name || t("ui.case_tooltip.unnamed")) + "</strong><br/>" +
    t("ui.genome_tooltip").replace("{n}", g.count)
  );
}

function refreshMarkerTooltips() {
  caseLayer.eachLayer(function(m) {
    if (m._bdbvCase) m.setTooltipContent(caseMarkerTooltip(m._bdbvCase));
  });
  genomeLayer.eachLayer(function(m) {
    if (m._bdbvGenome) m.setTooltipContent(genomeMarkerTooltip(m._bdbvGenome));
  });
}

for (const c of ACTIVE_CASES) {
  if (!isFinite(c.lat) || !isFinite(c.lon)) continue;
  const m = L.marker([c.lat, c.lon], {icon: caseIcon});
  m._bdbvCase = c;
  m.bindTooltip(caseMarkerTooltip(c), {direction:"top", offset:[0,-8]});
  caseLayer.addLayer(m);
}

for (const g of GENOME_SEQUENCES) {
  if (!isFinite(g.lat) || !isFinite(g.lon)) continue;
  const m = L.marker([g.lat, g.lon], {icon: genomeIcon(g.count)});
  m._bdbvGenome = g;
  m.bindTooltip(genomeMarkerTooltip(g), {direction:"top", offset:[0,-8]});
  genomeLayer.addLayer(m);
}

if (!PAYLOAD.genome_markers_available || !GENOME_SEQUENCES.length) {
  if (showGenomesRow) showGenomesRow.style.display = "none";
} else if (showGenomesBox) {
  showGenomesBox.addEventListener("change", function() {
    syncMarkerToggles("genomes");
  });
}

showCasesBox.addEventListener("change", function() {
  const epiCases = document.getElementById("epi-show-cases");
  if (epiCases) epiCases.checked = showCasesBox.checked;
  syncMarkerToggles("cases");
  if (activeView === "epi-trends") restoreCaseMarkersForView("epi-trends");
});

// --- Flowminder in/out flow arcs (toggle overlay) ---
const showFlowArcsBox = document.getElementById("show-flow-arcs");
const showFlowArcsRow = document.getElementById("show-flow-arcs-row");
let flowArcsUserPref = true;
if (!PAYLOAD.flow_arcs_available || !FLOW_ARC_LAYER) {
  if (showFlowArcsRow) showFlowArcsRow.style.display = "none";
  flowArcsUserPref = false;
} else if (showFlowArcsBox) {
  if (showFlowArcsRow) showFlowArcsRow.style.display = "";
  showFlowArcsBox.checked = true;
  flowArcsUserPref = true;
  showFlowArcsBox.addEventListener("change", function() {
    flowArcsUserPref = !!showFlowArcsBox.checked;
    recompute();
    syncMatrixUi();
  });
}

// --- Epidemiological trends controls ---
(function wireEpiTrendsUi() {
  const scopeSelect = document.getElementById("epi-scope-select");
  const tbody = document.getElementById("epi-trends-tbody");
  const tab = document.querySelector('.view-tab[data-view="epi-trends"]');
  const splitHandle = document.getElementById("epi-split-handle");
  const EPI_SPLIT_MIN = 28;
  const EPI_SPLIT_MAX = 72;
  const EPI_SPLIT_KEY = "bdbv_epi_panel_width_pct";

  function clampEpiSplitPct(pct) {
    return Math.max(EPI_SPLIT_MIN, Math.min(EPI_SPLIT_MAX, pct));
  }

  function applyEpiSplitPct(pct, invalidate) {
    const value = clampEpiSplitPct(pct);
    document.documentElement.style.setProperty("--epi-panel-width", value + "%");
    if (splitHandle) splitHandle.setAttribute("aria-valuenow", String(Math.round(value)));
    try { localStorage.setItem(EPI_SPLIT_KEY, String(value)); } catch (e) {}
    if (invalidate && activeView === "epi-trends") {
      map.invalidateSize({animate: false});
    }
    return value;
  }

  function readStoredEpiSplit() {
    try {
      const raw = localStorage.getItem(EPI_SPLIT_KEY);
      if (raw == null || raw === "") return 50;
      const n = Number(raw);
      return Number.isFinite(n) ? n : 50;
    } catch (e) {
      return 50;
    }
  }

  applyEpiSplitPct(readStoredEpiSplit(), false);
  if (splitHandle) {
    splitHandle.setAttribute("aria-valuemin", String(EPI_SPLIT_MIN));
    splitHandle.setAttribute("aria-valuemax", String(EPI_SPLIT_MAX));
    let dragging = false;
    function splitFromClientX(clientX) {
      const w = window.innerWidth || document.documentElement.clientWidth || 1;
      // Panel is on the right: width% = distance from right edge.
      return clampEpiSplitPct(((w - clientX) / w) * 100);
    }
    function onPointerMove(e) {
      if (!dragging) return;
      if (e.cancelable) e.preventDefault();
      const x = e.touches && e.touches[0] ? e.touches[0].clientX : e.clientX;
      applyEpiSplitPct(splitFromClientX(x), false);
    }
    function onPointerUp() {
      if (!dragging) return;
      dragging = false;
      document.body.classList.remove("epi-splitting");
      window.removeEventListener("mousemove", onPointerMove);
      window.removeEventListener("mouseup", onPointerUp);
      window.removeEventListener("touchmove", onPointerMove);
      window.removeEventListener("touchend", onPointerUp);
      window.removeEventListener("touchcancel", onPointerUp);
      if (activeView === "epi-trends") map.invalidateSize({animate: false});
    }
    function onPointerDown(e) {
      if (activeView !== "epi-trends") return;
      dragging = true;
      document.body.classList.add("epi-splitting");
      const x = e.touches && e.touches[0] ? e.touches[0].clientX : e.clientX;
      applyEpiSplitPct(splitFromClientX(x), false);
      window.addEventListener("mousemove", onPointerMove);
      window.addEventListener("mouseup", onPointerUp);
      window.addEventListener("touchmove", onPointerMove, {passive: false});
      window.addEventListener("touchend", onPointerUp);
      window.addEventListener("touchcancel", onPointerUp);
      if (e.cancelable) e.preventDefault();
    }
    splitHandle.addEventListener("mousedown", onPointerDown);
    splitHandle.addEventListener("touchstart", onPointerDown, {passive: false});
    splitHandle.addEventListener("keydown", function(e) {
      if (activeView !== "epi-trends") return;
      let delta = 0;
      if (e.key === "ArrowLeft") delta = 2;
      else if (e.key === "ArrowRight") delta = -2;
      else if (e.key === "Home") {
        applyEpiSplitPct(50, true);
        e.preventDefault();
        return;
      } else return;
      const cur = parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--epi-panel-width")
      ) || 50;
      applyEpiSplitPct(cur + delta, true);
      e.preventDefault();
    });
  }

  if (!INVASION_RISK || !Object.keys(INVASION_ZONES).length) {
    if (tab) tab.style.display = "none";
    if (splitHandle) splitHandle.style.display = "none";
    return;
  }
  if (scopeSelect) {
    scopeSelect.innerHTML = INVASION_SCOPES.map(function(s) {
      return "<option value='" + escHtml(s.id) + "'>" + escHtml(s.label) + "</option>";
    }).join("");
    scopeSelect.addEventListener("change", function() {
      epiScopeId = scopeSelect.value || "national";
      setEpiSelected(null);
      recomputeEpiTrends();
      // Fit map to selected province when filtering.
      const scope = epiCurrentScope();
      if (scope && scope.province) {
        const layers = [];
        geoLayer.eachLayer(function(layer) {
          if (layer.feature && layer.feature.properties.province === scope.province) {
            layers.push(layer);
          }
        });
        if (layers.length) {
          const group = L.featureGroup(layers);
          map.fitBounds(group.getBounds(), {padding: [30, 30], maxZoom: 8});
        }
      } else {
        map.setView([INITIAL_VIEW.lat, INITIAL_VIEW.lon], INITIAL_VIEW.zoom);
      }
    });
  }
  document.querySelectorAll(".epi-rank-btn").forEach(function(btn) {
    btn.addEventListener("click", function() {
      epiRankMode = btn.getAttribute("data-rank") || "rr";
      document.querySelectorAll(".epi-rank-btn").forEach(function(b) {
        b.classList.toggle("active", b === btn);
      });
      renderEpiTrendsTable();
    });
  });
  if (tbody) {
    tbody.addEventListener("click", function(e) {
      const tr = e.target.closest("tr[data-nom]");
      if (!tr) return;
      setEpiSelected(tr.getAttribute("data-nom"));
    });
  }
  const epiCases = document.getElementById("epi-show-cases");
  if (epiCases) {
    epiCases.checked = !!(showCasesBox && showCasesBox.checked);
    epiCases.addEventListener("change", function() {
      if (showCasesBox) showCasesBox.checked = epiCases.checked;
      if (activeView === "epi-trends") restoreCaseMarkersForView("epi-trends");
      else syncMarkerToggles("cases");
    });
  }

  function triggerDownload(filename, href) {
    const a = document.createElement("a");
    a.href = href;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  const csvBtn = document.getElementById("epi-download-csv");
  if (csvBtn) {
    csvBtn.addEventListener("click", function() {
      const csv = (INVASION_RISK && INVASION_RISK.download_csv) || "";
      if (!csv) return;
      const blob = new Blob([csv], {type: "text/csv;charset=utf-8"});
      const url = URL.createObjectURL(blob);
      const stamp = (INVASION_RISK.cutoff_date || "data").replace(/-/g, "");
      triggerDownload("invasion_risk_model_estimates_" + stamp + ".csv", url);
      setTimeout(function() { URL.revokeObjectURL(url); }, 1500);
    });
  }

  const mapBtn = document.getElementById("epi-download-map");
  if (mapBtn) {
    mapBtn.addEventListener("click", function() {
      if (typeof html2canvas !== "function") {
        window.alert(t("ui.epi_download_map_unavailable"));
        return;
      }
      const hadCases = map.hasLayer(caseLayer);
      const hadSelection = epiSelectedNom;
      const prevCenter = map.getCenter();
      const prevZoom = map.getZoom();
      clearEpiLinks();
      clearFlowArcs();
      if (hadSelection) setEpiSelected(null);
      if (hadCases) map.removeLayer(caseLayer);
      hideEpiFloat();
      document.body.classList.add("epi-map-exporting");
      map.invalidateSize({animate: false});
      try {
        map.fitBounds(geoLayer.getBounds(), {
          padding: [28, 28],
          animate: false,
          maxZoom: 7,
        });
      } catch (err) {
        map.setView([-2.5, 23.5], 5, {animate: false});
      }
      setTimeout(function() {
        html2canvas(map.getContainer(), {
          useCORS: true,
          allowTaint: true,
          backgroundColor: "#ffffff",
          scale: 2,
        }).then(function(canvas) {
          const jpg = canvas.toDataURL("image/jpeg", 0.92);
          const stamp = (INVASION_RISK && INVASION_RISK.cutoff_date || "map").replace(/-/g, "");
          triggerDownload("invasion_risk_map_" + stamp + ".jpg", jpg);
        }).catch(function(err) {
          console.error(err);
          window.alert(t("ui.epi_download_map_unavailable"));
        }).finally(function() {
          document.body.classList.remove("epi-map-exporting");
          map.invalidateSize({animate: false});
          map.setView(prevCenter, prevZoom, {animate: false});
          if (hadCases && (
            (document.getElementById("epi-show-cases") || {}).checked ||
            (showCasesBox && showCasesBox.checked)
          )) {
            caseLayer.addTo(map);
          }
          if (hadSelection) setEpiSelected(hadSelection);
        });
      }, 180);
    });
  }
})();

// Default: total cases layer, active-case markers ON, flow arcs ON from Mongbwalu.
showCasesBox.checked = true;
caseLayer.addTo(map);

layerSelect.addEventListener("change", function() {
  // OSRM layers (travel time / road distance) render from the origin zone's
  // matrix row, which visually competes with the Flowminder in/out-flow arcs
  // radiating from the same origin — turn the arcs off automatically, then
  // restore the user's Flowminder preference when leaving those layers.
  if (showFlowArcsBox && PAYLOAD.flow_arcs_available && FLOW_ARC_LAYER) {
    if (layerUsesMatrix(getLayer(layerSelect.value))) {
      showFlowArcsBox.checked = false;
    } else if (flowArcsUserPref) {
      showFlowArcsBox.checked = true;
    }
  }
  recompute();
  syncMatrixUi();
});
scaleSelect.addEventListener("change", recompute);

// --- modal wiring (Methods + Terms) ---
function wireModal(modalId, btnId, closeId) {
  const modal = document.getElementById(modalId);
  const btn = document.getElementById(btnId);
  const closeBtn = document.getElementById(closeId);
  if (!modal || !btn) return;
  function close() { modal.classList.remove("open"); }
  btn.addEventListener("click", function() {
    document.querySelectorAll(".modal.open").forEach(m => m.classList.remove("open"));
    modal.classList.add("open");
  });
  closeBtn.addEventListener("click", close);
  modal.addEventListener("click", function(e) {
    if (e.target === modal) close();
  });
}
document.addEventListener("keydown", function(e) {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal.open").forEach(m => m.classList.remove("open"));
  }
});
wireModal("methods-modal", "methods-btn", "methods-close");
wireModal("terms-modal", "terms-btn", "terms-close");

// --- collapsible panels (zone info + layer controls + legend) ---
(function wirePanelToggles() {
  function setCollapsed(panel, btn, collapsed) {
    if (collapsed) {
      panel.classList.add("collapsed");
      btn.textContent = "+";
    } else {
      panel.classList.remove("collapsed");
      btn.textContent = "−";
    }
  }
  const infoPanel = document.getElementById("info");
  const infoBtn = document.getElementById("info-toggle");
  if (infoPanel && infoBtn) {
    infoBtn.addEventListener("click", function() {
      setCollapsed(infoPanel, infoBtn, !infoPanel.classList.contains("collapsed"));
    });
  }
  document.querySelectorAll(".panel-toggle").forEach(function(btn) {
    const panel = document.getElementById(btn.dataset.target);
    if (!panel) return;
    btn.addEventListener("click", function() {
      setCollapsed(panel, btn, !panel.classList.contains("collapsed"));
    });
  });
  if (window.matchMedia && window.matchMedia("(max-width: 700px)").matches) {
    if (infoPanel && infoBtn) setCollapsed(infoPanel, infoBtn, true);
    document.querySelectorAll(".panel-toggle").forEach(function(btn) {
      const panel = document.getElementById(btn.dataset.target);
      if (panel) setCollapsed(panel, btn, true);
    });
  }
})();

// Pre-populate the zone info panel with Mongbwalu.
(function preloadMongbwalu() {
  for (const feat of PAYLOAD.geometry.features) {
    if ((feat.properties.nom || "").toLowerCase() === "mongbalu") {
      document.getElementById("info-body").className = "";
      document.getElementById("info-body").innerHTML = infoHTML(feat);
      return;
    }
  }
})();

(function initDashboardI18n() {
  LAYERS = (I18N.layers && I18N.layers[currentLang]) || PAYLOAD.layers;
  applyStaticI18n();
  rebuildLayerSelect();
  buildTitleSub();
  buildTracker();
  buildModeledEstimateNote();
  updateLegalContent();
  layerSelect.value = "obs::total";
  applyMatrixOriginToLayers();
  rebuildLayerSelect();
  recompute();
  syncMatrixUi();
})();

// --- deep-linking via URL params, e.g. ?genomes=1 or ?cases=1 ---
// Runs last so it overrides the defaults set above (cases ON, flow arcs ON).
(function applyMarkerUrlParams() {
  const params = new URLSearchParams(window.location.search);
  function isTruthy(v) {
    return v !== null && !["0", "false", "no"].includes(v.toLowerCase());
  }
  const genomesParam = params.get("genomes");
  const genomesRequested =
    isTruthy(genomesParam) &&
    PAYLOAD.genome_markers_available &&
    GENOME_SEQUENCES.length &&
    showGenomesBox;
  if (genomesRequested) {
    showGenomesBox.checked = true;
    syncMarkerToggles("genomes"); // also unticks + removes the case-marker layer
    if (showFlowArcsBox) {
      showFlowArcsBox.checked = false;
      flowArcsUserPref = false;
    }
    recompute();
    syncMatrixUi();
    return;
  }
  const casesParam = params.get("cases");
  if (isTruthy(casesParam) && showCasesBox) {
    showCasesBox.checked = true;
    syncMarkerToggles("cases");
  }
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(f"unserializable: {type(o)}")


def load_theme_css() -> str:
    """Optional brand/theme layer (Phase A: tokens + Leaflet; Phase B: panel overrides)."""
    if not THEME_CSS.exists():
        print(f"  NOTE: {THEME_CSS} not found; skipping theme CSS")
        return ""
    css = THEME_CSS.read_text(encoding="utf-8").strip()
    if css:
        print(f"  theme CSS: {THEME_CSS.name} ({len(css)} bytes)")
    return css


def main() -> int:
    payload = build_payload()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload_json = json.dumps(payload, separators=(",", ":"), default=_json_default,
                              allow_nan=False)
    html = HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)
    theme_css = load_theme_css()
    if theme_css:
        html = html.replace(
            "</head>",
            f"<style>\n{theme_css}\n</style>\n</head>",
            1,
        )
    OUTPUT_PATH.write_text(html)
    print(f"\nwrote {OUTPUT_PATH} ({len(html) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
