"""
"Spatial risk" page (formerly the "epi-trends" tab) -> output/spatial-risk.html.

See pages/snapshot.py for why this is currently a thin wrapper around the
shared payload + engine.
"""

from __future__ import annotations

from common.chrome import render_page

VIEW_ID = "epi-trends"


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, payload)
