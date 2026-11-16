
const LiveFigs = (() => {
  const S = { rec: null, d: null, res: null, s: null, out: null, figs: {}, timer: null };
  const LC = { 1: "Tree cover", 2: "Wetland", 0: "Other (incl. water)", 3: "Crop, grass, shrub" };
  const sdb = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(2)} dB`;
  const q = (sorted, p) => { if (!sorted.length) return NaN; const k = (sorted.length - 1) * p, lo = Math.floor(k); return sorted[lo] + (sorted[Math.min(sorted.length - 1, lo + 1)] - sorted[lo]) * (k - lo); };

  function compute() {
    const { rec, d, res, s } = S, W = rec.layout.width, H = rec.layout.height, n = W * H, C = LiveMethod.CONST, F = LiveMethod.FROZEN, px = rec.pixel_ha;
    const rule = { ...F, ...s }, lcSet = new Set(rule.landcover), land = (i) => !(d.water && d.water[i]);
    const eligible = (i, hmax) => res.change[i] === res.change[i] && lcSet.has(d.landcover[i]) && d.hand[i] < hmax && res.mapped[i];

    const step = 0.5, h0 = -1, h1 = 10, nb = Math.round((h1 - h0) / step), binVals = Array.from({ length: nb }, () => []), binFlag = new Array(nb).fill(0);
    for (let i = 0; i < n; i++) {
      const lc = d.landcover[i], hd = d.hand[i], v = res.change[i];
      if ((lc !== 1 && lc !== 2) || !(v === v) || !(d.dist[i] < rule.valley_m) || !(hd >= h0 && hd < h1)) continue;
      const k = Math.floor((hd - h0) / step);
      binVals[k].push(v);
      if (res.pred[i]) binFlag[k]++;
    }
    const sig = binVals.map((vals, k) => { const sv = Float64Array.from(vals).sort(); return { lo: h0 + k * step, hi: h0 + (k + 1) * step, n: sv.length, q25: q(sv, 0.25), q50: q(sv, 0.5), q75: q(sv, 0.75), flagged: sv.length ? binFlag[k] / sv.length : NaN }; });

    const base = rule.baseline === "single" ? d.one_hh : d.median_hh, dhh = new Float32Array(n);
    for (let i = 0; i < n; i++) dhh[i] = d.wet_hh[i] - base[i];
    const sm = LiveMethod._internal.smoothNan(dhh, W, H, rule.smooth_px), low = [], high = [];
    for (let i = 0; i < n; i++) {
      const v = sm[i];
      if (!(v === v) || d.landcover[i] !== C.LC_TREE || !(d.dist[i] < rule.valley_m)) continue;
      if (d.hand[i] < C.LOW_MAX_M) low.push(v); else if (d.hand[i] > C.HIGH_MIN_M && d.hand[i] < C.HIGH_MAX_M) high.push(v);
    }
    const trust = { low: Float64Array.from(low).sort(), high: Float64Array.from(high).sort(), min: C.MIN_CHECK_PX, rule: rule.confidence_db };
    trust.lowMed = trust.low.length >= C.MIN_CHECK_PX ? LiveMethod._internal.median(low) : null;
    trust.highMed = trust.high.length >= C.MIN_CHECK_PX ? LiveMethod._internal.median(high) : null;

    const byHeight = [2, 3, 4, 5, 6, 7, 8, 10].map((hm) => { const r = LiveMethod.run(d, W, H, { ...s, hand_max_m: hm }); return { hand_max_m: hm, ha: r.error ? null : r.flaggedLand * px, cut: r.error ? null : r.threshold }; });

    const sigOf = (hh, hv, i) => (res.usedRatio ? (hh[i] - d.median_hh[i]) - (hv[i] - d.median_hv[i]) : hh[i] - d.median_hh[i]);
    const dry = [], wet = [];
    for (let i = 0; i < n; i++) {
      if (!eligible(i, rule.hand_max_m) || !land(i)) continue;
      const a = sigOf(d.one_hh, d.one_hv, i), b = res.change[i];
      if (a === a && b === b) { dry.push(a); wet.push(b); }
    }
    const over = (arr) => (arr.length ? arr.filter((v) => v > res.threshold).length / arr.length : null);
    const noise = { dry: Float64Array.from(dry).sort(), wet: Float64Array.from(wet).sort(), dryOver: over(dry), wetOver: over(wet) };
    const above = (sorted, t) => { let lo = 0, hi = sorted.length; while (lo < hi) { const m = (lo + hi) >> 1; if (sorted[m] <= t) lo = m + 1; else hi = m; } return sorted.length ? (sorted.length - lo) / sorted.length : null; };
    const exceed = [];
    for (let t = 0; t <= 4.0001; t += 0.1) exceed.push({ cut: +t.toFixed(1), wet: above(noise.wet, t), dry: above(noise.dry, t) });

    let score = null, noRadar = null, agree = null;
    if (d.estimate) {
      const cuts = [];
      for (let t = 0; t <= 4.0001; t += 0.1) cuts.push(+t.toFixed(1));
      const tally = (on) => {
        let tp = 0, fn = 0, fp = 0;
        for (let i = 0; i < n; i++) {
          const e = d.estimate[i];
          if (!e || !res.mapped[i]) continue;
          const o = on(i);
          if (e === 1) o ? tp++ : fn++; else if (o) fp++;
        }
        return { csi: tp + fn + fp ? tp / (tp + fn + fp) : null, recall: tp + fn ? tp / (tp + fn) : null, precision: tp + fp ? tp / (tp + fp) : null };
      };
      score = cuts.map((t) => ({ cut: t, ...tally((i) => eligible(i, rule.hand_max_m) && res.change[i] > t) }));
      noRadar = tally((i) => eligible(i, rule.hand_max_m));
      agree = { hit: 0, miss: 0, fa: 0 };
      for (let i = 0; i < n; i++) {
        const e = d.estimate[i];
        if (!e || !res.mapped[i] || !land(i)) continue;
        const p = !!res.pred[i];
        if (e === 1 && p) agree.hit += px; else if (e === 1) agree.miss += px; else if (p) agree.fa += px;
      }
    }
    return { sig, trust, byHeight, noise: { dryOver: noise.dryOver, wetOver: noise.wetOver, n: noise.dry.length }, exceed, score, noRadar, agree, rule };
  }

  const panelH = (W) => (W < 640 ? 300 : 320);
  function panelWithKey(svg, W, H, title, items, corner = "tr") {
    const p = fkPanel(svg, { x: 0, y: 0, w: W, h: H, title });
    fkKey(p, items, corner);
    return p;
  }
  function captionNote(box, note) {
    const cap = box.closest("figure") && box.closest("figure").querySelector("figcaption");
    if (!cap) return;
    if (cap.dataset.base === undefined) cap.dataset.base = cap.innerHTML;
    cap.innerHTML = cap.dataset.base + (note ? ` ${note}` : "");
  }
  function figSignature(box) {
    return fkFigure(box, {
      name: "run-signature", label: "This run's radar signature: GLOWfm's signal against height above the nearest water",
      height: (W) => panelH(W) + 150,
      csv: () => [["height_from_m", "height_to_m", "pixels", "signal_q25_db", "signal_median_db", "signal_q75_db", "share_flagged"], ...S.out.sig.map((b) => [b.lo, b.hi, b.n, b.q25, b.q50, b.q75, b.flagged])],
      draw(svg, W, H, tip) {
        const o = S.out, ok = o.sig.filter((b) => b.n >= 30), x0 = -1, x1 = 10;
        const pa = fkPanel(svg, { x: 0, y: 0, w: W, h: panelH(W), letter: "a", title: `GLOWfm's signal by height above the nearest water (forest and wetland, ${o.sig.reduce((t, b) => t + b.n, 0).toLocaleString("en-US")} pixels)` });
        const vals = ok.flatMap((b) => [b.q25, b.q75, S.res.threshold]), lo = Math.floor(Math.min(...vals, -1)), hi = Math.ceil(Math.max(...vals, 2));
        const sx = fkLinear(x0, x1, 0, pa.w), sy = fkLinear(lo, hi, pa.h, 0);
        fkAxes(pa, sx, sy, { ylabel: "Signal (dB)", xticks: [] });
        fkShade(pa, sx(S.out.rule.hand_max_m), pa.w, "Not checked", "f-ink", { opacity: 0.07 });
        fkEl(pa.g, "path", { d: fkPath(ok.map((b) => [sx((b.lo + b.hi) / 2), sy(b.q75)])) + ok.slice().reverse().map((b) => `L${sx((b.lo + b.hi) / 2)} ${sy(b.q25)}`).join("") + "Z", class: "f-nisar", "fill-opacity": 0.18 });
        fkEl(pa.g, "path", { d: fkPath(ok.map((b) => [sx((b.lo + b.hi) / 2), sy(b.q50)])), class: "s-nisar", fill: "none", "stroke-width": 1.6 });
        fkEl(pa.g, "line", { x1: 0, x2: pa.w, y1: sy(S.res.threshold), y2: sy(S.res.threshold), class: "fk-ref" });
        fkEl(pa.g, "line", { x1: sx(S.out.rule.hand_max_m), x2: sx(S.out.rule.hand_max_m), y1: 0, y2: pa.h, class: "fk-ref" });
        fkEl(pa.g, "text", { x: 4, y: sy(S.res.threshold) - 5, class: "fk-tick" }, `cut-off ${sdb(S.res.threshold)}`);
        fkKey(pa, [["line", "s-nisar", "Median"], ["patch", "f-nisar", "Middle half"]], "br");
        const pts = ok.map((b) => ({ x: sx((b.lo + b.hi) / 2), y: sy(b.q50), html: `${b.lo}–${b.hi} m above water · ${b.n.toLocaleString("en-US")} px<br>median ${sdb(b.q50)} · ${Math.round(100 * b.flagged)}% flagged` }));
        fkHover(pa, tip, (px, py) => fkNearest(pts, px, py, 20));
        const pb = fkPanel(svg, { x: 0, y: panelH(W) + 6, w: W, h: 144, letter: "b", title: "Share of those pixels GLOWfm flagged", m: { t: 26, r: 18, b: 42, l: 56 } });
        const sy2 = fkLinear(0, 1, pb.h, 0);
        fkAxes(pb, sx, sy2, { xlabel: "Height above the nearest mapped water (m)", ylabel: "Flagged", yfmt: (v) => `${Math.round(v * 100)}%`, yticks: [0, 0.5, 1] });
        fkShade(pb, sx(S.out.rule.hand_max_m), pb.w, "", "f-ink", { opacity: 0.07 });
        ok.forEach((b) => fkEl(pb.g, "rect", { x: sx(b.lo) + 0.5, y: sy2(b.flagged), width: Math.max(1, sx(b.hi) - sx(b.lo) - 1), height: pb.h - sy2(b.flagged), class: "f-nisar", "fill-opacity": b.n < 100 ? 0.25 : 0.65 }));
        if (ok.some((b) => b.n < 100)) fkEl(pb.g, "text", { x: pb.w - 4, y: 12, class: "fk-tick", "text-anchor": "end" }, "paler: under 100 pixels");
        const ptsB = ok.map((b) => ({ x: sx((b.lo + b.hi) / 2), y: sy2(b.flagged), html: `${b.lo}–${b.hi} m above water<br>${Math.round(100 * b.flagged)}% of ${b.n.toLocaleString("en-US")} pixels flagged` }));
        fkHover(pb, tip, (px, py) => fkNearest(ptsB, px, py, 24));
      },
    });
  }

  function figTrust(box) {
    return fkFigure(box, {
      name: "run-trust-light", label: "Why the trust light is green or red: low forest against higher forest",
      height: (W) => panelH(W),
      csv: () => [["group", "pixels", "median_db"], ["forest under 2 m above water", S.out.trust.low.length, S.out.trust.lowMed], ["forest 4–8 m above water", S.out.trust.high.length, S.out.trust.highMed], ["gap (low minus high)", "", S.res.lowMinusHigh], ["rule: green if gap above", "", S.out.trust.rule]],
      draw(svg, W, H) {
        const t = S.out.trust, p = fkPanel(svg, { x: 0, y: 0, w: W, h: H, title: `Low forest against higher forest (${t.low.length.toLocaleString("en-US")} and ${t.high.length.toLocaleString("en-US")} pixels)` });
        const x0 = -4, x1 = 6, bw = 0.25, nb = Math.round((x1 - x0) / bw);
        const hist = (arr) => { const c = new Array(nb).fill(0); arr.forEach((v) => { const k = Math.floor((Math.min(x1 - 1e-6, Math.max(x0, v)) - x0) / bw); c[k]++; }); return c.map((x) => x / Math.max(1, arr.length) / bw); };
        const hl = hist(t.low), hh = hist(t.high), ymax = Math.max(...hl, ...hh, 0.1) * 1.1;
        const sx = fkLinear(x0, x1, 0, p.w), sy = fkLinear(0, ymax, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Smoothed HH change since before the flood (dB)", ylabel: "Density" });
        const step = (c) => fkPath(c.flatMap((v, k) => [[sx(x0 + k * bw), sy(v)], [sx(x0 + (k + 1) * bw), sy(v)]]));
        fkEl(p.g, "path", { d: step(hh), class: "s-veil", fill: "none", "stroke-width": 1.4 });
        fkEl(p.g, "path", { d: step(hl), class: "s-water", fill: "none", "stroke-width": 1.6 });
        if (t.lowMed !== null) fkEl(p.g, "line", { x1: sx(t.lowMed), x2: sx(t.lowMed), y1: 0, y2: p.h, class: "s-water", "stroke-dasharray": "4 3" });
        if (t.highMed !== null) fkEl(p.g, "line", { x1: sx(t.highMed), x2: sx(t.highMed), y1: 0, y2: p.h, class: "s-veil", "stroke-dasharray": "4 3" });
        const gap = S.res.lowMinusHigh, verdict = gap === null ? `too few forest pixels to compare (needs ${t.min} in each)` : `gap ${sdb(gap)}: ${gap > t.rule ? "above" : "not above"} the ${t.rule} dB rule, so ${gap > t.rule ? "green" : "red"}`;
        fkEl(p.g, "text", { x: 6, y: 16, class: "fk-tick" }, verdict);
        fkKey(p, [["line", "s-water", "Forest under 2 m above water"], ["line", "s-veil", "Forest 4–8 m above water"]], "br");
      },
    });
  }

  function figRobust(box) {
    return fkFigure(box, {
      name: "run-height-limit", label: "How much the flagged area depends on the height limit: the method rerun at each limit",
      height: (W) => panelH(W),
      csv: () => [["height_limit_m", "flagged_land_ha", "cut_off_db"], ...S.out.byHeight.map((r) => [r.hand_max_m, r.ha, r.cut])],
      draw(svg, W, H, tip) {
        const o = S.out, rows = o.byHeight.filter((r) => r.ha !== null), ymax = Math.max(...rows.map((r) => r.ha), 1) * 1.1;
        const p = fkPanel(svg, { x: 0, y: 0, w: W, h: H, title: "If the height limit were… (method rerun)" });
        const sx = fkLinear(2, 10, 0, p.w), sy = fkLinear(0, ymax, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Height limit above the nearest water (m)", ylabel: "Flagged land (ha)" });
        fkEl(p.g, "path", { d: fkPath(rows.map((r) => [sx(r.hand_max_m), sy(r.ha)])), class: "s-nisar", fill: "none", "stroke-width": 1.4 });
        rows.forEach((r) => fkMark(p.g, r.hand_max_m === o.rule.hand_max_m ? "o" : "s", sx(r.hand_max_m), sy(r.ha), r.hand_max_m === o.rule.hand_max_m ? "f-nisar" : "f-veil", r.hand_max_m === o.rule.hand_max_m ? 4.5 : 3));
        fkEl(p.g, "line", { x1: sx(LiveMethod.FROZEN.hand_max_m), x2: sx(LiveMethod.FROZEN.hand_max_m), y1: 0, y2: p.h, class: "fk-ref" });
        fkEl(p.g, "text", { x: sx(LiveMethod.FROZEN.hand_max_m) + 4, y: 14, class: "fk-tick" }, "frozen: 6 m");
        const at = rows.find((r) => r.hand_max_m === o.rule.hand_max_m), lo = rows.find((r) => r.hand_max_m === 4), hi = rows.find((r) => r.hand_max_m === 8);
        captionNote(box, at && lo && hi && at.ha > 0 ? `Here, from 4 m to 8 m the area changes by ${Math.round((100 * (hi.ha - lo.ha)) / at.ha)}% of this run's.` : "");
        const pts = rows.map((r) => ({ x: sx(r.hand_max_m), y: sy(r.ha), html: `limit ${r.hand_max_m} m: ${Math.round(r.ha).toLocaleString("en-US")} ha (cut-off ${sdb(r.cut)})` }));
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 16));
      },
    });
  }

  function figNoise(box) {
    return fkFigure(box, {
      name: "run-noise-floor", label: "Share of pixels above each cut-off: the flood pass against the last pass before the flood",
      height: (W) => panelH(W),
      csv: () => [["cut_off_db", "share_above_flood_pass", "share_above_last_pass_before"], ...S.out.exceed.map((r) => [r.cut, r.wet, r.dry])],
      draw(svg, W, H, tip) {
        const o = S.out, before = fkDay(S.rec.baseline[S.rec.baseline.length - 1].time), pc = (x) => (x === null ? "—" : `${(100 * x).toFixed(x < 0.1 ? 1 : 0)}%`);
        const p = panelWithKey(svg, W, H, `Pixels above each cut-off (${o.noise.n.toLocaleString("en-US")} pixels GLOWfm could flag)`, [
          ["line", "s-nisar", `Flood pass, ${fkDay(S.rec.wet.time)}: ${pc(o.noise.wetOver)} above the cut-off`],
          ["line", "s-veil", `Before the flood, ${before}: ${pc(o.noise.dryOver)}`],
          ["line", "fk-ref", `This run's cut-off, ${sdb(S.res.threshold)}`],
        ]);
        const sx = fkLinear(0, 4, 0, p.w), sy = fkLinear(0, 1, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: `Cut-off (${S.res.usedRatio ? "HH minus HV, " : ""}dB)`, ylabel: "Share above", yfmt: (v) => `${Math.round(v * 100)}%` });
        fkShade(p, 0, sx(LiveMethod.FROZEN.min_threshold_db), "Below the 0.5 dB floor", "f-ink", { opacity: 0.07 });
        fkEl(p.g, "path", { d: fkPath(o.exceed.map((r) => [sx(r.cut), sy(r.dry)])), class: "s-veil", fill: "none", "stroke-width": 1.4 });
        fkEl(p.g, "path", { d: fkPath(o.exceed.map((r) => [sx(r.cut), sy(r.wet)])), class: "s-nisar", fill: "none", "stroke-width": 1.8 });
        fkEl(p.g, "line", { x1: sx(S.res.threshold), x2: sx(S.res.threshold), y1: 0, y2: p.h, class: "fk-ref" });
        const pts = o.exceed.map((r) => ({ x: sx(r.cut), y: sy(r.wet), html: `cut-off ${sdb(r.cut)}: ${pc(r.wet)} on the flood pass, ${pc(r.dry)} on ${before}` }));
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 18));
      },
    });
  }

  function figScore(box) {
    return fkFigure(box, {
      name: "run-score-by-cut-off", label: "Score against the gauge-and-lidar estimate as the cut-off varies, with no radar for comparison",
      height: (W) => panelH(W),
      csv: () => [["cut_off_db", "csi", "recall", "precision"], ...S.out.score.map((r) => [r.cut, r.csi, r.recall, r.precision]), ["no radar (every eligible pixel)", S.out.noRadar.csi, S.out.noRadar.recall, S.out.noRadar.precision]],
      draw(svg, W, H, tip) {
        const o = S.out;
        const f = S.rec.score && S.rec.score.scores, ci = S.rec.score && S.rec.score.ci95 && S.rec.score.ci95.csi, ft = S.rec.reference_run && S.rec.reference_run.threshold_db;
        const published = f && f.csi !== null && f.csi !== undefined && ft !== undefined, noRadar = o.noRadar && o.noRadar.csi !== null;
        const p = panelWithKey(svg, W, H, "Against the river's gauges and lidar, if the cut-off were…", [
          ["line", "s-nisar", "Match (CSI)"], ["line", "s-veil", "Recall"], ["line", "s-ink", "Precision", "2 3"],
          ...(noRadar ? [["line", "s-water", `No radar ${o.noRadar.csi.toFixed(2)}`, "5 4"]] : []),
          ...(published ? [["errbar", "f-nisar s-nisar", `Published test ${f.csi.toFixed(2)}${ci ? `, 95% ${ci[0].toFixed(2)}–${ci[1].toFixed(2)}` : ""}`]] : []),
          ["line", "fk-ref", `This run's cut-off, ${sdb(S.res.threshold)}`],
        ]);
        const sx = fkLinear(0, 4, 0, p.w), sy = fkLinear(0, 1, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Cut-off (dB)", ylabel: "Score (1 is perfect)" });
        fkShade(p, 0, sx(LiveMethod.FROZEN.min_threshold_db), "Below the 0.5 dB floor", "f-ink", { opacity: 0.07 });
        if (noRadar) fkEl(p.g, "line", { x1: 0, x2: p.w, y1: sy(o.noRadar.csi), y2: sy(o.noRadar.csi), class: "s-water", "stroke-dasharray": "5 4", "stroke-width": 1.2 });
        [["csi", "s-nisar", 1.8], ["recall", "s-veil", 1.2], ["precision", "s-ink", 1.2]].forEach(([k, cls, sw]) => fkEl(p.g, "path", { d: fkPath(o.score.map((r) => [sx(r.cut), r[k] === null ? NaN : sy(r[k])])), class: cls, fill: "none", "stroke-width": sw, ...(k === "precision" ? { "stroke-dasharray": "2 3", "stroke-opacity": 0.7 } : {}) }));
        if (published) {
          if (ci) fkErr(p.g, sx(ft), sy(ci[0]), sx(ft), sy(ci[1]), "s-nisar");
          fkMark(p.g, "o", sx(ft), sy(f.csi), "f-nisar s-nisar", 4.5);
        }
        fkEl(p.g, "line", { x1: sx(S.res.threshold), x2: sx(S.res.threshold), y1: 0, y2: p.h, class: "fk-ref" });
        const pts = o.score.filter((r) => r.csi !== null).map((r) => ({ x: sx(r.cut), y: sy(r.csi), html: `cut-off ${sdb(r.cut)}: match ${r.csi.toFixed(2)} · recall ${r.recall === null ? "—" : r.recall.toFixed(2)} · precision ${r.precision === null ? "—" : r.precision.toFixed(2)}` }));
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 16));
      },
    });
  }

  const AGREE_RGB = { hit: [91, 140, 255], miss: [0, 200, 220], fa: [229, 122, 229] };
  function agreeImage() {
    const { rec, d, res } = S, W = rec.layout.width, H = rec.layout.height;
    let x0 = W, y0 = H, x1 = -1, y1 = -1;
    for (let i = 0; i < W * H; i++) if (d.estimate[i] && res.mapped[i]) { const x = i % W, y = (i / W) | 0; if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
    if (x1 < 0) return null;
    const pad = 4; x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad); x1 = Math.min(W - 1, x1 + pad); y1 = Math.min(H - 1, y1 + pad);
    const cw = x1 - x0 + 1, ch = y1 - y0 + 1, c = document.createElement("canvas");
    c.width = cw; c.height = ch;
    const g = c.getContext("2d"), img = g.createImageData(cw, ch), px = img.data;
    for (let y = y0; y <= y1; y++) for (let x = x0; x <= x1; x++) {
      const i = y * W + x, e = d.estimate[i];
      if (!e || !res.mapped[i] || (d.water && d.water[i])) continue;
      const p = !!res.pred[i], k = e === 1 && p ? "hit" : e === 1 ? "miss" : p ? "fa" : null, o = 4 * ((y - y0) * cw + (x - x0));
      if (k) { const [r, gg, b] = AGREE_RGB[k]; px[o] = r; px[o + 1] = gg; px[o + 2] = b; px[o + 3] = 255; }
      else { px[o] = 205; px[o + 1] = 225; px[o + 2] = 235; px[o + 3] = 26; }
    }
    g.putImageData(img, 0, 0);
    return { url: c.toDataURL("image/png"), w: cw, h: ch, km: (cw * Math.sqrt(rec.pixel_ha * 1e4)) / 1000 };
  }
  function figAgree(box) {
    const im = agreeImage(), size = (W) => { const iw = Math.min(W, 560), ih = im ? Math.min(460, Math.round(iw * (im.h / im.w))) : 0; return [im ? Math.round(ih * (im.w / im.h)) : iw, ih]; };
    return fkFigure(box, {
      name: "run-agreement-map", label: "Hits, misses and false alarms against the gauge-and-lidar estimate",
      height: (W) => size(W)[1] + (W < 640 ? 76 : 44),
      csv: () => [["class", "hectares"], ["both flooded (hit)", S.out.agree.hit], ["estimate only (missed)", S.out.agree.miss], ["NISAR only (false alarm)", S.out.agree.fa]],
      draw(svg, W) {
        const a = S.out.agree, [iw, ih] = size(W);
        if (im) {
          fkEl(svg, "image", { href: im.url, x: 0, y: 0, width: iw, height: ih, preserveAspectRatio: "none", style: "image-rendering: pixelated" });
          fkEl(svg, "text", { x: iw, y: ih + 14, class: "fk-tick", "text-anchor": "end" }, `about ${im.km.toFixed(1)} km across`);
        }
        const items = [["hit", `Both flooded ${Math.round(a.hit).toLocaleString("en-US")} ha`], ["miss", `Estimate only (missed) ${Math.round(a.miss).toLocaleString("en-US")} ha`], ["fa", `NISAR only (false alarm) ${Math.round(a.fa).toLocaleString("en-US")} ha`]];
        let x = 0;
        items.forEach(([k, t], j) => {
          const narrow = W < 640, y = ih + 32 + (narrow ? j * 18 : 0);
          if (narrow) x = 0;
          fkEl(svg, "rect", { x, y: y - 9, width: 10, height: 10, fill: `rgb(${AGREE_RGB[k].join(",")})` });
          fkEl(svg, "text", { x: x + 15, y, class: "fk-tick" }, t);
          x += 15 + t.length * 6.2 + 18;
        });
      },
    });
  }

  const MAKERS = { signature: figSignature, noise: figNoise, trust: figTrust, score: figScore, agree: figAgree, robust: figRobust };

  function drawFig(k) {
    const box = $(`af-${k}`).querySelector(".af-mount");
    if (S.figs[k] && S.figs[k].box === box) S.figs[k].fig.render();
    else S.figs[k] = { box, fig: MAKERS[k](box) };
  }

  function update(rec, d, res, s) {
    Object.assign(S, { rec, d, res, s });
    clearTimeout(S.timer);
    S.timer = setTimeout(() => {
      if (S.res !== res || res.error) return;
      S.out = compute();
      $("analysis").hidden = false;
      $("analysis-sub").innerHTML = `${escHtml(rec.place)} · NISAR pass ${fmtTime(rec.wet.time)}` + (rec.kind === "us" && d.estimate ? "" : ' · <span class="live-warn">not checked against ground truth</span>');
      const order = ["signature", "noise", "trust", ...(d.estimate ? ["score", "agree"] : []), "robust"];
      order.forEach((k) => $("figs-main").appendChild($(`af-${k}`)));
      ["score", "agree"].forEach((k) => { $(`af-${k}`).hidden = !d.estimate; });
      S.figs.agree = null;
      order.forEach(drawFig);
    }, 250);
  }

  function record() {
    const { rec, res, s, out } = S;
    return { site: "GLOWfm", method: "v4 (frozen), run in the browser", made_utc: new Date().toISOString(), case: { id: rec.id, place: rec.place, kind: rec.kind, custom: !!rec.custom, corners: rec.corners, box: rec.box || null },
      pass: rec.wet, baseline: rec.baseline, inputs: { heights: rec.inputs.heights, river: rec.inputs.river, epsg: rec.inputs.epsg }, settings: { ...LiveMethod.FROZEN, ...s },
      result: { threshold_db: res.threshold, otsu_db: res.otsuDb, used_hh_minus_hv: res.usedRatio, flagged_land_ha: res.flaggedLand * rec.pixel_ha, trust: { low_minus_high_db: res.lowMinusHigh, green: res.confident } },
      published_score: rec.score ? rec.score.scores : null, figures: out };
  }

  function brief({ map, light, frozen, yourCsi, next }) {
    const { rec, res } = S, W = 1240, H = 2600, M = 72, ink = "#10161c", soft = "#3d4a55", muted = "#6b7883", rule = "#d5dbe0", nisar = "#b4239f";
    const c = document.createElement("canvas"); c.width = W; c.height = H;
    const g = c.getContext("2d"), sans = (px, wt = 400) => `${wt} ${px}px 'IBM Plex Sans', system-ui, sans-serif`, disp = (px) => `600 ${px}px 'Space Grotesk', 'IBM Plex Sans', sans-serif`;
    g.fillStyle = "#fff"; g.fillRect(0, 0, W, H);
    const wrap = (text, x, y, maxW, lh, { font = sans(20), color = soft, breakAll = false } = {}) => {
      g.font = font; g.fillStyle = color;
      const words = breakAll ? [...text] : text.split(" "), sep = breakAll ? "" : " ";
      let line = "";
      for (const w of words) {
        const test = line ? line + sep + w : w;
        if (g.measureText(test).width > maxW && line) { g.fillText(line, x, y); y += lh; line = w; } else line = test;
      }
      if (line) { g.fillText(line, x, y); y += lh; }
      return y;
    };
    const hr = (y) => { g.fillStyle = rule; g.fillRect(M, y, W - 2 * M, 1); return y; };
    const area = res.flaggedLand * rec.pixel_ha, made = new Date();
    let y = 96;
    g.font = sans(18, 600); g.fillStyle = muted; g.fillText("GLOWfm · FLOOD BRIEF", M, y);
    g.textAlign = "right"; g.font = sans(18); g.fillText(`Made ${fmtTime(made.toISOString())}`, W - M, y); g.textAlign = "left";
    y = wrap(rec.place, M, y + 62, W - 2 * M, 54, { font: disp(46), color: ink });
    y = wrap(`NISAR pass ${fmtTime(rec.wet.time)}, compared with ${rec.baseline.length} earlier pass${rec.baseline.length === 1 ? "" : "es"} on the same track`, M, y + 4, W - 2 * M, 30, { font: sans(21) });
    hr(y + 14); y += 92;
    g.font = disp(84); g.fillStyle = nisar; g.fillText(`${ha(area)} ha`, M, y);
    y = wrap("flagged as flooded by GLOWfm, outside permanent lakes and rivers", M, y + 40, W - 2 * M, 30, { font: sans(22), color: soft });
    const dot = { green: "#2f9e4f", red: "#d64545", amber: "#d49b12", grey: "#8a969e" }[light.cls] || "#8a969e";
    g.fillStyle = dot; g.beginPath(); g.arc(M + 9, y + 12, 9, 0, 2 * Math.PI); g.fill();
    g.font = sans(23, 600); g.fillStyle = ink; g.fillText(light.label, M + 28, y + 20);
    y = wrap(light.why, M + 28, y + 52, W - 2 * M - 28, 28, { font: sans(19) });
    if (rec.kind === "us" && rec.score && rec.score.scores) {
      y = wrap(`Checked against the river's own gauges and lidar, it matched at ${rec.score.scores.csi.toFixed(2)} (1 is perfect, 95% range ${rec.score.ci95.csi[0].toFixed(2)}–${rec.score.ci95.csi[1].toFixed(2)}), in the frozen test run before anyone saw the result.`, M, y + 10, W - 2 * M, 28, { font: sans(19), color: ink });
    } else y = wrap("Not checked against ground truth. There are no river gauges here, so the trust light decides.", M, y + 10, W - 2 * M, 28, { font: sans(19), color: ink });
    if (!frozen) y = wrap(`Settings changed from the frozen method${yourCsi !== null && yourCsi !== undefined ? ` (match ${yourCsi.toFixed(2)} with these settings)` : ""}. This is not the tested run.`, M, y + 6, W - 2 * M, 28, { font: sans(19, 600), color: "#a35a00" });
    y += 18;
    if (map) {
      const maxH = 600, s = Math.min((W - 2 * M) / map.width, maxH / map.height), mw = map.width * s, mh = map.height * s;
      g.drawImage(map, M, y, mw, mh); g.strokeStyle = rule; g.lineWidth = 1; g.strokeRect(M + 0.5, y + 0.5, mw - 1, mh - 1);
      y += mh + 30;
      g.fillStyle = "#d63ad6"; g.fillRect(M, y - 13, 14, 14);
      g.font = sans(17); g.fillStyle = soft; g.fillText("NISAR's flood map, over satellite imagery, as shown on screen. Imagery © Esri.", M + 24, y);
      y += 16;
    }
    if (next) y = wrap(next, M, y + 24, W - 2 * M, 28, { font: sans(19, 500), color: ink });
    hr(y + 6); y += 44;
    g.font = sans(17, 600); g.fillStyle = muted; g.fillText("LIMITS", M, y);
    y = wrap("Provisional NISAR data; not an operational product. Not for emergency decisions on its own; use it beside official warnings and local reports. " +
      `${TRUST_RECORD} Water under trees shows as brighter radar; open water outside the river's valley floor is left out.`, M, y + 32, W - 2 * M, 27, { font: sans(18) });
    g.font = sans(17, 600); g.fillStyle = muted; g.fillText("WHERE IT CAME FROM", M, y + 22); y += 54;
    y = wrap(`Flood pass: ${rec.wet.name}`, M, y, W - 2 * M, 24, { font: sans(15), breakAll: true });
    y = wrap(`Earlier passes: ${rec.baseline.map((b) => b.name).join(", ")}`, M, y + 4, W - 2 * M, 24, { font: sans(15), breakAll: true });
    y = wrap(`Method: v4, frozen, run in the browser (research/V4_PROTOCOL.md; live runs under research/LIVE_PROTOCOL.md). Heights: ${rec.inputs.heights}. River: ${rec.inputs.river}. ` +
      `Map corners (lon, lat; NW, NE, SE, SW): ${rec.corners.map((p) => `${p[0].toFixed(3)}, ${p[1].toFixed(3)}`).join("; ")}.`, M, y + 8, W - 2 * M, 24, { font: sans(15) });
    y = wrap("Data: NISAR GCOV (NASA/ISRO, via ASF), ESA WorldCover 2021, Copernicus GLO-30" + (rec.kind === "us" ? ", USGS 3DEP lidar and river gauges, NOAA" : "") + (/FABDEM/i.test(rec.inputs.heights) ? ", FABDEM V1-2 (University of Bristol, CC BY-NC-SA 4.0)" : "") + (rec.kind === "us" ? "" : ", GDACS") + ". Imagery © Esri.", M, y + 14, W - 2 * M, 22, { font: sans(14), color: muted });
    const out = document.createElement("canvas"); out.width = W; out.height = Math.max(1754, Math.ceil(y + 60));
    const o = out.getContext("2d"); o.fillStyle = "#fff"; o.fillRect(0, 0, W, out.height); o.drawImage(c, 0, 0);
    return out;
  }

  return { update, record, brief };
})();
