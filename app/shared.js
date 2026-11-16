
const EXTRA_TITLES = { yellow: "Yellow River, FL", village_creek: "Village Creek, TX", pine_island: "Pine Island Bayou, TX", pee_dee: "Pee Dee River, SC", neuse: "Neuse River, NC", lower_sabine: "Lower Sabine River, TX/LA",
  satilla: "Satilla River, GA", alapaha: "Alapaha River, GA/FL", ochlockonee: "Ochlockonee River, GA/FL", withlacoochee: "Withlacoochee River, GA/FL", st_marys: "St Marys River, GA/FL", pearl: "Pearl River, LA/MS", tangipahoa: "Tangipahoa River, LA", choctawhatchee: "Choctawhatchee River, FL" };
const JUDGE_HA = 500;
const CHART = { nisar: "#d63ad6", estimate: "#00c8dc", lidar: "#bd8512", series: ["#1dbad0", "#bd8512", "#a86be8", "#4aa85e"], ink: "#cfdbe2", grid: "#2a3740" };
const CHART_FONT = { color: CHART.ink, family: '"IBM Plex Sans", system-ui, sans-serif', size: 12 };
const CHART_LEGEND = { orientation: "h", x: 0, y: 1.02, yanchor: "bottom" };

const $ = (id) => document.getElementById(id);
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

const PALETTE = (() => {
  const cs = getComputedStyle(document.documentElement), v = (name, fallback) => cs.getPropertyValue(name).trim() || fallback;
  return {
    water: v("--water", "#00c8dc"), waterInk: v("--water-ink", "#6fe3ef"), forest: v("--forest", "#4fdcb0"), forestInk: v("--forest-ink", "#8debcd"),
    nisar: v("--nisar", "#d63ad6"), nisarInk: v("--nisar-ink", "#e57ae5"), official: v("--official", "#286eff"), officialInk: v("--official-ink", "#8fb4ff"),
    veil: v("--veil", "#8a969e"), veilInk: v("--veil-ink", "#b9c4cb"), people: v("--people", "#ffb45a"), peopleInk: v("--people-ink", "#ffc98a"), action: v("--action", "#ffd166"),
  };
})();

function basemap() {
  const night = document.body.classList.contains("night");
  return {
    version: 8,
    sources: { img: { type: "raster", tileSize: 256, maxzoom: 17, tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"], attribution: "Imagery © Esri" } },
    layers: [{ id: "img", type: "raster", source: "img", paint: night ? { "raster-saturation": -0.5, "raster-brightness-max": 0.62, "raster-contrast": 0.06 } : { "raster-saturation": -0.35, "raster-brightness-max": 0.72 } }],
  };
}
const BASEMAP = basemap();

const SUPERSCRIPT = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
const pow10 = (metres) => `10${String(Math.round(Math.log10(metres))).split("").map((c) => SUPERSCRIPT[c]).join("")} m`;
const boundsWidthKm = (b) => { const [w, s, e, n] = Array.isArray(b[0]) ? [b[0][0], b[0][1], b[1][0], b[1][1]] : b; return Math.abs(e - w) * 111.32 * Math.cos(((s + n) / 2) * Math.PI / 180); };
const kmText = (x) => (x >= 100 ? `${Math.round(x).toLocaleString("en-US")} km` : x >= 10 ? `${Math.round(x)} km` : `${x.toFixed(1)} km`);

function countUp(el, to, fmt = (x) => String(Math.round(x)), ms = 1100) {
  if (!el) return;
  if (reducedMotion()) { el.textContent = fmt(to); return; }
  const t0 = performance.now();
  const step = (t) => { const f = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - f, 3); el.textContent = fmt(to * e); if (f < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
function countWhenSeen(el, to, fmt = (x) => String(Math.round(x)), ms = 1100) {
  if (!el) return;
  if (reducedMotion() || !("IntersectionObserver" in window)) { el.textContent = fmt(to); return; }
  el.textContent = fmt(0);
  const seen = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { seen.disconnect(); countUp(el, to, fmt, ms); } }, { threshold: 0.4 });
  seen.observe(el);
}

function visibleLoop(el, frame) {
  let on = false, raf = 0, last = 0;
  const tick = (t) => {
    if (!on || document.hidden) { raf = 0; return; }
    const dt = last ? Math.min(64, t - last) : 0;
    last = t;
    if (frame(dt, t) === false) { raf = 0; return; }
    raf = requestAnimationFrame(tick);
  };
  const kick = () => { if (!raf && on && !document.hidden) { last = 0; raf = requestAnimationFrame(tick); } };
  if ("IntersectionObserver" in window) new IntersectionObserver((es) => { on = es.some((e) => e.isIntersecting); kick(); }).observe(el);
  else on = true;
  document.addEventListener("visibilitychange", kick);
  return { kick };
}

function floodPicker(cases, sub, scores = null) {
  const e = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const score = (c) => (scores && Number.isFinite(scores[c.id]) ? scores[c.id] : null);
  const graded = (c) => (c.nisarOnly ? "NISAR map only" : c.kind === "us" ? (c.scored ? '<span class="dep-us">checked against its gauges</span>' : "gauges, not scored") : "map only, no gauges");
  return [...cases].sort((a, b) => (score(b) ?? -1) - (score(a) ?? -1) || Date.parse(b.wet) - Date.parse(a.wet)).map((c) =>
    `<li><button type="button" class="live-row pick-row" data-case="${e(c.id)}" aria-pressed="false" title="NISAR pass ${e(fmtTime(c.wet))}">` +
    `<span class="pick-place">${e(c.place)}</span><span class="pick-when">${fmtDay(c.wet)}</span>` +
    `<span class="pick-sub">${sub(c)} · ${graded(c)}</span></button></li>`).join("");
}

const notOffered = (c) => (c.pass_stage && c.pass_stage.in_flood === false && !c.pass_stage.exempt
  ? `${c.pass_stage.ft.toFixed(1)} ft when NISAR passed, below its ${c.pass_stage.flood_ft} ft flood stage`
  : c.scope && c.scope.too_small ? (c.scope.readable_ha === 0 && c.scope.late_ha > 0 ? "Long past its crest when NISAR passed, so GLOWfm holds back on all of it" : `Only ${c.scope.readable_ha.toLocaleString("en-US")} ha of ground GLOWfm can read at the pass`)
  : c.scope && c.scope.in_scope === false ? `${Math.round(100 * (c.scope.tree_share || 0))}% of the valley floor is forest or wetland` : null);
const LISTED_NOT = new Set(["us_elff1_20261010", "us_mkhf1_20261103", "tested_neuse_090A_jul26", "tested_lower_sabine_134A_jul17"]);
const currentCases = (index) => index.cases.filter((c) => !c.superseded_by && !notOffered(c) && !LISTED_NOT.has(c.id));
const notOfferedCases = (index) => index.cases.filter((c) => !c.superseded_by && notOffered(c));

const RUN_STEPS = [
  ["compare", "Compare the flood pass with the passes before it"],
  ["signal", "Choose the radar signal"],
  ["keep", "Keep forest and wetland close to the river"],
  ["cut", "Let the scene set its own cut-off"],
  ["skip", "Skip ground where the flood is long past its crest"],
  ["grade", "Grade it"],
];
const HERO_PHOTO = { file: "photo_s2.webp", time: "2026-10-14T16:14:00Z", corners: [[-82.78, 31.66], [-81.65, 31.66], [-81.65, 30.86], [-82.78, 30.86]] };
const LENS_PATH = [[-82.56, 31.33], [-82.42, 31.29], [-82.33, 31.225], [-82.24, 31.215], [-82.12, 31.26], [-82.24, 31.215]];
const pct = (x, d = 1) => (x === null || x === undefined ? "—" : `${(100 * x).toFixed(d)}%`);
const ha = (x) => Math.round(x).toLocaleString("en-US");
const fmtDate = (d) => new Date(`${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}T12:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
const fmtTime = (iso) => new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC";
const passDate = (pair) => { const m = pair.match(/_([a-z]{3})(\d{2})$/); return m ? `${m[1][0].toUpperCase()}${m[1].slice(1)} ${Number(m[2])}` : pair; };
const siteTitle = (id) => EXTRA_TITLES[id] || id;
const WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"];
const inWords = (n) => WORDS[n] ?? String(n);
const fmtDay = (t) => new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const NISAR_REPEAT_MS = 12 * 864e5;
const nextPassBy = (lastMs, nowMs = Date.now()) => lastMs + Math.max(1, Math.ceil((nowMs - lastMs) / NISAR_REPEAT_MS)) * NISAR_REPEAT_MS;
let CATALOG_WAIT = null;
const catalogWait = () => (CATALOG_WAIT ??= fetch("data/figures/coverage.json").then((r) => r.json()).then((c) => c.summary.latency_days).catch(() => null));
const nextPassText = (lastMs, wait) => `NISAR should pass again by ${fmtDay(nextPassBy(lastMs))}` +
  (wait ? `; its scenes reach NASA's catalog a median ${wait.median} days later (half within ${wait.p25}–${wait.p75}).` : ".");
const fmtClock = (t) => new Date(t).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "UTC" }) + " UTC";
const utcYmd = (t) => { const d = new Date(t); return [d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()]; };
const calendarDays = (a, b) => Math.round((Date.UTC(...utcYmd(b)) - Date.UTC(...utcYmd(a))) / 864e5);
const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;

const loadData = () => Promise.all([fetch("data/manifest.json").then((r) => r.json()), fetch("data/metrics.json").then((r) => r.json())]);

let plotlyLoading;
function loadPlotly() {
  plotlyLoading ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js";
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
  return plotlyLoading;
}

function whenNear(el, run) {
  const check = () => {
    if (el.getBoundingClientRect().top > innerHeight + 500) return false;
    removeEventListener("scroll", check);
    removeEventListener("resize", check);
    run();
    return true;
  };
  if (check()) return;
  addEventListener("scroll", check, { passive: true });
  addEventListener("resize", check, { passive: true });
}

const plotBase = (extra) => ({ paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: CHART_FONT, ...extra });
const PLOT_OPTIONS = { displayModeBar: false, responsive: true };

const judgedPasses = (metrics) => metrics.held_out.filter((r) => r.csi !== null && r.csi !== undefined && (r.confirmed_ha ?? r.estimated_ha) >= JUDGE_HA);
const latestPasses = (metrics) => judgedPasses(metrics).filter((r) => r.method.startsWith("v4, overbank"));
const scoreRange = (metrics) => { const c = latestPasses(metrics).map((r) => r.csi); return [Math.min(...c), Math.max(...c)]; };

const TRUST_RECORD = "Set before it was tested, and right on 3 of 4 new passes so far. Too few to prove it yet, and green is never a guarantee.";
function trustLight({ mapped = true, confident, rainy }) {
  if (!mapped) return { cls: "grey", label: "No map", why: "The river was far past its crest, so GLOWfm doesn't map this pass." };
  if (!confident) return { cls: "red", label: "Trust light: red", why: "GLOWfm's own check flagged this pass: flooded forest didn't stand out from higher ground, so the map may include ordinary change. Check it against other sources before acting on it." };
  if (rainy === null || rainy === undefined) return { cls: "amber", label: "Trust light: amber", why: "Its own check passed, but rain wasn't checked here, and heavy rain can make dry ground look flooded." };
  if (rainy) return { cls: "red", label: "Trust light: red", why: "Heavy rain fell in the days before, and wet ground can look flooded to radar. Check this map against other sources before acting on it." };
  return { cls: "green", label: "Trust light: green", why: "Flooded forest stood out clearly, with no heavy rain, the conditions where NISAR's maps scored best." };
}
const rainyFrom = (rain) => (rain && rain.rain_24h_mm !== undefined ? rain.rain_24h_mm >= 5 || rain.rain_72h_mm >= 25 : null);

const RAIN_LITTLE_MM = 50;
const loadFloodRain = () => fetch("data/dashboard/rain.json").then((r) => (r.ok ? r.json() : null)).catch(() => null);
function rainCause(rr) {
  if (!rr) return null;
  const day = (d) => fmtDay(`${d.slice(0, 10)}T12:00Z`), a = day(rr.spell_from), b = day(rr.spell_to);
  return { mm: rr.mm, little: rr.mm < RAIN_LITTLE_MM, crest: day(rr.crest), spell: a.split(" ")[0] === b.split(" ")[0] ? `${a}–${b.split(" ")[1]}` : `${a}–${b}`, spellMm: rr.spell_mm };
}
function trustChip(t, { long = false } = {}) {
  return `<span class="trust trust-${t.cls}"${long ? "" : ` title="${t.why}"`}><i class="trust-dot" aria-hidden="true"></i><b>${t.label}</b>${long ? `<span class="trust-why">${t.why}</span>` : ""}</span>`;
}

const mapLegend = (items, note) => `<ul class="map-legend">${items.map(([kind, text]) => `<li><i class="mk mk-${kind}" aria-hidden="true"></i>${text}</li>`).join("")}${note ? `<li class="mk-note">${note}</li>` : ""}</ul>`;
const coordText = (v, pos, neg, d = 4) => `${Math.abs(v).toFixed(d)}°${v >= 0 ? pos : neg}`;

function gaugeMarker(map, g) {
  const el = document.createElement("div");
  el.className = "gauge-pin";
  el.title = g.name;
  const marker = new maplibregl.Marker({ element: el }).setLngLat([g.lon, g.lat]).setPopup(new maplibregl.Popup({ offset: 10 }).setText(`USGS gauge: ${g.name}`)).addTo(map);
  el.tabIndex = -1;
  el.removeAttribute("aria-label");
  el.setAttribute("aria-hidden", "true");
  return marker;
}

function addInstruments(map, { coords = true, label } = {}) {
  if (label) map.getCanvas().setAttribute("aria-label", label);
  map.addControl(new maplibregl.ScaleControl({ unit: "metric", maxWidth: 100 }), "bottom-left");
  if (!coords) return;
  const chip = document.createElement("div");
  chip.className = "map-coord";
  chip.setAttribute("aria-hidden", "true");
  map.getContainer().appendChild(chip);
  const show = (p, label) => { const { lng, lat } = p.wrap(); chip.textContent = `${label} ${coordText(lat, "N", "S")} ${coordText(lng, "E", "W")}`; };
  let over = false;
  map.on("mousemove", (e) => { over = true; show(e.lngLat, "Cursor"); });
  map.getCanvasContainer().addEventListener("mouseleave", () => { over = false; show(map.getCenter(), "Center"); });
  map.on("move", () => { if (!over) show(map.getCenter(), "Center"); });
  show(map.getCenter(), "Center");
}

function labelScrollAreas() {
  document.querySelectorAll(".table-wrap").forEach((el) => {
    let heading = null;
    for (let at = el; at && !heading; at = at.parentElement) {
      for (let prev = at.previousElementSibling; prev && !heading; prev = prev.previousElementSibling) if (/^H[1-3]$/.test(prev.tagName)) heading = prev;
      if (at.tagName === "SECTION") break;
    }
    el.tabIndex = 0;
    el.setAttribute("role", "region");
    el.setAttribute("aria-label", heading ? `Table: ${heading.textContent}` : "Table");
  });
}
labelScrollAreas();
