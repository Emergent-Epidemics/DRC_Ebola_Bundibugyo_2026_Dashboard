"""
"Context" page (formerly the "context" tab) -> output/context.html.

See pages/snapshot.py for why this is currently a thin wrapper around the
shared payload + engine. Note this view still needs the Leaflet map
(health-zone clicks drive which context panel is shown) -- see README.
"""

from __future__ import annotations

from common.chrome import render_page

VIEW_ID = "context"


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, payload)
