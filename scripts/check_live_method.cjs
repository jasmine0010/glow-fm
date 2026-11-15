// Checks the browser's method v4 (app/livemethod.js) against Python's run on every published live case.
//   node scripts/check_live_method.cjs [folder]     (default app/data/live)
// Python's reference run uses the same rounded arrays the browser reads, so the two should agree almost exactly.
const fs = require("fs"), path = require("path");
const M = require(path.join(__dirname, "..", "app", "livemethod.js"));
const root = path.resolve(process.argv[2] || path.join(__dirname, "..", "app", "data", "live"));
const index = JSON.parse(fs.readFileSync(path.join(root, "index.json"), "utf8"));
let bad = 0;
for (const c of index.cases) {
  const rec = JSON.parse(fs.readFileSync(path.join(root, c.id, "case.json"), "utf8"));
  const buf = c.pack === "gz" ? require("zlib").gunzipSync(fs.readFileSync(path.join(root, c.id, "pack.bin.gz"))) : fs.readFileSync(path.join(root, c.id, "pack.bin"));
  const d = M.decodePack(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length), rec.layout);
  const r = M.run(d, rec.layout.width, rec.layout.height), ref = rec.reference_run;
  if (r.error) { bad++; console.log(`FAIL ${c.id}: ${r.error}`); continue; }
  const dThr = Math.abs(r.threshold - ref.threshold_db), dPx = Math.abs(r.flagged - ref.flagged_px) / Math.max(1, ref.flagged_px);
  const dLand = ref.flagged_land_px === undefined ? 0 : Math.abs(r.flaggedLand - ref.flagged_land_px) / Math.max(1, ref.flagged_land_px);
  const ok = dThr < 0.01 && dPx < 0.002 && dLand < 0.002 && r.usedRatio === ref.used_hh_minus_hv && r.confident === ref.confident;
  if (!ok) bad++;
  console.log(`${ok ? "ok  " : "FAIL"} ${c.id}: cut-off ${r.threshold.toFixed(4)} vs ${ref.threshold_db.toFixed(4)} dB, flagged ${r.flagged} vs ${ref.flagged_px} px, ` +
              `HH-HV ${r.usedRatio}/${ref.used_hh_minus_hv}, confident ${r.confident}/${ref.confident}`);
}
console.log(bad ? `${bad} FAILED` : `LIVE METHOD CHECK PASSED (${index.cases.length} cases)`);
process.exit(bad ? 1 : 0);
