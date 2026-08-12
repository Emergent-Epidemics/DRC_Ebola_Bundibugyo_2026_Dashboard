// Genomic Epidemiology tab — Phase 3 seam skeleton.
// Reads the page-scoped `genomic` payload slice and renders placeholder content
// into the rail, proving data flows through the contribution seam end-to-end.
// Shaped as a mount()/unmount() tab module for SPA-readiness; real panels,
// coordinator, and shared-map integration come in later phases.
(function () {
  "use strict";

  function setText(id, t) { var e = document.getElementById(id); if (e) e.textContent = t; }

  // Active toggle = accent colour + light band shade, set inline `!important` so it
  // beats the brand theme layer's `!important` button rules. Cleared when off.
  function applyToggleStyle(btn, on, color, band) {
    if (!btn) return;
    btn.classList.toggle("active", on);
    if (on) {
      btn.style.setProperty("color", color, "important");
      btn.style.setProperty("border-color", color, "important");
      btn.style.setProperty("background", band, "important");
    } else {
      btn.style.removeProperty("color");
      btn.style.removeProperty("border-color");
      btn.style.removeProperty("background");
    }
    btn.setAttribute("aria-pressed", String(on));
  }

  function readGenomic() {
    var el = document.getElementById("payload");
    if (!el) return null;
    try { return (JSON.parse(el.textContent) || {}).genomic || null; } catch (e) { return null; }
  }

  // --- log-Y helpers (ported verbatim from the source log-scale.js) ---
  function niceLogRange(lo, hi) {
    if (!(lo > 0) || !(hi > 0)) return [1, 10];
    var a = Math.pow(10, Math.floor(Math.log10(Math.min(lo, hi))));
    var b = Math.pow(10, Math.ceil(Math.log10(Math.max(lo, hi))));
    if (b <= a) b = a * 10;
    return [a, b];
  }
  function logTicks(min, max) {
    var lo = Math.round(Math.log10(min)), hi = Math.round(Math.log10(max)), ticks = [];
    for (var d = lo; d <= hi; d++) ticks.push(Math.pow(10, d));
    return ticks;
  }
  function fmtNe(v) { return v >= 1 ? String(Math.round(v)) : String(v); }
  var SVNS = "http://www.w3.org/2000/svg";
  function svgEl(name, attrs) {
    var n = document.createElementNS(SVNS, name);
    for (var k in attrs) n.setAttribute(k, String(attrs[k]));
    return n;
  }
  var NE_PAD = { left: 42, right: 12, top: 12, bottom: 22 };
  function fmtDay(t) { return new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "short" }); }

  // Renders the Ne panel into #gen-ne-body. Static calendar-X (root->mostRecent);
  // tree-lock/brush/markers are added with the coordinator in a later phase.
  function renderNePanel(genomic) {
    var host = document.getElementById("gen-ne-body");
    if (!host) return;
    var sg = genomic.skygrid, ex = genomic.exponential;
    if (!sg && !ex) { host.textContent = "No Ne data"; return; }
    var meta = sg || ex;
    var datasets = [
      sg && { key: "skygrid", label: "SkyGrid", color: "#587e72", band: "rgba(88,126,114,0.15)", btnId: "gen-ne-skygrid", data: sg },
      ex && { key: "exp", label: "Exp", color: "#7c1d1d", band: "rgba(124,29,29,0.12)", btnId: "gen-ne-exp", data: ex }
    ].filter(Boolean);
    datasets.forEach(function (ds) {
      ds.pts = ds.data.points.map(function (p) { return { t: +new Date(p.date), med: p.neMedian, lo: p.neLower, hi: p.neUpper }; });
      ds.visible = true;
    });

    var xMin = +new Date(meta.rootDate), xMax = +new Date(meta.mostRecentDate);
    var tip = document.createElement("div"); tip.className = "ne-tip"; tip.style.display = "none";

    function yDomain() {
      var los = [], his = [];
      datasets.filter(function (d) { return d.visible; }).forEach(function (d) {
        d.pts.forEach(function (p) { if (p.t >= xMin && p.t <= xMax) { if (p.lo > 0) los.push(p.lo); his.push(p.hi); } });
      });
      if (!los.length) return [1, 10];
      return niceLogRange(Math.min.apply(null, los), Math.max.apply(null, his));
    }

    function render() {
      var W = host.clientWidth || 320, H = host.clientHeight || 180;
      var yd = yDomain(), yMin = yd[0], yMax = yd[1];
      var xToPx = function (t) { return NE_PAD.left + ((t - xMin) / (xMax - xMin)) * (W - NE_PAD.left - NE_PAD.right); };
      var pxToDate = function (px) { return xMin + ((px - NE_PAD.left) / (W - NE_PAD.left - NE_PAD.right)) * (xMax - xMin); };
      var yOf = function (ne) {
        var lo = Math.log10(yMin), hi = Math.log10(yMax), v = Math.log10(Math.max(ne, Number.MIN_VALUE));
        return (H - NE_PAD.bottom) - ((v - lo) / (hi - lo)) * ((H - NE_PAD.bottom) - NE_PAD.top);
      };
      host.replaceChildren();
      var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none" });

      logTicks(yMin, yMax).forEach(function (tk) {
        var y = yOf(tk);
        svg.appendChild(svgEl("line", { x1: NE_PAD.left, y1: y, x2: W - NE_PAD.right, y2: y, stroke: "#eee", "stroke-width": 1 }));
        var lbl = svgEl("text", { x: NE_PAD.left - 4, y: y + 3, "font-size": 9, fill: "#9c968b", "text-anchor": "end" });
        lbl.textContent = fmtNe(tk); svg.appendChild(lbl);
      });

      var baseY = H - NE_PAD.bottom;
      svg.appendChild(svgEl("line", { x1: NE_PAD.left, y1: baseY, x2: W - NE_PAD.right, y2: baseY, stroke: "#c9c7c2", "stroke-width": 1 }));
      var nT = Math.max(2, Math.min(6, Math.floor((W - NE_PAD.left) / 80)));
      for (var i = 0; i <= nT; i++) {
        var t = xMin + ((xMax - xMin) * i) / nT, x = xToPx(t);
        svg.appendChild(svgEl("line", { x1: x, y1: baseY, x2: x, y2: baseY + 3, stroke: "#c9c7c2", "stroke-width": 1 }));
        var xl = svgEl("text", { x: x, y: baseY + 13, "font-size": 9, fill: "#9c968b", "text-anchor": "middle" });
        xl.textContent = fmtDay(t); svg.appendChild(xl);
      }

      datasets.forEach(function (ds) {
        if (!ds.visible) return;
        var d = "";
        ds.pts.forEach(function (p, i) { d += (i ? "L" : "M") + xToPx(p.t) + "," + yOf(p.hi) + " "; });
        for (var j = ds.pts.length - 1; j >= 0; j--) d += "L" + xToPx(ds.pts[j].t) + "," + yOf(ds.pts[j].lo) + " ";
        svg.appendChild(svgEl("path", { d: d + "Z", fill: ds.band, stroke: "none" }));
        var m = "";
        ds.pts.forEach(function (p, i) { m += (i ? "L" : "M") + xToPx(p.t) + "," + yOf(p.med) + " "; });
        svg.appendChild(svgEl("path", { d: m, fill: "none", stroke: ds.color, "stroke-width": 1.6 }));
      });
      host.appendChild(svg);
      host.appendChild(tip);

      svg.addEventListener("mousemove", function (ev) {
        var mx = ev.clientX - host.getBoundingClientRect().left;
        var vis = datasets.filter(function (d) { return d.visible; });
        if (!vis.length || mx < NE_PAD.left || mx > W - NE_PAD.right) { tip.style.display = "none"; return; }
        var dateMs = pxToDate(mx), html = '<div class="ne-tip-d">' + fmtDay(dateMs) + "</div>";
        vis.forEach(function (ds) {
          var best = null, bd = Infinity;
          ds.pts.forEach(function (p) { var dd = Math.abs(p.t - dateMs); if (dd < bd) { bd = dd; best = p; } });
          if (best) html += '<div><span style="color:' + ds.color + '">' + ds.label + "</span> <b>" + best.med.toPrecision(3) + "</b> " +
            '<span class="ne-tip-ci">(' + best.lo.toPrecision(2) + "–" + best.hi.toPrecision(2) + ")</span></div>";
        });
        tip.innerHTML = html; tip.style.display = ""; tip.style.left = Math.min(mx + 8, W - 130) + "px"; tip.style.top = (NE_PAD.top + 4) + "px";
      });
      svg.addEventListener("mouseleave", function () { tip.style.display = "none"; });
    }

    datasets.forEach(function (ds) {
      var btn = document.getElementById(ds.btnId);
      if (!btn) return;
      function reflect() { applyToggleStyle(btn, ds.visible, ds.color, ds.band); }
      reflect();
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var visCount = datasets.filter(function (d) { return d.visible; }).length;
        if (ds.visible && visCount <= 1) return;   // keep at least one visible
        ds.visible = !ds.visible;
        reflect();
        render();
      });
    });

    if (window.ResizeObserver) { new ResizeObserver(render).observe(host); }
    render();
  }

  var DIST_PAD = { left: 34, right: 14, top: 12, bottom: 22 };
  var DIST_OBS = "#9e2b2b", DIST_IMP = "#587e72";

  function niceLinearTicks(max) {
    max = Math.max(1, max);
    var raw = max / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var step = mag; if (raw / mag >= 5) step = 5 * mag; else if (raw / mag >= 2) step = 2 * mag;
    step = Math.max(1, Math.round(step));
    var ticks = []; for (var v = 0; v <= max + step * 0.001; v += step) ticks.push(v);
    return ticks;
  }

  // Renders the confirmed-positive-cases panel into #gen-dist-body. Static calendar-X;
  // per-zone scope, tree-lock, sequence track, brush, and markers are Phase 5b.
  function renderDistPanel(genomic) {
    var host = document.getElementById("gen-dist-body");
    if (!host) return;
    var od = genomic.onset_distribution;
    if (!od || !od.dates || !od.dates.length) { host.textContent = "No sample-distribution data"; return; }
    var series = od.national || {};
    var beyondFrom = od.beyond_tree_from ? +new Date(od.beyond_tree_from) : Infinity;
    var showImputed = true, showBeyond = false;
    var days = od.dates.map(function (d) {
      var c = series[d] || { observed: 0, imputed: 0 };
      return { t: +new Date(d), ds: d, obs: c.observed || 0, imp: c.imputed || 0 };
    });
    var tip = document.createElement("div"); tip.className = "ne-tip"; tip.style.display = "none";

    function render() {
      var W = host.clientWidth || 320, H = host.clientHeight || 180;
      var vis = days.filter(function (d) { return showBeyond || d.t <= beyondFrom; });
      if (!vis.length) vis = days;
      var t0 = Math.min.apply(null, vis.map(function (d) { return d.t; }));
      var t1 = Math.max.apply(null, vis.map(function (d) { return d.t; }));
      var xToPx = function (t) { return DIST_PAD.left + ((t - t0) / ((t1 - t0) || 1)) * (W - DIST_PAD.left - DIST_PAD.right); };
      var yMax = Math.max(1, Math.max.apply(null, vis.map(function (d) { return d.obs + (showImputed ? d.imp : 0); })));
      var baseY = H - DIST_PAD.bottom;
      var yToPx = function (v) { return baseY - (v / yMax) * (baseY - DIST_PAD.top); };
      var spanDays = Math.max(1, (t1 - t0) / 86400000);
      var barW = Math.max(1, (W - DIST_PAD.left - DIST_PAD.right) / (spanDays + 1) - 1);

      host.replaceChildren();
      var svg = svgEl("svg", { viewBox: "0 0 " + W + " " + H, preserveAspectRatio: "none" });

      if (showBeyond && isFinite(beyondFrom) && beyondFrom > t0 && beyondFrom < t1) {
        var bx = xToPx(beyondFrom);
        svg.appendChild(svgEl("rect", { x: bx, y: DIST_PAD.top, width: Math.max(0, (W - DIST_PAD.right) - bx), height: baseY - DIST_PAD.top, fill: "rgba(0,0,0,0.04)" }));
        var blab = svgEl("text", { x: bx + 3, y: DIST_PAD.top + 9, "font-size": 8, fill: "#9c968b" }); blab.textContent = "beyond tree"; svg.appendChild(blab);
      }

      niceLinearTicks(yMax).forEach(function (v) {
        var y = yToPx(v);
        svg.appendChild(svgEl("line", { x1: DIST_PAD.left, y1: y, x2: W - DIST_PAD.right, y2: y, stroke: "#eee", "stroke-width": 1 }));
        var lbl = svgEl("text", { x: DIST_PAD.left - 4, y: y + 3, "font-size": 9, fill: "#9c968b", "text-anchor": "end" }); lbl.textContent = String(v); svg.appendChild(lbl);
      });

      svg.appendChild(svgEl("line", { x1: DIST_PAD.left, y1: baseY, x2: W - DIST_PAD.right, y2: baseY, stroke: "#c9c7c2", "stroke-width": 1 }));
      var nT = Math.max(2, Math.min(6, Math.floor((W - DIST_PAD.left) / 80)));
      for (var i = 0; i <= nT; i++) {
        var t = t0 + ((t1 - t0) * i) / nT, x = xToPx(t);
        svg.appendChild(svgEl("line", { x1: x, y1: baseY, x2: x, y2: baseY + 3, stroke: "#c9c7c2", "stroke-width": 1 }));
        var xl = svgEl("text", { x: x, y: baseY + 13, "font-size": 9, fill: "#9c968b", "text-anchor": "middle" }); xl.textContent = fmtDay(t); svg.appendChild(xl);
      }

      vis.forEach(function (d) {
        var x = xToPx(d.t) - barW / 2;
        if (d.obs > 0) svg.appendChild(svgEl("rect", { x: x, y: yToPx(d.obs), width: barW, height: baseY - yToPx(d.obs), fill: DIST_OBS }));
        if (showImputed && d.imp > 0) {
          var yTop = yToPx(d.obs + d.imp), yBase = yToPx(d.obs);
          svg.appendChild(svgEl("rect", { x: x, y: yTop, width: barW, height: yBase - yTop, fill: DIST_IMP }));
        }
      });
      host.appendChild(svg); host.appendChild(tip);

      svg.addEventListener("mousemove", function (ev) {
        var mx = ev.clientX - host.getBoundingClientRect().left;
        var best = null, bd = Infinity;
        vis.forEach(function (d) { var dd = Math.abs(xToPx(d.t) - mx); if (dd < bd) { bd = dd; best = d; } });
        if (!best || bd > Math.max(barW, 8)) { tip.style.display = "none"; return; }
        var html = '<div class="ne-tip-d">' + fmtDay(best.t) + "</div>" +
          '<div><span style="color:' + DIST_OBS + '">observed</span> <b>' + best.obs + "</b></div>";
        if (showImputed) html += '<div><span style="color:' + DIST_IMP + '">imputed</span> <b>' + best.imp + "</b></div>";
        tip.innerHTML = html; tip.style.display = ""; tip.style.left = Math.min(mx + 8, W - 120) + "px"; tip.style.top = (DIST_PAD.top + 4) + "px";
      });
      svg.addEventListener("mouseleave", function () { tip.style.display = "none"; });
    }

    var impBtn = document.getElementById("gen-dist-imputed");
    applyToggleStyle(impBtn, showImputed, DIST_IMP, "rgba(88,126,114,0.15)");
    if (impBtn) impBtn.addEventListener("click", function (e) { e.preventDefault(); showImputed = !showImputed; applyToggleStyle(impBtn, showImputed, DIST_IMP, "rgba(88,126,114,0.15)"); render(); });

    var beyBtn = document.getElementById("gen-dist-beyond");
    applyToggleStyle(beyBtn, showBeyond, "#9b7d4e", "rgba(155,125,78,0.12)");
    if (beyBtn) beyBtn.addEventListener("click", function (e) { e.preventDefault(); showBeyond = !showBeyond; applyToggleStyle(beyBtn, showBeyond, "#9b7d4e", "rgba(155,125,78,0.12)"); render(); });

    if (window.ResizeObserver) { new ResizeObserver(render).observe(host); }
    render();
  }

  function createGenomicTab(ctx) {
    var data = (ctx && ctx.data) || {};
    return {
      mount: function () {
        var tips = (data.tips || []).length;
        setText("gen-tree-body", tips ? (tips + " sequences loaded — tree rendering pending") : "No genomic data");
        renderNePanel(data);
        renderDistPanel(data);
      },
      unmount: function () {
        ["gen-tree-body"].forEach(function (id) { setText(id, ""); });
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
