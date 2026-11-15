// The one-minute guided tour. Each part sets its whole picture from scratch, so jumping between parts always shows the same thing.
// Every number comes from the same data as the other pages.

const TOUR_STYLE = BASEMAP;
const TOUR_START = [-86, 28.5, -78, 34.5], TOUR_WORLD = [-170, -56, 179, 74];
const stillMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// atlas.js draws its ring on the page's main map.
let map, tourTop;
const tour = { i: 0, t: 0, playing: false, last: null, scenes: [], camera: null, finished: false, lens: { x: 0.5, y: 0.45, r: 0 } };

// ---------- the picture ----------
const BASE_LAYERS = ["photo", "gfm_none", "gfm_excl", "gfm", "atlas", "atlas-pick"];

function showLayers(baseOn, topOn) {
  BASE_LAYERS.forEach((id) => { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", baseOn.includes(id) ? "visible" : "none"); });
  tourTop.getStyle().layers.forEach((l) => { if (l.id !== "img") tourTop.setLayoutProperty(l.id, "visibility", topOn.includes(l.id) ? "visible" : "none"); });
}

function setLens(x, y, r) {
  Object.assign(tour.lens, { x, y, r });
  const stage = $("tour-stage");
  stage.style.setProperty("--lx", `${100 * x}%`);
  stage.style.setProperty("--ly", `${100 * y}%`);
  stage.style.setProperty("--lr", `${Math.round(r)}px`);
}

function lensRadius() {
  const box = $("tour-stage").getBoundingClientRect();
  return Math.max(70, Math.min(150, Math.min(box.width, box.height) * 0.2));
}

const fullRadius = () => { const box = $("tour-stage").getBoundingClientRect(); return Math.hypot(box.width, box.height) * 1.1; };

function setTopMap(mode) {
  // "off" hides the top map, "lens" shows it inside the circle, and "open" shows all of it.
  $("tour-top").style.visibility = mode === "off" ? "hidden" : "visible";
  $("tour-ring").hidden = mode !== "lens";
  if (mode === "open") setLens(0.5, 0.5, fullRadius());
}

function viewPadding() {
  const bar = $("tour-panel").getBoundingClientRect(), small = innerWidth < 700;
  return { top: small ? 58 : 66, bottom: Math.max(40, innerHeight - bar.top + 8), left: small ? 10 : 36, right: small ? 10 : 36 };
}

// Moves the camera. While jumping between parts, or with reduced motion, it goes straight there.
function moveCamera(bounds, ms, animate) {
  tour.camera = { bounds, ends: tour.t + ms };
  map.stop();
  map.fitBounds(bounds, { padding: viewPadding(), duration: animate && !stillMotion() ? ms : 0, essential: true });
}

function resumeCamera() {
  const c = tour.camera;
  if (c && tour.t < c.ends) map.fitBounds(c.bounds, { padding: viewPadding(), duration: stillMotion() ? 0 : c.ends - tour.t, essential: true });
}

function stageXY([lng, lat]) {
  const p = map.project([lng, lat]), box = $("tour-stage").getBoundingClientRect();
  return [p.x / box.width, p.y / box.height];
}

function pathAt(points, f) {
  const at = Math.max(0, Math.min(1, f)) * (points.length - 1), k = Math.min(points.length - 2, Math.floor(at)), u = at - k;
  return [points[k][0] + (points[k + 1][0] - points[k][0]) * u, points[k][1] + (points[k + 1][1] - points[k][1]) * u];
}
const ease = (f) => { const x = Math.max(0, Math.min(1, f)); return x * x * (3 - 2 * x); };

function setWords(caption, note, tag) {
  $("tour-caption").textContent = caption;
  $("tour-note").textContent = note || "";
  $("tour-tag").textContent = tag || "";
  $("tour-tag").hidden = !tag;
  $("tour-chip").textContent = "";
  $("tour-chip").hidden = true;
}

function setChip(text) {
  $("tour-chip").textContent = text;
  $("tour-chip").hidden = !text;
}

// ---------- the script ----------
function buildScenes(manifest, metrics, summary, iquitos) {
  const hero = manifest.hero, audit = metrics.satilla_audit, lead = metrics.overbank[0], [lo, hi] = scoreRange(metrics), yellow = manifest.sites.find((s) => s.timeline), frames = yellow.timeline;
  const heroBounds = [hero.bounds[0], hero.bounds[1] - 0.04, hero.bounds[2], hero.bounds[3] + 0.04];
  const gaugeWord = lead.above_flood === 2 && lead.gauges === 3 ? "Two of three" : `${lead.above_flood} of ${lead.gauges}`;
  const towns = (Math.round(summary.towns.high / 100) * 100).toLocaleString("en-US");
  const iq = iquitos.place, iqBox = [iq.lon - 1.1, iq.lat - 0.8, iq.lon + 1.1, iq.lat + 0.8];
  const label = (f) => {
    const day = new Date(f.time).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
    return f.flagged_ha === 0 ? `${day}: river far past its crest, so no NISAR map` : day;
  };
  const frameLayer = (k) => `y${k}`;
  return [
    { name: "A flooded river", ms: 6000,
      enter(animate) {
        showLayers(["photo"], []);
        setTopMap("off");
        if (animate) map.jumpTo(map.cameraForBounds(TOUR_START, { padding: viewPadding() }));
        moveCamera(heroBounds, 3200, animate);
        setWords(`The Satilla River, Georgia. ${gaugeWord} river gauges are above flood level. From space, it looks like forest.`, `Sentinel-2 photo, taken ${((Date.parse(hero.time) - Date.parse(HERO_PHOTO.time)) / 36e5).toFixed(1)} hours before NISAR's pass.`, `Satellite photo, ${fmtDay(HERO_PHOTO.time)}`);
      } },
    { name: "The lens", ms: 8000,
      enter(animate) {
        showLayers(["photo"], ["photo", "nisar"]);
        moveCamera(heroBounds, 0, false);
        setTopMap("lens");
        const pts = LENS_PATH.map(stageXY);
        setLens(pts[stillMotion() || !animate ? 3 : 0][0], pts[stillMotion() || !animate ? 3 : 0][1], lensRadius());
        this.points = pts;
        setWords("NISAR's long radar waves pass the leaves and bounce off what's underneath.", "NISAR's map isn't a picture of water. It's a radar flood estimate.", "Inside the lens: NISAR, Oct 15");
      },
      tick(f) { if (!stillMotion()) { const [x, y] = pathAt(this.points, ease(f / 0.92)); setLens(x, y, tour.lens.r); } } },
    { name: "All of NISAR's map", ms: 6500,
      enter() {
        showLayers(["photo"], ["photo", "nisar"]);
        moveCamera(heroBounds, 0, false);
        setTopMap("lens");
        this.start = { ...tour.lens, r: lensRadius() };
        if (!this.start.x) this.start = { x: 0.5, y: 0.45, r: lensRadius() };
        setWords("It mapped most of the flooding that river gauges and ground heights estimate, with a method fixed in advance.", "The method was frozen before this river's data was opened.", "NISAR flood map, Oct 15");
        setChip(`Match score ${lead.csi.toFixed(2)} out of 1 · fair test`);
      },
      tick(f) {
        const grow = ease(f / 0.28);
        setLens(this.start.x, this.start.y, this.start.r + (fullRadius() - this.start.r) * grow);
        $("tour-ring").hidden = grow >= 1;
      } },
    { name: "Today's flood map", ms: 6500,
      enter() {
        showLayers(["photo", "gfm_none", "gfm_excl", "gfm"], []);
        setTopMap("off");
        moveCamera(heroBounds, 0, false);
        setWords(`A global flood map's first scene here, on Oct 24, showed ${ha(audit.gfm_on_wet_ha)} of ${ha(audit.estimated_ha)} hectares of estimated flooding.`, "Copernicus GFM had no scene here from Sep 30, and it marks dense forest as ground it can't map. Grey is its own mask, and pale ground had no data.", "Copernicus GFM, Oct 24");
      } },
    { name: "Why forest lights up", ms: 6000,
      enter() {
        showLayers(["photo"], ["photo", "nisar"]);
        moveCamera(heroBounds, 0, false);
        setTopMap("open");
        setWords(`Water usually looks black to radar. Under trees it bounces back, so forest looked about ${iquitos.times.toFixed(1)} times as bright.`, "Measured with the river 0.75 m above the ground, comparing different patches of forest on one pass.", "NISAR flood map, Oct 15");
      } },
    { name: "Following a flood", ms: 8500,
      enter(animate) {
        showLayers([], [frameLayer(0)]);
        setTopMap("open");
        moveCamera(yellow.bounds, 1500, animate);
        setWords("NISAR returns every few days, so a map can follow a flood over time.", "Yellow River, Florida, which helped build the method.");
        this.shown = 0;
        setChip(label(frames[0]));
      },
      tick(f) {
        const k = Math.min(frames.length - 1, Math.floor(Math.max(0, (f - 0.14) / 0.84) * frames.length));
        if (k !== this.shown) { this.shown = k; showLayers([], [frameLayer(k)]); setChip(label(frames[k])); }
      } },
    { name: "Where it falls short", ms: 5500,
      enter() {
        // The last pass with a map, because the final pass has none to show.
        showLayers([], [frameLayer(frames.map((f) => f.flagged_ha > 0).lastIndexOf(true))]);
        setTopMap("open");
        moveCamera(yellow.bounds, 0, false);
        setWords(`It doesn't always work. Fair-test scores ran from ${lo.toFixed(2)} to ${hi.toFixed(2)}, and a lidar map matched the Satilla better.`, "The early passes on this river matched poorly too. A lidar map looks the same on every date, though, so it can't follow a flood.");
      } },
    { name: "The whole world", ms: 6500,
      enter(animate) {
        showLayers(["atlas"], []);
        setTopMap("off");
        moveCamera(TOUR_WORLD, 2600, animate);
        setWords(`This isn't only Georgia. ${(summary.tree_km2 / 1e6).toFixed(1)} million km² of the world's mapped river floodplains sit under trees.`, "From a modelled 100-year flood map and land cover. This shows risk, not flooding.");
      } },
    { name: "A town", ms: 6000,
      enter(animate) {
        showLayers(["atlas", "atlas-pick"], []);
        setTopMap("off");
        atlasRing(iq.lat, iq.lon);
        moveCamera(iqBox, 2400, animate);
        setWords(`About ${towns} towns, home to ${atlasPeople(summary)}, sit beside ground like this. Flood map blank near ${iq.name}? Don't trust it.`, `${pct(iquitos.share, 0)} of the floodplain near ${iq.name}, Peru, is under trees. This describes the nearby ground. It doesn't mean the town floods.`);
      } },
  ];
}

// ---------- playing ----------
function goTo(i, animate) {
  if (animate && tour.i !== i) soundTick(0.03);
  tour.finished = false;
  tour.i = i;
  tour.t = 0;
  $("tour-end").hidden = true;
  $("tour-card").hidden = false;
  $("tour-controls").hidden = false;
  tour.scenes[i].enter(animate);
  renderParts();
}

function finish() {
  tour.finished = true;
  setPlaying(false);
  $("tour-card").hidden = true;
  $("tour-controls").hidden = true;
  $("tour-tag").hidden = true;
  $("tour-end").hidden = false;
  $("tour-end-title").focus({ preventScroll: true });
}

function setPlaying(on) {
  tour.playing = on;
  $("tour-play").textContent = on ? "Pause" : "Play";
  if (on) resumeCamera(); else map.stop();
}

const totalMs = () => tour.scenes.reduce((sum, s) => sum + s.ms, 0);
const doneBefore = (i) => tour.scenes.slice(0, i).reduce((sum, s) => sum + s.ms, 0);

function renderParts() {
  const parts = $("tour-parts");
  if (!parts.children.length) parts.innerHTML = tour.scenes.map((s, k) => `<button type="button" class="tour-part" data-part="${k}" aria-label="Go to part ${k + 1}: ${s.name}"><i></i></button>`).join("");
  [...parts.children].forEach((b, k) => { b.classList.toggle("done", k < tour.i); b.classList.toggle("now", k === tour.i); if (k === tour.i) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current"); if (k !== tour.i) b.firstChild.style.width = k < tour.i ? "100%" : "0"; });
}

function clock() {
  const secs = Math.round((doneBefore(tour.i) + tour.t) / 1000);
  $("tour-clock").textContent = `0:${String(Math.min(59, secs)).padStart(2, "0")}${secs >= 60 ? "+" : ""} / 1:00`;
  const bar = $("tour-parts").children[tour.i];
  if (bar) bar.firstChild.style.width = `${Math.min(100, 100 * tour.t / tour.scenes[tour.i].ms)}%`;
}

function loop(now) {
  if (tour.playing && tour.last !== null) {
    // A slow frame, such as while the map loads a large image, slows the tour down and never skips part of it.
    tour.t += Math.min(now - tour.last, 200);
    const scene = tour.scenes[tour.i];
    if (scene.tick) scene.tick(tour.t / scene.ms);
    clock();
    if (tour.t >= scene.ms) { if (tour.i < tour.scenes.length - 1) goTo(tour.i + 1, true); else finish(); }
  }
  tour.last = now;
  requestAnimationFrame(loop);
}

function jump(i) {
  if (i < 0 || i >= tour.scenes.length) return;
  goTo(i, false);
  const scene = tour.scenes[i];
  if (scene.tick) scene.tick(0);
  clock();
}

function wire() {
  $("tour-play").addEventListener("click", () => setPlaying(!tour.playing));
  $("tour-back").addEventListener("click", () => jump(tour.i - 1));
  $("tour-next").addEventListener("click", () => { if (tour.i === tour.scenes.length - 1) finish(); else jump(tour.i + 1); });
  $("tour-parts").addEventListener("click", (e) => { const b = e.target.closest("[data-part]"); if (b) jump(Number(b.dataset.part)); });
  $("tour-again").addEventListener("click", () => { goTo(0, true); setPlaying(true); $("tour-play").focus({ preventScroll: true }); });
  addEventListener("keydown", (e) => {
    if (tour.finished) return;
    if (e.key === "ArrowRight") { e.preventDefault(); if (tour.i === tour.scenes.length - 1) finish(); else jump(tour.i + 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); jump(tour.i - 1); }
    if (e.key === " " && !e.target.closest("button, a")) { e.preventDefault(); setPlaying(!tour.playing); }
  });
  addEventListener("resize", () => { if (!tour.playing && tour.scenes.length) jump(tour.i); });
}

// ---------- starting ----------
const imageLoaded = (url) => new Promise((resolve) => { const img = new Image(); img.onload = resolve; img.onerror = resolve; img.src = url; });

function addImage(m, id, url, corners, resampling = "nearest") {
  m.addSource(id, { type: "image", url, coordinates: corners });
  m.addLayer({ id, type: "raster", source: id, layout: { visibility: "none" }, paint: { "raster-resampling": resampling, "raster-fade-duration": 0 } });
}

(async function start() {
  const [manifest, metrics, summary] = await Promise.all([fetch("data/manifest.json").then((r) => r.json()), fetch("data/metrics.json").then((r) => r.json()), loadAtlas()]);
  const heldout = await fetch("data/dashboard/heldout.json").then((r) => r.json());
  const hero = manifest.hero, yellow = manifest.sites.find((s) => s.timeline), url = (f) => `data/${hero.site}/${hero.pass}/${f}`;
  const curve = heldout.rivers.find((r) => r.id === hero.site).pairs.find((p) => p.id === hero.pass).drivers.curve, peak = curve.find((p) => p.water_above_ground_m === 0.75);
  const iq = summary.towns.examples.find((e) => e.name === "Iquitos"), got = await atlasLookup(iq.lat, iq.lon);
  const frameUrl = (k) => `data/${yellow.id}/${yellow.timeline[k].pair}/nisar.png`;
  await Promise.race([Promise.all([url(HERO_PHOTO.file), url(hero.layers.nisar), url(hero.layers.gfm_none), url(hero.layers.gfm_excl), url(hero.layers.gfm), ...yellow.timeline.map((_, k) => frameUrl(k))].map(imageLoaded)), new Promise((r) => setTimeout(r, 15000))]);

  const opts = (container) => ({ container, style: TOUR_STYLE, bounds: TOUR_START, attributionControl: { compact: true }, interactive: false, fadeDuration: 0 });
  map = new maplibregl.Map(opts("tour-base"));
  tourTop = new maplibregl.Map(opts("tour-top"));
  tourTop.getCanvas().setAttribute("aria-hidden", "true");
  tourTop.getCanvas().setAttribute("tabindex", "-1");
  map.getCanvas().setAttribute("tabindex", "-1");
  map.on("error", (e) => { if (!e.error || e.error.name !== "AbortError") console.error(e.error || e); });
  tourTop.on("error", (e) => { if (!e.error || e.error.name !== "AbortError") console.error(e.error || e); });
  map.on("move", () => tourTop.jumpTo({ center: map.getCenter(), zoom: map.getZoom() }));
  await Promise.all([new Promise((ok) => map.once("load", ok)), new Promise((ok) => tourTop.once("load", ok))]);

  addImage(map, "photo", url(HERO_PHOTO.file), HERO_PHOTO.corners, "linear");
  addImage(map, "gfm_none", url(hero.layers.gfm_none), hero.corners);
  addImage(map, "gfm_excl", url(hero.layers.gfm_excl), hero.corners);
  addImage(map, "gfm", url(hero.layers.gfm), hero.corners);
  addAtlasLayer(map);
  map.setPaintProperty("atlas", "raster-opacity", 0.9);
  addAtlasPick(map);
  addImage(tourTop, "photo", url(HERO_PHOTO.file), HERO_PHOTO.corners, "linear");
  addImage(tourTop, "nisar", url(hero.layers.nisar), hero.corners);
  yellow.timeline.forEach((_, k) => addImage(tourTop, `y${k}`, frameUrl(k), yellow.corners));

  tour.scenes = buildScenes(manifest, metrics, summary, { place: iq, share: got.share, times: 10 ** (peak.hh_db / 10) });
  wire();
  $("tour-loading").hidden = true;
  $("tour-card").hidden = false;
  $("tour-controls").hidden = false;
  goTo(0, true);
  setPlaying(new URLSearchParams(location.search).get("paused") !== "1");
  requestAnimationFrame(loop);
})().catch((e) => {
  console.error(e);
  $("tour-loading").textContent = "The tour couldn't load. Check your connection and try again.";
});
