"""
"Genomic Epidemiology" page -> output/genomic-epidemiology.html.

Placeholder/"coming soon" page for now -- see STUB_VIEWS in common/chrome.py
for how the stub panel and hiding of the map/other panels works.
"""

from __future__ import annotations

from common.chrome import render_page

VIEW_ID = "genomic-epidemiology"


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, payload)
