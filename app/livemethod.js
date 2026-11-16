(function (root) {
  const LC_TREE = 1;
  const LOW_MAX_M = 2, HIGH_MIN_M = 4, HIGH_MAX_M = 8, MIN_CHECK_PX = 200;

  function decodePack(buffer, layout) {
    const n = layout.width * layout.height, out = {};
    let off = 0;
    for (const a of layout.arrays) {
      if (a.type === "int16") {
        const v = new Int16Array(buffer.slice(off, off + 2 * n)), f = new Float32Array(n);
        for (let i = 0; i < n; i++) f[i] = v[i] === -32768 ? NaN : v[i] / 100;
        out[a.name] = f; off += 2 * n;
      } else if (a.type === "uint16") {
        const v = new Uint16Array(buffer.slice(off, off + 2 * n)), f = new Float32Array(n);
        for (let i = 0; i < n; i++) f[i] = v[i] === 65535 ? Infinity : v[i] * 10;
        out[a.name] = f; off += 2 * n;
      } else {
        out[a.name] = new Uint8Array(buffer.slice(off, off + n)); off += n;
      }
    }
    return out;
  }

  function smoothNan(a, w, h, size) {
    if (size <= 1) return a;
    const r = Math.floor(size / 2), out = new Float32Array(w * h);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        let num = 0, den = 0;
        for (let dy = -r; dy < size - r; dy++) {
          const yy = Math.min(h - 1, Math.max(0, y + dy));
          for (let dx = -r; dx < size - r; dx++) {
            const v = a[yy * w + Math.min(w - 1, Math.max(0, x + dx))];
            if (v === v) { num += v; den++; }
          }
        }
        out[y * w + x] = den > 0 ? num / den : NaN;
      }
    }
    return out;
  }

  const sorted = (vals) => Float64Array.from(vals).sort();
  function percentile(s, q) {
    const pos = (q / 100) * (s.length - 1), lo = Math.floor(pos), hi = Math.ceil(pos);
    return s[lo] + (s[hi] - s[lo]) * (pos - lo);
  }
  function median(vals) {
    const s = sorted(vals), m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }

  function otsuScan(vals, bins = 256) {
    const s = sorted(vals), lo = percentile(s, 0.5), hi = percentile(s, 99.5), h = new Float64Array(bins), width = (hi - lo) / bins;
    for (let i = 0; i < s.length; i++) {
      const v = Math.min(hi, Math.max(lo, s[i]));
      let b = width > 0 ? Math.floor((v - lo) / width) : 0;
      if (b >= bins) b = bins - 1;
      h[b]++;
    }
    let best = -1, at = 0, w0 = 0, s0 = 0;
    const curve = new Float64Array(bins);
    let total = 0, sTotal = 0;
    for (let b = 0; b < bins; b++) { total += h[b]; sTotal += h[b] * (lo + (b + 0.5) * width); }
    for (let b = 0; b < bins; b++) {
      const c = lo + (b + 0.5) * width;
      w0 += h[b]; s0 += h[b] * c;
      const w1 = total - w0, m0 = s0 / Math.max(w0, 1), m1 = (sTotal - s0) / Math.max(w1, 1), v = w0 * w1 * (m0 - m1) ** 2;
      curve[b] = v;
      if (v > best) { best = v; at = c; }
    }
    return { at, lo, width, curve };
  }
  const otsu = (vals) => otsuScan(vals).at;

  function histogram(vals, bins = 64) {
    const s = sorted(vals), lo = percentile(s, 0.5), hi = percentile(s, 99.5), counts = new Array(bins).fill(0), width = (hi - lo) / bins;
    for (let i = 0; i < s.length; i++) {
      if (s[i] < lo || s[i] > hi) continue;
      counts[Math.min(bins - 1, width > 0 ? Math.floor((s[i] - lo) / width) : 0)]++;
    }
    return { lo, hi, counts, n: s.length };
  }

  function valleyShift(dhhSmooth, lc, hand, dist, valleyM) {
    const low = [], high = [];
    for (let i = 0; i < dhhSmooth.length; i++) {
      const v = dhhSmooth[i];
      if (!(v === v) || lc[i] !== LC_TREE || !(dist[i] < valleyM)) continue;
      if (hand[i] < LOW_MAX_M) low.push(v);
      else if (hand[i] > HIGH_MIN_M && hand[i] < HIGH_MAX_M) high.push(v);
    }
    if (low.length < MIN_CHECK_PX || high.length < MIN_CHECK_PX) return { low: null, high: null, lowMinusHigh: null };
    const a = median(low), b = median(high);
    return { low: a, high: b, lowMinusHigh: a - b };
  }

  const FROZEN = { baseline: "median", signal: "adaptive", confidence_db: 0.5, wet_scene_db: 0.5, smooth_px: 3, hand_max_m: 6.0, valley_m: 4000.0,
                   min_threshold_db: 0.5, landcover: [1, 2, 0], abstain_timing: [4] };

  function run(d, w, h, rule = {}) {
    const r = { ...FROZEN, ...rule }, n = w * h;
    const baseHH = r.baseline === "single" ? d.one_hh : d.median_hh, baseHV = r.baseline === "single" ? d.one_hv : d.median_hv;
    const dhh = new Float32Array(n), dhv = new Float32Array(n);
    for (let i = 0; i < n; i++) { dhh[i] = d.wet_hh[i] - baseHH[i]; dhv[i] = d.wet_hv[i] - baseHV[i]; }
    const shift = valleyShift(smoothNan(dhh, w, h, r.smooth_px), d.landcover, d.hand, d.dist, r.valley_m);
    const useRatio = r.signal === "hh_minus_hv" || (r.signal === "adaptive" && shift.high !== null && shift.high > r.wet_scene_db);
    const raw = useRatio ? dhh.map((v, i) => v - dhv[i]) : dhh;
    const change = smoothNan(raw, w, h, r.smooth_px);
    const lcSet = new Set(r.landcover), abstain = new Set(r.abstain_timing);
    const eligible = new Uint8Array(n), mapped = new Uint8Array(n), floor = [];
    for (let i = 0; i < n; i++) {
      mapped[i] = abstain.has(d.timing[i]) ? 0 : 1;
      if (change[i] === change[i] && lcSet.has(d.landcover[i]) && d.hand[i] < r.hand_max_m) {
        eligible[i] = 1;
        if (d.dist[i] < r.valley_m) floor.push(change[i]);
      }
    }
    if (floor.length < 500) return { error: `Too few valley-floor pixels (${floor.length}) for GLOWfm to set a cut-off.` };
    const scan = otsuScan(floor), otsuDb = scan.at, threshold = Math.max(otsuDb, r.min_threshold_db);
    const pred = new Uint8Array(n);
    let flagged = 0, flaggedLand = 0;
    for (let i = 0; i < n; i++) if (eligible[i] && mapped[i] && change[i] > threshold) { pred[i] = 1; flagged++; if (!d.water || !d.water[i]) flaggedLand++; }
    return { pred, mapped, change, threshold, flagged, flaggedLand, usedRatio: useRatio, confident: shift.lowMinusHigh !== null && shift.lowMinusHigh > r.confidence_db,
             lowMinusHigh: shift.lowMinusHigh, highDb: shift.high, otsuDb, floorHist: histogram(floor), otsuScan: { lo: scan.lo, width: scan.width, curve: Array.from(scan.curve) } };
  }

  function score(res, estimate) {
    let tp = 0, fn = 0, fp = 0, tn = 0;
    for (let i = 0; i < res.pred.length; i++) {
      const e = estimate[i];
      if (!e || !res.mapped[i]) continue;
      if (e === 1) res.pred[i] ? tp++ : fn++;
      else res.pred[i] ? fp++ : tn++;
    }
    const judged = tp + fn + fp;
    return { tp, fn, fp, tn, csi: judged ? tp / judged : null, recall: tp + fn ? tp / (tp + fn) : null, precision: tp + fp ? tp / (tp + fp) : null };
  }

  const api = { decodePack, run, score, FROZEN, CONST: { LC_TREE, LOW_MAX_M, HIGH_MIN_M, HIGH_MAX_M, MIN_CHECK_PX }, _internal: { smoothNan, otsu, percentile, median } };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LiveMethod = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
