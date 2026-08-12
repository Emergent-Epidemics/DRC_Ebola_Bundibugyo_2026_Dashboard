# Genomic tab Phase 5a — Sample distribution panel

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline) — steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the sample-distribution placeholder with a real chart — confirmed cases by onset date as stacked daily bars (observed base + imputed on top), calendar-X / linear-Y, with **Imputed**, **Beyond** (extend past the tree's latest tip, shaded), and **CSV** export controls, plus a hover tooltip.

**Architecture:** A self-contained SVG renderer in `genomic.js` reading `PAYLOAD.genomic.onset_distribution` (`{dates:[...], national:{date:{observed,imputed}}, beyond_tree_from, source}`). Ported/simplified from the source `timeseries-panel.js`. **Deferred to Phase 5b** (need the tree + coordinator): x-axis lock to the phylogeny transform, per-zone re-scoping, the genomic sample-availability track, brush window, and selected-tip markers. Standalone shows the **national** series with a static domain.

**Tech Stack:** vanilla JS/SVG in `Scripts/assets/genomic.js`; markup in the page module; reuses existing `.gen-chart`/`.gen-toggle`/`.ne-tip` CSS. Verify in-browser.

**Reference:** source `src/timeseries-panel.js` — colours `CONFIRMED_COLOR="#9e2b2b"` (observed), `IMPUTED_COLOR="#587e72"` (imputed); `beyond` extends the domain past the tree's latest tip.

---

## Task 1: Shared toggle-style helper + distribution card markup

**Files:** Modify `Scripts/assets/genomic.js`, `Scripts/pages/genomic_epidemiology.py`

- [ ] **Step 1: Factor the active-toggle styling** (used by Ne and now distribution). In `genomic.js`, add near the top of the IIFE (after `setText`):
```javascript
  // Active toggle = dataset/accent colour + light band shade, set inline `!important`
  // so it beats the brand theme layer's `!important` button rules. Cleared when off.
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
```
Then replace the Ne panel's inline `reflect()` body to call it:
```javascript
      function reflect() { applyToggleStyle(btn, ds.visible, ds.color, ds.band); }
```
(delete the old `btn.classList.toggle(...)`/`setProperty` lines inside `reflect`).

- [ ] **Step 2: Distribution card markup.** In `_BODY` (`genomic_epidemiology.py`), replace the sample-distribution `<section>` with:
```python
  <section class="gen-card" id="gen-dist-card">
    <div class="gen-card-head">
      <h2>Sample distribution</h2>
      <span class="gen-toggles">
        <button type="button" id="gen-dist-imputed" class="gen-toggle" aria-pressed="true" title="Show cases with imputed onset dates">Imputed</button>
        <button type="button" id="gen-dist-beyond" class="gen-toggle" aria-pressed="false" title="Include onset dates after the tree's latest tip">Beyond</button>
        <button type="button" id="gen-dist-csv" class="gen-toggle" title="Download daily counts (CSV)">⤓ CSV</button>
      </span>
    </div>
    <div class="gen-body gen-chart" id="gen-dist-body"></div>
  </section>
```

- [ ] **Step 3: Seam assertion.** In `tests/test_genomic_seam.py`, append to `test_genomic_module_contributes_rail_and_script`:
```python
    assert 'id="gen-dist-imputed"' in html and 'id="gen-dist-csv"' in html   # distribution controls
```

- [ ] **Step 4:** `PYTHONPATH=Scripts python3.9 -m pytest tests/test_genomic_seam.py -q` → PASS. `node --check Scripts/assets/genomic.js`. Commit:
```bash
git add Scripts/assets/genomic.js Scripts/pages/genomic_epidemiology.py tests/test_genomic_seam.py
git commit -m "Genomic distribution panel: card markup (Imputed/Beyond/CSV) + shared toggle-style helper"
```

---

## Task 2: Distribution chart renderer in `genomic.js`

**Files:** Modify `Scripts/assets/genomic.js`

- [ ] **Step 1: Add the renderer** (after `renderNePanel`, before `createGenomicTab`). Full code:
```javascript
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

  function downloadDistCsv(days, source) {
    var rows = ["date,observed,imputed"];
    days.forEach(function (d) { rows.push(d.ds + "," + d.obs + "," + d.imp); });
    var blob = new Blob([rows.join("\n") + "\n"], { type: "text/csv" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = "sample-distribution_" + (source || "national") + ".csv";
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }

  // Renders the sample-distribution panel into #gen-dist-body. Static calendar-X;
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
        var bl = svgEl("text", { x: bx + 3, y: DIST_PAD.top + 9, "font-size": 8, fill: "#9c968b" }); bl.textContent = "beyond tree"; svg.appendChild(bl);
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

    var csvBtn = document.getElementById("gen-dist-csv");
    if (csvBtn) csvBtn.addEventListener("click", function (e) { e.preventDefault(); downloadDistCsv(days, od.source); });

    if (window.ResizeObserver) { new ResizeObserver(render).observe(host); }
    render();
  }
```

- [ ] **Step 2:** In `mount()`, replace the `gen-dist-body` placeholder line:
```javascript
        setText("gen-dist-body", dates
          ? (dates + " onset dates (source " + (od.source || "?") + "); data build " + (data.data_build_date || "?"))
          : "No sample-distribution data");
```
with:
```javascript
        renderDistPanel(data);
```
(The `var od = data.onset_distribution || {}; var dates = ...` lines above it are now unused — remove them if they were only feeding this placeholder; keep `var tips = ...` used by the tree placeholder.)

- [ ] **Step 3:** In `unmount()`, drop `gen-dist-body` from the clear list (leave `gen-tree-body`): `["gen-tree-body"].forEach(...)`.

- [ ] **Step 4:** `node --check Scripts/assets/genomic.js`; `PYTHONPATH=Scripts python3.9 -m pytest tests/ -q` → all pass. Commit:
```bash
git add Scripts/assets/genomic.js
git commit -m "Genomic distribution panel: stacked observed/imputed onset bars (Imputed/Beyond/CSV, hover)"
```

---

## Task 3: Build + browser verify

- [ ] **Step 1:** Rebuild + serve: `cd Scripts && PYTHONPATH=. python3.9 build_dashboard.py && cd ..` (relaunch `cd output && python3.9 -m http.server 8123 &` if down).
- [ ] **Step 2:** In-browser (Chrome MCP), load `genomic-epidemiology.html` and check `#gen-dist-body svg`: expect stacked bars (maroon observed + green imputed) over a calendar x-axis / integer y-axis. Verify: **Imputed** toggle hides/shows the green portion; **Beyond** extends the x-domain past 2026-06-23 with a shaded "beyond tree" region; hover shows date + observed/imputed counts. (CSV triggers a download — don't click it in automation.)
- [ ] **Step 3:** Screenshot the card for the user.
- [ ] **Step 4:** Revert generated output (`git checkout -- output/ ; git clean -fdq output/`); confirm only source committed.

---

## Notes
- Default domain is the tree window (`<= beyond_tree_from`); most onset data is *after* the tree's latest tip, so **Beyond** reveals the bulk of the case curve (expected — the tree lags the linelist).
- Deferred (Phase 5b): per-zone scope, x-lock to the phylogeny, the genomic sample-availability track, brush window, selected-tip markers.
