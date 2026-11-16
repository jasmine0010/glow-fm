// Writes each live case's scope into the case index, settled before any run: the share of its valley floor that is
// forest or wetland, the ground GLOWfm can read at the pass, and whether both are enough for GLOWfm to apply there
// (app/livescope.js holds the rules).
//   node scripts/scope_cases.cjs [folder]     (default app/data/live)
// scripts/prepare_all_floods.py runs it after preparing new floods.
const fs = require("fs"), path = require("path"), zlib = require("zlib");
const M = require(path.join(__dirname, "..", "app", "livemethod.js"));
const Scope = require(path.join(__dirname, "..", "app", "livescope.js"));
const root = path.resolve(process.argv[2] || path.join(__dirname, "..", "app", "data", "live"));
const indexPath = path.join(root, "index.json"), raw = fs.readFileSync(indexPath, "utf8"), index = JSON.parse(raw);
let inside = 0;
for (const c of index.cases) {
  const rec = JSON.parse(fs.readFileSync(path.join(root, c.id, "case.json"), "utf8"));
  const buf = c.pack === "gz" ? zlib.gunzipSync(fs.readFileSync(path.join(root, c.id, "pack.bin.gz"))) : fs.readFileSync(path.join(root, c.id, "pack.bin"));
  const d = M.decodePack(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.length), rec.layout);
  const s = Scope.share(d, rec.rule), area = Scope.readable(d, rec.rule, rec.pixel_ha), treesOk = Scope.inScope(s), areaOk = Scope.bigEnough(area);
  c.scope = { tree_share: s === null ? null : Math.round(s * 1000) / 1000, readable_ha: area.ha, late_ha: area.late_ha, in_scope: treesOk && areaOk };
  if (treesOk && !areaOk) c.scope.too_small = true;
  if (c.scope.in_scope) inside++;
  console.log(`${c.scope.in_scope ? "in " : "out"} ${s === null ? " -  " : s.toFixed(2)} ${String(area.ha).padStart(6)} ha ${c.id}`);
}
index.scope_rule = { min_tree_share: Scope.MIN, min_readable_ha: Scope.MIN_HA, added: "2026-11-15", defined_in: "app/livescope.js" };
// escaped like Python's json.dump, and the file keeps its own line endings
const text = JSON.stringify(index, null, 2).replace(/[\u007f-￿]/g, (ch) => "\\u" + ch.charCodeAt(0).toString(16).padStart(4, "0"));
fs.writeFileSync(indexPath, raw.includes("\r\n") ? text.replace(/\n/g, "\r\n") : text);
console.log(`${inside} of ${index.cases.length} cases in scope`);
