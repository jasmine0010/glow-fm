// The scientific figures (Results page, Fig. 1–11, and the story's headline figures), drawn with figkit.js from
// data/figures/*.json (scripts/build_figures.py), data/metrics.json and data/story/charts.json. Every number on them is
// read from those files. Mount one with <div class="fig-mount" data-fig="accuracy" data-only="a"></div>; it draws
// when it comes near the screen. Style: journal figures (boxed axes, outward ticks, framed legends, no gridlines).

const FIG_CACHE = {};
const figJson = (path) => (FIG_CACHE[path] ??= fetch(`data/${path}`).then((r) => r.json()));
const FIG_SHORT = (site) => siteTitle(site).split(",")[0];
const figDb = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)} dB`;
const figKm2 = (x) => `${Math.round(x).toLocaleString("en-US")} km²`;
const passDay = (pair) => passDate(pair);
const wide = (W) => W >= 760;
const PCT = (x) => `${Math.round(100 * x)}%`;
const n0f = (x) => Math.round(x).toLocaleString("en-US");
const refLine = (g, x1, y1, x2, y2) => fkEl(g, "line", { x1, y1, x2, y2, class: "fk-ref" });

// ---------- Fig. 1: study design ----------
async function figStudy(box, only) {
  const d = await figJson("figures/study.json");
  const start = Date.parse("2026-06-10T00:00Z"), end = Date.parse("2026-11-15T00:00Z");   // through Nov 14
  const rivers = [...d.rivers].sort((a, b) => Math.min(...a.passes.map((p) => Date.parse(p.time))) - Math.min(...b.passes.map((p) => Date.parse(p.time))));
  const bh = 40 + rivers.length * 24 + 56;
  fkFigure(box, {
    name: "fig1-study-design", label: `Map and observation timeline of the ${rivers.length} test rivers`,
    height: (W) => (only === "b" ? bh : only === "a" ? 330 : wide(W) ? bh : 330 + 16 + bh),
    csv: () => [["river", "role", "pass", "wet_time", "frozen_test"], ...rivers.flatMap((r) => r.passes.map((p) => [r.id, r.role, p.pair, p.time, p.tested]))],
    draw(svg, W, H, tip) {
      const showA = only !== "b", showB = only !== "a", side = wide(W) && showA && showB;
      if (showA) {
        const pw = side ? W * 0.4 : W, ph = side ? H : 330;
        const p = fkPanel(svg, { x: 0, y: 0, w: pw, h: ph, letter: only ? null : "a", title: "Study rivers", m: { t: 30, r: 10, b: 30, l: 44 } });
        const [w0, s0, e0, n0] = d.box, aspect = ((e0 - w0) * Math.cos((31 * Math.PI) / 180)) / (n0 - s0);
        const mw = Math.min(p.w, p.h * aspect), mh = mw / aspect, q = { g: p.g, w: mw, h: mh, x: p.x, y: p.y };
        const sx = fkLinear(w0, e0, 0, mw), sy = fkLinear(s0, n0, mh, 0);
        const clip = fkEl(fkEl(svg, "defs"), "clipPath", { id: `fk-study-clip-${only || "all"}` });
        fkEl(clip, "rect", { x: 0, y: 0, width: mw, height: mh });
        fkEl(p.g, "rect", { x: 0, y: 0, width: mw, height: mh, class: "fk-sea" });
        const g = fkEl(p.g, "g", { "clip-path": `url(#fk-study-clip-${only || "all"})` });
        d.coast.forEach((line) => fkEl(g, "path", { d: fkPath(line.map(([x, y]) => [sx(x), sy(y)])), class: "fk-coast" }));
        fkAxes(q, sx, sy, { xticks: [-95, -90, -85, -80, -75], yticks: [25, 30, 35], xfmt: (v) => `${-v}°W`, yfmt: (v) => `${v}°N` });
        const pts = [];
        rivers.forEach((r) => {
          const x = sx(r.center[0]), y = sy(r.center[1]), rad = 2 + Math.sqrt(r.labelled_ha) / 30;
          fkMark(p.g, "o", x, y, r.role === "held-out" ? "f-nisar" : "f-none s-veil", rad, { "fill-opacity": 0.7, "stroke-width": 1.2 });
          pts.push({ x, y, html: `<b>${siteTitle(r.id)}</b><br>${r.role === "held-out" ? "frozen tests" : "development only"} · ${r.passes.length} NISAR pass${r.passes.length > 1 ? "es" : ""}<br>${ha(r.labelled_ha)} ha labelled flooding` });
        });
        fkKey(q, [["o", "f-nisar", "Frozen test"], ["o", "f-none s-veil", "Development only"]], "br");
        fkHover(q, tip, (px, py) => fkNearest(pts, px, py, 24));
      }
      if (showB) {
        const top = showA && !side ? 346 : 0, x0 = side ? W * 0.4 + 14 : 0, pw = W - x0, ph = H - top;
        const p = fkPanel(svg, { x: x0, y: top, w: pw, h: ph, letter: only ? null : "b", title: "Observation timeline, 2026", m: { t: 30, r: 10, b: 56, l: wide(W) ? 112 : 96 } });
        const sx = fkTime(start, end, 0, p.w), row = p.h / rivers.length;
        fkAxes(p, sx, fkLinear(0, 1, p.h, 0), { yticks: [], xfmt: fkDay });
        const pts = [];
        rivers.forEach((r, k) => {
          const y = k * row, mid = y + row / 2;
          fkEl(p.g, "line", { x1: -FK_TICK, x2: 0, y1: mid, y2: mid, class: "fk-spine" });
          fkEl(p.g, "text", { x: -FK_TICK - 3, y: mid + 4, class: "fk-tick", "text-anchor": "end" }, wide(W) ? FIG_SHORT(r.id) : FIG_SHORT(r.id).replace(/ River$/, ""));
          if (r.hydro) {
            const base = y + row - 2, line = r.hydro.times.map((t, i) => [sx(Date.parse(`${t}Z`)), base - (r.hydro.rel[i] ?? NaN) * (row - 6)]).filter((q) => q[0] >= 0 && q[0] <= p.w);
            if (line.length > 2) fkEl(p.g, "path", { d: fkPath(line) + `L${line[line.length - 1][0]} ${base}L${line[0][0]} ${base}Z`, class: "f-water", "fill-opacity": 0.3 });
          }
          r.passes.forEach((q) => {
            const x = sx(Date.parse(q.time));
            fkEl(p.g, "line", { x1: x, x2: x, y1: y + 3, y2: y + row - 3, class: q.tested ? "s-nisar" : "s-veil", "stroke-width": 1.5 });
            pts.push({ x, y: mid, html: `<b>${siteTitle(r.id)}</b><br>NISAR pass ${q.pair.split("_")[0]}, ${fkDay(Date.parse(q.time))}<br>${q.tested ? "a frozen one-time test" : "development"}` });
          });
          d.gfm.filter((g) => g.river === r.id).forEach((g) => {
            const t = Date.parse(`${g.date.slice(0, 4)}-${g.date.slice(4, 6)}-${g.date.slice(6, 8)}T12:00Z`), x = sx(t);
            fkMark(p.g, "s", x, mid, "f-official", 3);
            pts.push({ x, y: mid, html: `<b>${siteTitle(r.id)}</b><br>Copernicus GFM scene audited, ${fkDay(t)}` });
          });
        });
        fkLegend(svg, p.x, top + ph - 8, [["line", "s-nisar", "NISAR pass, frozen test"], ["line", "s-veil", "NISAR pass, other"], ["s", "f-official", "GFM scene audited"], ["patch", "f-water", "Relative stage"]]);
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 16));
      }
    },
  });
}

// ---------- Fig. 2: the physical signature ----------
async function figSignature(box, only) {
  const d = await figJson("figures/signature.json");
  const edges = d.hh_edges, bins = d.bins.filter((b) => b.n >= 40);
  fkFigure(box, {
    name: "fig2-physical-signature", label: "Radar brightening of floodplain forest against water depth: distributions, every pass's median curve, and C-band against L-band",
    height: (W) => (only === "a" ? (wide(W) ? 460 : 556) : wide(W) && !only ? 560 : only ? 320 : 556 + 16 + 300 + 16 + 300),
    csv: () => [["water_above_ground_lo_m", "water_above_ground_hi_m", "pixels", "hh_q25_db", "hh_median_db", "hh_q75_db", "hv_median_db", ...edges.slice(0, -1).map((e) => `count_hh_${e}`)],
      ...d.bins.map((b) => [b.lo, b.hi, b.n, ...b.hh_q, b.hv_q[1], ...b.counts])],
    draw(svg, W, H, tip) {
      const side = wide(W) && !only, depthLabel = "Water depth above forest floor (m)";
      // (a) the ridgeline: one distribution per half metre of water, dry ground at the bottom, drawn back to front
      if (!only || only === "a") {
        const pw = side ? W * 0.52 : W, ph = only === "a" ? H : side ? H : 556;
        const n = d.pooled_from.length, px = bins.reduce((s, b) => s + b.n, 0);
        const p = fkPanel(svg, { x: 0, y: 0, w: pw, h: ph, letter: only ? null : "a", title: `ΔHH by water depth, forest pixels (${n} passes, n = ${n0f(px)})`, m: { t: 30, r: 14, b: wide(W) ? 42 : 78, l: 62 } });
        const sx = fkLinear(edges[0], edges[edges.length - 1], 0, p.w), step = p.h / (bins.length + 3.2), amp = step * 2.4;
        const baseOf = (k) => p.h - (k + 0.7) * step;
        fkAxes(p, sx, fkLinear(0, 1, p.h, 0), { xlabel: "ΔHH (dB)", yticks: [], ylabel: depthLabel, ylabelX: -50, xfmt: (v) => `${v > 0 ? "+" : ""}${v}` });
        refLine(p.g, sx(0), 0, sx(0), p.h);
        const pts = [];
        bins.map((b, k) => [b, k]).reverse().forEach(([b, k]) => {
          const base = baseOf(k), peak = Math.max(...b.counts), dry = b.hi <= 0;
          const line = b.counts.map((c, i) => [sx((edges[i] + edges[i + 1]) / 2), base - (c / peak) * amp]);
          fkEl(p.g, "path", { d: `M${sx(edges[0])} ${base}` + line.map(([x, y]) => `L${x.toFixed(1)} ${y.toFixed(1)}`).join("") + `L${sx(edges[edges.length - 1])} ${base}Z`, class: dry ? "f-veil s-veil" : "f-water s-water", "fill-opacity": dry ? 0.35 : 0.5, "stroke-width": 0.9 });
          const m = b.hh_q[1];
          fkEl(p.g, "line", { x1: sx(m), x2: sx(m), y1: base, y2: base - amp * 0.45, class: "s-ink", "stroke-width": 1.5 });
          const hero = d.hero && d.hero.find((h) => h.bin === d.bins.indexOf(b));
          if (hero && hero.hh !== null) fkMark(p.g, "D", sx(hero.hh), base - 3, "f-none s-nisar", 3, { "stroke-width": 1.3 });
          fkEl(p.g, "line", { x1: -FK_TICK, x2: 0, y1: base, y2: base, class: "fk-spine" });
          fkEl(p.g, "text", { x: -FK_TICK - 3, y: base + 4, class: "fk-tick", "text-anchor": "end" }, fkMinus(`${b.lo > 0 ? "+" : ""}${b.lo.toFixed(1)}`));
          pts.push({ x: sx(m), y: base - amp * 0.3, html: `<b>Water ${b.lo >= 0 ? "+" : ""}${b.lo} to ${b.hi >= 0 ? "+" : ""}${b.hi} m ${b.hi <= 0 ? "(below the forest floor)" : "above the forest floor"}</b><br>${ha(b.ha)} ha of forest, ${b.n.toLocaleString("en-US")} pixels<br>median ΔHH ${figDb(m)} · interquartile ${figDb(b.hh_q[0])} to ${figDb(b.hh_q[2])}` });
        });
        const key2a = [["line", "s-ink", "Median"], ["D", "f-none s-nisar", `Satilla, ${passDay("047A_oct15")}`], ["patch", "f-water", "Depth > 0 (flooded)"], ["patch", "f-veil", "Depth ≤ 0 (dry)"]];
        if (wide(W)) fkKey(p, key2a, "tr"); else fkLegend(svg, 6, ph - 26, key2a);
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 60));
      }
      const curvesPanel = (x, y, w, h, letter) => {
        const p = fkPanel(svg, { x, y, w, h, letter, title: `Median backscatter change, ${d.passes.length} passes` });
        const sx = fkLinear(-5, 3, 0, p.w), sy = fkLinear(-1, 4, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: depthLabel, ylabel: "Δγ⁰ (dB)" });
        refLine(p.g, sx(0), 0, sx(0), p.h);
        const band = d.bins.filter((b) => b.hh_q[0] !== null), mid = (b) => sx((b.lo + b.hi) / 2);
        fkEl(p.g, "path", { d: fkPath(band.map((b) => [mid(b), sy(b.hh_q[2])])) + band.slice().reverse().map((b) => `L${mid(b)} ${sy(b.hh_q[0])}`).join("") + "Z", class: "f-nisar", "fill-opacity": 0.15 });
        const pts = [];
        d.passes.forEach((q) => {
          fkEl(p.g, "path", { d: fkPath(q.curve.map((c) => [sx(c.water_above_ground_m), sy(c.hh_db)])), class: q.role === "held-out" ? "s-nisar" : "s-veil", fill: "none", "stroke-width": 0.8, "stroke-opacity": 0.5 });
          q.curve.forEach((c) => pts.push({ x: sx(c.water_above_ground_m), y: sy(c.hh_db), html: `<b>${siteTitle(q.river)}, ${passDay(q.pair)}</b> (${q.role})<br>${c.water_above_ground_m >= 0 ? "+" : ""}${c.water_above_ground_m} m: HH ${figDb(c.hh_db)}, HV ${figDb(c.hv_db)}` }));
        });
        fkEl(p.g, "path", { d: fkPath(band.map((b) => [mid(b), sy(b.hh_q[1])])), class: "s-nisar", fill: "none", "stroke-width": 2 });
        fkEl(p.g, "path", { d: fkPath(band.map((b) => [mid(b), sy(b.hv_q[1])])), class: "s-ink", fill: "none", "stroke-width": 1.5, "stroke-dasharray": "5 3" });
        fkKey(p, [["line", "s-nisar", "HH, pooled median"], ["patch", "f-nisar", "HH, interquartile range"], ["line", "s-ink", "HV, pooled median", "5 3"], ["line", "s-veil", "Single pass"]], "tl");
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 14));
      };
      const bandPanel = (x, y, w, h, letter) => {
        const p = fkPanel(svg, { x, y, w, h, letter, title: "C-band against L-band, Pearl River" });
        const c = d.pearl, sx = fkLinear(-5, 3, 0, p.w), sy = fkLinear(-1.5, 3, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: depthLabel, ylabel: "Δγ⁰ (dB)" });
        refLine(p.g, sx(0), 0, sx(0), p.h);
        refLine(p.g, 0, sy(0), p.w, sy(0));
        const pts = [];
        const line = (rows, key, cls, dash, label) => {
          fkEl(p.g, "path", { d: fkPath(rows.map((r) => [sx(r.water_above_ground_m), sy(r[key])])), class: cls, fill: "none", "stroke-width": 1.5, "stroke-dasharray": dash });
          rows.forEach((r) => { fkMark(p.g, "o", sx(r.water_above_ground_m), sy(r[key]), cls.replace("s-", "f-"), 2.2); pts.push({ x: sx(r.water_above_ground_m), y: sy(r[key]), html: `<b>${label}</b><br>${r.water_above_ground_m >= 0 ? "+" : ""}${r.water_above_ground_m} m: ${figDb(r[key])} (${ha(r.ha)} ha)` }); });
        };
        line(c.l_band, "hh_db", "s-nisar", null, "NISAR L-band, HH");
        line(c.c_band, "vv_db", "s-official", null, "Sentinel-1 C-band, VV");
        line(c.c_band, "vh_db", "s-official", "4 3", "Sentinel-1 C-band, VH");
        fkKey(p, [["line", "s-nisar", "NISAR L-band (24 cm), HH"], ["line", "s-official", "Sentinel-1 C-band (5.6 cm), VV"], ["line", "s-official", "Sentinel-1 C-band (5.6 cm), VH", "4 3"]], "tl");
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 14));
      };
      if (!only) {
        if (side) { curvesPanel(W * 0.52 + 12, 0, W * 0.48 - 12, H / 2 - 4, "b"); bandPanel(W * 0.52 + 12, H / 2 + 4, W * 0.48 - 12, H / 2 - 4, "c"); }
        else { curvesPanel(0, 572, W, 300, "b"); bandPanel(0, 888, W, 300, "c"); }
      } else if (only === "b") curvesPanel(0, 0, W, H, null);
      else if (only === "c") bandPanel(0, 0, W, H, null);
    },
  });
}

// ---------- Fig. 3: separability ----------
async function figSeparability(box) {
  const d = await figJson("figures/separability.json");
  const edges = d.hh_edges;
  let pick = d.passes.findIndex((p) => p.river === "satilla" && p.pair === "047A_oct15");
  const ctl = document.createElement("label");
  ctl.className = "fk-control";
  ctl.innerHTML = `Pass shown in <b>a</b> <select>${d.passes.map((p, k) => `<option value="${k}"${k === pick ? " selected" : ""}>${FIG_SHORT(p.river)}, ${passDay(p.pair)}</option>`).join("")}</select>`;
  const fig = fkFigure(box, {
    name: "fig3-separability", label: "Wet against dry pixel distributions with the frozen cut-off, and ROC curves for every judged pass",
    height: (W) => (wide(W) ? 520 : 320 + 30 + Math.ceil(d.passes.length / 2) * 160 + 40),
    csv: () => [["river", "pair", "signal", "frozen_cutoff_db", "auc_hh", "csi", "trust_light", "bin_lo_db", "wet_pixels", "dry_pixels"],
      ...d.passes.flatMap((p) => p.wet_hist.map((c, i) => [p.river, p.pair, p.signal, p.cutoff_db, p.auc, p.csi, p.trust, edges[i], c, p.dry_hist[i]]))],
    draw(svg, W, H, tip) {
      const q = d.passes[pick], side = wide(W);
      const p = fkPanel(svg, { x: 0, y: 0, w: side ? W * 0.5 : W, h: side ? H : 320, letter: "a", title: `Signal distribution, ${FIG_SHORT(q.river)}, ${passDay(q.pair)}` });
      const tot = (a) => a.reduce((s, v) => s + v, 0), nw = tot(q.wet_hist), nd = tot(q.dry_hist);
      const dens = (a, n) => a.map((c) => c / n / (edges[1] - edges[0]));
      const dw = dens(q.wet_hist, nw), dd = dens(q.dry_hist, nd), sx = fkLinear(edges[0], edges[edges.length - 1], 0, p.w), sy = fkLinear(0, Math.max(...dw, ...dd) * 1.1, p.h, 0);
      fkAxes(p, sx, sy, { xlabel: q.signal === "HH" ? "ΔHH, smoothed (dB)" : "ΔHH − ΔHV, smoothed (dB)", ylabel: "Density (dB⁻¹)", yfmt: (v) => v.toFixed(1) });
      const stepPath = (vals) => `M${sx(edges[0])} ${p.h}` + vals.map((v, i) => `L${sx(edges[i])} ${sy(v)}L${sx(edges[i + 1])} ${sy(v)}`).join("") + `L${sx(edges[edges.length - 1])} ${p.h}`;
      fkEl(p.g, "path", { d: stepPath(dd) + "Z", class: "f-veil", "fill-opacity": 0.35 });
      fkEl(p.g, "path", { d: stepPath(dw) + "Z", class: "f-water", "fill-opacity": 0.35 });
      fkEl(p.g, "path", { d: stepPath(dd), class: "s-veil", fill: "none", "stroke-width": 1.2 });
      fkEl(p.g, "path", { d: stepPath(dw), class: "s-water", fill: "none", "stroke-width": 1.2 });
      fkEl(p.g, "line", { x1: sx(q.cutoff_db), x2: sx(q.cutoff_db), y1: 0, y2: p.h, class: "s-nisar", "stroke-width": 1.5, "stroke-dasharray": "5 3" });
      fkKey(p, [["patch", "f-water", `Flooded (n = ${n0f(nw)})`], ["patch", "f-veil", `Dry (n = ${n0f(nd)})`], ["line", "s-nisar", `Frozen cut-off, ${figDb(q.cutoff_db)}`, "5 3"]], "tr");
      fkHover(p, tip, (px) => { const v = sx.invert(px), i = Math.max(0, Math.min(edges.length - 2, Math.floor((v - edges[0]) / (edges[1] - edges[0])))); return { x: sx((edges[i] + edges[i + 1]) / 2), y: sy(Math.max(dw[i], dd[i])), html: `${figDb(edges[i])} to ${figDb(edges[i + 1])}<br>flooded ${q.wet_hist[i].toLocaleString("en-US")} px · dry ${q.dry_hist[i].toLocaleString("en-US")} px` }; });
      // (b) ROC small multiples on shared axes
      const x0 = side ? W * 0.5 + 16 : 0, y0 = side ? 0 : 350, cols = side ? 3 : 2, n = d.passes.length, rows = Math.ceil(n / cols);
      const gx = x0 + 16, cw = (W - gx) / cols, ch = side ? (H - 24 - 26) / rows : 160;
      fkEl(svg, "text", { x: x0, y: y0 + 13, class: "fk-letter" }, "b");
      fkEl(svg, "text", { x: x0 + 16, y: y0 + 13, class: "fk-ptitle" }, "ROC curves, ΔHH (smoothed), forest and wetland");
      d.passes.forEach((r, k) => {
        const c = k % cols, rr = Math.floor(k / cols);
        const sp = fkPanel(svg, { x: gx + c * cw, y: y0 + 22 + rr * ch, w: cw, h: ch, title: `${FIG_SHORT(r.river).replace(/ River$/, "")}, ${passDay(r.pair)}`, m: { t: 24, r: 12, b: 24, l: 28 } });
        const s = fkLinear(0, 1, 0, sp.w), t = fkLinear(0, 1, sp.h, 0), f = (v) => (v === 0.5 ? "0.5" : String(v));
        fkAxes(sp, s, t, { xticks: [0, 0.5, 1], yticks: [0, 0.5, 1], xfmt: f, yfmt: f });
        refLine(sp.g, 0, sp.h, sp.w, 0);
        fkEl(sp.g, "path", { d: fkPath(r.roc.map(([fp, tp]) => [s(fp), t(tp)])), class: r.trust === "green" ? "s-green" : "s-red", fill: "none", "stroke-width": 1.5 });
        fkEl(sp.g, "text", { x: sp.w - 4, y: sp.h - 5, class: "fk-tick", "text-anchor": "end" }, `AUC = ${r.auc.toFixed(2)}`);
      });
      const yb = y0 + 22 + rows * ch;
      fkEl(svg, "text", { x: gx + (W - gx) / 2, y: yb + 14, class: "fk-label", "text-anchor": "middle" }, "False positive rate");
      fkEl(svg, "text", { x: -(y0 + 22 + (rows * ch) / 2), y: gx - 2, class: "fk-label", "text-anchor": "middle", transform: "rotate(-90)" }, "True positive rate");
      const slot = n % cols ? n : null;
      if (slot !== null) fkLegend(svg, gx + (slot % cols) * cw + 36, y0 + 22 + Math.floor(slot / cols) * ch + 40, [["line", "s-green", "Trust light green"], ["line", "s-red", "Trust light red"]], cw - 44);
      else fkLegend(svg, gx, yb + 34, [["line", "s-green", "Trust light green"], ["line", "s-red", "Trust light red"]]);
    },
  });
  box.prepend(ctl);
  ctl.querySelector("select").addEventListener("change", (e) => { pick = Number(e.target.value); fig.render(); });
}

// ---------- Fig. 5: accuracy ----------
async function figAccuracy(box, only) {
  const metrics = (await loadData())[1], refSelf = (await figJson("figures/reference.json")).summary.median_agreement;
  const ob = new Map(metrics.overbank.map((o) => [`${o.site} ${o.pair}`, o]));
  const short = (r) => `${FIG_SHORT(r.site).replace(/ River$/, "")}, ${passDay(r.pair)}`;
  const groups = [["Method 1, fixed cut-off", "v1", "Method 1"], ["Method 2, self-calibrating", "v2", "Method 2"], ["Method 3, Otsu", "v3", "Method 3"], ["Method 4, first test", "v4, median", "Method 4, first"], ["Method 4, latest test", "v4, overbank", "Method 4, latest"]];
  const rows = [];
  groups.forEach(([label, prefix, brief]) => {
    const g = metrics.held_out.filter((r) => r.method.startsWith(prefix)).sort((a, b) => (b.csi ?? -1) - (a.csi ?? -1));
    if (g.length) { rows.push({ head: label, brief }); g.forEach((r) => rows.push({ r, o: prefix === "v4, overbank" ? ob.get(`${r.site} ${r.pair}`) : null, judged: r.csi !== null && r.csi !== undefined && (r.confirmed_ha ?? r.estimated_ha) >= JUDGE_HA })); }
  });
  const scored = metrics.held_out.filter((r) => r.recall !== undefined && r.recall !== null);
  const forest = 30 + rows.length * 19 + 46, forestH = (W) => forest + (wide(W) ? 0 : 40);
  fkFigure(box, {
    name: "fig5-accuracy", label: "Match score with 95% intervals for every frozen test, against a lidar-only map, and precision against recall",
    height: (W) => (only === "a" ? forestH(W) : only === "b" ? 420 : wide(W) ? Math.max(forest, 440) : forestH(W) + 16 + 400),
    csv: () => [["river", "pass", "method", "csi", "csi_lo", "csi_hi", "recall", "precision", "lidar_csi", "judged"], ...rows.filter((x) => x.r).map(({ r, o, judged }) => [r.site, r.pair, r.method, r.csi, r.ci95?.[0], r.ci95?.[1], r.recall, r.precision, o?.lidar_csi, judged])],
    draw(svg, W, H, tip) {
      const side = wide(W) && !only;
      if (only !== "b") {
        const pw = side ? W * 0.56 : W;
        const p = fkPanel(svg, { x: 0, y: 0, w: pw, h: forestH(W), letter: only ? null : "a", title: `CSI of each frozen one-time test (n = ${metrics.held_out.length})`, m: { t: 30, r: 14, b: wide(W) ? 46 : 86, l: Math.min(190, pw * 0.42) } });
        const sx = fkLinear(0, 1, 0, p.w), rh = p.h / rows.length;
        fkAxes(p, sx, fkLinear(0, 1, p.h, 0), { xlabel: "Critical success index (CSI)", yticks: [], xfmt: (v) => v.toFixed(1) });
        // How well the reference matches itself with one gauge hidden (Fig. 10): scores near it are about as close as it can tell.
        fkEl(p.g, "line", { x1: sx(refSelf), x2: sx(refSelf), y1: 0, y2: p.h, class: "s-water", "stroke-width": 1.2, "stroke-dasharray": "5 4", "stroke-opacity": 0.8 });
        const pts = [];
        rows.forEach((x, k) => {
          const y = (k + 0.5) * rh;
          if (x.head) {
            if (k) fkEl(p.g, "line", { x1: 0, x2: p.w, y1: k * rh, y2: k * rh, class: "fk-sep" });
            fkEl(p.g, "text", { x: -FK_TICK - 3, y: y + 4, class: "fk-tick fk-strong", "text-anchor": "end" }, wide(W) ? x.head : x.brief);
            return;
          }
          const { r, o, judged } = x;
          fkEl(p.g, "line", { x1: -FK_TICK, x2: 0, y1: y, y2: y, class: "fk-spine" });
          fkEl(p.g, "text", { x: -FK_TICK - 3, y: y + 4, class: "fk-tick", "text-anchor": "end" }, wide(W) ? `${FIG_SHORT(r.site)}, ${passDay(r.pair)}` : short(r));
          if (r.csi === null || r.csi === undefined) { fkEl(p.g, "text", { x: 6, y: y + 4, class: "fk-tick fk-dim" }, "n/a"); return; }
          const cls = judged ? "s-nisar" : "s-veil";
          if (r.ci95) fkErr(p.g, sx(r.ci95[0]), y, sx(r.ci95[1]), y, cls);
          fkMark(p.g, "o", sx(r.csi), y, judged ? "f-nisar" : "f-veil", 3.5);
          if (o && o.lidar_csi !== null) fkMark(p.g, "D", sx(o.lidar_csi), y, "f-none s-ink", 3.5, { "stroke-width": 1.2 });
          pts.push({ x: sx(r.csi), y, html: `<b>${siteTitle(r.site)}, ${passDay(r.pair)}</b><br>${r.method}<br>CSI ${r.csi.toFixed(2)}${r.ci95 ? ` (95% ${r.ci95[0].toFixed(2)}–${r.ci95[1].toFixed(2)})` : ""}${o && o.lidar_csi !== null ? `<br>lidar-only map ${o.lidar_csi.toFixed(2)}` : ""}${judged ? "" : "<br>too little flooding to judge"}` });
        });
        const key4a = [["errbar", "f-nisar s-nisar", "NISAR, 95% CI"], ["D", "f-none s-ink", "Lidar-only map"], ["errbar", "f-veil s-veil", `< ${n0f(JUDGE_HA)} ha flooded (not judged)`], ["line", "s-water", `Reference vs itself, ${refSelf.toFixed(2)}`, "5 4"]];
        if (wide(W)) fkKey(p, key4a, "br"); else fkLegend(svg, 6, forestH(W) - 30, key4a);
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 18));
      }
      if (only !== "a") {
        const x0 = side ? W * 0.56 + 18 : 0, y0 = side || only ? 0 : forestH(W) + 16, pw = W - x0, ph = only ? H : side ? Math.min(H, 440) : 400;
        const p = fkPanel(svg, { x: x0, y: y0, w: pw, h: ph, letter: only ? null : "b", title: `Precision against recall (n = ${scored.length})` });
        const s = fkLinear(0, 1, 0, p.w), t = fkLinear(0, 1, p.h, 0);
        fkAxes(p, s, t, { xlabel: "Recall", ylabel: "Precision", xfmt: (v) => v.toFixed(1), yfmt: (v) => v.toFixed(1) });
        [0.2, 0.4, 0.6, 0.8].forEach((c) => {
          const line = [];
          for (let R = c + 0.001; R <= 1.0001; R += 0.005) { const P = 1 / (1 / c + 1 - 1 / R); if (P > 0 && P <= 1) line.push([s(R), t(P)]); }
          fkEl(p.g, "path", { d: fkPath(line), class: "s-veil", fill: "none", "stroke-width": 0.8, "stroke-dasharray": "3 3" });
          const end = line[line.length - 1];
          const lab = line[Math.max(0, line.length - 14)];
          if (lab) fkEl(p.g, "text", { x: lab[0] - 3, y: lab[1] - 4, class: "fk-tick fk-dim", "text-anchor": "end" }, String(c));
        });
        const pts = [];
        scored.forEach((r) => {
          const o = ob.get(`${r.site} ${r.pair}`), x = s(r.recall), y = t(r.precision), light = o ? o.signal : null;
          if (light === "red") fkMark(p.g, "^", x, y, "f-red", 4.5);
          else if (light === "green") fkMark(p.g, "o", x, y, "f-green", 4.5);
          else fkMark(p.g, "s", x, y, "f-veil", 3.5);
          pts.push({ x, y, html: `<b>${siteTitle(r.site)}, ${passDay(r.pair)}</b><br>recall ${PCT(r.recall)} · precision ${PCT(r.precision)} · CSI ${r.csi.toFixed(2)}${light ? `<br>trust light ${light}` : ""}` });
        });
        fkKey(p, [["o", "f-green", "Trust light green"], ["^", "f-red", "Trust light red"], ["s", "f-veil", "Earlier test (no light)"]], "br");
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 16));
      }
    },
  });
}

// ---------- Fig. 6: where it works ----------
async function figStrata(box) {
  const d = await figJson("figures/strata.json"), metrics = (await loadData())[1];
  const [green, all] = d.groups, ob = metrics.overbank.filter((o) => o.judgeable);
  fkFigure(box, {
    name: "fig6-where-it-works", label: "Recall and precision by water depth, height above the river and land cover, and the trust light against the outcome",
    height: (W) => (wide(W) ? 620 : 4 * 290),
    csv: () => [["group", "stratum", "label", "recall", "recall_lo", "recall_hi", "precision", "precision_lo", "precision_hi", "flooded_px", "dry_px"],
      ...d.groups.flatMap((g) => ["by_depth", "by_hand", "by_landcover"].flatMap((k) => g[k].map((c) => [g.group, k, c.label, c.recall, c.recall_ci?.[0], c.recall_ci?.[1], c.precision, c.precision_ci?.[0], c.precision_ci?.[1], c.n_wet, c.n_dry])))],
    draw(svg, W, H, tip) {
      const side = wide(W), pw = side ? W / 2 : W, ph = side ? H / 2 : 290;
      const at = (k) => (side ? [(k % 2) * pw, Math.floor(k / 2) * ph] : [0, k * ph]);
      const dotPanel = (k, letter, title, key, metric, xlabel) => {
        const [x, y] = at(k), p = fkPanel(svg, { x, y, w: pw - 10, h: ph - 8, letter, title });
        const labels = all[key].map((c) => c.label), sx = fkLinear(-0.5, labels.length - 0.5, 0, p.w), sy = fkLinear(0, 1.05, p.h, 0);
        fkAxes(p, sx, sy, { xlabel, ylabel: metric === "recall" ? "Recall" : "Recall, precision", xticks: labels.map((_, i) => i), xfmt: (i) => fkMinus(labels[i]), yticks: [0, 0.2, 0.4, 0.6, 0.8, 1], yfmt: (v) => v.toFixed(1) });
        const pts = [];
        [[all, -0.14, "f-veil", "s-veil"], [green, 0.14, "f-green", "s-green"]].forEach(([g, dx, f, s]) => {
          (metric === "both" ? ["recall", "precision"] : ["recall"]).forEach((m, mi) => {
            g[key].forEach((c) => {
              const i = labels.indexOf(c.label), v = c[m], ci = c[`${m}_ci`];
              if (i < 0 || v === null || (m === "precision" && c.n_wet + c.n_dry < 40)) return;
              const xx = sx(i + dx + (metric === "both" ? (mi ? 0.06 : -0.06) : 0));
              if (ci) fkErr(p.g, xx, sy(ci[0]), xx, sy(ci[1]), s, 2.5);
              fkMark(p.g, m === "recall" ? "o" : "s", xx, sy(v), f, 3.5);
              pts.push({ x: xx, y: sy(v), html: `<b>${c.label}</b> · ${g.group === "green" ? "green-light passes" : "all judged passes"}<br>${m} ${PCT(v)}${ci ? ` (95% ${PCT(ci[0])}–${PCT(ci[1])})` : ""}<br>${c.n_wet.toLocaleString("en-US")} flooded, ${c.n_dry.toLocaleString("en-US")} dry pixels` });
            });
          });
        });
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 16));
        return p;
      };
      const pa = dotPanel(0, "a", "Recall by water depth", "by_depth", "recall", "Water depth above forest floor");
      fkKey(pa, [["errbar", "f-green s-green", `Green-light passes (n = ${green.passes.length})`], ["errbar", "f-veil s-veil", `All judged passes (n = ${all.passes.length})`]], "bl");
      const pb = dotPanel(1, "b", "Recall and precision by height above the river", "by_hand", "both", "Ground height above the river");
      fkKey(pb, [["o", "f-ink", "Recall"], ["s", "f-ink", "Precision"]], "tr");
      dotPanel(2, "c", "Recall and precision by land cover", "by_landcover", "both", "Land cover (ESA WorldCover)");
      const [x, y] = at(3), p = fkPanel(svg, { x, y, w: pw - 10, h: ph - 8, letter: "d", title: `Trust light against outcome (n = ${ob.length})` });
      const sx = fkLinear(-0.6, 1.6, 0, p.w), sy = fkLinear(0, 1.05, p.h, 0);
      fkAxes(p, sx, sy, { xlabel: "Trust light, set before the test", ylabel: "CSI", xticks: [0, 1], xfmt: (v) => (v ? "Red" : "Green"), yticks: [0, 0.2, 0.4, 0.6, 0.8, 1], yfmt: (v) => v.toFixed(1) });
      // the rule fixed before the test: green is right when the score reaches 0.6, red when it doesn't
      refLine(p.g, 0, sy(0.6), p.w, sy(0.6));
      fkEl(p.g, "text", { x: p.w - 4, y: sy(0.6) - 5, class: "fk-tick fk-dim", "text-anchor": "end" }, "Rule: CSI = 0.6");
      const pts = [];
      const lane = (o) => { const g = ob.filter((q) => q.signal === o.signal).sort((a, b) => b.csi - a.csi); return (g.indexOf(o) - (g.length - 1) / 2) * 0.2; };
      ob.forEach((o) => {
        const i = o.signal === "green" ? 0 : 1, off = lane(o), xx = sx(i + off), yy = sy(o.csi), left = off < 0;
        fkMark(p.g, i ? "^" : "o", xx, yy, o.signal_right ? (i ? "f-red" : "f-green") : (i ? "f-none s-red" : "f-none s-green"), 4.5, { "stroke-width": 1.5 });
        fkEl(p.g, "text", { x: xx + (left ? -9 : 9), y: yy + 4, class: "fk-tick", "text-anchor": left ? "end" : "start" }, `${FIG_SHORT(o.site).replace(/ River$/, "")}, ${passDay(o.pair)}${o.signal_right ? "" : " (wrong)"}`);
        pts.push({ x: xx, y: yy, html: `<b>${siteTitle(o.site)}, ${passDay(o.pair)}</b><br>light ${o.signal}, CSI ${o.csi.toFixed(2)}<br>the light was ${o.signal_right ? "right" : "wrong"}` });
      });
      fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 16));
    },
  });
}

// ---------- Fig. 7: a flood through time ----------
async function figTime(box) {
  const [d, metrics] = await Promise.all([figJson("figures/time.json"), loadData().then((x) => x[1])]);
  const test = metrics.held_out.find((r) => r.site === d.river);
  const T = (s) => Date.parse(/Z$/.test(s) ? s : `${s}Z`), frames = d.frames;
  const t0 = T(frames[0].time) - 3 * 864e5, t1 = T(frames[frames.length - 1].time) + 3 * 864e5;
  fkFigure(box, {
    name: "fig7-flood-through-time", label: `River level, mapped area and match score for each NISAR pass on the ${siteTitle(d.river)}`,
    height: () => 600,
    csv: () => [["pass", "time", "nisar_mapped_ha", "rivers_answer_ha", "lidar_map_ha", "csi", "csi_lo", "csi_hi"], ...frames.map((f) => [f.pair, f.time, f.flagged_ha, f.confirmed_ha, f.static_ha, f.csi, f.csi_ci95?.[0], f.csi_ci95?.[1]])],
    draw(svg, W, H, tip) {
      // three panels on one shared time axis; dates are labelled on the bottom one only
      const spec = [["a", 190, 26, 8], ["b", 190, 26, 8], ["c", 220, 26, 50]];
      let y = 0;
      const out = spec.map(([letter, h, t, b]) => { const p = fkPanel(svg, { x: 0, y, w: W, h, letter, m: { t, r: 26, b, l: 62 } }); y += h; return p; });
      const sx = fkTime(t0, t1, 0, out[0].w), none = () => "";
      out.forEach((p) => frames.forEach((f) => fkEl(p.g, "line", { x1: sx(T(f.time)), x2: sx(T(f.time)), y1: 0, y2: p.h, class: "s-nisar", "stroke-opacity": 0.45, "stroke-dasharray": "1 3" })));
      // (a) gauges
      const series = d.gauges.map((g) => { const base = Math.min(...g.stage_m.filter((v) => v !== null)); return g.times.map((t, i) => [T(t), g.stage_m[i] === null ? NaN : g.stage_m[i] - base]).filter(([t]) => t >= t0 && t <= t1); });
      const ya = fkLinear(0, Math.max(...series.flat().map((p) => p[1]).filter(Number.isFinite)) * 1.08, out[0].h, 0);
      fkAxes(out[0], sx, ya, { xfmt: none, ylabel: "Stage rise (m)", ylabelX: -46 });
      const dashes = ["", "6 3", "1.5 2.5"];
      series.forEach((s, k) => fkEl(out[0].g, "path", { d: fkPath(s.map(([t, v]) => [sx(t), ya(v)])), class: "s-water", fill: "none", "stroke-width": 1.3, "stroke-dasharray": dashes[k % 3] }));
      fkKey(out[0], d.gauges.map((g, k) => ["line", "s-water", g.name.replace(/^Yellow River /, "").replace(/^./, (c) => c.toUpperCase()).replace(/, FL$/, ""), dashes[k % 3]]), "tl");
      // (b) areas
      const yb = fkLinear(0, Math.max(...frames.flatMap((f) => [f.flagged_ha, f.confirmed_ha, f.static_ha])) * 1.12, out[1].h, 0);
      fkAxes(out[1], sx, yb, { xfmt: none, ylabel: "Area (ha)", ylabelX: -50 });
      const ptsB = [];
      [["flagged_ha", "nisar", "NISAR flood map", null], ["confirmed_ha", "water", "River's answer", null], ["static_ha", "veil", "Lidar-only map", "5 3"]].forEach(([k, c, label, dash]) => {
        fkEl(out[1].g, "path", { d: fkPath(frames.map((f) => [sx(T(f.time)), yb(f[k])])), class: `s-${c}`, fill: "none", "stroke-width": 1.5, "stroke-dasharray": dash });
        frames.forEach((f) => { fkMark(out[1].g, "o", sx(T(f.time)), yb(f[k]), `f-${c}`, 3); ptsB.push({ x: sx(T(f.time)), y: yb(f[k]), html: `<b>${fkDay(T(f.time))}</b><br>${label}: ${ha(f[k])} ha` }); });
      });
      fkKey(out[1], [["line", "s-nisar", "NISAR flood map"], ["line", "s-water", "River's answer"], ["line", "s-veil", "Lidar-only map", "5 3"]], "cl");
      fkHover(out[1], tip, (px, py) => fkNearest(ptsB, px, py, 18));
      // (c) CSI
      const yc = fkLinear(0, 1.05, out[2].h, 0);
      fkAxes(out[2], sx, yc, { xfmt: fkDay, xlabel: "Date (2026, UTC)", ylabel: "CSI", yticks: [0, 0.2, 0.4, 0.6, 0.8, 1], yfmt: (v) => v.toFixed(1), ylabelX: -46 });
      const ptsC = [];
      frames.forEach((f) => {
        const x = sx(T(f.time));
        if (f.csi === null) { fkEl(out[2].g, "text", { x, y: out[2].h - 8, class: "fk-tick fk-dim", "text-anchor": "middle" }, "declined"); return; }
        if (f.csi_ci95) fkErr(out[2].g, x, yc(f.csi_ci95[0]), x, yc(f.csi_ci95[1]), "s-nisar");
        fkMark(out[2].g, "o", x, yc(f.csi), "f-nisar", 3.5);
        ptsC.push({ x, y: yc(f.csi), html: `<b>${fkDay(T(f.time))}</b><br>current method, CSI ${f.csi.toFixed(2)}${f.csi_ci95 ? ` (95% ${f.csi_ci95[0].toFixed(2)}–${f.csi_ci95[1].toFixed(2)})` : ""}<br>run after the fact, not a frozen test` });
        if (f.frozen && test) {
          const xt = x + 12, yt = yc(test.csi);
          fkErr(out[2].g, xt, yc(test.ci95[0]), xt, yc(test.ci95[1]), "s-ink");
          fkMark(out[2].g, "D", xt, yt, "f-bg s-ink", 3.5, { "stroke-width": 1.2 });
          ptsC.push({ x: xt, y: yt, html: `<b>${fkDay(T(f.time))}: the frozen test</b><br>${test.method.split(",")[0].replace("v", "Method ")}, CSI ${test.csi.toFixed(2)} (95% ${test.ci95[0].toFixed(2)}–${test.ci95[1].toFixed(2)})` });
        }
      });
      (d.unusable || []).forEach((u) => { const m = u.pair.match(/_([a-z]{3})(\d{2})$/), mo = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].indexOf(m[1]) + 1, t = Date.parse(`2026-${String(mo).padStart(2, "0")}-${m[2]}T12:00Z`); if (Number.isFinite(t)) fkEl(out[2].g, "text", { x: sx(t), y: out[2].h - 8, class: "fk-tick fk-dim", "text-anchor": "middle" }, "no valid radar"); });
      fkKey(out[2], [["errbar", "f-nisar s-nisar", "Current method (after the fact), 95% CI"], ["D", "f-bg s-ink", `Frozen test (${test ? test.method.split(",")[0].replace("v", "Method ") : "earlier method"})`]], "tl");
      fkHover(out[2], tip, (px, py) => fkNearest(ptsC, px, py, 18));
    },
  });
}

// ---------- Fig. 8: the official map's blind spot ----------
async function figBlind(box, only) {
  const [a, metrics, w, charts] = await Promise.all([figJson("figures/audit.json"), loadData().then((x) => x[1]), figJson("figures/world.json"), figJson("story/charts.json")]);
  const sat = metrics.satilla_audit;
  const rows = [...a.rows.map((r) => ({ site: r.site, date: r.date, est: r.estimated_ha, gfm: r.gfm_on_wet_ha })), { site: "satilla", date: sat.date, est: sat.estimated_ha, gfm: sat.gfm_on_wet_ha }]
    .filter((r) => r.est > 0).sort((x, y) => y.est - x.est);
  const day = (s) => fkDay(Date.parse(`${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}T12:00Z`));
  const ah = 30 + rows.length * 30 + 64;
  fkFigure(box, {
    name: "fig8-official-map-blind-spot", label: "Flooding estimated from the gauges against what the official flood map mapped, the official map's forest mask, and its revisits",
    height: (W) => (only === "a" ? ah : wide(W) && !only ? Math.max(ah, 380) + 16 + 320 : ah + 16 + 330 + 16 + 340),
    csv: () => [["river", "date", "estimated_ha", "gfm_mapped_ha"], ...rows.map((r) => [r.site, r.date, r.est, r.gfm])],
    draw(svg, W, H, tip) {
      const side = wide(W) && !only, top = side ? Math.max(ah, 380) : ah;
      {
        const p = fkPanel(svg, { x: 0, y: 0, w: side ? W * 0.55 : W, h: ah, letter: only ? null : "a", title: "Flooded area: estimate against GFM", m: { t: 30, r: wide(W) ? 20 : 60, b: 64, l: wide(W) ? 150 : 140 } });
        const sx = fkLog(0.1, 30000, 0, p.w), rh = p.h / rows.length;
        fkAxes(p, sx, fkLinear(0, 1, p.h, 0), { xlabel: "Area (ha, log scale)", yticks: [], xticks: p.w < 360 ? [0.1, 10, 1000] : undefined, xfmt: (v) => (v < 1 ? String(v) : fkFmt(v)) });
        const pts = [];
        rows.forEach((r, k) => {
          const y = (k + 0.5) * rh, xe = sx(r.est), xg = sx(Math.max(0.1, r.gfm ?? 0.1));
          fkEl(p.g, "line", { x1: -FK_TICK, x2: 0, y1: y, y2: y, class: "fk-spine" });
          fkEl(p.g, "text", { x: -FK_TICK - 3, y: y + 4, class: "fk-tick", "text-anchor": "end" }, `${wide(W) ? FIG_SHORT(r.site) : FIG_SHORT(r.site).replace(/ River$/, "")}, ${day(r.date)}`);
          fkEl(p.g, "line", { x1: xg, x2: xe, y1: y, y2: y, class: "s-veil", "stroke-width": 1 });
          fkMark(p.g, "o", xe, y, "f-water", 4);
          fkMark(p.g, "s", xg, y, r.gfm ? "f-official" : "f-bg s-official", 3.5, { "stroke-width": 1.2 });
          fkEl(p.g, "text", { x: xe + 8, y: y + 4, class: "fk-tick" }, n0f(r.est));
          if (r.gfm) fkEl(p.g, "text", { x: xg, y: y - 7, class: "fk-tick", "text-anchor": "middle" }, String(r.gfm));
          pts.push({ x: xe, y, html: `<b>${siteTitle(r.site)}, ${day(r.date)}</b><br>river's answer ${ha(r.est)} ha<br>official map ${r.gfm ?? 0} ha` });
        });
        fkLegend(svg, 6, ah - 6, [["o", "f-water", "Estimate (gauges and lidar)"], ["s", "f-official", "GFM, mapped"], ["s", "f-bg s-official", "GFM, nothing mapped"]]);
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 20));
      }
      if (only) return;
      {
        const x0 = side ? W * 0.55 + 18 : 0, y0 = side ? 0 : ah + 16, pw = W - x0, ph = side ? top : 330;
        const p = fkPanel(svg, { x: x0, y: y0, w: pw, h: ph, letter: "b", title: "Floodplain inside GFM's exclusion mask", m: { t: 30, r: Math.min(170, pw * 0.4), b: 42, l: 52 } });
        const sx = fkLinear(-0.12, 1.12, 0, p.w), sy = fkLinear(0, 1, p.h, 0);
        fkAxes(p, sx, sy, { xticks: [0, 1], xfmt: (v) => (v ? "Under trees" : "Elsewhere"), ylabel: "Share excluded", yfmt: PCT });
        const pts = [];
        // area names at the right end, pushed apart so they don't overlap
        const labels = w.check_areas.map((c) => ({ c, y: sy(c.gfm_excludes_share_under_trees) + 4 })).sort((x, y) => x.y - y.y);
        labels.forEach((l, k) => { if (k) l.y = Math.max(l.y, labels[k - 1].y + 13); });
        labels.forEach((l) => fkEl(p.g, "text", { x: p.w + 6, y: l.y, class: "fk-tick" }, l.c.area.split(",")[0].replace(" and ", " & ")));
        w.check_areas.forEach((c) => {
          fkEl(p.g, "line", { x1: sx(0), x2: sx(1), y1: sy(c.gfm_excludes_share_elsewhere), y2: sy(c.gfm_excludes_share_under_trees), class: "s-veil", "stroke-width": 1 });
          [0, 1].forEach((v) => fkMark(p.g, "o", sx(v), sy(v ? c.gfm_excludes_share_under_trees : c.gfm_excludes_share_elsewhere), "f-veil", 2.5));
          pts.push({ x: sx(1), y: sy(c.gfm_excludes_share_under_trees), html: `<b>${c.area}</b><br>left out under trees ${PCT(c.gfm_excludes_share_under_trees)}, elsewhere ${PCT(c.gfm_excludes_share_elsewhere)}` });
        });
        fkEl(p.g, "line", { x1: sx(0), x2: sx(1), y1: sy(w.check.excl_else), y2: sy(w.check.excl_trees), class: "s-official", "stroke-width": 2 });
        [[0, w.check.excl_else], [1, w.check.excl_trees]].forEach(([v, s]) => { fkMark(p.g, "o", sx(v), sy(s), "f-official", 4); fkEl(p.g, "text", { x: sx(v) + (v ? -9 : 9), y: sy(s) + (v ? 14 : -8), class: "fk-label", "text-anchor": v ? "end" : "start" }, PCT(s)); });
        fkKey(p, [["o", "f-official", `All ${w.check_areas.length} areas`], ["o", "f-veil", "Single area"]], "tl");
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 18));
      }
      {
        const wch = charts.watching, y0 = side ? top + 16 : ah + 16 + 330 + 16, ph = H - y0;
        const p = fkPanel(svg, { x: 0, y: y0, w: W, h: ph, letter: "c", title: "Satilla River, Sep–Oct 2026: stage and acquisitions", m: { t: 30, r: 16, b: 64, l: 56 } });
        const t0 = Date.parse(`${wch.start}T00:00Z`), t1 = Date.parse(`${wch.end}T23:59Z`), sx = fkTime(t0, t1, 0, p.w);
        const vals = wch.gauges.flatMap((g) => g.rows.map((r) => r[1])), sy = fkLinear(Math.floor(Math.min(...vals)), Math.max(1, Math.ceil(Math.max(...vals))), p.h, 0);
        fkAxes(p, sx, sy, { xfmt: fkDay, ylabel: "Stage − flood stage (m)", ylabelX: -40 });
        fkEl(p.g, "line", { x1: 0, x2: p.w, y1: sy(0), y2: sy(0), class: "s-ink", "stroke-width": 1, "stroke-dasharray": "4 3" });
        const dashes = ["", "6 3", "1.5 2.5"];
        wch.gauges.forEach((g, k) => fkEl(p.g, "path", { d: fkPath(g.rows.map((r) => [sx(Date.parse(r[0])), sy(r[1])])), class: "s-water", fill: "none", "stroke-width": 1.3, "stroke-dasharray": dashes[k % 3] }));
        fkKey(p, [...wch.gauges.map((g, k) => ["line", "s-water", g.name, dashes[k % 3]]), ["line", "s-ink", "Flood stage", "4 3"]], "tl");
        const pts = [];
        wch.nisar.forEach((t) => { const x = sx(Date.parse(t)); fkMark(p.g, "o", x, p.h + 32, "f-nisar", 3.5); pts.push({ x, y: p.h - 6, html: `NISAR pass, ${fkDay(Date.parse(t))}` }); });
        wch.gfm.forEach((g) => { const x = sx(Date.parse(`${g.date}T12:00Z`)); fkMark(p.g, "s", x, p.h + 48, g.covered > 0 ? "f-official" : "f-bg s-official", 3.5, { "stroke-width": 1.2 }); pts.push({ x, y: p.h - 6, html: `GFM scene, ${fkDay(Date.parse(`${g.date}T12:00Z`))}: ${g.covered > 0 ? `covers ${PCT(g.covered)} of this stretch` : "didn't reach this stretch"}` }); });
        fkEl(p.g, "text", { x: -FK_TICK - 3, y: p.h + 36, class: "fk-tick", "text-anchor": "end" }, "NISAR");
        fkEl(p.g, "text", { x: -FK_TICK - 3, y: p.h + 52, class: "fk-tick", "text-anchor": "end" }, "GFM");
        fkHover(p, tip, (px) => { const best = pts.reduce((b, q) => (Math.abs(q.x - px) < Math.abs(b.x - px) ? q : b), pts[0]); return Math.abs(best.x - px) < 14 ? best : null; });
      }
    },
  });
}

// ---------- Fig. 9: worldwide ----------
async function figWorld(box, only) {
  const d = await figJson("figures/world.json");
  const lats = d.lat.map((l, i) => ({ lat: l, f: d.floodplain_km2[i], t: d.tree_km2[i] })).filter((r) => r.lat >= -56 && r.lat <= 74);
  const latFmt = (v) => `${Math.abs(v)}°${v > 0 ? "N" : v < 0 ? "S" : ""}`;
  fkFigure(box, {
    name: "fig9-worldwide", label: "Forested and total river floodplain by latitude, and each country's floodplain against its share under trees",
    height: (W) => (only === "a" ? (wide(W) ? 420 : 520) : wide(W) && !only ? 540 : 520 + 16 + 420),
    csv: () => [["latitude_band_deg", "floodplain_km2", "floodplain_under_trees_km2"], ...lats.map((r) => [r.lat, r.f, r.t])],
    draw(svg, W, H, tip) {
      const side = wide(W) && !only;
      {
        const pw = side ? W * 0.46 : W, ph = only === "a" ? H : side ? H : 520;
        const p = fkPanel(svg, { x: 0, y: 0, w: pw, h: ph, letter: only ? null : "a", title: "River floodplain by latitude", m: { t: 30, r: 14, b: 42, l: 50 } });
        const gap = 4, mid = p.w / 2, maxv = Math.max(...lats.map((r) => r.f)), sx = fkLinear(0, maxv * 1.05, 0, mid - gap), sy = fkLinear(-56, 74, p.h, 0), bh = p.h / lats.length;
        fkAxes(p, fkLinear(0, 1, 0, p.w), sy, { xticks: [], yticks: [-40, -20, 0, 20, 40, 60], yfmt: latFmt, ylabel: "Latitude", ylabelX: -38 });
        fkEl(p.g, "rect", { x: 0, y: sy(23.44), width: p.w, height: sy(-23.44) - sy(23.44), class: "fk-zone" });
        fkEl(p.g, "text", { x: 5, y: sy(23.44) + 12, class: "fk-tick fk-dim" }, "Tropics");
        const pts = [];
        lats.forEach((r) => {
          const y = sy(r.lat + 1);
          fkEl(p.g, "rect", { x: mid - gap - sx(r.f), y, width: sx(r.f), height: bh + 0.3, class: "f-veil", "fill-opacity": 0.7 });
          fkEl(p.g, "rect", { x: mid + gap, y, width: sx(r.t), height: bh + 0.3, class: "f-forest", "fill-opacity": 0.85 });
          pts.push({ x: mid, y: y + bh / 2, html: `<b>${r.lat >= 0 ? `${r.lat}–${r.lat + 1}°N` : `${-r.lat - 1}–${-r.lat}°S`}</b><br>river floodplain ${figKm2(r.f)}<br>under trees ${figKm2(r.t)} (${r.f ? PCT(r.t / r.f) : "—"})` });
        });
        fkEl(p.g, "line", { x1: mid, x2: mid, y1: 0, y2: p.h, class: "fk-spine" });
        // a mirrored x axis: area grows outward from the centre line
        fkNice(0, maxv, 2).filter((v) => sx(v) <= mid - gap).forEach((v) => [-1, 1].forEach((s) => {
          const x = mid + s * (gap + sx(v));
          fkEl(p.g, "line", { x1: x, x2: x, y1: p.h, y2: p.h + FK_TICK, class: "fk-spine" });
          fkEl(p.g, "text", { x, y: p.h + FK_TICK + 12, class: "fk-tick", "text-anchor": "middle" }, fkFmt(v));
        }));
        fkEl(p.g, "text", { x: 6, y: p.h - 8, class: "fk-tick" }, "← All floodplain");
        fkEl(p.g, "text", { x: p.w - 6, y: p.h - 8, class: "fk-tick", "text-anchor": "end" }, "Under trees →");
        fkEl(p.g, "text", { x: p.w / 2, y: p.h + 32, class: "fk-label", "text-anchor": "middle" }, "Area per 1° band (km²)");
        fkHover(p, tip, (px, py) => { const lat = Math.floor(sy.invert(py)); return pts[lats.findIndex((x) => x.lat === lat)] || null; });
      }
      if (only === "a") return;
      {
        const x0 = side ? W * 0.46 + 18 : 0, y0 = side ? 0 : 536, pw = W - x0, ph = side ? H : 420;
        const p = fkPanel(svg, { x: x0, y: y0, w: pw, h: ph, letter: "b", title: `Countries with ≥ 1,000 km² of floodplain (n = ${d.countries.length})` });
        const sx = fkLog(1000, 3e6, 0, p.w), sy = fkLinear(0, 1, p.h, 0), rad = (n) => 1.5 + Math.sqrt(n) * 1.2;
        fkAxes(p, sx, sy, { xlabel: "Floodplain area (km²)", ylabel: "Fraction under tree cover", yfmt: (v) => v.toFixed(1) });
        const pts = [], top = [...d.countries].sort((a, b) => b.tree_km2 - a.tree_km2).slice(0, 8).map((c) => c.name).concat(d.countries.filter((c) => c.towns >= 80).map((c) => c.name));
        [...d.countries].sort((a, b) => b.towns - a.towns).forEach((c) => {
          const x = sx(c.floodplain_km2), y = sy(c.share), r = rad(c.towns);
          fkMark(p.g, "o", x, y, "f-forest s-forest", r, { "fill-opacity": 0.4, "stroke-width": 0.8 });
          if (top.includes(c.name)) fkEl(p.g, "text", x > p.w - 50 ? { x, y: y - r - 4, class: "fk-tick", "text-anchor": "middle" } : { x: x + r + 3, y: y + 4, class: "fk-tick" }, c.name.replace("United States of America", "USA").replace("Democratic Republic of the Congo", "DR Congo"));
          pts.push({ x, y, html: `<b>${c.name}</b><br>floodplain ${figKm2(c.floodplain_km2)}, ${PCT(c.share)} under trees<br>${c.towns} high-risk towns of 5,000+ people` });
        });
        // marker-size key, as a framed legend
        const kg = fkEl(p.g, "g", { class: "fk-legend" }), sizes = [10, 100, 300], kw = 210, kh = 2 * rad(300) + 30;
        kg.setAttribute("transform", `translate(${p.w - kw - 7},7)`);
        fkEl(kg, "rect", { width: kw, height: kh, class: "fk-legend-box", rx: 2 });
        fkEl(kg, "text", { x: 8, y: 15, class: "fk-tick" }, "High-risk towns per country");
        let kx = 18;
        sizes.forEach((n) => { const r = rad(n); fkMark(kg, "o", kx + r, 22 + rad(300), "f-forest s-forest", r, { "fill-opacity": 0.4, "stroke-width": 0.8 }); fkEl(kg, "text", { x: kx + 2 * r + 4, y: 26 + rad(300), class: "fk-tick" }, String(n)); kx += 2 * r + 30; });
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 14));
      }
    },
  });
}

// ---------- Fig. 10: checking the reference ----------
async function figReference(box) {
  const [d, rc] = await Promise.all([figJson("figures/reference.json"), figJson("figures/reference_checks.json")]);
  fkFigure(box, {
    name: "fig10-checking-the-reference", label: "Hidden-gauge check: predicted against measured water level, the error against the distance to the next gauge, and each score with the reference's water surface moved",
    height: (W) => (wide(W) ? 380 + 20 + 340 : 3 * 370 + 40),
    csv: () => [["river", "pass", "hidden_gauge", "neighbour_gap_km", "predicted_m", "measured_m", "error_m", "", "shift_river", "shift_pass", "shift_m", "csi"],
      ...Array.from({ length: Math.max(d.cases.length, rc.passes.length * rc.shifts_m.length) }, (_, i) => {
        const c = d.cases[i], q = rc.passes[Math.floor(i / rc.shifts_m.length)], sh = q && q.shift[i % rc.shifts_m.length];
        return [c?.river ?? "", c?.pair ?? "", c?.gauge ?? "", c?.neighbour_gap_km ?? "", c?.predicted_m ?? "", c?.measured_m ?? "", c?.error_m ?? "", "", q?.river ?? "", q?.pair ?? "", sh?.shift_m ?? "", sh?.csi ?? ""];
      })],
    draw(svg, W, H, tip) {
      const side = wide(W), pw = side ? W / 2 - 8 : W, ph = side ? 380 : 370;
      {
        const p = fkPanel(svg, { x: 0, y: 0, w: pw, h: ph, letter: "a", title: `Hidden-gauge prediction (n = ${d.cases.length})` });
        const vals = d.cases.flatMap((c) => [c.predicted_m, c.measured_m]), lo = Math.floor(Math.min(...vals)), hi = Math.ceil(Math.max(...vals));
        const sx = fkLinear(lo, hi, 0, p.w), sy = fkLinear(lo, hi, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Measured stage (m, NAVD88)", ylabel: "Predicted stage (m, NAVD88)" });
        refLine(p.g, sx(lo), sy(lo), sx(hi), sy(hi));
        const pts = d.cases.map((c) => { fkMark(p.g, "o", sx(c.measured_m), sy(c.predicted_m), "f-water", 3.5, { "fill-opacity": 0.75 }); return { x: sx(c.measured_m), y: sy(c.predicted_m), html: `<b>${c.gauge}</b>, ${siteTitle(c.river)}<br>predicted ${c.predicted_m.toFixed(2)} m · measured ${c.measured_m.toFixed(2)} m` }; });
        fkKey(p, [["o", "f-water", "Hidden gauge"], ["line", "s-ink", "1:1", "4 3"]], "tl");
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 14));
      }
      {
        const p = fkPanel(svg, { x: side ? W / 2 + 8 : 0, y: side ? 0 : 390, w: pw, h: ph, letter: "b", title: "Residual against gauge spacing" });
        const errs = d.cases.map((c) => c.error_m), m = Math.ceil(Math.max(...errs.map(Math.abs)));
        const sx = fkLinear(0, Math.ceil(Math.max(...d.cases.map((c) => c.neighbour_gap_km)) / 10) * 10, 0, p.w), sy = fkLinear(-m, m, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Distance to nearest gauge used (km)", ylabel: "Predicted − measured (m)" });
        refLine(p.g, 0, sy(0), p.w, sy(0));
        const pts = d.cases.map((c) => { fkMark(p.g, "o", sx(c.neighbour_gap_km), sy(c.error_m), "f-water", 3.5, { "fill-opacity": 0.75 }); return { x: sx(c.neighbour_gap_km), y: sy(c.error_m), html: `<b>${c.gauge}</b>, ${siteTitle(c.river)}<br>${c.neighbour_gap_km} km to the next gauge · error ${c.error_m >= 0 ? "+" : ""}${c.error_m.toFixed(2)} m` }; });
        fkEl(p.g, "text", { x: 8, y: 16, class: "fk-tick" }, `Median |error| = ${d.summary.median_abs_error_m.toFixed(2)} m`);
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 14));
      }
      {
        // Post hoc: the same frozen maps scored again with the reference's water surface moved up or down.
        const p = fkPanel(svg, { x: 0, y: side ? 400 : 780, w: W, h: side ? 340 : 370, letter: "c", title: "Each judged pass's CSI with the reference's water surface moved (post hoc)", m: { t: 30, r: side ? 170 : 18, b: 42, l: 56 } });
        const sx = fkLinear(rc.shifts_m[0], rc.shifts_m[rc.shifts_m.length - 1], 0, p.w), sy = fkLinear(0, 1, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Water surface moved (m)", ylabel: "CSI", xfmt: (v) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)}`, yfmt: (v) => v.toFixed(1) });
        refLine(p.g, sx(0), 0, sx(0), p.h);
        const pts = [], labels = [];
        rc.passes.forEach((q) => {
          const cls = q.trust === "green" ? "s-green" : "s-red";
          fkEl(p.g, "path", { d: fkPath(q.shift.map((x) => [sx(x.shift_m), sy(x.csi)])), class: cls, fill: "none", "stroke-width": 1.5 });
          q.shift.forEach((x) => pts.push({ x: sx(x.shift_m), y: sy(x.csi), html: `<b>${siteTitle(q.river)}, ${passDay(q.pair)}</b><br>surface ${x.shift_m > 0 ? "+" : ""}${x.shift_m} m · CSI ${x.csi.toFixed(2)}` }));
          labels.push({ y: sy(q.shift[q.shift.length - 1].csi) + 4, text: `${FIG_SHORT(q.river).replace(/ River$/, "")}, ${passDay(q.pair)}` });
        });
        // Line ends that sit close together get their names spaced apart.
        if (side) { labels.sort((a, b) => a.y - b.y); labels.forEach((l, k) => { if (k) l.y = Math.max(l.y, labels[k - 1].y + 12); fkEl(p.g, "text", { x: p.w + 6, y: l.y, class: "fk-tick" }, l.text); }); }
        fkKey(p, [["line", "s-green", "Trust light green"], ["line", "s-red", "Trust light red"]], "tl");
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 14));
      }
    },
  });
}

// Fig. 11: how often, and how soon, NISAR saw this season's reported floods (scripts/build_coverage.py, NASA's CMR catalog).
async function figCoverage(box, only) {
  const d = await figJson("figures/coverage.json"), S = d.summary, F = d.floods, N = F.length;
  const ecdf = (vals, xmax) => {   // share of all floods reached by day x, as a step line
    const v = vals.filter((x) => x !== null).map((x) => Math.max(0, x)).sort((a, b) => a - b), pts = [[0, 0]];
    v.forEach((x, k) => { if (x <= xmax) { pts.push([x, k / N], [x, (k + 1) / N]); } });
    pts.push([xmax, pts[pts.length - 1][1]]);
    return pts;
  };
  const lat = F.flatMap((f) => f.latency_days);
  fkFigure(box, {
    name: "fig11-nisar-coverage", label: "How often and how soon NISAR saw this season's reported floods",
    height: (W) => (only ? 330 : wide(W) ? 360 : 740),
    csv: () => [["gdacs_id", "country", "from", "to", "passes_during_flood", "method_kind_passes", "first_pass_days", "first_in_catalog_days", "in_catalog_during_flood"],
      ...F.map((f) => [f.id, f.country, f.from, f.to, f.passes, f.method_passes, f.first_pass_days, f.first_ready_days, f.ready_during_flood])],
    draw(svg, W, H, tip) {
      const side = wide(W) && !only, pw = side ? W / 2 - 8 : W, ph = side || only ? H : 360;
      {
        const xmax = Math.min(60, Math.ceil(Math.max(...F.map((f) => f.first_ready_days ?? 0), 10) / 10) * 10);
        const p = fkPanel(svg, { x: 0, y: 0, w: pw, h: ph, letter: only ? null : "a", title: `Reported floods NISAR saw (n = ${N})` });
        const sx = fkLinear(0, xmax, 0, p.w), sy = fkLinear(0, 1, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Days since the flood was first reported", ylabel: "Share of floods", yfmt: (v) => `${Math.round(v * 100)}%` });
        refLine(p.g, 0, sy(S.covered / N), p.w, sy(S.covered / N));
        fkEl(p.g, "path", { d: fkPath(ecdf(F.map((f) => f.first_pass_days), xmax).map(([x, y]) => [sx(x), sy(y)])), class: "s-nisar", fill: "none", "stroke-width": 1.8 });
        fkEl(p.g, "path", { d: fkPath(ecdf(F.map((f) => f.first_ready_days), xmax).map(([x, y]) => [sx(x), sy(y)])), class: "s-water", fill: "none", "stroke-width": 1.8, "stroke-dasharray": "5 3" });
        fkEl(p.g, "text", { x: p.w - 4, y: sy(S.covered / N) - 6, class: "fk-tick", "text-anchor": "end" }, `${Math.round((100 * S.covered) / N)}% had a NISAR pass during the flood`);
        fkKey(p, [["line", "s-nisar", "NISAR passed over"], ["line", "s-water", "That scene in NASA's catalog", "5 3"]], "br");
      }
      if (only) return;
      {
        const p = fkPanel(svg, { x: side ? W / 2 + 8 : 0, y: side ? 0 : 380, w: pw, h: ph, letter: "b", title: `Wait from recording to catalog (${lat.length} scenes)` });
        const top = Math.ceil(Math.max(...lat, 1)), bins = Array(top).fill(0);
        lat.forEach((x) => { bins[Math.min(top - 1, Math.floor(x))]++; });
        const sx = fkLinear(0, top, 0, p.w), sy = fkLinear(0, Math.max(...bins) * 1.1, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Days from recording to NASA's catalog", ylabel: "Scenes" });
        const pts = bins.map((c, k) => { fkEl(p.g, "rect", { x: sx(k) + 0.5, y: sy(c), width: Math.max(1, sx(k + 1) - sx(k) - 1), height: p.h - sy(c), class: "f-water", "fill-opacity": 0.7 }); return { x: sx(k + 0.5), y: sy(c), html: `${c} scene${c === 1 ? "" : "s"} took ${k}–${k + 1} days` }; });
        const m = S.latency_days.median;
        refLine(p.g, sx(m), 0, sx(m), p.h);
        fkEl(p.g, "text", { x: sx(m) + 5, y: 14, class: "fk-tick" }, `median ${m} days`);
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 18));
      }
    },
  });
}

// ---------- Fig. 12: water level under the canopy (exploratory, scripts/posthoc_swamp_fringes.py) ----------
// The pictures go into the SVG as data: URIs, so they stay in the SVG and PNG downloads.
const figDataUrl = (src) => (FIG_CACHE[src] ??= fetch(src).then((r) => r.blob()).then((b) => new Promise((ok, fail) => { const fr = new FileReader(); fr.onload = () => ok(fr.result); fr.onerror = fail; fr.readAsDataURL(b); })));
const FRINGE_LOOK = { control: ["s-ink", "2 3"], flood: ["s-nisar", null], crest: ["s-nisar", "6 3"] };

async function figFringes(box) {
  const d = await figJson("figures/fringes.json"), P = d.pairs, urls = await Promise.all(P.map((p) => figDataUrl(p.image)));
  const kmPerDeg = 111.32 * Math.cos((d.bunker[1] * Math.PI) / 180), km = (lon) => (lon - d.bunker[0]) * kmPerDeg;
  const [iw0, ih0] = P[0].image_px, aspect = ih0 / iw0, cmCycle = Math.round(100 * P[1].m_per_cycle);
  const layout = (W) => {
    const across = wide(W), gap = 12, iw = across ? (W - 2 * gap) / 3 : W, ih = iw * aspect, cell = 20 + ih;
    const aH = 30 + (across ? cell : 3 * cell + 2 * gap) + (across ? 34 : 50);
    return { across, gap, iw, ih, cell, aH, bH: 300 };
  };
  fkFigure(box, {
    name: "fig12-water-level-under-canopy", label: "NISAR interferograms over the Choctawhatchee delta swamp, and the water-level change along it",
    height: (W) => { const L = layout(W); return L.aH + 16 + L.bH; },
    csv: () => [["pair", "dates", "direction", "longitude", "km_east_of_bunker", "water_level_change_m", "coherent"],
      ...P.flatMap((p) => p.lon.map((lon, k) => [p.name, p.dates, p.direction, lon, km(lon).toFixed(2), p.dh_m[k], p.ok[k]]))],
    draw(svg, W, H, tip) {
      const L = layout(W);
      {
        const pa = fkPanel(svg, { x: 0, y: 0, w: W, h: L.aH, letter: "a", title: "Wrapped phase over the delta swamp (brightness: coherence)", m: { t: 30, r: 0, b: 0, l: 0 } });
        P.forEach((p, k) => {
          const x = L.across ? k * (L.iw + L.gap) : 0, y = L.across ? 0 : k * (L.cell + L.gap);
          fkEl(pa.g, "text", { x, y: y + 13, class: "fk-tick" }, `${p.dates}, ${p.track} (${p.direction}): ${p.role}`);
          fkEl(pa.g, "image", { x, y: y + 20, width: L.iw, height: L.ih, href: urls[k], preserveAspectRatio: "none" });
          const [bx0, by0, bx1, by1] = p.band_frac;
          fkEl(pa.g, "rect", { x: x + bx0 * L.iw, y: y + 20 + by0 * L.ih, width: (bx1 - bx0) * L.iw, height: (by1 - by0) * L.ih, fill: "none", stroke: "#ffffff", "stroke-opacity": 0.7, "stroke-width": 1, "stroke-dasharray": "4 3" });
          const gx = x + p.bunker_frac[0] * L.iw, gy = y + 20 + p.bunker_frac[1] * L.ih;
          fkEl(pa.g, "path", { d: `M${gx} ${gy - 6}L${gx + 5} ${gy + 4}L${gx - 5} ${gy + 4}Z`, fill: "#ffffff", stroke: "#000000", "stroke-width": 0.8 });
          if (k === 0) fkEl(pa.g, "text", { x: gx + 8, y: gy + 4, fill: "#ffffff", "font-size": 11, "font-family": "IBM Plex Sans, sans-serif", "paint-order": "stroke", stroke: "#000000", "stroke-width": 2.5 }, "Bunker gauge");
        });
        // the colour wheel: one full turn of colour is one cycle of phase
        const ky = L.aH - 30 - (L.across ? 14 : 30), wheel = fkEl(pa.g, "g", { transform: `translate(12,${ky})` });
        for (let s = 0; s < 36; s++) {
          const a0 = (s / 36) * 2 * Math.PI, a1 = ((s + 1) / 36) * 2 * Math.PI, r = 10;
          fkEl(wheel, "path", { d: `M0 0L${(r * Math.cos(a0)).toFixed(2)} ${(r * Math.sin(a0)).toFixed(2)}A${r} ${r} 0 0 1 ${(r * Math.cos(a1)).toFixed(2)} ${(r * Math.sin(a1)).toFixed(2)}Z`, fill: `hsl(${(s * 10 + 5).toFixed(0)}, 84%, 50%)` });
        }
        const keyText = [`One turn of the colour wheel ≈ ${cmCycle} cm of water-level change.`, "Dashed box: where panel b is measured."];
        if (L.across) fkEl(pa.g, "text", { x: 30, y: ky + 4, class: "fk-tick" }, keyText.join(" "));
        else keyText.forEach((t, k) => fkEl(pa.g, "text", { x: 30, y: ky + 4 + 16 * k, class: "fk-tick" }, t));
      }
      {
        const p = fkPanel(svg, { x: 0, y: L.aH + 16, w: W, h: L.bH, letter: "b", title: "Water-level change along the swamp, relative to the Bunker gauge", m: { t: 30, r: 18, b: 44, l: 56 } });
        const lons = P.flatMap((q) => q.lon), sx = fkLinear(km(Math.min(...lons)), km(Math.max(...lons)), 0, p.w);
        // on a phone the key needs the room above the lines
        const all = P.flatMap((q) => q.dh_m), sy = fkLinear(Math.min(-0.2, ...all) - 0.05, Math.max(...all) + (L.across ? 0.1 : 0.55), p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Distance east of the Bunker gauge (km)", ylabel: "Change (m)", yfmt: (v) => v.toFixed(1) });
        refLine(p.g, 0, sy(0), p.w, sy(0));
        refLine(p.g, sx(0), 0, sx(0), p.h);
        const pts = [];
        P.forEach((q) => {
          const [cls, dash] = FRINGE_LOOK[q.name];
          // coherent stretches only: across a gap the integration carries the last value, so it isn't drawn
          let run = [];
          const flush = () => { if (run.length > 1) fkEl(p.g, "path", { d: fkPath(run), class: cls, fill: "none", "stroke-width": 1.8, "stroke-dasharray": dash }); run = []; };
          q.lon.forEach((lon, k) => { if (q.ok[k]) { run.push([sx(km(lon)), sy(q.dh_m[k])]); pts.push({ x: sx(km(lon)), y: sy(q.dh_m[k]), html: `<b>${q.dates}</b> (${q.role})<br>${km(lon).toFixed(1)} km east of Bunker: ${fkMinus(q.dh_m[k] >= 0 ? `+${q.dh_m[k].toFixed(2)}` : q.dh_m[k].toFixed(2))} m` }); } else flush(); });
          flush();
        });
        fkKey(p, P.map((q) => ["line", FRINGE_LOOK[q.name][0], `${q.dates} (${q.role})`, FRINGE_LOOK[q.name][1]]), "tl");
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 22));
      }
    },
  });
}

// ---------- Fig. 4: maps of the results (scripts/posthoc_result_maps.py, drawn from the frozen runs' saved layers) ----------
const MAP_CLASSES = [["#6fa2ee", "Hit, both flooded"], ["#d63ad6", "False alarm, GLOWfm only"], ["#28c9e0", "Miss, the reference only"], ["rgba(120,132,140,0.47)", "Both dry"]];

async function figMaps(box) {
  const d = await figJson("figures/maps.json"), P = d.passes;
  const urls = await Promise.all(P.map((p) => Promise.all([p.overview.image, p.window.change, p.window.classes].map(figDataUrl))));
  const kindWord = { strong: "a strong pass", typical: "a typical pass", failed: "a failed pass" };
  const layout = (W) => {
    const across = wide(W), gap = 14;
    if (across) {
      const ow = Math.round(W * 0.27), ww = Math.floor((W - ow - 2 * gap) / 2), wh = Math.round((ww * P[0].window.px[1]) / P[0].window.px[0]);
      return { across, gap, ow, ww, wh, oh: wh, head: 0, row: 40 + 16 + wh + 26 };
    }
    const ww = W, wh = Math.round((W * P[0].window.px[1]) / P[0].window.px[0]), oh = 170;
    return { across, gap, ow: W, ww, wh, oh, head: 14, row: 14 + 40 + 3 * 16 + oh + 2 * wh + 2 * gap + 26 };
  };
  const label = (g, x, y, text) => fkEl(g, "text", { x, y, class: "fk-tick" }, text);
  const scaleBar = (g, x, y, pxPerKm) => {
    const km = 5, len = km * pxPerKm;
    fkEl(g, "rect", { x: x - 4, y: y - 14, width: len + 8, height: 20, fill: "#000", "fill-opacity": 0.45, rx: 2 });
    fkEl(g, "line", { x1: x, x2: x + len, y1: y, y2: y, stroke: "#fff", "stroke-width": 2 });
    [x, x + len].forEach((xx) => fkEl(g, "line", { x1: xx, x2: xx, y1: y - 4, y2: y + 1, stroke: "#fff", "stroke-width": 1.5 }));
    fkEl(g, "text", { x: x + len / 2, y: y - 4, "text-anchor": "middle", fill: "#fff", "font-size": 10, "font-family": "IBM Plex Sans, sans-serif" }, `${km} km`);
  };
  fkFigure(box, {
    name: "fig4-result-maps", label: "Maps of GLOWfm's frozen result against the reference for a strong, a typical and a failed pass: the whole reach, the radar change and each pixel as a hit, miss or false alarm",
    height: (W) => { const L = layout(W); return P.length * L.row + 64; },
    csv: () => [["river", "pass", "kind", "csi", "recall", "precision", "hit_ha", "false_alarm_ha", "miss_ha", "both_dry_ha", "trust_light"],
      ...P.map((p) => [p.river, p.pair, p.kind, p.csi, p.recall, p.precision, p.hit_ha, p.false_alarm_ha, p.miss_ha, p.dry_ha, p.trust ?? "none yet"])],
    draw(svg, W) {
      const L = layout(W);
      P.forEach((p, k) => {
        const g0 = fkEl(svg, "g", { transform: `translate(0,${k * L.row})` }), [ov, ch, cl] = urls[k];
        fkEl(g0, "text", { x: 0, y: 13, class: "fk-letter" }, "abc"[k]);
        fkEl(g0, "text", { x: 16, y: 13, class: "fk-ptitle" }, `${siteTitle(p.river)}, ${passDay(p.pair)}, ${kindWord[p.kind]}`);
        const lead = `CSI ${p.csi.toFixed(2)} · ${p.trust ? `trust light ${p.trust}` : "before the trust light"}`, counts = `hits ${p.hit_ha.toLocaleString("en-US")} ha · false alarms ${p.false_alarm_ha.toLocaleString("en-US")} ha · misses ${p.miss_ha.toLocaleString("en-US")} ha`;
        // on a phone the numbers take a second line
        if (L.across) label(g0, 16, 30, `${lead} · ${counts}`); else { label(g0, 16, 30, lead); label(g0, 16, 44, counts); }
        const g = fkEl(g0, "g", { transform: `translate(0,${L.head})` });
        // the whole scored reach, fitted into its box, with the window marked
        const [opw, oph] = p.overview.px, s = Math.min(L.ow / opw, L.oh / oph), iw = opw * s, ih = oph * s;
        const ox = L.across ? (L.ow - iw) / 2 : (W - iw) / 2, oy = 40 + 16 + (L.oh - ih) / 2;
        label(g, 0, 40 + 12, `Whole scored reach, ${p.overview.km[0]} × ${p.overview.km[1]} km`);
        fkEl(g, "rect", { x: L.across ? 0 : 0, y: 40 + 16, width: L.across ? L.ow : W, height: L.oh, class: "fk-spine", fill: "none" });
        fkEl(g, "image", { x: ox, y: oy, width: iw, height: ih, href: ov, preserveAspectRatio: "none", style: "image-rendering: pixelated" });
        const [fx, fy, fw, fh] = p.overview.window_frac;
        fkEl(g, "rect", { x: ox + fx * iw, y: oy + fy * ih, width: Math.max(3, fw * iw), height: Math.max(3, fh * ih), fill: "none", stroke: "#ffd166", "stroke-width": 1.5 });
        // the window: radar change, then the same pixels against the reference
        const wy = L.across ? 40 + 16 : 40 + 16 + L.oh + L.gap + 16;
        const cx = L.across ? L.ow + L.gap : 0, kx = L.across ? cx + L.ww + L.gap : 0, ky = L.across ? wy : wy + L.wh + L.gap + 16;
        const [kmW, kmH] = p.window.km;
        label(g, cx, wy - 4, `Radar change, smoothed HH (dB), the ${kmW} × ${kmH} km window`);
        label(g, kx, ky - 4, "The same window against the reference");
        fkEl(g, "rect", { x: cx, y: wy, width: L.ww, height: L.wh, class: "fk-spine", fill: "#000" });
        fkEl(g, "image", { x: cx, y: wy, width: L.ww, height: L.wh, href: ch, preserveAspectRatio: "none", style: "image-rendering: pixelated" });
        fkEl(g, "rect", { x: kx, y: ky, width: L.ww, height: L.wh, class: "fk-spine", fill: "none" });
        fkEl(g, "image", { x: kx, y: ky, width: L.ww, height: L.wh, href: cl, preserveAspectRatio: "none", style: "image-rendering: pixelated" });
        const pxPerKm = L.ww / kmW;
        scaleBar(g, cx + 12, wy + L.wh - 10, pxPerKm);
        scaleBar(g, kx + 12, ky + L.wh - 10, pxPerKm);
      });
      // the key: the four classes, and the change ramp
      const y0 = P.length * L.row + 6, g = fkEl(svg, "g", { transform: `translate(0,${y0})` });
      let x = 0, y = 0;
      MAP_CLASSES.forEach(([col, text]) => {
        const t = fkEl(g, "text", { x: x + 16, y: y + 10, class: "fk-tick" }, text), w = 16 + t.getComputedTextLength() + 18;
        if (x > 0 && x + w > W) { x = 0; y += 18; t.setAttribute("x", 16); t.setAttribute("y", y + 10); }
        fkEl(g, "rect", { x, y: y + 1, width: 11, height: 11, fill: col, rx: 2 });
        x += w;
      });
      const ry = y + 24, gradId = `ramp-${Math.random().toString(36).slice(2, 8)}`, defs = fkEl(svg, "defs");
      const grad = fkEl(defs, "linearGradient", { id: gradId });
      fkEl(grad, "stop", { offset: "0", "stop-color": "rgb(40,40,40)" }); fkEl(grad, "stop", { offset: "1", "stop-color": "rgb(255,255,255)" });
      fkEl(g, "rect", { x: 0, y: ry, width: 120, height: 10, fill: `url(#${gradId})`, stroke: "#8a969e", "stroke-width": 0.5 });
      const rampText = [`Radar change ${fkMinus(String(d.db_range[0]))} to +${d.db_range[1]} dB; brighter is a bigger rise.`, "The yellow box shows where the window sits."];
      if (wide(W)) fkEl(g, "text", { x: 128, y: ry + 9, class: "fk-tick" }, rampText.join(" "));
      else { fkEl(g, "text", { x: 128, y: ry + 9, class: "fk-tick" }, `${fkMinus(String(d.db_range[0]))} to +${d.db_range[1]} dB, brighter is a bigger rise`); fkEl(g, "text", { x: 0, y: ry + 28, class: "fk-tick" }, rampText[1]); }
    },
  });
}

const FIGS = { study: figStudy, signature: figSignature, separability: figSeparability, maps: figMaps, accuracy: figAccuracy, strata: figStrata, time: figTime, blind: figBlind, world: figWorld, reference: figReference, coverage: figCoverage, fringes: figFringes };

// Draw one mount, once (a later call is a no-op), and resolve when it's drawn.
function drawFigure(el) {
  el.figDrawn ??= FIGS[el.dataset.fig](el, el.dataset.only || null).catch((err) => { console.error("Figure failed", el.dataset.fig, err); el.textContent = "This figure couldn't load."; });
  return el.figDrawn;
}

// Draw every .fig-mount on the page when it comes near the screen.
// A figure inside a closed panel has no size yet, so it waits for the panel to open (story.js setupSeeData).
function mountFigures(root = document) {
  root.querySelectorAll(".fig-mount[data-fig]").forEach((el) => { if (!el.closest("details:not([open])")) whenNear(el, () => drawFigure(el)); });
}

// Draw every figure now, for printing or saving as PDF (figures far down the page haven't drawn yet).
const drawAllFigures = (root = document) => Promise.all([...root.querySelectorAll(".fig-mount[data-fig]")].map(drawFigure));
