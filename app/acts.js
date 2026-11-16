
const actFont = (size, weight = 500) => `${weight} ${size}px 'IBM Plex Sans', system-ui, sans-serif`;
const pctOf = (x) => `${Math.round(100 * x)}%`;

const ActGeo = {
  shape(w, h, box) {
    const top = 24, bottom = 58, k = Math.cos(((box.s + box.n) / 2) * DEG);
    const sx = (w - 8) / ((box.e - box.w) * k), sy = (h - top - bottom) / (box.n - box.s), s = Math.min(sx, sy);
    const ox = (w - (box.e - box.w) * k * s) / 2, oy = top + (h - top - bottom - (box.n - box.s) * s) / 2;
    return (lon, lat) => [ox + (lon - box.w) * k * s, oy + (box.n - lat) * s];
  },
  hist(w, h) {
    const key = `${w} ${h}`;
    if (PX.hist?.key === key) return PX.hist;
    const left = 8, right = w - 8, X0 = -3, X1 = 8, dot = 3, across = 3, binW = dot * across, head = 30, gap = 22, axis = 46;
    const X = (v) => left + ((Math.max(X0, Math.min(X1, v)) - X0) / (X1 - X0)) * (right - left);
    const nBins = Math.floor((right - left) / binW), bin = (v) => Math.min(nBins - 1, Math.floor((X(v) - left) / binW));
    const rows = [{ wet: 1, label: "Flooded under trees" }, { wet: 0, label: "Dry under trees" }];
    const xy = new Float32Array(2 * PX.N), counts = rows.map(() => new Map()), slot = new Int32Array(PX.N);
    for (let j = 0; j < PX.N; j++) {
      if (PX.skip[j]) continue;
      const k = PX.wet[j] ? 0 : 1, b = bin(PX.db[j]), n = counts[k].get(b) || 0;
      counts[k].set(b, n + 1); slot[j] = n;
      xy[2 * j] = left + b * binW + (n % across) * dot + dot / 2;
    }
    rows.forEach((r, k) => {
      r.peak = Math.ceil(Math.max(...counts[k].values()) / across);
      const v = []; for (let j = 0; j < PX.N; j++) if (PX.wet[j] === r.wet) v.push(PX.db[j]);
      v.sort((a, b) => a - b); r.median = v[v.length >> 1]; r.n = v.length;
    });
    const room = h - 2 * head - gap - axis, step = Math.min(dot, room / (rows[0].peak + rows[1].peak));
    const total = 2 * head + gap + axis + step * (rows[0].peak + rows[1].peak), top = Math.max(0, (h - total) / 2);
    rows[0].base = top + head + rows[0].peak * step;
    rows[1].base = rows[0].base + gap + head + rows[1].peak * step;
    rows.forEach((r) => { r.step = step; r.height = r.peak * step; });
    for (let j = 0; j < PX.N; j++) { if (PX.skip[j]) continue; const r = rows[PX.wet[j] ? 0 : 1]; xy[2 * j + 1] = r.base - (Math.floor(slot[j] / across) + 0.5) * step; }
    return (PX.hist = { key, left, right, top, base: rows[1].base, X0, X1, X, rows, xy, line: h * 0.62 });
  },
  world(w, h) {
    const mapH = h - 40, c30 = Math.cos(30 * DEG), yTop = Math.sin(75 * DEG) / c30, yBot = Math.sin(-60 * DEG) / c30;
    return { mapH, X: (lon) => ((lon + 180) / 360) * w, Y: (lat) => ((yTop - Math.sin(lat * DEG) / c30) / (yTop - yBot)) * mapH };
  },
  tests(w, h, metrics) {
    const groups = [["Method 1", "v1"], ["Method 2", "v2"], ["Method 3", "v3"], ["Method 4, first", "v4, median"], ["Method 4, latest", "v4, overbank"]];
    const laneH = Math.min(w < 600 ? 38 : 46, (h - 50) / groups.length), left = Math.min(124, w * 0.3), right = w - 14;
    const top = Math.max(0, (h - laneH * groups.length - 44) / 2), base = top + laneH * groups.length;
    const X = (v) => left + v * (right - left);
    const rows = groups.flatMap(([, prefix], g) => judgedPasses(metrics).filter((r) => r.method.startsWith(prefix)).map((r) => ({ r, g, x: X(r.csi), y: top + (g + 0.5) * laneH })));
    return { groups, left, right, top, base, laneH, X, rows };
  },
};

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
    PX.delay[j] = 0.75 * (chain[j] / cmax) + 0.25 * PX.rnd[j];
    PX.skip[j] = innerWidth < 760 && j % 2 ? 1 : 0;
  });
  PX.box = { w: Infinity, e: -Infinity, s: Infinity, n: -Infinity };
  for (let j = 0; j < N; j++) { PX.box.w = Math.min(PX.box.w, PX.lon[j]); PX.box.e = Math.max(PX.box.e, PX.lon[j]); PX.box.s = Math.min(PX.box.s, PX.lat[j]); PX.box.n = Math.max(PX.box.n, PX.lat[j]); }
}

function layout(name, w, h, extra = null) {
  const key = `${name} ${w} ${h} ${extra ? extra.join(",") : ""}`;
  if (PX.cache.has(key)) return PX.cache.get(key);
  const xy = new Float32Array(2 * PX.N);
  if (name === "shape") { const f = ActGeo.shape(w, h, PX.frame || PX.box); for (let j = 0; j < PX.N; j++) { const [x, y] = f(PX.lon[j], PX.lat[j]); xy[2 * j] = x; xy[2 * j + 1] = y; } }
  else if (name === "hist") xy.set(ActGeo.hist(w, h).xy);
  else if (name === "line") { const g = ActGeo.hist(w, h); for (let j = 0; j < PX.N; j++) { xy[2 * j] = g.xy[2 * j]; xy[2 * j + 1] = g.line + (PX.rnd2[j] - 0.5) * 2; } }
  else if (name === "point") { const [cx, cy, r] = extra; for (let j = 0; j < PX.N; j++) { const a = PX.rnd[j] * 2 * Math.PI * 7.3, d = r * Math.sqrt(PX.rnd2[j]); xy[2 * j] = cx + d * Math.cos(a); xy[2 * j + 1] = cy + d * Math.sin(a); } }
  PX.cache.set(key, xy);
  return xy;
}

function drawPixels(ctx, from, to, t, span, { alpha, color, size = innerWidth < 760 ? 1.8 : 2.1, delay = PX.delay }) {
  for (let j = 0; j < PX.N; j++) {
    if (PX.skip[j]) continue;
    const q = Motion.ease(Motion.clamp((t / span - delay[j] * 0.45) / 0.55));
    const a = alpha(j, q);
    if (a <= 0.01) continue;
    const x = Motion.lerp(from[2 * j], to[2 * j], q), y = Motion.lerp(from[2 * j + 1], to[2 * j + 1], q);
    ctx.globalAlpha = a; ctx.fillStyle = color(j, q, x);
    ctx.fillRect(x - size / 2, y - size / 2, size, size);
  }
  ctx.globalAlpha = 1;
}

async function setupActs(metrics) {
  const T = await figJson("story/thread.json");
  const F = T.fields, lon = F.indexOf("lon"), lat = F.indexOf("lat"), wet = F.indexOf("wet"), db = F.indexOf("d_hh_db");
  T.center = [T.particles.reduce((s, p) => s + p[lon], 0) / T.particles.length, T.particles.reduce((s, p) => s + p[lat], 0) / T.particles.length];
  loadPixels(T);
  const hero = await fetch("data/manifest.json").then((r) => r.json()).then((m) => m.hero).catch(() => null);
  if (hero && hero.site === T.site && hero.pass === T.pass) {
    const [[w, n], , [e, s]] = hero.corners, dir = `data/${hero.site}/${hero.pass}/`;
    PX.frame = { w, e, s, n };
    PX.layers = { truth: dir + hero.layers.truth, mask: dir + hero.layers.gfm_excl };
  }
  const med = (rows) => { const v = rows.map((p) => p[db]).sort((a, b) => a - b); return v[v.length >> 1]; };
  const sdb = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)} dB`;
  const day = fmtDay(T.time), [lo, hi] = scoreRange(metrics), latest = latestPasses(metrics);
  const put = (id, num, unit) => { const el = $(id); if (el) el.innerHTML = `<b>${num}</b><span>${unit}</span>`; };
  put("act1-num", pctOf(T.mask_share_wet), `of the Satilla's flooding on ${day} lies inside the official map's own "can't map here" mask`);
  put("act2-num", sdb(med(T.particles.filter((p) => p[wet] === 1))), `median brightening where the river says flooded, ${sdb(med(T.particles.filter((p) => p[wet] === 0)))} where it says dry`);
  put("act4-num", `${lo.toFixed(2)}–${hi.toFixed(2)}`, `GLOWfm's latest test, on the ${inWords(latest.length)} passes with enough flooding to judge, where 1 is perfect`);
  setupStage(T, metrics);
}
