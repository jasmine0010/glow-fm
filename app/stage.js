
const SKY = { g: null, ctx: null, gctx: null, w: 0, h: 0, dpr: 1, last: 0, T: null, metrics: null, cov: null, scratch: null, sy: -1, drawn: false };
const SKY_INK = { water: "#6fe3ef", veil: "#8a969e", nisar: "#e57ae5", dry: "#b9c4cb", rule: "rgba(205, 225, 235, .22)", muted: "#a7b9c5", text: "#d6e1e8" };
const skyTop = () => (innerWidth <= 760 ? 54 : 60);
const skyRect = (id) => { const el = typeof id === "string" ? document.getElementById(id) : id; return el ? el.getBoundingClientRect() : null; };
const pinned = (r) => (r ? clamp01(-r.top / Math.max(1, r.height - innerHeight)) : 0);
const arrival = (r) => (r ? clamp01((innerHeight - r.top) / innerHeight) : 0);
const onScreen = (r) => r && r.bottom > 0 && r.top < innerHeight;
const skyStill = () => reducedMotion();

function skyBox() {
  const w = SKY.w, h = SKY.h;
  return w <= 760 ? { x: 16, y: skyTop() + 20, w: w - 32, h: Math.min(h * 0.44, 360) } : { x: w * 0.45, y: h * 0.17, w: Math.min(w * 0.49, 780), h: h * 0.64 };
}

function skyResize() {
  const c = $("stage-canvas"), gl = $("stage-glow");
  SKY.g ||= makeGlobe();
  globeResize(c, gl, SKY.g);
  Object.assign(SKY, { ctx: SKY.g.ctx, gctx: SKY.g.gctx, w: SKY.g.w, h: SKY.g.h, dpr: SKY.g.dpr });
  SKY.sy = -1;
}

function skyClear() {
  const { ctx, gctx, w, h, dpr } = SKY;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
  gctx.setTransform(0.5, 0, 0, 0.5, 0, 0); gctx.clearRect(0, 0, w, h);
}

function skyPoint(cx, cy, r, slot = 0) {
  const xy = ((SKY.scratch ||= [new Float32Array(2 * PX.N), new Float32Array(2 * PX.N)])[slot]);
  for (let j = 0; j < PX.N; j++) { const a = PX.rnd[j] * 2 * Math.PI * 7.3, d = r * Math.sqrt(PX.rnd2[j]); xy[2 * j] = cx + d * Math.cos(a); xy[2 * j + 1] = cy + d * Math.sin(a); }
  return xy;
}
function skyPixels(box, from, to, q, alpha, color, delay) {
  const ctx = SKY.ctx;
  ctx.save(); ctx.translate(box.x, box.y);
  drawPixels(ctx, from, to, skyStill() ? 1 : q, 1, { alpha, color, size: SKY.w <= 760 ? 2 : 2.2, delay });
  ctx.restore();
}

function journeyView() {
  const top = skyTop(), sw = SKY.w, sh = SKY.h - top;
  const b = sw < 760 ? { R: Math.min(sw * 0.46, sh * 0.3), cx: sw * 0.5, cy: sh * 0.34 } : { R: Math.min(sh * 0.42, sw * 0.3), cx: sw * 0.64, cy: sh * 0.5 };
  return { lon: -105, lat: 10, R: Math.max(1, b.R), cx: b.cx, cy: b.cy + top };
}
function satillaOn(g) {
  const [lon, lat] = SKY.T.center, out = [0, 0, 0];
  return globeProject(lon * DEG, Math.sin(lat * DEG), Math.cos(lat * DEG), out, g) ? out : null;
}

const SKY_LAYERS = { img: {}, key: "" };
const SKY_MASK_A = 0.55;
function skyAct1Layers(box) {
  const L = SKY_LAYERS, F = PX.frame;
  if (!PX.layers || !F) return null;
  for (const k of ["truth", "mask"]) {
    if (L.img[k]) continue;
    const im = (L.img[k] = new Image());
    im.onload = () => { L.key = ""; SKY.drawn = false; };
    im.src = PX.layers[k];
  }
  if (!["truth", "mask"].every((k) => L.img[k].complete && L.img[k].naturalWidth)) return null;
  const f = ActGeo.shape(box.w, box.h, F), [x0, y0] = f(F.w, F.n), [x1, y1] = f(F.e, F.s), key = `${box.w} ${box.h} ${SKY.dpr}`;
  if (L.key !== key) {
    const W = Math.max(1, Math.round((x1 - x0) * SKY.dpr)), H = Math.max(1, Math.round((y1 - y0) * SKY.dpr));
    for (const [k, ink] of [["truth", SKY_INK.water], ["mask", SKY_INK.veil]]) {
      const c = (L[k] ||= document.createElement("canvas")), cx = c.getContext("2d");
      c.width = W; c.height = H;
      cx.imageSmoothingEnabled = true; cx.imageSmoothingQuality = "high"; cx.drawImage(L.img[k], 0, 0, W, H);
      cx.globalCompositeOperation = "source-in"; cx.fillStyle = ink; cx.fillRect(0, 0, W, H);
    }
    L.key = key;
  }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}
function skyLayer(box, r, c, alpha, upto = Infinity) {
  const vis = Math.min(r.w, upto - r.x);
  if (alpha <= 0.01 || vis <= 0) return;
  const ctx = SKY.ctx;
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.drawImage(c, 0, 0, (c.width * vis) / r.w, c.height, box.x + r.x, box.y + r.y, vis, r.h);
  ctx.restore();
}

function skyAct1Key(box, a, sweep) {
  if (a <= 0.02) return;
  const F = PX.frame || PX.box, ctx = SKY.ctx, f = ActGeo.shape(box.w, box.h, F), phone = SKY.w <= 760;
  const kmPx = (f(F.w, F.n - 0.1)[1] - f(F.w, F.n)[1]) / 11.12, km = kmPx * 10 > box.w / 3 ? 5 : 10, len = km * kmPx;
  const base = Math.min(box.h, f(F.e, F.s)[1] + (phone ? 54 : 46));
  const y1 = base - (phone ? 44 : 34), y2 = base - (phone ? 26 : 12), y3 = phone ? base - 8 : y2;
  ctx.save(); ctx.translate(box.x, box.y); ctx.globalAlpha = a; ctx.font = actFont(12); ctx.lineWidth = 1;
  ctx.fillStyle = SKY_INK.muted; ctx.textAlign = "left"; ctx.fillText(`Satilla River, ${fmtDay(SKY.T.time)}`, 0, y1);
  const r = box.w - 1, bl = r - len;
  ctx.strokeStyle = SKY_INK.muted; ctx.beginPath(); ctx.moveTo(bl, y1 - 4); ctx.lineTo(bl, y1); ctx.lineTo(r, y1); ctx.lineTo(r, y1 - 4); ctx.stroke();
  ctx.textAlign = "right"; ctx.fillText(`${km} km`, bl - 8, y1);
  const item = (x, y, ink, text, al, sw = 8, sa = 1) => {
    const sh = sw > 8 ? 10 : 8;
    ctx.globalAlpha = a * al * sa; ctx.fillStyle = ink; ctx.fillRect(x, y - sh, sw, sh);
    ctx.globalAlpha = a * al; ctx.fillStyle = SKY_INK.muted; ctx.textAlign = "left"; ctx.fillText(text, x + sw + 6, y);
    return x + sw + 6 + ctx.measureText(text).width + 22;
  };
  const next = item(0, y2, SKY_INK.water, "Flooded, from the river's gauges and lidar", 1);
  item(phone ? 0 : next, y3, SKY_INK.veil, "The official map's “can't map here” mask", clamp01(sweep / 0.3), 16, SKY_MASK_A + 0.15);
  ctx.restore();
}

function skyBeforeJourney(dt) {
  const g = SKY.g, j = skyRect("journey"), top = skyTop();
  const end = j.top + scrollY - top, u = clamp01(scrollY / Math.max(1, end));
  const r1 = skyRect("act-1"), rw = skyRect("who"), v = journeyView();
  const a = r1 && rw ? clamp01(-r1.top / Math.max(1, rw.top - r1.top - innerHeight)) : 0;
  const b = rw ? clamp01(-rw.top / Math.max(1, rw.height - top)) : 0;
  const out = clamp01((a - 0.05) / 0.3), back = clamp01((b - 0.25) / 0.6), shapeOn = Math.max(0, out - back);
  g.sat = globe.sat;
  if (!L.visible) globeAdvance(dt, !skyStill(), g);
  Object.assign(g.view, v, { cy: lerp(SKY.h + v.R * 0.7, v.cy, ease(clamp01(u * 1.08))) });
  globeDraw({ points: lerp(0.25, 0.05, shapeOn), coast: 0.9 * (1 - 0.8 * shapeOn), people: 0, swath: true, dim: 0.85 * shapeOn }, g);
  if (!SKY.T || a <= 0.02) return;
  const box = skyBox(), here = satillaOn(g) || [box.x + box.w / 2, box.y], shape = layout("shape", box.w, box.h);
  const pt = skyPoint(here[0] - box.x, here[1] - box.y, 3), sweep = b > 0.02 ? 1 : ease(clamp01((a - 0.45) / 0.4));
  const keep = 1 - ease(clamp01((b - 0.02) / 0.3)), lay = skyAct1Layers(box);
  skyAct1Key(box, clamp01((out - 0.6) / 0.4) * keep, sweep);
  const water = () => SKY_INK.water;
  if (lay) skyLayer(box, lay, SKY_LAYERS.truth, 0.55 * clamp01((out - 0.75) / 0.25) * keep);
  if (b > 0.02) {
    skyPixels(box, shape, pt, ease(back), (j2, qq) => (PX.wet[j2] ? 1 - clamp01((qq - 0.85) / 0.15) : 0), water);
  } else {
    skyPixels(box, pt, shape, out, (j2) => (PX.wet[j2] ? 1 : 0), water);
  }
  if (lay) skyLayer(box, lay, SKY_LAYERS.mask, SKY_MASK_A * keep, lerp(lay.x, lay.x + lay.w, sweep));
}

const SKY_PARTS = [
  { id: "act-2", draw: skySignal },
  { id: "why", draw: (p, box) => skyWindowFade(box) },
  { id: "timeline", draw: () => {} },
  { id: "game", draw: () => {} },
  { id: "act-3", draw: skyGather },
  { id: "where", draw: () => {} },
  { id: "run", draw: () => {} },
  { id: "act-4", draw: (p, box) => skyTests(p, box, skyTestsOut()) },
  { id: "deeper", draw: (p, box) => skyTests(1, box, skyTestsOut()) },
];

function skyHistAxes(box, a) {
  if (a <= 0.02) return;
  const ctx = SKY.ctx, g = ActGeo.hist(box.w, box.h), fmt = (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v)}`;
  ctx.save(); ctx.translate(box.x, box.y); ctx.globalAlpha = a; ctx.lineWidth = 1; ctx.font = actFont(12);
  const x0 = Math.round(g.X(0)) + 0.5;
  ctx.setLineDash([3, 4]); ctx.strokeStyle = "rgba(205, 225, 235, .22)"; ctx.beginPath(); ctx.moveTo(x0, g.top); ctx.lineTo(x0, g.base); ctx.stroke(); ctx.setLineDash([]);
  g.rows.forEach((r) => {
    const ink = r.wet ? SKY_INK.water : SKY_INK.dry, mx = Math.round(g.X(r.median)) + 0.5, peakY = r.base - r.height;
    ctx.strokeStyle = SKY_INK.rule; ctx.beginPath(); ctx.moveTo(g.left, r.base + 1.5); ctx.lineTo(g.right, r.base + 1.5); ctx.stroke();
    const nameLeft = mx > (g.left + g.right) / 2;
    ctx.fillStyle = ink; ctx.textAlign = nameLeft ? "left" : "right"; ctx.fillText(r.label, nameLeft ? g.left : g.right, peakY - 16);
    ctx.strokeStyle = ink; ctx.beginPath(); ctx.moveTo(mx, peakY - 4); ctx.lineTo(mx, peakY - 11); ctx.stroke();
    ctx.textAlign = "center"; ctx.fillText(`median ${r.median >= 0 ? "+" : "−"}${Math.abs(r.median).toFixed(1)} dB`, mx, peakY - 16);
  });
  ctx.fillStyle = SKY_INK.muted; ctx.strokeStyle = SKY_INK.rule; ctx.textAlign = "center";
  for (const v of [g.X0, 0, 2, 4, 6, 8]) { const x = Math.round(g.X(v)) + 0.5; ctx.beginPath(); ctx.moveTo(x, g.base + 2); ctx.lineTo(x, g.base + 6); ctx.stroke(); ctx.textAlign = v === g.X0 ? "left" : "center"; ctx.fillText(v === g.X0 ? `≤ ${fmt(v)}` : fmt(v), v === g.X0 ? x - 4 : x, g.base + 19); }
  ctx.textAlign = "center";
  ctx.fillText("Change in radar brightness (dB), each dot one 2.5 ha pixel", (g.left + g.right) / 2, g.base + 38);
  ctx.restore();
}

function skyHistStill(box, a) {
  const H = layout("hist", box.w, box.h);
  skyPixels(box, H, H, 1, (j) => a, (j) => (PX.wet[j] ? SKY_INK.water : SKY_INK.dry));
  skyHistAxes(box, a);
}

function skySignal(p, box) {
  const q = ease(clamp01((p - 0.05) / 0.6)), g = ActGeo.hist(box.w, box.h), out = skyHistOut();
  if (out <= 0) return;
  g.delay ||= Float32Array.from({ length: PX.N }, (_, j) => (g.xy[2 * j] - g.left) / Math.max(1, g.right - g.left));
  const draw = skyStill() ? 1 : clamp01((arrival(skyRect("act-2")) - 0.1) / 0.8) * 1.25;
  const shown = (j) => out * clamp01((draw - g.delay[j]) / 0.25);
  skyPixels(box, layout("line", box.w, box.h), layout("hist", box.w, box.h), q, shown, (j) => (PX.wet[j] ? SKY_INK.water : SKY_INK.dry), g.delay);
  skyHistAxes(box, clamp01((q - 0.5) / 0.5) * out);
}
const skyHistOut = () => 1 - clamp01((arrival(skyRect("why")) - 0.05) / 0.4);

function skyWindowFade(box) {
  const a = skyHistOut();
  if (a > 0) skyHistStill(box, a);
}

function skyGather(p) {
  const r = skyRect("town-globe");
  if (!r) return;
  const grows = ease(clamp01((arrival(r) - 0.1) / 0.45)), a = clamp01((p - 0.05) / 0.3) * (1 - clamp01(grows / 0.15));
  if (a <= 0) return;
  const cx = r.left + (SKY.w <= 760 ? r.width / 2 : r.width * 0.4), cy = Math.min(SKY.h - 40, r.top + r.height / 2), ctx = SKY.ctx;
  ctx.globalAlpha = a; ctx.fillStyle = SKY_INK.nisar; ctx.beginPath(); ctx.arc(cx, cy, 3.5, 0, 2 * Math.PI); ctx.fill();
  SKY.gctx.globalAlpha = a; SKY.gctx.fillStyle = SKY_INK.nisar; SKY.gctx.beginPath(); SKY.gctx.arc(cx, cy, 9, 0, 2 * Math.PI); SKY.gctx.fill();
  ctx.globalAlpha = SKY.gctx.globalAlpha = 1;
}

function skyTownGlobe() {
  const fig = $("town-globe"), r = fig && fig.getBoundingClientRect();
  if (!r || !onScreen(r)) { fig?.classList.remove("live"); return; }
  const grow = ease(clamp01((arrival(r) - 0.1) / 0.45));
  const live = TOWN.g && (grow >= 1 || TOWN.picked || TOWN.fly);
  fig.classList.toggle("live", !!live);
  if (live || grow <= 0) return;
  const g = (SKY.townG ||= makeGlobe());
  const v = TOWN.g ? TOWN.g.view : { lon: -60, lat: 12, R: Math.min(r.width * 0.36, r.height * 0.42), cx: SKY.w <= 760 ? r.width / 2 : r.width * 0.4, cy: r.height / 2 };
  Object.assign(g.view, { lon: v.lon, lat: v.lat, R: Math.max(1, v.R * grow), cx: r.left + v.cx, cy: r.top + v.cy });
  skyGlobeOver(g, { points: grow, coast: 0.9 * grow, people: 0, swath: false, dim: 0 });
}

function skyGlobeOver(g, opts) {
  const spare = (SKY.spare ||= { c: document.createElement("canvas"), gl: document.createElement("canvas") });
  if (spare.c.width !== SKY.ctx.canvas.width || spare.c.height !== SKY.ctx.canvas.height) {
    spare.c.width = SKY.ctx.canvas.width; spare.c.height = SKY.ctx.canvas.height; spare.gl.width = SKY.gctx.canvas.width; spare.gl.height = SKY.gctx.canvas.height;
  }
  Object.assign(g, { ctx: spare.c.getContext("2d"), gctx: spare.gl.getContext("2d"), w: SKY.w, h: SKY.h, dpr: SKY.dpr });
  globeDraw(opts, g);
  SKY.ctx.setTransform(1, 0, 0, 1, 0, 0); SKY.ctx.drawImage(spare.c, 0, 0); SKY.ctx.setTransform(SKY.dpr, 0, 0, SKY.dpr, 0, 0);
  SKY.gctx.setTransform(1, 0, 0, 1, 0, 0); SKY.gctx.drawImage(spare.gl, 0, 0); SKY.gctx.setTransform(0.5, 0, 0, 0.5, 0, 0);
}

function skyWorld() {
  const r = skyRect("run-world");
  if (!r || !onScreen(r) || !GLOBE_DATA.pts) return;
  const ctx = SKY.ctx, P = GLOBE_DATA.pts, e = arrival(r), un = skyStill() ? 1 : ease(clamp01((e - 0.2) / 0.55));
  const W = ActGeo.world(r.width, r.height + 40), g = (SKY.unrollG ||= makeGlobe());
  Object.assign(g.view, { lon: TOWN.g ? TOWN.g.view.lon : -60, lat: 12, R: r.height * 0.48, cx: r.left + r.width / 2, cy: r.top + r.height / 2 });
  const out = [0, 0, 0], s = Math.max(0.8, r.width / 900), step = SKY.w <= 760 ? 2 : 1;
  ctx.fillStyle = "rgba(79, 220, 176, .55)"; ctx.globalAlpha = 0.35 + 0.35 * (1 - un); ctx.beginPath();
  for (let i = 0; i < P.n; i += step) {
    const lon = P.lon[i] / DEG, lat = Math.asin(P.sinLat[i]) / DEG, x1 = r.left + W.X(lon), y1 = r.top + W.Y(lat);
    let x = x1, y = y1;
    if (un < 1) {
      const front = globeProject(P.lon[i], P.sinLat[i], P.cosLat[i], out, g);
      if (!front && un < 0.35) continue;
      if (front) { x = lerp(out[0], x1, un); y = lerp(out[1], y1, un); }
    }
    ctx.rect(x - s / 2, y - s / 2, s, s);
  }
  ctx.fill(); ctx.globalAlpha = 1;
  const F = SKY.cov ? SKY.cov.floods : [], lit = skyStill() ? 1 : clamp01((e - 0.7) / 0.3);
  F.forEach((f, k) => {
    const q = Motion.stagger(lit, k, F.length, 0.7, 0.3);
    if (q <= 0) return;
    const x = r.left + W.X(f.lon), y = r.top + W.Y(f.lat);
    ctx.globalAlpha = q;
    if (f.method_passes) { ctx.fillStyle = SKY_INK.water; ctx.beginPath(); ctx.arc(x, y, 3.4, 0, 2 * Math.PI); ctx.fill(); }
    else { ctx.strokeStyle = "rgba(205, 225, 235, .5)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(x, y, 2.6, 0, 2 * Math.PI); ctx.stroke(); }
    ctx.globalAlpha = 1;
  });
}

const skyTestsOut = () => 1 - clamp01((arrival(skyRect("deeper")) - 0.05) / 0.55);
function skyTests(p, box, fade = 1) {
  if (fade <= 0) return;
  const L4 = ActGeo.tests(box.w, box.h, SKY.metrics), T = SKY.T, ctx = SKY.ctx, latest = L4.groups.length - 1;
  const q = ease(clamp01((p - 0.05) / 0.45)), lit = skyStill() ? 1 : clamp01((p - 0.35) / 0.45), R = SKY.w <= 760 ? 3.5 : 4;
  const placed = [];
  L4.rows = L4.rows.map((d) => ({ ...d })).sort((a, b) => a.x - b.x);
  L4.rows.forEach((d) => {
    const y0 = d.y;
    for (const k of [0, -1, 1, -2, 2]) { d.y = y0 + k * (R + 1); if (!placed.some((o) => o.g === d.g && Math.hypot(o.x - d.x, o.y - d.y) < 2 * R + 1)) break; }
    placed.push(d);
  });
  const me = L4.rows.find(({ r }) => r.site === T.site && r.pair === T.pass && r.method.startsWith("v4, overbank"));
  const dot = (x, y, r) => { ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fill(); };
  ctx.save(); ctx.translate(box.x, box.y);
  ctx.globalAlpha = fade * clamp01(p / 0.2); ctx.lineWidth = 1; ctx.font = actFont(12);
  L4.groups.forEach(([label], g) => {
    const y = L4.top + (g + 0.5) * L4.laneH;
    ctx.fillStyle = g === latest ? SKY_INK.text : SKY_INK.muted; ctx.textAlign = "left"; ctx.fillText(label, 0, y + 4);
    ctx.strokeStyle = "rgba(205, 225, 235, .07)"; ctx.beginPath(); ctx.moveTo(L4.left, y + 0.5); ctx.lineTo(L4.right, y + 0.5); ctx.stroke();
  });
  ctx.strokeStyle = SKY_INK.rule; ctx.beginPath(); ctx.moveTo(L4.left, L4.base + 0.5); ctx.lineTo(L4.right, L4.base + 0.5); ctx.stroke();
  ctx.fillStyle = SKY_INK.muted; ctx.textAlign = "center";
  [0, 0.5, 1].forEach((v) => { const x = Math.round(L4.X(v)) + 0.5; ctx.beginPath(); ctx.moveTo(x, L4.base); ctx.lineTo(x, L4.base + 4); ctx.stroke(); ctx.fillText(String(v), x, L4.base + 18); });
  ctx.fillText("Match score", (L4.left + L4.right) / 2, L4.base + 38);
  let shown = 0, newest = 0;
  L4.rows.forEach(({ r, g, x, y }, k) => {
    if (r === me?.r) return;
    const a = Motion.stagger(lit, k, L4.rows.length, 0.7, 0.3);
    if (a <= 0) return;
    shown++; newest = x;
    ctx.globalAlpha = fade * a * (g === latest ? 1 : 0.75); ctx.fillStyle = g === latest ? SKY_INK.nisar : SKY_INK.muted;
    dot(x, y, R);
  });
  if (shown > (SKY.testsShown || 0) && typeof ambLight === "function") ambLight((newest - L4.left) / Math.max(1, L4.right - L4.left) * 2 - 1);
  SKY.testsShown = shown;
  if (me) {
    const on = skyStill() ? 1 : clamp01((q - 0.75) / 0.25);
    ctx.globalAlpha = fade * on; ctx.fillStyle = SKY_INK.nisar; dot(me.x, me.y, R);
    ctx.globalAlpha = fade * on * 0.55; ctx.strokeStyle = SKY_INK.nisar; ctx.beginPath(); ctx.arc(me.x, me.y, R + 5 + 14 * (1 - ease(on)), 0, 2 * Math.PI); ctx.stroke();
    ctx.globalAlpha = fade * on; ctx.textAlign = "center"; ctx.fillText("Satilla", me.x, me.y - R - 11);
  }
  ctx.globalAlpha = 1;
  ctx.restore();
}

function skyOrbit(dt) {
  const r = document.querySelector("footer.foot")?.getBoundingClientRect();
  if (!r || !onScreen(r)) return false;
  const e = ease(arrival(r)), g = (SKY.orbitG ||= makeGlobe()), R = Math.min(SKY.w, SKY.h) * (SKY.w <= 760 ? 0.32 : 0.26);
  g.sat = globe.sat;
  globeAdvance(dt, !skyStill(), g);
  Object.assign(g.view, { lon: (g.view.lon ?? -60) + (skyStill() ? 0 : dt * 0.003), lat: 10, R, cx: SKY.w * (SKY.w <= 760 ? 0.5 : 0.78), cy: SKY.h - R * 0.35 * e - 10 + R * (1 - e) });
  skyGlobeOver(g, { points: 0.8 * e, coast: 0.8 * e, people: 0, swath: true, dim: 0 });
  return true;
}

const SKY_DRIFT = { x: 0, y: 0, tx: 0, ty: 0 };
addEventListener("pointermove", (e) => {
  if (e.pointerType !== "mouse" || skyStill()) return;
  SKY_DRIFT.tx = (e.clientX / innerWidth - 0.5) * -12; SKY_DRIFT.ty = (e.clientY / innerHeight - 0.5) * -8;
}, { passive: true });
function skyDrift(dt) {
  const k = 1 - Math.exp(-dt / 400), d = SKY_DRIFT;
  d.x += (d.tx - d.x) * k; d.y += (d.ty - d.y) * k;
  if (Math.abs(d.tx - d.x) + Math.abs(d.ty - d.y) > 0.02) { const r = document.documentElement.style; r.setProperty("--drift-x", `${d.x.toFixed(2)}px`); r.setProperty("--drift-y", `${d.y.toFixed(2)}px`); }
}

function skyClips() {
  for (const id of ["waves-stage", "game-stage"]) {
    const el = $(id) || document.querySelector(`.${id}`);
    if (!el) continue;
    const k = skyStill() ? 0 : 1 - ease(clamp01((arrival(el.getBoundingClientRect()) - 0.15) / 0.65));
    el.style.clipPath = k > 0.001 ? `inset(${(k * 30).toFixed(2)}% ${(k * 34).toFixed(2)}% round ${8 + 20 * k}px)` : "";
  }
}

function skyFrameDraw(ts) {
  const dt = Math.min(64, ts - (SKY.last || ts));
  SKY.last = ts;
  if (!SKY.ctx) return;
  skyDrift(dt);
  const j = skyRect("journey"), top = skyTop();
  const during = j && j.top <= top + 1 && j.bottom >= innerHeight - 1;
  const before = j && j.top > top + 1;
  const foot = document.querySelector("footer.foot")?.getBoundingClientRect();
  const moving = (before || onScreen(foot)) && !skyStill();
  if (!moving && scrollY === SKY.sy && SKY.drawn) return;
  SKY.sy = scrollY; SKY.drawn = true;
  skyClips();
  skyClear();
  if (!PX.N) return;
  if (before) { skyBeforeJourney(dt); return; }
  if (during) return;
  const box = skyBox();
  let part = SKY_PARTS[0];
  for (const s of SKY_PARTS) { const r = skyRect(s.id); if (r && r.top < innerHeight * 0.55) part = s; }
  const r = skyRect(part.id);
  part.draw(part.id.startsWith("act-") ? pinned(r) : arrival(r), box);
  skyTownGlobe();
  skyWorld();
  skyOrbit(dt);
}

function skyLoop(ts) {
  requestAnimationFrame(skyLoop);
  if (!document.hidden && SKY.h > 0 && SKY.w > 0) skyFrameDraw(ts);
}

function setupStage(T, metrics) {
  SKY.T = T; SKY.metrics = metrics;
  skyResize();
  let again;
  addEventListener("resize", () => { clearTimeout(again); again = setTimeout(() => { skyResize(); SKY.drawn = false; }, 120); });
  loadGlobeData(small()).then(() => requestAnimationFrame(skyLoop));
}
