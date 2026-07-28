"""
"Epidemiological trends" page (formerly the "trends" tab) -> output/trends.html.

See pages/snapshot.py for why this is currently a thin wrapper around the
shared payload + engine. Note this view still needs the Leaflet map (province
outlines / health-zone clicks drive the plot selection) -- see README.
"""

from __future__ import annotations

from common.chrome import render_page

VIEW_ID = "trends"


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, payload)
