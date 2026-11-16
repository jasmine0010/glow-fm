
const DEG = Math.PI / 180;
const EARTH_KM = 6371;
const SWATH_HALF = (120 / EARTH_KM);
const INCLINATION = 98.4 * DEG;

const GLOBE_DATA = { pts: null, people: null, coast: [] };
function makeGlobe() {
  return {
    canvas: null, glow: null, ctx: null, gctx: null, w: 0, h: 0, dpr: 1,
    get pts() { return GLOBE_DATA.pts; }, get people() { return GLOBE_DATA.people; }, get coast() { return GLOBE_DATA.coast; },
    view: { lon: -60, lat: 12, R: 300, cx: 0, cy: 0 },
    sat: { u: 0, node: -40, on: true }, lit: null, buf: null, now: 0,
  };
}
const globe = makeGlobe();

let globeLoading = null;
function loadGlobeData(small) {
  globeLoading ??= Promise.all([
    fetch("data/story/lantern_points.bin", { cache: "no-cache" }).then((r) => r.arrayBuffer()),
    fetch("data/story/lantern_people.json", { cache: "no-cache" }).then((r) => r.json()),
    fetch("data/story/lantern_coast.json", { cache: "no-cache" }).then((r) => r.json()),
  ]).then(([buf, people, coast]) => { globeData(buf, people, coast, small); return { coast }; });
  return globeLoading;
}

function globeData(buffer, people, coast, small) {
  const raw = new Int16Array(buffer), all = raw.length / 3;
  const keep = [];
  for (let i = 0; i < all; i++) if (!small || raw[3 * i + 2] >= 6) keep.push(i);
  const n = keep.length, p = { n, sinLat: new Float32Array(n), cosLat: new Float32Array(n), lon: new Float32Array(n), km2: new Float32Array(n) };
  keep.forEach((i, k) => {
    const lat = raw[3 * i + 1] / 100 * DEG;
    p.lon[k] = raw[3 * i] / 100 * DEG; p.sinLat[k] = Math.sin(lat); p.cosLat[k] = Math.cos(lat); p.km2[k] = raw[3 * i + 2];
  });
  GLOBE_DATA.pts = p;
  const m = people.length;
  const T = { n: m, lon: new Float32Array(m), sinLat: new Float32Array(m), cosLat: new Float32Array(m), pop: new Float32Array(m) };
  people.forEach(([lon, lat, pop], k) => { T.lon[k] = lon * DEG; T.sinLat[k] = Math.sin(lat * DEG); T.cosLat[k] = Math.cos(lat * DEG); T.pop[k] = pop; });
  GLOBE_DATA.people = T;
  GLOBE_DATA.coast = coast.rings.map((r) => r.map(([x, y]) => [x * DEG, Math.sin(y * DEG), Math.cos(y * DEG)]));
}

function globeResize(canvas, glow, g = globe) {
  g.canvas = canvas; g.glow = glow;
  const r = canvas.getBoundingClientRect();
  g.dpr = Math.min(2, devicePixelRatio || 1);
  g.w = r.width; g.h = r.height;
  canvas.width = Math.round(r.width * g.dpr); canvas.height = Math.round(r.height * g.dpr);
  glow.width = Math.round(r.width / 2); glow.height = Math.round(r.height / 2);
  g.ctx = canvas.getContext("2d"); g.gctx = glow.getContext("2d");
}

function globeProject(lonR, sinLat, cosLat, out, g = globe) {
  const v = g.view, l0 = v.lon * DEG, p0 = v.lat * DEG, s0 = Math.sin(p0), c0 = Math.cos(p0);
  const d = lonR - l0, cd = Math.cos(d), cosc = s0 * sinLat + c0 * cosLat * cd;
  if (cosc <= 0) return null;
  out[0] = v.cx + v.R * cosLat * Math.sin(d);
  out[1] = v.cy - v.R * (c0 * sinLat - s0 * cosLat * cd);
  out[2] = cosc;
  return out;
}

function subSatellite(u, node) {
  const lat = Math.asin(Math.sin(INCLINATION) * Math.sin(u));
  const lon = node * DEG + Math.atan2(Math.cos(INCLINATION) * Math.sin(u), Math.cos(u));
  return [lon, lat];
}

function globeAdvance(dt, moving, g = globe) {
  g.now += dt;
  if (!moving) return;
  g.sat.u += dt * (2 * Math.PI / 16000);
  if (g.sat.u > 2 * Math.PI) { g.sat.u -= 2 * Math.PI; g.sat.node -= 24; }
}

const GLOBE_RGB = { forest: [79, 220, 176], nisar: [229, 122, 229], people: [255, 186, 102] };
const GLOBE_GAIN = 1.3;

function globeDraw(opts, g = globe) {
  const { ctx, gctx, w, h, dpr, view: v } = g;
  const [fr, fg, fb] = GLOBE_RGB.forest, [nr, ng, nb] = GLOBE_RGB.nisar;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  gctx.setTransform(0.5, 0, 0, 0.5, 0, 0);
  gctx.clearRect(0, 0, w, h);
  const out = [0, 0, 0];

  if (!(v.R > 0)) return;
  if (v.R < 6 * Math.max(w, h)) {
    const g = ctx.createRadialGradient(v.cx - v.R * 0.3, v.cy - v.R * 0.35, v.R * 0.1, v.cx, v.cy, v.R);
    g.addColorStop(0, "rgba(10, 26, 34, 0.96)"); g.addColorStop(1, "rgba(4, 9, 14, 0.98)");
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(v.cx, v.cy, v.R, 0, 2 * Math.PI); ctx.fill();
    const a = ctx.createRadialGradient(v.cx, v.cy, 0, v.cx, v.cy, v.R * 1.12), rim = 1 / 1.12;
    a.addColorStop(0, "rgba(90, 170, 200, 0)"); a.addColorStop(rim * 0.9, "rgba(90, 170, 200, 0)");
    a.addColorStop(rim, `rgba(90, 170, 200, ${0.26 * GLOBE_GAIN * (1 - opts.dim)})`); a.addColorStop(1, "rgba(90, 170, 200, 0)");
    ctx.fillStyle = a; ctx.beginPath(); ctx.arc(v.cx, v.cy, v.R * 1.12, 0, 2 * Math.PI); ctx.fill();
  } else {
    ctx.fillStyle = "rgba(5, 12, 18, 0.98)"; ctx.fillRect(0, 0, w, h);
  }

  if (opts.coast > 0) {
    ctx.strokeStyle = `rgba(150, 215, 230, ${0.16 * GLOBE_GAIN * opts.coast})`; ctx.lineWidth = 0.8;
    ctx.beginPath();
    for (const ring of GLOBE_DATA.coast) {
      let pen = false;
      for (const [lon, s, c] of ring) {
        if (globeProject(lon, s, c, out, g)) { if (pen) ctx.lineTo(out[0], out[1]); else ctx.moveTo(out[0], out[1]); pen = true; } else pen = false;
      }
    }
    ctx.stroke();
  }

  let satLon = 0, satLat = 0;
  const sOn = opts.swath;
  if (sOn) {
    [satLon, satLat] = subSatellite(g.sat.u, g.sat.node);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    const trail = [];
    for (let k = 0; k <= 50; k++) {
      const [lo, la] = subSatellite(g.sat.u - (50 - k) * 1.1 * DEG, g.sat.node);
      trail.push(globeProject(lo, Math.sin(la), Math.cos(la), [0, 0, 0], g));
    }
    const width = Math.max(3, 2 * v.R * Math.sin(SWATH_HALF));
    for (const [lw, a] of [[width * 2.4, 0.05], [width, 0.16], [1.2, 0.55]]) {
      ctx.strokeStyle = `rgba(${nr}, ${ng}, ${nb}, ${a})`; ctx.lineWidth = lw; ctx.beginPath();
      let pen = false;
      trail.forEach((p) => { if (p) { if (pen) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]); pen = true; } else pen = false; });
      ctx.stroke();
    }
    const head = globeProject(satLon, Math.sin(satLat), Math.cos(satLat), [0, 0, 0], g);
    if (head) {
      const hg = ctx.createRadialGradient(head[0], head[1], 0, head[0], head[1], 18);
      hg.addColorStop(0, "rgba(255, 236, 255, 1)"); hg.addColorStop(1, `rgba(${nr}, ${ng}, ${nb}, 0)`);
      ctx.fillStyle = hg; ctx.beginPath(); ctx.arc(head[0], head[1], 18, 0, 2 * Math.PI); ctx.fill();
    }
  }

  const P = GLOBE_DATA.pts;
  if (P && opts.points > 0) {
    ctx.globalCompositeOperation = "lighter"; gctx.globalCompositeOperation = "lighter";
    const sS = Math.sin(satLat), cS = Math.cos(satLat), litCos = Math.cos(SWATH_HALF * 1.6);
    const base = Math.max(1, Math.min(4, v.R / 260)), alpha = opts.points * (1 - 0.75 * opts.dim);
    if (!g.buf || g.buf.x.length !== P.n) g.buf = { x: new Float32Array(P.n), y: new Float32Array(P.n), s: new Float32Array(P.n), b: new Uint8Array(P.n), g: new Uint8Array(P.n), order: new Int32Array(P.n), start: new Int32Array(17), gOrder: new Int32Array(P.n) };
    if (!g.lit || g.lit.length !== P.n) g.lit = new Float32Array(P.n).fill(-1e9);
    const B = g.buf, NB = 8, F = opts.focus;
    const fS = F ? Math.sin(F.lat * DEG) : 0, fC = F ? Math.cos(F.lat * DEG) : 0, fL = F ? F.lon * DEG : 0, fCos = F ? Math.cos(F.km / EARTH_KM) : 2;
    let m = 0;
    for (let i = 0; i < P.n; i++) {
      if (!globeProject(P.lon[i], P.sinLat[i], P.cosLat[i], out, g)) continue;
      const x = out[0], y = out[1], cosc = out[2];
      if (x < -8 || y < -8 || x > w + 8 || y > h + 8) continue;
      if (sOn && P.sinLat[i] * sS + P.cosLat[i] * cS * Math.cos(P.lon[i] - satLon) > litCos) g.lit[i] = g.now;
      const near = F && P.sinLat[i] * fS + P.cosLat[i] * fC * Math.cos(P.lon[i] - fL) > fCos ? 1 : 0;
      const flare = sOn ? Math.exp(-(g.now - g.lit[i]) / 1400) : 0, lit = F ? near * F.glow : 0;
      const k = Math.min(1, Math.sqrt(P.km2[i]) / 22), limb = 0.3 + 0.7 * cosc;
      const a = Math.min(0.999, alpha * GLOBE_GAIN * limb * (0.22 + 0.78 * k) * (F && !near ? 1 - 0.55 * F.glow : 1) + 0.55 * lit);
      B.x[m] = x; B.y[m] = y; B.s[m] = base * (0.6 + 0.9 * k) * (1 + 1.2 * flare + 0.3 * lit);
      B.b[m] = flare > 0.25 ? NB + Math.min(NB - 1, (flare * NB) | 0) : (a * NB) | 0;
      B.g[m] = flare > 0.25 ? 2 : k > 0.6 || lit > 0.3 ? 1 : 0;
      m++;
    }
    const NBB = 2 * NB, start = B.start, order = B.order;
    start.fill(0);
    for (let j = 0; j < m; j++) start[B.b[j] + 1]++;
    for (let b = 0; b < NBB; b++) start[b + 1] += start[b];
    const at = start.slice(0, NBB);
    for (let j = 0; j < m; j++) order[at[B.b[j]]++] = j;
    for (let b = 0; b < NBB; b++) {
      if (start[b] === start[b + 1]) continue;
      const lvl = ((b % NB) + 0.5) / NB;
      ctx.fillStyle = b < NB ? `rgba(${fr}, ${fg}, ${fb}, ${lvl})` : `rgba(225, 255, 244, ${Math.min(1, alpha * lvl + 0.2)})`;
      ctx.beginPath();
      for (let q = start[b]; q < start[b + 1]; q++) { const j = order[q], s = B.s[j]; ctx.rect(B.x[j] - s / 2, B.y[j] - s / 2, s, s); }
      ctx.fill();
    }
    let n1 = 0, n2 = m;
    const go = B.gOrder;
    for (let j = 0; j < m; j++) { if (B.g[j] === 1) go[n1++] = j; else if (B.g[j] === 2) go[--n2] = j; }
    for (const [from, to, color] of [[0, n1, `rgba(${fr}, ${fg}, ${fb}, ${0.22 * GLOBE_GAIN * alpha})`], [n2, m, `rgba(175, 250, 225, ${0.55 * alpha})`]]) {
      if (from === to) continue;
      gctx.fillStyle = color; gctx.beginPath();
      for (let q = from; q < to; q++) { const j = go[q], s = B.s[j] * 3; gctx.rect(B.x[j] - s / 2, B.y[j] - s / 2, s, s); }
      gctx.fill();
    }
  }

  const T = GLOBE_DATA.people;
  if (T && opts.people > 0) {
    ctx.globalCompositeOperation = "lighter"; gctx.globalCompositeOperation = "lighter";
    for (let i = 0; i < T.n; i++) {
      const on = opts.pick ? opts.pick[i] : 1;
      if (!on || !globeProject(T.lon[i], T.sinLat[i], T.cosLat[i], out, g)) continue;
      const [x, y, cosc] = out, r = Math.max(1.2, Math.min(9, Math.sqrt(T.pop[i]) / 120)) * Math.max(1, v.R / 400), a = opts.people * on * (0.4 + 0.6 * cosc);
      ctx.fillStyle = `rgba(255, 214, 128, ${Math.min(1, a)})`; ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fill();
      gctx.fillStyle = `rgba(255, 190, 90, ${0.55 * a})`; gctx.beginPath(); gctx.arc(x, y, r * 3, 0, 2 * Math.PI); gctx.fill();
    }
  }
  ctx.globalCompositeOperation = "source-over"; gctx.globalCompositeOperation = "source-over";

  if (opts.ring) globeRing(opts.ring, g);
  if (opts.pin) {
    const p = globeProject(opts.pin.lon * DEG, Math.sin(opts.pin.lat * DEG), Math.cos(opts.pin.lat * DEG), [0, 0, 0], g);
    if (p) {
      const [pr, pg, pb] = GLOBE_RGB.people;
      ctx.fillStyle = `rgba(${pr}, ${pg}, ${pb}, .25)`; ctx.beginPath(); ctx.arc(p[0], p[1], 11, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = `rgb(${pr}, ${pg}, ${pb})`; ctx.beginPath(); ctx.arc(p[0], p[1], 4.5, 0, 2 * Math.PI); ctx.fill();
      ctx.strokeStyle = "rgba(255, 255, 255, .9)"; ctx.lineWidth = 1.5; ctx.stroke();
    }
  }
}

function globeRing({ lon, lat, km }, g = globe) {
  const ctx = g.ctx, a = km / EARTH_KM, p0 = lat * DEG, l0 = lon * DEG;
  ctx.strokeStyle = "rgba(255, 255, 255, .85)"; ctx.lineWidth = 1.2; ctx.setLineDash([3, 3]); ctx.beginPath();
  let pen = false;
  for (let k = 0; k <= 72; k++) {
    const b = (k / 72) * 2 * Math.PI, la = Math.asin(Math.sin(p0) * Math.cos(a) + Math.cos(p0) * Math.sin(a) * Math.cos(b));
    const lo = l0 + Math.atan2(Math.sin(b) * Math.sin(a) * Math.cos(p0), Math.cos(a) - Math.sin(p0) * Math.sin(la));
    const p = globeProject(lo, Math.sin(la), Math.cos(la), [0, 0, 0], g);
    if (p) { if (pen) ctx.lineTo(p[0], p[1]); else ctx.moveTo(p[0], p[1]); pen = true; } else pen = false;
  }
  ctx.stroke(); ctx.setLineDash([]);
}

function equalArea(lon, lat, lon0, lat0, scale) {
  const l = (lon - lon0) * DEG, p = lat * DEG, p0 = lat0 * DEG;
  const k = Math.sqrt(2 / (1 + Math.sin(p0) * Math.sin(p) + Math.cos(p0) * Math.cos(p) * Math.cos(l)));
  return [scale * k * Math.cos(p) * Math.sin(l), -scale * k * (Math.cos(p0) * Math.sin(p) - Math.sin(p0) * Math.cos(p) * Math.cos(l))];
}
