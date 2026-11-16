
const LANTERN_ACTS = [
  { key: "orbit", weight: 1.0, label: "Orbit" },
  { key: "scale", weight: 1.0, label: "Bigger than Greenland" },
  { key: "people", weight: 0.9, label: "Who lives beside it" },
  { key: "blind", weight: 0.9, label: "The blind spot" },
  { key: "river", weight: 1.8, label: "The river floods" },
  { key: "pixel", weight: 0.9, label: "One pixel" },
  { key: "tree", weight: 1.1, label: "One tree" },
];
const L = { act: -1, t: 0, lineKey: "", visible: false, last: 0, data: null, pour: null, pick: null, map: null, mapReady: null, river: null, strip: null, mapFrom: null };
const lanternReduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const ease = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
const lerp = (a, b, t) => a + (b - a) * t;
const clamp01 = (x) => Math.max(0, Math.min(1, x));
const small = () => innerWidth < 760;

function lanternCopy(kicker, number, unit, line, extra = "") {
  $("lantern-kicker").textContent = kicker;
  $("lantern-number").textContent = number;
  $("lantern-unit").textContent = unit;
  if (L.lineKey !== line) { $("lantern-line").textContent = line; L.lineKey = line; }
  if ($("lantern-extra").dataset.key !== extra) { $("lantern-extra").innerHTML = extra; $("lantern-extra").dataset.key = extra; lanternWireExtra(); }
}

function lanternScale(text, fov) {
  $("lantern-pow").textContent = text;
  $("lantern-fov").textContent = fov;
}

const km = (x) => (x >= 100 ? `${Math.round(x).toLocaleString("en-US")} km` : x >= 1 ? `${x.toFixed(1)} km` : `${Math.round(x * 1000)} m`);

const LANTERN_GLIDE_MS = 400;
function lanternProgress(dt = 0) {
  const sec = $("journey"), r = sec.getBoundingClientRect(), stageH = $("lantern-stage").offsetHeight;
  const raw = clamp01(-r.top / Math.max(1, r.height - stageH));
  if (L.sp == null || lanternReduced() || Math.abs(raw - L.sp) > 0.2) L.sp = raw;
  else { L.sp += (raw - L.sp) * (1 - Math.exp(-dt / LANTERN_GLIDE_MS)); if (Math.abs(raw - L.sp) < 2e-5) L.sp = raw; }
  const p = L.sp;
  const total = LANTERN_ACTS.reduce((s, a) => s + a.weight, 0);
  let acc = 0;
  for (let i = 0; i < LANTERN_ACTS.length; i++) {
    const w = LANTERN_ACTS[i].weight / total;
    if (p <= acc + w || i === LANTERN_ACTS.length - 1) return { act: i, t: clamp01((p - acc) / w), p };
    acc += w;
  }
  return { act: 0, t: 0, p };
}

function lanternJump(i) {
  const sec = $("journey"), total = LANTERN_ACTS.reduce((s, a) => s + a.weight, 0);
  const before = LANTERN_ACTS.slice(0, i).reduce((s, a) => s + a.weight, 0) / total;
  const span = sec.offsetHeight - $("lantern-stage").offsetHeight;
  scrollTo({ top: sec.getBoundingClientRect().top + scrollY + before * span + 4, behavior: lanternReduced() ? "auto" : "smooth" });
}

function baseView() {
  const w = globe.w, h = globe.h;
  return small() ? { R: Math.min(w * 0.46, h * 0.3), cx: w * 0.5, cy: h * 0.34 } : { R: Math.min(h * 0.42, w * 0.3), cx: w * 0.64, cy: h * 0.5 };
}

function actOrbit(t, dt) {
  const b = baseView(), d = L.data;
  Object.assign(globe.view, { lon: lerp(-105, -25, t), lat: 10, ...b });
  globeAdvance(dt, !lanternReduced());
  globeDraw({ points: clamp01(t * 6 + 0.25), coast: 0.9, people: 0, swath: true, dim: 0 });
  const shown = lanternReduced() ? 1 : ease(clamp01(t / 0.45));
  lanternCopy("10⁷ m · The night side of the Earth", (d.treeKm2 / 1e6 * shown).toFixed(1), "million km² of river floodplain under trees",
    "Each point of light is floodplain forest, drawn from our worldwide atlas: ground where a flood can hide from today's flood maps. The beam is NISAR's 240 km radar swath.");
  lanternScale("10⁷ m", `↔ ${km(Math.min(2 * EARTH_KM, (globe.w / globe.view.R) * EARTH_KM))}`);
}

function buildPour() {
  const d = L.data, w = globe.w, h = globe.h, ring = d.coast.greenland;
  const raw = ring.map(([x, y]) => equalArea(x, y, -42, 72, 1));
  const xs = raw.map((p) => p[0]), ys = raw.map((p) => p[1]);
  const bw = Math.max(...xs) - Math.min(...xs), bh = Math.max(...ys) - Math.min(...ys);
  const s = small() ? Math.min((w * 0.62) / bw, (h * 0.34) / bh) : Math.min((w * 0.3) / bw, (h * 0.62) / bh);
  const ox = small() ? w * 0.5 : w * 0.53, oy = small() ? h * 0.36 : h * 0.5;
  const mx = (Math.max(...xs) + Math.min(...xs)) / 2, my = (Math.max(...ys) + Math.min(...ys)) / 2;
  const poly = raw.map(([x, y]) => [ox + (x - mx) * s, oy + (y - my) * s]);
  let area = 0;
  for (let i = 0; i < poly.length; i++) { const [x1, y1] = poly[i], [x2, y2] = poly[(i + 1) % poly.length]; area += x1 * y2 - x2 * y1; }
  const gap = Math.max(3.2, Math.sqrt(Math.abs(area) / 2 / 1100));
  const inside = (x, y) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c; } return c; };
  const minX = Math.min(...poly.map((p) => p[0])) - gap * 8, maxX = Math.max(...poly.map((p) => p[0])) + gap * 8;
  const minY = Math.min(...poly.map((p) => p[1])) - gap * 8, maxY = Math.max(...poly.map((p) => p[1])) + gap * 8;
  const ins = [], outs = [];
  for (let y = minY; y <= maxY; y += gap) for (let x = minX; x <= maxX; x += gap) (inside(x, y) ? ins : outs).push([x, y]);
  ins.sort((a, b) => b[1] - a[1]);
  const near = (x, y) => Math.min(...poly.filter((_, k) => k % 3 === 0).map(([px, py]) => (px - x) ** 2 + (py - y) ** 2));
  const unitKm2 = d.coast.greenland_km2 / ins.length, count = Math.round(d.treeKm2 / unitKm2);
  const spill = outs.map((p) => [p, near(p[0], p[1])]).sort((a, b) => a[1] - b[1]).slice(0, Math.max(0, count - ins.length)).map((x) => x[0]);
  const slots = [...ins, ...spill].slice(0, count);
  const P = globe.pts, cum = new Float64Array(P.n);
  let acc = 0;
  for (let i = 0; i < P.n; i++) { acc += P.km2[i]; cum[i] = acc; }
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const grains = slots.map((slot, k) => {
    const want = rand() * acc;
    let lo = 0, hi = P.n - 1;
    while (lo < hi) { const m = (lo + hi) >> 1; if (cum[m] < want) lo = m + 1; else hi = m; }
    return { from: lo, to: slot, delay: k / slots.length };
  });
  L.pour = { poly, grains, unitKm2, inside: ins.length, count, w, h };
}

function actScale(t, dt) {
  const d = L.data, b = baseView();
  if (!L.pour || L.pour.w !== globe.w || L.pour.h !== globe.h) buildPour();
  const move = ease(clamp01(t / 0.25));
  const end = small() ? { R: b.R * 0.55, cx: globe.w * 0.5, cy: globe.h * 0.82 } : { R: b.R * 0.58, cx: globe.w * 0.86, cy: globe.h * 0.5 };
  Object.assign(globe.view, { lon: -25, lat: 10, R: lerp(b.R, end.R, move), cx: lerp(b.cx, end.cx, move), cy: lerp(b.cy, end.cy, move) });
  globeAdvance(dt, !lanternReduced());
  globeDraw({ points: 1, coast: 0.6, people: 0, swath: false, dim: 0.45 });
  const ctx = globe.ctx, pour = L.pour, out = [0, 0, 0], P = globe.pts;
  ctx.save();
  ctx.strokeStyle = "rgba(235, 245, 250, .55)"; ctx.lineWidth = 1.2; ctx.setLineDash([4, 4]);
  ctx.beginPath(); pour.poly.forEach(([x, y], k) => (k ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.stroke();
  ctx.setLineDash([]);
  const top = Math.min(...pour.poly.map((p) => p[1]));
  ctx.fillStyle = "rgba(235, 245, 250, .8)"; ctx.font = "600 13px 'IBM Plex Sans', system-ui, sans-serif"; ctx.textAlign = "center";
  ctx.fillText(`Greenland · ${(d.coast.greenland_km2 / 1e6).toFixed(2)} million km²`, (Math.min(...pour.poly.map((p) => p[0])) + Math.max(...pour.poly.map((p) => p[0]))) / 2, top - 14);
  ctx.restore();
  ctx.globalCompositeOperation = "lighter";
  let landed = 0;
  const go = lanternReduced() ? (t > 0.15 ? 1 : 0) : null;
  for (let k = 0; k < pour.grains.length; k++) {
    const g = pour.grains[k], q = go ?? ease(clamp01((t - 0.18 - g.delay * 0.55) / 0.22));
    if (q <= 0) continue;
    if (q >= 1) landed++;
    let sx = g.to[0], sy = g.to[1];
    if (q < 1 && globeProject(P.lon[g.from], P.sinLat[g.from], P.cosLat[g.from], out)) { sx = out[0]; sy = out[1]; }
    const x = lerp(sx, g.to[0], q), y = lerp(sy, g.to[1], q) - Math.sin(Math.PI * q) * 70;
    const over = k >= pour.inside;
    ctx.fillStyle = over ? "rgba(255, 255, 255, .95)" : "rgba(79, 220, 176, .9)";
    ctx.fillRect(x - 1.4, y - 1.4, 2.8, 2.8);
  }
  ctx.globalCompositeOperation = "source-over";
  const pct = Math.round((landed * pour.unitKm2 / d.coast.greenland_km2) * 100);
  lanternCopy("Scale · the same area, poured into one place", `${pct}%`, "of Greenland",
    `Pour every point together and it overfills Greenland: ${(d.treeKm2 / 1e6).toFixed(2)} million km² against ${(d.coast.greenland_km2 / 1e6).toFixed(2)} million. Each grain is ${Math.round(pour.unitKm2).toLocaleString("en-US")} km²; the white ones spill past the edge.`);
  lanternScale("10⁷ m", "equal-area view");
}

function actPeople(t, dt) {
  const d = L.data, b = baseView();
  const back = ease(clamp01(t / 0.15));
  const prev = small() ? { R: b.R * 0.55, cx: globe.w * 0.5, cy: globe.h * 0.82 } : { R: b.R * 0.58, cx: globe.w * 0.86, cy: globe.h * 0.5 };
  const lon = lerp(-25, 160, ease(t));
  Object.assign(globe.view, { lon, lat: 8, R: lerp(prev.R, b.R, back), cx: lerp(prev.cx, b.cx, back), cy: lerp(prev.cy, b.cy, back) });
  globeAdvance(dt, !lanternReduced());
  const T = globe.people;
  if (!L.pick || L.pick.length !== T.n) L.pick = new Float32Array(T.n);
  let sum = 0;
  const all = t > 0.94 || lanternReduced();
  let lit = -1;
  for (let i = 0; i < T.n; i++) {
    const want = all || T.lon[i] / DEG <= lon + 35 ? 1 : 0;
    if (want && L.pick[i] === 0) lit = i;
    L.pick[i] = want ? Math.min(1, L.pick[i] + dt / 650) : 0;
    if (want) sum += T.pop[i];
  }
  if (lit >= 0 && typeof ambLight === "function") ambLight((T.lon[lit] / DEG - lon + 35) / 60);
  globeDraw({ points: 0.75, coast: 0.8, people: 1, swath: true, dim: 0.35, pick: L.pick });
  lanternCopy("People · who lives beside it", (Math.min(sum, d.peopleTotal) / 1e6).toFixed(1), "million people",
    `They live in about ${(Math.round(d.summary.towns.high / 100) * 100).toLocaleString("en-US")} towns beside large forested floodplains. Each light is a town, or a few close neighbors together, sized by population. It counts who lives next to the blind spot, not who is at risk.`);
  lanternScale("10⁷ m", `↔ ${km(Math.min(2 * EARTH_KM, (globe.w / globe.view.R) * EARTH_KM))}`);
}

function actBlind(t, dt) {
  const d = L.data, b = baseView();
  const fly = ease(clamp01(t / 0.45));
  const lonFrom = 160, lonTo = 276;
  const R = lerp(b.R, b.R * (small() ? 4.2 : 3.6), fly);
  Object.assign(globe.view, { lon: ((lerp(lonFrom, lonTo, fly) + 540) % 360) - 180, lat: lerp(8, 31, fly), R, cx: lerp(b.cx, small() ? globe.w * 0.5 : globe.w * 0.66, fly), cy: lerp(b.cy, small() ? globe.h * 0.36 : globe.h * 0.5, fly) });
  globeAdvance(dt, !lanternReduced());
  globeDraw({ points: 1, coast: 1, people: 0.5, swath: false, dim: 0.3 });
  const ctx = globe.ctx, share = d.summary.check.gfm_excludes_share_under_trees, covered = Math.round(share * 100);
  const gap = small() ? 15 : Math.min(28, globe.h * 0.036), x0 = small() ? globe.w / 2 - 4.5 * gap : globe.w * 0.1, y0 = small() ? globe.h * 0.62 : globe.h * 0.5 - 4.5 * gap;
  const veil = lanternReduced() ? 1 : ease(clamp01((t - 0.4) / 0.45));
  const show = ease(clamp01((t - 0.3) / 0.15));
  ctx.save();
  ctx.globalAlpha = show;
  for (let k = 0; k < 100; k++) {
    const x = x0 + (k % 10) * gap, y = y0 + Math.floor(k / 10) * gap, hidden = k < covered && k / covered < veil;
    if (hidden) {
      ctx.fillStyle = "rgba(120, 132, 140, .55)"; ctx.beginPath(); ctx.arc(x, y, gap * 0.42, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = "rgba(170, 180, 186, .9)"; ctx.beginPath(); ctx.arc(x, y, gap * 0.18, 0, 2 * Math.PI); ctx.fill();
    } else {
      const g = ctx.createRadialGradient(x, y, 0, x, y, gap * 0.5);
      g.addColorStop(0, "rgba(190, 255, 232, 1)"); g.addColorStop(0.35, "rgba(79, 220, 176, .8)"); g.addColorStop(1, "rgba(79, 220, 176, 0)");
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, gap * 0.5, 0, 2 * Math.PI); ctx.fill();
    }
  }
  ctx.restore();
  const n = Math.round(covered * veil);
  lanternCopy("10⁶ m · The blind spot", `${n}%`, "hidden from the official flood map",
    `Each dot is 1% of the floodplain forest in the ${d.summary.check.areas.length} areas we checked. The global flood map, Copernicus GFM, says up front that it can't map dense forest, and its own mask covers ${pct(share, 0)} of this ground.`);
  lanternScale("10⁶ m", `↔ ${km((globe.w / globe.view.R) * EARTH_KM)}`);
}

function lanternMapEnsure() {
  if (L.mapReady) return L.mapReady;
  const d = L.data, hero = d.hero;
  L.mapReady = (async () => {
    const [rivers, gaugesRaw, buffer] = await Promise.all([fetch("data/dashboard/rivers.json").then((r) => r.json()), fetch("data/dashboard/satilla_gauges.json").then((r) => r.json()), fetch("data/dashboard/satilla.bin").then((r) => r.arrayBuffer())]);
    const river = rivers.rivers.find((r) => r.id === hero.site), pack = packFromBuffer(river.grid, buffer);
    const series = Object.fromEntries(gaugesRaw.map((g) => [g.id.replace("USGS-", ""), { times: g.times.map((x) => Date.parse(`${x}Z`)), ft: g.stage_ft }]));
    const t0 = Math.max(...Object.values(series).map((s) => s.times[0])), t1 = Math.min(...Object.values(series).map((s) => s.times[s.times.length - 1]));
    const hours = [];
    for (let t = Math.ceil(t0 / 36e5) * 36e5; t <= t1; t += 36e5) hours.push(t);
    const canvas = document.createElement("canvas");
    canvas.width = pack.meta.cols; canvas.height = pack.meta.rows;
    L.river = { river, pack, series, hours, canvas, cache: new Map(), hour: -1, shown: null };
    const m = new maplibregl.Map({ container: "lantern-map", style: STYLE, bounds: hero.bounds, fitBoundsOptions: { padding: small() ? 10 : 40 }, attributionControl: { compact: true }, interactive: false });
    L.map = m;
    await new Promise((ok) => m.on("load", ok));
    addOverlay(m, "l-photo", `data/${hero.site}/${hero.pass}/${HERO_PHOTO.file}`, HERO_PHOTO.corners, true, 0.55);
    m.setPaintProperty("l-photo", "raster-resampling", "linear");
    m.addSource("l-est", { type: "canvas", canvas, coordinates: pack.meta.quad, animate: false });
    m.addLayer({ id: "l-est", type: "raster", source: "l-est", paint: { "raster-resampling": "nearest", "raster-fade-duration": 0, "raster-opacity": 0.9 } });
    addOverlay(m, "l-nisar", `data/${hero.site}/${hero.pass}/${hero.layers.nisar}`, hero.corners, true, 0);
    hero.gauges.forEach((g) => gaugeMarker(m, g));
    m.on("move", lanternPlacePixel);
    L.mapFrom = { center: m.getCenter(), zoom: m.getZoom() };
    lanternStrip();
  })();
  return L.mapReady;
}

const mapWidthKm = () => { const b = L.map.getBounds(); return (b.getEast() - b.getWest()) * 111.32 * Math.cos(b.getCenter().lat * DEG); };

function stageAtTime(s, t) {
  const { times, ft } = s;
  if (t <= times[0]) return ft[0];
  if (t >= times[times.length - 1]) return ft[ft.length - 1];
  let lo = 0, hi = times.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (times[m] <= t) lo = m; else hi = m; }
  return ft[lo] + (ft[hi] - ft[lo]) * (t - times[lo]) / (times[hi] - times[lo]);
}

function riverAt(k) {
  const R = L.river;
  if (R.cache.has(k)) return R.cache.get(k);
  const t = R.hours[k];
  const pts = R.river.gauges.map((g) => ({ chain: g.chain_m, wse: waterSurface(g, stageAtTime(R.series[g.id], t)) }));
  const res = estimateFlood(R.pack, pts, 0);
  const wet = R.pack.wet.slice(), depth = R.pack.depth.slice();
  const out = { ha: res.ha, wet, depth };
  R.cache.set(k, out);
  return out;
}

function riverPaint(k) {
  const R = L.river;
  if (R.hour === k) return R.shown;
  R.hour = k;
  const got = riverAt(k), { pack, canvas } = R, ctx = canvas.getContext("2d"), img = ctx.createImageData(pack.meta.cols, pack.meta.rows), px = img.data;
  for (let i = 0; i < pack.n; i++) {
    if (!got.wet[i]) continue;
    const p = pack.idx[i] * 4, dd = Math.min(1, Math.max(0, (got.depth[i] - 0.5) / 2.5));
    px[p] = 60 * (1 - dd); px[p + 1] = 215 - 90 * dd; px[p + 2] = 235 - 30 * dd; px[p + 3] = 225;
  }
  ctx.putImageData(img, 0, 0);
  const src = L.map.getSource("l-est");
  if (src) { src.play(); src.pause(); }
  R.shown = got;
  return got;
}

function lanternStrip() {
  const d = L.data, w = d.watching, R = L.river;
  const t0 = R.hours[0], t1 = R.hours[R.hours.length - 1];
  const rows = w.gauges.map((g) => { const sr = R.series[g.id]; return sr ? sr.times.map((tt, i) => [tt, (sr.ft[i] - g.flood_ft) * 0.3048]).filter(([tt, v]) => tt >= t0 && tt <= t1 && Number.isFinite(v)) : []; });
  const avg = R.hours.map((t) => mean(w.gauges.filter((g) => R.series[g.id]).map((g) => (stageAtTime(R.series[g.id], t) - g.flood_ft) * 0.3048)));
  L.riverRange = [Math.min(...avg), Math.max(...avg)];
  L.riverAvg = avg;
  L.strip = passStrip($("lantern-strip"), { t0, t1, rows, zero: true, events: L.events,
    key: [["ls-k-gauge", `River level at ${rows.length} gauges`], ["ls-k-flood", "Flood level"], ["ls-k-nisar", "NISAR passes"], ["ls-k-gfm", "Official map's satellite"]] });
}

function actRiver(t, dt) {
  const d = L.data, fade = ease(clamp01(t / 0.12));
  if (fade < 1) {
    const b = baseView();
    Object.assign(globe.view, { lon: -82.3, lat: 31.25, R: b.R * 3.6 * Math.pow(60, fade), cx: small() ? globe.w * 0.5 : globe.w * 0.55, cy: globe.h * 0.45 });
    globeDraw({ points: 1 - fade, coast: 1 - fade, people: 0, swath: false, dim: 0.3 });
  }
  $("lantern-canvas").style.opacity = $("lantern-glow").style.opacity = String(1 - fade);
  $("lantern-map").style.opacity = String(fade);
  $("lantern-strip-wrap").style.opacity = String(ease(clamp01((t - 0.06) / 0.08)));
  lanternMapEnsure();
  if (!L.river || !L.map || !L.map.getSource("l-est")) {
    lanternCopy("10⁵ m · Satilla River, Georgia", "…", "loading the river's gauges", "Falling toward a real flood.");
    return;
  }
  if (Math.abs(L.map.getZoom() - L.mapFrom.zoom) > 0.01) L.map.jumpTo({ center: L.mapFrom.center, zoom: L.mapFrom.zoom });
  L.map.setPaintProperty("l-photo", "raster-opacity", 0.55);
  $("lantern-stage").classList.remove("l-pixel-on");
  const R = L.river, k = Math.round(lerp(0, R.hours.length - 1, clamp01((t - 0.1) / 0.86))), now = R.hours[k];
  const got = riverPaint(k);
  L.strip.head(now);
  if (L.riverAvg) { const [lo, hi] = L.riverRange; riverSound("journey", (L.riverAvg[k] - lo) / Math.max(1e-6, hi - lo)); }
  const nisarOn = now >= d.passTime;
  L.map.setPaintProperty("l-nisar", "raster-opacity", nisarOn ? 0.85 : 0);
  L.map.setPaintProperty("l-est", "raster-opacity", nisarOn ? 0.55 : 0.9);
  const seen = L.events.filter((e) => e.t <= now);
  const last = seen[seen.length - 1];
  if (L.seen !== undefined && seen.length > L.seen && last) { if (last.who === "nisar") soundPing({ gain: 0.08 }); else soundTick(0.03); }
  L.seen = seen.length;
  const when = new Date(now).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", timeZone: "UTC" });
  $("lantern-when").textContent = `${when} UTC`;
  lanternCopy("10⁵ m · Satilla River, Georgia", ha(got.ha), "hectares under water now, by the river's own gauges",
    last && now - last.t < 30 * 36e5 ? last.text : nisarOn ? d.nisarLine : "Scroll to run the flood, hour by hour. Satellites pass overhead as it happens: NISAR (magenta) and the official flood map's (blue).");
  lanternScale("10⁵ m", `↔ ${km(mapWidthKm())}`);
}

function lanternPlacePixel() {
  const m = L.map, f = L.data.focus;
  if (!m || !f) return;
  const [[w, n], [e, s]] = f.pixel, a = m.project([w, n]), b = m.project([e, s]), pad = 6, size = b.x - a.x;
  Object.assign($("lantern-reticle").style, { left: `${a.x - pad}px`, top: `${a.y - pad}px`, width: `${size + 2 * pad}px`, height: `${b.y - a.y + 2 * pad}px` });
  if (size > 6) Object.assign($("lantern-grid").style, { backgroundSize: `${size}px ${b.y - a.y}px`, backgroundPosition: `${a.x % size}px ${a.y % (b.y - a.y)}px` });
}

function actPixel(t) {
  const d = L.data;
  $("lantern-canvas").style.opacity = $("lantern-glow").style.opacity = "0";
  $("lantern-map").style.opacity = "1";
  $("lantern-strip-wrap").style.opacity = String(1 - ease(clamp01(t / 0.15)));
  lanternMapEnsure();
  if (!L.map || !L.map.getSource("l-est")) return;
  const z = ease(clamp01(t / 0.55)), from = L.mapFrom, to = d.focus.center;
  L.map.jumpTo({ center: [lerp(from.center.lng, to[0], z), lerp(from.center.lat, to[1], z)], zoom: lerp(from.zoom, 14.9, z) });
  L.map.setPaintProperty("l-est", "raster-opacity", 0.55 * (1 - z));
  L.map.setPaintProperty("l-nisar", "raster-opacity", 0.85 - 0.25 * z);
  L.map.setPaintProperty("l-photo", "raster-opacity", 0.55 * (1 - z));
  $("lantern-stage").classList.toggle("l-pixel-on", t > 0.5);
  lanternPlacePixel();
  const db = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)} dB`, ratio = 10 ** (d.contrast.hh_below_water_db / 10);
  lanternCopy(`${d.pixelM} m · One radar pixel`, db(d.contrast.hh_below_water_db), `about ${Math.round(ratio)}× the echo`,
    `Each square is one pixel of NISAR's map. Forest standing in 0.5–2 m of water sent back ${Math.round(ratio)} times the radar power it did before the flood. Forest on dry ground: ${db(d.contrast.hh_above_water_db)}. Measured on the Satilla on ${fmtDay(d.hero.time)}.`,
    `<div class="l-echo"><div class="l-bar"><i style="--v:${1 / ratio}"></i><span>Before the flood</span></div><div class="l-bar l-bar-wet"><i style="--v:1"></i><span>Flooded forest</span></div></div><button type="button" class="l-hear" id="l-hear">▶ Hear the echo</button>`);
  lanternScale(z > 0.9 ? `${d.pixelM} m` : "10⁴ m", `↔ ${km(mapWidthKm())}`);
}

function lanternEcho() {
  soundEcho(10 ** (L.data.contrast.hh_below_water_db / 10));
  const bars = document.querySelectorAll(".l-bar");
  bars[0]?.classList.add("l-ping"); setTimeout(() => bars[0]?.classList.remove("l-ping"), 500);
  setTimeout(() => { bars[1]?.classList.add("l-ping"); setTimeout(() => bars[1]?.classList.remove("l-ping"), 500); }, 900);
}

function lanternWireExtra() {
  const b = $("l-hear");
  if (b) b.addEventListener("click", lanternEcho);
}

const TREE_GROUND = 300, PX_PER_M = 34, TREES = [190, 336, 482, 628, 774], CROWN = { y: 150, rx: 58, ry: 52 }, TRUNK_W = 14;
const TREE_SAT_L = [110, 50], TREE_SAT_C = [820, 50];
const TREE_TRUNK_X = TREES[1] - TRUNK_W / 2, TREE_HIT_X = TREE_TRUNK_X - 16, TREE_SCATTER = [TREES[4] - 20, CROWN.y - 10];
function treeSvg() {
  return `<svg viewBox="0 0 900 420" role="img" aria-label="Cross-section of a flooded forest. NISAR's long radar waves pass the leaves and bounce off the water and a trunk; Sentinel-1's short waves break up in the leaves.">
    <defs><linearGradient id="lt-water-g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#3cc6d6" stop-opacity=".6"/><stop offset="1" stop-color="#0e4f66" stop-opacity=".5"/></linearGradient>
      <linearGradient id="lt-fade-g" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".07" stop-color="#fff"/><stop offset=".93" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
      <mask id="lt-fade"><rect width="900" height="420" fill="url(#lt-fade-g)"/></mask></defs>
    <g mask="url(#lt-fade)"><rect x="0" y="${TREE_GROUND}" width="900" height="120" class="lt-soil"/><rect id="lt-water" x="0" width="900" class="lt-water" fill="url(#lt-water-g)"/></g>
    <g class="lt-trees">${TREES.map((x) => `<rect x="${x - TRUNK_W / 2}" y="${CROWN.y + 20}" width="${TRUNK_W}" height="${TREE_GROUND - CROWN.y - 20}"/><ellipse class="lt-crown" cx="${x}" cy="${CROWN.y}" rx="${CROWN.rx}" ry="${CROWN.ry}"/>`).join("")}</g>
    <g class="lt-sat lt-sat-l" transform="translate(110 40)"><rect x="-13" y="-8" width="26" height="16" rx="2"/><rect x="-42" y="-4" width="24" height="8"/><rect x="18" y="-4" width="24" height="8"/></g>
    <g class="lt-sat lt-sat-c" transform="translate(${TREE_SAT_C[0]} 40)"><rect x="-13" y="-8" width="26" height="16" rx="2"/><rect x="-42" y="-4" width="24" height="8"/><rect x="18" y="-4" width="24" height="8"/></g>
    <text x="16" y="18" class="lt-label lt-l">NISAR · L-band · 24 cm wave</text>
    <text x="884" y="18" text-anchor="end" class="lt-label lt-c">Sentinel-1 · C-band · 5.6 cm wave</text>
    <path id="lt-wave-l" class="lt-wave lt-wave-l"/><path id="lt-echo" class="lt-wave lt-echo"/>
    <path id="lt-wave-c" class="lt-wave lt-wave-c"/><path id="lt-scatter" class="lt-scatter"/>
    <circle id="lt-hit" class="lt-hit" r="7"/>
    <text x="450" y="${TREE_GROUND + 34}" text-anchor="middle" class="lt-note" id="lt-level"></text>
    <text x="20" y="410" class="lt-note lt-small">Not to scale. The two waves are to scale with each other: NISAR's is ${(24 / 5.6).toFixed(1)}× longer.</text>
  </svg>`;
}

function wavePath(x1, y1, x2, y2, lambda, amp, phase, taper = 0) {
  const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy), ux = dx / len, uy = dy / len, nx = -uy, ny = ux;
  let s = "";
  for (let k = 0, n = Math.max(2, Math.ceil(len / 3)); k <= n; k++) {
    const d = (len * k) / n, env = taper ? Math.min(1, d / taper, (len - d) / taper) : 1;
    const o = amp * env * Math.sin((2 * Math.PI * d) / lambda + phase);
    s += `${k ? "L" : "M"}${(x1 + ux * d + nx * o).toFixed(1)} ${(y1 + uy * d + ny * o).toFixed(1)}`;
  }
  return s;
}

function curveAt(level) {
  const c = L.data.curve;
  if (level <= c[0].water_above_ground_m) return c[0].hh_db;
  for (let i = 1; i < c.length; i++) {
    if (level <= c[i].water_above_ground_m) { const a = c[i - 1], b = c[i], f = (level - a.water_above_ground_m) / (b.water_above_ground_m - a.water_above_ground_m); return a.hh_db + f * (b.hh_db - a.hh_db); }
  }
  return c[c.length - 1].hh_db;
}

function actTree(t, dt) {
  const d = L.data;
  $("lantern-map").style.opacity = String(1 - ease(clamp01(t / 0.12)));
  $("lantern-tree").style.opacity = String(ease(clamp01(t / 0.12)));
  $("lantern-stage").classList.remove("l-pixel-on");
  const level = lerp(-2.5, 1.6, ease(clamp01((t - 0.08) / 0.7)));
  const water = $("lt-water");
  if (!water) return;
  const top = TREE_GROUND - Math.max(0, level) * PX_PER_M;
  water.setAttribute("y", top); water.setAttribute("height", Math.max(0, TREE_GROUND - top));
  $("lt-level").textContent = level > 0 ? `Water ${level.toFixed(1)} m above the forest floor` : `River ${Math.abs(level).toFixed(1)} m below the forest floor`;
  L.phase = (L.phase || 0) + (lanternReduced() ? 0 : dt / 260);
  const ph = L.phase, Ll = 96, Lc = Ll * 5.6 / 24;
  const [sx0, sy0] = TREE_SAT_L, hitX = TREE_HIT_X, hitY = level > 0 ? top : TREE_GROUND, ux = hitX - sx0, uy = hitY - sy0;
  const trunkX = TREE_TRUNK_X, trunkY = hitY - ((trunkX - hitX) * uy) / ux, backY = 58, backX = trunkX - ((trunkY - backY) * ux) / uy;
  $("lt-wave-l").setAttribute("d", wavePath(sx0, sy0, hitX, hitY, Ll, 7, -ph, 24) + " " + wavePath(hitX, hitY, trunkX, trunkY, Ll, 7, -ph, 24).replace(/^M/, "L"));
  const db = curveAt(level), strength = clamp01((db - 0.2) / 3);
  $("lt-echo").setAttribute("d", wavePath(trunkX, trunkY, backX, backY, Ll, 7, -ph, 24));
  $("lt-echo").style.opacity = String(0.15 + 0.85 * strength);
  $("lt-hit").setAttribute("cx", hitX); $("lt-hit").setAttribute("cy", hitY); $("lt-hit").style.opacity = String(0.3 + 0.7 * strength);
  const [sx, sy] = TREE_SCATTER;
  $("lt-wave-c").setAttribute("d", wavePath(TREE_SAT_C[0], TREE_SAT_C[1], sx, sy, Lc, 4, -ph * 2.2, 10));
  const sc = [[-32, -10], [-26, 20], [12, -30], [34, 6], [-6, 34], [26, 28]].map(([a, b]) => wavePath(sx, sy, sx + a, sy + b, Lc, 2.5, -ph * 2.2, 8)).join(" ");
  $("lt-scatter").setAttribute("d", sc);
  const sign = db >= 0 ? "+" : "−";
  const ready = t > 0.72;
  $("lantern-fine").hidden = false;
  $("lantern-fine").classList.toggle("in", ready);
  const end = `<div class="l-cta"><a class="btn-primary" href="#act-2">See how NISAR sees it ↓</a><a class="btn-line" href="live.html">Run it yourself</a></div>`;
  lanternCopy("10 m · One tree", `${sign}${Math.abs(db).toFixed(1)} dB`, "NISAR's echo from this forest, measured at this water depth",
    `NISAR's long waves slip past the leaves, bounce off the water, then the trunk, and come straight back. Sentinel-1's short waves break up in the leaves. On the Pearl River, flooded forest brightened ${d.bandsL} for NISAR and ${d.bandsC} for Sentinel-1.`, end);
  document.querySelector("#lantern-extra .l-cta")?.classList.toggle("in", ready);
  lanternScale(pow10(20), "not to scale");
}

const ACT_FN = { orbit: actOrbit, scale: actScale, people: actPeople, blind: actBlind, river: actRiver, pixel: actPixel, tree: actTree };

function lanternFrame(ts) {
  if (!L.visible) { L.raf = null; return; }
  const dt = Math.min(64, ts - (L.last || ts));
  L.last = ts;
  const { act, t } = lanternProgress(dt);
  const jr = $("journey").getBoundingClientRect();
  $("lantern-stage").classList.toggle("pinned", jr.top <= skyTop() + 1 && jr.bottom >= innerHeight - 1);
  if (act !== L.act) {
    L.act = act;
    const stage = $("lantern-stage");
    stage.dataset.act = LANTERN_ACTS[act].key;
    if (act < 4) { $("lantern-canvas").style.opacity = $("lantern-glow").style.opacity = "1"; $("lantern-map").style.opacity = "0"; $("lantern-strip-wrap").style.opacity = "0"; }
    if (act < 6) { $("lantern-tree").style.opacity = "0"; $("lantern-fine").hidden = true; }
    if (act >= 2) lanternMapEnsure();
    if (LANTERN_ACTS[act].key !== "river") riverSound("journey", null);
  }
  ACT_FN[LANTERN_ACTS[act].key](t, dt);
  $("lantern-hint").style.opacity = act === 0 && t < 0.08 ? "1" : "0";
  L.raf = requestAnimationFrame(lanternFrame);
}

async function setupLantern(manifest, metrics) {
  const stage = $("lantern-stage");
  try {
    const get = (u) => fetch(u, { cache: "no-cache" });
    const [summary, { coast }, charts, held, bands] = await Promise.all([
      loadAtlas(), loadGlobeData(small()), get("data/story/charts.json").then((r) => r.json()),
      get("data/dashboard/heldout.json").then((r) => r.json()), get("data/story/bands.json").then((r) => r.json())]);
    const hero = manifest.hero, pass = held.rivers.find((r) => r.id === hero.site).pairs;
    const p15 = pass.find((p) => p.id === hero.pass), rowOf = (pair) => metrics.held_out.find((r) => r.site === hero.site && r.pair === pair);
    const focus = charts.game.focus, [[fw, fn], [fe]] = focus.pixel;
    const dbs = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)} dB`;
    const a = metrics.satilla_audit, ob = metrics.overbank.find((r) => r.site === hero.site && r.pair === hero.pass);
    L.data = {
      summary, hero, coast, focus, watching: charts.watching, treeKm2: summary.tree_km2, peopleTotal: summary.towns.people.total,
      contrast: p15.drivers.contrast, curve: p15.drivers.curve, pixelM: Math.round((fe - fw) * 111320 * Math.cos(fn * DEG)),
      passTime: Date.parse(hero.time), bandsL: dbs(bands.lband.contrast_db), bandsC: dbs(bands.cband.contrast_db),
      nisarLine: `NISAR, ${fmtDay(hero.time)}, near the crest: the magenta is where it mapped flooding under the trees, ${Math.round(100 * rowOf(hero.pass).recall)}% of what the gauges point to. Trust light: ${trustLight({ confident: ob.high, rainy: ob.rainy }).cls}.`,
    };
    const share = summary.check.gfm_excludes_share_under_trees, gap = calendarDays(hero.time, a.scene_time_utc);
    const bandsMonth = new Date(bands.lband.time).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
    $("jf-1").textContent = `The points of light are the blind-spot atlas, a modeled 100-year flood map crossed with ESA WorldCover land cover, summed on a half-degree grid. Their total is the atlas's ${(summary.tree_km2 / 1e6).toFixed(1)} million km² of river floodplain under trees. NISAR's orbit is drawn for illustration (98.4° inclination, a 240 km swath); it isn't NISAR's real track on any date, and neither is the orbit line down the side of the page.`;
    $("jf-2").textContent = `Greenland's area, ${coast.greenland_km2.toLocaleString("en-US")} km², is the CIA World Factbook figure; both shapes are drawn on an equal-area projection. The town lights are towns of 5,000 or more people (GeoNames) beside a large forested floodplain, with city districts skipped and towns within 10 km merged. The population is the towns', not a count of people at risk.`;
    $("jf-3").textContent = `The ${pct(share, 0)} comes from ${inWords(summary.check.areas.length)} areas where Copernicus GFM's own masks were saved, so it isn't a random sample of the world. The hour-by-hour flooding on the Satilla is the gauge-and-lidar estimate, a model rather than a photo of water, run in your browser from provisional USGS readings. GFM's ${fmtDay(a.scene_time_utc)} scene came ${inWords(gap)} days after NISAR's ${fmtDay(hero.time)} pass, so the two aren't scored against each other. With sound on, the water you hear there follows the gauges' average level against flood stage, a sonification of the readings, not a recording.`;
    $("jf-4").textContent = `The pixel's brightening is the measured median on the Satilla on ${fmtDay(hero.time)} (HH, forest under 0.5–2 m of water). The echo you can play uses that power ratio. The tree is a drawing, but its meter follows the measured Satilla curve. The C-band and L-band numbers were measured on a different river, the ${siteTitle(bands.site).replace(/,.*$/, "")}, in ${bandsMonth}.`;
    const dry = new Set(pass.map((p) => p.dry_time && p.dry_time.slice(0, 10)));
    L.events = [
      ...charts.watching.nisar.map((iso) => {
        const t = Date.parse(iso), pair = pass.find((p) => p.time.slice(0, 10) === iso.slice(0, 10)), row = pair && rowOf(pair.id);
        const text = row ? `NISAR passes, ${fmtDay(iso)}: under the trees it maps ${Math.round(100 * row.recall)}% of the flooding the gauges point to.`
          : dry.has(iso.slice(0, 10)) ? `NISAR passes, ${fmtDay(iso)}, before the flood: this becomes its "before" picture.` : `NISAR passes, ${fmtDay(iso)}.`;
        return { t, who: "nisar", text };
      }),
      ...charts.watching.gfm.map((g) => {
        const t = Date.parse(`${g.date}T12:00Z`), late = g.date.replaceAll("-", "") === a.date;
        const text = !g.covered ? `The official flood map's satellite, ${fmtDay(`${g.date}T12:00Z`)}: its picture doesn't reach this stretch.`
          : late ? `The official flood map, ${fmtDay(`${g.date}T12:00Z`)}: ${ha(a.gfm_on_wet_ha)} ha flooded. The gauges point to ${ha(a.estimated_ha)} ha under water.` : `The official flood map's satellite, ${fmtDay(`${g.date}T12:00Z`)}.`;
        return { t, who: "gfm", covered: g.covered > 0, text };
      }),
    ].sort((x, y) => x.t - y.t);
    globeResize($("lantern-canvas"), $("lantern-glow"));
    $("lantern-tree").innerHTML = treeSvg();
    addEventListener("resize", () => { globeResize($("lantern-canvas"), $("lantern-glow")); L.pour = null; if (L.map) L.map.resize(); });
    const watch = () => {
      const r = $("journey").getBoundingClientRect(), on = r.bottom > 0 && r.top < innerHeight;
      if (on && !L.visible) { L.visible = true; L.last = 0; L.sp = null; L.raf = requestAnimationFrame(lanternFrame); }
      else if (!on) { L.visible = false; riverSound("journey", null); }
    };
    addEventListener("scroll", watch, { passive: true });
    addEventListener("resize", watch);
    watch();
    stage.classList.add("ready");
  } catch (err) {
    console.error("The journey couldn't start", err);
    $("lantern-kicker").textContent = "";
    $("lantern-number").textContent = "";
    $("lantern-line").textContent = "The journey couldn't load. Reload the page to try again.";
  }
}
