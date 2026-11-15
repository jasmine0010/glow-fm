// GLOWfm story page, one night with NISAR: the blank map and the lens, the journey (lantern.js, globe.js), Beat the
// satellite (game.js), the mission console for Run it yourself (live.html), the two waves, the night log of a flood,
// your town on the night globe (where.js) and the logbook. Caveats sit in each part's "fine print" panel. Every number,
// date and count on the page is computed from the data files; only outside facts (NISAR's orbit, Greenland) are typed.

const STYLE = BASEMAP;
const nothingMapped = (p) => (p.frame || p).flagged_ha === 0;
const isoOfDate = (d) => `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}T12:00:00Z`;
const signedDb = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)} dB`;

let manifest, metrics;

function addOverlay(m, id, url, coords, visible, opacity = 1) {
  m.addSource(id, { type: "image", url, coordinates: coords });
  m.addLayer({ id, type: "raster", source: id, paint: { "raster-resampling": "nearest", "raster-opacity": opacity, "raster-fade-duration": 0 }, layout: { visibility: visible ? "visible" : "none" } });
}

const passUrl = (site, pass, file) => `data/${site.id}/${pass.id}/${file}`;

// ---------- the finding ----------
// The legend colours for the official map's layers are the ones baked into its images.
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
  let touched = false;
  const place = () => {
    stage.style.setProperty("--lx", `${100 * pos.x}%`);
    stage.style.setProperty("--ly", `${100 * pos.y}%`);
  };
  const size = () => { const r = stage.getBoundingClientRect(); stage.style.setProperty("--lr", `${Math.round(Math.max(58, Math.min(125, Math.min(r.width, r.height) * 0.2)))}px`); };
  // The whole ring stays inside the map, so on a narrow phone map the sweep never shows half a lens.
  const moveTo = (x, y) => {
    const r = stage.getBoundingClientRect(), lr = parseFloat(stage.style.getPropertyValue("--lr")) || 0;
    const mx = r.width ? Math.min(0.5, (lr + 4) / r.width) : 0, my = r.height ? Math.min(0.5, (lr + 4) / r.height) : 0;
    pos.x = Math.max(mx, Math.min(1 - mx, x)); pos.y = Math.max(my, Math.min(1 - my, y)); place();
  };
  const stopSweep = () => { touched = true; hint.classList.add("gone"); };
  const fromEvent = (e) => { const r = stage.getBoundingClientRect(); moveTo((e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height); };
  size();
  place();
  addEventListener("resize", size);
  // A mouse carries the lens around. A finger drags it, so the page can still scroll.
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
  // For anyone who can't or doesn't want to drag, one button shows the whole map.
  $("lens-all").addEventListener("click", (e) => {
    const open = stage.classList.toggle("lens-open");
    stopSweep();
    e.target.textContent = open ? "Back to the lens" : "Show all of NISAR's map";
    e.target.setAttribute("aria-pressed", String(open));
  });
  const stageXY = ([lng, lat]) => { const p = left.project([lng, lat]), r = stage.getBoundingClientRect(); return [p.x / r.width, p.y / r.height]; };
  const go = () => {
    const pts = LENS_PATH.map(stageXY);
    if (reducedMotion()) { moveTo(...pts[3]); return; }
    moveTo(...pts[0]);
    const start = performance.now() + 500, ms = 6000;
    const step = (t) => {
      if (touched) return;
      const f = Math.max(0, Math.min(1, (t - start) / ms)), eased = f * f * (3 - 2 * f), at = eased * (pts.length - 1), k = Math.min(pts.length - 2, Math.floor(at)), u = at - k;
      moveTo(pts[k][0] + (pts[k + 1][0] - pts[k][0]) * u, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * u);
      if (f < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  if (left.loaded()) go(); else left.once("load", go);
}

function setupFinding() {
  const hero = manifest.hero, a = metrics.satilla_audit, ob = metrics.overbank[0], [lo, hi] = scoreRange(metrics);
  const row = metrics.held_out.find((r) => r.site === hero.site && r.pair === hero.pass);
  const passDay = fmtDay(hero.time), gfmDay = fmtDay(a.scene_time_utc), gap = calendarDays(hero.time, a.scene_time_utc);
  HERO_VIEWS = heroViews(hero, a);
  const lede = (people) => `When a forest floods, the global flood map can stay blank. ${people ? `Towns home to ${people} sit beside forest like this. ` : ""}NISAR's radar sees through the trees.`;
  $("finding-lede").textContent = lede(null);
  loadAtlas().then((s) => { $("finding-lede").textContent = lede(atlasPeople(s)); });
  countUp($("fact-gfm"), a.gfm_on_wet_ha, (x) => `${ha(x)} ha`);
  $("fact-gfm-label").textContent = `flooded on the official map on ${gfmDay}. The gauges said ${ha(a.estimated_ha)} ha.`;
  countUp($("fact-nisar"), 100 * row.recall, (x) => `${Math.round(x)}%`, 1400);
  $("fact-nisar-label").textContent = `of the flooding found by NISAR's radar on ${passDay}, near the crest.`;
  $("finding-fine-facts").textContent = `The official map is Copernicus GFM. On ${gfmDay}, ${inWords(gap)} days after NISAR's pass, it marked ${ha(a.gfm_on_wet_ha)} ha flooded, though the gauges point to ${ha(a.estimated_ha)} ha under water, with the river still at flood level downstream. During the crest it had no picture of this stretch at all. On ${passDay}, NISAR's radar found ${Math.round(100 * row.recall)}% of the flooding the gauges point to, and ${Math.round(100 * row.precision)}% of what it marked was flooded. GLOWfm was fixed before this river's data was opened.`;
  $("finding-limit").innerHTML = `<b>Not always this good.</b> Across the ${judgedPasses(metrics).length} fair tests on US rivers with enough flooding to judge, match scores (1 is perfect) ran from ${lo.toFixed(2)} to ${hi.toFixed(2)}, and this one is ${ob.csi.toFixed(2)}. A lidar height map scored ${ob.lidar_csi.toFixed(2)} here, but it draws the same map every day, flood or not. NISAR shows the flood on the day: <a href="#timeline">watch it move</a>. <a href="evidence.html">See the results</a>`;
  const light = trustLight({ confident: ob.high, rainy: ob.rainy });
  $("hero-trust-why").textContent = `Every NISAR map carries a trust light that says when to rely on it. ${{ green: "This pass's trust light is green.", red: "This pass's trust light is red.", amber: "This pass's trust light is amber.", grey: "This pass has no map." }[light.cls]} ${light.why} ${TRUST_RECORD}`;

  const opts = (container) => ({ container, style: STYLE, bounds: hero.bounds, fitBoundsOptions: { padding: 12 }, attributionControl: { compact: true }, scrollZoom: false, dragRotate: false, pitchWithRotate: false, dragPan: false, touchZoomRotate: false });
  const left = new maplibregl.Map(opts("map-left")), right = new maplibregl.Map(opts("map-right"));
  addInstruments(left, { coords: false, label: "Map of the Satilla River, with a lens showing NISAR's flood map" });
  // One map for keyboards and screen readers; the other only repeats it.
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

// ---------- two waves on one forest (research/C_BAND_RESULTS.md) ----------
async function setupBands() {
  const b = await fetch("data/story/bands.json").then((r) => r.json());
  const cDay = fmtDay(`${b.cband.date}T12:00Z`), lDay = fmtDay(b.lband.time);
  countWhenSeen($("band-c-num"), b.cband.contrast_db, signedDb, 900);
  countWhenSeen($("band-l-num"), b.lband.contrast_db, signedDb, 1400);
  $("band-c-label").textContent = `On ${cDay}, Sentinel-1 saw the flooded forest barely brighten`;
  $("band-l-label").textContent = `On ${lDay}, NISAR saw the same forest light up`;
  $("bands-gfm").innerHTML = `That week, the official flood map marked <b>${ha(b.gfm.mapped_ha)} ha</b> flooded. The gauges said <b>${ha(b.gfm.estimated_ha)} ha</b>.`;
  $("bands-read").textContent = `The numbers are how much brighter flooded forest got than dry forest, in C-band (Sentinel-1) and L-band (NISAR). Across ${ha(b.flooded_forest_ha)} ha of flooded forest, C-band barely changed. NISAR's L-band lit up most of it, though not the middle of the river, where its signal stayed flat too. On ${cDay}, the official flood map marked ${ha(b.gfm.mapped_ha)} ha flooded, out of ${ha(b.gfm.estimated_ha)} ha the gauges point to.`;
  const apart = Math.round(Math.abs(Date.parse(b.lband.time) - Date.parse(b.cband.time || `${b.cband.date}T12:00Z`)) / 36e5);
  $("bands-note").textContent = `dB measures radar brightness, and +1 dB is about a quarter brighter. Each map is drawn against its own dry forest, which is what the numbers compare. The rules were written before the Sentinel-1 data was read. One river and one flood, with the two passes about ${apart} hours apart, and this river helped build GLOWfm, so it's a demonstration, not a general test.`;
  $("bands-hear").addEventListener("click", () => {
    const say = (cls, on) => document.querySelector(`.waves-${cls}`).classList.toggle("speaking", on);
    soundEcho(10 ** (b.cband.contrast_db / 10));
    say("c", true); setTimeout(() => say("c", false), 1500);
    setTimeout(() => { soundEcho(10 ** (b.lband.contrast_db / 10)); say("l", true); setTimeout(() => say("l", false), 1500); }, 2300);
  });
  whenNear($("map-why"), () => setupWhyMap(b));
}

// One map of the flooded forest. Left of the line is Sentinel-1's change, right of it NISAR's; both images share one
// grid, so a single canvas is redrawn from the two as the line moves. The waves along it are drawn to scale (5.6 : 24).
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
    [cImg, lImg] = await Promise.all([load(b.layers.cband), load(b.layers.lband)]);
    canvas = document.createElement("canvas");
    canvas.width = cImg.naturalWidth; canvas.height = cImg.naturalHeight;
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

// The caveat in Why NISAR's fine print (heldout.json and the figure data).
async function setupWhyCaveat() {
  const [{ rivers: held }, sig] = await Promise.all([fetch("data/dashboard/heldout.json").then((r) => r.json()), figJson("figures/signature.json")]);
  const barely = (id) => held.find((r) => r.id === id).pairs[0].drivers.contrast.hh_below_water_db;
  const day = fmtDay(manifest.hero.time);
  $("why-caveat").textContent = `Fig. 2 in the results pools ${inWords(sig.pooled_from.length)} tested passes, with the Satilla on ${day} marked; Act 2's chart shows the Satilla's pixels alone. Both compare different patches of forest at different depths, not one patch as the water rose. This doesn't always happen. On the Pee Dee and lower Sabine, forest the estimate calls flooded barely brightened (${signedDb(barely("pee_dee"))} and ${signedDb(barely("lower_sabine"))}).`;
}

// ---------- the mission console for Run it yourself ----------
async function setupRunTeaser() {
  const index = await fetch("data/live/index.json").then((r) => r.json());
  const cases = [...currentCases(index)].sort((a, b) => Date.parse(b.wet) - Date.parse(a.wet));
  $("run-board").insertAdjacentHTML("beforeend", floodBoard(cases, { short: true }));
  // How often, and how soon, NISAR saw this season's reported floods (Fig. 11 in the results).
  // How often NISAR sees the floods reported now: the saved count first (scripts/build_coverage.py), then the live one
  // (livefloods.js) once every flood is in. The arrival-time figures need NASA's insert dates, so they stay the saved ones.
  figJson("figures/coverage.json").then((cov) => {
    const c = cov.summary;
    showCoverage(cov);
    $("run-coverage-more").innerHTML = `Measured over the floods reported up to ${fmtDay(c.checked_utc)}, NISAR's first pass came a median ${c.first_pass_days_median} days after the first report. Its scenes reached NASA's catalog a median ${c.latency_days.median} days after recording, but ${pct(c.latency_days.share_over_7, 0)} took more than a week. In all, ${pct(c.ready_during_flood / c.floods, 0)} of the floods had a scene anyone could use while they were still being reported. <a href="evidence.html#fig11">Fig. 11</a>`;
  }).catch(() => {}).finally(() => liveCoverage().then(showCoverage).catch(() => {}));
  const latest = cases[0];
  $("foot-shift").innerHTML = `<b>End of shift.</b> The latest NISAR pass on this site was ${fmtTime(latest.wet)}, over ${esc(latest.place)}. NISAR's orbit repeats every 12 days, so the next shift has already started.`;
}

// The story's count of reported floods NISAR saw: "Right now" only when it's the live count, else dated.
function showCoverage(cov) {
  const c = cov.summary, n = `${c.covered_by_method_kind} of ${c.floods} floods reported worldwide had a NISAR pass GLOWfm can read`;
  $("hero-status").innerHTML = cov.live ? `<i class="live-dot" aria-hidden="true"></i>Right now, ${n}` : `As of ${fmtDay(c.checked_utc)}, ${n}`;
  $("run-coverage").innerHTML = `Of the ${c.floods} floods reported worldwide in ${c.gdacs_window_days} days, NISAR passed over ${pct(c.covered / c.floods, 0)} while they were still being reported${cov.live ? "" : `, as of ${fmtDay(c.checked_utc)}`}.`;
  drawToolMap(cov);
}

// The dashboard card's map: every reported flood, by whether NISAR passed over it, on Act 3's world map. Drawn once, then
// redrawn in place when the live count replaces the saved one.
const TOOL_MAP = { cov: null, inst: null };
async function drawToolMap(cov) {
  TOOL_MAP.cov = cov;
  await loadGlobeData(small());
  const F = cov.floods, ready = F.filter((f) => f.method_passes > 0).length, passed = F.filter((f) => f.passes > 0 && !f.method_passes).length;
  if (TOOL_MAP.cov !== cov) return;   // a newer count arrived while the globe data loaded
  $("tool-dash-key").innerHTML = mapLegend([["flood", `NISAR passed, with a scene GLOWfm reads (${ready})`], ["town", `NISAR passed, another kind of scene (${passed})`], ["ring", `No pass yet (${F.length - ready - passed})`]], `Floods GDACS reported in ${cov.summary.gdacs_window_days} days`);
  if (TOOL_MAP.inst) { TOOL_MAP.inst.redraw(); return; }
  TOOL_MAP.inst = Motion.instrument($("tool-dash-map"), (ctx, t, w, h) => {
    const F = TOOL_MAP.cov.floods, g = ActGeo.world(w, h + 40), P = GLOBE_DATA.pts, s = Math.max(0.7, w / 900);
    ctx.fillStyle = "rgba(79, 220, 176, .12)"; ctx.beginPath();
    if (P) for (let i = 0; i < P.n; i++) ctx.rect(g.X(P.lon[i] / DEG) - s / 2, g.Y(Math.asin(P.sinLat[i]) / DEG) - s / 2, s, s);
    ctx.fill();
    F.forEach((f, k) => {
      const q = Motion.stagger(t, k, F.length, 0.7, 0.3);
      if (q <= 0) return;
      const x = g.X(f.lon), y = g.Y(f.lat);
      ctx.globalAlpha = q;
      if (f.method_passes) { ctx.fillStyle = "#6fe3ef"; ctx.beginPath(); ctx.arc(x, y, 3.2, 0, 2 * Math.PI); ctx.fill(); }
      else if (f.passes) { ctx.fillStyle = "#ffc98a"; ctx.beginPath(); ctx.arc(x, y, 2.6, 0, 2 * Math.PI); ctx.fill(); }
      else { ctx.strokeStyle = "rgba(205, 225, 235, .55)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(x, y, 2.6, 0, 2 * Math.PI); ctx.stroke(); }
      ctx.globalAlpha = 1;
    });
  }, { ms: 1800 });
}

// ---------- your town: the fine print (the journey gives the worldwide numbers) ----------
function setupWhere() {
  loadAtlas().then((s) => {
    const c = s.check;
    const rows = metrics.audit.filter((r) => r.truth_wet_ha >= 100), mask = rows.map((r) => r.wet_share_in_mask);
    $("where-claim").textContent = `The official global flood map, Copernicus GFM, says upfront that it can't map dense forest. In the ${inWords(c.areas.length)} areas we checked, it left out ${pct(c.gfm_excludes_share_under_trees, 0)} of the floodplain under trees, and ${pct(Math.min(...mask), 0)}–${pct(Math.max(...mask), 0)} of the flooding on ${inWords(rows.length)} audited passes over ${inWords(new Set(rows.map((r) => r.site)).size)} Gulf Coast rivers. Worldwide, ${(s.tree_km2 / 1e6).toFixed(1)} million km² of river floodplain is under trees, an area bigger than Greenland, where a flood can hide in plain sight. Check the ground near you.`;
  });
}

// ---------- the night log: a flood through time ----------
const timeline = { site: null, frames: [], i: 0, view: "nisar", timer: null, map: null, ready: false, gauges: null, strip: null };
const frameLayers = (k) => [`t${k}-dhh`, `t${k}-nisar`, `t${k}-not`, `t${k}-truth`];

function showFrameLayers() {
  if (!timeline.ready) return;
  const { map: m, site, i, view } = timeline;
  site.pairs.forEach((p, k) => {
    const visible = { [`t${k}-dhh`]: view === "dhh", [`t${k}-nisar`]: view === "nisar", [`t${k}-not`]: view === "nisar", [`t${k}-truth`]: view === "truth" };
    for (const id of frameLayers(k)) if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", k === i && visible[id] ? "visible" : "none");
  });
}

// The driver behind each pass: how far the river moved since the last pass, against how NISAR's map moved.
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
  $("tl-stage").classList.toggle("tl-moving", i > 0);   // like the journey: the heading steps aside once the flood moves
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


// ---------- the pinned night log: scrolling moves through the flood's time ----------
function timeProgress() {
  const sec = $("timeline"), r = sec.getBoundingClientRect(), stageH = $("tl-stage").offsetHeight;
  return { p: clamp01(-r.top / Math.max(1, r.height - stageH)), pinned: r.top <= 61 && r.bottom >= innerHeight - 1, r };
}

// Scroll the page to a moment in the flood (the strip and the arrow keys use this).
function timeScrollTo(t, smooth) {
  const [t0, t1] = timeline.span, sec = $("timeline"), span = sec.offsetHeight - $("tl-stage").offsetHeight;
  scrollTo({ top: sec.getBoundingClientRect().top + scrollY + clamp01((t - t0) / (t1 - t0)) * span, behavior: smooth && !reducedMotion() ? "smooth" : "auto" });
}

function timeFrame(dt) {
  const { p, pinned } = timeProgress();
  if (timeline.sp == null || reducedMotion() || Math.abs(p - timeline.sp) > 0.25) timeline.sp = p;
  else timeline.sp += (p - timeline.sp) * (1 - Math.exp(-dt / 240));
  const [t0, t1] = timeline.span, t = t0 + timeline.sp * (t1 - t0), frames = timeline.frames;
  // The map shows NISAR's latest pass so far; before the first, the first.
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
  return Math.abs(p - timeline.sp) > 1e-4;   // sleep once it has caught up; scrolling wakes it
}

// The strip under the map: the river at each gauge as a rise above its level at the lowest pass (only one of the
// gauges has a flood stage, so flood level can't be drawn for all of them), NISAR's passes and the official map's scenes.
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
  // The water sound follows the gauges' average rise since the lowest pass, across this flood's range.
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
    // The river sits in the open part of the screen, clear of the words on the left and the numbers along the bottom.
    const pad = () => { const el = $("tl-stage"), w = el.clientWidth, h = el.clientHeight; return small() ? { top: 190, bottom: 210, left: 12, right: 12 } : { top: 70, bottom: Math.min(260, h * 0.34), left: Math.min(w * 0.36, 520), right: 90 }; };
    timeline.map = new maplibregl.Map({ container: "map-time", style: STYLE, bounds: site.bounds, fitBoundsOptions: { padding: pad() }, attributionControl: { compact: true }, scrollZoom: false, dragPan: false, dragRotate: false, touchZoomRotate: false, doubleClickZoom: false });
    let again;
    addEventListener("resize", () => { clearTimeout(again); again = setTimeout(() => timeline.map.fitBounds(site.bounds, { padding: pad(), duration: 0 }), 150); });
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

// ---------- the logbook ----------
// The Proof's reading of every test (the proof card above plots them).
function setupResultsRead() {
  const judged = judgedPasses(metrics);
  const obJudged = metrics.overbank.filter((r) => r.judgeable), failed = judged.filter((r) => r.method.startsWith("v4, median")).map((r) => r.csi), strong = judged.filter((r) => r.csi >= 0.6).length;
  $("results-read").textContent = `${strong} of ${judged.length} passes scored 0.60 or higher, and on ${inWords(failed.length)} rivers GLOWfm failed, at ${Math.min(...failed).toFixed(2)}–${Math.max(...failed).toFixed(2)}. In the latest test, a lidar map with no radar did about as well (${mean(obJudged.map((r) => r.lidar_csi)).toFixed(2)} against NISAR's ${mean(obJudged.map((r) => r.csi)).toFixed(2)}), and the estimate uses the same lidar, which favors it. Radar's clear extra is showing what's flooded on a given date.`;
  // Most rivers have no lidar: the frozen bare-earth test (scores only; research/BARE_EARTH_RESULTS.md).
  figJson("figures/elevation.json").then((e) => {
    $("results-read").textContent += ` Most of the world has no lidar. In a frozen test on ${inWords(e.rows.length)} of these US passes, NISAR averaged ${e.means.nisar_with_fabdem.toFixed(2)} using global elevation data with the trees removed (FABDEM), against ${e.means.nisar_with_lidar.toFixed(2)} with lidar and ${e.means.nisar_with_copernicus.toFixed(2)} with treetop heights.`;
  }).catch(() => {});
}

// Sections rise into view once, as they arrive. A plain scroll check, not an observer, so a section can never stay
// hidden: anything at or above the fold shows.
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
