
const STYLE = BASEMAP;
const IV = "https://waterservices.usgs.gov/nwis/iv/";
const CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.umm_json";
const FT = 0.3048, HOUR = 36e5, DAY = 864e5, REPEAT_DAYS = 12, STALE_H = 3, UNUSABLE_H = 24, LIVE_REUSE = 5 * 60 * 1000;
const FLY_MS = 2600, PHONE_MAX = 1024;
const PIN_SIDE = { tangipahoa: "left", yellow: "left" };
const BLANK = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";
const LAYER_ROWS = [
  { key: "roads", label: "Road under water", color: "#ff8c42", on: true },
  { key: "gauges", label: "River gauges", color: "#ffffff", on: true },
  { key: "world", label: "Floods reported now", color: "#6fe3ef", on: true },
  { key: "gfm", label: "Outside today's flood map", color: "#5a5a5a", on: false, after: true },
];
const SHOWS = ["both", "nisar", "estimate"], EST_ALPHA = 204, OVER = [40, 235, 255, 150];
const DRAWER_PANELS = ["gauges", "graphs", "about"];
const SCORE_KIND = { frozen: "fair test", development: "development test", live: "Run it yourself run", auto: "added automatically" };
const hasScore = (p) => p && p.score !== null && p.score !== undefined;
const gapText = (ms) => ageText(ms).replace(" ago", "");
const matchPhrase = (score) => (score >= 0.6 ? "they matched well" : score >= 0.4 ? "they partly matched" : "they matched poorly");
const GRID_STEPS = [20, 10, 5, 2, 1, 0.5, 0.25, 0.1, 0.05, 0.025, 0.01];

let rivers = [], map, plotsReady = false;
const state = { sel: "river", mode: "live", river: null, pack: null, series: {}, histSeries: {}, grid: [], i: 0, now: Date.now(), rise: 0, layers: Object.fromEntries(LAYER_ROWS.map((l) => [l.key, l.on])), show: "both", timer: null, result: null, rows: [], areaToken: 0, catalog: null, updated: null, markers: [], markerRiver: null, lastSpot: null, mapReady: false, canvas: null, liveFailed: false, stores: {}, stripLevels: null, flying: false, flightToken: 0, flightTimer: null, overview: false, userMoved: false, panel: null, pins: [], settleTimer: null, backgroundTimer: null };

const round = (x, d = 2) => (x === null || x === undefined ? "—" : x.toFixed(d));
const ageText = (ms) => { const h = ms / HOUR; if (h < 1) return `${Math.max(1, Math.round(h * 60))} min ago`; const n = Math.round(h); if (h < 48) return `${n} hour${n === 1 ? "" : "s"} ago`; return `${Math.round(h / 24)} days ago`; };
const dayText = (t) => new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const utcText = (t) => `${new Date(t).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "UTC" })} UTC`;
const shortGauge = (r, name) => name.replace(/^(.*River|.*Creek|.*Bayou)\s+/i, "").replace(/,\s*(FL|GA|LA|MS|TX|FLA\.?)$/i, "").replace(/^(near|at|nr)\s+/i, "").replace(/^(Ga|Us|La|Fl)\s/, (m) => m.toUpperCase());
const tidyName = (name) => name.replace(/\bNear\b/g, "near").replace(/,\s*(Ga|Fl|La|Ms|Tx)\b\.?/g, (m, s) => `, ${s.toUpperCase()}`).replace(/\b(Ga|Us|La|Fl)\s(\d)/g, (m, a, b) => `${a.toUpperCase()} ${b}`);
const shortRiver = (r) => r.title.split(",")[0].replace(/ River$/, "");
const inBounds = (b, p) => { const { lng, lat } = p.wrap(); return lng >= b[0] && lng <= b[2] && lat >= b[1] && lat <= b[3]; };
const storeOf = (r) => (state.stores[r.id] ??= { radarUrl: null, loading: null, pack: null, gfmLoaded: false });
const isPhone = () => innerWidth <= PHONE_MAX;
const railsShown = () => !isPhone();
const isTablet = () => isPhone() && innerWidth > 640;   // one panel at a time, as a column beside the map
const sideRail = () => (isTablet() && document.body.dataset.sheet ? $(`rail-${document.body.dataset.sheet}`) : null);
const activeBounds = () => state.river.bounds;
function showSel(kind) {
  state.sel = kind;
  document.body.dataset.sel = kind;
  $("sel-river").hidden = kind !== "river";
  $("atlas-pick").hidden = kind !== "pick";
  if (state.mapReady && kind !== "river" && map.getSource("roads-wet")) map.getSource("roads-wet").setData(NO_ROADS);
  if (kind === "river") {
    if (state.mapReady && map.getSource("atlas-pick")) map.getSource("atlas-pick").setData({ type: "FeatureCollection", features: [] });
    if (typeof clearQuick === "function" && quick.id) clearQuick();
    atlas.pick = null; atlas.event = null;
    if (typeof renderWorld === "function") renderWorld();
  }
}

async function fetchLevels(ids, period) {
  const ctrl = new AbortController(), stop = setTimeout(() => ctrl.abort(), 30000);
  try {
    const r = await fetch(`${IV}?format=json&sites=${ids.join(",")}&parameterCd=00065&period=${period}&siteStatus=all`, { signal: ctrl.signal });
    if (!r.ok) throw new Error(`USGS answered ${r.status}`);
    const out = {};
    for (const ts of (await r.json()).value.timeSeries) {
      const id = ts.sourceInfo.siteCode[0].value, nodata = ts.variable.noDataValue;
      const best = ts.values.map((v) => v.value).sort((a, b) => b.length - a.length)[0] || [];
      const pts = best.map((p) => [Date.parse(p.dateTime), Number(p.value)]).filter(([, v]) => Number.isFinite(v) && v !== nodata && v > -900);
      if (pts.length && (!out[id] || pts.length > out[id].times.length)) out[id] = { times: pts.map((p) => p[0]), ft: pts.map((p) => p[1]) };
    }
    return out;
  } finally { clearTimeout(stop); }
}

function stageAt(s, t, maxGapH = 6) {
  if (!s || !s.times.length) return null;
  const { times, ft } = s;
  if (t < times[0] - maxGapH * HOUR || t > times[times.length - 1] + maxGapH * HOUR) return null;
  let lo = 0, hi = times.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (times[m] <= t) lo = m; else hi = m; }
  if (t <= times[lo]) return ft[lo];
  if (t >= times[hi]) return ft[hi];
  if (times[hi] - times[lo] > maxGapH * HOUR) return null;
  return ft[lo] + (ft[hi] - ft[lo]) * (t - times[lo]) / (times[hi] - times[lo]);
}

function gaugeRows(t) {
  const r = state.river;
  return r.gauges.map((g) => {
    const s = state.series[g.id];
    const last = s && s.times.length ? s.times[s.times.length - 1] : null;
    const usable = state.mode === "live" ? last !== null && t - last <= UNUSABLE_H * HOUR : true;
    const ft = usable ? (state.mode === "live" ? s.ft[s.ft.length - 1] : stageAt(s, t)) : null;
    const when = state.mode === "live" ? last : t;
    const before = ft === null ? null : stageAt(s, when - 6 * HOUR);
    const rate = ft === null || before === null ? null : (ft - before) * FT;
    return { g, ft, stage_m: ft === null ? null : ft * FT, read: last, age: last === null ? null : t - last, rise6h: rate, flood_m: g.flood_ft ? g.flood_ft * FT : null, margin: ft !== null && g.flood_ft ? (ft - g.flood_ft) * FT + state.rise : null };
  });
}

const currentTime = () => (state.mode === "live" ? state.now : state.grid[state.i]);
const trend = (x) => (x === null ? "—" : x > 0.03 ? `rising ${x.toFixed(2)} m` : x < -0.03 ? `falling ${(-x).toFixed(2)} m` : "steady");
const headlinePass = (r) => r.passes.find((p) => p.score_type === "frozen") || [...r.passes].sort((a, b) => (b.score ?? -1) - (a.score ?? -1))[0];

function buildGrid(r, hist) {
  const seriesList = r.gauges.map((g) => hist[g.id]).filter(Boolean);
  const a = Math.min(...seriesList.map((s) => s.times[0])), b = Math.max(...seriesList.map((s) => s.times[s.times.length - 1]));
  const out = [];
  for (let t = Math.ceil(a / HOUR) * HOUR; t <= b; t += HOUR) out.push(t);
  r.passes.forEach((p) => out.push(Date.parse(p.time)));
  return [...new Set(out)].sort((x, y) => x - y);
}

function ensureStore(r) {
  const st = storeOf(r);
  st.loading ??= Promise.all([fetch(`data/dashboard/${r.id}.bin`).then((x) => x.arrayBuffer()), fetch(`data/dashboard/${r.id}_gauges.json`).then((x) => x.json())]).then(([buffer, hist]) => {
    st.buffer = buffer;
    st.pack = packFromBuffer(r.grid, buffer);
    st.valley = valleyStats(st.pack);
    st.histSeries = Object.fromEntries(hist.map((g) => [g.id.replace("USGS-", ""), { times: g.times.map((x) => Date.parse(`${x}Z`)), ft: g.stage_ft }]));
    st.grid = buildGrid(r, st.histSeries);
    st.i = Math.max(0, st.grid.findIndex((t) => t >= Date.parse(headlinePass(r).time)));
    st.canvas = document.createElement("canvas");
    st.canvas.width = r.grid.cols; st.canvas.height = r.grid.rows;
    attachCanvas(r, st);
    return st;
  }).catch((e) => { st.loading = null; throw e; });
  return st.loading;
}

function valleyStats(pack) {
  const { n, flags, chain } = pack;
  let tree = 0, covered = 0, excluded = 0, lo = Infinity, hi = -Infinity;
  for (let i = 0; i < n; i++) {
    const f = flags[i];
    if (((f & FLAG.LC_MASK) >> FLAG.LC_SHIFT) === 1) tree++;
    if (f & FLAG.GFM_COVERED) { covered++; if (f & FLAG.GFM_EXCLUDED) excluded++; }
    if (chain[i] < lo) lo = chain[i];
    if (chain[i] > hi) hi = chain[i];
  }
  return { ha: n * pack.meta.pixel_ha, km: (hi - lo) / 1000, treeShare: n ? tree / n : null, maskShare: covered ? excluded / covered : null };
}

function crestOf(t) {
  let best = null;
  for (const g of state.river.gauges) {
    const s = state.series[g.id];
    if (!s || !g.flood_ft) continue;
    for (let k = 0; k < s.times.length; k++) {
      if (s.times[k] > t || s.times[k] < t - 8 * DAY) continue;
      const m = (s.ft[k] - g.flood_ft) * FT;
      if (!best || m > best.margin) best = { g, margin: m, t: s.times[k] };
    }
  }
  return best;
}

function ensureRoads(r) {
  const st = storeOf(r);
  st.roadsLoading ??= fetch(`data/dashboard/${r.id}_roads.bin`).then((x) => (x.ok ? x.arrayBuffer() : null))
    .then((b) => { st.roads = b ? roadsFromBuffer(b) : null; if (state.river === r && state.pack) update(); })
    .catch((err) => { console.warn(`Couldn't load the roads for ${r.id}`, err); st.roads = null; });
  return st.roadsLoading;
}

function attachCanvas(r, st) {
  const id = `est:${r.id}`;
  if (!state.mapReady || !st.canvas || map.getSource(id)) return;
  map.addSource(id, { type: "canvas", canvas: st.canvas, coordinates: st.pack.meta.quad, animate: false });
  map.addLayer({ id, type: "raster", source: id, paint: { "raster-resampling": "nearest", "raster-fade-duration": 0 } });
}

function drawEstimate(r, st, hasResult) {
  const { pack, canvas } = st;
  if (!pack || !canvas) return;
  const ctx = canvas.getContext("2d"), { rows, cols } = pack.meta, img = ctx.createImageData(cols, rows), d = img.data;
  if (hasResult && state.show === "estimate") {
    for (let i = 0; i < pack.n; i++) {
      if (!pack.wet[i]) continue;
      const p = pack.idx[i] * 4, t = Math.min(1, Math.max(0, (pack.depth[i] - 0.5) / 2.5));
      d[p] = 90 * (1 - t); d[p + 1] = 225 - 100 * t; d[p + 2] = 240 - 40 * t; d[p + 3] = EST_ALPHA;
    }
  } else if (hasResult && state.show === "both") {
    for (let i = 0; i < pack.n; i++) {
      if (!pack.wet[i]) continue;
      const p = pack.idx[i] * 4; d[p] = OVER[0]; d[p + 1] = OVER[1]; d[p + 2] = OVER[2]; d[p + 3] = OVER[3];
    }
  }
  ctx.putImageData(img, 0, 0);
  repaintCanvas(r);
}

const NO_ROADS = { type: "FeatureCollection", features: [] };
function addRoadLayers(m) {
  m.addSource("roads-wet", { type: "geojson", data: NO_ROADS });
  const width = (w) => ["interpolate", ["linear"], ["zoom"], 8, w * 0.5, 12, w, 15, w * 1.7], kind = (k) => ["==", ["get", "kind"], k];
  const line = (id, k, color, w, opacity = 1) => m.addLayer({ id, type: "line", source: "roads-wet", filter: kind(k), layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": color, "line-width": width(w), "line-opacity": opacity } });
  line("roads-full-casing", "full", "#05080b", 3.4, 0.7);
  line("roads-full", "full", "#e9eef1", 1.5, 0.9);
  line("roads-wet-casing", "wet", "#160b03", 5, 0.85);
  line("roads-wet", "wet", "#ff8c42", 2.8);
}
const ROAD_LAYERS = ["roads-full-casing", "roads-full", "roads-wet-casing", "roads-wet"];
function drawRoads(res = state.result) {
  if (!state.mapReady) return;
  const r = state.river, st = r && storeOf(r), show = state.layers.roads && state.sel === "river" && res && st && st.roads;
  let data = NO_ROADS;
  if (show) {
    const { full, wet } = roadFeatures(state.pack, st.roads);
    data = { type: "FeatureCollection", features: [{ type: "Feature", properties: { kind: "full" }, geometry: { type: "MultiLineString", coordinates: full } }, { type: "Feature", properties: { kind: "wet" }, geometry: { type: "MultiLineString", coordinates: wet } }] };
  }
  if (!map.getSource("roads-wet")) addRoadLayers(map);
  ROAD_LAYERS.forEach((id) => map.moveLayer(id));
  map.getSource("roads-wet").setData(data);
}

function roadFeatures(pack, roads) {
  const { pts, off, t, seg, way, pix } = roads, wet = [], hit = new Set();
  const point = (s, q) => (q === 0 ? [pts[2 * s], pts[2 * s + 1]] : q === 65535 ? [pts[2 * s + 2], pts[2 * s + 3]]
    : [pts[2 * s] + ((pts[2 * s + 2] - pts[2 * s]) * q) / 65535, pts[2 * s + 1] + ((pts[2 * s + 3] - pts[2 * s + 1]) * q) / 65535]);
  let line = null, last = null;
  for (let j = 0; j < roads.k; j++) {
    if (!pack.wet[pix[j]]) { line = null; continue; }
    hit.add(way[j]);
    const a = point(seg[j], t[2 * j]), b = point(seg[j], t[2 * j + 1]);
    if (line && a[0] === last[0] && a[1] === last[1]) line.push(b);
    else { line = [a, b]; wet.push(line); }
    last = b;
  }
  const full = [...hit].map((li) => { const out = []; for (let s = off[li]; s < off[li + 1]; s++) out.push([pts[2 * s], pts[2 * s + 1]]); return out; });
  return { full, wet };
}

function repaintCanvas(r) {
  const src = state.mapReady && map.getSource(`est:${r.id}`);
  if (src) { src.play(); src.pause(); }
}
const repaintCanvases = () => rivers.forEach(repaintCanvas);

function bothAt(r, t) {
  if (state.mode !== "live" || state.show === "estimate") return null;
  const p = r.passes[r.passes.length - 1];
  return p && t - Date.parse(p.time) > DAY ? Date.parse(p.time) : null;
}
function estimateAt(r, st, when) {
  const pts = [];
  for (const g of r.gauges) {
    const ft = stageAt(st.histSeries[g.id], when);
    if (ft !== null) pts.push({ chain: g.chain_m, wse: waterSurface(g, ft) });
  }
  return pts.length >= 2 ? estimateFlood(st.pack, pts, state.rise) : null;
}

function drawBackground() {
  for (const r of rivers) {
    const st = state.stores[r.id];
    if (!st || !st.pack || r === state.river) continue;
    const tb = bothAt(r, state.now);
    if (tb !== null) { drawEstimate(r, st, !!estimateAt(r, st, tb)); continue; }
    const pts = [];
    for (const g of r.gauges) {
      let ft = null;
      if (state.mode === "live") {
        const s = state.stripLevels && state.stripLevels[g.id];
        if (s && s.times.length && Date.now() - s.times[s.times.length - 1] <= UNUSABLE_H * HOUR) ft = s.ft[s.ft.length - 1];
      } else ft = stageAt(st.histSeries[g.id], st.grid[st.i]);
      if (ft !== null) pts.push({ chain: g.chain_m, wse: waterSurface(g, ft) });
    }
    const result = pts.length >= 2 ? estimateFlood(st.pack, pts, state.rise) : null;
    drawEstimate(r, st, !!result);
  }
}
const scheduleBackground = () => { clearTimeout(state.backgroundTimer); state.backgroundTimer = setTimeout(drawBackground, 250); };

function currentPass(t, r = state.river) {
  const passes = r.passes;
  if (state.mode === "live") return passes[passes.length - 1];
  return [...passes].reverse().find((p) => Date.parse(p.time) <= t) || null;
}

function passFor(r) {
  if (r === state.river && state.pack) return currentPass(currentTime(), r);
  return state.mode === "live" ? r.passes[r.passes.length - 1] : headlinePass(r);
}

function syncLayers() {
  if (!state.mapReady) return;
  const showNisar = state.show !== "estimate";
  for (const r of rivers) {
    const st = storeOf(r), p = passFor(r), nisar = `nisar:${r.id}`, gfm = `gfm:${r.id}`;
    if (p && st.radarUrl !== p.layer) {
      st.radarUrl = p.layer;
      map.getSource(nisar).updateImage({ url: `data/${p.layer}`, coordinates: r.corners });
    }
    map.setLayoutProperty(nisar, "visibility", p && showNisar ? "visible" : "none");
    if (state.layers.gfm && r.gfm_layer && !st.gfmLoaded) { st.gfmLoaded = true; map.getSource(gfm).updateImage({ url: `data/${r.gfm_layer}`, coordinates: r.corners }); }
    map.setLayoutProperty(gfm, "visibility", state.layers.gfm && r.gfm_layer ? "visible" : "none");
  }
  ["world-floods", "world-floods-halo"].forEach((id) => { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", state.layers.world ? "visible" : "none"); });
  $("show-switch").hidden = state.sel !== "river";
  $("map-tag").hidden = state.sel !== "river";
  map.setLayoutProperty("grid", "visibility", state.flying ? "none" : "visible");
  $("grid-labels").hidden = state.flying;
}

function drawMarkers() {
  const show = state.mapReady && state.layers.gauges;
  const same = show && state.markerRiver === state.river.id && state.markers.length;
  if (!same) { state.markers.forEach((m) => m.marker.remove()); state.markers = []; state.markerRiver = null; }
  if (!show) return;
  state.rows.forEach((row, k) => {
    const above = row.margin !== null && row.margin > 0;
    const text = row.ft === null ? "no recent reading" : `${(row.stage_m).toFixed(2)} m at the gauge${row.margin === null ? ", no listed flood level" : `, ${Math.abs(row.margin).toFixed(2)} m ${above ? "above" : "below"} flood level`}`;
    const cls = `gauge-pin${above ? " above" : ""}${row.ft === null ? " off" : ""}`, label = `${row.g.name}: ${text}`;
    if (same) {
      state.markers.filter((m) => m.k === k).forEach((m) => { m.el.classList.toggle("above", above); m.el.classList.toggle("off", row.ft === null); m.popup.setText(label); });
      return;
    }
    const el = document.createElement("div"), popup = new maplibregl.Popup({ offset: 10 }).setText(label);
    el.className = cls; el.title = row.g.name;
    state.markers.push({ k, el, popup, marker: new maplibregl.Marker({ element: el }).setLngLat([row.g.lon, row.g.lat]).setPopup(popup).addTo(map) });
    el.tabIndex = -1; el.removeAttribute("aria-label"); el.setAttribute("aria-hidden", "true");
  });
  state.markerRiver = state.river.id;
}

function update() {
  const r = state.river, t = currentTime(), st = storeOf(r);
  if (!r || !state.pack) return;
  st.i = state.i;
  state.rows = gaugeRows(t);
  const tb = bothAt(r, t);
  state.bothAt = tb === null ? null : { t: tb, ok: false };
  if (tb !== null) { const rb = estimateAt(r, st, tb); state.bothAt.ok = !!rb; drawEstimate(r, st, !!rb); if (!st.roadsLoading) ensureRoads(r); drawRoads(rb); }
  const pts = state.rows.filter((x) => x.ft !== null).map((x) => ({ chain: x.g.chain_m, wse: waterSurface(x.g, x.ft) }));
  state.result = pts.length >= 2 ? estimateFlood(state.pack, pts, state.rise) : null;
  if (!st.roadsLoading) ensureRoads(r);
  if (state.result && st.roads) state.result.roads = roadsUnder(state.pack, st.roads);
  state.points = pts;
  if (tb === null) { drawEstimate(r, st, !!state.result); drawRoads(); }
  syncLayers(); drawMarkers();
  renderKpis(t); renderVerdict(t); renderGauges(); renderInsights(); renderTag(t); renderFacts(t); renderFreshness();
  drawProfile(); moveCursors(t);
  if (state.lastSpot) showSpot(state.lastSpot);
  {
    const now = state.mode === "live";
    $("t-out").innerHTML = now ? `<i class="live-dot"></i>${utcText(t)} · live` : utcText(t);
    $("t-strip").setAttribute("aria-valuenow", String(now ? state.grid.length : state.i));
    $("t-strip").setAttribute("aria-valuetext", now ? `Live river levels, ${utcText(t)}` : utcText(t));
    if (state.strip) { state.strip.head(t); state.strip.select(now ? -1 : state.river.passes.findIndex((p) => Math.abs(Date.parse(p.time) - t) < 60000)); }
  }
  $("card-note").hidden = !state.liveFailed;
  $("card-note").textContent = "Live river levels couldn't be reached, so this shows the recorded flood. They're tried again every 5 minutes.";
  syncUrl();
}

function clearPanels(r) {
  ["k-radar", "k-ha"].forEach((id) => { $(id).textContent = "…"; });
  ["k-radar-sub", "k-ha-sub", "k-trust"].forEach((id) => { $(id).textContent = ""; });
  $("facts").innerHTML = ""; $("facts").style.minHeight = "";
  $("spot").innerHTML = '<p class="muted">Click the map.</p>';
  $("river-title").textContent = r.title;
  $("dash-sub").textContent = "Loading…";
  $("freshness").innerHTML = "";
  $("mini").textContent = r.title;
  state.lastSpot = null;
}

function renderKpis(t) {
  const { result, rows } = state;
  const reading = rows.filter((x) => x.ft !== null), listed = reading.filter((x) => x.margin !== null), above = listed.filter((x) => x.margin > 0);
  const big = (x) => `${ha(x)}<small> ha</small>`;
  $("k-ha-label").textContent = state.mode === "live" ? "Estimate now" : `Estimate, ${dayText(t)}`;
  $("k-ha").innerHTML = result ? big(result.ha) : "—";
  $("k-ha-sub").textContent = (state.rise ? `river +${state.rise} m · ` : "") + (!result ? "needs two gauges reading" : result.ha > 0 ? `${pct(result.treeShare, 0)} under trees` : "none near the gauges");
  const p = currentPass(t), gap = p ? t - Date.parse(p.time) : null, samePass = p && gap < 60000;
  $("k-radar-label").textContent = p ? `NISAR map, ${dayText(p.time)}${p.box ? ", one box" : ""}` : "NISAR map";
  $("k-radar").innerHTML = !p ? "—" : p.flagged_ha === undefined ? "—" : big(p.flagged_ha);
  $("k-trust").innerHTML = p && p.confident !== undefined ? trustChip(trustLight({ mapped: p.flagged_ha !== 0, confident: p.confident, rainy: p.rainy })) : "";
  $("k-radar-sub").textContent = !p ? "no pass yet" : gap > DAY ? "" : !samePass ? `mapped ${gapText(gap)} before this estimate` : state.rise ? "no match score in a what-if view" : hasScore(p) ? `match ${p.score.toFixed(2)} of 1 · ${SCORE_KIND[p.score_type] || p.score_type}` : "no match score";
  if (p && p.box && (samePass || gap <= DAY)) $("k-radar-sub").textContent = `only ${p.box}`;
  $("mini").textContent = state.river.title;
}

const hiddenRoad = (road, ofIt = "") => (road.hiddenKm >= 0.995 * road.km ? `all${ofIt}` : road.hiddenKm >= 0.95 * road.km ? `nearly all${ofIt}` : kmText(road.hiddenKm));

function renderVerdict(t) {
  const { result, rows } = state, p = currentPass(t), gap = p ? t - Date.parse(p.time) : null;
  let text;
  if (!result) text = "Too few gauges are reading for an estimate.";
  else if (state.rise) text = `What-if view, with every gauge ${state.rise} m higher.`;
  else if (state.mode === "live") {
    const listed = rows.filter((x) => x.margin !== null), above = listed.filter((x) => x.margin > 0).length;
    text = listed.length ? `${above ? `${above} of ${listed.length}` : "No"} gauge${above === 1 ? " is" : "s are"} above flood level now.` : "Live river levels, no listed flood levels.";
  } else if (p && gap < 60000) {
    const when = dayText(p.time);
    text = p.box ? `On ${when}, GLOWfm was run only on ${p.box}.`
      : p.flagged_ha === 0 ? `On ${when}, GLOWfm mapped no flooding.`
        : hasScore(p) ? `On ${when}, NISAR's map and the gauge estimate ${matchPhrase(p.score).replace(/^they /, "")}.`
          : `On ${when}, NISAR passed; this pass has no match score.`;
  } else text = `${dayText(t)}, between NISAR passes.`;
  $("dash-sub").textContent = text;
}

function renderKey() {
  if (atlas.summary) $("atlas-ramp").innerHTML = atlasKey();
}

function renderTag(t) {
  renderKey();
  const p = currentPass(t), est = `estimate ${utcText(t)}${state.rise ? `, +${state.rise} m` : ""}`, radar = p ? `NISAR ${dayText(p.time)}` : "No NISAR pass yet";
  const rise = state.rise ? `, +${state.rise} m` : "", onPass = p && state.mode === "history" && Math.abs(t - Date.parse(p.time)) < 60000;
  const same = state.bothAt ? (state.bothAt.ok ? `${utcText(Date.parse(p.time))}${rise}` : `NISAR ${dayText(p.time)} · no recorded river levels for that day`)
    : onPass ? `${utcText(t)}${rise}` : `${radar} · ${est}`;
  $("map-tag").innerHTML = state.show === "nisar" ? radar : state.show === "estimate" ? `${est[0].toUpperCase()}${est.slice(1)}`
    : same;
  $("map-note").textContent = `The switch on the map picks what it shows. NISAR shows NISAR's flood map in magenta. Estimate shows flooding estimated from gauges and lidar in blue, computed in your browser, deeper water darker. Both lays the estimate in see-through cyan over NISAR's magenta, so blue is where they agree, magenta where only NISAR mapped flooding and cyan where only the estimate did. In Live mode, when NISAR's map is more than a day old, Both compares it with the estimate for that same pass, from the river's recorded levels, so the colors never compare two different days; Estimate and the card show today.${state.layers.roads && state.result && state.result.roads && state.result.roads.km >= 0.05 ? " Orange lines are drivable roads on the estimated flooding; the rest of each of those roads is drawn in white." : ""}${atlas.enabled ? " Green-teal blocks are the blind-spot map, which shows where floodplain is under trees, a risk rather than flooding." : ""}`;
}

function freeArea() {
  const left = railsShown() ? $("rail-left").getBoundingClientRect().right : 0, right = railsShown() ? $("rail-right").getBoundingClientRect().left : innerWidth;
  return [left, right];
}

function renderFreshness() {
  const t = currentTime(), p = currentPass(t), gap = p ? t - Date.parse(p.time) : null, items = [];
  if (state.mode === "live") {
    const reading = state.rows.filter((x) => x.read !== null), newest = reading.length ? Math.max(...reading.map((x) => x.read)) : null, oldest = reading.length ? Math.min(...reading.map((x) => x.read)) : null;
    const stale = oldest !== null && Date.now() - oldest > STALE_H * HOUR;
    items.push(`<span class="fresh-item"><i class="live-dot"></i><b>River</b> ${newest === null ? "no reading" : ageText(Date.now() - newest)}${stale ? ", some gauges behind" : ""}</span>`);
  }
  if (!p) items.push(`<span class="fresh-item">No NISAR pass yet</span>`);
  else if (gap > DAY) items.push(`<span class="fresh-item"><b>NISAR map</b> ${gapText(gap)} older</span>`);
  $("freshness").innerHTML = items.join("");
}

function renderGauges() {
  $("t-gauges").innerHTML = "<tr><th>Gauge</th><th>Level</th><th>NWS flood level</th><th>Against flood level</th><th>Past 6 hours</th><th>Water surface (NAVD88)</th><th>Reading</th></tr>" +
    state.rows.map((x) => {
      const pill = x.margin === null ? '<span class="pill grey">no level</span>' : x.margin > 0 ? `<span class="pill red">${x.margin.toFixed(2)} m above</span>` : `<span class="pill green">${(-x.margin).toFixed(2)} m below</span>`;
      const readText = state.mode === "history" ? utcText(currentTime()) : x.read === null ? "none" : ageText(Date.now() - x.read);
      return `<tr><td>${x.g.name}</td><td>${x.ft === null ? "no reading" : `${(x.stage_m + state.rise).toFixed(2)} m`}</td><td>${x.flood_m === null ? "—" : `${x.flood_m.toFixed(2)} m`}</td><td>${x.ft === null ? "—" : pill}</td><td>${trend(x.rise6h)}</td><td>${x.ft === null ? "—" : `${(waterSurface(x.g, x.ft) + state.rise).toFixed(2)} m`}</td><td>${readText}</td></tr>`;
    }).join("");
}

function renderInsights() {
  $("insights").innerHTML = `<div class="insight"><b>How far to trust this</b><p>The estimate is a model, not a sighting of water. In our hidden-gauge test it was often off by more than a meter across long gaps between gauges.</p></div>`;
}

function renderFacts(t) {
  const r = state.river, { rows, result } = state, st = storeOf(r), p = currentPass(t), live = state.mode === "live";
  const row = (k, v) => (v === null || v === undefined || v === "" ? "" : `<dt>${k}</dt><dd>${v}</dd>`);
  const group = (head, items) => { const body = items.join(""); return body ? `<p class="facts-head">${head}</p><dl class="facts-list">${body}</dl>` : ""; };
  const val = (fig, rest = "", cls = "") => `<b${cls ? ` class="${cls}"` : ""}>${fig}</b>${rest ? ` <span>${rest}</span>` : ""}`;
  const vs = (m) => val(`${Math.abs(m).toFixed(1)} m ${m > 0 ? "above" : "below"}`, "", m > 0 ? "f-red" : "");
  const where = (g) => shortGauge(r, g.name);

  const reading = rows.filter((x) => x.ft !== null), listed = reading.filter((x) => x.margin !== null), above = listed.filter((x) => x.margin > 0);
  const top = [...listed].sort((a, b) => b.margin - a.margin)[0];
  const moving = reading.filter((x) => x.rise6h !== null), mean6 = moving.length ? moving.reduce((s, x) => s + x.rise6h, 0) / moving.length : null;
  const crest = crestOf(t), road = result && result.roads;
  const sixHours = mean6 === null ? null : Math.abs(mean6) <= 0.03 ? val("steady") : val(`${mean6 > 0 ? "↑" : "↓"} ${Math.abs(mean6).toFixed(2)} m`, mean6 > 0 ? "rising" : "falling");
  const river = [
    row("Above flood level", listed.length ? val(`${above.length} of ${listed.length}`, "gauges", above.length ? "f-red" : "") : reading.length ? val("—", "no flood levels listed") : val("—", "no gauge reporting")),
    top ? row(above.length ? "Highest gauge" : "Closest to flood", `${vs(top.margin)} <span>${where(top.g)}</span>`) : "",
    row("Past 6 hours", sixHours),
    row("Peak, 8 days", crest ? `${vs(crest.margin)} <span>${dayText(crest.t)}, ${where(crest.g)}</span>` : null),
    row("Road under water", !road ? null : road.km < 0.05 ? val("none") : val(kmText(road.km), road.hiddenKm >= 0.05 ? `${hiddenRoad(road)} off the official map` : "", "f-road")),
    row("Deepest water", !result ? null : result.ha > 0 ? val(`${result.maxDepth.toFixed(1)} m`, "", "f-water") : val("—")),
    row("Official map misses", !result ? null : result.ha > 0 && result.maskShare !== null ? val(pct(result.maskShare, 0), "of this flooding, in its mask", "f-official") : val("—")),
  ];

  const track = p && p.layer.match(/(\d{3})([AD])_/), c = live ? state.catalog : null;
  const utc = (x) => new Date(x).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "UTC" });
  const newer = c && c.newest && p && c.newest > Date.parse(p.time) + HOUR ? c.newest : null;
  const nisar = [
    row("Map shown", p ? val(dayText(p.time), `${utc(p.time)} UTC${track ? `, track ${track[1]} ${track[2] === "A" ? "ascending" : "descending"}` : ""}`, "f-nisar") : val("—", "no pass yet")),
    row("Next pass", c && c.next ? val(`~${dayText(c.next)}`, newer ? `a newer scene from ${dayText(newer)} isn't mapped yet` : "", "f-nisar") : null),
  ];

  const v = st.valley, a = r.audit, f = r.frozen, held = r.role === "held-out" || r.role === "sealed";
  const aDay = a ? dayText(`${a.date.slice(0, 4)}-${a.date.slice(4, 6)}-${a.date.slice(6, 8)}T12:00Z`) : "";
  const valley = [
    row("Under trees", v && v.treeShare !== null ? val(pct(v.treeShare, 0), "of the valley", "f-forest") : null),
    row("Official map skips", v && v.maskShare !== null ? val(pct(v.maskShare, 0), "of the valley it covers", "f-official") : null),
    row("Size", v ? val(kmText(v.km), `${ha(v.ha)} ha, ${r.gauges.length} gauges`) : null),
  ];
  const fp = f && r.passes.find((x) => x.id === f.pair);
  const rc = rainCause(state.rain && state.rain.rivers[r.id]);
  const record = [
    row("Likely cause", !rc ? null : rc.little
      ? val(`${rc.mm} mm`, `of rain on its catchment in the two weeks to the ${rc.crest} crest, little, so it was likely high from earlier rain (NASA GPM IMERG)`)
      : val(`${rc.mm} mm`, `of rain on its catchment in the two weeks to the ${rc.crest} crest, ${rc.spellMm} mm of it on ${rc.spell} (NASA GPM IMERG)`, "f-water")),
    row("Fair test", !f ? null : f.csi === null || f.csi === undefined ? val("—", "too little flooding to score") : val(f.csi.toFixed(2), `of 1, ${passDate(f.pair)}${held ? ", held out" : r.role === "development" ? ", a river that helped build GLOWfm" : ""}`)),
    row("Lidar-only map", fp && fp.lidar_score !== null && fp.lidar_score !== undefined ? val(fp.lidar_score.toFixed(2), `of 1, ${passDate(f.pair)}, the same map every day`) : null),
    a ? row("Official map", val(`${ha(a.gfm_ha)} ha`, `mapped on ${aDay}, of ${ha(a.estimated_ha)} ha estimated`, "f-official")) : "",
  ];

  const html = group("NISAR", nisar) + group(live ? "River now" : `River, ${dayText(t)}`, river) + group("This valley", valley) + group(`On record${r.event ? ` <span>${r.event}</span>` : ""}`, record);
  if ($("facts").dataset.html !== html) { $("facts").innerHTML = html; $("facts").dataset.html = html; }
}

function quadToPixel(lng, lat) {
  const { quad, rows, cols } = state.pack.meta;
  const [[x0, y0], [x1, y1], , [x3, y3]] = quad;
  const ax = x1 - x0, ay = y1 - y0, bx = x3 - x0, by = y3 - y0, det = ax * by - ay * bx;
  const u = ((lng - x0) * by - (lat - y0) * bx) / det, v = ((lat - y0) * ax - (lng - x0) * ay) / det;
  return { r: Math.floor(v * rows), c: Math.floor(u * cols) };
}

function showSpot(lngLat) {
  if (state.lastSpot !== lngLat) $("details-box").open = true;
  state.lastSpot = lngLat;
  const { pack } = state;
  if (!pack) return;
  const { r, c } = quadToPixel(lngLat.lng, lngLat.lat), { rows, cols } = pack.meta;
  const i = r >= 0 && c >= 0 && r < rows && c < cols ? pack.lookup[r * cols + c] : -1;
  if (i < 0) { $("spot").innerHTML = '<p class="muted">Outside the valley corridor this tool covers.</p>'; return; }
  const f = pack.flags[i], lc = ["other", "tree cover", "wetland", "crop, grass or shrub"][(f & FLAG.LC_MASK) >> FLAG.LC_SHIFT], supported = f & FLAG.SUPPORTED, depth = pack.depth[i];
  const verdict = f & FLAG.SEED ? "Permanent water, so it isn't counted as flooding."
    : !supported ? "More than 10 km from a gauge, so the estimate doesn't cover this spot."
      : pack.wet[i] ? `Estimated flooded, about ${depth.toFixed(1)} m deep.`
        : depth > 0 ? "Below the water line, but within the margin or not connected to the channel, so it isn't counted."
          : `Estimated dry, with ground ${(-depth).toFixed(1)} m above the water line.`;
  $("spot").innerHTML = `<dl><dt>Ground height</dt><dd>${pack.dem[i].toFixed(1)} m</dd><dt>Water surface</dt><dd>${(pack.dem[i] + depth).toFixed(1)} m</dd><dt>Land cover</dt><dd>${lc}</dd><dt>Along valley</dt><dd>${(pack.chain[i] / 1000).toFixed(1)} km</dd><dt>GFM</dt><dd>${f & FLAG.GFM_COVERED ? (f & FLAG.GFM_EXCLUDED ? "doesn't map this spot" : "maps this spot") : "no data here"}</dd></dl><div class="verdict">${verdict}</div>`;
}

function onMapClick(e) {
  const flood = worldAt(map, e.point);
  if (flood) { chooseWorld(flood); return; }
  const here = (r) => inBounds(r.bounds, e.lngLat);
  if (state.sel === "river" && here(state.river)) { showSpot(e.lngLat); if (isPhone() && state.panel !== "right") setPanel("right"); return; }
  const other = rivers.find((r) => here(r));
  if (other) { setFloodTab("tested"); return activate(other.id); }
  if (!atlas.enabled) return;
  const { lat, lng } = e.lngLat.wrap();
  setFloodTab("blind");
  atlasPickAt(lat, lng);
  if (isPhone() && state.panel !== "right") setPanel("right");
}

const graphsOpen = () => plotsReady && state.panel === "graphs";

function moveCursors(t) {
  if (!graphsOpen()) return;
  const shape = { type: "line", xref: "x", yref: "paper", x0: new Date(t), x1: new Date(t), y0: 0, y1: 1, line: { color: "#e8eef2", width: 1.5 } };
  const passes = visiblePasses().map((p) => ({ type: "line", xref: "x", yref: "paper", x0: p.time, x1: p.time, y0: 0, y1: 0.06, line: { color: CHART.nisar, width: 3 } }));
  for (const id of ["c-levels", "c-area"]) if ($(id).data) Plotly.relayout(id, { shapes: [...(id === "c-levels" ? floodShapes() : []), shape, ...passes] });
}

const visiblePasses = () => { const [a, b] = chartRange(); return state.river.passes.filter((p) => { const x = Date.parse(p.time); return x >= a && x <= b; }); };
const chartRange = () => (state.mode === "live" ? [state.now - 7 * DAY, state.now] : [state.grid[0], state.grid[state.grid.length - 1]]);
const floodShapes = () => state.river.gauges.map((g, k) => (g.flood_ft ? { type: "line", xref: "paper", yref: "y", x0: 0, x1: 1, y0: g.flood_ft * FT, y1: g.flood_ft * FT, line: { color: CHART.series[k % 4], width: 1, dash: "dot" } } : null)).filter(Boolean);

function drawLevels() {
  const r = state.river, [a, b] = chartRange();
  const traces = r.gauges.map((g, k) => {
    const s = state.series[g.id];
    const keep = s ? s.times.map((x, i) => [x, s.ft[i]]).filter(([x]) => x >= a && x <= b) : [];
    return { x: keep.map((p) => new Date(p[0])), y: keep.map((p) => p[1] * FT), name: shortGauge(r, g.name), mode: "lines", line: { width: 2, color: CHART.series[k % 4] } };
  });
  Plotly.newPlot("c-levels", traces, plotBase({ margin: { l: 50, r: 10, t: 56, b: 36 }, yaxis: { title: "level at gauge (m)", gridcolor: CHART.grid }, xaxis: { gridcolor: CHART.grid, range: [new Date(a), new Date(b)] }, legend: CHART_LEGEND, shapes: floodShapes() }), PLOT_OPTIONS);
}

function drawArea() {
  const token = ++state.areaToken, r = state.river, [a, b] = chartRange(), st = storeOf(r);
  st.seriesPack ??= packFromBuffer(r.grid, st.buffer);
  const step = state.mode === "live" ? 3 * HOUR : 6 * HOUR, times = [];
  for (let t = a; t <= b; t += step) times.push(t);
  const xs = [], ys = [];
  const passes = r.passes.filter((p) => p.flagged_ha !== undefined && Date.parse(p.time) >= a && Date.parse(p.time) <= b);
  const traces = [{ x: [], y: [], name: "Gauge and lidar estimate", mode: "lines", line: { color: CHART.estimate, width: 2 } }, { x: passes.map((p) => p.time), y: passes.map((p) => p.flagged_ha), name: "NISAR flood map", mode: "markers", marker: { color: CHART.nisar, size: 10 } }];
  const stat = r.passes.find((p) => p.static_ha !== undefined);
  if (stat) traces.push({ x: [new Date(a), new Date(b)], y: [stat.static_ha, stat.static_ha], name: "Lidar map, same every day", mode: "lines", line: { color: CHART.lidar, width: 2, dash: "dash" } });
  Plotly.newPlot("c-area", traces, plotBase({ margin: { l: 56, r: 10, t: 56, b: 36 }, yaxis: { title: "hectares", gridcolor: CHART.grid, rangemode: "tozero" }, xaxis: { gridcolor: CHART.grid, range: [new Date(a), new Date(b)] }, legend: CHART_LEGEND }), PLOT_OPTIONS);
  $("c-area-note").textContent = state.mode === "live" ? "Past 7 days, recomputed from each gauge's readings." : "Recomputed from the recorded gauge levels. NISAR dots show what each pass mapped.";
  const series = state.series;
  const seriesFor = (t) => {
    const pts = r.gauges.map((g) => { const ft = stageAt(series[g.id], t); return ft === null ? null : { chain: g.chain_m, wse: waterSurface(g, ft) }; }).filter(Boolean);
    return pts.length >= 2 ? estimateFlood(st.seriesPack, pts, 0).ha : null;
  };
  let k = 0;
  const chunk = () => {
    if (token !== state.areaToken) return;
    const stop = performance.now() + 30;
    while (k < times.length && performance.now() < stop) { xs.push(new Date(times[k])); ys.push(seriesFor(times[k])); k++; }
    Plotly.restyle("c-area", { x: [xs], y: [ys] }, [0]);
    if (k < times.length) setTimeout(chunk, 0);
  };
  chunk();
}

function drawProfile() {
  if (!graphsOpen()) return;
  const r = state.river, sorted = state.rows.filter((x) => x.ft !== null).sort((a, b) => a.g.chain_m - b.g.chain_m);
  const km = r.profile.map((p) => p.km);
  const traces = [
    { x: km, y: r.profile.map((p) => p.low_m), name: "Lowest ground", mode: "lines", line: { color: CHART.lidar, width: 2 } },
    { x: km, y: r.profile.map((p) => p.typical_m), name: "Typical valley ground", mode: "lines", line: { color: CHART.series[2], width: 2 } },
    { x: sorted.map((x) => x.g.chain_m / 1000), y: sorted.map((x) => waterSurface(x.g, x.ft) + state.rise), name: "Water surface", mode: "lines+markers", line: { color: CHART.estimate, width: 2 }, marker: { size: 9 }, text: sorted.map((x) => x.g.name), hovertemplate: "%{text}<br>%{y:.2f} m<extra></extra>" },
  ];
  const layout = plotBase({ margin: { l: 56, r: 10, t: 56, b: 44 }, xaxis: { title: "distance along the valley (km)", gridcolor: CHART.grid }, yaxis: { title: "height above sea level (m)", gridcolor: CHART.grid }, legend: CHART_LEGEND });
  if ($("c-profile").data) Plotly.react("c-profile", traces, layout, PLOT_OPTIONS); else Plotly.newPlot("c-profile", traces, layout, PLOT_OPTIONS);
}

function drawCharts() {
  if (!graphsOpen()) return;
  if (!state.pack) return;
  drawLevels(); drawArea(); drawProfile(); moveCursors(currentTime());
}

async function loadCatalog(r) {
  state.catalog = null;
  if (typeof world === "object" && world.catalogDown) return;
  const lons = r.gauges.map((g) => g.lon), lats = r.gauges.map((g) => g.lat);
  try {
    const q = new URLSearchParams({ short_name: "NISAR_L2_GCOV_V1", bounding_box: `${Math.min(...lons)},${Math.min(...lats)},${Math.max(...lons)},${Math.max(...lats)}`, sort_key: "-start_date", page_size: "20" });
    q.append("short_name", "NISAR_L2_GCOV_PROVISIONAL_V1");
    const j = await (await withTimeout(`${CMR_URL}?${q}`)).json();
    const scenes = j.items.map((i) => ({ t: Date.parse(i.umm.TemporalExtent.RangeDateTime.BeginningDateTime), track: i.umm.GranuleUR.split("_")[6] + i.umm.GranuleUR.split("_")[7] }));
    if (!scenes.length) return;
    const latest = {};
    for (const s of scenes) if (!latest[s.track] || s.t > latest[s.track]) latest[s.track] = s.t;
    const now = Date.now();
    const nexts = Object.values(latest).map((t) => { let x = t; while (x < now) x += REPEAT_DAYS * DAY; return x; });
    if (state.river === r) { state.catalog = { newest: scenes[0].t, next: Math.min(...nexts) }; update(); }
  } catch (e) { console.warn("NASA catalog unavailable", e); if (typeof world === "object") world.catalogDown = true; }
}

function viewPadding() {
  const shown = railsShown(), phone = isPhone();
  const side = sideRail(), left = shown ? $("rail-left").getBoundingClientRect().right + 20 : 20;
  const right = shown ? innerWidth - $("rail-right").getBoundingClientRect().left + 20 : side ? innerWidth - side.getBoundingClientRect().left + 20 : 20;
  const wanted = { top: phone && !side ? 190 : 76, bottom: innerHeight - document.querySelector(".dock-stack").getBoundingClientRect().top + 12 };
  const room = innerHeight - 100, fit = Math.min(1, room / (wanted.top + wanted.bottom));
  return { left, right, top: wanted.top * fit, bottom: wanted.bottom * fit };
}

function updateScale() {
  const metersPerPx = 40075016.686 * Math.cos(map.getCenter().lat * Math.PI / 180) / (512 * 2 ** map.getZoom());
  const target = metersPerPx * 60, power = 10 ** Math.floor(Math.log10(target)), nice = [5, 2, 1].map((n) => n * power).find((n) => n <= target) || power;
  $("hud-bar").style.width = `${Math.round(nice / metersPerPx)}px`;
  $("hud-scale").textContent = nice >= 1000 ? `${nice / 1000} km` : `${nice} m`;
}

function showCoord(p, label) {
  const { lng, lat } = p.wrap();
  $("hud-coord").textContent = `${coordText(lat, "N", "S", 3)} ${coordText(lng, "E", "W", 3)}`;
}

function updateGrid() {
  if (!state.mapReady) return;
  const step = GRID_STEPS.find((s) => s * 512 * 2 ** map.getZoom() / 360 <= 300) || 0.01, b = map.getBounds();
  const w = b.getWest(), e = b.getEast(), s = b.getSouth(), n = b.getNorth(), lines = [];
  const dx = e - w, dy = n - s, x0 = Math.floor((w - dx) / step), x1 = Math.ceil((e + dx) / step), y0 = Math.floor(Math.max(-85, s - dy) / step), y1 = Math.ceil(Math.min(85, n + dy) / step);
  for (let i = x0; i <= x1 && x1 - x0 < 400; i++) lines.push([[i * step, y0 * step], [i * step, y1 * step]]);
  for (let i = y0; i <= y1 && y1 - y0 < 400; i++) lines.push([[x0 * step, i * step], [x1 * step, i * step]]);
  const data = { type: "Feature", geometry: { type: "MultiLineString", coordinates: lines }, properties: {} };
  map.getSource("grid").setData(data);
  state.gridStep = step;
  placeGridLabels();
}

function placeGridLabels() {
  const step = state.gridStep;
  if (!step || !state.mapReady || isPhone() || state.flying) return;
  const [a, c] = freeArea(), top = 66, bottom = document.querySelector(".dock-stack").getBoundingClientRect().top - 12, d = step < 0.1 ? 3 : step < 1 ? 2 : 0;
  const leftX = a + 8, topY = 94, b = map.getBounds(), out = [];
  const boxes = ["show-switch", "map-tag"].map((id) => $(id)).filter((el) => !el.hidden).map((el) => el.getBoundingClientRect());
  const clearA = boxes.length ? Math.min(...boxes.map((r) => r.left)) : 0, clearB = boxes.length ? Math.max(...boxes.map((r) => r.right)) : 0;
  for (let i = Math.ceil(b.getWest() / step); i * step <= b.getEast(); i++) {
    const x = map.project([i * step, b.getCenter().lat]).x, lng = ((i * step + 540) % 360) - 180;
    if (x > a + 60 && x < c - 110 && !(x + 60 > clearA && x < clearB)) out.push(`<span style="left:${x + 4}px;top:${topY}px">${coordText(lng, "E", "W", d)}</span>`);
  }
  for (let i = Math.ceil(b.getSouth() / step); i * step <= b.getNorth(); i++) {
    const y = map.project([b.getCenter().lng, i * step]).y;
    if (y > top + 44 && y < bottom) out.push(`<span style="left:${leftX}px;top:${y + 3}px">${coordText(i * step, "N", "S", d)}</span>`);
  }
  $("grid-labels").innerHTML = out.join("");
}

function flyToPlace(lon, lat, zoom) {
  const pad = viewPadding(), ms = document.hidden ? 0 : 1800, token = ++state.flightToken;
  const target = { center: [lon, lat], zoom, offset: [(pad.left - pad.right) / 2, (pad.top - pad.bottom) / 2] };
  clearTimeout(state.flightTimer);
  state.flying = true;
  map.stop();
  state.flying = ms > 0;
  syncLayers();
  const land = () => {
    if (token !== state.flightToken) return;
    clearTimeout(state.flightTimer);
    state.flying = false;
    settleNow();
  };
  map.once("moveend", land);
  map.flyTo({ ...target, duration: ms });
  if (ms > 0) state.flightTimer = setTimeout(() => { if (token === state.flightToken && state.flying) { map.stop(); map.flyTo({ ...target, duration: 0 }); land(); } }, ms + 900);
}

function flyToBounds(bounds, { duration = FLY_MS, labelRoom = 0 } = {}) {
  const ms = document.hidden ? 0 : duration, token = ++state.flightToken;
  const padding = viewPadding();
  padding.left += labelRoom; padding.right += labelRoom;
  map.stop();
  clearTimeout(state.flightTimer);
  state.flying = ms > 0;
  syncLayers();
  const land = () => {
    if (token !== state.flightToken) return;
    clearTimeout(state.flightTimer);
    state.flying = false;
    settleNow();
  };
  map.once("moveend", land);
  map.fitBounds(bounds, { padding, duration: ms, curve: 1.5, maxZoom: 12 });
  if (ms > 0) state.flightTimer = setTimeout(() => { if (token === state.flightToken && state.flying) { map.stop(); map.fitBounds(bounds, { padding, duration: 0 }); land(); } }, ms + 900);
}

const usBounds = () => [Math.min(...rivers.map((r) => r.bounds[0])), Math.min(...rivers.map((r) => r.bounds[1])), Math.max(...rivers.map((r) => r.bounds[2])), Math.max(...rivers.map((r) => r.bounds[3]))];
function overviewBelow(bounds) {
  const cam = map.cameraForBounds(bounds, { padding: viewPadding() });
  return (cam && Number.isFinite(cam.zoom) ? cam.zoom : 8.5) - 1.5;
}

function settleNow() {
  const ov = map.getZoom() < overviewBelow(activeBounds());
  state.overview = ov;
  document.body.classList.toggle("overview", ov);
  document.body.classList.toggle("far-out", map.getZoom() < 4.5);
  state.userMoved = false;
  syncLayers();
  updateGrid();
  if (state.pack) renderTag(currentTime());
  renderFlyBack();
  repaintCanvases();
  map.once("idle", repaintCanvases);
  loadInView();
}

function loadInView() {
  if (!state.mapReady || map.getZoom() < 7) return;
  const b = map.getBounds();
  for (const r of rivers) {
    const [w, s, e, n] = r.bounds, st = storeOf(r);
    if (st.loading || e < b.getWest() || w > b.getEast() || n < b.getSouth() || s > b.getNorth()) continue;
    ensureStore(r).then(scheduleBackground).catch((err) => console.warn(`Couldn't load ${r.id}`, err));
  }
}
const settle = () => { clearTimeout(state.settleTimer); state.settleTimer = setTimeout(settleNow, 120); };

function renderFlyBack() {
  if (state.river) $("fly-back").textContent = `Zoom to the ${shortRiver(state.river)}`;
}

function riverStatus(r) {
  if (state.mode === "history") {
    const f = r.frozen, best = r.passes.filter((p) => p.score !== null && p.score !== undefined).sort((x, y) => y.score - x.score)[0];
    const fair = f && f.csi !== null && f.csi !== undefined;
    if (fair) return { status: `${r.event}, fair test on ${passDate(f.pair)}, match score ${f.csi.toFixed(2)}`, cls: "past", value: f.csi.toFixed(2), sub: `fair test, ${passDate(f.pair)}` };
    if (r.role === "auto") return { status: `${r.event}, added automatically, not tested, and dams and levees weren't checked`, cls: "past", value: "not tested", sub: "added automatically" };
    if (r.role === "sealed") return { status: `${r.event}, the sealed test's river, where NISAR's next passes are scored against a prediction sealed on Nov 15`, cls: "past", value: "sealed", sub: "sealed test" };
    if (f && r.role === "held-out") return { status: `${r.event}, fair test on ${passDate(f.pair)}, too little flooding to score`, cls: "past", value: "not scored", sub: `fair test, ${passDate(f.pair)}` };
    return { status: `${r.event}, helped build GLOWfm${best ? `, match score up to ${best.score.toFixed(2)}` : ""}`, cls: "past", value: best ? `up to ${best.score.toFixed(2)}` : "—", sub: "helped build GLOWfm" };
  }
  let status = "no live data", cls = "grey", value = "no data";
  const levels = state.stripLevels;
  if (levels) {
    const rows = r.gauges.map((g) => { const s = levels[g.id]; if (!s) return null; const ft = s.ft[s.ft.length - 1]; return { above: g.flood_ft ? ft - g.flood_ft : null }; }).filter(Boolean), listed = rows.filter((x) => x.above !== null), n = listed.filter((x) => x.above > 0).length;
    if (!rows.length) { status = "no gauge reporting"; value = "no reading"; }
    else if (n) { status = `${n} of ${listed.length} above flood level`; value = `${n}/${listed.length} above`; cls = "red"; }
    else if (listed.length) { const near = Math.min(...listed.map((x) => -x.above * FT)); status = `${near.toFixed(1)} m below flood level`; value = `${near.toFixed(1)} m below`; cls = near < 0.5 ? "amber" : "green"; }
    else { status = "no listed flood level"; value = "no level"; }
  }
  return { status, cls, value };
}

function renderEvents() {
  const activeId = state.river && state.river.id;
  const row = (r, s) => { const name = shortRiver(r), where = r.title.split(", ")[1] || "";
    return `<button type="button" class="event-row${r.id === activeId ? " on" : ""}" data-river="${r.id}" aria-pressed="${r.id === activeId}" aria-label="${name}, ${where}: ${s.status}"><span class="event-main"><i class="status-dot ${s.cls}"></i><span class="event-name">${name}</span><span class="event-value">${s.value}</span></span><span class="event-sub">${[where, s.sub || r.event].filter(Boolean).join(" · ")}</span></button>`; };
  const statuses = Object.fromEntries(rivers.map((r) => [r.id, riverStatus(r)]));
  const head = state.mode === "history" ? "Match score (0–1)" : "Closest to flood level";
  const focused = document.activeElement && document.activeElement.closest && document.activeElement.closest("#events [data-river]"), focusId = focused && focused.dataset.river;
  $("events").innerHTML = `<div class="events-head" aria-hidden="true"><span>River</span><span>${head}</span></div>` + rivers.map((r) => row(r, statuses[r.id])).join("");
  if (focusId) { const again = $("events").querySelector(`[data-river="${focusId}"]`); if (again) again.focus(); }
  state.pins.forEach((p) => {
    p.el.classList.toggle("is-active", p.id === activeId);
    const dot = p.el.querySelector("i");
    dot.className = `status-dot ${statuses[p.id].cls}`;
    p.el.title = `${p.name}: ${statuses[p.id].status}`;
  });
}

function addPin(id, name, lngLat) {
  const side = PIN_SIDE[id] || "right", el = document.createElement("button");
  el.type = "button"; el.className = `event-pin pin-${side}`; el.tabIndex = -1; el.setAttribute("aria-hidden", "true");
  el.innerHTML = `<i class="status-dot grey"></i><span>${name}</span>`;
  el.addEventListener("click", (e) => { e.stopPropagation(); setFloodTab("tested"); activate(id); });
  new maplibregl.Marker({ element: el, anchor: side === "right" ? "left" : "right" }).setLngLat(lngLat).addTo(map);
  el.removeAttribute("aria-label");
  state.pins.push({ id, name, el });
}

async function loadStrip() {
  const ids = rivers.flatMap((r) => r.gauges.map((g) => g.id));
  try { state.stripLevels = await fetchLevels(ids, "P1D"); } catch (e) { console.warn("USGS unavailable", e); state.stripLevels = null; }
  renderEvents();
  scheduleBackground();
}

async function activate(id, { fly = true, time, mode } = {}) {
  const r = rivers.find((x) => x.id === id) || rivers[0], changed = r !== state.river;
  stopPlay();
  showSel("river");
  if (changed) { state.pack = null; state.series = {}; state.result = null; }
  $("fly-back").textContent = `Zoom to the ${shortRiver(r)}`;
  state.river = r;
  if (mode) state.mode = mode;
  if (changed) { clearPanels(r); $("announce").textContent = `Now showing ${r.title}.`; }
  if (fly) flyToBounds(r.bounds); else syncLayers();
  renderEvents();
  const st = await ensureStore(r);
  if (state.river !== r || state.sel !== "river") return;
  state.pack = st.pack; state.canvas = st.canvas; state.histSeries = st.histSeries; state.grid = st.grid;
  if (time !== undefined) st.i = Math.max(0, st.grid.findIndex((t) => t >= time));
  state.i = st.i;
  timeStrip(r, st);
  raise(r);
  await setMode(state.mode);
  if (state.river === r) loadCatalog(r);
  if (state.river === r && !st.live) prefetchLive(r, st);
}

async function prefetchLive(r, st) {
  try { await loadLive(r, st, false, false); } catch (e) { console.warn("USGS unavailable", e); return; }
  if (state.river !== r || st.stripLiveAt === st.liveAt) return;
  timeStrip(r, st);
  update();
}

function raise(r) {
  if (!state.mapReady) return;
  [`gfm:${r.id}`, `nisar:${r.id}`, `est:${r.id}`].forEach((id) => { if (map.getLayer(id)) map.moveLayer(id); });
}

async function setMode(mode, force = false) {
  stopPlay();
  if (state.mode !== mode) $("facts").style.minHeight = "";
  state.mode = mode;
  paintMode(mode);
  $("time-bar").hidden = false;
  state.liveFailed = false;
  const r = state.river, st = storeOf(r);
  if (mode === "live") {
    try {
      await loadLive(r, st, force);
      if (state.river !== r || state.mode !== "live") return;
      if (st.stripLiveAt !== st.liveAt) timeStrip(r, st);
    } catch (e) {
      console.warn("USGS unavailable", e);
      if (state.river !== r) return;
      state.liveFailed = true;
      state.mode = "history";
      paintMode("history");
      state.series = state.histSeries;
    }
  } else state.series = state.histSeries;
  renderEvents();
  scheduleBackground();
  update();
  drawCharts();
}

function paintMode(mode) {
  $("time-bar").classList.toggle("is-live", mode === "live");
}

async function loadLive(r, st, force, use = true) {
  if (force || !st.live || Date.now() - st.liveAt > LIVE_REUSE) {
    st.live = await fetchLevels(r.gauges.map((g) => g.id), "P8D");
    st.liveAt = Date.now();
  }
  if (!use || state.river !== r) return;
  state.series = st.live;
  state.now = st.liveAt;
  state.updated = st.liveAt;
}

function timeStrip(r, st) {
  const t0 = st.grid[0], t1 = st.grid[st.grid.length - 1];
  const nowAt = st.live ? st.liveAt : null, tailFrom = nowAt === null ? null : Math.max(t1 + HOUR, nowAt - 7 * DAY);
  const rows = r.gauges.filter((g) => g.flood_ft && st.histSeries[g.id]).map((g) => {
    const s = st.histSeries[g.id], l = st.live && st.live[g.id];
    const past = s.times.map((t, k) => [t, (s.ft[k] - g.flood_ft) * FT]).filter(([t, v]) => t >= t0 && t <= t1 && Number.isFinite(v));
    const recent = l && nowAt !== null ? l.times.map((t, k) => [t, (l.ft[k] - g.flood_ft) * FT]).filter(([t, v]) => t >= tailFrom && t <= nowAt && Number.isFinite(v)) : [];
    return past.concat(recent);
  }).filter((x) => x.length);
  const events = r.passes.map((p) => ({ t: Date.parse(p.time), who: "nisar" }));
  const nearest = (t) => st.grid.reduce((best, x, k) => (Math.abs(x - t) < Math.abs(st.grid[best] - t) ? k : best), 0);
  const gapDays = nowAt === null ? 0 : Math.round((tailFrom - t1) / DAY);
  const tail = nowAt === null ? null : { t0: tailFrom, t1: nowAt, gap: gapDays >= 1 ? `${gapDays} d` : "" };
  const box = $("t-strip");
  state.strip = passStrip(box, { t0, t1, rows: rows.length ? rows : [[[t0, 0], [t1, 0]]], zero: rows.length > 0, events, tail,
    label: "Time in this flood, then now. The marks are NISAR passes. Drag, or use the arrow keys.",
    scrub: (t) => { stopPlay(); if (t > t1) goNow(); else goTo(nearest(t)); },
    onKey: (dir) => { stopPlay(); jumpPass(dir); } });
  st.stripLiveAt = nowAt;
  box.setAttribute("aria-valuemin", "0");
  box.setAttribute("aria-valuemax", String(st.grid.length));
}
function goTo(i) {
  state.i = Math.max(0, Math.min(state.grid.length - 1, i));
  if (state.mode !== "history") setMode("history"); else update();
}
function goNow() { if (state.mode !== "live") setMode("live"); }
const PLAY_MS = 700;
function nextDay() {
  const k = state.grid.findIndex((x) => x >= currentTime() + DAY);
  if (k >= 0) { state.i = k; update(); return; }
  if (state.i < state.grid.length - 1) { state.i = state.grid.length - 1; update(); return; }
  stopPlay();
  goNow();
}
function setPlayIcon(playing) {
  const b = $("t-play");
  b.innerHTML = playing ? '<svg viewBox="0 0 16 16" aria-hidden="true"><rect x="3.5" y="3" width="3" height="10" rx="0.6"/><rect x="9.5" y="3" width="3" height="10" rx="0.6"/></svg>'
    : '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 2.8v10.4a.6.6 0 0 0 .9.5l8.2-5.2a.6.6 0 0 0 0-1L5.4 2.3a.6.6 0 0 0-.9.5z"/></svg>';
  b.setAttribute("aria-label", playing ? "Pause" : "Play, one day at a time");
  b.title = playing ? "Pause" : "Play, one day at a time";
}
async function startPlay() {
  if (state.mode === "live" || state.i >= state.grid.length - 1) { state.i = 0; if (state.mode !== "history") await setMode("history"); else update(); }
  setPlayIcon(true);
  state.timer = setInterval(nextDay, PLAY_MS);
}
function stopPlay() { clearInterval(state.timer); state.timer = null; setPlayIcon(false); }
function jumpPass(dir) {
  const t = state.mode === "live" ? Infinity : currentTime(), times = state.river.passes.map((p) => Date.parse(p.time));
  const target = dir > 0 ? times.find((x) => x > t + 60000) : [...times].reverse().find((x) => x < t - 60000);
  if (target === undefined) { if (dir > 0) goNow(); return; }
  goTo(state.grid.findIndex((x) => x >= target));
}

function syncUrl() {
  if (WANT_FLOOD && !world.opened) return;
  if (state.sel === "pick") return atlasUrl();
  const q = new URLSearchParams({ river: state.river.id, mode: state.mode });
  if (state.mode === "history") q.set("t", new Date(state.grid[state.i]).toISOString().slice(0, 16));
  if (state.show !== "both") q.set("show", state.show);
  if (state.rise) q.set("rise", String(state.rise));
  if (!atlas.enabled) q.set("blind", "off");
  history.replaceState(null, "", `?${q}`);
}

function downloadCsv() {
  const t = new Date(currentTime()).toISOString();
  const lines = [["river", "mode", "time_utc", "gauge_id", "gauge", "level_m", "flood_level_m", "water_surface_navd88_m", "what_if_rise_m", "estimated_flooding_ha"].join(",")];
  for (const x of state.rows) lines.push([state.river.id, state.mode, t, x.g.id, `"${x.g.name}"`, x.stage_m === null ? "" : x.stage_m.toFixed(3), x.flood_m === null ? "" : x.flood_m.toFixed(3), x.ft === null ? "" : (waterSurface(x.g, x.ft) + state.rise).toFixed(3), state.rise, state.result ? state.result.ha : ""].join(","));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
  a.download = `glowfm-${state.river.id}-${t.slice(0, 13)}.csv`;
  a.click();
}

function setPanel(name) {
  state.panel = state.panel === name ? null : name;
  const body = document.body, wasOpen = body.classList.contains("drawer-open"), nowOpen = DRAWER_PANELS.includes(state.panel);
  body.classList.toggle("drawer-open", nowOpen);
  if (wasOpen !== nowOpen && !state.overview && state.mapReady && state.sel === "river") flyToBounds(activeBounds(), { duration: 500 });
  if (nowOpen && !wasOpen) { state.panelOpener = document.activeElement; $("drawer").focus({ preventScroll: true }); }
  if (wasOpen && !nowOpen && state.panelOpener && state.panelOpener.isConnected) state.panelOpener.focus({ preventScroll: true });
  const sheetWas = body.dataset.sheet || "";
  body.dataset.sheet = state.panel === "left" || state.panel === "right" ? state.panel : "";
  if (isTablet() && !!sheetWas !== !!body.dataset.sheet && !state.overview && state.mapReady && state.sel === "river") flyToBounds(activeBounds(), { duration: 500 });
  DRAWER_PANELS.forEach((p) => { $(`pane-${p}`).hidden = state.panel !== p; });
  document.querySelectorAll("button[data-panel]").forEach((b) => { const on = b.dataset.panel === state.panel; b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); });
  if (state.panel === "graphs") {
    const status = $("graphs-status");
    if (!plotsReady) { status.hidden = false; status.textContent = "Loading graphs…"; }
    loadPlotly().then(() => { plotsReady = true; status.hidden = true; drawCharts(); }).catch(() => { status.hidden = false; status.textContent = "The graphs couldn't load. Check your connection and try again. The gauge table still works."; });
  }
}

function wireControls() {
  if (isPhone()) $("layers-box").open = false;
  $("rise").addEventListener("input", (e) => {
    state.rise = Number(e.target.value); $("rise-out").textContent = `+${state.rise} m`;
    const f = $("facts"), before = f.offsetHeight;
    update(); scheduleBackground();
    if (f.offsetHeight < before) f.style.minHeight = `${before}px`;
  });
  $("show-switch").addEventListener("click", (e) => { const b = e.target.closest("[data-show]"); if (b) setShow(b.dataset.show); });
  $("share").addEventListener("click", async () => {
    let said;
    try { await navigator.clipboard.writeText(location.href); said = "Link copied"; } catch { said = "Couldn't copy the link"; }
    $("share").textContent = said; $("announce").textContent = said;
    setTimeout(() => { $("share").textContent = "Copy link to this view"; $("bar-more").open = false; }, 1200);
  });
  $("csv").addEventListener("click", downloadCsv);
  $("t-play").addEventListener("click", () => { if (state.timer) stopPlay(); else startPlay(); });
  $("t-prev").addEventListener("click", () => { stopPlay(); jumpPass(-1); });
  $("t-next").addEventListener("click", () => { stopPlay(); jumpPass(1); });
  $("events").addEventListener("click", (e) => { const b = e.target.closest("[data-river]"); if (!b) return; activate(b.dataset.river); if (isPhone() && !isTablet()) setPanel("left"); });
  $("fly-back").addEventListener("click", () => flyToBounds(activeBounds()));
  $("zoom-in").addEventListener("click", () => map.zoomIn());
  $("zoom-out").addEventListener("click", () => map.zoomOut());
  document.querySelectorAll("button[data-panel]").forEach((b) => b.addEventListener("click", () => setPanel(b.dataset.panel)));
  $("bar-more").addEventListener("click", (e) => { if (e.target.closest(".bar-menu a, .bar-menu button") && !e.target.closest("#share")) $("bar-more").open = false; });
  document.addEventListener("click", (e) => { if (!e.target.closest("#bar-more")) $("bar-more").open = false; });
  $("drawer-close").addEventListener("click", () => setPanel(state.panel));
  addEventListener("keydown", (e) => { if (e.key === "Escape" && state.panel) setPanel(state.panel); });
  addEventListener("resize", settle);
  const layerRow = (l) => `<label><input type="checkbox" id="lyr-${l.key}" ${state.layers[l.key] ? "checked" : ""}><span class="swatch${l.key === "gauges" ? " diamond" : l.key === "world" ? " dot" : ""}" style="background:${l.color}"></span>${l.label}</label>`;
  $("dash-layers").innerHTML = LAYER_ROWS.filter((l) => !l.after).map(layerRow).join("");
  $("dash-layers-after").innerHTML = LAYER_ROWS.filter((l) => l.after).map(layerRow).join("");
  LAYER_ROWS.forEach((l) => $(`lyr-${l.key}`).addEventListener("change", (e) => { state.layers[l.key] = e.target.checked; update(); scheduleBackground(); }));
}

function setShow(show) {
  state.show = SHOWS.includes(show) ? show : "both";
  document.querySelectorAll("#show-switch [data-show]").forEach((b) => { const on = b.dataset.show === state.show; b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); });
  update();
  scheduleBackground();
}

function setupMap(startBounds) {
  return new Promise((resolve) => {
    const startPadding = viewPadding();
    if (!new URLSearchParams(location.search).get("river") && innerWidth - startPadding.left - startPadding.right > 520) { startPadding.left += 110; startPadding.right += 110; }
    const opts = (container) => ({ container, style: STYLE, bounds: startBounds, fitBoundsOptions: { padding: startPadding }, attributionControl: { compact: true }, dragRotate: false, pitchWithRotate: false, touchPitch: false });
    map = new maplibregl.Map(opts("dash-map"));
    map.touchZoomRotate.disableRotation();
    map.getCanvas().setAttribute("aria-label", "Map of flood events. The arrow keys pan, and plus and minus zoom. The flood events list moves between floods.");
    const addGrid = (m) => {
      m.addSource("grid", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      m.addLayer({ id: "grid", type: "line", source: "grid", paint: { "line-color": "#e8eef2", "line-opacity": 0.16, "line-width": 1 } });
    };
    const add = (m, r, kinds) => kinds.forEach((kind) => {
      const id = `${kind}:${r.id}`, pass = passFor(r);
      storeOf(r).radarUrl = pass.layer;
      m.addSource(id, { type: "image", url: kind === "nisar" ? `data/${pass.layer}` : BLANK, coordinates: r.corners });
      m.addLayer({ id, type: "raster", source: id, paint: { "raster-resampling": "nearest", "raster-fade-duration": 0 }, layout: { visibility: "none" } });
    });
    map.once("style.load", () => {
      addAtlasLayer(map); addGrid(map); rivers.forEach((r) => add(map, r, ["gfm", "nisar"])); addAtlasPick(map); addWorldLayer(map);
      state.mapReady = true;
      const credits = document.querySelector("#dash-map .maplibregl-ctrl-attrib");
      if (credits) {
        let wanted = false;
        credits.addEventListener("click", () => setTimeout(() => { wanted = credits.classList.contains("maplibregl-compact-show"); }));
        map.on("dragstart", () => { wanted = false; });
        const fold = () => { if (!wanted && credits.classList.contains("maplibregl-compact-show")) { credits.classList.remove("maplibregl-compact-show"); credits.removeAttribute("open"); } };
        fold(); map.on("idle", fold);
      }
      rivers.forEach((r) => { const st = state.stores[r.id]; if (st && st.pack) attachCanvas(r, st); });
      rivers.forEach((r) => addPin(r.id, shortRiver(r), [(r.bounds[0] + r.bounds[2]) / 2, (r.bounds[1] + r.bounds[3]) / 2]));
      renderEvents();
      settleNow();
      if (state.pack) { raise(state.river); update(); }
      scheduleBackground();
      resolve();
    });
    map.on("error", (e) => { if (!e.error || e.error.name !== "AbortError") console.error(e.error || e); });
    map.on("click", onMapClick);
    map.on("movestart", (e) => { if (e.originalEvent) state.userMoved = true; });
    map.on("moveend", () => { if (!state.flying) settle(); });
    map.on("mousemove", (e) => { state.cursorOn = true; showCoord(e.lngLat, "Cursor"); });
    map.getCanvasContainer().addEventListener("mouseleave", () => { state.cursorOn = false; showCoord(map.getCenter(), "Center"); });
    map.on("move", () => { updateScale(); if (!state.cursorOn || state.flying) showCoord(map.getCenter(), "Center"); if (!state.flying) placeGridLabels(); });
    updateScale();
    showCoord(map.getCenter(), "Center");
  });
}

(async function start() {
  const { rivers: list } = await fetch("data/dashboard/rivers.json").then((r) => r.json());
  rivers = list;
  loadFloodRain().then((x) => { state.rain = x; if (state.river && state.pack) update(); });
  rivers.forEach((r) => r.gauges.forEach((g) => { g.name = tidyName(g.name); }));
  const q = new URLSearchParams(location.search), wanted = q.get("river");
  state.mode = q.get("mode") === "live" ? "live" : "history";
  state.rise = Math.max(0, Math.min(5, Number(q.get("rise")) || 0));
  $("rise").value = String(state.rise); $("rise-out").textContent = `+${state.rise} m`;
  state.river = rivers.find((r) => r.id === wanted) || rivers[0];
  wireControls();
  wireAtlas();
  renderEvents();
  clearPanels(state.river);
  const first = state.river, deepLink = !!wanted, t = q.get("t");
  if (isTablet()) setPanel(deepLink ? "right" : "left");
  setShow(q.get("show"));
  const atlasLink = q.get("view") === "atlas" || q.get("view") === "place", at = (q.get("at") || "").split(",").map(Number);
  if (q.get("blind") === "off" && !atlasLink) atlasSetEnabled(false);
  const opening = setupMap(atlasLink ? ATLAS_WORLD : deepLink ? first.bounds : usBounds());
  wireWorld();
  opening.then(() => setTimeout(loadWorld, WANT_FLOOD ? 0 : 1500));
  loadStrip();
  await activate(first.id, { fly: false, ...(t ? { time: Date.parse(t.length === 13 ? `${t}:00:00Z` : `${t}:00Z`) } : {}) });
  await opening;
  await loadAtlas();
  renderAtlas();
  if (atlasLink) {
    setFloodTab("blind");
    if (q.get("country")) atlasPickCountry(q.get("country"));
    else if (at.length === 2 && at.every(Number.isFinite)) { map.jumpTo({ center: [at[1], at[0]], zoom: 5.6 }); atlasPickAt(at[0], at[1], q.get("name") || undefined, q.get("short") || undefined); }
  }
  else if (!deepLink && !WANT_FLOOD) setTimeout(() => { if (state.river === first && state.sel === "river") flyToBounds(first.bounds); }, 500);
  loadInView();
  scheduleBackground();
  setInterval(() => { if (state.mode === "live" && !document.hidden) { loadStrip(); setMode("live", true); } }, 5 * 60 * 1000);
})();
