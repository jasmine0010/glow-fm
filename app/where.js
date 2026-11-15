// "Your town": back to orbit. The night globe from the journey returns (its own instance of globe.js), with the towns
// beside large forested floodplains as amber lights. Search for a place, or click a light, and the globe turns and closes
// in on it: the forest nearby lights up, a pin marks the place, and a dashed ring shows the 25 km the check covers, drawn
// to scale. The verdict comes from atlas.js (atlasLookup, atlasVerdict). The lights are half-degree summaries; the
// number comes from the 25 km check. Nothing typed leaves the page.

const TOWN = { g: null, rows: null, xy: null, picked: null, fly: null, loop: null };
const TOWN_ZOOM_KM = 3200;                        // how much ground the view shows when it arrives at a town

// On a wide screen the globe sits left of centre, clear of the panel on the right.
const townCx = () => (small() ? TOWN.g.w / 2 : TOWN.g.w * 0.4);
function townHome() {
  const g = TOWN.g;
  return { lon: TOWN.g.view.lon, lat: 12, R: Math.min(g.w * 0.36, g.h * 0.42), cx: townCx(), cy: g.h / 2 };
}

// Fly the globe to a view: the turn and the zoom together, the zoom on a log scale so it feels steady.
function townFlyTo(to, ms = 1700) {
  const g = TOWN.g, from = { ...g.view };
  let dl = ((to.lon - from.lon + 540) % 360) - 180;          // the short way round
  TOWN.fly = { from, to: { ...to, lon: from.lon + dl }, t: reducedMotion() ? 1 : 0, ms };
  TOWN.loop.kick();
}

function townDraw() {
  const g = TOWN.g, p = TOWN.picked, arrived = TOWN.fly ? TOWN.fly.t : 1;
  const place = p && !p.country ? p : null;
  globeDraw({ points: 1, coast: 0.9, people: 0, swath: false, dim: 0,
    focus: p ? { lon: p.lon, lat: p.lat, km: p.country ? 400 : 260, glow: 0.9 * ease(arrived) } : null,
    ring: place && arrived > 0.6 ? { lon: place.lon, lat: place.lat, km: ATLAS_RADIUS_KM } : null,
    pin: place ? { lon: place.lon, lat: place.lat } : null }, g);
  // The towns: small amber lights, remembered on screen so a click can find the nearest.
  const rows = TOWN.rows;
  if (!rows) return;
  const ctx = g.ctx, out = [0, 0, 0], xy = TOWN.xy, [pr, pg, pb] = GLOBE_RGB.people, r = Math.max(1.1, Math.min(2.6, g.view.R / 500));
  ctx.globalCompositeOperation = "lighter";
  ctx.fillStyle = `rgba(${pr}, ${pg}, ${pb}, .85)`; ctx.beginPath();
  for (let i = 0; i < rows.length; i++) {
    const t = rows[i];
    if (globeProject(t.lonR, t.s, t.c, out, g)) { xy[2 * i] = out[0]; xy[2 * i + 1] = out[1]; ctx.rect(out[0] - r, out[1] - r, 2 * r, 2 * r); }
    else { xy[2 * i] = -1e4; xy[2 * i + 1] = -1e4; }
  }
  ctx.fill();
  ctx.globalCompositeOperation = "source-over";
}

function townFrame(dt) {
  const g = TOWN.g, f = TOWN.fly;
  if (f) {
    f.t = Math.min(1, f.t + dt / f.ms);
    const e = ease(f.t);
    g.view.lon = lerp(f.from.lon, f.to.lon, e); g.view.lat = lerp(f.from.lat, f.to.lat, e);
    g.view.R = Math.exp(lerp(Math.log(f.from.R), Math.log(f.to.R), e));
    g.view.cx = lerp(f.from.cx, f.to.cx, e); g.view.cy = lerp(f.from.cy, f.to.cy, e);
    townDraw();
    if (f.t >= 1) { TOWN.fly = null; if (TOWN.picked) return false; }
    return true;
  }
  // Idle on the whole Earth: it turns slowly. Arrived at a place: it holds still and the loop sleeps.
  if (TOWN.picked || reducedMotion()) { townDraw(); return false; }
  g.view.lon = ((g.view.lon + dt * 0.004 + 540) % 360) - 180;
  townDraw();
  return true;
}

function renderTownLabel(p) {
  const v = atlasVerdict(p.share, p.floodplain), label = atlasLabelText(p, v), q = new URLSearchParams({ view: "atlas", at: `${p.at[0].toFixed(2)},${p.at[1].toFixed(2)}`, name: p.name, short: p.short });
  const enough = p.floodplain >= atlas.summary.towns.rule.min_floodplain_km2;
  $("town-label").innerHTML = `<p class="atlas-place">${esc(p.name)}</p>` +
    (enough ? `<div class="qn" style="--c: var(--forest-ink)"><span class="qn-k">Floodplain under trees</span><b class="qn-n" id="tl-share">${pct(p.share, 0)}</b><span class="qn-u">of ${km2(p.floodplain)} of river floodplain within about ${ATLAS_RADIUS_KM} km</span></div>` : "") +
    `<p class="atlas-label atlas-label-${v.cls}">${esc(label)}</p><p class="atlas-level"><i class="status-dot ${v.cls}"></i>${v.level}</p><p class="atlas-why">${v.text}</p>${v.act ? `<p class="atlas-act"><b>What to do:</b> ${v.act}</p>` : ""}` +
    `<p class="atlas-not">Not a flood forecast: it says how well flood maps can see the ground here.</p><a class="more-link" href="dashboard.html?${esc(q.toString())}">Open on the blind-spot map</a>`;
  if (enough) countUp($("tl-share"), 100 * p.share, (x) => `${Math.round(x)}%`, 900);
  $("town-announce").textContent = label;
  soundPing({ gain: 0.08 });
}

function setupTownGlobe(summary) {
  const towns = summary.towns;
  $("town-count").textContent = atlasTownsText(summary);
  $("town-try").innerHTML = `<span class="atlas-try-label">Try</span>${towns.examples.slice(0, 3).map((e, k) => `<button type="button" class="atlas-chip" data-try="${k}">${esc(e.name)}</button>`).join("")}`;
  $("tg-caption").innerHTML = mapLegend([["forest", "Floodplain under trees"], ["town", "Town beside it"], ["ring", `${ATLAS_RADIUS_KM} km checked`]], "Lights are 0.5° summaries");
  let token = 0;
  const choose = async (hit) => {
    const mine = ++token;
    $("town-results").innerHTML = "";
    $("town-q").value = "";
    atlas.hits = [];
    const g = TOWN.g;
    if (hit.country) {
      const c = atlas.summary.countries.find((x) => x.name === hit.country);
      const [w, s, e, n] = c.bbox, lat = (s + n) / 2, lon = (w + e) / 2;
      TOWN.picked = { name: c.name, lat, lon, country: true };
      if (g) { const span = Math.max(boundsWidthKm(c.bbox), (n - s) * 111.32) * 1.3; townFlyTo({ lon, lat, R: g.w / (Math.min(2 * EARTH_KM, span) / EARTH_KM), cx: townCx(), cy: g.h / 2 }); }
      const v = atlasVerdict(c.share, c.floodplain_km2);
      $("town-label").innerHTML = `<p class="atlas-place">${esc(c.name)}</p><div class="qn" style="--c: var(--forest-ink)"><span class="qn-k">Floodplain under trees</span><b class="qn-n">${pct(c.share, 0)}</b><span class="qn-u">of ${km2(c.floodplain_km2)} of mapped river floodplain</span></div><p class="atlas-label atlas-label-${v.cls}">${esc(atlasLabelText({ name: c.name }, v))}</p><p class="atlas-why">${v.text}</p>${v.act ? `<p class="atlas-act"><b>What to do:</b> ${v.act}</p>` : ""}<p class="atlas-not">Not a flood forecast: it says how well flood maps can see the ground here.</p>`;
      soundPing({ gain: 0.08 });
      return;
    }
    const where = hit.where === "river" ? hit.name : `${hit.name}, ${hit.where}`;
    TOWN.picked = { name: where, lat: hit.lat, lon: hit.lon };
    if (g) townFlyTo({ lon: hit.lon, lat: hit.lat, R: g.w / (TOWN_ZOOM_KM / EARTH_KM), cx: townCx(), cy: g.h / 2 });
    $("town-label").innerHTML = `<p class="muted">Checking ${esc(where)}…</p>`;
    let got;
    try { got = await atlasLookup(hit.lat, hit.lon); } catch (err) {
      console.warn("Town check failed", err);
      if (mine === token) { $("town-label").innerHTML = `<p class="muted">Couldn't check ${esc(where)} just now. <button type="button" class="link-btn" id="town-retry">Try again</button></p>`; $("town-retry").addEventListener("click", () => choose(hit)); }
      return;
    }
    if (mine === token) renderTownLabel({ ...got, name: where, short: hit.name, at: [hit.lat, hit.lon] });
  };
  $("town-q").addEventListener("input", async (e) => {
    const q = fold(e.target.value.trim()), box = $("town-results");
    if (q.length < 2) { box.innerHTML = ""; atlas.hits = []; return; }
    await loadPlaces();
    if (fold($("town-q").value.trim()) !== q) return;
    atlas.hits = atlasMatches(q);
    box.innerHTML = atlas.hits.length ? atlas.hits.map((p, k) => `<button type="button" class="atlas-row atlas-hit" data-hit="${k}"><span>${esc(p.name)}</span><span>${esc(p.where)}</span></button>`).join("") : '<p class="muted">No match. Try a nearby town.</p>';
  });
  $("town-q").addEventListener("keydown", (e) => { if (e.key === "Enter" && atlas.hits.length) { e.preventDefault(); choose(atlas.hits[0]); } });
  $("town-results").addEventListener("click", (e) => { const b = e.target.closest("[data-hit]"); if (b) choose(atlas.hits[Number(b.dataset.hit)]); });
  $("town-try").addEventListener("click", (e) => { const b = e.target.closest("[data-try]"); if (b) choose(towns.examples[Number(b.dataset.try)]); });
  setupHeroCheck(choose);
  $("town-world").addEventListener("click", () => { if (!TOWN.g) return; TOWN.picked = null; townFlyTo({ ...townHome() }); });

  whenNear($("town-globe"), async () => {
    const [rows] = await Promise.all([fetch("data/atlas/towns.json").then((r) => r.json()), loadGlobeData(small())]);
    TOWN.rows = rows.map(([name, where, lat, lon]) => ({ name, where, lat, lon, lonR: lon * DEG, s: Math.sin(lat * DEG), c: Math.cos(lat * DEG) }));
    TOWN.xy = new Float32Array(2 * rows.length);
    const g = (TOWN.g = makeGlobe());
    const canvas = $("tg-canvas");
    globeResize(canvas, $("tg-glow"), g);
    Object.assign(g.view, { lon: -60 }, townHome());
    TOWN.loop = visibleLoop($("town-globe"), townFrame);
    // Picked before the globe was ready (the hero's search): go straight there.
    if (TOWN.picked) { const p = TOWN.picked; townFlyTo({ lon: p.lon, lat: p.lat, R: g.w / ((p.country ? 3000 : TOWN_ZOOM_KM) / EARTH_KM), cx: townCx(), cy: g.h / 2 }, 1); }
    townDraw();
    let again;
    addEventListener("resize", () => {
      clearTimeout(again);
      again = setTimeout(() => { const fov = g.w / g.view.R; globeResize(canvas, $("tg-glow"), g); Object.assign(g.view, { R: g.w / fov, cx: townCx(), cy: g.h / 2 }); townDraw(); }, 120);
    });
    // Hover a town light to see its name; click it to check it.
    const tip = $("town-tip");
    const nearest = (e) => {
      const r = canvas.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
      let best = -1, d2 = 100;
      for (let i = 0; i < TOWN.rows.length; i++) { const dx = TOWN.xy[2 * i] - x, dy = TOWN.xy[2 * i + 1] - y, d = dx * dx + dy * dy; if (d < d2) { d2 = d; best = i; } }
      return best < 0 ? null : { t: TOWN.rows[best], x, y };
    };
    canvas.addEventListener("pointermove", (e) => {
      const n = nearest(e);
      canvas.style.cursor = n ? "pointer" : "";
      tip.hidden = !n;
      if (n) { tip.textContent = `${n.t.name}, ${n.t.where}`; tip.style.left = `${n.x + 12}px`; tip.style.top = `${n.y + 12}px`; }
    });
    canvas.addEventListener("pointerleave", () => { tip.hidden = true; });
    canvas.addEventListener("click", (e) => { const n = nearest(e); if (n) choose({ name: n.t.name, where: n.t.where, lat: n.t.lat, lon: n.t.lon }); });
  });
}
