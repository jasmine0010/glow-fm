
const STYLE = BASEMAP;
const nothingMapped = (p) => (p.frame || p).flagged_ha === 0;
const signedDb = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)} dB`;

let manifest, metrics;

function addOverlay(m, id, url, coords, visible, opacity = 1) {
  m.addSource(id, { type: "image", url, coordinates: coords });
  m.addLayer({ id, type: "raster", source: id, paint: { "raster-resampling": "nearest", "raster-opacity": opacity, "raster-fade-duration": 0 }, layout: { visibility: visible ? "visible" : "none" } });
}

const passUrl = (site, pass, file) => `data/${site.id}/${pass.id}/${file}`;

function heroViews(hero, a) {
  const photoDay = fmtDay(HERO_PHOTO.time), passDay = fmtDay(hero.time), gfmDay = fmtDay(a.scene_time_utc), gap = calendarDays(hero.time, a.scene_time_utc);
  const hours = (Date.parse(hero.time) - Date.parse(HERO_PHOTO.time)) / 36e5;
  return {
    photo: { tag: `Satellite photo<small>Sentinel-2, ${photoDay}</small>`, layers: [],
      legend: [[PALETTE.nisar, "NISAR flood map, inside the lens"]],
      note: `The photo was taken ${hours.toFixed(1)} hours before NISAR's pass, with river levels about the same. NISAR's map is a radar flood estimate, not a picture of water. The far left is outside this photo.` },
    gfm: { tag: `Official flood map: Copernicus GFM<small>${gfmDay}, ${inWords(gap)} days later</small>`, layers: ["gfm_none", "gfm_excl", "gfm"],
      legend: [["#5a5a5a", "Area GFM says it can't map"], ["#286eff", "GFM flood"], ["#e8d6aa", "No GFM data"], [PALETTE.nisar, "NISAR flood map, inside the lens"]],
      note: `GFM had no picture of this stretch during the crest. Its next one, ${inWords(gap)} days after NISAR's pass, mapped ${ha(a.gfm_on_wet_ha)} ha of flooding here. The days differ, so the two maps aren't scored against each other.` },
    truth: { tag: `River's answer: gauges and lidar<small>${passDay}</small>`, layers: ["truth"],
      legend: [[PALETTE.water, "Flooded, by the river's answer"], [PALETTE.nisar, "NISAR flood map, inside the lens"]],
      note: `The river's answer puts the gauges' water level onto lidar ground height. It's a model, not a photo of water. Both maps show ${passDay}, and scores count ground within 10 km of a gauge.` },
  };
}
let HERO_VIEWS = {};

function setHeroView(key, left) {
  const v = HERO_VIEWS[key];
  $("tag-left").innerHTML = v.tag;
  for (const id of ["gfm_none", "gfm_excl", "gfm", "truth"]) if (left.getLayer(id)) left.setLayoutProperty(id, "visibility", v.layers.includes(id) ? "visible" : "none");
  $("hero-legend").innerHTML = `<span class="legend-items">${v.legend.map(([c, t]) => `<span><i class="swatch" style="background:${c}"></i>${t}</span>`).join("")}<span><i class="swatch dot gauge-swatch"></i>River gauge</span></span>`;
  $("hero-view-note").textContent = v.note;
  document.querySelectorAll(".view-switch button").forEach((b) => { const on = b.dataset.view === key; b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); });
}

function setupLens(left, hero) {
  const stage = $("lens"), ring = $("lens-ring"), hint = $("lens-hint");
  const pos = { x: 0.55, y: 0.5 };
  let mode = "sweep", raf = 0, pts = [];
  const place = () => {
    stage.style.setProperty("--lx", `${100 * pos.x}%`);
    stage.style.setProperty("--ly", `${100 * pos.y}%`);
  };
  const size = () => { const r = stage.getBoundingClientRect(); stage.style.setProperty("--lr", `${Math.round(Math.max(58, Math.min(125, Math.min(r.width, r.height) * 0.2)))}px`); };
  const moveTo = (x, y) => {
    const r = stage.getBoundingClientRect(), lr = parseFloat(stage.style.getPropertyValue("--lr")) || 0;
    const mx = r.width ? Math.min(0.5, (lr + 4) / r.width) : 0, my = r.height ? Math.min(0.5, (lr + 4) / r.height) : 0;
    pos.x = Math.max(mx, Math.min(1 - mx, x)); pos.y = Math.max(my, Math.min(1 - my, y)); place();
  };
  const stopSweep = () => { mode = "user"; cancelAnimationFrame(raf); hint.classList.add("gone"); };
  const fromEvent = (e) => { const r = stage.getBoundingClientRect(); moveTo((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height); };
  size();
  place();
  addEventListener("resize", size);
  stage.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse" || e.target.closest("button:not(.lens-ring), .maplibregl-ctrl")) return;
    stopSweep();
    fromEvent(e);
  });
  ring.addEventListener("pointerdown", (e) => { stopSweep(); ring.setPointerCapture(e.pointerId); });
  ring.addEventListener("pointermove", (e) => { if (ring.hasPointerCapture(e.pointerId)) fromEvent(e); });
  ring.addEventListener("keydown", (e) => {
    const step = 0.04, move = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (!move) return;
    e.preventDefault();
    stopSweep();
    moveTo(pos.x + move[0], pos.y + move[1]);
  });
  const stageXY = ([lng, lat]) => { const p = left.project([lng, lat]), r = stage.getBoundingClientRect(); return [p.x / r.width, p.y / r.height]; };
  const ease = (f) => f * f * (3 - 2 * f);
  const pathAt = (u) => {
    const at = Math.max(0, Math.min(1, u)) * (pts.length - 1), k = Math.min(pts.length - 2, Math.floor(at)), f = at - k;
    return [pts[k][0] + (pts[k + 1][0] - pts[k][0]) * f, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * f];
  };
  const measure = () => { pts = LENS_PATH.slice(0, 5).map(stageXY); };
  const rest = () => stageXY(LENS_PATH[3]);
  let onScreen = true;
  new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; }).observe(stage);
  const sweepFrom = (u, delay) => {
    const to = u > 0.5 ? 0 : 1, ms = 6000 * Math.abs(to - u);
    let t0 = performance.now() + delay, last = null;
    const step = (t) => {
      if (mode !== "sweep") return;
      if (!onScreen) { t0 += t - (last ?? t); last = t; raf = requestAnimationFrame(step); return; }
      last = t;
      const f = Math.max(0, Math.min(1, (t - t0) / Math.max(1, ms)));
      moveTo(...pathAt(u + (to - u) * ease(f)));
      if (f < 1) raf = requestAnimationFrame(step); else sweepFrom(to, 900);
    };
    raf = requestAnimationFrame(step);
  };
  const resume = () => {
    if (mode === "sweep") return;
    mode = "sweep";
    if (!pts.length) return;
    measure();
    if (reducedMotion()) { moveTo(...rest()); return; }
    let u = 0, best = Infinity;
    for (let i = 0; i <= 200; i++) { const [x, y] = pathAt(i / 200), d = (x - pos.x) ** 2 + (y - pos.y) ** 2; if (d < best) { best = d; u = i / 200; } }
    const [x0, y0] = [pos.x, pos.y], [x1, y1] = pathAt(u), t0 = performance.now(), ms = 900;
    const step = (t) => {
      if (mode !== "sweep") return;
      const f = Math.min(1, (t - t0) / ms), e = ease(f);
      moveTo(x0 + (x1 - x0) * e, y0 + (y1 - y0) * e);
      if (f < 1) raf = requestAnimationFrame(step); else sweepFrom(u, 300);
    };
    raf = requestAnimationFrame(step);
  };
  stage.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") resume(); });
  const go = () => {
    measure();
    if (reducedMotion()) { moveTo(...rest()); return; }
    if (mode !== "sweep") return;
    moveTo(...pathAt(0));
    sweepFrom(0, 500);
  };
  if (left.loaded()) go(); else left.once("load", go);
}

function setupFinding() {
  const cue = $("story-cue"), cueOff = () => cue.classList.toggle("gone", scrollY > 60);
  if (cue) { addEventListener("scroll", cueOff, { passive: true }); cueOff(); }
  const hero = manifest.hero, a = metrics.satilla_audit, ob = metrics.overbank[0], [lo, hi] = scoreRange(metrics);
  const row = metrics.held_out.find((r) => r.site === hero.site && r.pair === hero.pass);
  const passDay = fmtDay(hero.time), gfmDay = fmtDay(a.scene_time_utc), gap = calendarDays(hero.time, a.scene_time_utc);
  HERO_VIEWS = heroViews(hero, a);
  const lede = (people) => `When a forest floods, the global flood map can stay blank. ${people ? `Towns home to ${people} sit beside forest like this. ` : ""}NISAR's radar sees through the trees.`;
  $("finding-lede").textContent = lede(null);
  loadAtlas().then((s) => { $("finding-lede").textContent = lede(atlasPeople(s)); });
  countUp($("fact-gfm"), a.estimated_ha ? (100 * a.gfm_on_wet_ha) / a.estimated_ha : 0, (x) => `${Math.round(x)}%`, 1900);
  $("fact-gfm-label").textContent = `No picture of this stretch at the crest. On ${gfmDay}, it mapped ${ha(a.gfm_on_wet_ha)} of the ${ha(a.estimated_ha)} ha the gauges pointed to.`;
  countUp($("fact-nisar"), 100 * row.recall, (x) => `${Math.round(x)}%`, 2250);
  $("fact-nisar-label").textContent = `Found on ${passDay}, near the crest, from one radar pass.`;
  $("finding-fine-facts").textContent = `The official map is Copernicus GFM. On ${gfmDay}, ${inWords(gap)} days after NISAR's pass, it marked ${ha(a.gfm_on_wet_ha)} ha flooded, though the gauges point to ${ha(a.estimated_ha)} ha under water, with the river still at flood level downstream. During the crest it had no picture of this stretch at all. On ${passDay}, NISAR's radar found ${Math.round(100 * row.recall)}% of the flooding the gauges point to, and ${Math.round(100 * row.precision)}% of what it marked was flooded. GLOWfm was fixed before this river's data was opened.`;
  $("finding-limit").innerHTML = `<b>Not always this good.</b> In GLOWfm's latest test, match scores (1 is perfect) on the ${inWords(latestPasses(metrics).length)} passes with enough flooding to judge ran from ${lo.toFixed(2)} to ${hi.toFixed(2)}, and this one ${ob.csi.toFixed(2) === hi.toFixed(2) ? "is the highest" : `is ${ob.csi.toFixed(2)}`}. A lidar height map scored ${ob.lidar_csi.toFixed(2)} here, but it draws the same map every day, flood or not. NISAR shows the flood on the day: <a href="#timeline">watch it move</a>. <a href="evidence.html">See the results</a>`;
  const light = trustLight({ confident: ob.high, rainy: ob.rainy });
  $("hero-trust-why").textContent = `Every NISAR map carries a trust light that says how far to trust it. ${{ green: "This pass's trust light is green.", red: "This pass's trust light is red.", amber: "This pass's trust light is amber.", grey: "This pass has no map." }[light.cls]} ${light.why} ${TRUST_RECORD}`;

  const opts = (container) => ({ container, style: STYLE, bounds: hero.bounds, fitBoundsOptions: { padding: 12 }, attributionControl: { compact: true }, scrollZoom: false, dragRotate: false, pitchWithRotate: false, dragPan: false, touchZoomRotate: false });
  const left = new maplibregl.Map(opts("map-left")), right = new maplibregl.Map(opts("map-right"));
  addInstruments(left, { coords: false, label: "Map of the Satilla River, with a lens showing NISAR's flood map" });
  right.getCanvas().setAttribute("tabindex", "-1");
  right.getCanvas().setAttribute("aria-hidden", "true");
  const url = (f) => `data/${hero.site}/${hero.pass}/${f}`;
  const marks = (m) => hero.gauges.forEach((g) => gaugeMarker(m, g));
  const addPhoto = (m) => { addOverlay(m, "photo", url(HERO_PHOTO.file), HERO_PHOTO.corners, true); m.setPaintProperty("photo", "raster-resampling", "linear"); };
  left.on("load", () => {
    addPhoto(left);
    addOverlay(left, "gfm_none", url(hero.layers.gfm_none), hero.corners, false);
    addOverlay(left, "gfm_excl", url(hero.layers.gfm_excl), hero.corners, false);
    addOverlay(left, "gfm", url(hero.layers.gfm), hero.corners, false);
    addOverlay(left, "truth", url(hero.layers.truth), hero.corners, false);
    setHeroView(document.querySelector(".view-switch button.on").dataset.view, left);
    marks(left);
  });
  right.on("load", () => { addPhoto(right); addOverlay(right, "nisar", url(hero.layers.nisar), hero.corners, true); marks(right); });
  setHeroView("photo", left);
  $("tag-right").innerHTML = `Inside the lens: NISAR radar<small>${passDay}</small>`;
  left.on("move", () => right.jumpTo({ center: left.getCenter(), zoom: left.getZoom() }));
  document.querySelectorAll(".view-switch button").forEach((b) => b.addEventListener("click", () => setHeroView(b.dataset.view, left)));
  setupLens(left, hero);
}

async function setupBands() {
  const b = await fetch("data/story/bands.json").then((r) => r.json());
  const cDay = fmtDay(`${b.cband.date}T12:00Z`), lDay = fmtDay(b.lband.time);
  countWhenSeen($("band-c-num"), b.cband.contrast_db, signedDb, 1500);
  countWhenSeen($("band-l-num"), b.lband.contrast_db, signedDb, 2250);
  $("band-c-label").textContent = `On ${cDay}, Sentinel-1 saw the flooded forest barely brighten`;
  $("band-l-label").textContent = `On ${lDay}, NISAR saw the same forest light up`;
  $("bands-gfm").innerHTML = `That week, the official flood map marked <b>${ha(b.gfm.mapped_ha)} ha</b> flooded. The gauges said <b>${ha(b.gfm.estimated_ha)} ha</b>.`;
  $("bands-read").textContent = `The numbers are how much brighter flooded forest got than dry forest, in C-band (Sentinel-1) and L-band (NISAR). Across ${ha(b.flooded_forest_ha)} ha of flooded forest, C-band barely changed. NISAR's L-band lit up most of it, though not the middle of the river, where its signal stayed flat too. On ${cDay}, the official flood map marked ${ha(b.gfm.mapped_ha)} ha flooded, out of ${ha(b.gfm.estimated_ha)} ha the gauges point to.`;
  const apart = Math.round(Math.abs(Date.parse(b.lband.time) - Date.parse(b.cband.time || `${b.cband.date}T12:00Z`)) / 36e5);
  $("bands-note").textContent = `dB measures radar brightness, and +1 dB is about a quarter brighter. Each map is drawn against its own dry forest, which is what the numbers compare, and both use one color scale, from +1 dB to full at +${WHY_FULL_DB} dB. The rules were written before the Sentinel-1 data was read. One river and one flood, with the two passes about ${apart} hours apart, and this river helped build GLOWfm, so it's a demonstration, not a general test.`;
  $("bands-hear").addEventListener("click", () => {
    const say = (cls, on) => document.querySelector(`.waves-${cls}`).classList.toggle("speaking", on);
    soundEcho(10 ** (b.cband.contrast_db / 10));
    say("c", true); setTimeout(() => say("c", false), 1500);
    setTimeout(() => { soundEcho(10 ** (b.lband.contrast_db / 10)); say("l", true); setTimeout(() => say("l", false), 1500); }, 2300);
  });
  whenNear($("map-why"), () => setupWhyMap(b));
}

const WHY_FULL_DB = 2.5;
function whyTint(img, [r, g, bl]) {
  const c = document.createElement("canvas");
  c.width = img.naturalWidth; c.height = img.naturalHeight;
  const ctx = c.getContext("2d");
  ctx.drawImage(img, 0, 0);
  const d = ctx.getImageData(0, 0, c.width, c.height), p = d.data, k = 3 / (WHY_FULL_DB - 1);
  for (let i = 0; i < p.length; i += 4) {
    const s = Math.min(1, (p[i + 3] / 235) * k);
    p[i] = r; p[i + 1] = g; p[i + 2] = bl; p[i + 3] = Math.round(245 * s);
  }
  ctx.putImageData(d, 0, 0);
  return c;
}

function setupWhyMap(b) {
  const url = (f) => `data/${b.site}/${b.pass}/${f}`;
  const load = (f) => new Promise((ok, fail) => { const im = new Image(); im.onload = () => ok(im); im.onerror = fail; im.src = url(f); });
  const stage = $("waves-stage"), handle = $("waves-handle"), svg = $("waves-svg");
  const m = new maplibregl.Map({ container: "map-why", style: STYLE, bounds: b.bounds, fitBoundsOptions: { padding: 4 }, attributionControl: { compact: true }, interactive: false });
  m.getCanvas().setAttribute("aria-label", "Map of the flooded Pearl River forest. Left of the line, Sentinel-1's radar change; right of it, NISAR's.");
  const lons = b.corners.map((c) => c[0]), west = Math.min(...lons), east = Math.max(...lons);
  let frac = 0.5, cImg = null, lImg = null, canvas = null, phase = 0;
  const compose = () => {
    if (!canvas) return;
    const r = stage.getBoundingClientRect(), mr = m.getContainer().getBoundingClientRect();
    const lng = m.unproject([r.left + frac * r.width - mr.left, mr.height / 2]).lng;
    const col = Math.round(Math.max(0, Math.min(1, (lng - west) / (east - west))) * canvas.width), H = canvas.height, W = canvas.width, ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, W, H);
    if (col > 0) ctx.drawImage(cImg, 0, 0, col, H, 0, 0, col, H);
    if (col < W) ctx.drawImage(lImg, col, 0, W - col, H, col, 0, W - col, H);
    const src = m.getSource("why");
    if (src) { src.play(); m.once("render", () => src.pause()); m.triggerRepaint(); }
  };
  const drawWaves = () => {
    const r = stage.getBoundingClientRect(), x = frac * r.width, L = Math.min(140, r.height / 4), C = L * 5.6 / 24;
    svg.setAttribute("viewBox", `0 0 ${r.width} ${r.height}`);
    svg.innerHTML = `<path class="wv wv-c" d="${wavePath(x - 16, 0, x - 16, r.height, C, 5, phase * 2.2)}"/><path class="wv wv-l" d="${wavePath(x + 16, 0, x + 16, r.height, L, 10, phase)}"/>`;
  };
  const place = () => {
    stage.style.setProperty("--x", `${(100 * frac).toFixed(2)}%`);
    handle.setAttribute("aria-valuenow", String(Math.round(100 * frac)));
    handle.setAttribute("aria-valuetext", `${Math.round(100 * frac)}% Sentinel-1, ${100 - Math.round(100 * frac)}% NISAR`);
    compose();
    drawWaves();
  };
  const fromEvent = (e) => { const r = stage.getBoundingClientRect(); frac = Math.max(0.02, Math.min(0.98, (e.clientX - r.left) / r.width)); place(); };
  stage.addEventListener("pointerdown", (e) => { if (e.target.closest(".maplibregl-ctrl")) return; stage.setPointerCapture(e.pointerId); fromEvent(e); });
  stage.addEventListener("pointermove", (e) => { if (stage.hasPointerCapture(e.pointerId)) fromEvent(e); });
  handle.addEventListener("keydown", (e) => {
    const d = { ArrowLeft: -0.04, ArrowDown: -0.04, ArrowRight: 0.04, ArrowUp: 0.04, Home: -1, End: 1 }[e.key];
    if (d === undefined) return;
    e.preventDefault();
    frac = Math.max(0.02, Math.min(0.98, frac + d));
    place();
  });
  m.on("load", async () => {
    const [c0, l0] = await Promise.all([load(b.layers.cband), load(b.layers.lband)]);
    [cImg, lImg] = [whyTint(c0, [143, 180, 255]), whyTint(l0, [229, 122, 229])];
    const r = stage.getBoundingClientRect(), mr = m.getContainer().getBoundingClientRect();
    const px = lImg.getContext("2d").getImageData(0, 0, lImg.width, lImg.height).data, mass = new Float64Array(lImg.width);
    for (let i = 3, k = 0; i < px.length; i += 4, k++) mass[k % lImg.width] += px[i];
    const half = mass.reduce((t, v) => t + v, 0) / 2;
    let col = 0;
    for (let run = 0; col < mass.length && (run += mass[col]) < half; col++);
    const mid = m.project([west + ((col + 0.5) / lImg.width) * (east - west), (b.bounds[1] + b.bounds[3]) / 2]).x + mr.left - r.left;
    if (r.width > 0) frac = Math.max(0.1, Math.min(0.9, mid / r.width));
    canvas = document.createElement("canvas");
    canvas.width = cImg.width; canvas.height = cImg.height;
    m.addSource("why", { type: "canvas", canvas, coordinates: b.corners, animate: false });
    m.addLayer({ id: "why", type: "raster", source: "why", paint: { "raster-resampling": "nearest", "raster-fade-duration": 0 } });
    addOverlay(m, "truth", url(b.layers.truth), b.corners, $("bands-truth").checked, 0.45);
    place();
  });
  m.on("resize", () => { m.fitBounds(b.bounds, { padding: 4, duration: 0 }); place(); });
  $("bands-truth").addEventListener("change", (e) => { if (m.getLayer("truth")) m.setLayoutProperty("truth", "visibility", e.target.checked ? "visible" : "none"); });
  place();
  visibleLoop(stage, (dt) => { if (reducedMotion()) { drawWaves(); return false; } phase -= dt / 320; drawWaves(); });
}

async function setupWhyCaveat() {
  const [{ rivers: held }, sig] = await Promise.all([fetch("data/dashboard/heldout.json").then((r) => r.json()), figJson("figures/signature.json")]);
  const barely = (id) => held.find((r) => r.id === id).pairs[0].drivers.contrast.hh_below_water_db;
  const day = fmtDay(manifest.hero.time);
  $("why-caveat").textContent = `A figure in the results pools ${inWords(sig.pooled_from.length)} tested passes, with the Satilla on ${day} marked; Act 2's chart shows the Satilla's pixels alone. Both compare different patches of forest at different depths, not one patch as the water rose. This doesn't always happen. On the Pee Dee and lower Sabine, forest the estimate calls flooded barely brightened (${signedDb(barely("pee_dee"))} and ${signedDb(barely("lower_sabine"))}).`;
}

async function setupRunTeaser() {
  const index = await fetch("data/live/index.json").then((r) => r.json());
  const cases = [...currentCases(index)].sort((a, b) => Date.parse(b.wet) - Date.parse(a.wet));
  figJson("figures/coverage.json").then((cov) => {
    const c = cov.summary;
    showCoverage(cov);
    $("run-coverage-more").innerHTML = `Measured over the floods reported up to ${fmtDay(c.checked_utc)}, NISAR's first pass came a median ${c.first_pass_days_median} days after the first report. Its scenes reached NASA's catalog a median ${c.latency_days.median} days after recording, but ${pct(c.latency_days.share_over_7, 0)} took more than a week. In all, ${pct(c.ready_during_flood / c.floods, 0)} of the floods had a scene anyone could use while they were still being reported. <a href="evidence.html#fig-coverage">More in the results</a>.`;
  }).catch(() => {}).finally(() => liveCoverage().then(showCoverage).catch(() => {}));
  const latest = cases[0];
  $("foot-shift").innerHTML = `<b>End of shift.</b> The latest NISAR pass on this site was ${fmtTime(latest.wet)}, over ${esc(latest.place)}. NISAR's orbit repeats every 12 days, so the next shift has already started.`;
}

function showCoverage(cov) {
  const c = cov.summary, n = `${c.covered_by_method_kind} of ${c.floods} floods reported worldwide had a NISAR pass GLOWfm can read`;
  $("hero-status").innerHTML = cov.live ? `<i class="live-dot" aria-hidden="true"></i>Right now, ${n}` : `As of ${fmtDay(c.checked_utc)}, ${n}`;
  $("run-coverage").innerHTML = `Of the ${c.floods} floods reported worldwide in ${c.gdacs_window_days} days, NISAR passed over ${pct(c.covered / c.floods, 0)} while they were still being reported${cov.live ? "" : `, as of ${fmtDay(c.checked_utc)}`}.`;
  SKY.cov = cov; SKY.drawn = false;
}

function setupWhere() {
  loadAtlas().then((s) => {
    const c = s.check;
    const rows = metrics.audit.filter((r) => r.truth_wet_ha >= 100), mask = rows.map((r) => r.wet_share_in_mask);
    $("where-claim").textContent = `The official global flood map, Copernicus GFM, says upfront that it can't map dense forest. In the ${inWords(c.areas.length)} areas we checked, it left out ${pct(c.gfm_excludes_share_under_trees, 0)} of the floodplain under trees, and ${pct(Math.min(...mask), 0)}–${pct(Math.max(...mask), 0)} of the flooding on ${inWords(rows.length)} audited passes over ${inWords(new Set(rows.map((r) => r.site)).size)} Gulf Coast rivers. Worldwide, ${(s.tree_km2 / 1e6).toFixed(1)} million km² of river floodplain is under trees, an area bigger than Greenland, where a flood can hide in plain sight. Check the ground near you.`;
  });
}

const timeline = { site: null, frames: [], i: 0, view: "nisar", timer: null, map: null, ready: false, gauges: null, strip: null };
const frameLayers = (k) => [`t${k}-dhh`, `t${k}-nisar`, `t${k}-not`, `t${k}-truth`];

function showFrameLayers() {
  if (!timeline.ready) return;
  const { map: m, site, i, view } = timeline;
  site.pairs.forEach((p, k) => {
    const visible = { [`t${k}-dhh`]: view === "dhh", [`t${k}-nisar`]: view === "nisar", [`t${k}-not`]: view === "nisar", [`t${k}-truth`]: view === "truth" };
    for (const id of frameLayers(k)) {
      if (!m.getLayer(id)) continue;
      m.setLayoutProperty(id, "visibility", visible[id] ? "visible" : "none");
      m.setPaintProperty(id, "raster-opacity-transition", { duration: reducedMotion() ? 0 : 450, delay: 0 });
      m.setPaintProperty(id, "raster-opacity", k === i ? 1 : 0);
    }
  });
}

const riseOf = (f) => f.stage_rise_m.reduce((a, b) => a + b, 0) / f.stage_rise_m.length;
const mapped = (f) => f.flagged_ha > 0 && f.csi !== null;
const passWay = (pair) => (/\d+A_/.test(pair) ? "ascending pass" : /\d+D_/.test(pair) ? "descending pass" : "pass");

function timeWhy(i) {
  const f = timeline.frames[i], prev = timeline.frames[i - 1], n = f.stage_rise_m.length;
  if (!prev) return `First look. The river is within ${Math.max(...f.stage_rise_m.map(Math.abs)).toFixed(1)} m of its low point, and NISAR maps ${ha(f.flagged_ha)} ha.`;
  const d = riseOf(f) - riseOf(prev), day = fmtDay(prev.time), river = `river ${d >= 0 ? "up" : "down"} ${Math.abs(d).toFixed(1)} m`;
  if (!mapped(f)) return `Since ${day}, ${river}, and now well past its crest at every gauge, so GLOWfm declines to map this pass.`;
  const dA = f.flagged_ha - prev.flagged_ha;
  let s = `Since ${day}, ${river} on average across ${inWords(n)} gauges, and NISAR's flood map ${dA >= 0 ? "grew" : "shrank"} by ${ha(Math.abs(dA))} ha.`;
  if (f.flagged_on_dry_ha > 0.4 * f.flagged_ha) s += " Much of it is on ground the estimate calls dry, because early in the rise this map overreaches.";
  return s;
}

function timeClaim(frames) {
  const steps = frames.slice(1).map((f, k) => [frames[k], f]).filter(([a, b]) => mapped(a) && mapped(b));
  const same = steps.filter(([a, b]) => Math.sign(riseOf(b) - riseOf(a)) === Math.sign(b.flagged_ha - a.flagged_ha)).length;
  const best = frames.filter((f) => f.csi !== null && f.static_csi !== null).sort((a, b) => b.csi - a.csi)[0];
  const lead = same === steps.length ? `Between every pair of mapped passes, NISAR's flood map grew when the river rose and shrank when it fell.` : `On ${same} of ${steps.length} steps between mapped passes, NISAR's flood map moved the same way as the river.`;
  return `${lead} On ${fmtDay(best.time)} it scored ${best.csi.toFixed(2)} where the lidar map alone scored ${best.static_csi.toFixed(2)}, on a river that helped build GLOWfm. Lidar shows where a flood could go. NISAR shows where it is that day.`;
}

function setFrame(i) {
  timeline.i = i;
  const f = timeline.frames[i];
  const strip = $("time-strip");
  strip.setAttribute("aria-valuenow", String(i));
  strip.setAttribute("aria-valuetext", `${fmtTime(f.time)}: NISAR mapped ${ha(f.flagged_ha)} ha`);
  if (timeline.strip) timeline.strip.select(i);
  $("time-date").textContent = fmtTime(f.time);
  $("time-day").textContent = fmtDay(f.time);
  $("time-when").textContent = `${fmtClock(f.time)} · ${passWay(f.pair)}`;
  $("time-why").innerHTML = timeWhy(i) + (f.csi === null ? "" : ` It matches the river's answer at <b>${f.csi.toFixed(2)}</b>, where 1 is perfect.`);
  $("tl-stage").classList.toggle("tl-moving", i > 0);
  const pair = timeline.site.pairs.find((p) => p.id === f.pair);
  const light = trustLight({ mapped: !nothingMapped(f), confident: f.confident, rainy: rainyFrom(pair && pair.drivers.rain) });
  $("time-conf").innerHTML = trustChip(light);
  $("time-trust-why").textContent = `${light.label}. ${light.why}`;
  const names = timeline.site.gauge_points.map((g) => g.name.replace("Yellow River ", "").replace(", FL", ""));
  $("time-gauges").textContent = f.timing.map((t, k) => `${names[k]} ${t}, ${f.stage_rise_m[k] >= 0 ? "+" : ""}${f.stage_rise_m[k].toFixed(1)} m`).join(" · ");
  $("time-flagged").textContent = `${ha(f.flagged_ha)} ha`;
  $("time-confirmed").textContent = `${ha(f.confirmed_ha)} ha`;
  $("time-false").textContent = `${ha(f.flagged_on_dry_ha)} ha`;
  $("time-csi-full").textContent = f.csi === null ? ", and wasn't scored" : `, and matched the river's answer at ${f.csi.toFixed(2)} (95% range ${f.csi_ci95[0].toFixed(2)}–${f.csi_ci95[1].toFixed(2)})`;
  showFrameLayers();
}


function timeProgress() {
  const sec = $("timeline"), r = sec.getBoundingClientRect(), stageH = $("tl-stage").offsetHeight;
  return { p: clamp01(-r.top / Math.max(1, r.height - stageH)), pinned: r.top <= 61 && r.bottom >= innerHeight - 1, r };
}

function timeScrollTo(t, smooth) {
  const [t0, t1] = timeline.span, sec = $("timeline"), span = sec.offsetHeight - $("tl-stage").offsetHeight;
  scrollTo({ top: sec.getBoundingClientRect().top + scrollY + clamp01((t - t0) / (t1 - t0)) * span, behavior: smooth && !reducedMotion() ? "smooth" : "auto" });
}

function timeFrame(dt) {
  const { p, pinned } = timeProgress();
  if (timeline.sp == null || reducedMotion() || Math.abs(p - timeline.sp) > 0.25) timeline.sp = p;
  else timeline.sp += (p - timeline.sp) * (1 - Math.exp(-dt / 240));
  const [t0, t1] = timeline.span, t = t0 + timeline.sp * (t1 - t0), frames = timeline.frames;
  let k = 0;
  while (k < frames.length - 1 && Date.parse(frames[k + 1].time) <= t) k++;
  if (k !== timeline.i) {
    const forward = k > timeline.i;
    setFrame(k);
    if (forward && pinned) { if (frames[k].flagged_ha > 0) soundPing({ gain: 0.07 }); else soundPing({ gain: 0.05, from: 620, to: 300 }); }
  }
  if (timeline.strip) timeline.strip.head(t);
  const snd = timeline.sound;
  if (snd && pinned) {
    const h = Math.max(0, Math.min(snd.hours.length - 1, Math.round((t - snd.hours[0]) / 36e5)));
    riverSound("timeline", (snd.avg[h] - snd.lo) / Math.max(1e-6, snd.hi - snd.lo));
  } else riverSound("timeline", null);
  return Math.abs(p - timeline.sp) > 1e-4;
}

async function setupTimeStrip(site) {
  const gauges = await fetch(`data/${site.gauges}`).then((r) => r.json());
  timeline.gauges = gauges;
  const frames = site.timeline, first = Date.parse(frames[0].time), last = Date.parse(frames[frames.length - 1].time);
  const t0 = first - 2 * 864e5, t1 = last + 2 * 864e5;
  const series = gauges.map((g) => ({ times: g.times.map((x) => Date.parse(/Z$/.test(x) ? x : `${x}Z`)), ft: g.stage_ft }));
  const at = (s, t) => { let k = 0; while (k < s.times.length - 1 && s.times[k + 1] <= t) k++; return s.ft[k]; };
  const rows = series.map((s) => {
    const base = Math.min(...frames.map((f) => at(s, Date.parse(f.time))));
    return s.times.map((t, k) => [t, (s.ft[k] - base) * 0.3048]).filter(([t, v]) => t >= t0 && t <= t1 && Number.isFinite(v));
  });
  const gfm = [...new Set(site.pairs.map((p) => p.gfm_time).filter(Boolean))].map((t) => ({ t: Date.parse(t), who: "gfm", covered: true }));
  const events = [...frames.map((f) => ({ t: Date.parse(f.time), who: "nisar" })), ...gfm];
  const hours = [];
  for (let t = Math.ceil(t0 / 36e5) * 36e5; t <= t1; t += 36e5) hours.push(t);
  const avg = hours.map((t) => mean(series.map((s, k) => (at(s, t) - Math.min(...frames.map((f) => at(s, Date.parse(f.time))))) * 0.3048)));
  timeline.sound = { hours, avg, lo: Math.min(...avg), hi: Math.max(...avg) };
  timeline.span = [t0, t1];
  timeline.strip = passStrip($("time-strip"), { t0, t1, rows, zero: true, events, label: "Time in the flood: drag, or use the arrow keys to step through NISAR's passes",
    key: [["ls-k-gauge", `River level at ${inWords(rows.length)} gauges`], ["ls-k-flood", "Level at the lowest pass"], ["ls-k-nisar", "NISAR passes"], ["ls-k-gfm", "Official map's scenes we compared"]],
    scrub: (t) => timeScrollTo(t, false),
    onKey: (d) => { const k = Math.max(0, Math.min(frames.length - 1, timeline.i + d)); timeScrollTo(Date.parse(frames[k].time) + 6e4, true); } });
  $("time-strip").setAttribute("aria-valuemin", "0");
  $("time-strip").setAttribute("aria-valuemax", String(frames.length - 1));
  timeline.loop?.kick();
  setFrame(timeline.i);
}

function floodExtent(site) {
  const urls = site.pairs.filter((p) => p.layers.truth).map((p) => passUrl(site, p, p.layers.truth));
  const box = (url) => new Promise((done) => {
    const im = new Image();
    im.onload = () => {
      const s = Math.min(1, 800 / Math.max(im.naturalWidth, im.naturalHeight)), w = Math.round(im.naturalWidth * s), h = Math.round(im.naturalHeight * s);
      const c = document.createElement("canvas"); c.width = w; c.height = h;
      const ctx = c.getContext("2d"); ctx.drawImage(im, 0, 0, w, h);
      const d = ctx.getImageData(0, 0, w, h).data;
      let x0 = w, y0 = h, x1 = -1, y1 = -1;
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (d[4 * (y * w + x) + 3] > 40) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
      done(x1 < 0 ? null : [x0 / w, y0 / h, (x1 + 1) / w, (y1 + 1) / h]);
    };
    im.onerror = () => done(null);
    im.src = url;
  });
  return Promise.all(urls.map(box)).then((bs) => {
    bs = bs.filter(Boolean);
    if (!bs.length) return null;
    const fx0 = Math.min(...bs.map((b) => b[0])), fy0 = Math.min(...bs.map((b) => b[1])), fx1 = Math.max(...bs.map((b) => b[2])), fy1 = Math.max(...bs.map((b) => b[3]));
    const [w0, s0, e0, n0] = site.bounds, mx = 0.12 * (fx1 - fx0), my = 0.12 * (fy1 - fy0);
    const lon = (f) => w0 + Math.max(0, Math.min(1, f)) * (e0 - w0), lat = (f) => n0 - Math.max(0, Math.min(1, f)) * (n0 - s0);
    return [[lon(fx0 - mx), lat(fy1 + my)], [lon(fx1 + mx), lat(fy0 - my)]];
  });
}

function setupTimeline() {
  const site = manifest.sites.find((s) => s.timeline);
  timeline.site = site;
  timeline.frames = site.timeline;
  $("time-claim").textContent = timeClaim(site.timeline);
  const n = site.timeline.length, w = boundsWidthKm(site.bounds);
  const days = site.timeline.map((f) => fmtDay(f.time));
  document.querySelectorAll("#time-view button").forEach((b) => b.addEventListener("click", () => {
    timeline.view = b.dataset.view;
    document.querySelectorAll("#time-view button").forEach((x) => { const on = x === b; x.classList.toggle("on", on); x.setAttribute("aria-pressed", String(on)); });
    showFrameLayers();
  }));
  setFrame(0);
  loadFloodRain().then((rain) => {
    const rc = rainCause(rain && rain.rivers[site.id]);
    if (!rc) return;
    const river = site.title.split(",")[0].replace(/\s*\(.*\)$/, "");
    $("time-cause").textContent = rc.little
      ? `Little rain fell before it: ${rc.mm} mm on the ${river}'s catchment in the two weeks to its ${rc.crest} crest, so the river was likely already high (NASA GPM IMERG).`
      : `What drove it: about ${rc.mm} mm of rain fell on the ${river}'s catchment in the two weeks before its ${rc.crest} crest, ${rc.spellMm} mm of it on ${rc.spell} (NASA GPM IMERG).`;
    $("time-cause").hidden = false;
  });
  timeline.span = [Date.parse(site.timeline[0].time) - 2 * 864e5, Date.parse(site.timeline[n - 1].time) + 2 * 864e5];
  setupTimeStrip(site);
  timeline.loop = visibleLoop($("timeline"), timeFrame);
  addEventListener("scroll", () => timeline.loop.kick(), { passive: true });
  new IntersectionObserver((es) => { if (!es.some((e) => e.isIntersecting)) riverSound("timeline", null); }).observe($("timeline"));
  $("time-sound-note").textContent = `With sound on, the water you hear follows the average rise of the ${inWords(site.gauge_points.length)} gauges since the lowest pass as you scroll, and each NISAR pass pings (a low tone when GLOWfm declined to map). It's a sonification of the gauge readings, not a recording.`;
  const first = site.timeline[0], worst = site.timeline.find((f) => f.pair === "076A_oct05"), frozen = site.pairs.find((p) => p.frozen);
  const declined = site.timeline.filter((f) => !mapped(f)).map((f) => fmtDay(f.time));
  $("time-area-note").textContent = `A lidar map gives the same ${ha(first.static_ha)} ha on every date, including ${days[0]}, when the estimate is ${ha(first.confirmed_ha)} ha. NISAR's mapped area rises and falls with the flood, though it over-maps early. Scores here are development numbers, because this river helped build GLOWfm.`;
  $("time-note").textContent = `The one frozen test on this river was an earlier method's on ${fmtDay(frozen.time)}, which scored ${frozen.v3_csi.toFixed(2)}. ${(site.unusable || []).map((u) => `There is no usable pass at the crest, because the ${passDate(u.pair)} pass has ${u.why}.`).join(" ")} On ${fmtDay(worst.time)}, NISAR mapped ${ha(worst.flagged_on_dry_ha)} ha on ground the estimate calls dry, for a score of ${worst.csi.toFixed(2)}, and its trust light is red. ${declined.length ? `On ${declined.join(" and ")} the river is far past its crest at every gauge, so GLOWfm declines to map it.` : ""}`;
  whenNear($("map-time"), () => {
    const pad = () => { const el = $("tl-stage"), w = el.clientWidth, h = el.clientHeight; return small() ? { top: 190, bottom: 210, left: 12, right: 12 } : { top: 70, bottom: Math.min(260, h * 0.34), left: Math.min(w * 0.36, 520), right: 90 }; };
    timeline.map = new maplibregl.Map({ container: "map-time", style: STYLE, bounds: site.bounds, fitBoundsOptions: { padding: pad() }, attributionControl: { compact: true }, scrollZoom: false, dragPan: false, dragRotate: false, touchZoomRotate: false, doubleClickZoom: false });
    let focus = site.bounds;
    floodExtent(site).then((b) => { if (b) { focus = b; timeline.map.fitBounds(focus, { padding: pad(), duration: 0 }); } });
    let again;
    addEventListener("resize", () => { clearTimeout(again); again = setTimeout(() => timeline.map.fitBounds(focus, { padding: pad(), duration: 0 }), 150); });
    addInstruments(timeline.map, { coords: false, label: "Map of the Yellow River flood by date" });
    timeline.map.on("load", () => {
      site.pairs.forEach((p, k) => {
        addOverlay(timeline.map, `t${k}-dhh`, passUrl(site, p, p.layers.dhh), site.corners, false);
        if (p.layers.not_mapped) addOverlay(timeline.map, `t${k}-not`, passUrl(site, p, p.layers.not_mapped), site.corners, false);
        addOverlay(timeline.map, `t${k}-nisar`, passUrl(site, p, p.layers.nisar), site.corners, false);
        addOverlay(timeline.map, `t${k}-truth`, passUrl(site, p, p.layers.truth), site.corners, false);
      });
      timeline.ready = true;
      showFrameLayers();
    });
  });
}

function setupResultsRead() {
  const judged = judgedPasses(metrics), latest = latestPasses(metrics), [lo, hi] = scoreRange(metrics);
  const obJudged = metrics.overbank.filter((r) => r.judgeable), failed = judged.filter((r) => r.method.startsWith("v4, median")).map((r) => r.csi), strong = latest.filter((r) => r.csi >= 0.6).length;
  $("results-read").textContent = `In GLOWfm's latest test, ${inWords(strong)} of the ${inWords(latest.length)} passes with enough flooding to judge scored 0.60 or higher, and the scores ran from ${lo.toFixed(2)} to ${hi.toFixed(2)}. An earlier test of the same method failed on ${inWords(failed.length)} rivers, at ${Math.min(...failed).toFixed(2)}–${Math.max(...failed).toFixed(2)}. In the latest test, a lidar map with no radar did about as well (${mean(obJudged.map((r) => r.lidar_csi)).toFixed(2)} against NISAR's ${mean(obJudged.map((r) => r.csi)).toFixed(2)}), and the estimate uses the same lidar, which favors it. Radar's clear extra is showing what's flooded on a given date.`;
  figJson("figures/elevation.json").then((e) => {
    $("results-read").textContent += ` Most of the world has no lidar. In a frozen test on ${inWords(e.rows.length)} of these US passes, NISAR averaged ${e.means.nisar_with_fabdem.toFixed(2)} using global elevation data with the trees removed (FABDEM), against ${e.means.nisar_with_lidar.toFixed(2)} with lidar and ${e.means.nisar_with_copernicus.toFixed(2)} with treetop heights.`;
  }).catch(() => {});
}

function setupReveal() {
  if (reducedMotion()) return;
  document.documentElement.classList.add("js-reveal");
  const reveal = () => {
    const left = [...document.querySelectorAll(".reveal:not(.in)")];
    left.forEach((el) => { if (el.getBoundingClientRect().top < innerHeight * 0.92) el.classList.add("in"); });
    if (!left.length) { removeEventListener("scroll", reveal); removeEventListener("resize", reveal); }
  };
  addEventListener("scroll", reveal, { passive: true });
  addEventListener("resize", reveal, { passive: true });
  reveal();
}

loadData().then(([m, k]) => {
  manifest = m; metrics = k;
  setupFinding(); setupLantern(manifest, metrics); setupGame(manifest, metrics); setupBands(); setupWhyCaveat(); setupRunTeaser(); setupActs(metrics); setupTimeline(); setupReveal(); setupResultsRead(); setupWhere(); setupCharts(manifest, metrics); mountFigures();
  setupOrbit();
});
