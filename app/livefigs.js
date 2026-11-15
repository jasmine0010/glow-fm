// Run it yourself, analysis: figures computed in the browser from a run's pack (live.data) and result (live.result), in
// the Results page's style (figkit.js), each downloadable as SVG, PNG and CSV. They use the method's own signal and
// rules (livemethod.js), so they explain this run: whether low ground brightened, why the trust light is green or red,
// how much the map depends on its settings, where the flagged area sits, and, where gauges exist, how the score moves.
// Descriptive: a figure here is a look at one run, not a test of the method.

const LiveFigs = (() => {
  const S = { rec: null, d: null, res: null, s: null, out: null, figs: {}, timer: null };
  const LC = { 1: "Tree cover", 2: "Wetland", 0: "Other (incl. water)", 3: "Crop, grass, shrub" };
  const sdb = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(2)} dB`;
  const q = (sorted, p) => { if (!sorted.length) return NaN; const k = (sorted.length - 1) * p, lo = Math.floor(k); return sorted[lo] + (sorted[Math.min(sorted.length - 1, lo + 1)] - sorted[lo]) * (k - lo); };

  // ---------- the numbers behind every figure, from one pass over the run ----------
  function compute() {
    const { rec, d, res, s } = S, W = rec.layout.width, H = rec.layout.height, n = W * H, C = LiveMethod.CONST, F = LiveMethod.FROZEN, px = rec.pixel_ha;
    const rule = { ...F, ...s }, lcSet = new Set(rule.landcover), land = (i) => !(d.water && d.water[i]);
    const eligible = (i, hmax) => res.change[i] === res.change[i] && lcSet.has(d.landcover[i]) && d.hand[i] < hmax && res.mapped[i];

    // A. the method's signal against height above the nearest water, forest and wetland on the valley floor
    const step = 0.5, h0 = -1, h1 = 10, nb = Math.round((h1 - h0) / step), binVals = Array.from({ length: nb }, () => []), binFlag = new Array(nb).fill(0);
    for (let i = 0; i < n; i++) {
      const lc = d.landcover[i], hd = d.hand[i], v = res.change[i];
      if ((lc !== 1 && lc !== 2) || !(v === v) || !(d.dist[i] < rule.valley_m) || !(hd >= h0 && hd < h1)) continue;
      const k = Math.floor((hd - h0) / step);
      binVals[k].push(v);
      if (res.pred[i]) binFlag[k]++;
    }
    const sig = binVals.map((vals, k) => { const sv = Float64Array.from(vals).sort(); return { lo: h0 + k * step, hi: h0 + (k + 1) * step, n: sv.length, q25: q(sv, 0.25), q50: q(sv, 0.5), q75: q(sv, 0.75), flagged: sv.length ? binFlag[k] / sv.length : NaN }; });

    // B. the trust light's own comparison: smoothed HH change on low forest against higher forest (LiveMethod's valleyShift)
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

    // C. flagged land as the cut-off varies (everything else as run), and as the height limit varies (the method rerun)
    const cuts = [];
    for (let t = 0; t <= 4.0001; t += 0.1) cuts.push(+t.toFixed(1));
    const byCut = cuts.map((t) => { let c = 0; for (let i = 0; i < n; i++) if (eligible(i, rule.hand_max_m) && res.change[i] > t && land(i)) c++; return { cut: t, ha: c * px }; });
    const atRun = (() => { let c = 0; for (let i = 0; i < n; i++) if (eligible(i, rule.hand_max_m) && res.change[i] > res.threshold && land(i)) c++; return c * px; })();
    const byHeight = [2, 3, 4, 5, 6, 7, 8, 10].map((hm) => { const r = LiveMethod.run(d, W, H, { ...s, hand_max_m: hm }); return { hand_max_m: hm, ha: r.error ? null : r.flaggedLand * px, cut: r.error ? null : r.threshold }; });

    // D. where the flagged land sits
    const byLc = {}, bands = [[-Infinity, 1, "under 1 m"], [1, 2, "1–2 m"], [2, 4, "2–4 m"], [4, 6, "4–6 m"], [6, Infinity, "6 m or more"]], byBand = bands.map(() => 0);
    for (let i = 0; i < n; i++) {
      if (!res.pred[i] || !land(i)) continue;
      byLc[d.landcover[i]] = (byLc[d.landcover[i]] || 0) + px;
      const b = bands.findIndex(([a, z]) => d.hand[i] >= a && d.hand[i] < z);
      if (b >= 0) byBand[b] += px;
    }

    // E. against the gauge-and-lidar estimate, as the cut-off varies (only where gauges exist)
    let score = null;
    if (d.estimate) {
      score = cuts.map((t) => {
        let tp = 0, fn = 0, fp = 0;
        for (let i = 0; i < n; i++) {
          const e = d.estimate[i];
          if (!e || !res.mapped[i]) continue;
          const on = eligible(i, rule.hand_max_m) && res.change[i] > t;
          if (e === 1) on ? tp++ : fn++; else if (on) fp++;
        }
        return { cut: t, csi: tp + fn + fp ? tp / (tp + fn + fp) : null, recall: tp + fn ? tp / (tp + fn) : null, precision: tp + fp ? tp / (tp + fp) : null };
      });
    }
    return { sig, trust, byCut, atRun, byHeight, byLc, bands: bands.map((b, k) => ({ band: b[2], ha: byBand[k] })), score, rule };
  }

  // ---------- the figures ----------
  const panelH = (W) => (W < 640 ? 300 : 320);
  function figSignature(box) {
    return fkFigure(box, {
      name: "run-signature", label: "This run's radar signature: the method's signal against height above the nearest water",
      height: (W) => panelH(W) + 150,
      csv: () => [["height_from_m", "height_to_m", "pixels", "signal_q25_db", "signal_median_db", "signal_q75_db", "share_flagged"], ...S.out.sig.map((b) => [b.lo, b.hi, b.n, b.q25, b.q50, b.q75, b.flagged])],
      draw(svg, W, H, tip) {
        const o = S.out, ok = o.sig.filter((b) => b.n >= 30), x0 = -1, x1 = 10;
        const pa = fkPanel(svg, { x: 0, y: 0, w: W, h: panelH(W), letter: "a", title: `The method's signal by height above the nearest water (forest and wetland, ${o.sig.reduce((t, b) => t + b.n, 0).toLocaleString("en-US")} pixels)` });
        const vals = ok.flatMap((b) => [b.q25, b.q75, S.res.threshold]), lo = Math.floor(Math.min(...vals, -1)), hi = Math.ceil(Math.max(...vals, 2));
        const sx = fkLinear(x0, x1, 0, pa.w), sy = fkLinear(lo, hi, pa.h, 0);
        fkAxes(pa, sx, sy, { ylabel: "Signal (dB)", xticks: [] });
        fkEl(pa.g, "path", { d: fkPath(ok.map((b) => [sx((b.lo + b.hi) / 2), sy(b.q75)])) + ok.slice().reverse().map((b) => `L${sx((b.lo + b.hi) / 2)} ${sy(b.q25)}`).join("") + "Z", class: "f-nisar", "fill-opacity": 0.18 });
        fkEl(pa.g, "path", { d: fkPath(ok.map((b) => [sx((b.lo + b.hi) / 2), sy(b.q50)])), class: "s-nisar", fill: "none", "stroke-width": 1.6 });
        fkEl(pa.g, "line", { x1: 0, x2: pa.w, y1: sy(S.res.threshold), y2: sy(S.res.threshold), class: "fk-ref" });
        fkEl(pa.g, "line", { x1: sx(S.out.rule.hand_max_m), x2: sx(S.out.rule.hand_max_m), y1: 0, y2: pa.h, class: "fk-ref" });
        fkEl(pa.g, "text", { x: 4, y: sy(S.res.threshold) - 5, class: "fk-tick" }, `cut-off ${sdb(S.res.threshold)}`);
        fkEl(pa.g, "text", { x: sx(S.out.rule.hand_max_m) + 4, y: 14, class: "fk-tick" }, `height limit ${S.out.rule.hand_max_m} m`);
        fkKey(pa, [["line", "s-nisar", "Median"], ["patch", "f-nisar", "Middle half"]], "tr");
        const pts = ok.map((b) => ({ x: sx((b.lo + b.hi) / 2), y: sy(b.q50), html: `${b.lo}–${b.hi} m above water · ${b.n.toLocaleString("en-US")} px<br>median ${sdb(b.q50)} · ${Math.round(100 * b.flagged)}% flagged` }));
        fkHover(pa, tip, (px, py) => fkNearest(pts, px, py, 20));
        const pb = fkPanel(svg, { x: 0, y: panelH(W) + 6, w: W, h: 144, letter: "b", title: "Share of those pixels the method flagged", m: { t: 26, r: 18, b: 42, l: 56 } });
        const sy2 = fkLinear(0, 1, pb.h, 0);
        fkAxes(pb, sx, sy2, { xlabel: "Height above the nearest mapped water (m)", ylabel: "Flagged", yfmt: (v) => `${Math.round(v * 100)}%`, yticks: [0, 0.5, 1] });
        ok.forEach((b) => fkEl(pb.g, "rect", { x: sx(b.lo) + 0.5, y: sy2(b.flagged), width: Math.max(1, sx(b.hi) - sx(b.lo) - 1), height: pb.h - sy2(b.flagged), class: "f-nisar", "fill-opacity": 0.6 }));
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
        fkKey(p, [["line", "s-water", "Forest under 2 m above water"], ["line", "s-veil", "Forest 4–8 m above water"]], "tr");
      },
    });
  }

  function figRobust(box) {
    return fkFigure(box, {
      name: "run-robustness", label: "How much the map depends on its settings: flagged area against cut-off and height limit",
      height: (W) => (W < 700 ? 2 * panelH(W) + 10 : panelH(W)),
      csv: () => [["sweep", "value", "flagged_land_ha", "cut_off_db"], ...S.out.byCut.map((r) => ["cut-off (dB)", r.cut, r.ha, r.cut]), ...S.out.byHeight.map((r) => ["height limit (m)", r.hand_max_m, r.ha, r.cut])],
      draw(svg, W, H, tip) {
        const o = S.out, side = W >= 700, pw = side ? W / 2 - 8 : W, ph = side ? H : panelH(W), ymax = Math.max(...o.byCut.map((r) => r.ha), ...o.byHeight.map((r) => r.ha || 0), 1) * 1.08;
        {
          const p = fkPanel(svg, { x: 0, y: 0, w: pw, h: ph, letter: "a", title: "If the cut-off were…" });
          const sx = fkLinear(0, 4, 0, p.w), sy = fkLinear(0, ymax, p.h, 0);
          fkAxes(p, sx, sy, { xlabel: "Cut-off (dB)", ylabel: "Flagged land (ha)" });
          fkEl(p.g, "path", { d: fkPath(o.byCut.map((r) => [sx(r.cut), sy(r.ha)])), class: "s-nisar", fill: "none", "stroke-width": 1.6 });
          fkEl(p.g, "line", { x1: sx(o.rule.min_threshold_db), x2: sx(o.rule.min_threshold_db), y1: 0, y2: p.h, class: "fk-ref" });
          fkMark(p.g, "o", sx(S.res.threshold), sy(o.atRun), "f-nisar", 4.5);
          fkEl(p.g, "text", { x: sx(S.res.threshold) + 8, y: sy(o.atRun) - 6, class: "fk-tick" }, `this run: ${Math.round(o.atRun).toLocaleString("en-US")} ha at ${sdb(S.res.threshold)}`);
          const pts = o.byCut.map((r) => ({ x: sx(r.cut), y: sy(r.ha), html: `cut-off ${sdb(r.cut)}: ${Math.round(r.ha).toLocaleString("en-US")} ha` }));
          fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 16));
        }
        {
          const p = fkPanel(svg, { x: side ? W / 2 + 8 : 0, y: side ? 0 : ph + 10, w: pw, h: ph, letter: "b", title: "If the height limit were… (method rerun)" });
          const sx = fkLinear(2, 10, 0, p.w), sy = fkLinear(0, ymax, p.h, 0), rows = o.byHeight.filter((r) => r.ha !== null);
          fkAxes(p, sx, sy, { xlabel: "Height limit above the nearest water (m)", ylabel: "Flagged land (ha)" });
          fkEl(p.g, "path", { d: fkPath(rows.map((r) => [sx(r.hand_max_m), sy(r.ha)])), class: "s-nisar", fill: "none", "stroke-width": 1.4 });
          rows.forEach((r) => fkMark(p.g, r.hand_max_m === o.rule.hand_max_m ? "o" : "s", sx(r.hand_max_m), sy(r.ha), r.hand_max_m === o.rule.hand_max_m ? "f-nisar" : "f-veil", r.hand_max_m === o.rule.hand_max_m ? 4.5 : 3));
          fkEl(p.g, "line", { x1: sx(LiveMethod.FROZEN.hand_max_m), x2: sx(LiveMethod.FROZEN.hand_max_m), y1: 0, y2: p.h, class: "fk-ref" });
          fkEl(p.g, "text", { x: sx(LiveMethod.FROZEN.hand_max_m) + 4, y: 14, class: "fk-tick" }, "frozen: 6 m");
          const pts = rows.map((r) => ({ x: sx(r.hand_max_m), y: sy(r.ha), html: `limit ${r.hand_max_m} m: ${Math.round(r.ha).toLocaleString("en-US")} ha (cut-off ${sdb(r.cut)})` }));
          fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 16));
        }
      },
    });
  }

  function figWhere(box) {
    return fkFigure(box, {
      name: "run-flagged-area", label: "Where the flagged area sits: by land cover and by height above water",
      height: (W) => (W < 700 ? 2 * 220 + 10 : 220),
      csv: () => [["group", "class", "flagged_land_ha"], ...Object.entries(S.out.byLc).map(([k, v]) => ["land cover", LC[k] || k, v]), ...S.out.bands.map((b) => ["height above water", b.band, b.ha])],
      draw(svg, W, H) {
        const o = S.out, side = W >= 700, pw = side ? W / 2 - 8 : W, ph = side ? H : 220;
        const bars = (x, y, letter, title, rows) => {
          const p = fkPanel(svg, { x, y, w: pw, h: ph, letter, title, m: { t: 30, r: 60, b: 36, l: 120 } });
          const vmax = Math.max(...rows.map((r) => r[1]), 1), sx = fkLinear(0, vmax * 1.05, 0, p.w), rowH = p.h / rows.length;
          fkAxes(p, sx, fkLinear(0, 1, p.h, 0), { xlabel: "Flagged land (ha)", yticks: [] });
          rows.forEach(([label, v], k) => {
            const yy = k * rowH + rowH * 0.2;
            fkEl(p.g, "rect", { x: 0, y: yy, width: Math.max(0, sx(v)), height: rowH * 0.6, class: "f-nisar", "fill-opacity": 0.7 });
            fkEl(p.g, "text", { x: -6, y: yy + rowH * 0.3 + 4, class: "fk-tick", "text-anchor": "end" }, label);
            fkEl(p.g, "text", { x: sx(v) + 4, y: yy + rowH * 0.3 + 4, class: "fk-tick" }, Math.round(v).toLocaleString("en-US"));
          });
        };
        bars(0, 0, "a", "By land cover", [1, 2, 0, 3].map((k) => [LC[k], o.byLc[k] || 0]));
        bars(side ? W / 2 + 8 : 0, side ? 0 : ph + 10, "b", "By height above the nearest water", o.bands.map((b) => [b.band, b.ha]));
      },
    });
  }

  function figScore(box) {
    return fkFigure(box, {
      name: "run-score-by-cut-off", label: "Score against the gauge-and-lidar estimate as the cut-off varies",
      height: (W) => panelH(W),
      csv: () => [["cut_off_db", "csi", "recall", "precision"], ...S.out.score.map((r) => [r.cut, r.csi, r.recall, r.precision])],
      draw(svg, W, H, tip) {
        const o = S.out, p = fkPanel(svg, { x: 0, y: 0, w: W, h: H, title: "Against the river's gauges and lidar, if the cut-off were…" });
        const sx = fkLinear(0, 4, 0, p.w), sy = fkLinear(0, 1, p.h, 0);
        fkAxes(p, sx, sy, { xlabel: "Cut-off (dB)", ylabel: "Score (1 is perfect)" });
        [["csi", "s-nisar", 1.8], ["recall", "s-water", 1.2], ["precision", "s-veil", 1.2]].forEach(([k, cls, sw]) => fkEl(p.g, "path", { d: fkPath(o.score.map((r) => [sx(r.cut), r[k] === null ? NaN : sy(r[k])])), class: cls, fill: "none", "stroke-width": sw }));
        const f = S.rec.score && S.rec.score.scores, ft = S.rec.reference_run && S.rec.reference_run.threshold_db;
        if (f && ft !== undefined) { fkMark(p.g, "D", sx(ft), sy(f.csi), "f-nisar", 4.5); fkEl(p.g, "text", { x: sx(ft) + 8, y: sy(f.csi) - 6, class: "fk-tick" }, `published test: ${f.csi.toFixed(2)}`); }
        fkEl(p.g, "line", { x1: sx(S.res.threshold), x2: sx(S.res.threshold), y1: 0, y2: p.h, class: "fk-ref" });
        fkEl(p.g, "text", { x: 6, y: p.h - 8, class: "fk-tick" }, "A cut-off chosen after seeing this curve is tuning, not testing.");
        fkKey(p, [["line", "s-nisar", "Match (CSI)"], ["line", "s-water", "Recall"], ["line", "s-veil", "Precision"]], "tr");
        const pts = o.score.filter((r) => r.csi !== null).map((r) => ({ x: sx(r.cut), y: sy(r.csi), html: `cut-off ${sdb(r.cut)}: match ${r.csi.toFixed(2)} · recall ${r.recall === null ? "—" : r.recall.toFixed(2)} · precision ${r.precision === null ? "—" : r.precision.toFixed(2)}` }));
        fkHover(p, tip, (px, py) => fkNearest(pts, px, py, 16));
      },
    });
  }

  const MAKERS = { signature: figSignature, trust: figTrust, robust: figRobust, where: figWhere, score: figScore };

  // ---------- public: draw (or redraw) for the latest run ----------
  function update(rec, d, res, s) {
    Object.assign(S, { rec, d, res, s });
    clearTimeout(S.timer);
    S.timer = setTimeout(() => {
      if (S.res !== res || res.error) return;
      S.out = compute();
      $("analysis").hidden = false;
      $("analysis-sub").innerHTML = `${escHtml(rec.place)} · NISAR pass ${fmtTime(rec.wet.time)} · ${rec.layout.width} × ${rec.layout.height} pixels of ${(Math.sqrt(rec.pixel_ha) * 100).toFixed(0)} m` +
        (rec.kind === "us" && d.estimate ? "" : ' · <span class="live-warn">not checked against ground truth</span>') + ". Each figure is computed here, from this run, and downloads with its data.";
      $("af-score").hidden = !d.estimate;
      for (const [k, make] of Object.entries(MAKERS)) {
        if (k === "score" && !d.estimate) continue;
        const box = $(`af-${k}`).querySelector(".af-mount");
        if (S.figs[k] && S.figs[k].box === box) S.figs[k].fig.render();
        else S.figs[k] = { box, fig: make(box) };
      }
    }, 250);
  }

  // A record of the run, so it can be cited and repeated: case, pass, settings, inputs and every figure's numbers.
  function record() {
    const { rec, res, s, out } = S;
    return { site: "GLOWfm", method: "v4 (frozen), run in the browser", made_utc: new Date().toISOString(), case: { id: rec.id, place: rec.place, kind: rec.kind, custom: !!rec.custom, corners: rec.corners, box: rec.box || null },
      pass: rec.wet, baseline: rec.baseline, inputs: { heights: rec.inputs.heights, river: rec.inputs.river, epsg: rec.inputs.epsg }, settings: { ...LiveMethod.FROZEN, ...s },
      result: { threshold_db: res.threshold, otsu_db: res.otsuDb, used_hh_minus_hv: res.usedRatio, flagged_land_ha: res.flaggedLand * rec.pixel_ha, trust: { low_minus_high_db: res.lowMinusHigh, green: res.confident } },
      published_score: rec.score ? rec.score.scores : null, figures: out };
  }

  // A one-page brief for someone who has to act on the map: the number, the trust light, the map as shown, when NISAR
  // passes next, the limits and where every input came from. White, so it prints. `map` is a canvas of the map view.
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
    y = wrap("flagged as flooded by NISAR's method, outside permanent lakes and rivers", M, y + 40, W - 2 * M, 30, { font: sans(22), color: soft });
    const dot = { green: "#2f9e4f", red: "#d64545", amber: "#d49b12", grey: "#8a969e" }[light.cls] || "#8a969e";
    g.fillStyle = dot; g.beginPath(); g.arc(M + 9, y + 12, 9, 0, 2 * Math.PI); g.fill();
    g.font = sans(23, 600); g.fillStyle = ink; g.fillText(light.cls === "grey" ? light.label : `Trust light: ${light.cls}${light.cls === "red" ? ". Don't rely on this map" : ""}`, M + 28, y + 20);
    y = wrap(light.why, M + 28, y + 52, W - 2 * M - 28, 28, { font: sans(19) });
    if (rec.kind === "us" && rec.score && rec.score.scores) {
      y = wrap(`Checked against the river's own gauges and lidar: match ${rec.score.scores.csi.toFixed(2)} (1 is perfect, 95% range ${rec.score.ci95.csi[0].toFixed(2)}–${rec.score.ci95.csi[1].toFixed(2)}), in the frozen test run before anyone saw the result.`, M, y + 10, W - 2 * M, 28, { font: sans(19), color: ink });
    } else y = wrap("Not checked against ground truth: there are no river gauges here, so the trust light decides.", M, y + 10, W - 2 * M, 28, { font: sans(19), color: ink });
    if (!frozen) y = wrap(`Settings changed from the frozen method${yourCsi !== null && yourCsi !== undefined ? ` (match ${yourCsi.toFixed(2)} with these settings)` : ""}. This is not the tested run.`, M, y + 6, W - 2 * M, 28, { font: sans(19, 600), color: "#a35a00" });
    // the map as shown on screen
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
    y = wrap("Provisional NISAR data; not an operational product. Not for emergency decisions on its own: use it beside official warnings and local reports. " +
      `${TRUST_RECORD} Water under trees shows as brighter radar; open water outside the river's valley floor is left out.`, M, y + 32, W - 2 * M, 27, { font: sans(18) });
    g.font = sans(17, 600); g.fillStyle = muted; g.fillText("WHERE IT CAME FROM", M, y + 22); y += 54;
    y = wrap(`Flood pass: ${rec.wet.name}`, M, y, W - 2 * M, 24, { font: sans(15), breakAll: true });
    y = wrap(`Earlier passes: ${rec.baseline.map((b) => b.name).join(", ")}`, M, y + 4, W - 2 * M, 24, { font: sans(15), breakAll: true });
    y = wrap(`Method: v4, frozen, run in the browser (research/V4_PROTOCOL.md; live runs under research/LIVE_PROTOCOL.md). Heights: ${rec.inputs.heights}. River: ${rec.inputs.river}. ` +
      `Map corners (lon, lat; NW, NE, SE, SW): ${rec.corners.map((p) => `${p[0].toFixed(3)}, ${p[1].toFixed(3)}`).join("; ")}.`, M, y + 8, W - 2 * M, 24, { font: sans(15) });
    y = wrap("Data: NISAR GCOV (NASA/ISRO, via ASF), ESA WorldCover 2021, Copernicus GLO-30" + (rec.kind === "us" ? ", USGS 3DEP lidar and river gauges, NOAA" : "") + (/FABDEM/i.test(rec.inputs.heights) ? ", FABDEM V1-2 (University of Bristol, CC BY-NC-SA 4.0)" : "") + (rec.kind === "us" ? "" : ", GDACS") + ". Imagery © Esri.", M, y + 14, W - 2 * M, 22, { font: sans(14), color: muted });
    // At least an A4 page's proportions; longer if the provenance needs it.
    const out = document.createElement("canvas"); out.width = W; out.height = Math.max(1754, Math.ceil(y + 60));
    const o = out.getContext("2d"); o.fillStyle = "#fff"; o.fillRect(0, 0, W, out.height); o.drawImage(c, 0, 0);
    return out;
  }

  return { update, record, brief };
})();
