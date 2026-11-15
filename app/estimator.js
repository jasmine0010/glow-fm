// The gauge-and-lidar flood estimate in the browser. It follows hydraulic_truth in src/hidden_floods/truth.py:
// water level is interpolated along the valley between gauges and held flat past the ends, and ground counts as flooded
// if the water sits more than the margin above it and connects to reference water through ground below the water.
// scripts/check_estimator.cjs compares it with the Python result at the end of each build.

const FLAG = { SEED: 1, SUPPORTED: 2, LC_SHIFT: 2, LC_MASK: 12, GFM_EXCLUDED: 16, GFM_COVERED: 32 };

function packFromBuffer(meta, buffer) {
  const n = meta.pixels;
  const idx = new Int32Array(buffer, 0, n), dem = new Float32Array(buffer, 4 * n, n), chain = new Float32Array(buffer, 8 * n, n), flags = new Uint8Array(buffer, 12 * n, n);
  const lookup = new Int32Array(meta.rows * meta.cols).fill(-1);
  for (let i = 0; i < n; i++) lookup[idx[i]] = i;
  return { meta, n, idx, dem, chain, flags, lookup, depth: new Float32Array(n), wet: new Uint8Array(n), seen: new Uint8Array(n), queue: new Int32Array(n) };
}

// points: [{ chain, wse }]. extra is the what-if rise in metres, added to every gauge.
function estimateFlood(pack, points, extra = 0) {
  const { meta, n, idx, dem, chain, flags, lookup, depth, wet, seen, queue } = pack;
  const sorted = [...points].sort((a, b) => a.chain - b.chain);
  const xs = sorted.map((p) => p.chain), ys = sorted.map((p) => p.wse + extra), last = xs.length - 1;
  let seg = 0;
  for (let i = 0; i < n; i++) {
    const x = chain[i];
    let w;
    if (x <= xs[0]) w = ys[0];
    else if (x >= xs[last]) w = ys[last];
    else {
      if (x < xs[seg] || x > xs[seg + 1]) { seg = 0; while (seg < last - 1 && x > xs[seg + 1]) seg++; }
      w = ys[seg] + (ys[seg + 1] - ys[seg]) * (x - xs[seg]) / (xs[seg + 1] - xs[seg]);
    }
    depth[i] = w - dem[i];
  }
  // Flood fill from reference water through ground below the water surface, with 8 neighbours.
  seen.fill(0);
  let head = 0, tail = 0;
  for (let i = 0; i < n; i++) if ((flags[i] & FLAG.SEED) && depth[i] > 0) { seen[i] = 1; queue[tail++] = i; }
  const { rows, cols } = meta;
  while (head < tail) {
    const i = queue[head++], r = Math.floor(idx[i] / cols), c = idx[i] - r * cols;
    for (let dr = -1; dr <= 1; dr++) {
      const rr = r + dr;
      if (rr < 0 || rr >= rows) continue;
      for (let dc = -1; dc <= 1; dc++) {
        const cc = c + dc;
        if (cc < 0 || cc >= cols) continue;
        const j = lookup[rr * cols + cc];
        if (j >= 0 && !seen[j] && depth[j] > 0) { seen[j] = 1; queue[tail++] = j; }
      }
    }
  }
  let wetCount = 0, tree = 0, excluded = 0, covered = 0, depthSum = 0, maxDepth = 0;
  for (let i = 0; i < n; i++) {
    const f = flags[i], counted = seen[i] && depth[i] > meta.margin_m && (f & FLAG.SUPPORTED) && !(f & FLAG.SEED);
    wet[i] = counted ? 1 : 0;
    if (!counted) continue;
    wetCount++;
    depthSum += depth[i];
    if (depth[i] > maxDepth) maxDepth = depth[i];
    if (((f & FLAG.LC_MASK) >> FLAG.LC_SHIFT) === 1) tree++;
    if (f & FLAG.GFM_COVERED) { covered++; if (f & FLAG.GFM_EXCLUDED) excluded++; }
  }
  const area = meta.pixel_ha;
  return { ha: wetCount * area, treeShare: wetCount ? tree / wetCount : null, maskShare: covered ? excluded / covered : null, meanDepth: wetCount ? depthSum / wetCount : null, maxDepth: wetCount ? maxDepth : null };
}

// Roads on the corridor (scripts/build_roads.py). First the whole of each road that crosses the corridor (points in
// longitude and latitude, with offsets), then short pieces, one per pixel a road crosses: its pixel number, the stretch
// of road it lies on (a point number), where along that stretch it starts and ends (0 to 65535), its length in metres,
// and 1 for a major road. way[j] is the road each piece belongs to.
function roadsFromBuffer(buffer) {
  const L = new Int32Array(buffer, 0, 1)[0], off = new Int32Array(buffer, 4, L + 1), pts = new Float32Array(buffer, 8 + 4 * L, 2 * off[L]);
  const at = 8 + 4 * L + 8 * off[L], k = new Int32Array(buffer, at, 1)[0];
  const pix = new Int32Array(buffer, at + 4, k), seg = new Int32Array(buffer, at + 4 + 4 * k, k), t = new Uint16Array(buffer, at + 4 + 8 * k, 2 * k);
  const metres = new Float32Array(buffer, at + 4 + 12 * k, k), major = new Uint8Array(buffer, at + 4 + 16 * k, k), way = new Int32Array(k);
  for (let j = 0, li = 0; j < k; j++) { while (off[li + 1] <= seg[j]) li++; way[j] = li; }
  return { L, off, pts, k, pix, seg, t, metres, major, way };
}

// Road under the flooding estimateFlood just computed (pack.wet), and the part where Copernicus GFM's exclusion mask says
// today's flood map doesn't map. The same rules as the frozen blind-spot audit: drivable roads, bridges left out.
function roadsUnder(pack, roads) {
  let m = 0, hidden = 0, major = 0;
  for (let j = 0; j < roads.k; j++) {
    const i = roads.pix[j];
    if (!pack.wet[i]) continue;
    const v = roads.metres[j];
    m += v;
    if (roads.major[j]) major += v;
    if (pack.flags[i] & FLAG.GFM_EXCLUDED) hidden += v;
  }
  return { km: m / 1000, hiddenKm: hidden / 1000, majorKm: major / 1000 };
}

const waterSurface = (gauge, stageFt) => (stageFt + gauge.datum_ft + gauge.navd88_offset_ft) * 0.3048;

if (typeof module !== "undefined") module.exports = { FLAG, packFromBuffer, estimateFlood, waterSurface, roadsFromBuffer, roadsUnder };
