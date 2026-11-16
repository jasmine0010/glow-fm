
function drawGapBars(metrics) {
  const rows = metrics.audit.filter((r) => r.truth_wet_ha >= 100).sort((a, b) => b.truth_wet_ha - a.truth_wet_ha);
  const value = (x) => (x > 0 && x < 1 ? String(x) : ha(x));
  const label = (r) => [siteTitle(r.site).split(",")[0].replace(" River", ""), fmtDate(r.date).replace(/, \d{4}$/, "")];
  $("gap-bars").innerHTML = `<div class="gap-key" aria-hidden="true"><span><i class="gap-swatch gap-est"></i>Flooding estimated from gauges and lidar (square area, to scale)</span><span><i class="gap-swatch gap-gfm"></i>Flooding Copernicus GFM mapped, magnified in the loupe (drawn in the corner to compare sizes, not at its real place)</span></div>` +
    `<canvas class="gap-grains" role="img" aria-label="${rows.map((r) => `${label(r).join(", ")}: ${value(r.truth_wet_ha)} hectares estimated, ${value(r.gfm_on_wet_ha)} mapped by GFM`).join("; ")}"></canvas>`;
  const cv = $("gap-bars").querySelector("canvas"), est = "#6fe3ef", gfm = "#8fb4ff";
  const maxEst = rows[0].truth_wet_ha, maxGfm = Math.max(...rows.map((r) => r.gfm_on_wet_ha));
  const cols = () => { const w = cv.getBoundingClientRect().width; return w < 480 ? 1 : w < 760 ? 2 : 3; };
  const sideOf = (cw, C) => Math.min(150, cw * (C === 1 ? 0.3 : 0.42));
  const cellH = (w) => sideOf(w / cols(), cols()) + 74;
  cv.style.height = `${Math.ceil(rows.length / cols()) * cellH(cv.getBoundingClientRect().width || 900)}px`;
  Motion.instrument(cv, (ctx, t, w) => {
    const C = cols(), cw = w / C, S = sideOf(cw, C), H = S + 74, LR = Math.min(34, Math.max(20, cw * 0.09));
    const zoom = maxGfm > 0 ? Math.max(1, Math.round(Math.min(200, (LR * 0.9) / (S * Math.sqrt(maxGfm / maxEst))) / 10) * 10) : 100;
    const grow = Motion.ease(Motion.clamp(t / 0.6)), open = Motion.ease(Motion.clamp((t - 0.6) / 0.35));
    rows.forEach((r, i) => {
      const x0 = (i % C) * cw, y0 = Math.floor(i / C) * H, side = S * Math.sqrt((r.truth_wet_ha / maxEst) * grow);
      const bx = x0, by = y0 + 18 + S;
      const [place, day] = label(r);
      ctx.font = "600 13px 'IBM Plex Sans', system-ui, sans-serif"; ctx.fillStyle = "#f2f6f8"; ctx.textAlign = "left";
      ctx.fillText(place, x0, y0 + 12);
      ctx.font = "500 11px 'IBM Plex Sans', system-ui, sans-serif"; ctx.fillStyle = "#a7b9c5"; ctx.fillText(day, x0 + ctx.measureText(place).width * 1.18 + 8, y0 + 12);
      ctx.fillStyle = "rgba(111, 227, 239, .22)"; ctx.fillRect(bx, by - side, side, side);
      ctx.strokeStyle = est; ctx.lineWidth = 1; ctx.strokeRect(bx + 0.5, by - side + 0.5, side - 1, side - 1);
      ctx.font = "600 12px 'IBM Plex Sans', system-ui, sans-serif"; ctx.fillStyle = est;
      ctx.fillText(`${value(t >= 1 ? r.truth_wet_ha : r.truth_wet_ha * grow)} ha`, x0, by + 16);
      if (open <= 0) return;
      const lx = bx + S * Math.sqrt(r.truth_wet_ha / maxEst) + LR + 18, ly = by - LR - 4, rr = LR * open;
      ctx.strokeStyle = "rgba(205, 225, 235, .45)"; ctx.beginPath(); ctx.moveTo(bx + 2, by - 2); ctx.lineTo(lx - rr * 0.7, ly + rr * 0.7); ctx.stroke();
      ctx.save(); ctx.beginPath(); ctx.arc(lx, ly, rr, 0, 2 * Math.PI); ctx.fillStyle = "#03060a"; ctx.fill(); ctx.clip();
      const cx = lx - rr * 0.55, cy = ly + rr * 0.55;
      ctx.fillStyle = "rgba(111, 227, 239, .22)"; ctx.fillRect(cx, cy - rr * 2, rr * 3, rr * 2);
      ctx.strokeStyle = est; ctx.beginPath(); ctx.moveTo(cx + 0.5, cy - rr * 2); ctx.lineTo(cx + 0.5, cy + 0.5); ctx.lineTo(cx + rr * 3, cy + 0.5); ctx.stroke();
      const g = S * Math.sqrt(r.gfm_on_wet_ha / maxEst) * zoom * open;
      if (g > 0) { ctx.fillStyle = gfm; ctx.fillRect(cx + 1, cy - g, g, g); }
      ctx.restore();
      ctx.strokeStyle = "rgba(242, 246, 248, .8)"; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.arc(lx, ly, rr, 0, 2 * Math.PI); ctx.stroke(); ctx.lineWidth = 1;
      ctx.font = "500 11px 'IBM Plex Sans', system-ui, sans-serif"; ctx.fillStyle = "#a7b9c5"; ctx.fillText(`×${zoom}`, lx + LR + 6, ly - LR + 10);
      ctx.font = "600 12px 'IBM Plex Sans', system-ui, sans-serif"; ctx.fillStyle = gfm;
      ctx.fillText(`${value(r.gfm_on_wet_ha)} ha`, lx + LR + 6, ly + 4);
      ctx.font = "500 11px 'IBM Plex Sans', system-ui, sans-serif"; ctx.fillStyle = "#a7b9c5"; ctx.fillText(r.gfm_on_wet_ha > 0 ? "mapped by GFM" : "nothing mapped", lx + LR + 6, ly + 18);
    });
  }, { ms: 2600 });
}

function setupHeroCheck(choose) {
  const input = $("hero-q"), box = $("hero-results");
  if (!input) return;
  let hits = [];
  const go = (hit) => {
    box.innerHTML = "";
    input.value = hit.where && hit.where !== "country" && hit.where !== "river" ? `${hit.name}, ${hit.where}` : hit.name;
    const gap = () => $("towns").getBoundingClientRect().top - ((document.querySelector(".topbar")?.offsetHeight || 47) + 12);
    scrollTo({ top: scrollY + gap(), behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    let moved = false;
    const stop = () => { moved = true; };
    setTimeout(() => ["wheel", "touchmove", "keydown"].forEach((t) => addEventListener(t, stop, { once: true, passive: true })), 0);
    [1100, 2200, 3500].forEach((ms) => setTimeout(() => { if (moved) return; const off = gap(); if (Math.abs(off) > 4 && Math.abs(off) < 400) scrollTo({ top: scrollY + off, behavior: "auto" }); }, ms));
    choose(hit);
    $("town-label").setAttribute("tabindex", "-1");
    setTimeout(() => $("town-label").focus({ preventScroll: true }), 50);
  };
  input.addEventListener("input", async () => {
    const q = fold(input.value.trim());
    if (q.length < 2) { box.innerHTML = ""; hits = []; return; }
    await loadPlaces();
    if (fold(input.value.trim()) !== q) return;
    hits = atlasMatches(q);
    box.innerHTML = hits.length ? hits.map((p, k) => `<button type="button" class="atlas-row atlas-hit" data-hit="${k}"><span>${esc(p.name)}</span><span>${esc(p.where)}</span></button>`).join("") : '<p class="muted">No match. Try a nearby town.</p>';
  });
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && hits.length) { e.preventDefault(); go(hits[0]); } });
  box.addEventListener("click", (e) => { const b = e.target.closest("[data-hit]"); if (b) go(hits[Number(b.dataset.hit)]); });
}

async function setupCharts(manifest, metrics) {
  drawGapBars(metrics);
  const [charts, summary] = await Promise.all([fetch("data/story/charts.json").then((r) => r.json()), loadAtlas()]);
  const w = charts.watching, hero = manifest.hero, passT = Date.parse(hero.time);
  const at = (g, t) => g.rows.reduce((best, r) => (Math.abs(Date.parse(r[0]) - t) < Math.abs(Date.parse(best[0]) - t) ? r : best))[1];
  const above = w.gauges.filter((g) => at(g, passT) > 0).length, next = w.gfm.find((g) => g.covered > 0 && Date.parse(`${g.date}T12:00Z`) > passT);
  $("jf-5").textContent = `NISAR passed over on ${fmtDay(hero.time)}, close to the crest, with ${inWords(above)} of ${inWords(w.gauges.length)} gauges above flood level.${next ? ` The next Copernicus GFM scene covering this stretch came on ${fmtDay(`${next.date}T12:00Z`)}, after the river had started to fall. GFM's catalog lists no scene covering this stretch in between; we didn't establish why, and other Sentinel-1 data may exist.` : ""}`;
  setupTownGlobe(summary);
}
