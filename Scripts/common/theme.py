"""JSON serialization helper + optional brand/theme CSS loader (shared)."""

from __future__ import annotations

import numpy as np

from common.paths import THEME_CSS


def json_default(o):
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
