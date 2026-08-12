// Genomic Epidemiology tab — Phase 3 seam skeleton.
// Reads the page-scoped `genomic` payload slice and renders placeholder content
// into the rail, proving data flows through the contribution seam end-to-end.
// Shaped as a mount()/unmount() tab module for SPA-readiness; real panels,
// coordinator, and shared-map integration come in later phases.
(function () {
  "use strict";

  function setText(id, t) { var e = document.getElementById(id); if (e) e.textContent = t; }

  function readGenomic() {
    var el = document.getElementById("payload");
    if (!el) return null;
    try { return (JSON.parse(el.textContent) || {}).genomic || null; } catch (e) { return null; }
  }

  function createGenomicTab(ctx) {
    var data = (ctx && ctx.data) || {};
    return {
      mount: function () {
        var tips = (data.tips || []).length;
        var od = data.onset_distribution || {};
        var dates = (od.dates || []).length;
        setText("gen-tree-body", tips ? (tips + " sequences loaded — tree rendering pending") : "No genomic data");
        setText("gen-ne-body", data.skygrid ? "SkyGrid + exponential estimates loaded" : "No Ne data");
        setText("gen-dist-body", dates
          ? (dates + " onset dates (source " + (od.source || "?") + "); data build " + (data.data_build_date || "?"))
          : "No sample-distribution data");
      },
      unmount: function () {
        ["gen-tree-body", "gen-ne-body", "gen-dist-body"].forEach(function (id) { setText(id, ""); });
      }
    };
  }

  function boot() {
    if (document.body.getAttribute("data-initial-view") !== "genomic-epidemiology") return;
    var tab = createGenomicTab({ data: readGenomic() });
    tab.mount();
    window.__genomicTab = tab;   // exposed for later engine/coordinator integration
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
