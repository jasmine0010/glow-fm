// Writes each live case's scope into the case index: the share of its valley floor that is forest or wetland, and
// whether that's enough for GLOWfm to apply there (app/livescope.js holds the rule).
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
  const s = Scope.share(d, rec.rule), ok = Scope.inScope(s);
  c.scope = { tree_share: s === null ? null : Math.round(s * 1000) / 1000, in_scope: ok };
  if (ok) inside++;
  console.log(`${ok ? "in " : "out"} ${s === null ? " -  " : s.toFixed(2)} ${c.id}`);
}
index.scope_rule = { min_tree_share: Scope.MIN, added: "2026-11-15", defined_in: "app/livescope.js" };
const text = JSON.stringify(index, null, 2);   // the file keeps its own line endings
fs.writeFileSync(indexPath, raw.includes("\r\n") ? text.replace(/\n/g, "\r\n") : text);
console.log(`${inside} of ${index.cases.length} cases in scope`);
