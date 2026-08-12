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

  // Drag-to-resize the right rail; width persisted per browser (like the
  // Trends/Spatial-Risk rails). Clamped to a sensible range.
  var WIDTH_KEY = "bdbv_genomic_rail_width_px";
  var MIN_W = 320;
  function maxW() { return Math.round(window.innerWidth * 0.7); }
  function applyWidth(px) {
    var panel = document.getElementById("genomic-panel");
    if (!panel) return;
    px = Math.max(MIN_W, Math.min(maxW(), px));
    panel.style.width = px + "px";
  }
  function initResize() {
    var panel = document.getElementById("genomic-panel");
    var handle = document.getElementById("genomic-resize");
    if (!panel || !handle) return;
    var stored = parseFloat(localStorage.getItem(WIDTH_KEY) || "");
    if (isFinite(stored)) applyWidth(stored);

    var dragging = false;
    function onMove(e) {
      if (!dragging) return;
      applyWidth(window.innerWidth - e.clientX);   // rail hugs the right edge
      e.preventDefault();
    }
    function onUp() {
      if (!dragging) return;
      dragging = false;
      document.body.classList.remove("genomic-resizing");
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      try { localStorage.setItem(WIDTH_KEY, String(parseInt(panel.style.width, 10) || MIN_W)); } catch (e) {}
    }
    handle.addEventListener("mousedown", function (e) {
      dragging = true;
      document.body.classList.add("genomic-resizing");
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
      e.preventDefault();
    });
    // Keyboard resize for accessibility (± 20px on arrow keys).
    handle.addEventListener("keydown", function (e) {
      var cur = parseInt(panel.style.width, 10) || panel.getBoundingClientRect().width;
      if (e.key === "ArrowLeft") { applyWidth(cur + 20); e.preventDefault(); }
      else if (e.key === "ArrowRight") { applyWidth(cur - 20); e.preventDefault(); }
      else return;
      try { localStorage.setItem(WIDTH_KEY, String(parseInt(panel.style.width, 10))); } catch (err) {}
    });
  }

  function boot() {
    if (document.body.getAttribute("data-initial-view") !== "genomic-epidemiology") return;
    var tab = createGenomicTab({ data: readGenomic() });
    tab.mount();
    initResize();
    window.__genomicTab = tab;   // exposed for later engine/coordinator integration
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
