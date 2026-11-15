// The act cards (index.html, .act-card) share one set of particles: real pixels of the Satilla flood on its frozen test
// pass (data/story/thread.json, from scripts/build_thread.py), each 2.5 ha. Every card draws them in its own frame and
// assembles them from the previous card's shape, so the same pixels carry through the story without anything crossing
// the text: Act 1, the flood's real shape with the official map's mask passing over it; Act 2, sorted into radar
// brightening against water depth; Act 3, gathered into one light on Earth; the proof, collapsed into their test's dot.

const ACT_INK = { water: "#6fe3ef", official: "#8fb4ff", nisar: "#e57ae5", veil: "#8a969e", text: "#d6e1e8", muted: "#a7b9c5", rule: "rgba(205, 225, 235, .22)", forest: "79, 220, 176" };
const actFont = (size, weight = 500) => `${weight} ${size}px 'IBM Plex Sans', system-ui, sans-serif`;
const actNum = (size) => `600 ${size}px 'Space Grotesk', 'IBM Plex Sans', system-ui, sans-serif`;
const pctOf = (x) => `${Math.round(100 * x)}%`;

// ---------- each card's geometry (in the card canvas's own pixels) ----------
const ActGeo = {
  // Act 1: the flood's real shape, fitted into the card (equirectangular with the local longitude scale).
  shape(w, h, box) {
    const top = 24, bottom = 58, k = Math.cos(((box.s + box.n) / 2) * DEG);
    const sx = (w - 8) / ((box.e - box.w) * k), sy = (h - top - bottom) / (box.n - box.s), s = Math.min(sx, sy);
    const ox = (w - (box.e - box.w) * k * s) / 2, oy = top + (h - top - bottom - (box.n - box.s) * s) / 2;
    return (lon, lat) => [ox + (lon - box.w) * k * s, oy + (box.n - lat) * s];
  },
  // Act 2: radar brightening (dB) against the water's height above the ground (m).
  scatter(w, h) {
    const left = 44, right = w - 8, top = 26, base = h - 30, X0 = -4, X1 = 8, Y0 = -5, Y1 = 2.5;
    return { left, right, top, base, X0, X1, Y0, Y1,
      X: (v) => left + ((Math.max(X0, Math.min(X1, v)) - X0) / (X1 - X0)) * (right - left),
      Y: (v) => base - ((Math.max(Y0, Math.min(Y1, v)) - Y0) / (Y1 - Y0)) * (base - top) };
  },
  // Act 3: an equal-area world map (Lambert cylindrical, standard parallel 30°), as on the Run it yourself console.
  world(w, h) {
    const mapH = h - 40, c30 = Math.cos(30 * DEG), yTop = Math.sin(75 * DEG) / c30, yBot = Math.sin(-60 * DEG) / c30;
    return { mapH, X: (lon) => ((lon + 180) / 360) * w, Y: (lat) => ((yTop - Math.sin(lat * DEG) / c30) / (yTop - yBot)) * mapH };
  },
  // The proof: every judged test, one lane per method; each test's dot position.
  tests(w, h, metrics) {
    const groups = [["Method 1", "v1"], ["Method 2", "v2"], ["Method 3", "v3"], ["Method 4, first", "v4, median"], ["Method 4, latest", "v4, overbank"]];
    const left = Math.min(118, w * 0.3), right = w - 10, top = 26, base = h - 22, laneH = (base - top) / groups.length;
    const X = (v) => left + v * (right - left);
    const rows = groups.flatMap(([, prefix], g) => judgedPasses(metrics).filter((r) => r.method.startsWith(prefix)).map((r) => ({ r, g, x: X(r.csi), y: top + (g + 0.5) * laneH })));
    return { groups, left, right, top, base, laneH, X, rows };
  },
};

function actFigure(k, legend, label, replay = true) {
  const fig = $(`instr-${k}`);
  if (!fig) return null;
  fig.querySelector(".act-legend").textContent = legend;
  if (label) fig.querySelector("canvas").setAttribute("aria-label", label);
  return { fig, canvas: fig.querySelector("canvas"), replay: replay ? Motion.replayButton(fig, legend) : null };
}

// ---------- the Satilla's pixels, shared by every card ----------
const PX = { N: 0 };
function loadPixels(T) {
  const F = T.fields, col = (k) => F.indexOf(k), rows = T.particles, N = rows.length, rand = Motion.seeded(3);
  const chain = rows.map((r) => r[col("chainage_km")]), cmax = Math.max(...chain) || 1;
  Object.assign(PX, { N, lon: new Float64Array(N), lat: new Float64Array(N), wet: new Uint8Array(N), excl: new Uint8Array(N), db: new Float32Array(N), water: new Float32Array(N),
                      delay: new Float32Array(N), rnd: new Float32Array(N), rnd2: new Float32Array(N), skip: new Uint8Array(N), cache: new Map() });
  rows.forEach((r, j) => {
    PX.lon[j] = r[col("lon")]; PX.lat[j] = r[col("lat")]; PX.wet[j] = r[col("wet")]; PX.db[j] = r[col("d_hh_db")]; PX.water[j] = r[col("water_m")];
    PX.excl[j] = r[col("gfm_covered")] && r[col("gfm_excluded")] ? 1 : 0;
    PX.rnd[j] = rand(); PX.rnd2[j] = rand();
    PX.delay[j] = 0.75 * (chain[j] / cmax) + 0.25 * PX.rnd[j];      // upstream first, like the river
    PX.skip[j] = innerWidth < 760 && j % 2 ? 1 : 0;                 // phones draw half
  });
  PX.box = { w: Infinity, e: -Infinity, s: Infinity, n: -Infinity };
  for (let j = 0; j < N; j++) { PX.box.w = Math.min(PX.box.w, PX.lon[j]); PX.box.e = Math.max(PX.box.e, PX.lon[j]); PX.box.s = Math.min(PX.box.s, PX.lat[j]); PX.box.n = Math.max(PX.box.n, PX.lat[j]); }
}

// Where each pixel sits in a given layout, in a canvas of size w × h (cached per layout and size).
function layout(name, w, h, extra = null) {
  const key = `${name} ${w} ${h} ${extra ? extra.join(",") : ""}`;
  if (PX.cache.has(key)) return PX.cache.get(key);
  const xy = new Float32Array(2 * PX.N);
  if (name === "shape") { const f = ActGeo.shape(w, h, PX.box); for (let j = 0; j < PX.N; j++) { const [x, y] = f(PX.lon[j], PX.lat[j]); xy[2 * j] = x; xy[2 * j + 1] = y; } }
  else if (name === "scatter") { const g = ActGeo.scatter(w, h); for (let j = 0; j < PX.N; j++) { xy[2 * j] = g.X(PX.db[j]) + (PX.rnd[j] - 0.5) * 2; xy[2 * j + 1] = g.Y(PX.water[j]) + (PX.rnd2[j] - 0.5) * 2; } }
  else if (name === "point") { const [cx, cy, r] = extra; for (let j = 0; j < PX.N; j++) { const a = PX.rnd[j] * 2 * Math.PI * 7.3, d = r * Math.sqrt(PX.rnd2[j]); xy[2 * j] = cx + d * Math.cos(a); xy[2 * j + 1] = cy + d * Math.sin(a); } }
  PX.cache.set(key, xy);
  return xy;
}

// Draw the pixels moving from one layout to another: q runs 0 to 1 over `span` of the card's time, in river order.
function drawPixels(ctx, from, to, t, span, { alpha, color, size = innerWidth < 760 ? 1.8 : 2.1 }) {
  for (let j = 0; j < PX.N; j++) {
    if (PX.skip[j]) continue;
    const q = Motion.ease(Motion.clamp((t / span - PX.delay[j] * 0.45) / 0.55));
    const a = alpha(j, q);
    if (a <= 0.01) continue;
    const x = Motion.lerp(from[2 * j], to[2 * j], q), y = Motion.lerp(from[2 * j + 1], to[2 * j + 1], q);
    ctx.globalAlpha = a; ctx.fillStyle = color(j, q, x);
    ctx.fillRect(x - size / 2, y - size / 2, size, size);
  }
  ctx.globalAlpha = 1;
}

// ---------- Act 1: the flood, and the official map's own mask passing over it ----------
function actVeil(T) {
  const day = fmtDay(T.time), gfmDay = fmtDay(`${T.gfm_date.slice(0, 4)}-${T.gfm_date.slice(4, 6)}-${T.gfm_date.slice(6, 8)}T12:00Z`);
  const f = actFigure(1, `Each point is ${T.unit_ha} ha of the flooding the river's gauges point to on ${day}, on the map above. Grey: inside the "can't map here" mask the official map (Copernicus GFM) published with its ${gfmDay} scene.`,
    `${pctOf(T.mask_share_wet)} of the Satilla's flooding on ${day} lies inside the official flood map's own exclusion mask; ${pctOf(T.tree_share_wet)} is under trees.`);
  if (!f) return;
  Motion.instrument(f.canvas, (ctx, t, w, h) => {
    const sweep = Motion.ease(Motion.clamp((t - 0.38) / 0.62)), x = Motion.lerp(-6, w + 6, sweep);
    ctx.font = actFont(12); ctx.fillStyle = ACT_INK.muted; ctx.textAlign = "left";
    ctx.fillText(`The Satilla's flooding on ${day}, in its real shape`, 0, 12);
    const shape = layout("shape", w, h);
    drawPixels(ctx, shape, shape, t, 0.4, { alpha: (j, q) => (PX.wet[j] ? q : 0), color: (j, q, px) => (PX.excl[j] && px <= x ? ACT_INK.veil : ACT_INK.water) });
    if (sweep > 0 && sweep < 1) {
      ctx.strokeStyle = "rgba(235, 245, 250, .75)"; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(x + 0.5, 20); ctx.lineTo(x + 0.5, h - 54); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = "rgba(138, 150, 158, .1)"; ctx.fillRect(0, 20, x, h - 74);
    }
    ctx.fillStyle = ACT_INK.rule; ctx.fillRect(0, h - 48, w, 1);
    const share = t >= 1 ? T.mask_share_wet : T.mask_share_wet * Motion.clamp(sweep * 1.04);
    ctx.font = actNum(26); ctx.fillStyle = ACT_INK.text; ctx.fillText(pctOf(share), 0, h - 14);
    const wNum = ctx.measureText("100%").width;
    ctx.font = actFont(12); ctx.fillStyle = ACT_INK.muted;
    ctx.fillText("inside the official map's own", wNum + 10, h - 27); ctx.fillText("\"can't map here\" mask", wNum + 10, h - 12);
    const x2 = Math.max(wNum + 190, w * 0.62);
    ctx.font = actNum(26); ctx.fillStyle = ACT_INK.text; ctx.fillText(pctOf(T.tree_share_wet), x2, h - 14);
    ctx.font = actFont(12); ctx.fillStyle = ACT_INK.muted; ctx.fillText("of the same flooding", x2 + wNum + 10, h - 27); ctx.fillText("is under trees", x2 + wNum + 10, h - 12);
  }, { ms: 3600, replay: f.replay, threshold: 0.5 });
}

// ---------- Act 2: the flood's shape sorts itself into radar brightening against water depth ----------
function actScatter(T) {
  const f = actFigure(2, `The same pixels, sorted: each point is ${T.unit_ha} ha of the Satilla on ${fmtDay(T.time)}. Cyan: flooded, by the river's answer; grey: dry. Values beyond the axes sit on the edge.`,
    "Radar brightening against water depth, for the Satilla's pixels: flooded forest brightens; dry ground doesn't.");
  if (!f) return;
  const P = T.particles, F = T.fields, wet = F.indexOf("wet"), db = F.indexOf("d_hh_db");
  const med = (rows) => { const v = rows.map((p) => p[db]).sort((a, b) => a - b); return v[v.length >> 1]; };
  const mWet = med(P.filter((p) => p[wet] === 1)), mDry = med(P.filter((p) => p[wet] === 0)), sdb = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)} dB`;
  Motion.instrument(f.canvas, (ctx, t, w, h) => {
    const g = ActGeo.scatter(w, h);
    ctx.strokeStyle = ACT_INK.rule; ctx.lineWidth = 1; ctx.font = actFont(11); ctx.fillStyle = ACT_INK.muted; ctx.textAlign = "center";
    ctx.beginPath(); ctx.moveTo(g.left, g.base + 0.5); ctx.lineTo(g.right, g.base + 0.5); ctx.moveTo(g.left + 0.5, g.top); ctx.lineTo(g.left + 0.5, g.base); ctx.stroke();
    for (const v of [-4, -2, 0, 2, 4, 6, 8]) { ctx.fillRect(g.X(v), g.base, 1, 4); ctx.fillText(v === 0 ? "0" : `${v > 0 ? "+" : "−"}${Math.abs(v)}`, g.X(v), g.base + 15); }
    ctx.fillText("radar brightening, HH (dB)", (g.left + g.right) / 2, h - 1);
    ctx.textAlign = "right";
    for (const v of [-4, -2, 0, 2]) { ctx.fillRect(g.left - 4, g.Y(v), 4, 1); ctx.fillText(`${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v)} m`, g.left - 7, g.Y(v) + 4); }
    ctx.setLineDash([3, 3]); ctx.strokeStyle = "rgba(205, 225, 235, .4)"; ctx.beginPath(); ctx.moveTo(g.left, g.Y(0) + 0.5); ctx.lineTo(g.right, g.Y(0) + 0.5); ctx.stroke(); ctx.setLineDash([]);
    ctx.textAlign = "left"; ctx.fillStyle = ACT_INK.muted; ctx.fillText("forest floor", g.left + 6, g.Y(0) - 5);
    ctx.textAlign = "right";       // both medians sit against the right edge, so they fit on a phone
    ctx.fillStyle = ACT_INK.water; ctx.fillText(`flooded · median ${sdb(mWet)}`, g.right, g.top + 6);
    ctx.fillStyle = ACT_INK.muted; ctx.fillText(`dry · median ${sdb(mDry)}`, g.right, g.base - 8);
    // The pixels start in the flood's shape (the dry ground around it fading in) and sort into place.
    drawPixels(ctx, layout("shape", w, h), layout("scatter", w, h), t, 0.9, { alpha: (j, q) => (PX.wet[j] ? 1 : q), color: (j) => (PX.wet[j] ? ACT_INK.water : "#b9c4cb") });
  }, { ms: 3000, replay: f.replay, threshold: 0.5 });
}

// ---------- Act 3: the world map, and this season's floods ----------
async function actSeason(T) {
  const index = await fetch("data/live/index.json").then((r) => r.json());
  const cases = currentCases(index).slice().sort((a, b) => Date.parse(a.wet) - Date.parse(b.wet));
  const span = cases.length ? `${fmtDay(cases[0].wet)}–${fmtDay(cases[cases.length - 1].wet)}` : "";
  const f = actFigure(3, `The Satilla's flood, gathered into its place on Earth (magenta). Cyan: this season's floods ready to run, lit in the order NISAR passed them, ${span}. Equal-area map.`,
    `The Satilla River, and ${cases.length} floods ready to run: ${cases.map((c) => c.place).join("; ")}.`);
  if (!f) return;
  await loadGlobeData(small());
  let bg = null;
  const t0 = cases.length ? Date.parse(cases[0].wet) : 0, t1 = cases.length ? Date.parse(cases[cases.length - 1].wet) : 1;
  Motion.instrument(f.canvas, (ctx, t, w, h) => {
    const g = ActGeo.world(w, h);
    if (!bg || bg.w !== w || bg.h !== h) {
      const off = document.createElement("canvas"), dpr = Math.min(2, devicePixelRatio || 1), P = GLOBE_DATA.pts, s = Math.max(0.7, w / 900);
      off.width = Math.round(w * dpr); off.height = Math.round(g.mapH * dpr);
      const o = off.getContext("2d"); o.setTransform(dpr, 0, 0, dpr, 0, 0); o.fillStyle = `rgba(${ACT_INK.forest}, .13)`; o.beginPath();
      if (P) for (let i = 0; i < P.n; i++) o.rect(g.X(P.lon[i] / DEG) - s / 2, g.Y(Math.asin(P.sinLat[i]) / DEG) - s / 2, s, s);
      o.fill();
      bg = { w, h, off };
    }
    ctx.drawImage(bg.off, 0, 0, w, g.mapH);
    // The Satilla's pixels gather from the scatter into one light at its place (first half), then the season plays.
    const here = [g.X(T.center[0]), g.Y(T.center[1]), 5];
    drawPixels(ctx, layout("scatter", w, h), layout("point", w, h, here), t, 0.5, { alpha: () => 1, color: (j, q) => (q > 0.6 ? ACT_INK.nisar : PX.wet[j] ? ACT_INK.water : "#b9c4cb") });
    const ts = Motion.clamp((t - 0.45) / 0.55);
    const now = t0 + Motion.ease(ts) * (t1 - t0), ty = h - 20, TX = (ms) => (t1 > t0 ? (ms - t0) / (t1 - t0) : 0.5) * (w - 20) + 10;
    ctx.strokeStyle = ACT_INK.rule; ctx.beginPath(); ctx.moveTo(0, ty + 0.5); ctx.lineTo(w, ty + 0.5); ctx.stroke();
    let latest = null;
    cases.forEach((c) => {
      const when = Date.parse(c.wet), on = t >= 1 || (ts > 0 && now >= when), x = g.X(c.lon), y = g.Y(c.lat);
      ctx.fillStyle = on ? ACT_INK.water : ACT_INK.rule; ctx.fillRect(TX(when) - 1, ty - 4, 2, 9);
      if (!on) return;
      latest = c;
      const age = t1 > t0 ? (now - when) / (t1 - t0) / 0.15 : 1;
      if (t < 1 && ts > 0 && age < 1) { ctx.strokeStyle = `rgba(255, 255, 255, ${0.9 * (1 - age)})`; ctx.beginPath(); ctx.arc(x, y, 4 + 16 * age, 0, 2 * Math.PI); ctx.stroke(); }
      ctx.fillStyle = ACT_INK.water; ctx.beginPath(); ctx.arc(x, y, 3, 0, 2 * Math.PI); ctx.fill();
    });
    ctx.font = actFont(12); ctx.textAlign = "left"; ctx.fillStyle = ACT_INK.muted;
    ctx.fillText(t >= 1 || !latest ? `${cases.length} floods ready to run · ${span}` : `${fmtTime(latest.wet)} · ${latest.place}`, 0, h - 2);
    if (t > 0.35) { ctx.fillStyle = ACT_INK.nisar; ctx.fillText("Satilla", here[0] + 9, here[1] - 7); }
  }, { ms: 3600, replay: f.replay, threshold: 0.5 });
}

// ---------- The proof: the flood becomes its own test's dot, among every judged test ----------
function actTests(metrics, T) {
  const judged = judgedPasses(metrics), [lo, hi] = scoreRange(metrics);
  const f = actFigure(4, `Each dot is one frozen test, run once, with its 95% range. The Satilla's pixels gather into their own test's dot, ${T.csi.toFixed(2)}. Grey: Method 4's first test, where it failed on three rivers.`,
    `${judged.length} judged tests, scores from ${lo.toFixed(2)} to ${hi.toFixed(2)}, where 1 is perfect; the Satilla on ${fmtDay(T.time)} scored ${T.csi.toFixed(2)}.`);
  if (!f) return;
  Motion.instrument(f.canvas, (ctx, t, w, h) => {
    const L = ActGeo.tests(w, h, metrics);
    ctx.font = actFont(11); ctx.textAlign = "center"; ctx.fillStyle = ACT_INK.muted; ctx.strokeStyle = ACT_INK.rule; ctx.lineWidth = 1;
    for (const v of [0, 0.2, 0.4, 0.6, 0.8, 1]) { ctx.beginPath(); ctx.moveTo(L.X(v) + 0.5, L.top); ctx.lineTo(L.X(v) + 0.5, L.base); ctx.stroke(); ctx.fillText(v === 0 || v === 1 ? String(v) : v.toFixed(1), L.X(v), L.base + 15); }
    ctx.textAlign = "left";
    L.groups.forEach(([label], g) => ctx.fillText(label, 0, L.top + (g + 0.5) * L.laneH + 4));
    let shown = 0;
    L.rows.forEach(({ r, g, x, y }, k) => {
      const hero = r.site === T.site && r.pair === T.pass && r.method.startsWith("v4, overbank");
      const q = hero ? Motion.clamp((t - 0.4) / 0.2) : Motion.stagger(Motion.clamp((t - 0.45) / 0.55), k, L.rows.length, 0.7, 0.25);
      if (q <= 0) return;
      shown++;
      const col = g === 3 ? ACT_INK.veil : g === 4 ? ACT_INK.nisar : ACT_INK.water, bar = Motion.clamp((q - 0.5) / 0.5);
      if (bar > 0 && r.ci95) { ctx.strokeStyle = col; ctx.globalAlpha = 0.55; ctx.beginPath(); ctx.moveTo(L.X(r.csi + (r.ci95[0] - r.csi) * bar), y + 0.5); ctx.lineTo(L.X(r.csi + (r.ci95[1] - r.csi) * bar), y + 0.5); ctx.stroke(); ctx.globalAlpha = 1; }
      if (!hero) { ctx.fillStyle = col; ctx.globalAlpha = Math.min(1, q * 2); ctx.beginPath(); ctx.arc(x, y, 3.4, 0, 2 * Math.PI); ctx.fill(); ctx.globalAlpha = 1; }
      else { ctx.fillStyle = ACT_INK.nisar; ctx.font = actFont(11, 600); ctx.fillText(`Satilla, ${fmtDay(T.time)}`, x + 10, y - 8); ctx.font = actFont(11); }
    });
    // The flood, in its shape, collapses into its own test's dot.
    const me = L.rows.find(({ r }) => r.site === T.site && r.pair === T.pass && r.method.startsWith("v4, overbank"));
    if (me) drawPixels(ctx, layout("shape", w, h), layout("point", w, h, [me.x, me.y, 3.6]), t, 0.45, { alpha: (j) => (PX.wet[j] ? 1 : 0), color: (j, q) => (q > 0.5 ? ACT_INK.nisar : ACT_INK.water) });
    ctx.font = actFont(12); ctx.fillStyle = ACT_INK.text; ctx.textAlign = "right";
    ctx.fillText(t >= 1 ? `${judged.length} tests · ${lo.toFixed(2)}–${hi.toFixed(2)} · 1 is perfect` : `${shown} of ${judged.length} tests`, L.right, 13);
  }, { ms: 3600, replay: f.replay, threshold: 0.5 });
}

async function setupActs(metrics) {
  const T = await figJson("story/thread.json");
  const F = T.fields, lon = F.indexOf("lon"), lat = F.indexOf("lat");
  T.center = [T.particles.reduce((s, p) => s + p[lon], 0) / T.particles.length, T.particles.reduce((s, p) => s + p[lat], 0) / T.particles.length];
  loadPixels(T);
  actVeil(T);
  actScatter(T);
  actSeason(T).catch((e) => console.error("Act 3", e));
  actTests(metrics, T);
}
