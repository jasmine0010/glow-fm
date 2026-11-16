
const GAME_COLORS = { water: [0, 200, 220], you: [255, 180, 90], nisar: [214, 58, 214], paint: "rgba(255, 180, 90, 0.72)", ground: [205, 219, 226] };
const game = { key: null, map: null, paint: null, glow: null, result: null, tool: "paint", painted: 0, done: false, show: "you", me: null, nisar: null, sweeping: false };

const hex = (c) => `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
const mercY = (lat) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));

async function loadGameKey(meta) {
  const img = new Image();
  await new Promise((ok, fail) => { img.onload = ok; img.onerror = fail; img.src = `data/${meta.file}`; });
  const c = document.createElement("canvas");
  c.width = meta.cols; c.height = meta.rows;
  const ctx = c.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(img, 0, 0);
  const d = ctx.getImageData(0, 0, meta.cols, meta.rows).data, n = meta.cols * meta.rows;
  const scored = new Uint8Array(n), wet = new Uint8Array(n), nisar = new Uint8Array(n);
  for (let i = 0; i < n; i++) { scored[i] = d[4 * i] > 127; wet[i] = d[4 * i + 1] > 127; nisar[i] = d[4 * i + 2] > 127; }
  return { ...meta, scored, wet, nisar, n };
}

function scoredBox(key) {
  let c0 = key.cols, c1 = 0, r0 = key.rows, r1 = 0;
  for (let i = 0; i < key.n; i++) {
    if (!key.scored[i]) continue;
    const r = Math.floor(i / key.cols), c = i - r * key.cols;
    if (c < c0) c0 = c; if (c > c1) c1 = c; if (r < r0) r0 = r; if (r > r1) r1 = r;
  }
  return { c0, c1, r0, r1 };
}
const keyLat = (key, row) => { const [[, n], , , [, s]] = key.corners, yN = mercY(n), yS = mercY(s); return (2 * Math.atan(Math.exp(yN - (row / key.rows) * (yN - yS))) - Math.PI / 2) * 180 / Math.PI; };
const keyLon = (key, col) => { const [[w], [e]] = key.corners; return w + (col / key.cols) * (e - w); };
function scoredBounds(key) {
  const { c0, c1, r0, r1 } = scoredBox(key);
  return [keyLon(key, c0), keyLat(key, r1 + 1), keyLon(key, c1 + 1), keyLat(key, r0)];
}

function gradeMap(key, marked) {
  let found = 0, missed = 0, dry = 0;
  for (let i = 0; i < key.n; i++) {
    if (!key.scored[i]) continue;
    if (key.wet[i]) { if (marked[i]) found++; else missed++; } else if (marked[i]) dry++;
  }
  return { found, missed, dry, csi: found / Math.max(1, found + missed + dry), share: found / Math.max(1, found + missed), onDry: found + dry ? dry / (found + dry) : 0 };
}

function paintedMask() {
  const { width, height } = game.paint, d = game.paint.getContext("2d").getImageData(0, 0, width, height).data, out = new Uint8Array(width * height);
  for (let i = 0; i < out.length; i++) out[i] = d[4 * i + 3] > 20;
  return out;
}

function resultImage(view) {
  const key = game.key, img = game.result.getContext("2d").createImageData(key.cols, key.rows), d = img.data;
  const mine = view === "you" ? game.me.mask : key.nisar, marker = view === "you" ? GAME_COLORS.you : GAME_COLORS.nisar;
  for (let i = 0; i < key.n; i++) {
    if (!key.scored[i]) continue;
    const r = Math.floor(i / key.cols), col = i - r * key.cols;
    let c = null, a = 235;
    if (view === "truth") { if (key.wet[i]) c = GAME_COLORS.water; else { c = GAME_COLORS.ground; a = 34; } }
    else if (key.wet[i]) { if (mine[i]) c = GAME_COLORS.water; else if ((col + r) % 7 < 2) { c = GAME_COLORS.water; a = 205; } }
    else if (mine[i] && col % 5 < 2 && r % 5 < 2) { c = marker; a = 245; }
    if (c) { d[4 * i] = c[0]; d[4 * i + 1] = c[1]; d[4 * i + 2] = c[2]; d[4 * i + 3] = a; }
  }
  return img;
}

function drawResult(view) {
  game.result.getContext("2d").putImageData(resultImage(view), 0, 0);
  refresh("game-result");
}

function refresh(id) {
  const src = game.map && game.map.getSource(id);
  if (!src) return;
  src.play();
  game.map.once("render", () => src.pause());
  game.map.triggerRepaint();
}

function refreshGlow() {
  const g = game.glow.getContext("2d");
  g.clearRect(0, 0, game.glow.width, game.glow.height);
  g.filter = "blur(5px)";
  g.drawImage(game.paint, 0, 0);
  g.filter = "none";
  refresh("game-glow");
}

function lineupIntro() {
  const row = (who, color) => `<div class="qn" style="--c:${color}"><span class="qn-k">${who}</span><b class="qn-n">?</b></div>`;
  return `<div class="game-scores">${row("You", "var(--people-ink)")}${row("Official flood map", "var(--official-ink)")}${row("NISAR radar", "var(--nisar-ink)")}</div>`;
}

function gameIntro() {
  $("game-side").innerHTML = `<h3>Your turn</h3>
    <p>Paint over the forest where you think the river spread. Water follows the low ground beside the channel, but under the trees you can't see it.</p>
    ${lineupIntro()}
    <p class="game-buttons"><button type="button" class="btn-primary" id="game-grade" disabled>Grade my map</button> <button type="button" class="btn-quiet" id="game-skip">Just show me</button></p>
    <p class="note" id="game-progress">Paint at least a little to be graded.</p>`;
  $("game-grade").addEventListener("click", () => grade());
  $("game-skip").addEventListener("click", () => grade(true));
}

function setShow(view) {
  game.show = view;
  document.querySelectorAll("#game-view button").forEach((b) => { const on = b.dataset.show === view; b.classList.toggle("on", on); b.setAttribute("aria-pressed", String(on)); });
  for (const id of ["game-paint", "game-glow"]) if (game.map.getLayer(id)) game.map.setLayoutProperty(id, "visibility", "none");
  drawResult(view);
  const key = $("game-key");
  if (!key) return;
  key.innerHTML = view === "truth"
    ? `<span><i class="swatch sw-found"></i>Flooded, by the river's answer</span><span><i class="swatch" style="background:rgba(205,219,226,.4)"></i>Dry ground that counts</span>`
    : `<span><i class="swatch sw-found"></i>Found</span><span><i class="swatch sw-missed"></i>Missed</span><span><i class="swatch sw-dry sw-dry-${view}"></i>Marked, but dry</span>`;
}

function sweep(img, done) {
  const key = game.key, m = game.map, beam = $("game-beam"), box = $("game-map");
  if (reducedMotion() || !m.getSource("game-result")) { game.result.getContext("2d").putImageData(img, 0, 0); refresh("game-result"); done(); return; }
  game.sweeping = true;
  const dpr = Math.min(2, devicePixelRatio || 1), W = box.clientWidth, H = box.clientHeight;
  Object.assign(beam.style, { left: `${box.offsetLeft}px`, top: `${box.offsetTop}px`, width: `${W}px`, height: `${H}px` });
  beam.width = Math.round(W * dpr); beam.height = Math.round(H * dpr);
  const bctx = beam.getContext("2d"), rctx = game.result.getContext("2d"), pctx = game.paint.getContext("2d"), gctx = game.glow.getContext("2d");
  bctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  rctx.clearRect(0, 0, key.cols, key.rows);
  const sources = ["game-result", "game-paint", "game-glow"].map((id) => m.getSource(id)).filter(Boolean);
  sources.forEach((s) => s.play());
  const { r0, r1 } = scoredBox(key), lonMid = (keyLon(key, 0) + keyLon(key, key.cols)) / 2, ms = 3200, t0 = performance.now();
  const yTop = m.project([lonMid, keyLat(key, r0)]).y, yBot = m.project([lonMid, keyLat(key, r1 + 1)]).y;
  const rowAt = (y) => Math.max(r0, Math.min(r1 + 1, Math.round(r0 + ((y - yTop) / Math.max(1, yBot - yTop)) * (r1 + 1 - r0))));
  const beamAt = (y, a) => {
    bctx.clearRect(0, 0, W, H);
    if (a <= 0) return;
    bctx.globalAlpha = a;
    const trail = bctx.createLinearGradient(0, y, 0, y + 90);
    trail.addColorStop(0, "rgba(229, 122, 229, .32)"); trail.addColorStop(1, "rgba(229, 122, 229, 0)");
    bctx.fillStyle = trail; bctx.fillRect(0, y, W, 90);
    bctx.fillStyle = "rgba(255, 236, 255, .95)"; bctx.fillRect(0, y - 1, W, 2);
    bctx.globalAlpha = 1;
  };
  soundChirp(ms);
  const frame = (t) => {
    const f = Math.min(1, (t - t0) / ms), y = H + 2 - (H + 4) * f, row = rowAt(y);
    rctx.putImageData(img, 0, 0, 0, row, key.cols, key.rows - row);
    pctx.clearRect(0, row, key.cols, key.rows - row);
    gctx.clearRect(0, row, key.cols, key.rows - row);
    beamAt(y, 1);
    if (f < 1) { requestAnimationFrame(frame); return; }
    sources.forEach((s) => s.pause());
    game.sweeping = false;
    soundPing({ gain: 0.09 });
    done();
    const t1 = performance.now(), fade = (tt) => { const a = 1 - Math.min(1, (tt - t1) / 700); beamAt(y, a); if (a > 0) requestAnimationFrame(fade); };
    requestAnimationFrame(fade);
  };
  requestAnimationFrame(frame);
}

function gameOverlap(me, n, skipped) {
  const cv = $("game-tally");
  if (!cv) return;
  const rows = [];
  if (!skipped) { const flood = me.found + me.missed || 1; rows.push({ label: "You", color: "255, 201, 138", found: me.found / flood, map: (me.found + me.dry) / flood, csi: me.csi }); }
  rows.push({ label: "NISAR", color: "229, 122, 229", found: n.share, map: n.share / Math.max(1e-9, 1 - n.onDry), csi: n.csi });
  const biggest = Math.max(1, ...rows.map((r) => r.map));
  Motion.instrument(cv, (ctx, t, w, h) => {
    const colW = w / rows.length, R = Math.min(colW * 0.28, (h - 50) / 2) / Math.sqrt(biggest);
    rows.forEach((r, k) => {
      const rf = R, rm = R * Math.sqrt(r.map), cy = 26 + Math.max(rf, rm), cx = k * colW + colW / 2;
      const target = Motion.distanceForOverlap(rf, rm, r.found * R * R * Math.PI), far = rf + rm + 14;
      const d = Motion.lerp(far, target, Motion.ease(Motion.clamp((t - k * 0.12) / 0.75)));
      const fx = cx - d / 2 + (rm - rf) / 4, mx = fx + d;
      ctx.save();
      ctx.globalCompositeOperation = "lighter";
      ctx.fillStyle = "rgba(111, 227, 239, .28)"; ctx.beginPath(); ctx.arc(fx, cy, rf, 0, 2 * Math.PI); ctx.fill();
      ctx.fillStyle = `rgba(${r.color}, .3)`; ctx.beginPath(); ctx.arc(mx, cy, Math.max(0.5, rm), 0, 2 * Math.PI); ctx.fill();
      ctx.restore();
      ctx.lineWidth = 1.2;
      ctx.strokeStyle = "#6fe3ef"; ctx.beginPath(); ctx.arc(fx, cy, rf, 0, 2 * Math.PI); ctx.stroke();
      ctx.strokeStyle = `rgb(${r.color})`; ctx.beginPath(); ctx.arc(mx, cy, Math.max(0.5, rm), 0, 2 * Math.PI); ctx.stroke();
      const shared = Motion.circleOverlap(rf, rm, d), match = shared / (Math.PI * rf * rf + Math.PI * rm * rm - shared);
      const shown = t >= 1 ? r.csi : match;
      ctx.textAlign = "center"; ctx.fillStyle = `rgb(${r.color})`; ctx.font = "600 12px 'IBM Plex Sans', system-ui, sans-serif";
      ctx.fillText(r.label, cx, 14);
      ctx.font = "600 20px 'Space Grotesk', 'IBM Plex Sans', system-ui, sans-serif"; ctx.fillStyle = "#f2f6f8";
      ctx.fillText(`match ${shown.toFixed(2)}`, cx, h - 4);
    });
  }, { ms: 3500, start: "none" }).play();
}

function grade(skipped = false) {
  if (!game.key || game.sweeping) return;
  game.done = true;
  game.me = { mask: skipped ? new Uint8Array(game.key.n) : paintedMask() };
  Object.assign(game.me, gradeMap(game.key, game.me.mask));
  const n = game.nisar, me = game.me, pc = (x) => `${Math.round(100 * x)}%`;
  const beat = !skipped && me.csi > n.csi;
  const photo = "From a photo, flooded forest looks like any other forest.";
  const verdict = skipped ? "Here's how NISAR did."
    : beat ? "You beat the satellite. Few people do."
    : !me.found ? `None of your paint landed on the flood. ${photo}`
    : me.share >= n.share ? `You covered more of the flood than NISAR, but ${pc(me.onDry)} of your paint landed on dry ground, so your match is lower. ${photo}`
    : `NISAR found ${(n.share / me.share).toFixed(1)} times as much of the flood as you did${me.onDry > 0.5 ? ", and most of your paint landed on dry ground" : ""}. ${photo}`;
  $("game-tools").hidden = true;
  $("game-help").hidden = true;
  $("game-side").innerHTML = `<h3>${skipped ? "The answer" : "NISAR is passing over…"}</h3>${lineupIntro()}`;
  const view = skipped ? "nisar" : "you";
  sweep(resultImage(view), () => {
    $("game-side").innerHTML = `<h3>${skipped ? "The answer" : "How you did"}</h3>
      <p class="game-verdict">${verdict}</p>
      <div class="game-scores">
        ${skipped ? "" : `<div class="qn" style="--c: var(--people-ink)"><span class="qn-k">You</span><b class="qn-n" id="gs-you">${pc(me.share)}</b><span class="qn-u">of the flood found · ${pc(me.onDry)} on dry ground</span></div>`}
        <div class="qn" style="--c: var(--nisar-ink)"><span class="qn-k">NISAR radar</span><b class="qn-n" id="gs-nisar">${pc(n.share)}</b><span class="qn-u">of the flood found · ${pc(n.onDry)} on dry ground</span></div>
      </div>
      <figure class="game-tally"><canvas id="game-tally" role="img" aria-label="Circles to scale: the flood the gauges point to, and the map. ${skipped ? "" : `Your match: ${me.csi.toFixed(2)}. `}NISAR's match: ${n.csi.toFixed(2)}."></canvas></figure>
      <p class="game-trust">${trustChip(trustLight({ confident: n.confident, rainy: n.rainy }))}</p>
      <div class="game-key" id="game-key"></div>
      <details class="fine"><summary>The fine print</summary><div class="fine-body"><p>The official flood map had no picture of this river during the crest; ${n.gfmLater}.</p><p>Match (1 is perfect) is the score used in every test here. A lidar height map scored ${n.lidar.toFixed(2)} here, but it draws the same map every day, flood or not.</p></div></details>
      <p class="game-buttons"><button type="button" class="btn" id="game-again">Try again</button></p>`;
    if (!skipped) countUp($("gs-you"), 100 * me.share, (x) => `${Math.round(x)}%`, 1500);
    countUp($("gs-nisar"), 100 * n.share, (x) => `${Math.round(x)}%`, 2000);
    gameOverlap(me, n, skipped);
    $("game-again").addEventListener("click", resetGame);
    $("game-view").hidden = false;
    document.querySelector('#game-view [data-show="you"]').hidden = skipped;
    setShow(view);
  });
}

function resetGame() {
  game.done = false;
  game.painted = 0;
  for (const c of [game.paint, game.glow, game.result]) c.getContext("2d").clearRect(0, 0, c.width, c.height);
  for (const id of ["game-paint", "game-glow"]) if (game.map && game.map.getLayer(id)) game.map.setLayoutProperty(id, "visibility", "visible");
  refresh("game-paint"); refresh("game-glow"); refresh("game-result");
  $("game-tools").hidden = false;
  $("game-view").hidden = true;
  $("game-help").hidden = false;
  document.querySelector('#game-view [data-show="you"]').hidden = false;
  gameIntro();
}

function setupPainting(meta) {
  const m = game.map, box = m.getCanvasContainer(), [[w, nLat], [e], , [, sLat]] = meta.corners;
  const yN = mercY(nLat), yS = mercY(sLat), ctx = game.paint.getContext("2d");
  const toGrid = (ev) => {
    const r = box.getBoundingClientRect(), ll = m.unproject([ev.clientX - r.left, ev.clientY - r.top]);
    return [(ll.lng - w) / (e - w) * meta.cols, (yN - mercY(ll.lat)) / (yN - yS) * meta.rows];
  };
  const radius = () => 14 * meta.cols / Math.max(1, m.project([e, nLat]).x - m.project([w, nLat]).x);
  let last = null;
  const stroke = (p) => {
    ctx.globalCompositeOperation = game.tool === "erase" ? "destination-out" : "source-over";
    ctx.strokeStyle = ctx.fillStyle = GAME_COLORS.paint;
    ctx.lineCap = "round";
    ctx.lineWidth = 2 * radius();
    ctx.beginPath();
    if (last) { ctx.moveTo(...last); ctx.lineTo(...p); ctx.stroke(); } else { ctx.arc(p[0], p[1], radius(), 0, 2 * Math.PI); ctx.fill(); }
    last = p;
    if (game.tool === "paint") game.painted++;
    $("game-help").hidden = true;
    const btn = $("game-grade");
    if (btn && game.painted > 3) { btn.disabled = false; $("game-progress").textContent = "Paint as much as you like, then grade it."; }
  };
  box.addEventListener("pointerdown", (ev) => {
    if (game.done || ev.button > 0 || ev.target.closest(".maplibregl-ctrl, .maplibregl-marker")) return;
    ev.preventDefault();
    box.setPointerCapture(ev.pointerId);
    last = null;
    m.getSource("game-paint").play();
    stroke(toGrid(ev));
  });
  box.addEventListener("pointermove", (ev) => { if (!game.done && box.hasPointerCapture(ev.pointerId)) stroke(toGrid(ev)); });
  const end = (ev) => { if (box.hasPointerCapture(ev.pointerId)) box.releasePointerCapture(ev.pointerId); last = null; refresh("game-paint"); refreshGlow(); };
  box.addEventListener("pointerup", end);
  box.addEventListener("pointercancel", end);
  document.querySelectorAll("#game-tools [data-tool]").forEach((b) => b.addEventListener("click", () => {
    game.tool = b.dataset.tool;
    document.querySelectorAll("#game-tools [data-tool]").forEach((x) => { const on = x === b; x.classList.toggle("on", on); x.setAttribute("aria-pressed", String(on)); });
  }));
  $("game-clear").addEventListener("click", () => { ctx.clearRect(0, 0, game.paint.width, game.paint.height); game.painted = 0; refresh("game-paint"); refreshGlow(); const btn = $("game-grade"); if (btn) btn.disabled = true; });
  document.querySelectorAll("#game-view [data-show]").forEach((b) => b.addEventListener("click", () => setShow(b.dataset.show)));
}

async function setupGame(manifest, metrics) {
  const hero = manifest.hero, row = metrics.held_out.find((r) => r.site === hero.site && r.pair === hero.pass), ob = metrics.overbank.find((r) => r.site === hero.site && r.pair === hero.pass);
  const a = metrics.satilla_audit, later = calendarDays(hero.time, a.scene_time_utc);
  game.nisar = { csi: ob.csi, share: row.recall, onDry: 1 - row.precision, lidar: ob.lidar_csi, confident: ob.high, rainy: ob.rainy, gfmLater: `${inWords(later)} days later: ${ha(a.gfm_on_wet_ha)} ha flooded` };
  const before = calendarDays(HERO_PHOTO.time, hero.time);
  $("game-fine-photo").textContent = `The photo of the ${siteTitle(hero.site).replace(", GA", ", Georgia")} is Sentinel-2 from ${fmtDay(HERO_PHOTO.time)}, ${before === 1 ? "the day" : `${inWords(before)} days`} before NISAR's ${fmtDay(hero.time)} pass.`;
  gameIntro();
  whenNear($("game-map"), async () => {
    const meta = (await fetch("data/story/charts.json").then((r) => r.json())).game;
    const make = () => { const c = document.createElement("canvas"); c.width = meta.cols; c.height = meta.rows; return c; };
    game.paint = make();
    game.glow = make();
    game.result = make();
    const [key] = await Promise.all([loadGameKey(meta)]);
    game.key = key;
    const frame = scoredBounds(key);
    const m = new maplibregl.Map({ container: "game-map", style: STYLE, bounds: frame, fitBoundsOptions: { padding: 24 }, attributionControl: { compact: true },
      interactive: false });
    game.map = m;
    if ("ResizeObserver" in window) new ResizeObserver(() => { m.resize(); m.fitBounds(frame, { padding: 24, duration: 0 }); }).observe($("game-map"));
    addInstruments(m, { coords: false });
    m.on("load", () => {
      addOverlay(m, "photo", `data/${hero.site}/${hero.pass}/${HERO_PHOTO.file}`, HERO_PHOTO.corners, true);
      m.setPaintProperty("photo", "raster-resampling", "linear");
      m.addSource("game-result", { type: "canvas", canvas: game.result, coordinates: meta.corners, animate: false });
      m.addLayer({ id: "game-result", type: "raster", source: "game-result", paint: { "raster-resampling": "nearest", "raster-fade-duration": 0 } });
      m.addSource("game-glow", { type: "canvas", canvas: game.glow, coordinates: meta.corners, animate: false });
      m.addLayer({ id: "game-glow", type: "raster", source: "game-glow", paint: { "raster-fade-duration": 0, "raster-opacity": 0.9 } });
      m.addSource("game-paint", { type: "canvas", canvas: game.paint, coordinates: meta.corners, animate: false });
      m.addLayer({ id: "game-paint", type: "raster", source: "game-paint", paint: { "raster-fade-duration": 0 } });
      hero.gauges.forEach((g) => gaugeMarker(m, g));
      setupPainting(meta);
    });
    addEventListener("resize", () => m.fitBounds(frame, { padding: 24, duration: 0 }));
  });
}
