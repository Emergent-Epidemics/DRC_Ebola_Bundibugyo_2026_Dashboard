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

# Page-scoped CSP: PearTree's bundle injects an `@import` to fonts.googleapis.com
# (+ a gstatic font fetch). `font-src 'self' data:` blocks the font download so no
# external request leaves the page; the tree falls back to the system font stack
# (which is what every other panel uses anyway). Only font loading is restricted --
# scripts/styles/images stay unconstrained (no default-src), so the rest of the
# page (Leaflet, html2canvas) is unaffected. Proven in the Phase 0 spike.
_HEAD = r"""<meta http-equiv="Content-Security-Policy" content="font-src 'self' data:;" />"""

# Right-rail skeleton. Plain text (no data-i18n yet -- i18n is a later phase).
# genomic.js fills the .gen-body divs from PAYLOAD.genomic.
_BODY = r"""<div id="genomic-panel">
  <div id="genomic-resize" role="separator" aria-orientation="vertical" title="Drag to resize" tabindex="0"></div>
  <section class="gen-card gen-tree-card" id="gen-tree-card">
    <div class="gen-card-head">
      <h2>Phylogeny</h2>
      <span class="gen-toggles">
        <button type="button" id="gen-tree-legend" class="gen-toggle" aria-pressed="false" title="Show/hide the health-zone colour legend">Legend</button>
        <button type="button" id="gen-tree-nodebars" class="gen-toggle" aria-pressed="true" title="Show/hide node confidence (95% HPD) bars">Node Bars</button>
        <button type="button" id="gen-tree-tiplabels" class="gen-toggle" aria-pressed="true" title="Show/hide health-zone tip labels">Tip Labels</button>
      </span>
    </div>
    <div class="gen-tree-wrap">
      <div class="gen-body gen-tree-body" id="gen-tree-body">Loading…</div>
      <div class="gen-tree-legend-box" id="gen-tree-legend-box" hidden></div>
    </div>
  </section>
  <section class="gen-card" id="gen-ne-card">
    <div class="gen-card-head">
      <h2>Effective population size</h2>
      <span class="gen-toggles">
        <button type="button" id="gen-ne-skygrid" class="gen-toggle" aria-pressed="true">SkyGrid</button>
        <button type="button" id="gen-ne-exp" class="gen-toggle" aria-pressed="true">Exp</button>
      </span>
    </div>
    <div class="gen-body gen-chart" id="gen-ne-body"></div>
  </section>
  <section class="gen-card" id="gen-dist-card">
    <div class="gen-card-head">
      <h2>Confirmed positive cases</h2>
      <span class="gen-toggles">
        <button type="button" id="gen-dist-imputed" class="gen-toggle" aria-pressed="true" title="Show cases with imputed onset dates">Imputed</button>
        <button type="button" id="gen-dist-beyond" class="gen-toggle" aria-pressed="false" title="Include onset dates after the tree's latest tip">Look beyond</button>
      </span>
    </div>
    <div class="gen-body gen-chart" id="gen-dist-body"></div>
  </section>
</div>"""

# PearTree bundle exposes window.PearTreeEmbed; it MUST load before genomic.js,
# which calls PearTreeEmbed.embed() to render the phylogeny.
_SCRIPTS = (
    '<script src="__ASSETS_PREFIX__peartree.bundle.min.js"></script>\n'
    '<script src="__ASSETS_PREFIX__genomic.js"></script>'
)


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, payload, page_body=_BODY,
                       extra_scripts=_SCRIPTS, extra_head=_HEAD)
