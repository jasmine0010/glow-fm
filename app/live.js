// Run it yourself (live runs): pick a flood from this season and run the frozen method on it in the browser (app/livemethod.js).
// Cases are prepared by scripts/live_cases.py under research/LIVE_PROTOCOL.md; this page never contacts NASA.
const LIVE_STYLE = BASEMAP;
const LIVE_COLORS = { nisar: [214, 58, 214], estimate: [0, 200, 220] };
const escHtml = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const day = (iso) => new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const floodWord = (c) => (c.kind === "us" ? `${escHtml(c.category)} flood` : `GDACS ${escHtml(c.category)} alert`);
const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const live = { index: null, map: null, case: null, data: null, result: null, layers: { flood: true, estimate: false, change: false }, token: 0, ready: null };

// ---------- the list: the shared flood board (shared.js) ----------
function renderList() {
  const cases = currentCases(live.index);
  $("cases-board").innerHTML = floodPicker(cases, floodWord);
  if (!cases.some((c) => c.kind === "us")) $("cases-note").insertAdjacentHTML("afterbegin", "No US flood is ready right now. The job prepares new ones as they happen. ");
  const skipped = live.index.considered || [];
  $("skip-n").textContent = skipped.length;
  $("skipped").innerHTML = skipped.map((s) => `<li><b>${escHtml(s.place || s.name)}</b>: ${escHtml(s.skip)}</li>`).join("");
  $("live-updated").textContent = `${live.index.checked_utc ? `Floods last checked ${new Date(live.index.checked_utc).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}. ` : ""}NISAR scenes reach NASA's catalog days after they're recorded.`;
  // The wait, as measured over this season's scenes (scripts/build_coverage.py).
  fetch("data/figures/coverage.json").then((r) => r.json()).then(({ summary: c }) => {
    $("live-updated").textContent = $("live-updated").textContent.replace("days after they're recorded.", `a median ${c.latency_days.median} days after they're recorded, though ${Math.round(100 * c.latency_days.share_over_7)}% of this season's took more than a week.`);
  }).catch(() => {});
}

function markActive() {
  const shown = live.case && (live.index.cases.find((c) => c.id === live.case.id)?.superseded_by || live.case.id);   // a first run lights its newer twin's row
  document.querySelectorAll(".live-row").forEach((b) => {
    const on = b.dataset.case === shown;
    b.classList.toggle("on", on);
    b.setAttribute("aria-pressed", String(on));
  });
}

// ---------- choosing a case ----------
async function chooseCase(id) {
  const summary = live.index.cases.find((c) => c.id === id);
  if (!summary) return;
  await showCase(summary, `data/live/${id}`);
}

// Show a prepared case (published, or a custom one from the local box reader) from its folder.
async function showCase(summary, base) {
  const mine = ++live.token, id = summary.id;
  $("case-title").textContent = summary.place;
  $("case-sub").textContent = "Loading the prepared radar…";
  $("run").disabled = true;
  $("steps").hidden = true;
  $("cut-instr").hidden = true;
  $("analysis").hidden = true;
  $("result").innerHTML = "";
  live.result = null;
  const [rec, buf] = await Promise.all([fetch(`${base}/case.json`).then((r) => r.json()), fetch(`${base}/pack.bin`).then((r) => r.arrayBuffer())]);
  if (mine !== live.token) return;
  live.case = rec;
  live.data = LiveMethod.decodePack(buf, rec.layout);
  history.replaceState(null, "", rec.custom ? location.pathname : `?case=${encodeURIComponent(id)}`);   // a custom run has no shareable link
  markActive();
  const scored = rec.kind === "us" && rec.score;
  $("case-sub").innerHTML = rec.custom
    ? `Your choice · NISAR passed on <b>${day(rec.wet.time)}</b>, compared with ${rec.baseline.length} earlier passes on its track<br><span class="live-warn">Not checked against ground truth: there are no gauges in a custom run, so the trust light decides. It uses the frozen method; it isn't a test of it.</span>`
    : `${floodWord(rec)} since ${day(rec.flood_from)}${rec.flood_from_is_record_start ? " (or earlier)" : ""} · NISAR passed on <b>${day(rec.wet.time)}</b>, ` +
      `compared with ${rec.baseline.length} passes before the flood` + (rec.kind === "us" ? "" : `<br><span class="live-warn">Not checked against ground truth. GDACS gives one point per flood, so this 24 km box may miss the flooding.</span>`);
  $("case-notes").innerHTML = `Heights: ${escHtml(rec.inputs.heights)}. River: ${escHtml(rec.inputs.river)}.` +
    (rec.kind === "us" ? (scored ? ` Scored on ground within reach of ${rec.inputs.gauges.length} USGS gauge${rec.inputs.gauges.length === 1 ? "" : "s"}.` : ` ${escHtml(rec.score_skipped || "Not scored.")}`) : "") +
    (rec.wet.quicklook ? ` <a href="${escHtml(rec.wet.quicklook.url)}" target="_blank" rel="noopener">NASA's picture of this pass</a>.` : "") +
    (rec.report ? ` <a href="${escHtml(rec.report)}" target="_blank" rel="noopener">GDACS report</a>.` : "") +
    ` <a href="dashboard.html${summary.gdacs ? `?flood=${encodeURIComponent(summary.gdacs)}` : ""}">See it on the dashboard</a>.` + versionNote(rec, summary);
  // While the flood may still be going (its pass is under two repeat cycles old): when NISAR should see it next.
  const lastPass = Date.parse(rec.wet.time);
  if (Date.now() - lastPass < 2 * NISAR_REPEAT_MS) catalogWait().then((w) => { if (mine === live.token) $("case-notes").insertAdjacentHTML("beforeend", ` If the flood is still going, ${nextPassText(lastPass, w)}`); });
  renderLayerToggles();
  await live.ready;
  const [nw, ne, se, sw] = rec.corners;
  const lons = rec.corners.map((p) => p[0]), lats = rec.corners.map((p) => p[1]);
  live.map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 24, duration: reduced() ? 0 : 1200 });
  live.map.getSource("box").setData({ type: "Feature", geometry: { type: "Polygon", coordinates: [[nw, ne, se, sw, nw]] }, properties: {} });
  live.map.getSource("gauge").setData({ type: "Feature", geometry: { type: "Point", coordinates: [rec.lon, rec.lat] }, properties: {} });
  drawLayer(null);
  $("run").disabled = false;
  $("run").textContent = "Run NISAR's method";
}

// Protocol v2 rebuilt each first-run world flood with bare-earth heights (FABDEM) in place of treetop heights.
function versionNote(rec, summary) {
  const link = (id, text) => `<a href="?case=${encodeURIComponent(id)}" data-case-switch="${escHtml(id)}">${text}</a>`;
  if (rec.rebuilt_from) {
    const v1 = rec.v1_run;
    return `<br><b>Updated heights.</b> First run with treetop heights (Copernicus GLO-30), now rerun on the same radar with the trees removed, which tested better without lidar. ` +
      `The first run flagged ${ha(v1.flagged_ha)} ha${v1.confident === rec.frozen_run.confident ? "" : `, and its trust light was ${v1.confident ? "green" : "red"}`}: ${link(rec.rebuilt_from, "see the first run")}. ` +
      `<span class="note">Height layer from FABDEM V1-2 (Hawker et al. 2022), CC BY-NC-SA 4.0, non-commercial use.</span>`;
  }
  if (summary.superseded_by) return `<br><b>First run, with treetop heights.</b> Kept as published. ${link(summary.superseded_by, "See the rerun with the trees removed")}.`;
  return "";
}

// ---------- running ----------
function settings() {
  return {
    baseline: document.querySelector('input[name="baseline"]:checked').value,
    signal: document.querySelector('input[name="signal"]:checked').value,
    min_threshold_db: Number($("floor").value),
    hand_max_m: Number($("hand").value),
    abstain_timing: $("late").checked ? [4] : [],
  };
}
const isFrozen = (s) => s.baseline === "median" && s.signal === "adaptive" && s.min_threshold_db === 0.5 && s.hand_max_m === 6 && s.abstain_timing.length === 1;

const STEPS = RUN_STEPS;
// The map view as an image: read in the same frame it's drawn, so the WebGL canvas still holds it.
const captureMap = () => new Promise((resolve) => {
  live.map.once("render", () => {
    try { const src = live.map.getCanvas(), c = document.createElement("canvas"); c.width = src.width; c.height = src.height; c.getContext("2d").drawImage(src, 0, 0); resolve(c); } catch { resolve(null); }
  });
  live.map.triggerRepaint();
});
const saveFile = (name, blob) => { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); };
const sdb = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(2)} dB`;
const pause = (ms) => new Promise((ok) => setTimeout(ok, ms));

// The cut-off, set by the scene, as Otsu's search actually runs: a line scans every candidate cut-off across the valley
// floor's histogram while the between-class variance (how cleanly that cut splits the pixels in two) draws behind it.
// The cut-off lands on the curve's peak, then rises to the floor if the peak fell below it. Bars right of the line are
// what the method keeps.
function cutInstrument() {
  if (live.cut) return live.cut;
  const fig = $("cut-instr"), cv = fig.querySelector("canvas");
  const draw = (ctx, t, w, h) => {
    const st = live.cutState;
    if (!st) return;
    const H = st.hist, O = st.scan, max = Math.max(...H.counts), vmax = Math.max(...O.curve) || 1, base = h - 18, top = 26;
    const X = (v) => ((v - H.lo) / (H.hi - H.lo)) * w, bw = w / H.counts.length, raised = st.otsu < st.floor;
    // The scan (0 to 0.6), back to the peak (0.6 to 0.78), up to the floor if needed (0.78 to 1).
    const scanX = H.lo + (H.hi - H.lo) * Motion.clamp(t / 0.6);
    const back = Motion.ease(Motion.clamp((t - 0.6) / 0.18)), up = raised ? Motion.ease(Motion.clamp((t - 0.78) / 0.22)) : 0;
    const line = t < 0.6 ? scanX : Motion.lerp(Motion.lerp(H.hi, st.otsu, back), st.cut, up);
    H.counts.forEach((c, k) => {
      const mid = H.lo + (k + 0.5) * (H.hi - H.lo) / H.counts.length, bh = (c / max) * (base - top);
      ctx.fillStyle = mid > line ? "#e57ae5" : "rgba(185, 196, 203, .5)";
      ctx.fillRect(k * bw + 0.5, base - bh, Math.max(1, bw - 1), bh);
    });
    // The variance curve, drawn as far as the scan has reached, and the best split so far.
    const reach = t < 0.6 ? scanX : H.hi, pts = [];
    let best = -1, bestX = 0;
    O.curve.forEach((v, k) => {
      const c = O.lo + (k + 0.5) * O.width;
      if (c > reach) return;
      pts.push([X(c), base - (v / vmax) * (base - top)]);
      if (v > best) { best = v; bestX = c; }
    });
    if (pts.length > 1) {
      ctx.strokeStyle = "rgba(242, 246, 248, .85)"; ctx.lineWidth = 1.4; ctx.beginPath(); Motion.smoothPath(ctx, pts); ctx.stroke(); ctx.lineWidth = 1;
      const by = base - (best / vmax) * (base - top);
      ctx.fillStyle = "#ffd166"; ctx.beginPath(); ctx.arc(X(bestX), by, 3.5, 0, 2 * Math.PI); ctx.fill();
      if (t >= 0.6) { ctx.fillStyle = "#ffd166"; ctx.font = "500 11px 'IBM Plex Sans', system-ui, sans-serif"; ctx.textAlign = X(bestX) > w * 0.6 ? "right" : "left"; ctx.fillText("best split", X(bestX) + (X(bestX) > w * 0.6 ? -7 : 7), by + 14); }
    }
    ctx.strokeStyle = "rgba(205, 225, 235, .3)"; ctx.beginPath(); ctx.moveTo(0, base + 0.5); ctx.lineTo(w, base + 0.5); ctx.stroke();
    ctx.font = "500 11px 'IBM Plex Sans', system-ui, sans-serif"; ctx.fillStyle = "#a7b9c5"; ctx.textAlign = "center";
    for (let v = Math.ceil(H.lo); v <= Math.floor(H.hi); v += Math.max(1, Math.round((H.hi - H.lo) / 5))) { ctx.fillRect(X(v), base, 1, 3); ctx.fillText(v === 0 ? "0 dB" : `${v > 0 ? "+" : "−"}${Math.abs(v)}`, X(v), h - 3); }
    const lx = X(line);
    ctx.strokeStyle = "#f2f6f8"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(lx, 12); ctx.lineTo(lx, base); ctx.stroke(); ctx.lineWidth = 1;
    ctx.fillStyle = "#f2f6f8"; ctx.font = "600 12px 'IBM Plex Sans', system-ui, sans-serif"; ctx.textAlign = lx > w * 0.6 ? "right" : "left";
    ctx.fillText(t < 0.6 ? `trying ${sdb(line)}` : `cut-off ${sdb(line)}${raised && up >= 1 ? " (the floor)" : ""}`, lx + (lx > w * 0.6 ? -6 : 6), 11);
  };
  live.cut = Motion.instrument(cv, draw, { ms: 2600, start: "none" });
  return live.cut;
}

async function showCut(res, s, animate) {
  const fig = $("cut-instr"), H = res.floorHist, raised = res.otsuDb < s.min_threshold_db;
  fig.hidden = false;
  live.cutState = { hist: H, scan: res.otsuScan, otsu: res.otsuDb, floor: s.min_threshold_db, cut: res.threshold };
  const text = `The valley floor's radar change, ${H.n.toLocaleString("en-US")} pixels. Otsu's split ` +
    (raised ? `peaked at ${sdb(res.otsuDb)}, below the ${s.min_threshold_db.toFixed(1)} dB floor, so the floor is the cut-off.` : `peaked at ${sdb(res.threshold)}: the cut-off.`) + " Line: how cleanly each cut-off splits the pixels in two (Otsu's between-class variance). Magenta: kept.";
  fig.querySelector("figcaption").textContent = text;
  fig.querySelector("canvas").setAttribute("aria-label", text);
  const inst = cutInstrument();
  if (animate && !reduced()) { inst.play(); await pause(2650); } else inst.finish();
}

// NISAR's map, strongest echo first: the counter is the pixels shown so far, ending at the run's own total.
async function revealPixels(res) {
  const d = live.data, rec = live.case, vals = [];
  for (let i = 0; i < res.pred.length; i++) if (res.pred[i] && !(d.water && d.water[i])) vals.push(res.change[i]);
  vals.sort((a, b) => b - a);
  const num = document.querySelector("#result .run-area .stat-num"), STEPS_N = 16;
  for (let k = 1; k <= STEPS_N && vals.length; k++) {
    if (live.result !== res) return;
    const shown = Math.ceil((vals.length * k) / STEPS_N);
    drawLayer(res, k < STEPS_N ? vals[shown - 1] : null);
    if (num) num.textContent = `${ha(shown * rec.pixel_ha)} ha`;
    await pause(65);
  }
}

async function runMethod(animate) {
  const rec = live.case, s = settings();
  $("run").disabled = true;
  const steps = $("steps");
  steps.hidden = false;
  steps.innerHTML = STEPS.map(([k, t]) => `<li data-step="${k}">${t}<span class="live-step-note"></span></li>`).join("");
  const res = LiveMethod.run(live.data, rec.layout.width, rec.layout.height, s);
  const notes = res.error ? {} : {
    compare: s.baseline === "median" ? `${rec.baseline.length} earlier passes, median of each pixel` : "the latest earlier pass only",
    signal: res.usedRatio ? "HH minus HV: higher ground brightened too, which looks like rain" : "HH change: water under trees brightens HH most",
    keep: `within ${s.hand_max_m} m of the river's height`,
    cut: `${res.threshold.toFixed(2)} dB brighter than before${res.threshold === s.min_threshold_db ? " (the lowest allowed)" : ""}`,
    skip: rec.kind === "us" ? (s.abstain_timing.length ? "using the nearest gauge's timing" : "off") : "no gauges here, so nothing is skipped",
    grade: rec.kind === "us" && live.data.estimate ? "against the river's gauges and lidar" : "no gauges here, so the trust light decides",
  };
  for (const [k] of STEPS) {
    const li = steps.querySelector(`[data-step="${k}"]`);
    if (animate && !reduced()) await new Promise((ok) => setTimeout(ok, 380));
    li.classList.add("done");
    if (animate) soundTick(0.03);
    li.querySelector(".live-step-note").textContent = notes[k] ? ` · ${notes[k]}` : "";
    if (k === "cut" && !res.error) await showCut(res, s, animate);
  }
  live.result = res;
  if (animate) soundPing({ gain: 0.08 });
  renderResult(s);
  if (animate && !reduced() && !res.error) await revealPixels(res);
  else drawLayer(res);
  if (!res.error && live.result === res) LiveFigs.update(rec, live.data, res, s);
  $("run").disabled = false;
  $("run").textContent = "Run it again";
}

function renderResult(s) {
  const rec = live.case, res = live.result, box = $("result");
  if (res.error) { box.innerHTML = `<p class="live-warn">${escHtml(res.error)}</p>`; return; }
  const area = res.flaggedLand * rec.pixel_ha;
  const light = trustLight({ mapped: area > 0, confident: res.confident, rainy: null });
  let html = `<div class="run-area"><span class="stat-num">${ha(area)} ha</span><span class="stat-label">flagged as flooded by NISAR's method, not counting permanent lakes and rivers</span></div>`;
  if (rec.kind === "us" && live.data.estimate) {
    const mine = LiveMethod.score(res, live.data.estimate);
    html += `<div class="run-grade"><span class="stat-num">${mine.csi === null ? "—" : mine.csi.toFixed(2)}</span><span class="stat-label">match with the river's gauges, where 1 is perfect${isFrozen(s) ? "" : ", with your settings"}</span></div>`;
  } else if (rec.kind !== "us") {
    html += `<div class="run-grade run-grade-none"><span class="stat-label">No gauges here to grade it. ${light.cls === "red" ? "Its trust light is red: don't rely on this one." : "Treat it as unchecked."}</span></div>`;
  }
  html += `<p class="live-trust">${trustChip(light, { long: true })}</p>`;
  if (rec.kind === "us" && live.data.estimate) {
    const yours = LiveMethod.score(res, live.data.estimate), f = rec.score, frozen = f && f.scores && f.scores.csi;
    const ci = f && f.ci95 && f.ci95.csi ? ` (95% range ${f.ci95.csi[0].toFixed(2)}–${f.ci95.csi[1].toFixed(2)})` : "";
    html += `<div class="live-score"><p class="live-score-head">The published test</p>` +
      `<p><b>${frozen !== null && frozen !== undefined ? frozen.toFixed(2) : "—"}</b> with the frozen settings${ci}. This is the published test.</p>` +
      (isFrozen(s) ? "" : `<p><b>${yours.csi === null ? "—" : yours.csi.toFixed(2)}</b> with your settings. Settings picked after seeing a score are tuning, not testing.</p>`) +
      `<p class="note">Scored on ${ha(f.estimate_wet_ha + f.estimate_dry_ha)} ha the estimate can label near ${rec.inputs.gauges.length === 1 ? "its one gauge (3 km along the river)" : `its ${rec.inputs.gauges.length} gauges`}, not the whole box. ` +
      `0 to 1, where 1 is perfect. The estimate is a model from gauges and lidar, not a sighting of water.</p></div>`;
  } else if (rec.kind === "us") {
    html += `<p class="note">${escHtml(rec.score_skipped || "No score for this flood.")}</p>`;
  }
  box.innerHTML = html;
}

// ---------- the map ----------
function renderLayerToggles() {
  const rows = [["flood", "NISAR's flood map", "#d63ad6"], ["change", "Radar change since before the flood", "#bfc6cc"]];
  if (live.case.kind === "us" && live.data.estimate) rows.splice(1, 0, ["estimate", "Gauge-and-lidar estimate", "#00c8dc"]);
  $("layers").innerHTML = rows.map(([k, t, c]) => `<label class="layer-row"><input type="checkbox" data-layer="${k}"${live.layers[k] ? " checked" : ""}><span class="swatch" style="background:${c}"></span>${t}</label>`).join("");
  $("live-legend").innerHTML = rows.filter(([k]) => live.layers[k]).map(([, t, c]) => `<span><i class="swatch" style="background:${c}"></i>${t}</span>`).join("") +
    '<span><i class="swatch live-box-swatch"></i>The 24 km box the method sees</span>';
}

function drawLayer(res, minChange = null) {
  const rec = live.case, w = rec.layout.width, h = rec.layout.height, d = live.data;
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  const g = c.getContext("2d"), img = g.createImageData(w, h), px = img.data;
  const showChange = live.layers.change, showEst = live.layers.estimate && d.estimate, showFlood = live.layers.flood && res && !res.error;
  for (let i = 0; i < w * h; i++) {
    let r = 0, gg = 0, b = 0, a = 0;
    if (showChange) {
      const base = d.median_hh[i], v = d.wet_hh[i] - base;
      if (v === v) { const t = Math.max(0, Math.min(1, (v + 3) / 6)); r = gg = b = Math.round(40 + 200 * t); a = 200; }
    }
    if (showFlood && res.pred[i] && !(d.water && d.water[i]) && (minChange === null || res.change[i] >= minChange)) { [r, gg, b] = LIVE_COLORS.nisar; a = 230; }
    if (showEst && d.estimate[i] === 1) { [r, gg, b] = LIVE_COLORS.estimate; a = 235; }   // on top, so the small scored area stays visible
    px[4 * i] = r; px[4 * i + 1] = gg; px[4 * i + 2] = b; px[4 * i + 3] = a;
  }
  g.putImageData(img, 0, 0);
  const url = c.toDataURL("image/png"), src = live.map.getSource("layer");
  if (src) src.updateImage({ url, coordinates: rec.corners });
  else {
    live.map.addSource("layer", { type: "image", url, coordinates: rec.corners });
    live.map.addLayer({ id: "layer", type: "raster", source: "layer", paint: { "raster-resampling": "nearest", "raster-fade-duration": 0 } }, "box-line");
  }
}

function setupMap() {
  live.map = new maplibregl.Map({ container: "live-map", style: LIVE_STYLE, center: [-40, 25], zoom: 1.4, attributionControl: { compact: true }, dragRotate: false, pitchWithRotate: false });
  live.map.touchZoomRotate.disableRotation();
  live.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  addInstruments(live.map, { coords: false, label: "Map of the chosen flood: NISAR's flood map, and for US floods the gauge-and-lidar estimate, inside a 24 km box" });
  live.ready = new Promise((ok) => live.map.on("load", () => {
    const empty = { type: "FeatureCollection", features: [] };
    live.map.addSource("box", { type: "geojson", data: empty });
    live.map.addLayer({ id: "box-line", type: "line", source: "box", paint: { "line-color": "#ffffff", "line-opacity": 0.85, "line-width": 1.5, "line-dasharray": [3, 2] } });
    live.map.addSource("gauge", { type: "geojson", data: empty });
    live.map.addLayer({ id: "gauge", type: "circle", source: "gauge", paint: { "circle-radius": 5, "circle-color": "#ffffff", "circle-stroke-color": "#00c8dc", "circle-stroke-width": 2 } });
    ok();
  }));
}

// ---------- wiring ----------
function wire() {
  document.querySelector(".live-cases").addEventListener("click", (e) => { const b = e.target.closest("[data-case]"); if (b) chooseCase(b.dataset.case); });
  $("run").addEventListener("click", () => runMethod(true));
  $("run-download").addEventListener("click", () => saveFile(`${live.case.id}-run.json`, new Blob([JSON.stringify(LiveFigs.record(), null, 1)], { type: "application/json" })));
  $("map-download").addEventListener("click", () => {
    // NISAR's flood map for this run as a PNG, and its corners (lon, lat: NW, NE, SE, SW) so it can be placed in a GIS.
    const rec = live.case, w = rec.layout.width, h = rec.layout.height, c = document.createElement("canvas");
    c.width = w; c.height = h;
    const g = c.getContext("2d"), img = g.createImageData(w, h);
    for (let i = 0; i < w * h; i++) if (live.result.pred[i] && !(live.data.water && live.data.water[i])) { img.data[4 * i] = 214; img.data[4 * i + 1] = 58; img.data[4 * i + 2] = 214; img.data[4 * i + 3] = 255; }
    g.putImageData(img, 0, 0);
    c.toBlob((b) => saveFile(`${rec.id}-nisar-map.png`, b));
    saveFile(`${rec.id}-nisar-map-corners.json`, new Blob([JSON.stringify({ corners_lon_lat: rec.corners, order: "NW, NE, SE, SW", pixel_m: 50, epsg_of_grid: rec.inputs.epsg }, null, 1)], { type: "application/json" }));
  });
  $("brief-download").addEventListener("click", async () => {
    // One page for someone who has to act on it: the run as shown, with its trust light, limits and sources.
    const rec = live.case, res = live.result, s = settings(), area = res.flaggedLand * rec.pixel_ha;
    const light = trustLight({ mapped: area > 0, confident: res.confident, rainy: null });
    const yourCsi = rec.kind === "us" && live.data.estimate ? LiveMethod.score(res, live.data.estimate).csi : null;
    const last = Date.parse(rec.wet.time), w = await catalogWait();
    const next = Date.now() - last < 2 * NISAR_REPEAT_MS ? `If the flood is still going, ${nextPassText(last, w)}` : null;
    const map = await captureMap();
    LiveFigs.brief({ map, light, frozen: isFrozen(s), yourCsi, next }).toBlob((b) => saveFile(`${rec.id}-brief.png`, b));
  });
  $("case-notes").addEventListener("click", (e) => { const a = e.target.closest("[data-case-switch]"); if (a) { e.preventDefault(); chooseCase(a.dataset.caseSwitch); } });
  $("layers").addEventListener("change", (e) => {
    const k = e.target.dataset.layer;
    if (!k) return;
    live.layers[k] = e.target.checked;
    renderLayerToggles();
    drawLayer(live.result);
  });
  const rerun = () => { $("floor-out").textContent = `${Number($("floor").value).toFixed(1)} dB`; $("hand-out").textContent = `${$("hand").value} m`; if (live.result) runMethod(false); };
  $("settings").addEventListener("input", rerun);
  $("reset").addEventListener("click", () => {
    document.querySelector('input[name="baseline"][value="median"]').checked = true;
    document.querySelector('input[name="signal"][value="adaptive"]').checked = true;
    $("floor").value = "0.5"; $("hand").value = "6"; $("late").checked = true;
    rerun();
  });
}

// ---------- Run it anywhere (needs scripts/custom_server.py on this computer) ----------
const anywhere = { box: null, drawing: false, start: null, poll: null };
const anyDate = (d) => d.toISOString().slice(0, 10);
const BOX_LIMITS = [5, 50];                 // km a side: the server holds the same limits
const boxKm = ([w, s, e, n]) => [(e - w) * 111.32 * Math.cos(((s + n) / 2) * Math.PI / 180), (n - s) * 111.32];
const boxAround = (lon, lat, km = 24) => { const dy = km / 2 / 111.32, dx = dy / Math.max(0.1, Math.cos(lat * Math.PI / 180)); return [lon - dx, lat - dy, lon + dx, lat + dy]; };
const ll = (lat, lon) => `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? "N" : "S"} ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? "E" : "W"}`;

async function setupAnywhere() {
  const want = new URLSearchParams(location.search), wantBox = (want.get("box") || "").split(",").map(Number);
  const asked = wantBox.length === 4 && wantBox.every(Number.isFinite);
  const noReader = () => {   // a link from the dashboard, but this copy of the site has no local box reader
    if (!asked) return;
    $("cases-note").insertAdjacentHTML("afterbegin", `<span class="live-warn">The dashboard sent a flood we haven't prepared. Running a new place needs the local box reader: on a computer with an Earthdata sign-in, run <code>python scripts/custom_server.py</code> and open <code>http://127.0.0.1:8767/live.html${escHtml(location.search)}</code>.</span> `);
  };
  if (!document.querySelector('meta[name="glowfm-reader"]')) { noReader(); return; }   // only scripts/custom_server.py adds this
  try { if (!(await fetch("/api/health").then((r) => r.json())).ok) { noReader(); return; } } catch { noReader(); return; }
  $("pick-tabs").hidden = false;
  document.querySelectorAll("#pick-tabs button").forEach((b) => b.addEventListener("click", () => setPane(b.dataset.pane)));
  const now = new Date();
  $("any-from").value = anyDate(new Date(now - 30 * 864e5)); $("any-to").value = anyDate(now);
  const span = () => { $("any-span").textContent = $("any-to").value === anyDate(new Date()) && $("any-from").value === anyDate(new Date(Date.now() - 30 * 864e5)) ? "the last 30 days" : `${fmtDay($("any-from").value)} to ${fmtDay($("any-to").value)}`; };
  ["any-from", "any-to"].forEach((k) => $(k).addEventListener("change", () => { span(); if (anywhere.box) findPasses(); }));
  // Typed coordinates make a 24 km box around the point.
  $("any-coords").addEventListener("change", () => {
    const m = $("any-coords").value.match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/);
    if (!m || Math.abs(+m[1]) > 80 || Math.abs(+m[2]) > 180) { $("any-status").textContent = "Type latitude, then longitude, in decimal degrees: for example -3.25, -60.2."; return; }
    setBox(boxAround(+m[2], +m[1]), true);
    findPasses();
  });
  $("any-draw").addEventListener("click", () => drawMode(!anywhere.drawing));
  $("any-clear").addEventListener("click", () => setBox(null));
  $("any-passes").addEventListener("click", (e) => {
    const b = e.target.closest("[data-pass]");
    if (b) prepareCustom(b.dataset.pass, b.dataset.label);
  });
  if (asked) { if (want.get("from")) $("any-from").value = want.get("from"); if (want.get("to")) $("any-to").value = want.get("to"); span(); setPane("any"); }
  // Only the map's own parts wait for the map; the rest works at once.
  await live.ready;
  live.map.addSource("any-box", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  live.map.addLayer({ id: "any-box-fill", type: "fill", source: "any-box", paint: { "fill-color": "#ffd166", "fill-opacity": 0.12 } });
  live.map.addLayer({ id: "any-box-line", type: "line", source: "any-box", paint: { "line-color": "#ffd166", "line-width": 2 } });
  const at = (e) => [e.lngLat.lng, e.lngLat.lat];
  const down = (e) => { if (!anywhere.drawing) return; e.preventDefault(); anywhere.start = at(e); };
  const move = (e) => { if (!anywhere.drawing || !anywhere.start) return; const [x, y] = at(e), [x0, y0] = anywhere.start; setBox([Math.min(x, x0), Math.min(y, y0), Math.max(x, x0), Math.max(y, y0)]); };
  const up = (e) => {
    if (!anywhere.drawing || !anywhere.start) return;
    const [x, y] = at(e), [x0, y0] = anywhere.start, tiny = Math.abs(x - x0) < 1e-3 && Math.abs(y - y0) < 1e-3;
    setBox(tiny ? boxAround(x, y) : [Math.min(x, x0), Math.min(y, y0), Math.max(x, x0), Math.max(y, y0)]);   // a click drops a 24 km box
    anywhere.start = null;
    drawMode(false);
    findPasses();   // a drawn box is searched at once
  };
  ["mousedown", "touchstart"].forEach((k) => live.map.on(k, down));
  ["mousemove", "touchmove"].forEach((k) => live.map.on(k, move));
  ["mouseup", "touchend"].forEach((k) => live.map.on(k, up));
  // A flood sent from the dashboard: its box, searched at once.
  if (asked) { setBox(wantBox, true); findPasses(); $("live-cases").scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "start" }); }
}

// One list at a time: the prepared floods, or your own box.
function setPane(name) {
  document.querySelectorAll("#pick-tabs button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.pane === name)));
  $("pane-ready").hidden = name !== "ready";
  $("anywhere").hidden = name !== "any";
  $("pick-title").lastChild.textContent = name === "any" ? " Choose a place" : " Choose a flood";
  if (name !== "any" && anywhere.drawing) drawMode(false);
}

function drawMode(on) {
  anywhere.drawing = on;
  $("any-draw").setAttribute("aria-pressed", String(on));
  $("any-draw").textContent = on ? "Drag on the map to draw…" : anywhere.box ? "Draw another box" : "Draw a box on the map";
  live.map.getCanvas().style.cursor = on ? "crosshair" : "";
  if (on) { live.map.dragPan.disable(); live.map.touchZoomRotate.disable(); $("any-status").textContent = "Drag a rectangle on the map, or click once for a 24 km box."; $("live-map").scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "center" }); }
  else { live.map.dragPan.enable(); live.map.touchZoomRotate.enable(); live.map.touchZoomRotate.disableRotation(); }
}

function setBox(box, fly = false) {
  anywhere.box = box;
  const src = live.map.getSource("any-box");
  if (src) src.setData(box ? { type: "Feature", geometry: { type: "Polygon", coordinates: [[[box[0], box[1]], [box[2], box[1]], [box[2], box[3]], [box[0], box[3]], [box[0], box[1]]]] }, properties: {} } : { type: "FeatureCollection", features: [] });
  $("any-passes").innerHTML = "";
  $("any-clear").hidden = !box;
  if (!box) { $("any-point").textContent = "No box yet."; $("any-point").classList.remove("any-bad"); $("any-status").textContent = ""; return; }
  const [kx, ky] = boxKm(box), ok = Math.min(kx, ky) >= BOX_LIMITS[0] && Math.max(kx, ky) <= BOX_LIMITS[1];
  $("any-point").textContent = `Box: ${kx.toFixed(0)} × ${ky.toFixed(0)} km around ${ll((box[1] + box[3]) / 2, (box[0] + box[2]) / 2)}` + (ok ? "" : ` · boxes must be ${BOX_LIMITS[0]}–${BOX_LIMITS[1]} km a side`);
  $("any-point").classList.toggle("any-bad", !ok);
  $("any-coords").value = `${((box[1] + box[3]) / 2).toFixed(4)}, ${((box[0] + box[2]) / 2).toFixed(4)}`;
  $("any-status").textContent = ok ? "" : "Resize the box before searching.";
  if (fly) live.map.fitBounds([[box[0], box[1]], [box[2], box[3]]], { padding: 60, duration: reduced() ? 0 : 900, maxZoom: 11 });
}

async function findPasses() {
  const box = anywhere.box;
  if (!box) return;
  const [kx, ky] = boxKm(box), ask = (anywhere.ask = (anywhere.ask || 0) + 1);   // only the latest search writes the list
  if (Math.min(kx, ky) < BOX_LIMITS[0] || Math.max(kx, ky) > BOX_LIMITS[1]) { $("any-status").textContent = `Boxes must be ${BOX_LIMITS[0]}–${BOX_LIMITS[1]} km a side; this one is ${kx.toFixed(0)} × ${ky.toFixed(0)} km.`; return; }
  $("any-status").textContent = "Searching NASA's catalog…";
  $("any-passes").innerHTML = "";
  const q = `w=${box[0].toFixed(5)}&s=${box[1].toFixed(5)}&e=${box[2].toFixed(5)}&n=${box[3].toFixed(5)}&from=${$("any-from").value}&to=${$("any-to").value}`;
  const r = await fetch(`/api/passes?${q}`).then((x) => x.json()).catch(() => ({ error: "The local box reader didn't answer." }));
  if (ask !== anywhere.ask) return;
  if (r.error) { $("any-status").textContent = r.error; return; }
  if (!r.passes.length) { $("any-status").textContent = "No NISAR pass of the kind the method uses (40 MHz, HH and HV) covers this whole box in these dates. A smaller box, or one away from a scene's edge, may fit."; return; }
  $("any-status").textContent = `${r.passes.length} pass${r.passes.length === 1 ? " covers" : "es cover"} the whole box. Choose ${r.passes.length === 1 ? "it" : "one"} to prepare.`;
  $("any-passes").innerHTML = r.passes.map((p) => {
    const label = `${fmtTime(p.time)} · track ${p.stack.split("_")[0]}`;
    return `<li><button type="button" class="any-pass" data-pass="${escHtml(p.name)}" data-label="${escHtml(label)}"${p.usable ? "" : " disabled"}><b>${escHtml(label)}</b>` +
      `<span>${p.usable ? `${p.earlier} earlier passes to compare` : `only ${p.earlier} earlier pass${p.earlier === 1 ? "" : "es"}: the method needs 3`}</span></button>` +
      (p.quicklook ? ` <a href="${escHtml(p.quicklook.url)}" target="_blank" rel="noopener">picture</a>` : "") + "</li>";
  }).join("");
}

async function prepareCustom(name, label) {
  const box = anywhere.box, [kx, ky] = boxKm(box), place = `Your box, ${kx.toFixed(0)} × ${ky.toFixed(0)} km at ${ll((box[1] + box[3]) / 2, (box[0] + box[2]) / 2)}`;
  clearInterval(anywhere.poll);
  $("any-passes").querySelectorAll("button").forEach((b) => { b.disabled = true; });
  const job = await fetch("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ pass: name, place }) }).then((r) => r.json());
  if (job.error) { $("any-status").textContent = job.error; return; }
  const tick = async () => {
    const s = await fetch(`/api/job/${job.id}`).then((r) => r.json());
    $("any-status").textContent = `${label}: ${s.step}${s.state === "running" || s.state === "queued" ? ` · ${s.seconds} s` : ""}`;
    const reopen = () => $("any-passes").querySelectorAll("button").forEach((b) => { b.disabled = b.querySelector("span").textContent.startsWith("only"); });
    if (s.state === "failed") { clearInterval(anywhere.poll); reopen(); }
    if (s.state === "done") { clearInterval(anywhere.poll); reopen(); $("any-status").textContent = `${label}: ready. Press Run.`; await showCase({ id: job.id, place, wet: null }, `/api/custom/${job.id}`); }
  };
  anywhere.poll = setInterval(tick, 1500);
  tick();
}

(async function start() {
  setupMap();
  wire();
  setupAnywhere();
  try {
    live.index = await fetch("data/live/index.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
  } catch {
    $("cases-note").textContent = "No live cases have been prepared yet.";
    return;
  }
  renderList();
  const wanted = new URLSearchParams(location.search).get("case");
  const first = live.index.cases.find((c) => c.id === wanted) || currentCases(live.index).sort((a, b) => (b.kind === "us") - (a.kind === "us") || b.wet.localeCompare(a.wet))[0];
  if (first) chooseCase(first.id);
})();
