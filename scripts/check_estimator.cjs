// Compares the browser flood estimate with the Python result recorded for each river by scripts/build_dashboard.py.
// Run with: node scripts/check_estimator.cjs. It exits with an error if any case differs by more than 0.5%.

const fs = require("fs");
const path = require("path");
const { packFromBuffer, estimateFlood } = require("../app/estimator.js");

const dir = path.join(__dirname, "..", "app", "data", "dashboard");
const { rivers } = JSON.parse(fs.readFileSync(path.join(dir, "rivers.json"), "utf8"));
let failed = 0;
for (const river of rivers) {
  const file = fs.readFileSync(path.join(dir, `${river.id}.bin`));
  const buffer = file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength);
  const pack = packFromBuffer(river.grid, buffer);
  for (const check of river.checks) {
    const points = river.gauges.map((g, k) => ({ chain: g.chain_m, wse: check.wse_m[k] }));
    const t0 = Date.now();
    const got = estimateFlood(pack, points);
    const off = check.estimated_ha ? Math.abs(got.ha - check.estimated_ha) / check.estimated_ha : Math.abs(got.ha);
    const ok = off <= 0.005;
    failed += ok ? 0 : 1;
    console.log(`${ok ? "ok  " : "FAIL"} ${river.id} ${check.time}: browser ${got.ha.toFixed(2)} ha, Python ${check.estimated_ha.toFixed(2)} ha, ${(Date.now() - t0)} ms`);
  }
}
if (failed) { console.error(`${failed} case(s) differ by more than 0.5%`); process.exit(1); }
console.log("ESTIMATOR CHECK PASSED");
