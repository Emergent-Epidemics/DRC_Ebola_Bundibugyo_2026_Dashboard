"""
"Genomic Epidemiology" page -> output/genomic-epidemiology.html.

No longer a stub: contributes its own right-rail panel shell (via render_page's
page_body seam) and a page-scoped genomic.js that reads the `genomic` payload
slice. Real panels (tree/Ne/distribution), engine map hooks, PearTree, and i18n
arrive in later phases; the markup here is a light-rail skeleton.
"""

from __future__ import annotations

from common.chrome import render_page

VIEW_ID = "genomic-epidemiology"

# Right-rail skeleton. Plain text (no data-i18n yet -- i18n is a later phase).
# genomic.js fills the .gen-body divs from PAYLOAD.genomic.
_BODY = r"""<div id="genomic-panel">
  <div id="genomic-resize" role="separator" aria-orientation="vertical" title="Drag to resize" tabindex="0"></div>
  <section class="gen-card"><h2>Phylogeny</h2><div class="gen-body" id="gen-tree-body">Loading…</div></section>
  <section class="gen-card"><h2>Effective population size</h2><div class="gen-body" id="gen-ne-body">Loading…</div></section>
  <section class="gen-card"><h2>Sample distribution</h2><div class="gen-body" id="gen-dist-body">Loading…</div></section>
</div>"""

_SCRIPTS = '<script src="__ASSETS_PREFIX__genomic.js"></script>'


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, payload, page_body=_BODY, extra_scripts=_SCRIPTS)
