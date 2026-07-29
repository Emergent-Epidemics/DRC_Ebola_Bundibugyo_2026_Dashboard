#!/usr/bin/env python3
"""
Build the DRC Ebola Bundibugyo 2026 dashboard as four HTML pages (Current
snapshot, Spatial risk, Epidemiological trends, Context) from publicly
available inputs.

This is the master/orchestrator script in the multi-page dashboard
structure (see README "Multi-page structure"). It:

  1. Loads all source data and builds the one shared JSON payload
     (common/payload.py) -- still shared across all four pages for now,
     since the JS engine reads fields from all of them regardless of which
     page is open (e.g. the Trends page reads PAYLOAD.confirmed_timeseries,
     the Context page reads PAYLOAD.phr_context, etc).
  2. Writes the shared static assets once: assets/dashboard.css (base
     stylesheet + optional brand theme layer) and assets/engine.js (the
     shared JS engine).
  3. Calls each page module in Scripts/pages/ to render its page and writes
     the result to output/<page>.html.

Usage
-----
    python build_dashboard.py

Layout
------
    project_root/
    ├── Scripts/
    │   ├── build_dashboard.py         (this file -- master/orchestrator)
    │   ├── common/                    shared data loading, payload, chrome
    │   ├── assets/                    shared dashboard.css + engine.js (source)
    │   └── pages/                     one module per page (snapshot, spatial_risk,
    │                                   trends, context)
    ├── Data/                          (see original docstring in
    │                                   common/data_sources.py for the full
    │                                   Data/ layout)
    └── output/
        ├── index.html                 Current snapshot (was the "map" tab)
        ├── spatial-risk.html          Spatial risk (was the "epi-trends" tab)
        ├── trends.html                Epidemiological trends
        ├── spatial-risk.html          Spatial risk
        ├── context.html               Public health context
        ├── clinical-symptoms.html     Clinical symptoms (coming soon)
        ├── surveillance-testing.html  Surveillance and testing (coming soon)
        ├── genomic-epidemiology.html  Genomic epidemiology (coming soon)
        └── assets/
            ├── dashboard.css
            └── engine.js

Set the ``DATA_ROOT`` environment variable to override the default Data/
location (useful when testing from a different working directory).

Inputs are tolerated when missing: the corresponding layers / sections are
hidden and a warning is printed.
"""

from __future__ import annotations

from common.paths import OUTPUT_DIR, ASSETS_DIRNAME, PAGE_FILENAMES, SCRIPT_DIR
from common.payload import build_shared_payload
from common.theme import load_theme_css
from pages import (
    snapshot, spatial_risk, trends, context,
    clinical_symptoms, surveillance_testing, genomic_epidemiology,
)

PAGE_MODULES = [
    snapshot, trends, spatial_risk, context,
    clinical_symptoms, surveillance_testing, genomic_epidemiology,
]


def _write_shared_assets(assets_dir) -> tuple[int, int]:
    base_css = (SCRIPT_DIR / "assets" / "dashboard.css").read_text(encoding="utf-8")
    theme_css = load_theme_css()
    css = base_css if not theme_css else f"{base_css}\n\n/* --- theme overrides --- */\n{theme_css}\n"
    (assets_dir / "dashboard.css").write_text(css, encoding="utf-8")

    engine_js = (SCRIPT_DIR / "assets" / "engine.js").read_text(encoding="utf-8")
    (assets_dir / "engine.js").write_text(engine_js, encoding="utf-8")

    return len(css.encode("utf-8")), len(engine_js.encode("utf-8"))


def main() -> int:
    payload = build_shared_payload()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assets_dir = OUTPUT_DIR / ASSETS_DIRNAME
    assets_dir.mkdir(parents=True, exist_ok=True)

    css_bytes, js_bytes = _write_shared_assets(assets_dir)
    print(f"\n  wrote {assets_dir / 'dashboard.css'} ({css_bytes / 1e3:.0f} KB)")
    print(f"  wrote {assets_dir / 'engine.js'} ({js_bytes / 1e3:.0f} KB)")

    total_bytes = 0
    for module in PAGE_MODULES:
        html = module.build_page(payload)
        out_path = OUTPUT_DIR / PAGE_FILENAMES[module.VIEW_ID]
        out_path.write_text(html, encoding="utf-8")
        total_bytes += len(html.encode("utf-8"))
        print(f"  wrote {out_path} ({len(html.encode('utf-8')) / 1e6:.2f} MB)")

    grand_total = total_bytes + css_bytes + js_bytes
    print(f"\ntotal: {grand_total / 1e6:.1f} MB across {len(PAGE_MODULES)} pages + shared assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
