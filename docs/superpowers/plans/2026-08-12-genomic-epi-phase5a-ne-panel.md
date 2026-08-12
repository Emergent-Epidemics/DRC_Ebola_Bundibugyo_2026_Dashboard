# Genomic tab Phase 5a — Effective population size (Ne) panel

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline) — steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the Ne placeholder card with a real chart — SkyGrid + exponential-growth Ne trajectories (median line + 95% HPD ribbon) on a log-Y / calendar-X axis, with Exp/SkyGrid toggles and a hover tooltip.

**Architecture:** A self-contained SVG renderer in `genomic.js` reading `PAYLOAD.genomic.skygrid` / `.exponential` (each `{points:[{date,neMedian,neLower,neUpper}], rootDate, mostRecentDate, cutOffYears}`). Ported/simplified from the source `ne-panel.js`: **static** calendar-X (rootDate→mostRecentDate), no tree-lock/brush/selected-tip markers (those are Phase 5b, once the tree + coordinator exist). Light theme (warm palette).

**Tech Stack:** vanilla JS/SVG in `Scripts/assets/genomic.js`; markup in the page module; CSS in `dashboard.css`. Verify in-browser (SVG isn't pytest-testable; a seam test asserts the toggle markup).

**Reference:** source `src/ne-panel.js` (render loop, ribbon/line path building, hover) and `src/log-scale.js` (`niceLogRange`/`logTicks`/`fmtNe`, ported verbatim below).

**Colours:** SkyGrid `#587e72` (green) band `rgba(88,126,114,0.15)`; Exponential `#7c1d1d` (maroon) band `rgba(124,29,29,0.12)`.

---

## Task 1: Ne card markup + CSS

**Files:** Modify `Scripts/pages/genomic_epidemiology.py`, `Scripts/assets/dashboard.css`

- [ ] **Step 1:** In `_BODY`, replace the Ne `<section>` with a header carrying the two toggles + a chart holder:
```python
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
```

- [ ] **Step 2:** Append to the genomic CSS block in `dashboard.css`:
```css
  #genomic-panel .gen-card-head { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:6px; }
  #genomic-panel .gen-card-head h2 { margin:0; }
  #genomic-panel .gen-toggles { display:flex; gap:4px; }
  #genomic-panel .gen-toggle {
    font-size:11px; padding:2px 7px; border:1px solid #e7e3db; border-radius:4px;
    background:#fff; color:#9c968b; cursor:pointer;
  }
  #genomic-panel .gen-toggle.active { font-weight:600; }
  #genomic-panel .gen-chart { position:relative; height:180px; min-height:180px; }
  #genomic-panel .gen-chart svg { display:block; width:100%; height:100%; }
  #genomic-panel .ne-tip {
    position:absolute; pointer-events:none; background:rgba(255,255,255,0.97);
    border:1px solid #e7e3db; border-radius:6px; padding:4px 7px; font-size:10.5px;
    color:#2a2a27; white-space:nowrap; box-shadow:0 1px 3px rgba(0,0,0,0.12);
  }
  #genomic-panel .ne-tip-d { font-weight:700; margin-bottom:2px; }
  #genomic-panel .ne-tip-ci { color:#9c968b; }
```

- [ ] **Step 3:** Add a seam assertion (append to `test_genomic_module_contributes_rail_and_script` in `tests/test_genomic_seam.py`):
```python
    assert 'id="gen-ne-skygrid"' in html and 'id="gen-ne-exp"' in html   # Ne toggles present
```

- [ ] **Step 4:** Run `PYTHONPATH=Scripts python3.9 -m pytest tests/test_genomic_seam.py -q` → PASS. Commit:
```bash
git add Scripts/pages/genomic_epidemiology.py Scripts/assets/dashboard.css tests/test_genomic_seam.py
git commit -m "Genomic Ne panel: card markup (SkyGrid/Exp toggles) + chart styling"
```

---

## Task 2: Ne chart renderer in `genomic.js`

**Files:** Modify `Scripts/assets/genomic.js`

- [ ] **Step 1:** Add the renderer (inside the IIFE, before `boot`). Full code:
```javascript
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

  // Renders the Ne panel into #gen-ne-body. Static calendar-X (root→mostRecent);
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
    var host2 = host;
    var tip = document.createElement("div"); tip.className = "ne-tip"; tip.style.display = "none";

    function yDomain() {
      var vis = datasets.filter(function (d) { return d.visible; });
      var los = [], his = [];
      vis.forEach(function (d) { d.pts.forEach(function (p) { if (p.t >= xMin && p.t <= xMax) { if (p.lo > 0) los.push(p.lo); his.push(p.hi); } }); });
      if (!los.length) return [1, 10];
      return niceLogRange(Math.min.apply(null, los), Math.max.apply(null, his));
    }

    function render() {
      var W = host2.clientWidth || 320, H = host2.clientHeight || 180;
      var yd = yDomain(), yMin = yd[0], yMax = yd[1];
      var xToPx = function (t) { return NE_PAD.left + ((t - xMin) / (xMax - xMin)) * (W - NE_PAD.left - NE_PAD.right); };
      var pxToDate = function (px) { return xMin + ((px - NE_PAD.left) / (W - NE_PAD.left - NE_PAD.right)) * (xMax - xMin); };
      var yOf = function (ne) {
        var lo = Math.log10(yMin), hi = Math.log10(yMax), v = Math.log10(Math.max(ne, Number.MIN_VALUE));
        return (H - NE_PAD.bottom) - ((v - lo) / (hi - lo)) * ((H - NE_PAD.bottom) - NE_PAD.top);
      };
      host2.replaceChildren();
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
      host2.appendChild(svg);
      host2.appendChild(tip);

      svg.addEventListener("mousemove", function (ev) {
        var mx = ev.clientX - host2.getBoundingClientRect().left;
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
      btn.classList.toggle("active", ds.visible);
      btn.style.color = ds.visible ? ds.color : "";
      btn.style.borderColor = ds.visible ? ds.color : "";
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        var visCount = datasets.filter(function (d) { return d.visible; }).length;
        if (ds.visible && visCount <= 1) return;   // keep at least one visible
        ds.visible = !ds.visible;
        btn.classList.toggle("active", ds.visible);
        btn.style.color = ds.visible ? ds.color : "";
        btn.style.borderColor = ds.visible ? ds.color : "";
        btn.setAttribute("aria-pressed", String(ds.visible));
        render();
      });
    });

    if (window.ResizeObserver) { new ResizeObserver(render).observe(host2); }
    render();
  }
```

- [ ] **Step 2:** In the tab module's `mount()`, replace the `gen-ne-body` placeholder line with a call to the renderer. Change:
```javascript
        setText("gen-ne-body", data.skygrid ? "SkyGrid + exponential estimates loaded" : "No Ne data");
```
to:
```javascript
        renderNePanel(data);
```
(Leave the `gen-tree-body` and `gen-dist-body` placeholder lines as-is for now.)

- [ ] **Step 3:** In `unmount()`, drop `gen-ne-body` from the `setText("", …)` clear list (it now owns richer content); leave `gen-tree-body`/`gen-dist-body`.

- [ ] **Step 4:** Commit:
```bash
git add Scripts/assets/genomic.js
git commit -m "Genomic Ne panel: SkyGrid + exponential Ne chart (log-Y, HPD ribbons, toggles, hover)"
```

---

## Task 3: Build + browser verify

- [ ] **Step 1:** `PYTHONPATH=Scripts python3.9 -m pytest tests/ -q` → all pass.
- [ ] **Step 2:** Rebuild for viewing: `cd Scripts && PYTHONPATH=. python3.9 build_dashboard.py && cd ..`. Then load `http://localhost:8123/genomic-epidemiology.html` (relaunch the server if down: `cd output && python3.9 -m http.server 8123 &`).
- [ ] **Step 3:** In the browser (Chrome MCP): screenshot the Ne card — expect two trajectories (green SkyGrid, maroon Exp) with shaded HPD ribbons on a log-Y axis and a calendar x-axis; toggling `SkyGrid`/`Exp` shows/hides each (min one stays); hover shows a date + per-dataset median (CI) tooltip.
- [ ] **Step 4:** Revert generated output (`git checkout -- output/ ; git clean -fdq output/`). Confirm only source committed.

---

## Notes
- Deferred to Phase 5b (needs the tree + coordinator): x-axis lock to the phylogeny view transform, the shared brushed-window highlight, and selected-tip date markers. The static root→mostRecent domain stands in until then.
- The y-domain recomputes from visible datasets on toggle (source froze it to the tree window; with a static domain, recompute is fine and keeps both curves in frame).
