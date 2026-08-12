# Genomic tab Phase 3 — per-tab contribution seam + un-stub

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an additive per-page contribution seam to `chrome.py`, remove the genomic tab from `STUB_VIEWS`, and have `pages/genomic_epidemiology.py` contribute its own body markup + a page-scoped `genomic.js` that reads the `genomic` payload slice — proving data flows end-to-end into a real (skeletal) page.

**Architecture:** `render_page()` gains optional `page_body` + `extra_scripts` kwargs injected into new `__PAGE_BODY__` / `__EXTRA_SCRIPTS__` template slots; existing pages pass nothing and render byte-identically. The genomic page module supplies a light-rail panel shell + `<script>` for `assets/genomic.js`, a small `mount()/unmount()` module that renders placeholder content from `PAYLOAD.genomic`. No engine integration or real panels yet (Phase 4/5); no PearTree vendoring yet (Phase 5, pending licence).

**Tech Stack:** Python 3.9 (`PYTHONPATH=Scripts python3.9 -m pytest`); the dashboard's `common.chrome`/`build_dashboard`; vanilla JS asset in `Scripts/assets/`.

**Scope guard:** Phase 3 is the seam + un-stub + a data-proving skeleton. Do NOT build the real tree/Ne/distribution panels, the coordinator, engine map hooks, PearTree, or i18n — those are Phases 4–6. The skeleton uses plain English text (no `data-i18n`) so it needs no locale keys yet.

**Reference anchors:**
- `chrome.py:39` `STUB_VIEWS`; `chrome.py:398-402` the `#stub-genomic-epidemiology` block + closing `</div>` of `#viewport-area`; `chrome.py:405-411` `SCRIPTS_TEMPLATE`; `chrome.py:453-486` `render_page()`; `chrome.py:448-451` `_PAGE_SCOPED_PAYLOAD_KEYS` (now includes `genomic`).
- `Scripts/pages/genomic_epidemiology.py` — stub `build_page` calling `render_page`.
- `Scripts/build_dashboard.py:73-82` `_write_shared_assets` (writes `dashboard.css` + `engine.js`).
- Body class is `view-<view_id>`; `data-initial-view="<view_id>"` (`chrome.py` BODY_TEMPLATE `<body ...>`).

---

## File structure
- Modify `Scripts/common/chrome.py` — seam slots + `render_page` kwargs; drop genomic from `STUB_VIEWS`; replace its stub block with `__PAGE_BODY__`.
- Modify `Scripts/pages/genomic_epidemiology.py` — contribute body + script.
- Create `Scripts/assets/genomic.js` — the skeleton tab module.
- Modify `Scripts/build_dashboard.py` — also write `genomic.js`.
- Modify `Scripts/assets/dashboard.css` — minimal light-rail styling for `#genomic-panel`.
- Create `tests/test_genomic_seam.py`.

---

## Task 1: Add the contribution seam to `render_page`

**Files:** Modify `Scripts/common/chrome.py`

- [ ] **Step 1: Add the `__EXTRA_SCRIPTS__` slot to `SCRIPTS_TEMPLATE`**

Replace (`chrome.py:405-408`):
```python
SCRIPTS_TEMPLATE = r"""<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script src="__ASSETS_PREFIX__engine.js"></script>
```
with:
```python
SCRIPTS_TEMPLATE = r"""<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script src="__ASSETS_PREFIX__engine.js"></script>
__EXTRA_SCRIPTS__
```

- [ ] **Step 2: Replace the genomic stub block with the `__PAGE_BODY__` slot**

Replace (`chrome.py:398-402`):
```python
<div id="stub-genomic-epidemiology" class="panel stub-panel">
  <h2 data-i18n="ui.view_genomic_epidemiology">Genomic Epidemiology</h2>
  <p data-i18n="ui.stub_coming_soon">Coming soon.</p>
</div>
</div>
"""
```
with:
```python
__PAGE_BODY__
</div>
"""
```
(The other two stubs — clinical-symptoms, surveillance-testing — stay untouched.)

- [ ] **Step 3: Drop genomic from `STUB_VIEWS`**

Change (`chrome.py:39`):
```python
STUB_VIEWS = {"clinical-symptoms", "surveillance-testing", "genomic-epidemiology"}
```
to:
```python
STUB_VIEWS = {"clinical-symptoms", "surveillance-testing"}
```

- [ ] **Step 4: Add the kwargs + replacements to `render_page`**

Change the signature (`chrome.py:453`):
```python
def render_page(view_id: str, payload: dict, assets_prefix: str = "assets/",
                *, page_body: str = "", extra_scripts: str = "") -> str:
```
In the body-assembly block add (after the `__NAV_LINKS__` replace):
```python
    body = body.replace("__PAGE_BODY__", page_body)
```
In the scripts-assembly block, insert the extra-scripts replace BEFORE the `__ASSETS_PREFIX__` replace (so `__ASSETS_PREFIX__` tokens inside `extra_scripts` are also expanded):
```python
    scripts = SCRIPTS_TEMPLATE.replace("__PAYLOAD__", payload_json)
    scripts = scripts.replace("__EXTRA_SCRIPTS__", extra_scripts)
    scripts = scripts.replace("__ASSETS_PREFIX__", assets_prefix)
```

- [ ] **Step 5: Write the seam test**

```python
# tests/test_genomic_seam.py
import importlib

chrome = importlib.import_module("common.chrome")

MINIMAL = {"geometry": {"type": "FeatureCollection", "features": []}, "zone_data": {}, "layers": []}


def test_genomic_not_in_stub_views():
    assert "genomic-epidemiology" not in chrome.STUB_VIEWS


def test_page_body_and_scripts_injected_only_when_contributed():
    html = chrome.render_page("genomic-epidemiology", MINIMAL,
                              page_body='<div id="genomic-panel">RAIL</div>',
                              extra_scripts='<script src="__ASSETS_PREFIX__genomic.js"></script>')
    assert '<div id="genomic-panel">RAIL</div>' in html
    assert 'src="assets/genomic.js"' in html                 # __ASSETS_PREFIX__ expanded
    assert "__PAGE_BODY__" not in html and "__EXTRA_SCRIPTS__" not in html


def test_non_contributing_page_is_clean():
    html = chrome.render_page("trends", MINIMAL)
    assert "__PAGE_BODY__" not in html and "__EXTRA_SCRIPTS__" not in html
    assert "genomic.js" not in html
    assert 'id="genomic-panel"' not in html


def test_genomic_page_has_no_stub_markup():
    html = chrome.render_page("genomic-epidemiology", MINIMAL, page_body='<div id="genomic-panel"></div>')
    assert "stub-view" not in html            # body no longer carries the stub class
    assert "Coming soon" not in html
    assert "stub-genomic-epidemiology" not in html
```

- [ ] **Step 6: Run the test**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/test_genomic_seam.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add Scripts/common/chrome.py tests/test_genomic_seam.py
git commit -m "Add additive per-page contribution seam; un-stub the genomic tab"
```

---

## Task 2: Genomic page module contributes its rail + script

**Files:** Modify `Scripts/pages/genomic_epidemiology.py`

- [ ] **Step 1: Replace the stub module body**

Replace the whole file with:
```python
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

# Right-rail skeleton. Plain text (no data-i18n yet — i18n is a later phase).
# genomic.js fills the .gen-body divs from PAYLOAD.genomic.
_BODY = r"""<div id="genomic-panel">
  <section class="gen-card"><h2>Phylogeny</h2><div class="gen-body" id="gen-tree-body">Loading…</div></section>
  <section class="gen-card"><h2>Effective population size</h2><div class="gen-body" id="gen-ne-body">Loading…</div></section>
  <section class="gen-card"><h2>Sample distribution</h2><div class="gen-body" id="gen-dist-body">Loading…</div></section>
</div>"""

_SCRIPTS = '<script src="__ASSETS_PREFIX__genomic.js"></script>'


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, payload, page_body=_BODY, extra_scripts=_SCRIPTS)
```

- [ ] **Step 2: Add a test for the module's contribution**

Append to `tests/test_genomic_seam.py`:
```python
def test_genomic_module_contributes_rail_and_script():
    page = importlib.import_module("pages.genomic_epidemiology")
    html = page.build_page(MINIMAL)
    assert 'id="genomic-panel"' in html
    assert 'id="gen-tree-body"' in html and 'id="gen-dist-body"' in html
    assert 'src="assets/genomic.js"' in html
    assert "Coming soon" not in html
```

- [ ] **Step 3: Run the test**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/test_genomic_seam.py -v`
Expected: PASS (5 tests).

- [ ] **Step 4: Commit**

```bash
git add Scripts/pages/genomic_epidemiology.py tests/test_genomic_seam.py
git commit -m "Genomic page contributes its rail shell and page-scoped genomic.js"
```

---

## Task 3: `genomic.js` asset + build wiring + minimal styling

**Files:** Create `Scripts/assets/genomic.js`; Modify `Scripts/build_dashboard.py`, `Scripts/assets/dashboard.css`

- [ ] **Step 1: Create `Scripts/assets/genomic.js`**

```javascript
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
```

- [ ] **Step 2: Write `genomic.js` to output assets**

In `Scripts/build_dashboard.py`'s `_write_shared_assets` (after the engine.js write, ~`:80`), add:
```python
    genomic_js = (SCRIPT_DIR / "assets" / "genomic.js").read_text(encoding="utf-8")
    (assets_dir / "genomic.js").write_text(genomic_js, encoding="utf-8")
```
(Written unconditionally alongside engine.js; only the genomic page references it. Returning its byte size is optional — leave the function's return tuple as-is unless you also add a print line.)

- [ ] **Step 3: Add minimal light-rail styling to `dashboard.css`**

Append to `Scripts/assets/dashboard.css`:
```css
/* Genomic Epidemiology tab (Phase 3 seam skeleton). Light rail matching the
   Trends/Spatial-Risk side panels (#f6f5f2/#2a2a27/#e7e3db); full layout
   (drag splitter, collapse, real panels) arrives in later phases. */
#genomic-panel {
  position: absolute; top: 0; right: 0; bottom: 0; width: 440px;
  display: flex; flex-direction: column; gap: 10px;
  background: #f6f5f2; color: #2a2a27; border-left: 1px solid #e7e3db;
  padding: 10px; overflow: auto; z-index: 500;
}
#genomic-panel .gen-card {
  background: #fff; border: 1px solid #e7e3db; border-radius: 4px; padding: 8px 10px;
}
#genomic-panel .gen-card h2 { margin: 0 0 6px; font-size: 13px; color: #2a2a27; }
#genomic-panel .gen-body { font-size: 12px; color: #5c574f; }
```

- [ ] **Step 4: Build and verify the genomic page renders the rail + boots the script**

Run:
```bash
cd Scripts && PYTHONPATH=. python3.9 build_dashboard.py > /tmp/gb3.log 2>&1; echo "exit $?"; cd ..
python3.9 - <<'PY'
import pathlib
h = pathlib.Path("output/genomic-epidemiology.html").read_text()
print("has rail:", 'id="genomic-panel"' in h)
print("has genomic.js tag:", 'src="assets/genomic.js"' in h)
print("no coming-soon:", "Coming soon" not in h)
print("asset written:", pathlib.Path("output/assets/genomic.js").exists())
t = pathlib.Path("output/trends.html").read_text()
print("trends clean:", 'id="genomic-panel"' not in t and "genomic.js" not in t)
PY
```
Expected: `has rail: True`, `has genomic.js tag: True`, `no coming-soon: True`, `asset written: True`, `trends clean: True`.

- [ ] **Step 5: Revert generated HTML (CI artifacts), keep only source**

```bash
git checkout -- output/ 2>/dev/null || true
git status --short
```
Expected: only the source files under `Scripts/` staged/modified — no `output/*.html` in the diff.

- [ ] **Step 6: Commit**

```bash
git add Scripts/assets/genomic.js Scripts/build_dashboard.py Scripts/assets/dashboard.css
git commit -m "Add genomic.js skeleton (reads payload slice), build wiring, and light-rail styling"
```

---

## Task 4: Full suite + wrap-up

**Files:** none (verification)

- [ ] **Step 1: Full pytest suite**

Run: `PYTHONPATH=Scripts python3.9 -m pytest tests/ -q`
Expected: all pass (Phase 2's tests + the new seam tests).

- [ ] **Step 2: Confirm no generated HTML is staged**

Run: `git status --short`
Expected: clean working tree (aside from any pre-existing untracked files); no `output/*.html`.

---

## Self-review notes
- **Additive:** existing pages pass no `page_body`/`extra_scripts`; their `__PAGE_BODY__`/`__EXTRA_SCRIPTS__` slots resolve to `""` — byte-identical output except the genomic page.
- **Un-stub side effect (expected):** with genomic out of `STUB_VIEWS`, its page now renders the full shared map + engine (no `stub-view` hiding). Some snapshot chrome may show until Phase 4 adds the `activeView` handling/map hooks — acceptable for this phase; the seam is proven by the rail rendering `PAYLOAD.genomic` counts.
- **Deferred:** real tree/Ne/distribution panels, coordinator, engine map hooks, PearTree vendoring (licence first), and i18n (Phases 4–6).
