const PAYLOAD = JSON.parse(document.getElementById("payload").textContent);
const ZONE_DATA = PAYLOAD.zone_data;
const I18N = PAYLOAD.i18n || {};
let LAYERS = PAYLOAD.layers;
const TRAVEL_FROM = PAYLOAD.travel_from || "Mongbwalu";
const MATRICES = PAYLOAD.matrices || {};
const MATRIX_INDEX = {};
(function buildMatrixIndex() {
  (MATRICES.zones || []).forEach(function(nom, i) { MATRIX_INDEX[nom] = i; });
})();
let matrixOriginNom = PAYLOAD.matrix_default_origin || "Mongbwalu";
const FLOW_CATALOGS = PAYLOAD.flow_catalogs || {};
const IMPORT_FORCE_PAIRWISE = PAYLOAD.import_force_pairwise || null;
const FLOW_ARC_LAYER = PAYLOAD.flow_arc_layer || null;
let flowHubNom = PAYLOAD.flow_default_hub || "Mongbwalu";
let flowHubUserSelected = !!(PAYLOAD.flow_arcs_available && FLOW_ARC_LAYER);
let flowArcStats = null;
let activeView = "map";
const MATRIX_ORIGIN_FILL = "#5b9bd5";
const FLOW_OUT_COLOR = "#b23b2e";
const FLOW_IN_COLOR = "#5b86b3";
const FLOW_MUTED_FILL = "#e8e4dc";
const EPICENTER_NOMS = new Set(PAYLOAD.epicenter_noms || []);
const EPICENTER_FILL = PAYLOAD.epicenter_fill || "#9b7d4e";
let currentLang = (function resolveLang() {
  const stored = localStorage.getItem("bdbv-dashboard-lang");
  if (stored && I18N.strings && I18N.strings[stored]) return stored;
  const nav = (navigator.language || "").slice(0, 2).toLowerCase();
  if (nav === "fr" && I18N.strings && I18N.strings.fr) return "fr";
  return I18N.default || "en";
})();

function t(path) {
  const parts = String(path).split(".");
  let node = (I18N.strings && I18N.strings[currentLang]) || (I18N.strings && I18N.strings.en) || {};
  for (let i = 0; i < parts.length; i++) {
    if (node == null || typeof node !== "object") return path;
    node = node[parts[i]];
  }
  return node != null ? node : path;
}

function tf(path, vars) {
  let s = String(t(path));
  if (vars) {
    Object.keys(vars).forEach(function(k) {
      s = s.split("{" + k + "}").join(String(vars[k]));
    });
  }
  return s;
}

function localeTag() {
  return currentLang === "fr" ? "fr-FR" : "en-US";
}

function fmtLocale(v) {
  return (v == null ? 0 : v).toLocaleString(localeTag());
}

function trackerCaveats() {
  const byLang = (I18N.tracker_caveats || {})[currentLang];
  if (byLang && byLang.length) return byLang;
  return PAYLOAD.tracker_caveats || [];
}

function layerEpicenterHighlight(layer) {
  return !!(layer && layer.epicenter_highlight);
}
function layerUsesMatrix(layer) {
  return !!(layer && layer.matrix_id);
}
function layerUsesFlowArcs(layer) {
  return !!(layer && layer.viz === "flow_arcs");
}
function flowArcsOverlayActive() {
  if (!FLOW_ARC_LAYER) return false;
  if (activeView === "map") {
    const box = document.getElementById("show-flow-arcs");
    return !!(box && box.checked);
  }
  // Epidemiological trends: same curved Flowminder arcs as snapshot, only while a zone is selected.
  if (activeView === "epi-trends") {
    return !!epiSelectedNom;
  }
  return false;
}
function flowArcLayerDef() {
  return FLOW_ARC_LAYER;
}
function layerOriginHighlight(layer) {
  return !!(layer && layer.origin_highlight);
}
function flowCatalogForLayer(layer) {
  if (!layer || !layer.flow_catalog) return null;
  return FLOW_CATALOGS[layer.flow_catalog] || null;
}
function layerEpicenterNoms(layer) {
  if (layer && layer.epicenter_noms && layer.epicenter_noms.length) {
    return new Set(layer.epicenter_noms);
  }
  return EPICENTER_NOMS;
}
function isEpicenterZone(ref, layer) {
  return layerEpicenterHighlight(layer) && layerEpicenterNoms(layer).has(ref);
}
function isHubZone(ref, layer) {
  if (layerUsesMatrix(layer) && layerOriginHighlight(layer)) {
    return !!(matrixOriginNom && ref === matrixOriginNom);
  }
  return false;
}
function isMatrixOriginZone(ref, layer) {
  return isHubZone(ref, layer);
}
function hubDisplayName(nom) {
  return zoneDisplayName(nom) || TRAVEL_FROM;
}
function matrixOriginDisplayName() {
  return hubDisplayName(matrixOriginNom);
}
function flowHubDisplayName() {
  return hubDisplayName(flowHubNom);
}
function matrixValue(matrixId, originNom, destNom, scaleOverride) {
  const ds = MATRICES.datasets && MATRICES.datasets[matrixId];
  if (!ds || !ds.values) return null;
  const oi = MATRIX_INDEX[originNom];
  const di = MATRIX_INDEX[destNom];
  if (oi == null || di == null) return null;
  const raw = ds.values[oi][di];
  if (raw == null || Number.isNaN(raw)) return null;
  const scale = scaleOverride != null ? scaleOverride : (ds.scale || 1);
  return raw / scale;
}
function applyMatrixOriginToLayers() {
  const origin = matrixOriginDisplayName();
  LAYERS.forEach(function(L) {
    if (!L.label_template) return;
    L.label = L.label_template.split("{origin}").join(origin);
  });
}
function flowHubHasData(nom, layer) {
  const cat = flowCatalogForLayer(layer);
  if (!cat || !nom) return false;
  const outs = (cat.out_by_origin && cat.out_by_origin[nom]) || [];
  const ins = (cat.in_by_dest && cat.in_by_dest[nom]) || [];
  return outs.length > 0 || ins.length > 0;
}
function syncFlowHintPanels() {
  const flowLayer = flowArcLayerDef();
  const flowActive = flowArcsOverlayActive();
  const selected = flowActive && flowHubUserSelected;
  const noData = selected && !flowHubHasData(flowHubNom, flowLayer);
  document.body.classList.toggle("flow-hub-selected", selected);
  document.body.classList.toggle("flow-hub-no-data", noData);
  const emptyHint = document.getElementById("flow-empty-hint");
  if (emptyHint) {
    emptyHint.textContent = noData
      ? tf("ui.hints.flow_no_data", {zone: flowHubDisplayName()})
      : t("ui.hints.flow_no_data");
  }
}
function syncMatrixUi() {
  const layer = getLayer(layerSelect.value);
  const travelActive = !!(layer && layerUsesMatrix(layer) && activeView === "map");
  const flowActive = flowArcsOverlayActive();
  document.body.classList.toggle("matrix-layer-active", travelActive);
  document.body.classList.toggle("flow-layer-active", flowActive);
  if (!flowActive) {
    document.body.classList.remove("flow-hub-selected", "flow-hub-no-data");
  }
  syncFlowHintPanels();
  if (layer && (layerUsesMatrix(layer) || flowActive)) {
    updateLayerMeta(layer);
    updateLegend(layer);
  }
}
function setMatrixOrigin(nom) {
  if (!nom || nom === matrixOriginNom) return;
  matrixOriginNom = nom;
  applyMatrixOriginToLayers();
  rebuildLayerSelect();
  recompute();
  syncMatrixUi();
}
function setFlowHub(nom) {
  // Snapshot's flow-arc origin. A null nom clears it (arcs disappear) -- the
  // tab's "nothing selected" state. Matrix-layer origins are separate and
  // always stay set, since a matrix choropleth needs an origin to render.
  flowHubNom = nom || null;
  flowHubUserSelected = !!nom;
  recompute();
  syncMatrixUi();
}

function applyStaticI18n() {
  document.documentElement.lang = currentLang;
  document.title = t("meta.title");
  const heading = document.getElementById("page-heading");
  if (heading) heading.textContent = t("meta.heading");
  document.querySelectorAll("[data-i18n]").forEach(function(el) {
    const key = el.getAttribute("data-i18n");
    const val = t(key);
    if (el.id === "info-body" && !el.classList.contains("info-empty")) return;
    if (el.id === "context-body" && contextSelectedNom) return;
    el.textContent = val;
  });
  document.querySelectorAll("[data-i18n-aria]").forEach(function(el) {
    el.setAttribute("aria-label", t(el.getAttribute("data-i18n-aria")));
  });
  document.querySelectorAll("[data-i18n-title]").forEach(function(el) {
    el.setAttribute("title", t(el.getAttribute("data-i18n-title")));
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(function(el) {
    el.setAttribute("placeholder", t(el.getAttribute("data-i18n-placeholder")));
  });
  document.querySelectorAll(".lang-btn").forEach(function(btn) {
    const on = btn.dataset.lang === currentLang;
    btn.classList.toggle("active", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  });
  const langSwitcher = document.getElementById("lang-switcher");
  if (langSwitcher) langSwitcher.classList.toggle("lang-fr", currentLang === "fr");
  const methodsModal = document.getElementById("methods-modal");
  const termsModal = document.getElementById("terms-modal");
  if (methodsModal) methodsModal.setAttribute("aria-label", t("ui.methods_modal_title"));
  if (termsModal) termsModal.setAttribute("aria-label", t("ui.terms_modal_title"));
}

function updateLegalContent() {
  const methods = (I18N.methods_html || {})[currentLang] || PAYLOAD.methods_html || "";
  const terms = (I18N.terms_html || {})[currentLang] || PAYLOAD.terms_html || "";
  const updated = ((I18N.terms_updated || {})[currentLang]) || PAYLOAD.terms_updated || "";
  document.getElementById("methods-content").innerHTML =
    methods || "<p style='color:#888'>" + t("ui.methods_missing") + "</p>";
  document.getElementById("terms-content").innerHTML =
    terms || "<p style='color:#888'>" + t("ui.terms_missing") + "</p>";
  const termsUpdatedEl = document.getElementById("terms-updated");
  if (termsUpdatedEl) {
    termsUpdatedEl.textContent = updated ? (t("ui.terms_updated") + " " + updated) : "";
  }
}

function formatBuildTimestamp(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const locale = currentLang === "fr" ? "fr-FR" : "en-GB";
  const datePart = d.toLocaleDateString(locale, { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  const timePart = d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", timeZone: "UTC", hour12: false });
  return datePart + ", " + timePart + " UTC";
}

function buildTitleSub() {
  const linkStyle = "color:#9fcdfb;text-decoration:underline";
  // Latest SitRep link + "built on" tag -- shown inline in #title-sub on
  // wide screens; on narrow screens (see @media max-width:700px) this moves
  // into the info icon's popup instead, since #title-sub itself is hidden
  // there in favor of #header-narrow-row.
  let sitrepHtml =
    t("ui.title_sub.latest") + " " +
    "<a href='" + (PAYLOAD.insp_sitrep_url || "https://insp.cd/") + "' target='_blank' rel='noopener' " +
    "style='" + linkStyle + "'>" + t("ui.title_sub.insp_sitrep") + "</a>" +
    " - " + PAYLOAD.asof;
  const db = PAYLOAD.data_build;
  if (db && db.url && db.tag) {
    sitrepHtml +=
      " · " + t("ui.title_sub.built_on") + " <a href='" + db.url + "' target='_blank' rel='noopener' style='" + linkStyle + "'>" +
       db.tag + "</a>";
  }
  // "Dashboard updated" line -- shown on every screen size: inline (as the
  // second line of #title-sub) when wide, or standalone next to the info
  // icon in #header-narrow-row when narrow.
  let updatedHtml = "";
  const builtAtFormatted = formatBuildTimestamp(PAYLOAD.dashboard_built_at);
  if (builtAtFormatted) {
    updatedHtml = t("ui.title_sub.dashboard_updated") + " " + builtAtFormatted;
  }

  document.getElementById("title-sub").innerHTML =
    sitrepHtml + (updatedHtml ? "<br/>" + updatedHtml : "");

  const updatedLineEl = document.getElementById("header-updated-line");
  if (updatedLineEl) updatedLineEl.innerHTML = updatedHtml;
  const popupBodyEl = document.getElementById("header-info-popup-body");
  if (popupBodyEl) popupBodyEl.innerHTML = sitrepHtml;
}

function buildTracker() {
  const totals = PAYLOAD.totals || {};
  const tracker = document.getElementById("tracker");
  const caveats = trackerCaveats();
  const caveatByMetric = {};
  caveats.forEach(function(c) { caveatByMetric[c.metric] = c.mark; });
  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }
  function countWithMark(v, metric) {
    const base = fmtLocale(v);
    const mark = caveatByMetric[metric];
    return mark
      ? base + "<span class='caveat-mark' aria-hidden='true'>" + esc(mark) + "</span>"
      : base;
  }
  const tr = t("ui.tracker");
  const per = (totals.per_country || []);
  const countryHTML = per.map(function(c) {
    return "<div class='country'>" +
             "<span class='name'>" + esc(c.country) + "</span>" +
             "<span class='nums'>" +
               "<span class='conf'>"   + countWithMark(c.confirmed_cases,  "confirmed_cases")  + "</span> " + tr.conf + " · " +
               "<span class='susp'>"   + countWithMark(c.suspected_cases,  "suspected_cases")  + "</span> " + tr.susp + " · " +
               "<span class='conf-d'>" + countWithMark(c.confirmed_deaths, "confirmed_deaths") + "</span> " + tr.conf_deaths + " · " +
               "<span class='susp-d'>" + countWithMark(c.suspected_deaths, "suspected_deaths") + "</span> " + tr.susp_deaths +
             "</span>" +
           "</div>";
  }).join("");
  const footnotesHTML = caveats.length
    ? "<div class='tracker-footnotes'>" +
        caveats.map(function(c) {
          return "<p><span class='mark'>" + esc(c.mark) + "</span>" + esc(c.warning) + "</p>";
        }).join("") +
      "</div>"
    : "";
  const globalDeaths = (totals.global_confirmed_deaths || 0);
  const globalRecovered = (totals.global_recovered_cases || 0);
  tracker.innerHTML =
    "<div class='stats-block'>" +
      "<div class='global-title'>" + tr.outbreak_size + "</div>" +
      "<div class='global-row'>" +
        "<div class='global-cell cases'>" +
          "<div class='num'>" + fmtLocale(totals.global_total_cases) + "</div>" +
          "<div class='sub'>" + tr.cases + "</div>" +
        "</div>" +
        "<div class='global-cell deaths'>" +
          "<div class='num'>" + fmtLocale(globalDeaths) + "</div>" +
          "<div class='sub'>" + tr.deaths + "</div>" +
        "</div>" +
        "<div class='global-cell recovered'>" +
          "<div class='num'>" + fmtLocale(globalRecovered) + "</div>" +
          "<div class='sub'>" + tr.recovered + "</div>" +
        "</div>" +
      "</div>" +
    "</div>" +
    "<div class='countries-row tracker-countries'>" + (countryHTML || "<span class='sub'>—</span>") + "</div>" +
    footnotesHTML;
}

function buildModeledEstimateNote() {
  const root = document.getElementById("imperial-model-estimates");
  if (!root) return;
  root.innerHTML = "";
  root.style.display = "none";
}

// --- narrow-header info popup (see #header-narrow-row in chrome.py) ---
// Hover opens it on desktop via CSS alone (:hover/:focus-within); this just
// adds a click/tap toggle for touch devices, where hover doesn't apply, plus
// close-on-outside-click and Escape.
(function wireHeaderInfoPopup() {
  const row = document.getElementById("header-narrow-row");
  const btn = document.getElementById("header-info-btn");
  const popup = document.getElementById("header-info-popup");
  if (!row || !btn || !popup) return;
  function setOpen(open) {
    row.classList.toggle("open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    popup.setAttribute("aria-hidden", open ? "false" : "true");
  }
  btn.addEventListener("click", function(e) {
    e.stopPropagation();
    setOpen(!row.classList.contains("open"));
  });
  document.addEventListener("click", function(e) {
    if (!e.target.closest("#header-narrow-row")) setOpen(false);
  });
  row.addEventListener("keydown", function(e) {
    if (e.key === "Escape") {
      setOpen(false);
      btn.blur();
    }
  });
  // Methods/Terms open a full-screen modal over everything, but tidy up by
  // closing the popup itself rather than leaving it open underneath.
  const popupLinks = document.getElementById("header-info-popup-links");
  if (popupLinks) {
    popupLinks.addEventListener("click", function() { setOpen(false); });
  }
})();

// --- partners strip ---
(function buildPartners() {
  const partners = PAYLOAD.partners || [];
  const root = document.getElementById("partners");
  if (!partners.length || !root) { if (root) root.style.display="none"; return; }
  root.innerHTML = partners.map(function(p) {
    const img = "<img src='" + p.data_uri + "' alt='" + p.alt + "' title='" + p.alt + "' />";
    return p.href
      ? "<a href='" + p.href + "' target='_blank' rel='noopener'>" + img + "</a>"
      : img;
  }).join("");
})();

const layerSelect = document.getElementById("layer-select");
const layerMeta = document.getElementById("layer-meta");

function rebuildLayerSelect() {
  const selected = layerSelect.value;
  layerSelect.innerHTML = "";
  const groups = {};
  for (const L of LAYERS) {
    if (!groups[L.group]) {
      const og = document.createElement("optgroup");
      og.label = L.group;
      layerSelect.appendChild(og);
      groups[L.group] = og;
    }
    const o = document.createElement("option");
    o.value = L.id; o.textContent = L.label;
    groups[L.group].appendChild(o);
  }
  if (selected && getLayer(selected)) layerSelect.value = selected;
  else if (LAYERS.length) layerSelect.value = LAYERS[0].id;
}

function setLang(lang) {
  if (!I18N.strings || !I18N.strings[lang]) return;
  currentLang = lang;
  localStorage.setItem("bdbv-dashboard-lang", lang);
  LAYERS = (I18N.layers && I18N.layers[lang]) || PAYLOAD.layers;
  applyStaticI18n();
  rebuildLayerSelect();
  buildTitleSub();
  buildTracker();
  buildModeledEstimateNote();
  updateLegalContent();
  applyMatrixOriginToLayers();
  rebuildLayerSelect();
  recompute();
  syncMatrixUi();
  refreshMarkerTooltips();
  if (zoneSearchInput && zoneSearchResults && !zoneSearchResults.hidden) {
    renderZoneSearchResults(zoneSearchInput.value);
  }
  if (activeView === "trends") {
    updateTrendsDateLabel();
    syncTrendsPlayButton();
    renderTrendsPlots();
  } else if (activeView === "context") {
    renderContextPanel(contextSelectedNom);
  } else if (activeView === "epi-trends") {
    updateEpiTitle();
    updateEpiMetaNotes();
    renderEpiLegendBars();
    renderEpiTrendsTable();
  } else {
    const infoBody = document.getElementById("info-body");
    if (infoBody && !infoBody.classList.contains("info-empty")) {
      for (const feat of PAYLOAD.geometry.features) {
        if ((feat.properties.name || "").toLowerCase() === (TRAVEL_FROM || "Mongbwalu").toLowerCase() ||
            (feat.properties.nom || "").toLowerCase() === "mongbalu") {
          infoBody.innerHTML = infoHTML(feat);
          break;
        }
      }
    }
  }
}

document.querySelectorAll(".lang-btn").forEach(function(btn) {
  btn.addEventListener("click", function() { setLang(btn.dataset.lang || "en"); });
});

function getLayer(id) { return LAYERS.find(L => L.id === id); }

// color palettes
const PLASMA = [
  [13,8,135],[75,3,161],[125,3,168],[168,34,150],[203,70,121],
  [229,107,93],[248,148,65],[253,195,40],[240,249,33]];
const REDS = [
  [255,245,235],[254,217,181],[253,173,118],[252,127,73],[239,77,55],
  [205,32,32],[140,17,17]];
// Brand sequential ramp: #f6e3df → #e8b3a6 → #d08163 → #aa4a32 → #7c1d1d
const OUTBREAK = [
  [246,227,223],[232,179,166],[208,129,99],[170,74,50],[124,29,29]];
const VIRIDIS = [
  [68,1,84],[72,40,120],[62,73,137],[49,104,142],[38,130,142],[31,158,137],
  [53,183,121],[109,206,89],[180,222,44],[253,231,37]];
// Darker, subdued purple ramp for invasion probability.
const PURPLES = [
  [236,230,242],[214,201,224],[184,164,201],[150,124,171],[117,90,140],
  [91,68,112],[72,52,90],[55,40,72],[42,30,56]];
const PALETTES = {
  plasma:PLASMA, plasma_r:[...PLASMA].reverse(),
  reds:REDS, outbreak:OUTBREAK, viridis:VIRIDIS, purples:PURPLES,
};

function lerpColor(stops, t) {
  if (t <= 0) return stops[0];
  if (t >= 1) return stops[stops.length - 1];
  const s = t * (stops.length - 1);
  const i = Math.floor(s), f = s - i;
  const a = stops[i], b = stops[i + 1];
  return [a[0]+(b[0]-a[0])*f, a[1]+(b[1]-a[1])*f, a[2]+(b[2]-a[2])*f];
}
function rgb(c) { return "rgb(" + Math.round(c[0]) + "," + Math.round(c[1]) + "," + Math.round(c[2]) + ")"; }

const PROJ_MASK = PAYLOAD.projection_mask || null;
const PROJ_MASK_LAYERS = new Set((PROJ_MASK && PROJ_MASK.layers) || []);

function valueForZone(ref, zone, layer) {
  if (PROJ_MASK && PROJ_MASK_LAYERS.has(layer.id)) {
    const m = zone[PROJ_MASK.field];
    if (m == null || Number.isNaN(m) || Number(m) < PROJ_MASK.min) return null;
  }
  if (layerUsesMatrix(layer)) {
    return matrixValue(layer.matrix_id, matrixOriginNom, ref, layer.matrix_scale);
  }
  const v = zone[layer.field];
  return (v == null || Number.isNaN(v)) ? null : Number(v);
}

// --- map setup ---
const INITIAL_VIEW = PAYLOAD.initial_view || {lat: -2.5, lon: 22.5, zoom: 5};
const map = L.map("map").setView([INITIAL_VIEW.lat, INITIAL_VIEW.lon], INITIAL_VIEW.zoom);
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>, &copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains: "abcd", maxZoom: 19
}).addTo(map);

// Zone borders read as hairlines at the national default zoom (many small
// zones packed together) and gain a little presence as you zoom into the
// outbreak. Scale a resting stroke weight by the current zoom; emphasized
// strokes (hover, selection, travel origin) keep their fixed weight.
function zoomWeight(base) {
  const f = Math.max(0.5, Math.min(2.1, 0.5 + (map.getZoom() - 5) * 0.28));
  return base * f;
}

map.createPane("flow-arcs");
map.getPane("flow-arcs").style.zIndex = "450";
map.createPane("epi-links");
map.getPane("epi-links").style.zIndex = "455";
const flowArcLayer = L.layerGroup();
const epiLinkLayer = L.layerGroup();

function zoneCentroid(nom) {
  const z = ZONE_DATA[nom];
  if (!z || z.centroid_lat == null || z.centroid_lon == null) return null;
  if (!isFinite(z.centroid_lat) || !isFinite(z.centroid_lon)) return null;
  return [z.centroid_lat, z.centroid_lon];
}

function clearFlowArcs() {
  flowArcLayer.clearLayers();
  if (map.hasLayer(flowArcLayer)) map.removeLayer(flowArcLayer);
  flowArcStats = null;
}

function quadraticBezierPoints(lat1, lon1, lat2, lon2, bend) {
  const steps = 24;
  const midLat = (lat1 + lat2) / 2;
  const midLon = (lon1 + lon2) / 2;
  const dlat = lat2 - lat1;
  const dlon = lon2 - lon1;
  const len = Math.sqrt(dlat * dlat + dlon * dlon) || 1;
  const sign = bend >= 0 ? 1 : -1;
  const offset = 0.18 * len * sign;
  // Counterclockwise bow from (lat1,lon1) toward (lat2,lon2) in the map plane.
  const cpLat = midLat + (dlon / len) * offset;
  const cpLon = midLon + (-dlat / len) * offset;
  const pts = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const u = 1 - t;
    const lat = u * u * lat1 + 2 * u * t * cpLat + t * t * lat2;
    const lon = u * u * lon1 + 2 * u * t * cpLon + t * t * lon2;
    pts.push([lat, lon]);
  }
  return pts;
}

function flowArcWeight(count, maxCount) {
  if (!maxCount || maxCount <= 0) return 1.5;
  return 1 + 4 * Math.sqrt(count / maxCount);
}

function flowArcWeightNormalized(frac) {
  if (frac == null || !isFinite(frac) || frac <= 0) return 1.2;
  return 1 + 4 * Math.max(0, Math.min(1, frac));
}

function zoneConfirmedCases(nom) {
  const z = ZONE_DATA[nom];
  if (!z) return 0;
  const c = Number(z.confirmed_cases);
  return (isFinite(c) && c > 0) ? c : 0;
}

function importationPressure(sourceNom, movers) {
  // Spatial risk: Flowminder inflow edges weighted by confirmed cases in the
  // external (origin) health zone. No movement → no pressure.
  const n = Number(movers);
  if (!isFinite(n) || n <= 0) return 0;
  return zoneConfirmedCases(sourceNom);
}

function addFlowWingMarker(pts, color, opts) {
  opts = opts || {};
  if (!pts || pts.length < 2) return;
  // Place near the destination for inward (import) arrows so they read as
  // pointing into the selected health zone; otherwise mid-arc.
  const frac = opts.nearEnd ? 0.78 : 0.5;
  const midIdx = Math.max(1, Math.min(pts.length - 2, Math.floor((pts.length - 1) * frac)));
  const mid = pts[midIdx];
  const prev = pts[Math.max(0, midIdx - 1)];
  const next = pts[Math.min(pts.length - 1, midIdx + 1)];
  // Screen-space bearing so the chevron follows the drawn path (toward hub
  // for inflow polylines that run origin → selected zone).
  const p0 = map.latLngToLayerPoint(L.latLng(prev[0], prev[1]));
  const p1 = map.latLngToLayerPoint(L.latLng(next[0], next[1]));
  const angle = Math.atan2(p1.y - p0.y, p1.x - p0.x) * 180 / Math.PI;
  const svg =
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16" ' +
    'style="transform:rotate(' + angle + 'deg)">' +
    '<line x1="2" y1="3.5" x2="11" y2="8" stroke="' + color + '" stroke-width="1.7" stroke-linecap="round"/>' +
    '<line x1="2" y1="12.5" x2="11" y2="8" stroke="' + color + '" stroke-width="1.7" stroke-linecap="round"/>' +
    '</svg>';
  L.marker([mid[0], mid[1]], {
    icon: L.divIcon({
      className: "flow-wing-icon",
      html: svg,
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    }),
    interactive: false,
    pane: "flow-arcs",
  }).addTo(flowArcLayer);
}

function renderFlowArcs(hubNom, layer) {
  clearFlowArcs();
  const cat = flowCatalogForLayer(layer);
  if (!cat || !hubNom) return;
  const hub = zoneCentroid(hubNom);
  if (!hub) return;

  const outs = (cat.out_by_origin && cat.out_by_origin[hubNom]) || [];
  const ins = (cat.in_by_dest && cat.in_by_dest[hubNom]) || [];
  const outSorted = outs.slice().sort(function(a, b) { return b[1] - a[1]; });
  const inSorted = ins.slice().sort(function(a, b) { return b[1] - a[1]; });
  // Spatial risk: only inflows into the selected zone (drawn in red),
  // weighted by confirmed cases in each external origin zone.
  const useImportPressure = activeView === "epi-trends";

  let maxMetric = 0;
  if (useImportPressure) {
    inSorted.forEach(function(p) {
      const m = importationPressure(p[0], p[1]);
      if (m > maxMetric) maxMetric = m;
    });
  } else {
    outSorted.concat(inSorted).forEach(function(p) {
      const m = Number(p[1]) || 0;
      if (m > maxMetric) maxMetric = m;
    });
    if (maxMetric < 1) maxMetric = 1;
  }

  if (!useImportPressure) {
    outSorted.forEach(function(pair) {
      const dest = pair[0];
      const count = pair[1];
      const end = zoneCentroid(dest);
      if (!end) return;
      const pts = quadraticBezierPoints(hub[0], hub[1], end[0], end[1], 1);
      const line = L.polyline(pts, {
        color: FLOW_OUT_COLOR,
        weight: flowArcWeight(count, maxMetric),
        opacity: 0.82,
        pane: "flow-arcs",
        // Arrows are annotations of the selected zone, not controls. Keep the
        // hover tooltip but stop clicks bubbling to the map's click handler,
        // which would otherwise clear the selection (and the arrows with it).
        bubblingMouseEvents: false,
      });
      line.bindTooltip(tf("ui.flow_arc_tooltip", {
        from: flowHubDisplayName(),
        to: hubDisplayName(dest),
        count: fmt(count),
      }), {direction: "top", sticky: true});
      line.addTo(flowArcLayer);
      addFlowWingMarker(pts, FLOW_OUT_COLOR);
    });
  }

  const pairwiseEdges = (useImportPressure && IMPORT_FORCE_PAIRWISE
    && IMPORT_FORCE_PAIRWISE.in_by_dest
    && IMPORT_FORCE_PAIRWISE.in_by_dest[hubNom]) || null;
  if (pairwiseEdges) {
    // Only origins with a centroid are drawable; compute the per-zone max foi
    // over THOSE, so the widest *visible* arrow reaches full width even if a
    // centroid-less origin had a higher foi.
    const drawable = pairwiseEdges
      .map(function(e) {
        return {origin: e[0], foi: e[1], share: e[2], start: zoneCentroid(e[0])};
      })
      .filter(function(e) { return !!e.start; });
    let maxFoi = 0;
    drawable.forEach(function(e) { if (e.foi > maxFoi) maxFoi = e.foi; });
    drawable.forEach(function(e) {
      const pts = quadraticBezierPoints(e.start[0], e.start[1], hub[0], hub[1], 1);
      const line = L.polyline(pts, {
        color: FLOW_OUT_COLOR,
        weight: flowArcWeight(e.foi, maxFoi),      // 1 + 4*sqrt(foi/maxFoi)
        opacity: 0.82,
        pane: "flow-arcs",
        bubblingMouseEvents: false, // see note on the outflow arc above
      });
      line.bindTooltip(tf("ui.import_force_tooltip", {
        from: hubDisplayName(e.origin),
        to: flowHubDisplayName(),
        foi: e.foi.toPrecision(2),
        share: (e.share != null ? (e.share * 100).toFixed(1) + "%" : "—"),
      }), {direction: "top", sticky: true});
      line.addTo(flowArcLayer);
      addFlowWingMarker(pts, FLOW_OUT_COLOR, {nearEnd: true});
    });
    flowArcStats = {
      outTotal: outs.length, outShown: 0,
      inTotal: drawable.length, inShown: drawable.length,
      metric: "import_force", maxMetric: maxFoi,
    };
    flowArcLayer.addTo(map);
    return;
  }

  inSorted.forEach(function(pair) {
    const origin = pair[0];
    const count = pair[1];
    const start = zoneCentroid(origin);
    if (!start) return;
    const cases = zoneConfirmedCases(origin);
    const pressure = useImportPressure ? importationPressure(origin, count) : count;
    const weight = useImportPressure
      ? flowArcWeightNormalized(maxMetric > 0 ? pressure / maxMetric : 0)
      : flowArcWeight(count, maxMetric);
    const color = useImportPressure ? FLOW_OUT_COLOR : FLOW_IN_COLOR;
    // Always draw origin → selected hub so chevrons point inward.
    const pts = quadraticBezierPoints(start[0], start[1], hub[0], hub[1], 1);
    const line = L.polyline(pts, {
      color: color,
      weight: weight,
      opacity: 0.82,
      pane: "flow-arcs",
      bubblingMouseEvents: false, // see note on the outflow arc above
    });
    if (useImportPressure) {
      line.bindTooltip(tf("ui.importation_pressure_tooltip", {
        from: hubDisplayName(origin),
        to: flowHubDisplayName(),
        pressure: (maxMetric > 0 ? pressure / maxMetric : 0).toFixed(3),
        cases: fmt(cases),
        count: fmt(count),
      }), {direction: "top", sticky: true});
    } else {
      line.bindTooltip(tf("ui.flow_arc_tooltip", {
        from: hubDisplayName(origin),
        to: flowHubDisplayName(),
        count: fmt(count),
      }), {direction: "top", sticky: true});
    }
    line.addTo(flowArcLayer);
    addFlowWingMarker(pts, color, useImportPressure ? {nearEnd: true} : null);
  });

  flowArcStats = {
    outTotal: outs.length,
    outShown: useImportPressure ? 0 : outSorted.length,
    inTotal: ins.length,
    inShown: inSorted.length,
    metric: useImportPressure ? "importation_pressure" : "persons",
    maxMetric: maxMetric,
  };
  flowArcLayer.addTo(map);
}

// --- Epidemiological trends (invasion risk) ---
const INVASION_RISK = PAYLOAD.invasion_risk || null;
const INVASION_ZONES = (INVASION_RISK && INVASION_RISK.zones) || {};
const INVASION_SCOPES = (INVASION_RISK && INVASION_RISK.scopes) || [];
// The Spatial Risk table always shows the national ranking -- there is no
// geographic scope toggle any more (the old National/Provincial buttons were
// removed). epiCurrentScope() therefore always resolves to the "national"
// INVASION_SCOPES entry (rr_nat / rr_nat_rank); the province-specific columns
// still ship in the payload and CSV download, they're just no longer surfaced
// in the UI.
// Sortable column headers replace the old "rank by relative risk / rank by
// vulnerability-based priority" buttons -- any column can be sorted by
// clicking (or Enter/Space on) its header, see wireEpiTrendsUi().
let epiSortKey = "rr_rank";
let epiSortDir = "asc";
let epiSelectedNom = null;
let epiFocusNoms = null; // Set of noms to keep vivid when a zone is selected
let epiInvasionDomain = {min: 0, max: 1, palette: PURPLES};
let epiCasesDomain = {min: 0, max: 1, isLog: true, palette: REDS};

function clearEpiLinks() {
  epiLinkLayer.clearLayers();
  if (map.hasLayer(epiLinkLayer)) map.removeLayer(epiLinkLayer);
}

function renderEpiStraightLinks(hubNom) {
  clearEpiLinks();
  if (!hubNom) return;
  const hub = zoneCentroid(hubNom);
  if (!hub) return;
  const cat = flowCatalogForLayer(FLOW_ARC_LAYER);
  if (!cat) return;

  const edges = [];
  const outs = (cat.out_by_origin && cat.out_by_origin[hubNom]) || [];
  const ins = (cat.in_by_dest && cat.in_by_dest[hubNom]) || [];
  outs.forEach(function(pair) {
    if (pair && pair[0] && Number(pair[1]) > 0) edges.push({nom: pair[0], count: Number(pair[1]), dir: "out"});
  });
  ins.forEach(function(pair) {
    if (pair && pair[0] && Number(pair[1]) > 0) edges.push({nom: pair[0], count: Number(pair[1]), dir: "in"});
  });
  if (!edges.length) return;

  let maxCount = 1;
  edges.forEach(function(e) { if (e.count > maxCount) maxCount = e.count; });

  edges.forEach(function(e) {
    const end = zoneCentroid(e.nom);
    if (!end) return;
    const color = e.dir === "out" ? FLOW_OUT_COLOR : FLOW_IN_COLOR;
    const line = L.polyline([hub, end], {
      color: color,
      weight: 1.2 + 3.5 * Math.sqrt(e.count / maxCount),
      opacity: 0.85,
      pane: "epi-links",
      interactive: false,
    });
    line.bindTooltip(tf("ui.flow_arc_tooltip", {
      from: e.dir === "out" ? hubDisplayName(hubNom) : hubDisplayName(e.nom),
      to: e.dir === "out" ? hubDisplayName(e.nom) : hubDisplayName(hubNom),
      count: fmt(e.count),
    }), {direction: "top", sticky: true});
    line.addTo(epiLinkLayer);
  });
  epiLinkLayer.addTo(map);
}

function epiCurrentScope() {
  // Always the national scope (rr_nat / rr_nat_rank) -- the provincial toggle
  // was removed, so there is no other scope to resolve to.
  return INVASION_SCOPES.find(function(s) { return s.id === "national"; }) || INVASION_SCOPES[0] || null;
}

function epiZoneVisible(row) {
  // National scope shows every zone; nothing to filter now that the
  // provincial toggle is gone.
  return !!epiCurrentScope();
}

function epiFlowConnectedNoms(hubNom) {
  const out = new Set([hubNom]);
  const layer = FLOW_ARC_LAYER;
  const cat = flowCatalogForLayer(layer);
  if (!cat || !hubNom) return out;
  // Spatial risk focuses on inflows into the selected zone.
  const ins = (cat.in_by_dest && cat.in_by_dest[hubNom]) || [];
  ins.forEach(function(p) { if (p && p[0]) out.add(p[0]); });
  return out;
}

function epiFmtProb(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return Number(v).toLocaleString(undefined, {minimumFractionDigits: 3, maximumFractionDigits: 3});
}

function epiFmtNum(v, digits) {
  if (v == null || Number.isNaN(v)) return "—";
  if (digits == null) return Number(v).toLocaleString(undefined, {maximumFractionDigits: 2});
  return Number(v).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
}

function updateEpiTitle() {
  const el = document.getElementById("epi-trends-title");
  if (!el) return;
  // Always the national ranking now that the provincial scope is gone.
  el.textContent = t("ui.epi_trends_title");
}

function epiCapitalizeFirst(text) {
  const s = String(text || "");
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function epiParseIsoDate(iso) {
  if (!iso) return null;
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
}

function epiOrdinalDay(n) {
  const rem100 = n % 100;
  if (rem100 >= 11 && rem100 <= 13) return n + "th";
  const rem10 = n % 10;
  if (rem10 === 1) return n + "st";
  if (rem10 === 2) return n + "nd";
  if (rem10 === 3) return n + "rd";
  return n + "th";
}

function epiFormatLongDate(iso) {
  const d = epiParseIsoDate(iso);
  if (!d || Number.isNaN(d.getTime())) return "";
  const monthsEn = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  const monthsFr = ["janvier","février","mars","avril","mai","juin","juillet","août","septembre","octobre","novembre","décembre"];
  if (currentLang === "fr") {
    return d.getDate() + " " + monthsFr[d.getMonth()] + " " + d.getFullYear();
  }
  return monthsEn[d.getMonth()] + " " + epiOrdinalDay(d.getDate());
}

function epiForecastEndIso() {
  if (INVASION_RISK && INVASION_RISK.forecast_end_date) {
    return INVASION_RISK.forecast_end_date;
  }
  const cutoff = INVASION_RISK && INVASION_RISK.cutoff_date;
  const weeks = INVASION_RISK && INVASION_RISK.horizon_window;
  const d = epiParseIsoDate(cutoff);
  if (!d || weeks == null || Number.isNaN(Number(weeks))) return null;
  d.setDate(d.getDate() + Math.round(Number(weeks)) * 7);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return yyyy + "-" + mm + "-" + dd;
}

function updateEpiMetaNotes() {
  const sub = document.getElementById("epi-trends-subtitle");
  if (sub) {
    // Prefer the pipeline's own forecast_start_date (ground truth from
    // run_info.json's forecast_target_windows) over cutoff_date, which is
    // "data up to" (last training day), not "forecast starts on".
    const startIso = INVASION_RISK && (
      INVASION_RISK.forecast_start_date || INVASION_RISK.cutoff_date
    );
    const weeksRaw = INVASION_RISK && (
      INVASION_RISK.forecasting_window != null
        ? INVASION_RISK.forecasting_window
        : INVASION_RISK.horizon_window
    );
    const weeks = (weeksRaw == null || Number.isNaN(Number(weeksRaw)))
      ? null
      : Math.round(Number(weeksRaw));
    const endIso = epiForecastEndIso();
    const startLabel = epiFormatLongDate(startIso);
    const endLabel = epiFormatLongDate(endIso);
    if (startLabel && endLabel && weeks != null) {
      sub.textContent = tf("ui.epi_forecast_subtitle", {
        start: startLabel,
        weeks: String(weeks),
        week_unit: weeks === 1 ? t("ui.epi_week_one") : t("ui.epi_week_other"),
        end: endLabel,
      });
    } else {
      sub.textContent = "";
    }
  }
  const methodEl = document.getElementById("epi-trends-method");
  if (!methodEl) return;
  if (!INVASION_RISK) {
    methodEl.textContent = t("ui.epi_no_data");
    return;
  }
  const label = (INVASION_RISK.method_label) || t("ui.epi_method_label");
  const url = INVASION_RISK.method_url || t("ui.epi_method_url");
  const cutoffLabel = epiFormatLongDate(INVASION_RISK.cutoff_date);
  let html = escHtml(t("ui.epi_method_prefix")) + " " +
    "<a href='" + escHtml(url) + "' target='_blank' rel='noopener'>" +
    escHtml(label) + "</a>";
  if (cutoffLabel) {
    html += " · " + escHtml(tf("ui.epi_data_up_to", {date: cutoffLabel}));
  }
  methodEl.innerHTML = html;
}

function renderEpiLegendBars() {
  function fillBar(barId, ticksId, domain, round) {
    const bar = document.getElementById(barId);
    const ticks = document.getElementById(ticksId);
    if (!bar || !ticks) return;
    const stops = [];
    for (let i = 0; i <= 10; i++) {
      const tt = i / 10;
      stops.push(rgb(lerpColor(domain.palette, tt)) + " " + Math.round(tt * 100) + "%");
    }
    bar.style.background = "linear-gradient(to right, " + stops.join(", ") + ")";
    const lo = domain.min, hi = domain.max;
    const mid = domain.isLog ? Math.sqrt(Math.max(lo, 1e-9) * Math.max(hi, 1e-9)) : (lo + hi) / 2;
    ticks.innerHTML =
      "<span>" + fmtLegend(lo, round) + "</span>" +
      "<span>" + fmtLegend(mid, round) + "</span>" +
      "<span>" + fmtLegend(hi, round) + "</span>";
  }
  const invLabel = document.getElementById("epi-legend-invasion-label");
  if (invLabel) {
    const raw = (INVASION_RISK && INVASION_RISK.p_case_invasion_label) ||
      t("ui.epi_p_invasion");
    invLabel.textContent = epiCapitalizeFirst(raw);
  }
  const activeLabel = document.querySelector('#epi-trends-legend [data-i18n="ui.epi_legend_active"]');
  if (activeLabel) {
    activeLabel.textContent = epiCapitalizeFirst(t("ui.epi_legend_active"));
  }
  fillBar("epi-legend-invasion-bar", "epi-legend-invasion-ticks", epiInvasionDomain, 2);
  fillBar("epi-legend-cases-bar", "epi-legend-cases-ticks", epiCasesDomain, "int");
}

function updateEpiFloat(nom, latlng) {
  const box = document.getElementById("epi-float");
  if (!box) return;
  const row = INVASION_ZONES[nom];
  if (!row || !epiZoneVisible(row)) {
    box.classList.remove("visible");
    return;
  }
  const name = zoneDisplayName(nom) || nom;
  box.innerHTML =
    "<strong>" + escHtml(name) + "</strong>" +
    "<table>" +
    "<tr><td>" + escHtml(t("ui.epi_surveillance_gap")) + "</td><td>" + epiFmtNum(row.surveillance_gap, 3) + "</td></tr>" +
    "<tr><td>" + escHtml(t("ui.epi_access_gap")) + "</td><td>" + epiFmtNum(row.access_gap, 3) + "</td></tr>" +
    "<tr><td>" + escHtml(t("ui.epi_social_vuln")) + "</td><td>" + epiFmtNum(row.social_vulnerability, 3) + "</td></tr>" +
    "</table>";
  const c = latlng
    ? [latlng.lat, latlng.lng]
    : zoneCentroid(nom);
  if (c) {
    const pt = map.latLngToContainerPoint(L.latLng(c[0], c[1]));
    const mapEl = map.getContainer();
    const x = Math.min(Math.max(12, pt.x + 14), mapEl.clientWidth - 220);
    const y = Math.min(Math.max(12, pt.y - 20), mapEl.clientHeight - 120);
    box.style.left = x + "px";
    box.style.top = y + "px";
  }
  box.classList.add("visible");
}

function hideEpiFloat() {
  const box = document.getElementById("epi-float");
  if (box) box.classList.remove("visible");
}

function setEpiSelected(nom) {
  if (!nom || !INVASION_ZONES[nom] || !epiZoneVisible(INVASION_ZONES[nom])) {
    epiSelectedNom = null;
    epiFocusNoms = null;
    clearEpiLinks();
    clearFlowArcs();
  } else {
    epiSelectedNom = nom;
    epiFocusNoms = epiFlowConnectedNoms(nom);
    flowHubNom = nom;
    clearEpiLinks();
    renderFlowArcs(nom, flowArcLayerDef());
  }
  renderEpiTrendsTable();
  recomputeEpiTrends();
}

// Extracts the value used to sort a given column -- shared by the click
// handler (which just needs to know which column) and epiSortedRows(). "zone"
// and "province" are strings; everything else is numeric-or-null. "norm_rr"
// (the on-screen "Relative risk (norm.)" column) is item.rr divided by a
// constant (the max across visible rows), so it sorts identically to the raw
// relative risk -- no need to recompute the normalised value just to sort by it.
function epiSortValue(item, key) {
  switch (key) {
    case "province": return item.row.province || "";
    case "zone": return zoneDisplayName(item.nom) || item.nom || "";
    case "p_invasion": return item.row.p_case_invasion;
    // No single natural sort key for a range -- use the lower bound.
    case "p_ci": return item.row.p_case_lo;
    case "norm_rr": return item.rr;
    case "rr_rank": return item.rrRank;
    case "priority": return item.priority;
    case "priority_rank": return item.priorityRank;
    default: return null;
  }
}

// Generic comparator for sortable-column values: nulls always sort last
// regardless of direction (there's nothing meaningful to rank an unknown
// value against), strings compare case/locale-insensitively, numbers compare
// numerically. dir "desc" just flips a non-null comparison.
function epiCompareValues(a, b, dir) {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  const cmp = (typeof a === "string" || typeof b === "string")
    ? String(a).localeCompare(String(b), undefined, {sensitivity: "base", numeric: true})
    : (a - b);
  return dir === "desc" ? -cmp : cmp;
}

function epiSortedRows() {
  const scope = epiCurrentScope();
  if (!scope) return [];
  const rows = [];
  Object.keys(INVASION_ZONES).forEach(function(nom) {
    const row = INVASION_ZONES[nom];
    if (!epiZoneVisible(row)) return;
    rows.push({
      nom: nom,
      row: row,
      rr: row[scope.rr],
      rrRank: row[scope.rank],
      priority: row.priority,
      priorityRank: row.priority_rank,
    });
  });
  rows.sort(function(a, b) {
    const cmp = epiCompareValues(epiSortValue(a, epiSortKey), epiSortValue(b, epiSortKey), epiSortDir);
    if (cmp !== 0) return cmp;
    // Stable tiebreaker so equal/both-null values still render in a
    // predictable order instead of shuffling between re-renders.
    return String(zoneDisplayName(a.nom) || a.nom).localeCompare(String(zoneDisplayName(b.nom) || b.nom));
  });
  return rows;
}

function epiFmtCi(lo, hi, digits) {
  const a = epiFmtNum(lo, digits);
  const b = epiFmtNum(hi, digits);
  if (a === "—" && b === "—") return "—";
  return a + " - " + b;
}

function renderEpiTrendsTable() {
  const tbody = document.getElementById("epi-trends-tbody");
  if (!tbody) return;
  const rows = epiSortedRows();
  if (!rows.length) {
    // Covers both "Provincial scope, no province picked yet" (epiCurrentScope()
    // returned null) and "a scope is active but happens to match zero zones" --
    // same prompt either way, since the fix in both cases is "search for a
    // province above".
    tbody.innerHTML = "<tr class='epi-empty-row'><td colspan='8' class='trends-empty'>" +
      escHtml(t("ui.epi_scope_empty")) + "</td></tr>";
    return;
  }
  let maxRr = 0;
  rows.forEach(function(item) {
    if (item.rr != null && !Number.isNaN(item.rr) && item.rr > maxRr) maxRr = item.rr;
  });
  tbody.innerHTML = rows.map(function(item) {
    const sel = item.nom === epiSelectedNom ? " selected" : "";
    const norm = (item.rr == null || Number.isNaN(item.rr) || maxRr <= 0)
      ? null
      : (item.rr / maxRr);
    const pInv = item.row.p_case_invasion;
    const pLo = item.row.p_case_lo;
    const pHi = item.row.p_case_hi != null ? item.row.p_case_hi : item.row.p_case_high;
    return "<tr class='" + sel + "' data-nom='" + escHtml(item.nom) + "'>" +
      "<td>" + escHtml(item.row.province || "—") + "</td>" +
      "<td>" + escHtml(zoneDisplayName(item.nom) || item.nom) + "</td>" +
      "<td class='num'>" + epiFmtNum(pInv, 3) + "</td>" +
      "<td class='num'>" + epiFmtCi(pLo, pHi, 3) + "</td>" +
      "<td class='num'>" + epiFmtNum(norm, 3) + "</td>" +
      "<td class='num'>" + (item.rrRank == null ? "—" : item.rrRank) + "</td>" +
      "<td class='num'>" + epiFmtNum(item.priority, 3) + "</td>" +
      "<td class='num'>" + (item.priorityRank == null ? "—" : item.priorityRank) + "</td>" +
      "</tr>";
  }).join("");
}

// Fills in the ▲/▼ glyph on whichever column header matches epiSortKey and
// clears it from every other header -- called once at setup and again
// whenever a header click changes epiSortKey/epiSortDir.
function updateEpiSortIndicators() {
  document.querySelectorAll("#epi-trends-table th[data-sort]").forEach(function(th) {
    const key = th.getAttribute("data-sort");
    const active = key === epiSortKey;
    const arrow = th.querySelector(".sort-arrow");
    th.classList.toggle("sort-active", active);
    th.setAttribute("aria-sort", active ? (epiSortDir === "desc" ? "descending" : "ascending") : "none");
    if (arrow) arrow.textContent = active ? (epiSortDir === "desc" ? "▼" : "▲") : "";
  });
}

function recomputeEpiTrends() {
  if (!INVASION_RISK) return;
  const invasionVals = [];
  const caseVals = [];
  Object.keys(INVASION_ZONES).forEach(function(nom) {
    const row = INVASION_ZONES[nom];
    if (!epiZoneVisible(row)) return;
    if (row.was_active_before) {
      const z = ZONE_DATA[nom] || {};
      const c = z.confirmed_cases;
      if (c != null && !Number.isNaN(Number(c)) && Number(c) > 0) caseVals.push(Number(c));
    } else if (row.p_case_invasion != null && !Number.isNaN(row.p_case_invasion)) {
      invasionVals.push(row.p_case_invasion);
    }
  });
  if (invasionVals.length) {
    epiInvasionDomain = {
      min: Math.min.apply(null, invasionVals),
      max: Math.max.apply(null, invasionVals),
      palette: PURPLES,
    };
    if (epiInvasionDomain.max === epiInvasionDomain.min) {
      epiInvasionDomain.max = epiInvasionDomain.min + 0.01;
    }
  } else {
    epiInvasionDomain = {min: 0, max: 1, palette: PURPLES};
  }
  if (caseVals.length) {
    const lo = Math.min.apply(null, caseVals);
    const hi = Math.max.apply(null, caseVals);
    epiCasesDomain = {
      min: lo,
      max: hi === lo ? lo * 10 : hi,
      isLog: true,
      palette: REDS,
    };
  } else {
    epiCasesDomain = {min: 1, max: 10, isLog: true, palette: REDS};
  }
  updateEpiTitle();
  updateEpiMetaNotes();
  renderEpiLegendBars();
  renderEpiTrendsTable();
  geoLayer.setStyle(styleFn);
  clearEpiLinks();
  if (flowArcsOverlayActive()) {
    renderFlowArcs(flowHubNom || epiSelectedNom, flowArcLayerDef());
  } else {
    clearFlowArcs();
  }
}

function epiTrendsStyleFn(feature) {
  const ref = feature.properties.nom;
  const row = INVASION_ZONES[ref];
  if (!row || !epiZoneVisible(row)) {
    return {color: "#111", weight: zoomWeight(0.25), fillOpacity: 0.04, fillColor: "#222"};
  }
  let fill = ZERO_FILL;
  let has = false;
  if (row.was_active_before) {
    const z = ZONE_DATA[ref] || {};
    const v = z.confirmed_cases;
    if (v != null && !Number.isNaN(Number(v))) {
      has = true;
      const num = Number(v);
      if (num <= 0) fill = ZERO_FILL;
      else {
        let t = (Math.log(num) - Math.log(epiCasesDomain.min)) /
          (Math.log(epiCasesDomain.max) - Math.log(epiCasesDomain.min) || 1);
        if (!isFinite(t)) t = 0;
        t = Math.max(0, Math.min(1, t));
        fill = rgb(lerpColor(epiCasesDomain.palette, t));
      }
    }
  } else if (row.p_case_invasion != null && !Number.isNaN(row.p_case_invasion)) {
    has = true;
    let t = (row.p_case_invasion - epiInvasionDomain.min) /
      (epiInvasionDomain.max - epiInvasionDomain.min || 1);
    if (!isFinite(t)) t = 0;
    t = Math.max(0, Math.min(1, t));
    fill = rgb(lerpColor(epiInvasionDomain.palette, t));
  }
  if (!has) {
    return {color: "#111", weight: zoomWeight(0.35), fillOpacity: 0};
  }
  let opacity = 0.82;
  let weight = zoomWeight(0.35);
  if (epiSelectedNom) {
    const focus = epiFocusNoms && epiFocusNoms.has(ref);
    if (ref === epiSelectedNom) {
      opacity = 0.95;
      weight = 1.8;
    } else if (focus) {
      opacity = 0.78;
      weight = 0.8;
    } else {
      opacity = 0.12;
    }
  }
  return {
    color: ref === epiSelectedNom ? "#ffae42" : "#111",
    weight: weight,
    fillColor: fill,
    fillOpacity: opacity,
  };
}

function enterEpiTrendsView() {
  if (!INVASION_RISK || !Object.keys(INVASION_ZONES).length) {
    const methodEl = document.getElementById("epi-trends-method");
    if (methodEl) methodEl.textContent = t("ui.epi_no_data");
  }
  hideProvinceOutlines();
  clearContextSelection();
  clearEpiLinks();
  const epiCases = document.getElementById("epi-show-cases");
  if (epiCases && showCasesBox) epiCases.checked = !!showCasesBox.checked;
  if (!epiSelectedNom) {
    flowHubNom = PAYLOAD.flow_default_hub || flowHubNom;
    clearFlowArcs();
  } else {
    flowHubNom = epiSelectedNom;
    renderFlowArcs(epiSelectedNom, flowArcLayerDef());
  }
  updateEpiMetaNotes();
}

function leaveEpiTrendsView() {
  epiSelectedNom = null;
  epiFocusNoms = null;
  hideEpiFloat();
  clearEpiLinks();
  clearFlowArcs();
  document.body.classList.remove("view-epi-trends", "epi-splitting");
}

const ZERO_FILL    = "#c4bfb6";
let currentValues = new Map();
let currentDomain = {min:0, max:1, isLog:true, palette:OUTBREAK};

function recompute() {
  const layer = getLayer(layerSelect.value);
  const highlightEpicenter = layerEpicenterHighlight(layer);
  currentValues.clear();
  const positives = [];
  let lo = Infinity, hi = -Infinity;
  for (const feat of PAYLOAD.geometry.features) {
    const ref = feat.properties.nom;
    const zone = ZONE_DATA[ref];
    if (!zone) continue;
    const v = valueForZone(ref, zone, layer);
    if (v == null || Number.isNaN(v)) {
      if (!highlightEpicenter || !isEpicenterZone(ref, layer)) continue;
      currentValues.set(ref, v);
      continue;
    }
    currentValues.set(ref, v);
    if (highlightEpicenter && isEpicenterZone(ref, layer)) continue;
    if (layerOriginHighlight(layer) && isMatrixOriginZone(ref, layer)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
    if (v > 0) positives.push(v);
  }
  if (!isFinite(lo)) { lo = 0; hi = 1; }
  // Log vs. linear is decided per layer on the backend (layer_config.yaml /
  // EXTRA_LAYER_DEFS' "scale" field), not by a user-facing toggle.
  const useLog = layer.scale === "log" && positives.length > 0;
  let dlo, dhi;
  if (useLog) {
    dlo = Math.min.apply(null, positives);
    dhi = Math.max.apply(null, positives);
    if (dhi === dlo) dhi = dlo * 10;
  } else {
    dlo = Math.min(0, lo);
    dhi = (hi === dlo) ? dlo + 1 : hi;
  }
  currentDomain = {min:dlo, max:dhi, isLog:useLog, palette:PALETTES[layer.palette] || PLASMA};
  geoLayer.setStyle(styleFn);
  if (flowArcsOverlayActive()) {
    renderFlowArcs(flowHubNom, flowArcLayerDef());
  } else {
    clearFlowArcs();
  }
  updateLegend(layer);
  updateLayerMeta(layer);
}

function valueToColor(v, ref, layer) {
  if (isHubZone(ref, layer)) return MATRIX_ORIGIN_FILL;
  if (isEpicenterZone(ref, layer)) return EPICENTER_FILL;
  const d = currentDomain;
  if (d.isLog && v <= 0) return ZERO_FILL;
  let t;
  if (d.isLog) t = (Math.log(v) - Math.log(d.min)) / (Math.log(d.max) - Math.log(d.min));
  else t = (v - d.min) / (d.max - d.min || 1);
  if (!isFinite(t)) t = 0;
  t = Math.max(0, Math.min(1, t));
  return rgb(lerpColor(d.palette, t));
}

function styleFn(feature) {
  if (activeView === "epi-trends") return epiTrendsStyleFn(feature);
  const ref = feature.properties.nom;
  const v = currentValues.get(ref);
  const has = v != null && !Number.isNaN(v);
  const layer = getLayer(layerSelect.value);
  if (isHubZone(ref, layer)) {
    return {
      color: "#111", weight: 1.6,
      fillColor: MATRIX_ORIGIN_FILL,
      fillOpacity: 0.92
    };
  }
  if (isEpicenterZone(ref, layer)) {
    return {
      color: "#111", weight: zoomWeight(0.5),
      fillColor: EPICENTER_FILL,
      fillOpacity: 0.88
    };
  }
  if (!has) {
    return { color: "#111", weight: zoomWeight(0.35), fillOpacity: 0 };
  }
  const isOutbreak = layer && layer.palette === "outbreak";
  const dataOpacity = isOutbreak ? 0.72 : 0.85;
  const mutedOpacity = isOutbreak ? 0.48 : 0.55;
  const isZero = currentDomain.isLog ? v <= 0 : v === 0;
  return {
    color:"#111", weight:zoomWeight(0.35),
    fillColor: valueToColor(v, ref, layer),
    fillOpacity: isZero ? mutedOpacity : dataOpacity
  };
}

function fmtLegend(v, round) {
  if (v == null || Number.isNaN(v)) return "—";
  if (typeof v !== "number") return String(v);
  if (round === "int" || round == null) return Math.round(v).toLocaleString();
  var d = Number(round);
  if (!isFinite(d)) return Math.round(v).toLocaleString();
  return v.toLocaleString(undefined, {minimumFractionDigits: d, maximumFractionDigits: d});
}

function fmt(v, kind) {
  if (v == null || Number.isNaN(v)) return "—";
  if (typeof v !== "number") return String(v);
  if (kind === "rel") return v.toFixed(2);
  if (kind === "cal") {
    if (Math.abs(v) < 1) return v.toFixed(1);
    return Math.round(v).toLocaleString();
  }
  return Math.round(v).toLocaleString();
}

function updateLayerMeta(layer) {
  let html = layer.source || "";
  if (layerUsesMatrix(layer)) {
    const originLine = tf("ui.matrix_origin", {origin: matrixOriginDisplayName()});
    html = (html ? html + "<br>" : "") + originLine;
  }
  if (flowArcsOverlayActive()) {
    const flowLayer = flowArcLayerDef();
    const hubLine = tf("ui.flow_hub", {hub: flowHubDisplayName()});
    html = (html ? html + "<br>" : "") + hubLine;
    if (flowArcStats) {
      html += "<br>" + tf("ui.flow_arc_summary", {
        outShown: flowArcStats.outShown,
        outTotal: flowArcStats.outTotal,
        inShown: flowArcStats.inShown,
        inTotal: flowArcStats.inTotal,
      });
    } else {
      const cat = flowCatalogForLayer(flowLayer);
      const hasHub = cat && (
        (cat.out_by_origin && cat.out_by_origin[flowHubNom]) ||
        (cat.in_by_dest && cat.in_by_dest[flowHubNom])
      );
      if (!hasHub) {
        html += "<br>" + t("ui.flow_no_data");
      }
    }
  }
  layerMeta.innerHTML = html;
}

function updateLegend(layer) {
  document.getElementById("legend-title").innerHTML = "<strong>" + layer.label + "</strong>";
  const stops = [];
  const N = 32;
  for (let i = 0; i < N; i++) {
    const t = i / (N - 1);
    stops.push(rgb(lerpColor(currentDomain.palette, t)) + " " + Math.round(t * 100) + "%");
  }
  document.getElementById("legend-bar").style.background = "linear-gradient(to right, " + stops.join(", ") + ")";
  const ticks = document.getElementById("legend-ticks");
  const lo = currentDomain.min, hi = currentDomain.max;
  const mid = currentDomain.isLog ? Math.sqrt(lo * hi) : (lo + hi) / 2;
  var lr = layer.legend_round != null ? layer.legend_round : "int";
  ticks.innerHTML =
    "<span>" + fmtLegend(lo,  lr) + "</span>" +
    "<span>" + fmtLegend(mid, lr) + "</span>" +
    "<span>" + fmtLegend(hi,  lr) + "</span>";
  document.getElementById("legend-scale").textContent =
    layer.legend_caption
      ? layer.legend_caption
      : (currentDomain.isLog ? t("ui.legend.log_scale") : t("ui.legend.linear_scale"));
  var grayParts = [
    "<span class='swatch' style='background:" + ZERO_FILL + "'></span>" + t("ui.legend.zero"),
    "<span class='swatch swatch-no-data'></span>" + t("ui.legend.no_data")
  ];
  if (layerEpicenterHighlight(layer)) {
    grayParts.push(
      "<span class='swatch' style='background:" + EPICENTER_FILL + "'></span>" + t("ui.legend.epicenter")
    );
  }
  if (layerUsesMatrix(layer) && layerOriginHighlight(layer)) {
    grayParts.push(
      "<span class='swatch' style='background:" + MATRIX_ORIGIN_FILL + "'></span>" + t("ui.legend.matrix_origin")
    );
  }
  if (flowArcsOverlayActive()) {
    grayParts.push(
      "<span class='swatch' style='background:" + FLOW_OUT_COLOR + "'></span>" + t("ui.legend.flow_out"),
      "<span class='swatch' style='background:" + FLOW_IN_COLOR + "'></span>" + t("ui.legend.flow_in")
    );
    const scaleEl = document.getElementById("legend-scale");
    scaleEl.textContent = (scaleEl.textContent || "") + " · " + t("ui.legend.flow_width");
  }
  document.getElementById("legend-gray").innerHTML = grayParts.join(" · ");
}

function infoHTML(feature) {
  const ref = feature.properties.nom;
  const z = ZONE_DATA[ref] || {};
  const name = feature.properties.name || t("ui.case_tooltip.unnamed");
  const info = t("ui.info");
  let h = "<div><strong>" + name + "</strong></div>";
  h += "<div style='color:#aaa;font-size:11px;margin-bottom:6px'>" + (ref || "—") + "</div>";

  // Trimmed to the fields Ciara asked to keep visible in the hover/click
  // panel: confirmed cases, confirmed deaths, population, health facilities,
  // incoming mobility, distance from the travel-matrix origin, and genomic
  // surveillance (when available). Total/suspected case counts, contact
  // tracing, testing capacity, and modeled relative-risk projection used to
  // show here too but were dropped to keep the panel shorter -- that data
  // still lives in ZONE_DATA/PAYLOAD if it needs to resurface elsewhere.
  h += "<h4>" + info.observed_cases + " (" + PAYLOAD.asof + ")</h4>";
  h += "<table>";
  h += "<tr><td>" + info.confirmed + "</td><td>" + fmt(z.confirmed_cases) + "</td></tr>";
  h += "<tr><td>" + info.confirmed_deaths + "</td><td>" + fmt(z.confirmed_deaths) + "</td></tr>";
  h += "</table>";

  h += "<h4>" + info.population + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.pop_count + "</td><td>" + fmt(z.worldpop__pop_count__pop_count) + "</td></tr>";
  h += "</table>";

  h += "<h4>" + info.health_facilities_grid3 + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.healthsite_count + "</td><td>" + fmt(z.grid3_healthsites__healthsite_count__healthsite_count) + "</td></tr>";
  h += "</table>";

  h += "<h4>" + info.incoming_mobility + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.displaced_12mo + "</td><td>" + fmt(z.displaced_in_individuals_12mo) + "</td></tr>";
  h += "<tr><td>" + info.flowminder_mar + "</td><td>" + fmt(z.flowminder_in_mar2026) + "</td></tr>";
  h += "<tr><td>" + info.flowminder_apr + "</td><td>" + fmt(z.flowminder_in_202604) + "</td></tr>";
  h += "<tr><td>" + info.flowminder_may + "</td><td>" + fmt(z.flowminder_short_trips__outflow_20260524__outflow_20260524, "cal") + "</td></tr>";
  h += "</table>";

  h += "<h4>" + tf("ui.info.distance_from", {origin: matrixOriginDisplayName()}) + "</h4>";
  h += "<table>";
  h += "<tr><td>" + info.travel_time_h + "</td><td>" + fmt(matrixValue("osrm__travel_time", matrixOriginNom, ref, 60)) + "</td></tr>";
  h += "<tr><td>" + info.road_distance_km + "</td><td>" + fmt(matrixValue("osrm__road_distance", matrixOriginNom, ref, 1)) + "</td></tr>";
  h += "</table>";

  if (z.genomic_sequence_count) {
    h += "<h4>" + info.genomic_surveillance + "</h4>";
    h += "<table>";
    h += "<tr><td>" + info.genome_sequences + "</td><td>" + fmt(z.genomic_sequence_count) + "</td></tr>";
    h += "</table>";
  }
  return h;
}

const geoLayer = L.geoJSON(PAYLOAD.geometry, {
  style: styleFn,
  onEachFeature: function (feature, layer) {
    layer.on({
      mouseover: function(e) {
        if (activeView === "trends") {
          if (trendsScope === "national") return;
          e.target.setStyle({weight: 1.6, color: "#ffae42"});
          e.target.bringToFront();
          return;
        }
        if (activeView === "context") {
          return;
        }
        if (activeView === "epi-trends") {
          e.target.setStyle({weight: 1.6, color: "#ffae42"});
          e.target.bringToFront();
          updateEpiFloat(feature.properties.nom, e.latlng);
          return;
        }
        e.target.setStyle({weight: 1.6, color: "#ffae42"});
        e.target.bringToFront();
        document.getElementById("info-body").className = "";
        document.getElementById("info-body").innerHTML = infoHTML(feature);
      },
      mouseout: function(e) {
        if (activeView === "trends") {
          geoLayer.resetStyle(e.target);
          if (trendsScope === "health_zone" && trendsSelectedKey &&
              feature.properties.nom === trendsSelectedKey) {
            e.target.setStyle({weight: 2, color: "#ffae42"});
          }
          return;
        }
        if (activeView === "context") {
          if (e.target !== contextSelectedLayer) {
            geoLayer.resetStyle(e.target);
          }
          return;
        }
        if (activeView === "epi-trends") {
          hideEpiFloat();
          geoLayer.resetStyle(e.target);
          return;
        }
        geoLayer.resetStyle(e.target);
      },
      click: function(e) {
        if (activeView === "trends") {
          L.DomEvent.stop(e);
          if (trendsScope === "national") return;
          if (trendsScope === "province") {
            setTrendsSelection(feature.properties.province || null);
            return;
          }
          if (trendsScope === "health_zone") {
            setTrendsSelection(feature.properties.nom || null);
            return;
          }
          return;
        }
        if (activeView === "context") {
          L.DomEvent.stop(e);
          // Re-clicking the selected zone toggles it off (empty-map click also
          // clears -- see the map "click" handler below).
          if (feature.properties.nom === contextSelectedNom) clearContextSelection();
          else selectContextZone(feature.properties.nom, e.target);
          return;
        }
        if (activeView === "epi-trends") {
          L.DomEvent.stop(e);
          // Re-clicking the already-selected zone toggles it off. Any other
          // zone switches the selection to it. (Clicking empty map also
          // clears -- see the map "click" handler below.)
          const nom = feature.properties.nom;
          setEpiSelected(nom === epiSelectedNom ? null : nom);
          return;
        }
        const layer = getLayer(layerSelect.value);
        if (activeView === "map" && flowArcsOverlayActive()) {
          L.DomEvent.stop(e);
          // Re-clicking the current flow origin clears it (arcs disappear);
          // empty-map click clears too -- see the map "click" handler below.
          const nom = feature.properties.nom;
          setFlowHub(nom === flowHubNom ? null : nom);
          return;
        }
        if (activeView === "map" && layerUsesMatrix(layer)) {
          L.DomEvent.stop(e);
          setMatrixOrigin(feature.properties.nom);
          return;
        }
        map.fitBounds(e.target.getBounds(), {padding:[40,40]});
      },
      dblclick: function(e) {
        if (activeView === "context") return;
        if (activeView === "trends" && trendsScope === "national") {
          return;
        }
        L.DomEvent.stop(e);
        map.fitBounds(e.target.getBounds(), {padding:[40,40]});
      }
    });
  }
}).addTo(map);

// Re-apply zone borders after a zoom so zoomWeight() picks up the new zoom.
// styleFn already encodes the map/epi-trends selection, so re-styling the whole
// layer preserves those; the trends/context selection highlight lives outside
// styleFn, so re-apply it.
map.on("zoomend", function () {
  geoLayer.setStyle(styleFn);
  if (activeView === "trends" && trendsScope === "health_zone" && trendsSelectedKey) {
    geoLayer.eachLayer(function (layer) {
      if (layer.feature && layer.feature.properties.nom === trendsSelectedKey) {
        layer.setStyle({weight: 2, color: "#ffae42"});
        layer.bringToFront();
      }
    });
  } else if (activeView === "context" && contextSelectedLayer) {
    contextSelectedLayer.setStyle({weight: 1.6, color: "#ffae42"});
    contextSelectedLayer.bringToFront();
  }
});

map.on("click", function() {
  if (activeView === "context") clearContextSelection();
  if (activeView === "epi-trends") setEpiSelected(null);
  // Snapshot: clearing the flow origin (arcs off) is its deselect. Only while
  // arcs are the active overlay -- matrix layers keep their origin, and their
  // arcs are already suppressed so flowArcsOverlayActive() is false there.
  if (activeView === "map" && flowArcsOverlayActive()) setFlowHub(null);
});

// --- health-zone search ---
const ZONE_SEARCH_INDEX = (PAYLOAD.geometry.features || []).map(function(feat) {
  const props = feat.properties || {};
  const name = props.name || props.nom || "";
  const nom = props.nom || "";
  return {
    nom: nom,
    name: name,
    label: name,
    haystack: (name + " " + nom).toLowerCase(),
  };
}).filter(function(z) { return !!z.nom; })
  .sort(function(a, b) {
    return String(a.name).localeCompare(String(b.name), undefined, {sensitivity: "base"});
  });

// --- Trends tab location search: every province + health zone, regardless
// of whether a plot happens to exist for it (unlike the old trendsEntityList()
// approach, which only ever listed places trendsPlotData() had a plot for).
// Mirrors ZONE_SEARCH_INDEX above so behaviour matches the Current Snapshot
// search, just also covering provinces since Trends has a province scope.
const TRENDS_LOCATION_INDEX = (function() {
  const provinceNames = {};
  (PAYLOAD.province_boundaries && PAYLOAD.province_boundaries.features || []).forEach(function(feat) {
    const name = feat.properties && feat.properties.province;
    if (name) provinceNames[name] = true;
  });
  const provinces = Object.keys(provinceNames).map(function(name) {
    return {id: name, label: name, kind: "province", haystack: name.toLowerCase()};
  });
  const zones = ZONE_SEARCH_INDEX.map(function(z) {
    return {id: z.nom, label: z.name, kind: "health_zone", haystack: z.haystack};
  });
  return provinces.concat(zones).sort(function(a, b) {
    return String(a.label).localeCompare(String(b.label), undefined, {sensitivity: "base"});
  });
})();

const zoneSearchInput = document.getElementById("zone-search-input");
const zoneSearchResults = document.getElementById("zone-search-results");
const zoneSearchWrap = document.getElementById("zone-search-wrap");
let zoneSearchMatches = [];
let zoneSearchActiveIdx = -1;
let searchHighlightLayer = null;
let searchHighlightTimer = null;

function findGeoLayerByNom(nom) {
  let found = null;
  geoLayer.eachLayer(function(layer) {
    if (!found && layer.feature && layer.feature.properties && layer.feature.properties.nom === nom) {
      found = layer;
    }
  });
  return found;
}

function clearSearchHighlight() {
  if (searchHighlightTimer) {
    clearTimeout(searchHighlightTimer);
    searchHighlightTimer = null;
  }
  if (searchHighlightLayer && searchHighlightLayer !== contextSelectedLayer) {
    geoLayer.resetStyle(searchHighlightLayer);
  }
  searchHighlightLayer = null;
}

function closeZoneSearchResults() {
  if (!zoneSearchResults) return;
  zoneSearchResults.hidden = true;
  zoneSearchResults.innerHTML = "";
  zoneSearchMatches = [];
  zoneSearchActiveIdx = -1;
  if (zoneSearchInput) zoneSearchInput.setAttribute("aria-expanded", "false");
}

function renderZoneSearchResults(query) {
  if (!zoneSearchResults) return;
  const q = String(query || "").trim().toLowerCase();
  if (!q) {
    closeZoneSearchResults();
    return;
  }
  zoneSearchMatches = ZONE_SEARCH_INDEX.filter(function(z) {
    return z.haystack.indexOf(q) !== -1;
  }).slice(0, 12);
  zoneSearchActiveIdx = zoneSearchMatches.length ? 0 : -1;
  if (!zoneSearchMatches.length) {
    zoneSearchResults.innerHTML =
      "<div class='zone-search-empty' data-i18n-live='1'>" + t("ui.zone_search_no_matches") + "</div>";
    zoneSearchResults.hidden = false;
    if (zoneSearchInput) zoneSearchInput.setAttribute("aria-expanded", "true");
    return;
  }
  zoneSearchResults.innerHTML = zoneSearchMatches.map(function(z, i) {
    return (
      "<button type='button' class='zone-search-option" + (i === 0 ? " active" : "") +
      "' role='option' data-nom='" + escHtml(z.nom) + "'>" + escHtml(z.label) + "</button>"
    );
  }).join("");
  zoneSearchResults.hidden = false;
  if (zoneSearchInput) zoneSearchInput.setAttribute("aria-expanded", "true");
}

function setZoneSearchActive(idx) {
  if (!zoneSearchMatches.length) return;
  zoneSearchActiveIdx = Math.max(0, Math.min(idx, zoneSearchMatches.length - 1));
  const opts = zoneSearchResults.querySelectorAll(".zone-search-option");
  opts.forEach(function(el, i) {
    el.classList.toggle("active", i === zoneSearchActiveIdx);
  });
  const active = opts[zoneSearchActiveIdx];
  if (active && active.scrollIntoView) active.scrollIntoView({block: "nearest"});
}

function selectHealthZone(nom) {
  const layer = findGeoLayerByNom(nom);
  if (!layer || !layer.feature) return;
  const feature = layer.feature;
  const displayName = feature.properties.name || nom;

  if (activeView === "context") {
    selectContextZone(nom, layer);
    map.fitBounds(layer.getBounds(), {padding: [40, 40], maxZoom: 10});
  } else if (activeView === "map") {
    clearSearchHighlight();
    if (flowArcsOverlayActive()) {
      setFlowHub(nom);
    } else if (layerUsesMatrix(getLayer(layerSelect.value))) {
      setMatrixOrigin(nom);
    }
    map.fitBounds(layer.getBounds(), {padding: [40, 40], maxZoom: 10});
    layer.setStyle({weight: 1.6, color: "#ffae42"});
    layer.bringToFront();
    searchHighlightLayer = layer;
    const infoBody = document.getElementById("info-body");
    if (infoBody) {
      infoBody.className = "";
      infoBody.innerHTML = infoHTML(feature);
    }
    searchHighlightTimer = setTimeout(function() {
      if (searchHighlightLayer === layer && layer !== contextSelectedLayer) {
        geoLayer.resetStyle(layer);
      }
      searchHighlightLayer = null;
      searchHighlightTimer = null;
    }, 2500);
  }

  if (zoneSearchInput) zoneSearchInput.value = displayName;
  closeZoneSearchResults();
}

if (zoneSearchWrap) {
  L.DomEvent.disableClickPropagation(zoneSearchWrap);
  L.DomEvent.disableScrollPropagation(zoneSearchWrap);
}

if (zoneSearchInput && zoneSearchResults) {
  zoneSearchInput.addEventListener("input", function() {
    renderZoneSearchResults(zoneSearchInput.value);
  });
  zoneSearchInput.addEventListener("focus", function() {
    if (zoneSearchInput.value.trim()) renderZoneSearchResults(zoneSearchInput.value);
  });
  zoneSearchInput.addEventListener("keydown", function(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (zoneSearchResults.hidden) renderZoneSearchResults(zoneSearchInput.value);
      setZoneSearchActive(zoneSearchActiveIdx + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setZoneSearchActive(zoneSearchActiveIdx - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (zoneSearchActiveIdx >= 0 && zoneSearchMatches[zoneSearchActiveIdx]) {
        selectHealthZone(zoneSearchMatches[zoneSearchActiveIdx].nom);
      } else if (!zoneSearchResults.hidden && zoneSearchMatches[0]) {
        selectHealthZone(zoneSearchMatches[0].nom);
      }
    } else if (e.key === "Escape") {
      closeZoneSearchResults();
      zoneSearchInput.blur();
    }
  });
  zoneSearchResults.addEventListener("mousedown", function(e) {
    const btn = e.target.closest(".zone-search-option");
    if (!btn) return;
    e.preventDefault();
    selectHealthZone(btn.getAttribute("data-nom"));
  });
  document.addEventListener("click", function(e) {
    if (!zoneSearchWrap) return;
    if (!zoneSearchWrap.contains(e.target)) closeZoneSearchResults();
  });
}

// --- province outlines (Trends view) ---
let trendsScope = "national";
let trendsSelectedKey = null;
let trendsHoverTimer = null;
let trendsHoveredProvince = null;
function themeVar(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}
function provinceOutlineStyle(selected) {
  const provinceMode = activeView === "trends" && trendsScope === "province";
  const baseWeight = provinceMode
    ? parseFloat(themeVar("--province-outline-weight-wide", "1.4"))
    : parseFloat(themeVar("--province-outline-weight", "1"));
  const selWeight = provinceMode
    ? parseFloat(themeVar("--province-outline-weight-wide-hover", "2"))
    : parseFloat(themeVar("--province-outline-weight-hover", "1.5"));
  return {
    color: selected
      ? themeVar("--province-outline-hover", "#b23b2e")
      : themeVar("--province-outline", "#9b7d4e"),
    weight: selected ? selWeight : baseWeight,
    opacity: selected ? 1 : (provinceMode ? 0.95 : 0.88),
    fillOpacity: 0,
  };
}

map.createPane("province-outline");
map.getPane("province-outline").style.zIndex = 550;
const provinceOutlineLayer = L.geoJSON(PAYLOAD.province_boundaries || {type:"FeatureCollection", features:[]}, {
  pane: "province-outline",
  interactive: false,
  style: function() {
    return provinceOutlineStyle(false);
  },
});

function applyProvinceOutlineStyles(selectedProvince) {
  trendsHoveredProvince = selectedProvince || null;
  document.body.classList.toggle("trends-province-hovered", !!trendsHoveredProvince);
  provinceOutlineLayer.eachLayer(function(layer) {
    const match = trendsHoveredProvince &&
      layer.feature.properties.province === trendsHoveredProvince;
    layer.setStyle(provinceOutlineStyle(!!match));
    if (match) layer.bringToFront();
  });
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderTrendsPanel(_unused) {
  renderTrendsPlots();
}

function setTrendsProvinceHover(province) {
  // Kept for compatibility; selection-driven plots replace hover plots.
  if (activeView === "trends" && trendsScope === "province" && !trendsSelectedKey) {
    applyProvinceOutlineStyles(province || null);
  }
}

function trendsPlotData() {
  return PAYLOAD.onset_trends || null;
}

function trendsIndexes() {
  const data = trendsPlotData();
  return (data && data.indexes) || {};
}

function trendsIndexEntry(bucket, key) {
  if (!key) return null;
  const entries = trendsIndexes()[bucket] || {};
  if (entries[key]) return entries[key];
  const target = String(key).toLowerCase();
  const keys = Object.keys(entries);
  for (let i = 0; i < keys.length; i++) {
    if (String(keys[i]).toLowerCase() === target) return entries[keys[i]];
  }
  return null;
}

// Always returns a real array, however the manifest happens to have shaped
// lab_codes (missing, a single string, etc.) -- a non-array value here used
// to reach a bare .forEach() downstream and throw, which silently froze the
// whole labs card (the exception aborted renderTrendsLabs() before it could
// update the DOM, so it just kept showing whatever the previous selection
// had rendered).
function asCodeArray(v) {
  if (Array.isArray(v)) return v;
  if (v == null || v === "") return [];
  return [v];
}

function trendsLabCodesForSelection() {
  if (trendsScope === "health_zone" && trendsSelectedKey) {
    const entry = trendsIndexEntry("by_health_zone", trendsSelectedKey);
    return asCodeArray(entry && entry.lab_codes);
  }
  if (trendsScope === "province" && trendsSelectedKey) {
    const entry = trendsIndexEntry("by_province", trendsSelectedKey);
    return asCodeArray(entry && entry.lab_codes);
  }
  return [];
}

// Normalizes a place name for cross-dataset matching: strips accents,
// drops parenthetical suffixes ("Idiofa (Secteur)"), and collapses
// punctuation/whitespace. Health zone naming has historically drifted a bit
// between data feeds (see _NAME_TO_NOM on the Python side), so lab metadata
// doesn't always spell a zone name exactly the same way the case/geometry
// data does.
function normalizeLabLocationKey(s) {
  return String(s || "")
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/\([^)]*\)/g, "")
    .replace(/[^a-z0-9]+/gi, " ")
    .trim()
    .toLowerCase();
}

function trendsLabsForSelection() {
  const data = trendsPlotData() || {};
  const labs = data.labs || [];
  // National shows every lab -- no province/health-zone subsetting needed.
  if (trendsScope === "national") return labs;
  if (!trendsSelectedKey) return [];

  // Match each lab's own health_zone/province field against the current
  // selection directly, rather than relying solely on the manifest's
  // indexes.by_health_zone/by_province reverse lookup -- in practice that
  // index hasn't always been populated for every health zone.
  const candidateKeys = (trendsScope === "health_zone"
    ? [trendsSelectedKey, zoneDisplayName(trendsSelectedKey)]
    : [trendsSelectedKey]
  ).map(normalizeLabLocationKey).filter(Boolean);
  const labField = trendsScope === "health_zone" ? "health_zone" : "province";
  const direct = labs.filter(function(lab) {
    const val = lab[labField];
    return val && candidateKeys.indexOf(normalizeLabLocationKey(val)) !== -1;
  });

  // Union in anything the manifest's index knows about that the direct
  // field match missed.
  const codes = trendsLabCodesForSelection();
  if (codes.length) {
    const byCode = data.labs_by_code || {};
    const seen = new Set(direct.map(function(l) { return l.lab_code || l.id; }));
    codes.forEach(function(code) {
      const lab = byCode[code];
      const key = lab && (lab.lab_code || lab.id);
      if (lab && key && !seen.has(key)) {
        direct.push(lab);
        seen.add(key);
      }
    });
  }
  return direct;
}

function findTrendsLab(id) {
  const labs = (trendsPlotData() && trendsPlotData().labs) || [];
  for (let i = 0; i < labs.length; i++) {
    if (labs[i].id === id) return labs[i];
  }
  return null;
}

function trendsEntityList() {
  const data = trendsPlotData();
  if (!data) return [];
  if (trendsScope === "province") {
    return Object.keys(data.provinces || data.plots || {}).sort(function(a, b) {
      return String(a).localeCompare(String(b), undefined, {sensitivity: "base"});
    }).map(function(id) {
      return {id: id, label: id, kind: "province"};
    });
  }
  if (trendsScope === "health_zone") {
    return Object.keys(data.health_zones || {}).sort(function(a, b) {
      return String(a).localeCompare(String(b), undefined, {sensitivity: "base"});
    }).map(function(id) {
      return {id: id, label: zoneDisplayName(id) || id, kind: "health_zone"};
    });
  }
  return [{id: "national", label: t("ui.trends_scope_national"), kind: "national"}];
}

function resolveTrendsPlot() {
  const data = trendsPlotData();
  if (!data) return null;
  if (trendsScope === "national") return data.national || null;
  if (trendsScope === "province") {
    if (!trendsSelectedKey) return null;
    return (data.provinces && data.provinces[trendsSelectedKey]) ||
      (data.plots && data.plots[trendsSelectedKey]) || null;
  }
  if (trendsScope === "health_zone") {
    if (!trendsSelectedKey) return null;
    return (data.health_zones && data.health_zones[trendsSelectedKey]) || null;
  }
  return null;
}

// Every plot SVG from the data pipeline bakes its own chart title into the
// top of the image (in the same spot the card header's title already
// shows), plus a bit of margin above the actual chart panel. Rather than
// leaving that redundant text (and blank space) visible, shift the SVG's
// viewBox down to crop it off entirely instead of just visually clipping a
// gap. Every plot type currently shares the same 648x324 canvas with a
// 25.28pt top margin before the chart panel starts, so one fixed crop
// works everywhere; if a plot ever uses a different margin, the regex
// simply won't match cleanly enough to matter -- worst case the title
// stays visible rather than the chart getting mangled.
const PLOT_SVG_TITLE_CROP = 40.56; // 26 + 20% + 30%
function cropPlotSvgTop(svg, cropPx) {
  if (!svg) return svg;
  const m = svg.match(/viewBox=(['"])\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\1/);
  if (!m) return svg;
  const quote = m[1];
  const minX = parseFloat(m[2]);
  const minY = parseFloat(m[3]);
  const w = parseFloat(m[4]);
  const h = parseFloat(m[5]);
  if (!isFinite(minX) || !isFinite(minY) || !isFinite(w) || !isFinite(h)) return svg;
  if (!(cropPx > 0) || cropPx >= h) return svg;
  const newViewBox = minX + " " + (minY + cropPx) + " " + w + " " + (h - cropPx);
  return svg.replace(m[0], "viewBox=" + quote + newViewBox + quote);
}

// Shared renderer for every card in #trends-plots-column: fills in the SVG
// (or an appropriate empty-state message) for whichever plot was resolved.
// #trends (confirmed cases), #trends-deaths (cumulative deaths), and
// #trends-positivity (rolling test positivity) all use this -- future plot
// cards should too, rather than re-implementing the empty-state copy.
function renderPlotCard(titleId, bodyId, plot, fallbackTitleKey) {
  const titleEl = document.getElementById(titleId);
  const body = document.getElementById(bodyId);
  if (!body) return;
  if (plot && plot.svg) {
    // Built from the localized plot-type label + place name rather than
    // plot.title (the SVG's own baked title) -- that text is generated once
    // in English by the data pipeline and never changes with the language
    // toggle. Place names (provinces/health zones) are proper nouns with no
    // separate French form in this dataset, so only the type label and
    // "National" need localizing.
    if (titleEl) {
      const place = plot.id === "national" ? t("ui.trends_scope_national") : (plot.label || plot.id || "");
      titleEl.textContent = place ? (t(fallbackTitleKey) + " - " + place) : t(fallbackTitleKey);
    }
    body.className = "panel-body";
    body.innerHTML = "<div class='onset-chart-wrap'>" + cropPlotSvgTop(plot.svg, PLOT_SVG_TITLE_CROP) + "</div>";
    return;
  }
  if (titleEl) titleEl.textContent = t(fallbackTitleKey);
  body.className = "panel-body trends-empty";
  if (trendsScope === "national") {
    body.innerHTML = "<p>" + escHtml(t("ui.trends_no_plot").replace("{name}", t("ui.trends_scope_national"))) + "</p>";
  } else if (trendsScope === "province") {
    body.innerHTML = "<p>" + escHtml(
      trendsSelectedKey
        ? tf("ui.trends_no_plot", {name: trendsSelectedKey})
        : t("ui.trends_select_province")
    ) + "</p>";
  } else if (trendsScope === "health_zone") {
    body.innerHTML = "<p>" + escHtml(
      trendsSelectedKey
        ? tf("ui.trends_no_plot", {name: zoneDisplayName(trendsSelectedKey) || trendsSelectedKey})
        : t("ui.trends_select_health_zone")
    ) + "</p>";
  }
}

function renderTrendsPlot() {
  renderPlotCard("trends-title", "trends-body", resolveTrendsPlot(), "ui.trends_panel");
}

function resolveCumulativeDeathsPlot() {
  const data = trendsPlotData();
  const deaths = data && data.cumulative_deaths;
  if (!deaths) return null;
  if (trendsScope === "national") return deaths.national || null;
  if (trendsScope === "province") {
    if (!trendsSelectedKey) return null;
    return (deaths.provinces && deaths.provinces[trendsSelectedKey]) || null;
  }
  if (trendsScope === "health_zone") {
    if (!trendsSelectedKey) return null;
    return (deaths.health_zones && deaths.health_zones[trendsSelectedKey]) || null;
  }
  return null;
}

function resolveRollingPositivityPlot() {
  const data = trendsPlotData();
  const positivity = data && data.rolling_positivity;
  if (!positivity) return null;
  if (trendsScope === "national") return positivity.national || null;
  if (trendsScope === "province") {
    if (!trendsSelectedKey) return null;
    return (positivity.provinces && positivity.provinces[trendsSelectedKey]) || null;
  }
  if (trendsScope === "health_zone") {
    if (!trendsSelectedKey) return null;
    return (positivity.health_zones && positivity.health_zones[trendsSelectedKey]) || null;
  }
  return null;
}

function renderCumulativeDeathsPlot() {
  renderPlotCard("trends-deaths-title", "trends-deaths-body", resolveCumulativeDeathsPlot(), "ui.trends_deaths_panel");
}

function renderRollingPositivityPlot() {
  renderPlotCard("trends-positivity-title", "trends-positivity-body", resolveRollingPositivityPlot(), "ui.trends_positivity_panel");
}

function trendsSelectionLabel() {
  if (trendsScope === "national") return t("ui.trends_scope_national");
  if (!trendsSelectedKey) return "";
  if (trendsScope === "health_zone") {
    return zoneDisplayName(trendsSelectedKey) || trendsSelectedKey;
  }
  return trendsSelectedKey;
}

function renderTrendsLabs() {
  const card = document.getElementById("trends-labs");
  const titleEl = document.getElementById("trends-labs-title");
  const body = document.getElementById("trends-labs-body");
  if (!card || !body) return;

  // National always shows (every lab); province/health zone need a selection first.
  const show = trendsScope === "national" ||
    ((trendsScope === "province" || trendsScope === "health_zone") && trendsSelectedKey);
  card.style.display = show ? "" : "none";
  if (!show) {
    body.innerHTML = "";
    body.className = "panel-body trends-empty";
    return;
  }

  // Set the title before computing labs: an unexpected manifest/lab data
  // shape used to throw inside trendsLabsForSelection() and silently freeze
  // this whole card -- everything after the throw (including the title)
  // never ran, so it just kept showing the previous selection.
  const locationLabel = trendsSelectionLabel();
  if (titleEl) {
    titleEl.textContent = tf("ui.trends_labs_panel", {location: locationLabel});
  }

  let labs = [];
  try {
    labs = trendsLabsForSelection();
  } catch (err) {
    console.error("trendsLabsForSelection failed for", trendsScope, trendsSelectedKey, err);
    labs = [];
  }

  if (!labs.length) {
    body.className = "panel-body trends-empty";
    body.innerHTML = "<p>" + escHtml(tf("ui.trends_no_labs", {name: locationLabel})) + "</p>";
    return;
  }

  try {
    body.className = "panel-body trends-labs-body";
    body.innerHTML = labs.map(function(lab) {
      return "<div class='trends-lab-subplot'>" +
        "<h4 class='trends-lab-subplot-title'>" + escHtml(lab.label || lab.lab_code || lab.id) + "</h4>" +
        "<div class='onset-chart-wrap'>" + cropPlotSvgTop(lab.svg, PLOT_SVG_TITLE_CROP) + "</div>" +
        "</div>";
    }).join("");
  } catch (err) {
    console.error("renderTrendsLabs markup failed for", trendsScope, trendsSelectedKey, err);
    body.className = "panel-body trends-empty";
    body.innerHTML = "<p>" + escHtml(tf("ui.trends_no_labs", {name: locationLabel})) + "</p>";
  }
}

// Renders every card in the plots column. Call sites that used to call
// renderTrendsPlot() directly now call this instead, so the deaths card
// (and any future card) stays in sync with the scope/selection too.
function renderTrendsPlots() {
  renderTrendsPlot();
  renderCumulativeDeathsPlot();
  renderRollingPositivityPlot();
  renderTrendsLabs();
}

// fitMapToTrendsSelection() used to live here and auto pan/zoom the map to
// whichever province/health zone was selected, with padding carved out for
// the old floating trends panel that used to sit on top of the map. Now
// that the map and plots panel are two separate fixed columns (nothing
// overlaps), that auto-pan just made the map jump around distractingly on
// every click, so it's been removed -- selecting a zone/province no longer
// moves the map at all.

function setTrendsSelection(key, opts) {
  opts = opts || {};
  trendsSelectedKey = key || null;
  if (trendsScope === "province") {
    applyProvinceOutlineStyles(trendsSelectedKey);
  } else if (trendsScope === "health_zone") {
    applyProvinceOutlineStyles(null);
  } else {
    applyProvinceOutlineStyles(null);
  }
  renderTrendsPlots();
  if (activeView === "trends") {
    // Restyle health-zone polygons to emphasize selection.
    geoLayer.setStyle(styleFn);
    if (trendsScope === "health_zone" && trendsSelectedKey) {
      geoLayer.eachLayer(function(layer) {
        if (layer.feature && layer.feature.properties.nom === trendsSelectedKey) {
          layer.setStyle({weight: 2, color: "#ffae42"});
          layer.bringToFront();
        }
      });
    }
  }
  if (opts.fromSearch) {
    const input = document.getElementById("trends-search-input");
    const results = document.getElementById("trends-search-results");
    if (input) input.value = "";
    if (results) {
      results.classList.remove("open");
      results.innerHTML = "";
    }
  }
}

function setTrendsScope(scope) {
  trendsScope = scope || "national";
  trendsSelectedKey = null;
  applyProvinceOutlineStyles(null);
  renderTrendsPlots();
  if (activeView === "trends") {
    geoLayer.setStyle(styleFn);
    showProvinceOutlines();
  }
}

function renderTrendsSearchResults(query) {
  const root = document.getElementById("trends-search-results");
  if (!root) return;
  const q = String(query || "").trim().toLowerCase();
  // Only open the match list once the user starts typing. Search covers
  // every province/health zone regardless of current scope or plot
  // availability -- picking a result switches scope automatically.
  if (!q) {
    root.classList.remove("open");
    root.innerHTML = "";
    return;
  }
  let items = TRENDS_LOCATION_INDEX.filter(function(it) {
    return it.haystack.indexOf(q) >= 0;
  });
  if (!items.length) {
    root.innerHTML = "<div class='zone-search-empty'>" + escHtml(t("ui.zone_search_no_matches") || "No matches") + "</div>";
    root.classList.add("open");
    return;
  }
  // Keep enough matches that the expanded panel can fill its ≥5-hit capacity.
  root.innerHTML = items.slice(0, 40).map(function(it) {
    return "<button type='button' role='option' data-id='" + escHtml(it.id) + "' data-kind='" + escHtml(it.kind) + "'>" +
      escHtml(it.label) + "</button>";
  }).join("");
  root.classList.add("open");
}

function syncTrendsPlayButton() {
  const btn = document.getElementById("trends-play-btn");
  if (!btn) return;
  btn.classList.toggle("playing", !!trendsSliderAnimating);
  // Actual play/pause glyphs -- no need to localize the symbol itself, but
  // the accessible name still is (aria-label), same strings as before.
  btn.textContent = trendsSliderAnimating ? "⏸" : "▶";
  btn.setAttribute("aria-label", trendsSliderAnimating ? t("ui.trends_pause") : t("ui.trends_play"));
}

function formatContextDate(raw) {
  if (!raw) return "";
  const s = String(raw).trim();
  if (!s) return "";
  if (s.length >= 10 && s[2] === "-" && s[5] === "-") {
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const d = parseInt(s.slice(0, 2), 10);
    const m = parseInt(s.slice(3, 5), 10);
    const y = s.slice(6, 10);
    if (m >= 1 && m <= 12 && d >= 1) {
      return String(d) + " " + months[m - 1] + " " + y;
    }
  }
  if (s.length >= 10 && s[4] === "-" && s[7] === "-") {
    const parts = s.slice(0, 10).split("-");
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const m = parseInt(parts[1], 10);
    const d = parseInt(parts[2], 10);
    if (m >= 1 && m <= 12 && d >= 1) {
      return String(d) + " " + months[m - 1] + " " + parts[0];
    }
  }
  if (s.indexOf("/") >= 0) {
    const bits = s.split("/");
    if (bits.length === 3) {
      const a = parseInt(bits[0], 10), b = parseInt(bits[1], 10);
      let y = parseInt(bits[2], 10);
      if (y < 100) y += 2000;
      const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
      const day = a > 12 ? a : b;
      const month = a > 12 ? b : a;
      if (month >= 1 && month <= 12) {
        return String(day) + " " + months[month - 1] + " " + y;
      }
    }
  }
  return s;
}

function contextDateSortKey(pillar) {
  if (pillar && pillar.date_iso) {
    const t = Date.parse(pillar.date_iso);
    if (!isNaN(t)) return t;
  }
  const raw = pillar ? pillar.date : null;
  if (raw == null) return Number.NEGATIVE_INFINITY;
  const s = String(raw).trim();
  if (!s) return Number.NEGATIVE_INFINITY;
  if (s.length >= 10 && s[2] === "-" && s[5] === "-") {
    const d = parseInt(s.slice(0, 2), 10);
    const m = parseInt(s.slice(3, 5), 10) - 1;
    const y = parseInt(s.slice(6, 10), 10);
    const t = Date.UTC(y, m, d);
    if (!isNaN(t)) return t;
  }
  if (s.length >= 10 && s[4] === "-" && s[7] === "-") {
    const t = Date.parse(s.slice(0, 10));
    if (!isNaN(t)) return t;
  }
  if (s.indexOf("/") >= 0) {
    const bits = s.split("/");
    if (bits.length === 3) {
      const a = parseInt(bits[0], 10), b = parseInt(bits[1], 10);
      let y = parseInt(bits[2], 10);
      if (y < 100) y += 2000;
      const day = a > 12 ? a : b;
      const month = (a > 12 ? b : a) - 1;
      const t = Date.UTC(y, month, day);
      if (!isNaN(t)) return t;
    }
  }
  return Number.NEGATIVE_INFINITY;
}

function sortContextPillarsByDate(pillars) {
  return pillars.slice().sort(function(a, b) {
    const diff = contextDateSortKey(b) - contextDateSortKey(a);
    if (diff !== 0) return diff;
    return phrLabel(a).localeCompare(phrLabel(b));
  });
}

function phrPillarCategoryClass(pillar) {
  const cat = pillar.category || (pillar.metric || "").replace(/^national_/, "").replace(/^provincial_/, "");
  if (!cat) return "";
  return "pillar-" + cat.replace(/_/g, "-");
}

function phrLabel(pillar) {
  const key = (pillar.metric || "").replace(/^national_/, "").replace(/^provincial_/, "");
  const labels = t("phr");
  if (labels && typeof labels === "object" && labels[key]) return labels[key];
  return pillar.label || key;
}

function phrScopeStamp(pillar) {
  if (pillar && pillar.scope_tag && pillar.scope !== "national" && pillar.scope !== "zone") {
    return pillar.scope_tag;
  }
  if (!pillar) return "";
  if (pillar.scope === "national") return t("scope_tags.national");
  if (pillar.scope === "provincial" && pillar.province) {
    return String(pillar.province).toUpperCase();
  }
  if (pillar.scope === "zone") return t("scope_tags.health_zone");
  return pillar.scope_tag || "";
}

function renderContextPillarHtml(pillar, opts) {
  opts = opts || {};
  const catClass = phrPillarCategoryClass(pillar);
  let meta = "";
  if (!opts.hideScopeTag) {
    const stamp = phrScopeStamp(pillar);
    if (stamp) meta = "<span class='scope-tag'>" + escHtml(stamp) + "</span>";
  }
  const dateStr = formatContextDate(pillar.date);
  if (dateStr) meta += "<span>" + t("ui.context_as_of") + " " + escHtml(dateStr) + "</span>";
  const metaBlock = meta ? "<div class='context-meta'>" + meta + "</div>" : "";
  return (
    "<div class='context-pillar " + catClass + "'>" +
      "<h4>" + escHtml(phrLabel(pillar)) + "</h4>" +
      metaBlock +
      "<p>" + escHtml(pillar.text) + "</p>" +
    "</div>"
  );
}

function zoneFeatureProps(nom) {
  for (const feat of PAYLOAD.geometry.features) {
    if (feat.properties.nom === nom) {
      return feat.properties;
    }
  }
  return null;
}

function zoneDisplayName(nom) {
  const props = zoneFeatureProps(nom);
  return props ? (props.name || nom) : nom;
}

function zoneProvince(nom) {
  const props = zoneFeatureProps(nom);
  return props ? (props.province || null) : null;
}

function phrContext() {
  const byLang = (I18N.phr_context || PAYLOAD.phr_context_by_lang || null);
  if (byLang && (byLang.en || byLang.fr)) {
    return byLang[currentLang] || byLang.en || {national: [], by_nom: {}};
  }
  const legacy = PAYLOAD.phr_context || {};
  if (legacy.national || legacy.by_nom) return legacy;
  return {national: [], by_nom: {}};
}

function filterRollupsForContext(nom) {
  const allRollups = phrContext().national || [];
  if (!nom) {
    return allRollups.filter(function(p) { return p.scope === "national"; });
  }
  const province = zoneProvince(nom);
  return allRollups.filter(function(p) {
    if (p.scope === "national") return true;
    if (p.scope === "provincial" && province && p.province === province) return true;
    return false;
  });
}

function renderNationalContextPanel(nom) {
  const body = document.getElementById("context-national-body");
  if (!body) return;
  body.scrollTop = 0;
  const rollups = filterRollupsForContext(nom);
  if (!rollups.length) {
    body.className = "panel-body context-empty";
    body.innerHTML = nom
      ? "<p>" + t("ui.context_no_national_area") + "</p>"
      : "<p>" + t("ui.context_no_national") + "</p>";
    return;
  }
  body.className = "panel-body";
  body.innerHTML = sortContextPillarsByDate(rollups).map(function(p) {
    return renderContextPillarHtml(p);
  }).join("");
}

let contextSelectedNom = null;
let contextSelectedLayer = null;

function clearContextSelection() {
  if (contextSelectedLayer) {
    geoLayer.resetStyle(contextSelectedLayer);
    contextSelectedLayer = null;
  }
  contextSelectedNom = null;
  renderContextPanel(null);
}

function selectContextZone(nom, layer) {
  if (!nom || !layer) return;
  if (contextSelectedLayer && contextSelectedLayer !== layer) {
    geoLayer.resetStyle(contextSelectedLayer);
  }
  contextSelectedNom = nom;
  contextSelectedLayer = layer;
  layer.setStyle({weight: 1.6, color: "#ffae42"});
  layer.bringToFront();
  renderContextPanel(nom);
}

function renderContextPanel(nom) {
  const body = document.getElementById("context-body");
  const title = document.getElementById("context-title");
  if (!body) return;
  document.body.classList.toggle("context-zone-hovered", !!nom);
  renderNationalContextPanel(nom);
  body.scrollTop = 0;
  if (!nom) {
    if (title) title.textContent = t("ui.context_zone");
    body.className = "panel-body context-empty";
    body.innerHTML = "<p>" + t("ui.context_click_zone") + "</p>";
    return;
  }
  const zonePillars = (phrContext().by_nom || {})[nom] || [];
  const displayName = zoneDisplayName(nom);
  if (title) title.textContent = displayName;
  if (!zonePillars.length) {
    body.className = "panel-body context-empty";
    body.innerHTML = "<p>" + tf("ui.context_no_zone", {zone: escHtml(displayName)}) + "</p>";
    return;
  }
  body.className = "panel-body";
  body.innerHTML = sortContextPillarsByDate(zonePillars).map(function(p) {
    return renderContextPillarHtml(p, {hideScopeTag: true});
  }).join("");
}

function showProvinceOutlines() {
  if (!map.hasLayer(provinceOutlineLayer)) {
    provinceOutlineLayer.addTo(map);
  }
  provinceOutlineLayer.bringToFront();
  applyProvinceOutlineStyles(null);
}

function hideProvinceOutlines() {
  if (map.hasLayer(provinceOutlineLayer)) {
    map.removeLayer(provinceOutlineLayer);
  }
  applyProvinceOutlineStyles(null);
}

// --- Map / Trends / Context tab switching ---
let savedMapLayerId = null;
let trendsDateIdx = 0;
let trendsSliderTimer = null;
let trendsSliderAnimating = false;
let trendsSliderPointerDown = false;
const TRENDS_SLIDER_STEP_MS = 150;

function setTrendsSliderBusy(busy) {
  document.body.classList.toggle("trends-slider-busy", !!busy);
}

function syncTrendsSliderBusy() {
  setTrendsSliderBusy(trendsSliderAnimating || trendsSliderPointerDown);
}

function stopTrendsSliderAnimation() {
  if (trendsSliderTimer != null) {
    clearInterval(trendsSliderTimer);
    trendsSliderTimer = null;
  }
  trendsSliderAnimating = false;
  syncTrendsSliderBusy();
  syncTrendsPlayButton();
}

function applyTrendsDateIdx(idx) {
  const ts = PAYLOAD.confirmed_timeseries;
  const slider = document.getElementById("trends-date-slider");
  if (!ts || !ts.dates || !ts.dates.length) return;
  trendsDateIdx = Math.max(0, Math.min(idx, ts.dates.length - 1));
  if (slider) slider.value = String(trendsDateIdx);
  updateTrendsDateLabel();
  recomputeTrendsMap();
}

function playTrendsSliderAnimation() {
  stopTrendsSliderAnimation();
  const ts = PAYLOAD.confirmed_timeseries;
  if (!ts || !ts.dates || ts.dates.length < 2) return;
  trendsSliderAnimating = true;
  syncTrendsSliderBusy();
  syncTrendsPlayButton();
  let idx = 0;
  applyTrendsDateIdx(0);
  trendsSliderTimer = setInterval(function() {
    if (activeView !== "trends") {
      stopTrendsSliderAnimation();
      return;
    }
    idx += 1;
    if (idx >= ts.dates.length) {
      applyTrendsDateIdx(ts.dates.length - 1);
      stopTrendsSliderAnimation();
      return;
    }
    applyTrendsDateIdx(idx);
  }, TRENDS_SLIDER_STEP_MS);
}

function getTrendsConfirmedAt(nom, dateIdx) {
  const ts = PAYLOAD.confirmed_timeseries;
  if (!ts || !ts.by_nom) return 0;
  const series = ts.by_nom[nom];
  if (!series || dateIdx < 0 || dateIdx >= series.length) return 0;
  return series[dateIdx];
}

function initTrendsLegendBar() {
  const ts = PAYLOAD.confirmed_timeseries;
  if (!ts) return;
  const layer = getLayer("obs::confirmed");
  const palette = PALETTES[(layer && layer.palette) || "reds"] || REDS;
  const bar = document.getElementById("trends-legend-bar");
  if (!bar) return;
  const stops = [];
  const N = 32;
  for (let i = 0; i < N; i++) {
    const t = i / (N - 1);
    stops.push(rgb(lerpColor(palette, t)) + " " + Math.round(t * 100) + "%");
  }
  bar.style.background = "linear-gradient(to right, " + stops.join(", ") + ")";
  const lo = ts.min_positive || 1;
  const hi = ts.max_confirmed || 1;
  const mid = Math.sqrt(lo * hi);
  const ticks = document.getElementById("trends-legend-ticks");
  if (ticks) {
    ticks.innerHTML =
      "<span>" + fmtLegend(lo, "int") + "</span>" +
      "<span>" + fmtLegend(mid, "int") + "</span>" +
      "<span>" + fmtLegend(hi, "int") + "</span>";
  }
  const scaleEl = document.getElementById("trends-legend-scale");
  if (scaleEl) scaleEl.textContent = t("ui.trends_scale_log");
}

function updateTrendsDateLabel() {
  const ts = PAYLOAD.confirmed_timeseries;
  const label = document.getElementById("trends-date-label");
  if (!label || !ts || !ts.dates || !ts.dates.length) return;
  const iso = ts.dates[trendsDateIdx];
  const raw = (ts.date_labels && ts.date_labels[iso]) || iso;
  label.textContent = t("ui.trends_as_of").replace("—", formatContextDate(raw));
}

function recomputeTrendsMap() {
  const ts = PAYLOAD.confirmed_timeseries;
  if (!ts || !ts.dates || !ts.dates.length) return;
  const layer = getLayer("obs::confirmed") || { palette: "reds" };
  currentValues.clear();
  for (const feat of PAYLOAD.geometry.features) {
    const ref = feat.properties.nom;
    currentValues.set(ref, getTrendsConfirmedAt(ref, trendsDateIdx));
  }
  const lo = ts.min_positive || 1;
  let hi = ts.max_confirmed || 1;
  if (hi <= lo) hi = lo + 1;
  currentDomain = {
    min: lo,
    max: hi,
    isLog: true,
    palette: PALETTES[layer.palette] || REDS,
  };
  geoLayer.setStyle(styleFn);
  if (activeView === "trends" && trendsScope === "health_zone" && trendsSelectedKey) {
    geoLayer.eachLayer(function(layer) {
      if (layer.feature && layer.feature.properties.nom === trendsSelectedKey) {
        layer.setStyle({weight: 2, color: "#ffae42"});
        layer.bringToFront();
      }
    });
  }
}

function restoreCaseMarkersForView(view) {
  if (view === "trends") {
    map.removeLayer(caseLayer);
    return;
  }
  if (view === "epi-trends") {
    const epiCases = document.getElementById("epi-show-cases");
    const on = epiCases ? epiCases.checked : (showCasesBox && showCasesBox.checked);
    if (on) caseLayer.addTo(map);
    else map.removeLayer(caseLayer);
    return;
  }
  if (showCasesBox.checked) caseLayer.addTo(map);
  else map.removeLayer(caseLayer);
}

function restoreFlowArcsForView(view) {
  if (view !== "map" && view !== "epi-trends") {
    clearFlowArcs();
    return;
  }
  if (flowArcsOverlayActive()) {
    renderFlowArcs(flowHubNom, flowArcLayerDef());
  } else {
    clearFlowArcs();
  }
}

function enterTrendsView() {
  savedMapLayerId = layerSelect.value;
  clearFlowArcs();
  layerSelect.value = "obs::confirmed";
  map.removeLayer(caseLayer);
  showProvinceOutlines();
  clearContextSelection();
  const ts = PAYLOAD.confirmed_timeseries;
  const legendPanel = document.getElementById("trends-legend");
  if (!ts || !ts.dates || !ts.dates.length) {
    if (legendPanel) legendPanel.style.display = "none";
    recompute();
  } else {
    if (legendPanel) legendPanel.style.display = "";
    initTrendsLegendBar();
    const slider = document.getElementById("trends-date-slider");
    if (slider) slider.max = String(ts.dates.length - 1);
    // Auto-play from the start every time the tab is opened, rather than
    // jumping straight to the latest sitrep and waiting for a manual Play click.
    playTrendsSliderAnimation();
  }
  const activeScopeBtn = document.querySelector(".trends-scope-btn.active");
  setTrendsScope((activeScopeBtn && activeScopeBtn.getAttribute("data-scope")) || "national");
  map.invalidateSize({animate: false});
}

function leaveTrendsView() {
  stopTrendsSliderAnimation();
  trendsSliderPointerDown = false;
  setTrendsSliderBusy(false);
  hideProvinceOutlines();
  trendsSelectedKey = null;
  renderTrendsPlots();
  if (savedMapLayerId) {
    layerSelect.value = savedMapLayerId;
    recompute();
  }
}

function setActiveView(view) {
  if (view === activeView) return;
  if (view === "trends") {
    enterTrendsView();
  } else if (view === "epi-trends") {
    if (activeView === "trends") leaveTrendsView();
    else {
      hideProvinceOutlines();
      clearContextSelection();
    }
    enterEpiTrendsView();
  } else if (view === "context") {
    clearFlowArcs();
    if (activeView === "trends") leaveTrendsView();
    else if (activeView === "epi-trends") leaveEpiTrendsView();
    else {
      hideProvinceOutlines();
      renderTrendsPanel(null);
    }
    clearContextSelection();
  } else {
    if (activeView === "trends") leaveTrendsView();
    else if (activeView === "epi-trends") leaveEpiTrendsView();
    else {
      hideProvinceOutlines();
      clearContextSelection();
    }
  }
  activeView = view;
  restoreCaseMarkersForView(view);
  restoreFlowArcsForView(view);
  document.body.classList.toggle("view-map", view === "map");
  document.body.classList.toggle("view-trends", view === "trends");
  document.body.classList.toggle("view-epi-trends", view === "epi-trends");
  document.body.classList.toggle("view-context", view === "context");
  syncMatrixUi();
  document.querySelectorAll(".view-tab").forEach(function(btn) {
    btn.classList.toggle("active", btn.dataset.view === view);
  });
  if (view === "epi-trends") {
    map.invalidateSize();
    recomputeEpiTrends();
  } else if (view === "trends") {
    map.invalidateSize();
  } else if (view === "map") {
    map.invalidateSize();
    recompute();
  }
}

// NOTE: view switching used to happen here via a click handler on
// ".view-tab" buttons that called setActiveView() without a page reload.
// Now that each view is a separate page, ".view-tab" elements are real
// <a href="..."> links (see common/chrome.py) and navigation is handled by
// the browser. setActiveView() is instead invoked once on load, below, to
// initialise whichever view this page represents (see "page bootstrap").

(function wireTrendsDateSlider() {
  const slider = document.getElementById("trends-date-slider");
  if (!slider) return;
  function onUserSliderChange() {
    if (activeView !== "trends") return;
    stopTrendsSliderAnimation();
    applyTrendsDateIdx(parseInt(slider.value, 10) || 0);
  }
  function onSliderPointerDown() {
    trendsSliderPointerDown = true;
    syncTrendsSliderBusy();
    stopTrendsSliderAnimation();
  }
  function onSliderPointerUp() {
    trendsSliderPointerDown = false;
    syncTrendsSliderBusy();
  }
  slider.addEventListener("input", onUserSliderChange);
  slider.addEventListener("pointerdown", onSliderPointerDown);
  slider.addEventListener("pointerup", onSliderPointerUp);
  slider.addEventListener("pointercancel", onSliderPointerUp);
  const playBtn = document.getElementById("trends-play-btn");
  if (playBtn) {
    playBtn.addEventListener("click", function() {
      if (activeView !== "trends") return;
      if (trendsSliderAnimating) stopTrendsSliderAnimation();
      else playTrendsSliderAnimation();
    });
  }
  syncTrendsPlayButton();
})();

(function wireTrendsPanelUi() {
  const scopeButtons = document.querySelectorAll(".trends-scope-btn");
  const searchInput = document.getElementById("trends-search-input");
  const searchResults = document.getElementById("trends-search-results");

  scopeButtons.forEach(function(btn) {
    btn.addEventListener("click", function() {
      const scope = btn.getAttribute("data-scope") || "national";
      scopeButtons.forEach(function(b) { b.classList.toggle("active", b === btn); });
      setTrendsScope(scope);
      if (searchInput) searchInput.value = "";
      if (searchResults) {
        searchResults.classList.remove("open");
        searchResults.innerHTML = "";
      }
    });
  });
  if (searchInput) {
    searchInput.addEventListener("input", function() {
      renderTrendsSearchResults(searchInput.value);
    });
    searchInput.addEventListener("focus", function() {
      renderTrendsSearchResults(searchInput.value);
    });
  }
  if (searchResults) {
    searchResults.addEventListener("click", function(e) {
      const btn = e.target.closest("button[data-id]");
      if (!btn) return;
      const kind = btn.getAttribute("data-kind");
      if (kind && kind !== trendsScope) {
        const targetBtn = document.querySelector(".trends-scope-btn[data-scope='" + kind + "']");
        if (targetBtn) {
          scopeButtons.forEach(function(b) { b.classList.toggle("active", b === targetBtn); });
        }
        setTrendsScope(kind);
      }
      setTrendsSelection(btn.getAttribute("data-id"), {fromSearch: true});
    });
  }
  document.addEventListener("click", function(e) {
    if (!searchResults || !searchResults.classList.contains("open")) return;
    if (e.target.closest("#trends-search-wrap")) return;
    searchResults.classList.remove("open");
  });
  setTrendsScope("national");
})();

// --- Trends tab: on narrow screens, relocate the location search bar out of
// #trends-controls (now buried in the stacked bottom panel, see
// body.view-trends #trends-panel in dashboard.css) into #trends-search-slot,
// a sibling of #map, positioned top-left where the Leaflet zoom control used
// to sit on this page (see body.view-trends .leaflet-control-zoom). Moves it
// back to its original spot -- right after .trends-scope-row inside
// #trends-controls -- on wider screens. ---
(function wireTrendsSearchSlot() {
  const searchWrap = document.getElementById("trends-search-wrap");
  const slot = document.getElementById("trends-search-slot");
  const controls = document.getElementById("trends-controls");
  if (!searchWrap || !slot || !controls) return;
  const scopeRow = controls.querySelector(".trends-scope-row");
  const mq = window.matchMedia("(max-width: 700px)");

  function place(narrow) {
    if (narrow) {
      if (searchWrap.parentElement !== slot) slot.appendChild(searchWrap);
    } else if (searchWrap.parentElement !== controls) {
      if (scopeRow && scopeRow.nextSibling) {
        controls.insertBefore(searchWrap, scopeRow.nextSibling);
      } else {
        controls.appendChild(searchWrap);
      }
    }
  }

  place(mq.matches);
  if (mq.addEventListener) {
    mq.addEventListener("change", function(e) { place(e.matches); });
  } else if (mq.addListener) {
    mq.addListener(function(e) { place(e.matches); });
  }
})();

// --- Trends tab map/plots split handle (mirrors wireEpiTrendsUi's
// #epi-split-handle drag logic, with its own CSS var + storage key so the
// Trends and Spatial Risk tabs remember independent split positions). ---
(function wireTrendsSplitUi() {
  const splitHandle = document.getElementById("trends-split-handle");
  const TRENDS_SPLIT_MIN = 28;
  const TRENDS_SPLIT_MAX = 72;
  const TRENDS_SPLIT_KEY = "bdbv_trends_panel_width_pct";

  function clampTrendsSplitPct(pct) {
    return Math.max(TRENDS_SPLIT_MIN, Math.min(TRENDS_SPLIT_MAX, pct));
  }

  function applyTrendsSplitPct(pct, invalidate) {
    const value = clampTrendsSplitPct(pct);
    document.documentElement.style.setProperty("--trends-panel-width", value + "%");
    if (splitHandle) splitHandle.setAttribute("aria-valuenow", String(Math.round(value)));
    try { localStorage.setItem(TRENDS_SPLIT_KEY, String(value)); } catch (e) {}
    if (invalidate && activeView === "trends") {
      map.invalidateSize({animate: false});
    }
    return value;
  }

  function readStoredTrendsSplit() {
    try {
      const raw = localStorage.getItem(TRENDS_SPLIT_KEY);
      if (raw == null || raw === "") return 40;
      const n = Number(raw);
      return Number.isFinite(n) ? n : 40;
    } catch (e) {
      return 40;
    }
  }

  applyTrendsSplitPct(readStoredTrendsSplit(), false);
  if (!splitHandle) return;
  splitHandle.setAttribute("aria-valuemin", String(TRENDS_SPLIT_MIN));
  splitHandle.setAttribute("aria-valuemax", String(TRENDS_SPLIT_MAX));
  let dragging = false;
  function splitFromClientX(clientX) {
    const w = window.innerWidth || document.documentElement.clientWidth || 1;
    // Panel is on the right: width% = distance from right edge.
    return clampTrendsSplitPct(((w - clientX) / w) * 100);
  }
  function onPointerMove(e) {
    if (!dragging) return;
    if (e.cancelable) e.preventDefault();
    const x = e.touches && e.touches[0] ? e.touches[0].clientX : e.clientX;
    applyTrendsSplitPct(splitFromClientX(x), false);
  }
  function onPointerUp() {
    if (!dragging) return;
    dragging = false;
    document.body.classList.remove("trends-splitting");
    window.removeEventListener("mousemove", onPointerMove);
    window.removeEventListener("mouseup", onPointerUp);
    window.removeEventListener("touchmove", onPointerMove);
    window.removeEventListener("touchend", onPointerUp);
    window.removeEventListener("touchcancel", onPointerUp);
    if (activeView === "trends") map.invalidateSize({animate: false});
  }
  function onPointerDown(e) {
    if (activeView !== "trends") return;
    dragging = true;
    document.body.classList.add("trends-splitting");
    const x = e.touches && e.touches[0] ? e.touches[0].clientX : e.clientX;
    applyTrendsSplitPct(splitFromClientX(x), false);
    window.addEventListener("mousemove", onPointerMove);
    window.addEventListener("mouseup", onPointerUp);
    window.addEventListener("touchmove", onPointerMove, {passive: false});
    window.addEventListener("touchend", onPointerUp);
    window.addEventListener("touchcancel", onPointerUp);
    if (e.cancelable) e.preventDefault();
  }
  splitHandle.addEventListener("mousedown", onPointerDown);
  splitHandle.addEventListener("touchstart", onPointerDown, {passive: false});
  splitHandle.addEventListener("keydown", function(e) {
    if (activeView !== "trends") return;
    let delta = 0;
    if (e.key === "ArrowLeft") delta = 2;
    else if (e.key === "ArrowRight") delta = -2;
    else if (e.key === "Home") {
      applyTrendsSplitPct(40, true);
      e.preventDefault();
      return;
    } else return;
    const cur = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--trends-panel-width")
    ) || 40;
    applyTrendsSplitPct(cur + delta, true);
    e.preventDefault();
  });
})();

// --- active-case markers ---
const ACTIVE_CASES = PAYLOAD.active_case_markers || [];
const GENOME_SEQUENCES = PAYLOAD.genome_sequence_markers || [];
const GENOME_MAX_COUNT = GENOME_SEQUENCES.reduce(function(max, g) {
  return Math.max(max, g.count || 0);
}, 1);
const caseIcon = L.divIcon({className:"", html:"<div class='case-icon'></div>", iconSize:[14,14]});
const caseLayer = L.layerGroup();
const genomeLayer = L.layerGroup();
const showCasesBox = document.getElementById("show-cases");
const showGenomesBox = document.getElementById("show-genomes");
const showGenomesRow = document.getElementById("show-genomes-row");

function genomeIcon(count) {
  const minD = 10;
  const maxD = 38;
  const t = GENOME_MAX_COUNT > 1 ? (count - 1) / (GENOME_MAX_COUNT - 1) : 1;
  const d = Math.round(minD + t * (maxD - minD));
  return L.divIcon({
    className: "",
    html: "<div class='genome-icon' style='width:" + d + "px;height:" + d + "px;'></div>",
    iconSize: [d, d],
    iconAnchor: [d / 2, d / 2],
  });
}

function syncMarkerToggles(from) {
  if (from === "cases" && showCasesBox.checked) {
    showGenomesBox.checked = false;
    map.removeLayer(genomeLayer);
    caseLayer.addTo(map);
    return;
  }
  if (from === "genomes" && showGenomesBox.checked) {
    showCasesBox.checked = false;
    map.removeLayer(caseLayer);
    genomeLayer.addTo(map);
    return;
  }
  if (from === "cases") map.removeLayer(caseLayer);
  if (from === "genomes") map.removeLayer(genomeLayer);
}

function caseMarkerTooltip(c) {
  const totalDeaths = (c.confirmed_deaths || 0) + (c.suspected_deaths || 0);
  return (
    "<strong>" + (c.name || t("ui.case_tooltip.unnamed")) + "</strong><br/>" +
    t("ui.case_tooltip.confirmed") + ": " + c.confirmed + "  ·  " +
    t("ui.case_tooltip.suspected") + ": " + c.suspected +
    (totalDeaths > 0 ? "<br/>" + t("ui.case_tooltip.deaths") + ": " + totalDeaths : "")
  );
}

function genomeMarkerTooltip(g) {
  return (
    "<strong>" + (g.name || t("ui.case_tooltip.unnamed")) + "</strong><br/>" +
    t("ui.genome_tooltip").replace("{n}", g.count)
  );
}

function refreshMarkerTooltips() {
  caseLayer.eachLayer(function(m) {
    if (m._bdbvCase) m.setTooltipContent(caseMarkerTooltip(m._bdbvCase));
  });
  genomeLayer.eachLayer(function(m) {
    if (m._bdbvGenome) m.setTooltipContent(genomeMarkerTooltip(m._bdbvGenome));
  });
}

// A case marker sits in the marker pane above its zone polygon and (unlike a
// path) does not bubble clicks, so without this it would swallow the click and
// leave the zone unselectable via its own case dot. One marker == one zone
// (c.nom), so route the click to the same select/toggle logic as clicking the
// polygon in whichever view is active. Returns true if it handled the click.
function handleCaseMarkerClick(nom) {
  if (!nom) return false;
  if (activeView === "epi-trends") {
    setEpiSelected(nom === epiSelectedNom ? null : nom);
    return true;
  }
  if (activeView === "context") {
    if (nom === contextSelectedNom) clearContextSelection();
    else {
      const lyr = findGeoLayerByNom(nom);
      if (lyr) selectContextZone(nom, lyr);
    }
    return true;
  }
  if (activeView === "map") {
    if (flowArcsOverlayActive()) {
      setFlowHub(nom === flowHubNom ? null : nom);
      return true;
    }
    // Matrix layers need an origin, so no toggle-to-null here.
    if (layerUsesMatrix(getLayer(layerSelect.value))) {
      setMatrixOrigin(nom);
      return true;
    }
  }
  return false;
}

for (const c of ACTIVE_CASES) {
  if (!isFinite(c.lat) || !isFinite(c.lon)) continue;
  const m = L.marker([c.lat, c.lon], {icon: caseIcon});
  m._bdbvCase = c;
  m.bindTooltip(caseMarkerTooltip(c), {direction:"top", offset:[0,-8]});
  m.on("click", function(e) {
    if (handleCaseMarkerClick(c.nom)) L.DomEvent.stop(e);
  });
  caseLayer.addLayer(m);
}

for (const g of GENOME_SEQUENCES) {
  if (!isFinite(g.lat) || !isFinite(g.lon)) continue;
  const m = L.marker([g.lat, g.lon], {icon: genomeIcon(g.count)});
  m._bdbvGenome = g;
  m.bindTooltip(genomeMarkerTooltip(g), {direction:"top", offset:[0,-8]});
  genomeLayer.addLayer(m);
}

if (!PAYLOAD.genome_markers_available || !GENOME_SEQUENCES.length) {
  if (showGenomesRow) showGenomesRow.style.display = "none";
} else if (showGenomesBox) {
  showGenomesBox.addEventListener("change", function() {
    syncMarkerToggles("genomes");
  });
}

showCasesBox.addEventListener("change", function() {
  const epiCases = document.getElementById("epi-show-cases");
  if (epiCases) epiCases.checked = showCasesBox.checked;
  syncMarkerToggles("cases");
  if (activeView === "epi-trends") restoreCaseMarkersForView("epi-trends");
});

// --- Flowminder in/out flow arcs (toggle overlay) ---
const showFlowArcsBox = document.getElementById("show-flow-arcs");
const showFlowArcsRow = document.getElementById("show-flow-arcs-row");
let flowArcsUserPref = true;
if (!PAYLOAD.flow_arcs_available || !FLOW_ARC_LAYER) {
  if (showFlowArcsRow) showFlowArcsRow.style.display = "none";
  flowArcsUserPref = false;
} else if (showFlowArcsBox) {
  if (showFlowArcsRow) showFlowArcsRow.style.display = "";
  showFlowArcsBox.checked = true;
  flowArcsUserPref = true;
  showFlowArcsBox.addEventListener("change", function() {
    flowArcsUserPref = !!showFlowArcsBox.checked;
    recompute();
    syncMatrixUi();
  });
}

// --- Epidemiological trends controls ---
(function wireEpiTrendsUi() {
  const tbody = document.getElementById("epi-trends-tbody");
  const tab = document.querySelector('.view-tab[data-view="epi-trends"]');
  const splitHandle = document.getElementById("epi-split-handle");
  const EPI_SPLIT_MIN = 28;
  const EPI_SPLIT_MAX = 72;
  const EPI_SPLIT_KEY = "bdbv_epi_panel_width_pct";

  function clampEpiSplitPct(pct) {
    return Math.max(EPI_SPLIT_MIN, Math.min(EPI_SPLIT_MAX, pct));
  }

  function applyEpiSplitPct(pct, invalidate) {
    const value = clampEpiSplitPct(pct);
    document.documentElement.style.setProperty("--epi-panel-width", value + "%");
    if (splitHandle) splitHandle.setAttribute("aria-valuenow", String(Math.round(value)));
    try { localStorage.setItem(EPI_SPLIT_KEY, String(value)); } catch (e) {}
    if (invalidate && activeView === "epi-trends") {
      map.invalidateSize({animate: false});
    }
    return value;
  }

  function readStoredEpiSplit() {
    try {
      const raw = localStorage.getItem(EPI_SPLIT_KEY);
      if (raw == null || raw === "") return 50;
      const n = Number(raw);
      return Number.isFinite(n) ? n : 50;
    } catch (e) {
      return 50;
    }
  }

  applyEpiSplitPct(readStoredEpiSplit(), false);
  if (splitHandle) {
    splitHandle.setAttribute("aria-valuemin", String(EPI_SPLIT_MIN));
    splitHandle.setAttribute("aria-valuemax", String(EPI_SPLIT_MAX));
    let dragging = false;
    function splitFromClientX(clientX) {
      const w = window.innerWidth || document.documentElement.clientWidth || 1;
      // Panel is on the right: width% = distance from right edge.
      return clampEpiSplitPct(((w - clientX) / w) * 100);
    }
    function onPointerMove(e) {
      if (!dragging) return;
      if (e.cancelable) e.preventDefault();
      const x = e.touches && e.touches[0] ? e.touches[0].clientX : e.clientX;
      applyEpiSplitPct(splitFromClientX(x), false);
    }
    function onPointerUp() {
      if (!dragging) return;
      dragging = false;
      document.body.classList.remove("epi-splitting");
      window.removeEventListener("mousemove", onPointerMove);
      window.removeEventListener("mouseup", onPointerUp);
      window.removeEventListener("touchmove", onPointerMove);
      window.removeEventListener("touchend", onPointerUp);
      window.removeEventListener("touchcancel", onPointerUp);
      if (activeView === "epi-trends") map.invalidateSize({animate: false});
    }
    function onPointerDown(e) {
      if (activeView !== "epi-trends") return;
      dragging = true;
      document.body.classList.add("epi-splitting");
      const x = e.touches && e.touches[0] ? e.touches[0].clientX : e.clientX;
      applyEpiSplitPct(splitFromClientX(x), false);
      window.addEventListener("mousemove", onPointerMove);
      window.addEventListener("mouseup", onPointerUp);
      window.addEventListener("touchmove", onPointerMove, {passive: false});
      window.addEventListener("touchend", onPointerUp);
      window.addEventListener("touchcancel", onPointerUp);
      if (e.cancelable) e.preventDefault();
    }
    splitHandle.addEventListener("mousedown", onPointerDown);
    splitHandle.addEventListener("touchstart", onPointerDown, {passive: false});
    splitHandle.addEventListener("keydown", function(e) {
      if (activeView !== "epi-trends") return;
      let delta = 0;
      if (e.key === "ArrowLeft") delta = 2;
      else if (e.key === "ArrowRight") delta = -2;
      else if (e.key === "Home") {
        applyEpiSplitPct(50, true);
        e.preventDefault();
        return;
      } else return;
      const cur = parseFloat(
        getComputedStyle(document.documentElement).getPropertyValue("--epi-panel-width")
      ) || 50;
      applyEpiSplitPct(cur + delta, true);
      e.preventDefault();
    });
  }

  if (!INVASION_RISK || !Object.keys(INVASION_ZONES).length) {
    if (tab) tab.style.display = "none";
    if (splitHandle) splitHandle.style.display = "none";
    return;
  }
  const epiSearchInput = document.getElementById("epi-search-input");
  const epiSearchResults = document.getElementById("epi-search-results");

  function epiClearSearchUi() {
    if (epiSearchInput) epiSearchInput.value = "";
    if (epiSearchResults) {
      epiSearchResults.classList.remove("open");
      epiSearchResults.innerHTML = "";
    }
  }

  // Picking a health zone from search selects/highlights its row (a ranked
  // list of one zone isn't useful, so it doesn't filter the table), same as
  // clicking that row directly. setEpiSelected() re-renders the table, so the
  // scroll-into-view happens after it.
  function epiApplyHealthZone(nom) {
    setEpiSelected(nom);
    if (tbody) {
      const tr = Array.prototype.find.call(
        tbody.querySelectorAll("tr[data-nom]"),
        function(el) { return el.getAttribute("data-nom") === nom; }
      );
      if (tr && tr.scrollIntoView) tr.scrollIntoView({block: "center"});
    }
  }

  // Shares TRENDS_LOCATION_INDEX with the Trends tab (every province + health
  // zone), but this page has no provincial scope, so province entries are
  // filtered out -- only health zones are shown/selectable here.
  function renderEpiSearchResults(query) {
    if (!epiSearchResults) return;
    const q = String(query || "").trim().toLowerCase();
    if (!q) {
      epiSearchResults.classList.remove("open");
      epiSearchResults.innerHTML = "";
      return;
    }
    const items = TRENDS_LOCATION_INDEX.filter(function(it) {
      return it.kind === "health_zone" && it.haystack.indexOf(q) >= 0;
    });
    if (!items.length) {
      epiSearchResults.innerHTML = "<div class='zone-search-empty'>" +
        escHtml(t("ui.zone_search_no_matches") || "No matches") + "</div>";
      epiSearchResults.classList.add("open");
      return;
    }
    epiSearchResults.innerHTML = items.slice(0, 40).map(function(it) {
      return "<button type='button' role='option' data-id='" + escHtml(it.id) + "' data-kind='" + escHtml(it.kind) + "'>" +
        escHtml(it.label) + "</button>";
    }).join("");
    epiSearchResults.classList.add("open");
  }

  if (epiSearchInput) {
    epiSearchInput.addEventListener("input", function() { renderEpiSearchResults(epiSearchInput.value); });
    epiSearchInput.addEventListener("focus", function() { renderEpiSearchResults(epiSearchInput.value); });
  }
  if (epiSearchResults) {
    epiSearchResults.addEventListener("click", function(e) {
      const btn = e.target.closest("button[data-id]");
      if (!btn) return;
      const kind = btn.getAttribute("data-kind");
      const id = btn.getAttribute("data-id");
      if (kind === "health_zone") epiApplyHealthZone(id);
      epiClearSearchUi();
    });
  }
  document.addEventListener("click", function(e) {
    if (!epiSearchResults || !epiSearchResults.classList.contains("open")) return;
    if (e.target.closest("#epi-search-wrap")) return;
    epiSearchResults.classList.remove("open");
  });

  // Sortable column headers replace the old rank-by-RR/rank-by-priority
  // buttons -- click (or Enter/Space) any header to sort by it, click again
  // to reverse. See epiSortValue()/epiCompareValues()/epiSortedRows() and
  // updateEpiSortIndicators() for the ▲/▼ glyph.
  document.querySelectorAll("#epi-trends-table th[data-sort]").forEach(function(th) {
    function activateSort() {
      const key = th.getAttribute("data-sort");
      if (epiSortKey === key) {
        epiSortDir = epiSortDir === "asc" ? "desc" : "asc";
      } else {
        epiSortKey = key;
        epiSortDir = "asc";
      }
      updateEpiSortIndicators();
      renderEpiTrendsTable();
    }
    th.addEventListener("click", activateSort);
    th.addEventListener("keydown", function(e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      activateSort();
    });
  });
  updateEpiSortIndicators();
  if (tbody) {
    tbody.addEventListener("click", function(e) {
      const tr = e.target.closest("tr[data-nom]");
      if (!tr) return;
      setEpiSelected(tr.getAttribute("data-nom"));
    });
  }
  const epiCases = document.getElementById("epi-show-cases");
  if (epiCases) {
    epiCases.checked = !!(showCasesBox && showCasesBox.checked);
    epiCases.addEventListener("change", function() {
      if (showCasesBox) showCasesBox.checked = epiCases.checked;
      if (activeView === "epi-trends") restoreCaseMarkersForView("epi-trends");
      else syncMarkerToggles("cases");
    });
  }

  function triggerDownload(filename, href) {
    const a = document.createElement("a");
    a.href = href;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  const csvBtn = document.getElementById("epi-download-csv");
  if (csvBtn) {
    csvBtn.addEventListener("click", function() {
      const csv = (INVASION_RISK && INVASION_RISK.download_csv) || "";
      if (!csv) return;
      const blob = new Blob([csv], {type: "text/csv;charset=utf-8"});
      const url = URL.createObjectURL(blob);
      const stamp = (INVASION_RISK.cutoff_date || "data").replace(/-/g, "");
      triggerDownload("invasion_risk_model_estimates_" + stamp + ".csv", url);
      setTimeout(function() { URL.revokeObjectURL(url); }, 1500);
    });
  }

  const mapBtn = document.getElementById("epi-download-map");
  if (mapBtn) {
    mapBtn.addEventListener("click", function() {
      if (typeof html2canvas !== "function") {
        window.alert(t("ui.epi_download_map_unavailable"));
        return;
      }
      const hadCases = map.hasLayer(caseLayer);
      const hadSelection = epiSelectedNom;
      const prevCenter = map.getCenter();
      const prevZoom = map.getZoom();
      clearEpiLinks();
      clearFlowArcs();
      if (hadSelection) setEpiSelected(null);
      if (hadCases) map.removeLayer(caseLayer);
      hideEpiFloat();
      document.body.classList.add("epi-map-exporting");
      map.invalidateSize({animate: false});
      try {
        map.fitBounds(geoLayer.getBounds(), {
          padding: [28, 28],
          animate: false,
          maxZoom: 7,
        });
      } catch (err) {
        map.setView([-2.5, 23.5], 5, {animate: false});
      }
      setTimeout(function() {
        html2canvas(map.getContainer(), {
          useCORS: true,
          allowTaint: true,
          backgroundColor: "#ffffff",
          scale: 2,
        }).then(function(canvas) {
          const jpg = canvas.toDataURL("image/jpeg", 0.92);
          const stamp = (INVASION_RISK && INVASION_RISK.cutoff_date || "map").replace(/-/g, "");
          triggerDownload("invasion_risk_map_" + stamp + ".jpg", jpg);
        }).catch(function(err) {
          console.error(err);
          window.alert(t("ui.epi_download_map_unavailable"));
        }).finally(function() {
          document.body.classList.remove("epi-map-exporting");
          map.invalidateSize({animate: false});
          map.setView(prevCenter, prevZoom, {animate: false});
          if (hadCases && (
            (document.getElementById("epi-show-cases") || {}).checked ||
            (showCasesBox && showCasesBox.checked)
          )) {
            caseLayer.addTo(map);
          }
          if (hadSelection) setEpiSelected(hadSelection);
        });
      }, 180);
    });
  }
})();

// Default: total cases layer, active-case markers ON, flow arcs ON from Mongbwalu.
showCasesBox.checked = true;
caseLayer.addTo(map);

layerSelect.addEventListener("change", function() {
  // OSRM layers (travel time / road distance) render from the origin zone's
  // matrix row, which visually competes with the Flowminder in/out-flow arcs
  // radiating from the same origin — turn the arcs off automatically, then
  // restore the user's Flowminder preference when leaving those layers.
  if (showFlowArcsBox && PAYLOAD.flow_arcs_available && FLOW_ARC_LAYER) {
    if (layerUsesMatrix(getLayer(layerSelect.value))) {
      showFlowArcsBox.checked = false;
    } else if (flowArcsUserPref) {
      showFlowArcsBox.checked = true;
    }
  }
  recompute();
  syncMatrixUi();
});

// --- modal wiring (Methods + Terms) ---
// btnIds may be a single id or an array -- the header-info-popup's
// methods/terms buttons (narrow screens) open the same modals as the
// footer's Contributors/Methods and Terms buttons (wide screens).
function wireModal(modalId, btnIds, closeId) {
  const modal = document.getElementById(modalId);
  const closeBtn = document.getElementById(closeId);
  if (!modal) return;
  function open() {
    document.querySelectorAll(".modal.open").forEach(m => m.classList.remove("open"));
    modal.classList.add("open");
  }
  function close() { modal.classList.remove("open"); }
  (Array.isArray(btnIds) ? btnIds : [btnIds]).forEach(function(id) {
    const btn = document.getElementById(id);
    if (btn) btn.addEventListener("click", open);
  });
  if (closeBtn) closeBtn.addEventListener("click", close);
  modal.addEventListener("click", function(e) {
    if (e.target === modal) close();
  });
}
document.addEventListener("keydown", function(e) {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal.open").forEach(m => m.classList.remove("open"));
  }
});
wireModal("methods-modal", ["methods-btn", "header-methods-btn"], "methods-close");
wireModal("terms-modal", ["terms-btn", "header-terms-btn"], "terms-close");

// --- collapsible panels (zone info + layer controls + legend) ---
(function wirePanelToggles() {
  function setCollapsed(panel, btn, collapsed) {
    if (collapsed) {
      panel.classList.add("collapsed");
      btn.textContent = "+";
    } else {
      panel.classList.remove("collapsed");
      btn.textContent = "−";
    }
  }
  const infoPanel = document.getElementById("info");
  const infoBtn = document.getElementById("info-toggle");
  if (infoPanel && infoBtn) {
    infoBtn.addEventListener("click", function() {
      setCollapsed(infoPanel, infoBtn, !infoPanel.classList.contains("collapsed"));
    });
  }
  document.querySelectorAll(".panel-toggle").forEach(function(btn) {
    const panel = document.getElementById(btn.dataset.target);
    if (!panel) return;
    btn.addEventListener("click", function() {
      setCollapsed(panel, btn, !panel.classList.contains("collapsed"));
    });
  });
  if (window.matchMedia && window.matchMedia("(max-width: 700px)").matches) {
    if (infoPanel && infoBtn) setCollapsed(infoPanel, infoBtn, true);
    document.querySelectorAll(".panel-toggle").forEach(function(btn) {
      const panel = document.getElementById(btn.dataset.target);
      if (panel) setCollapsed(panel, btn, true);
    });
  }
})();

// Pre-populate the zone info panel with Mongbwalu.
(function preloadMongbwalu() {
  for (const feat of PAYLOAD.geometry.features) {
    if ((feat.properties.nom || "").toLowerCase() === "mongbalu") {
      document.getElementById("info-body").className = "";
      document.getElementById("info-body").innerHTML = infoHTML(feat);
      return;
    }
  }
})();

(function initDashboardI18n() {
  LAYERS = (I18N.layers && I18N.layers[currentLang]) || PAYLOAD.layers;
  applyStaticI18n();
  rebuildLayerSelect();
  buildTitleSub();
  buildTracker();
  buildModeledEstimateNote();
  updateLegalContent();
  layerSelect.value = "obs::total";
  applyMatrixOriginToLayers();
  rebuildLayerSelect();
  recompute();
  syncMatrixUi();
})();

// --- deep-linking via URL params, e.g. ?genomes=1 or ?cases=1 ---
// Runs last so it overrides the defaults set above (cases ON, flow arcs ON).
(function applyMarkerUrlParams() {
  const params = new URLSearchParams(window.location.search);
  function isTruthy(v) {
    return v !== null && !["0", "false", "no"].includes(v.toLowerCase());
  }
  const genomesParam = params.get("genomes");
  const genomesRequested =
    isTruthy(genomesParam) &&
    PAYLOAD.genome_markers_available &&
    GENOME_SEQUENCES.length &&
    showGenomesBox;
  if (genomesRequested) {
    showGenomesBox.checked = true;
    syncMarkerToggles("genomes"); // also unticks + removes the case-marker layer
    if (showFlowArcsBox) {
      showFlowArcsBox.checked = false;
      flowArcsUserPref = false;
    }
    recompute();
    syncMatrixUi();
    return;
  }
  const casesParam = params.get("cases");
  if (isTruthy(casesParam) && showCasesBox) {
    showCasesBox.checked = true;
    syncMarkerToggles("cases");
  }
})();

// --- page bootstrap (multi-page split) ---
// Each page's <body data-initial-view="..."> tells the shared engine which
// of the four views this page represents. The engine's default in-memory
// state (activeView = "map", body class "view-map") matches the snapshot
// page, so no extra work is needed there; every other page runs the same
// enter/leave transition logic that used to fire on tab click.
(function bootstrapInitialView() {
  const initialView = document.body.dataset.initialView || "map";
  if (initialView !== "map") {
    setActiveView(initialView);
  }
})();
