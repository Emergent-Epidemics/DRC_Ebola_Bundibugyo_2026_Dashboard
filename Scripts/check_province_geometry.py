#!/usr/bin/env python3
"""Report interior rings + sub-threshold detached parts in the province outlines
embedded in a built dashboard page.

Usage:
    python Scripts/check_province_geometry.py [path/to/trends.html]

A clean build (after build_province_boundaries' snap -> union -> strip-slivers)
has 0 interior rings and 0 sub-threshold parts. Run against the FINAL built page
so coordinate rounding is included in what is checked (spec section 10). Exit code
is 0 on PASS, 1 on FAIL, so it can gate CI.
"""
import json
import re
import sys

SLIVER_MAX_DEG2 = 1e-3  # keep in sync with data_sources.PROVINCE_SLIVER_MAX


def ring_area(ring):
    s = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][:2]
        x2, y2 = ring[i + 1][:2]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def main(path):
    with open(path) as fh:
        html = fh.read()
    # Tolerant of attribute order / spacing so a template tweak doesn't falsely fail.
    m = re.search(r'<script\b[^>]*\bid=["\']payload["\'][^>]*>', html)
    if not m:
        print("FAIL: no payload script in", path)
        return 1
    start = m.end()
    end = html.index("</script>", start)
    pb = json.loads(html[start:end]).get("province_boundaries", {})
    feats = pb.get("features", [])

    total_holes = 0
    total_small_parts = 0
    for f in feats:
        g = f["geometry"]
        prov = f["properties"].get("province")
        parts = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        holes = sum(len(p) - 1 for p in parts)
        small_parts = sum(1 for p in parts if ring_area(p[0]) < SLIVER_MAX_DEG2)
        total_holes += holes
        total_small_parts += small_parts
        if holes or small_parts:
            print(f"{prov:24s} holes={holes} small_parts={small_parts}")

    print(f"\n{len(feats)} provinces; interior rings={total_holes}, "
          f"sub-threshold parts={total_small_parts}")
    ok = total_holes == 0 and total_small_parts == 0
    print("PASS" if ok else "FAIL: sliver artefacts remain")
    return 0 if ok else 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "trends.html"
    sys.exit(main(target))
