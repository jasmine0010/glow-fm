// Helpers shared by the story and evidence pages. All data comes from data/manifest.json and data/metrics.json
// (built by scripts/build_app.py). No server is needed.

const EXTRA_TITLES = { yellow: "Yellow River, FL", village_creek: "Village Creek, TX", pine_island: "Pine Island Bayou, TX", pee_dee: "Pee Dee River, SC", neuse: "Neuse River, NC", lower_sabine: "Lower Sabine River, TX/LA",
  satilla: "Satilla River, GA", alapaha: "Alapaha River, GA/FL", ochlockonee: "Ochlockonee River, GA/FL", withlacoochee: "Withlacoochee River, GA/FL", st_marys: "St Marys River, GA/FL", pearl: "Pearl River, LA/MS", tangipahoa: "Tangipahoa River, LA", choctawhatchee: "Choctawhatchee River, FL" };
const JUDGE_HA = 500;
// Checked with the dataviz palette validator on the dark surface. NISAR stays magenta everywhere; other series keep these slots.
const CHART = { nisar: "#d63ad6", estimate: "#00c8dc", lidar: "#bd8512", series: ["#1dbad0", "#bd8512", "#a86be8", "#4aa85e"], ink: "#cfdbe2", grid: "#2a3740" };
const CHART_FONT = { color: CHART.ink, family: '"IBM Plex Sans", system-ui, sans-serif', size: 12 };
// Above the plot, so a legend that wraps pushes into its own margin and not onto the data.
const CHART_LEGEND = { orientation: "h", x: 0, y: 1.02, yanchor: "bottom" };

const $ = (id) => document.getElementById(id);
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// ---------- the night: one meaning per colour, read from the tokens in style.css so maps, charts and words agree ----------
const PALETTE = (() => {
  const cs = getComputedStyle(document.documentElement), v = (name, fallback) => cs.getPropertyValue(name).trim() || fallback;
  return {
    water: v("--water", "#00c8dc"), waterInk: v("--water-ink", "#6fe3ef"), forest: v("--forest", "#4fdcb0"), forestInk: v("--forest-ink", "#8debcd"),
    nisar: v("--nisar", "#d63ad6"), nisarInk: v("--nisar-ink", "#e57ae5"), official: v("--official", "#286eff"), officialInk: v("--official-ink", "#8fb4ff"),
    veil: v("--veil", "#8a969e"), veilInk: v("--veil-ink", "#b9c4cb"), people: v("--people", "#ffb45a"), peopleInk: v("--people-ink", "#ffc98a"), action: v("--action", "#ffd166"),
  };
})();
const rgbOf = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));

// One basemap for every map: Esri World Imagery, toned down. On the night pages it's darker still, so the data carries the colour.
function basemap() {
  const night = document.body.classList.contains("night");
  return {
    version: 8,
    sources: { img: { type: "raster", tileSize: 256, maxzoom: 17, tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"], attribution: "Imagery © Esri" } },
    layers: [{ id: "img", type: "raster", source: "img", paint: night ? { "raster-saturation": -0.5, "raster-brightness-max": 0.62, "raster-contrast": 0.06 } : { "raster-saturation": -0.35, "raster-brightness-max": 0.72 } }],
  };
}
const BASEMAP = basemap();

// Scale helpers: a power of ten for the journey's scale readout, and a map's width in km.
const SUPERSCRIPT = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
const pow10 = (metres) => `10${String(Math.round(Math.log10(metres))).split("").map((c) => SUPERSCRIPT[c]).join("")} m`;
const boundsWidthKm = (b) => { const [w, s, e, n] = Array.isArray(b[0]) ? [b[0][0], b[0][1], b[1][0], b[1][1]] : b; return Math.abs(e - w) * 111.32 * Math.cos(((s + n) / 2) * Math.PI / 180); };
const kmText = (x) => (x >= 100 ? `${Math.round(x).toLocaleString("en-US")} km` : x >= 10 ? `${Math.round(x)} km` : `${x.toFixed(1)} km`);

// A number that counts up once, the first time it comes into view. With reduced motion it simply appears.
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

// An animation loop that runs only while `el` is on screen and the tab is visible. frame(dt) may return false to sleep
// until kick() wakes it, so an idle picture costs nothing.
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

// The flood board: the floods ready to run, newest NISAR pass first, and whether each is graded. The story page's
// console and the Run it yourself page share it; with pick, each flood is a button that chooses it.
function floodBoard(cases, { short = false } = {}) {
  const e = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const name = (c) => (short ? c.place.replace(/ at [^,]*/, "").replace(/ near [^,]*/, "") : c.place);
  const graded = (c) => (c.kind === "us" ? (c.scored ? '<span class="dep dep-us">against its gauges</span>' : '<span class="dep">gauges, not scored</span>') : '<span class="dep">map only, no gauges</span>');
  const first = (c) => `<span class="dep-place">${e(name(c))}</span><span class="dep-inline">${graded(c)}</span>`;
  const rows = [...cases].sort((a, b) => Date.parse(b.wet) - Date.parse(a.wet));
  return `<thead><tr><th scope="col">Flood</th><th scope="col">NISAR pass</th><th scope="col">Graded</th></tr></thead><tbody>${rows.map((c) => `<tr><td>${first(c)}</td><td>${fmtTime(c.wet)}</td><td>${graded(c)}</td></tr>`).join("")}</tbody>`;
}

// The same floods as a list to choose from (Run it yourself): one row each, the whole row a button.
function floodPicker(cases, sub) {
  const e = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const graded = (c) => (c.kind === "us" ? (c.scored ? '<span class="dep-us">checked against its gauges</span>' : "gauges, not scored") : "map only, no gauges");
  return [...cases].sort((a, b) => Date.parse(b.wet) - Date.parse(a.wet)).map((c) =>
    `<li><button type="button" class="live-row pick-row" data-case="${e(c.id)}" aria-pressed="false" title="NISAR pass ${e(fmtTime(c.wet))}">` +
    `<span class="pick-place">${e(c.place)}</span><span class="pick-when">${fmtDay(c.wet)}</span>` +
    `<span class="pick-sub">${sub(c)} · ${graded(c)}</span></button></li>`).join("");
}

// Live floods to list: a run rebuilt under a later protocol (research/LIVE_PROTOCOL_V2.md) replaces its first run in lists;
// the first run stays published and is linked from the newer one.
const currentCases = (index) => index.cases.filter((c) => !c.superseded_by);

// The steps of the method, in the order it runs them: the Run it yourself page and the story page's teaser share them.
const RUN_STEPS = [
  ["compare", "Compare the flood pass with the passes before it"],
  ["signal", "Choose the radar signal"],
  ["keep", "Keep forest and wetland close to the river"],
  ["cut", "Let the scene set its own cut-off"],
  ["skip", "Skip ground where the flood is long past its crest"],
  ["grade", "Grade it"],
];
// Sentinel-2 true color, Oct 14 16:14 UTC, 18.5 hours before NISAR's pass. See scripts/build_hero_photo.py.
const HERO_PHOTO = { file: "photo_s2.webp", time: "2026-10-14T16:14:00Z", corners: [[-82.78, 31.66], [-81.65, 31.66], [-81.65, 30.86], [-82.78, 30.86]] };
// The lens travels along the flooded valley once on arrival, and stops where NISAR's map is clearest.
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
// NISAR repeats each track every 12 days, so it passes a point again by the last pass + 12 days × k, the first such
// time after now. Another track can bring it sooner, hence "by".
const NISAR_REPEAT_MS = 12 * 864e5;
const nextPassBy = (lastMs, nowMs = Date.now()) => lastMs + Math.max(1, Math.ceil((nowMs - lastMs) / NISAR_REPEAT_MS)) * NISAR_REPEAT_MS;
// How long this season's scenes took to reach NASA's catalog (scripts/build_coverage.py), loaded once.
let CATALOG_WAIT = null;
const catalogWait = () => (CATALOG_WAIT ??= fetch("data/figures/coverage.json").then((r) => r.json()).then((c) => c.summary.latency_days).catch(() => null));
const nextPassText = (lastMs, wait) => `NISAR should pass again by ${fmtDay(nextPassBy(lastMs))}` +
  (wait ? `; its scenes reach NASA's catalog a median ${wait.median} days later (half within ${wait.p25}–${wait.p75}).` : ".");
const fmtClock = (t) => new Date(t).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "UTC" }) + " UTC";
// Days between two dates on the calendar (UTC), so a scene late on Oct 24 is nine days after Oct 15.
const utcYmd = (t) => { const d = new Date(t); return [d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()]; };
const calendarDays = (a, b) => Math.round((Date.UTC(...utcYmd(b)) - Date.UTC(...utcYmd(a))) / 864e5);
const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;

const loadData = () => Promise.all([fetch("data/manifest.json").then((r) => r.json()), fetch("data/metrics.json").then((r) => r.json())]);

// Plotly is large, so it loads only when a chart comes near the screen.
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

// Runs fn once, the first time a <details> panel opens, so charts and maps inside it draw at their real size.
function onOpen(details, fn) {
  if (!details) return;
  let done = false;
  const go = () => { if (done || !details.open) return; done = true; setTimeout(fn, 0); };
  details.addEventListener("toggle", go);
  go();
}

const plotBase = (extra) => ({ paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: CHART_FONT, ...extra });
const PLOT_OPTIONS = { displayModeBar: false, responsive: true };

// The passes plotted on the story page's scoreboard and summarised on both pages: frozen, with enough estimated flooding to judge.
const judgedPasses = (metrics) => metrics.held_out.filter((r) => r.csi !== null && r.csi !== undefined && (r.confirmed_ha ?? r.estimated_ha) >= JUDGE_HA);
const scoreRange = (metrics) => { const c = judgedPasses(metrics).map((r) => r.csi); return [Math.min(...c), Math.max(...c)]; };

function gaugeChart(id, gauges, layout) {
  const short = (n) => n.replace(/^(.*River|.*Creek|.*Bayou) /, "").replace(", FL", "").replace(", LA", "").replace(", MS", "");
  return Plotly.newPlot(id, gauges.map((g, i) => ({ x: g.times, y: g.stage_ft, name: short(g.name), mode: "lines", line: { width: 2, color: CHART.series[i % CHART.series.length] } })),
    plotBase({ margin: { l: 50, r: 10, t: 56, b: 36 }, yaxis: { title: "river level (ft)", gridcolor: CHART.grid }, xaxis: { gridcolor: CHART.grid }, legend: CHART_LEGEND, ...layout }), PLOT_OPTIONS);
}

// ---------- the trust light ----------
// One light on every NISAR map, from the trust signal fixed in research/OVERBANK_PROTOCOL.md section 4, before its first fair test:
// green if the map's own contrast check passed (low forest brightened more than higher forest) and there was no heavy rain,
// red otherwise. Rain means at least 5 mm in 24 hours or 25 mm in 72 hours (research/RAINFALL.md). Where rain wasn't checked,
// the light can't be green, so it shows amber. Its record: right on 3 of 4 fresh passes, too few to prove it.
const TRUST_RECORD = "Set before it was tested, and right on 3 of 4 new passes so far. Too few to prove it yet, and green is never a guarantee.";
function trustLight({ mapped = true, confident, rainy }) {
  if (!mapped) return { cls: "grey", label: "No map", why: "The river was far past its crest, so GLOWfm doesn't map this pass." };
  if (!confident) return { cls: "red", label: "Don't rely on this map", why: "Its own check failed, because flooded forest didn't stand out clearly from higher ground." };
  if (rainy === null || rainy === undefined) return { cls: "amber", label: "Partly checked", why: "Its own check passed, but rain wasn't checked, and heavy rain can make dry ground look flooded." };
  if (rainy) return { cls: "red", label: "Don't rely on this map", why: "Heavy rain fell in the days before, and wet ground can look flooded to radar." };
  return { cls: "green", label: "Trust light: green", why: "Flooded forest stood out clearly, with no heavy rain, the conditions where NISAR's maps scored best." };
}
const rainyFrom = (rain) => (rain && rain.rain_24h_mm !== undefined ? rain.rain_24h_mm >= 5 || rain.rain_72h_mm >= 25 : null);
function trustChip(t, { long = false } = {}) {
  return `<span class="trust trust-${t.cls}"${long ? "" : ` title="${t.why}"`}><i class="trust-dot" aria-hidden="true"></i><b>${t.label}</b>${long ? `<span class="trust-why">${t.why}</span>` : ""}</span>`;
}

// ---------- shared map parts ----------
// A map legend: one swatch and a few words per entry. Kinds: forest (floodplain points), town, flood, ring (dashed outline).
// A trailing note (the projection, say) sits after the entries in a quieter tone.
const mapLegend = (items, note) => `<ul class="map-legend">${items.map(([kind, text]) => `<li><i class="mk mk-${kind}" aria-hidden="true"></i>${text}</li>`).join("")}${note ? `<li class="mk-note">${note}</li>` : ""}</ul>`;
const coordText = (v, pos, neg, d = 4) => `${Math.abs(v).toFixed(d)}°${v >= 0 ? pos : neg}`;

// The small gauge marker used on every map. Pointers open it; it stays out of the keyboard order, because there can be dozens.
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

// A scale bar on any map, and optionally a coordinate readout that follows the cursor.
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

// Wide tables scroll sideways, so keyboard users need to be able to reach them.
function labelScrollAreas() {
  document.querySelectorAll(".table-wrap").forEach((el) => {
    // The nearest heading above this table, so that two tables in a section get different names.
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
