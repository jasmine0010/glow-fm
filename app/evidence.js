
const METHOD_NAME = (m) => m.split(",")[0].replace("v", "Method ");
const passLabel = (r) => `${r.pair.split("_")[0]}, ${passDate(r.pair)}`;
const n0 = (x) => Math.round(x).toLocaleString("en-US");
const range = (a, f = (x) => x.toFixed(2)) => `${f(Math.min(...a))}–${f(Math.max(...a))}`;
const dbRange = (a) => { const sg = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)}`; return `${sg(Math.min(...a))} to ${sg(Math.max(...a))} dB`; };
const BOOT = "95% intervals from a 2 km block bootstrap, as in the frozen tests";

function setupLimits(metrics, F) {
  const [lo, hi] = scoreRange(metrics), judged = metrics.overbank.filter((r) => r.judgeable), h = metrics.hidden_gauge;
  const failedN = metrics.held_out.filter((r) => r.method.startsWith("v4, median")).length;
  const wins = judged.filter((r) => r.csi > r.lidar_csi).length;
  const cards = [
    [`${lo.toFixed(2)}–${hi.toFixed(2)}`, "Latest test", `The range across its judged passes, although an earlier test of the same method struggled on ${inWords(failedN)} rivers that never reached flood stage.`],
    [`${wins} of ${judged.length}`, "Ahead of a lidar map", `GLOWfm edged out a lidar-only map on ${inWords(wins)} of ${inWords(judged.length)} passes, and only the radar can show when the water comes and goes.`],
    [`${h.median_abs_error_m.toFixed(2)} m`, "Checked against a model", `The reference has its own error, about ${h.median_abs_error_m.toFixed(2)} m in water level with one gauge hidden, so scores near ${F.ref.summary.median_agreement.toFixed(2)} are as close as it can tell.`],
    ["US only", "Tested in the US", "Every fair test so far is on US rivers, and one early try in Cambodia didn't carry over, so this isn't an operational product yet."],
  ];
  $("limits").innerHTML = cards.map(([num, title, text]) => `<div class="stat-card"><span class="stat-num">${num}</span><b class="ev-title">${title}</b><span class="stat-label">${text}</span></div>`).join("");
}

async function resultFacts(metrics) {
  const [sig, strata, study, time, world, ref, elev, cov, fringes, rc, maps] = await Promise.all(["signature", "strata", "study", "time", "world", "reference", "elevation", "coverage", "fringes", "reference_checks", "maps"].map((f) => figJson(`figures/${f}.json`)));
  const dry = sig.bins.filter((b) => b.hi <= 0).map((b) => b.hh_q[1]);
  const wet = sig.bins.filter((b) => b.lo >= 0 && b.n >= 1000).reduce((a, b) => (b.hh_q[1] > a.hh_q[1] ? b : a));
  const [green, all] = strata.groups, tree = (g) => g.by_landcover.find((c) => c.label === "tree cover");
  const audit = metrics.audit.filter((r) => r.truth_wet_ha >= 100), biggest = audit.reduce((a, b) => (b.truth_wet_ha > a.truth_wet_ha ? b : a));
  const peak = world.lat[world.tree_km2.indexOf(Math.max(...world.tree_km2))];
  const judgedTests = metrics.held_out.filter((r) => r.csi !== null && r.csi !== undefined && (r.confirmed_ha ?? r.estimated_ha) >= JUDGE_HA);
  const greenPasses = rc.passes.filter((q) => q.trust === "green");
  const at = (q, m) => q.shift.find((x) => x.shift_m === m).csi;
  const drop = rc.passes.map((q) => ({ q, d: q.csi - at(q, -0.5) })).reduce((a, b) => (b.d > a.d ? b : a));
  const gain = Math.max(...rc.passes.map((q) => at(q, 0.5) - q.csi));
  const width = (ci) => ci[1] - ci[0], enough = rc.passes.filter((q) => q.n_blocks["10000"] >= 5), few = rc.passes.filter((q) => q.n_blocks["10000"] < 5);
  const wider = enough.filter((q) => width(q.ci_by_block["10000"]) > width(q.ci_by_block["2000"]) + 0.02);
  const widest = enough.reduce((a, b) => (width(b.ci_by_block["10000"]) - width(b.ci_by_block["2000"]) > width(a.ci_by_block["10000"]) - width(a.ci_by_block["2000"]) ? b : a));
  const sameFlood = greenPasses.length - new Set(greenPasses.map((q) => q.river)).size;
  return { sig, strata, study, time, world, ref, elev, cov, fringes, rc, maps, dry, wet, green, all, treeGreen: tree(green), treeAll: tree(all), audit, biggest, peak,
    judged: judgedPasses(metrics), rivers: new Set(metrics.held_out.map((r) => r.site)).size, ob: metrics.overbank.filter((o) => o.judgeable),
    judgedTests, judgedRivers: new Set(judgedTests.map((r) => r.site)).size, greenPasses, sameFlood, at, drop, gain, enough, few, wider, widest };
}

function setupAbstract(metrics, F) {
  const [lo, hi] = scoreRange(metrics), px = F.sig.bins.reduce((s, b) => s + b.n, 0);
  const ob = metrics.overbank.filter((r) => r.judgeable), vsLidar = { n: ob.length, wins: ob.filter((r) => r.csi > r.lidar_csi).length, clear: ob.some((r) => r.lidar_interval[0] > 0) };
  $("summary").innerHTML = `Copernicus's global flood map leaves out flooded forest by design, and its mask covers ${PCT(F.world.check.excl_trees)} of the floodplain under trees (${ref("fig-blind")}). That water still shows up in NISAR's L-band radar, because flooded forest brightens by about ${figDb(F.wet.hh_q[1])} (${ref("fig-signature")}). In GLOWfm's latest frozen test, run on rivers it had never seen, its maps matched the river gauges at a CSI of ${lo.toFixed(2)}–${hi.toFixed(2)} (${ref("fig-accuracy")}). GLOWfm also beat a lidar-only map on ${inWords(vsLidar.wins)} of those ${inWords(vsLidar.n)} passes (${ref("lidar")}). ${vsLidar.clear ? "" : "The margins are too small to call, but "}the reference is built from that same lidar, which favors the lidar map, and only the radar shows when the water arrives and drains (${ref("fig-time")}). So far, every test has been on US rivers.`;
  $("abstract-text").innerHTML = `Floodwater under a forest canopy is hidden from optical satellites and hard for the C-band radar behind today's global flood maps, and the Copernicus Global Flood Monitoring (GFM) map leaves it out by design. We tested whether NISAR's L-band radar can map it instead. Flooded forest does brighten, from ${dbRange(F.dry)} while the water stays below ground to ${figDb(F.wet.hh_q[1])} under ${F.wet.lo.toFixed(1)}–${F.wet.hi.toFixed(1)} m of water, across ${n0(px)} forest pixels from ${inWords(F.sig.pooled_from.length)} frozen test passes (${ref("fig-signature")}). Each version of the method was frozen before a flood's data was opened and then run once, for ${metrics.held_out.length} tests on ${F.rivers} rivers, ${F.judgedTests.length} of which (on ${F.judgedRivers} rivers) had enough flooding to judge. The latest test's ${inWords(latestPasses(metrics).length)} judged passes scored a CSI of ${lo.toFixed(2)}–${hi.toFixed(2)} (${ref("fig-accuracy")}, with maps of three in ${ref("fig-maps")}), and on the ${inWords(F.greenPasses.length)} passes the trust light marked green${F.sameFlood ? `, ${inWords(F.sameFlood + 1)} of them the same ${siteTitle(F.greenPasses.find((q, k, a) => a.findIndex((x) => x.river === q.river) !== k).river).split(",")[0]} flood` : ""}, GLOWfm found ${range(F.greenPasses.map((q) => q.trees.recall), PCT)} of the flooding under trees at ${range(F.greenPasses.map((q) => q.trees.precision), PCT)} precision. Those scores are measured against a modeled reference that matches itself at ${F.ref.summary.median_agreement.toFixed(2)} when one gauge is hidden, and lowering its water surface by 0.5 m drops the ${siteTitle(F.drop.q.river).split(",")[0]}'s ${passDate(F.drop.q.pair)} score from ${F.drop.q.csi.toFixed(2)} to ${F.at(F.drop.q, -0.5).toFixed(2)} (${ref("fig-reference")}). On ${F.audit.length} audited passes over ${inWords(new Set(F.audit.map((r) => r.site)).size)} Gulf Coast rivers, GFM mapped at most ${Math.max(...F.audit.map((r) => r.gfm_on_wet_ha))} ha where gauges and lidar estimated ${range(F.audit.map((r) => r.truth_wet_ha), n0)} ha, and worldwide ${(F.world.totals.tree_km2 / 1e6).toFixed(1)} million km² of river floodplain lies under trees (${ref("fig-blind")}). GLOWfm narrowly beat a lidar-only map on ${inWords(vsLidar.wins)} of ${inWords(vsLidar.n)} passes and, unlike it, shows when the water arrives and drains (${ref("lidar")}; ${ref("fig-time")}). Without lidar, NISAR averaged ${F.elev.means.nisar_with_copernicus.toFixed(2)} with elevation data that includes treetops and ${F.elev.means.nisar_with_fabdem.toFixed(2)} with a bare-earth model (FABDEM), against ${F.elev.means.nisar_with_lidar.toFixed(2)} with lidar (${ref("no-lidar")}). Every test so far is on US rivers, and this isn't an operational product yet.`;
}

const TAKE = {
  blind: (F) => `Copernicus GFM's own mask leaves out ${PCT(F.world.check.excl_trees)} of the floodplain under trees but only ${PCT(F.world.check.excl_else)} elsewhere, and on ${F.audit.length} audited passes it mapped at most ${Math.max(...F.audit.map((r) => r.gfm_on_wet_ha))} ha where gauges and lidar estimated ${range(F.audit.map((r) => r.truth_wet_ha), n0)} ha.`,
  signature: (F) => `Across ${n0(F.sig.bins.reduce((s, b) => s + b.n, 0))} forest pixels from ${inWords(F.sig.pooled_from.length)} frozen test passes, the median change sits at ${dbRange(F.dry)} while the water stays below ground and climbs to ${figDb(F.wet.hh_q[1])} under ${F.wet.lo.toFixed(1)}–${F.wet.hi.toFixed(1)} m of water, as the long waves bounce between the water and the trunks.`,
  maps: (F) => {
    const [strong, typical, failed] = ["strong", "typical", "failed"].map((k) => F.maps.passes.find((p) => p.kind === k)), name = (p) => `${siteTitle(p.river).split(",")[0]}, ${p.csi.toFixed(2)}`;
    return `Here's GLOWfm's map pixel by pixel against the river's answer on a strong pass (${name(strong)}), a typical one (${name(typical)}) and a failure (${name(failed)}).`;
  },
  accuracy: (F, metrics) => {
    const [lo, hi] = scoreRange(metrics), failed = metrics.held_out.filter((r) => r.method.startsWith("v4, median")).map((r) => r.csi);
    return `GLOWfm has had ${metrics.held_out.length} frozen tests on ${F.rivers} rivers, ${F.judgedTests.length} of them with enough flooding to judge, and the latest scored ${lo.toFixed(2)}–${hi.toFixed(2)}, though an earlier test of the same method struggled on ${inWords(failed.length)} rivers that never reached flood stage (${range(failed)}).`;
  },
  time: (F) => `Over one ${siteTitle(F.time.river).split(",")[0]} flood, NISAR's mapped area rises and falls with the gauges while a lidar-only map stays the same on every date. This was run after the fact on a river that helped build the method, so it flatters GLOWfm a little.`,
  reference: (F) => `When one gauge is hidden, the others predict its level with a median error of ${F.ref.summary.median_abs_error_m.toFixed(2)} m and the reference matches itself at ${F.ref.summary.median_agreement.toFixed(2)}, so scores near that line are about as close as it can tell.`,
  study: (F) => `The ${F.study.rivers.length} rivers we worked on in the US Southeast, with every NISAR pass we used and each river's rise and fall from June to October 2026.`,
  coverage: (F) => `NISAR passed over ${pct(F.cov.summary.covered / F.cov.summary.floods, 0)} of the ${F.cov.summary.floods} floods reported worldwide while they were still being reported, and its scenes reached NASA's catalog a median of ${F.cov.summary.latency_days.median} days after they were recorded.`,
  fringes: () => "NISAR's phase shows the water rising under the trees of a Florida swamp during Hurricane Isaias, compared with a dry-season control. This one is exploratory and wasn't scored.",
};

const CAPTIONS = {
  study: (F) => {
    const held = F.study.rivers.filter((r) => r.role === "held-out").length, tested = F.study.rivers.flatMap((r) => r.passes).filter((p) => p.tested).length;
    return `<b>a)</b> The ${F.study.rivers.length} rivers, with circle area showing how much flooding was labeled on each river's tested passes. Magenta marks the ${held} rivers with frozen one-time tests and gray the ones used only in development. <b>b)</b> Every NISAR pass we used (magenta for the ${tested} frozen test passes), every Copernicus GFM scene we audited (blue squares, ${F.study.gfm.length}) and each river's rise and fall at its USGS gauges, scaled to that river's own range as a sketch rather than a level.`;
  },
  signature: (F) => {
    const px = F.sig.bins.reduce((s, b) => s + b.n, 0), p = F.sig.pearl;
    return `<b>a)</b> The change in HH backscatter from a dry pass to the flood pass for forest pixels, grouped into 0.5 m bands of water above the forest floor and pooled over ${inWords(F.sig.pooled_from.length)} frozen test passes (${n0(px)} pixels). Each ridge is scaled to its own peak, the white ticks mark each band's median and the diamonds follow the Satilla on Oct 15. <b>b)</b> The median change against depth for all ${F.sig.passes.length} passes, with the pooled HH median in bold, its interquartile band and the pooled HV median dashed, and the side where water stands above the forest floor shaded. <b>c)</b> The same Pearl River flood seen by Sentinel-1's C-band (${fkDay(Date.parse(p.c_dates.before))} to ${fkDay(Date.parse(p.c_dates.flood))}) and NISAR's L-band (pass ${p.l_pair.split("_")[0]}, ${passDate(p.l_pair)}), where the shorter C-band wave didn't brighten. That comparison is rough, since Sentinel-1 is measured against one earlier date and NISAR against a 60-day median, and C-band can still brighten in sparse or leafless forest elsewhere.`;
  },
  maps: (F) => {
    const P = F.maps.passes, name = (p) => `${siteTitle(p.river).split(",")[0]}, ${passDate(p.pair)}`, ha = (x) => n0(x);
    const [strong, typical, failed] = ["strong", "typical", "failed"].map((k) => P.find((p) => p.kind === k));
    const blocks = [...new Set(P.map((p) => p.overview.block_m))].sort((a, b) => a - b);
    return `<b>a–c)</b> GLOWfm's frozen map against the river's answer on a strong pass (${name(strong)}, CSI ${strong.csi.toFixed(2)}), a typical one (${name(typical)}, ${typical.csi.toFixed(2)}) and a failure (${name(failed)}, ${failed.csi.toFixed(2)}). ` +
      `On the left is the whole scored reach in ${blocks.length > 1 ? `${blocks[0]}–${blocks[blocks.length - 1]}` : blocks[0]} m blocks colored by their most common class, with the ${P[0].window.km[0]} × ${P[0].window.km[1]} km window in yellow, then the radar change in that window, and on the right every scored 50 m pixel. ` +
      `Blue pixels are hits, magenta are false alarms only GLOWfm flagged, cyan are misses only the reference flooded and gray are dry in both. ` +
      `On the ${name(strong)}, hits (${ha(strong.hit_ha)} ha) far outweigh misses (${ha(strong.miss_ha)} ha) and false alarms (${ha(strong.false_alarm_ha)} ha), while on the ${name(failed)} false alarms outnumber hits about ${Math.round(failed.false_alarm_ha / failed.hit_ha)} to 1. ` +
      `Since the reference is itself a model (${ref("fig-reference")}), a miss or false alarm can be its error rather than GLOWfm's.`;
  },
  accuracy: (F, metrics) => {
    const scored = metrics.held_out.filter((r) => r.recall !== undefined && r.recall !== null);
    const right = F.ob.filter((o) => o.signal_right).length, high = F.ob.filter((o) => o.csi >= 0.6).length;
    const failed = metrics.held_out.filter((r) => r.method.startsWith("v4, median")).map((r) => r.csi);
    return `<b>a)</b> The CSI (hits divided by hits, misses and false alarms) of every frozen test against the river's answer, grouped by method version, with ${BOOT}. The dashed cyan line is the reference's agreement with itself when one gauge is hidden (${F.ref.summary.median_agreement.toFixed(2)}, ${ref("fig-reference")}), and the hollow diamonds are a lidar-only map scored on the same pixels in the latest test. Gray marks passes with under ${n0(JUDGE_HA)} ha of flooding, too little to judge, and the shaded bands are the readings each protocol fixed in advance, moderate from 0.40 and strong from 0.60. With 10 km blocks instead of 2 km, the intervals of ${inWords(F.wider.length)} of ${inWords(F.enough.length)} version-4 passes widen, most on the ${siteTitle(F.widest.river).split(",")[0]} on ${passDate(F.widest.pair)} (from ${F.widest.ci_by_block["2000"].map((v) => v.toFixed(2)).join("–")} to ${F.widest.ci_by_block["10000"].map((v) => v.toFixed(2)).join("–")}). ` +
      `<b>b)</b> Precision against recall for the ${scored.length} tests with both, with dashed curves joining points of equal CSI and the trust light shown wherever it was set beforehand. The light was right on ${right} of ${F.ob.length} judgeable passes, against ${high} for always green and ${F.ob.length - high} for always red, which is too few to prove it. On its green-light passes GLOWfm found ${range(F.greenPasses.map((q) => q.trees.recall), PCT)} of the flooding under trees at ${range(F.greenPasses.map((q) => q.trees.precision), PCT)} precision${F.sameFlood ? `, though ${inWords(F.sameFlood + 1)} of them are one flood` : ""}. ` +
      `In the first version-4 test it scored ${range(failed)} on ${inWords(failed.length)} rivers, mostly through false alarms that rain explains only in part, and passes from the same storm aren't independent tests.`;
  },
  time: (F, metrics) => {
    const t = F.time, frozen = t.frames.find((f) => f.frozen), test = metrics.held_out.find((r) => r.site === t.river);
    return `Every NISAR pass over one ${siteTitle(t.river)} flood (dotted lines). <b>a)</b> The rise in water level at ${t.gauges.length} USGS gauges (${t.gauges.map((g) => g.name.replace(/^Yellow River /, "")).join(", ")}) since each one's lowest reading, where the gauge near Milton also rises and falls daily before the flood, most likely with the tide. <b>b)</b> The flooded area from NISAR (magenta), the river's answer (cyan) and the lidar-only map (gray), which stays the same on every date. ` +
      `<b>c)</b> The current method's CSI on each pass with its 95% interval, run after the fact on a river that helped build it, so these aren't frozen tests and they flatter it. The hollow diamond is the one frozen test on this river, ${METHOD_NAME(test.method)} on ${passDate(frozen.pair)} (${test.csi.toFixed(2)}). On ${t.frames.filter((f) => f.csi === null).map((f) => passDate(f.pair)).join(" and ")} the river was far past its crest, so GLOWfm declined to map it, and the ${t.unusable.map((u) => passDate(u.pair)).join(", ")} pass had no valid radar over the reach.`;
  },
  blind: (F, metrics) => {
    const b = F.biggest, w = F.world, rows = metrics.audit.filter((r) => r.truth_wet_ha >= 100), mask = rows.map((r) => r.wet_share_in_mask), sa = metrics.satilla_audit;
    return `<b>a)</b> The flooding estimated from gauges and lidar (cyan) against what Copernicus GFM mapped on the same pixels (blue, hollow where it mapped nothing), on a log scale. The largest gap is the ${siteTitle(b.site)} on ${fmtDate(b.date)}, with ${n0(b.truth_wet_ha)} ha against ${b.gfm_on_wet_ha} ha. ` +
      `<b>b)</b> The share of floodplain that GFM's own exclusion mask leaves out, under trees and elsewhere, in the ${w.check_areas.length} areas where we have its masks (${PCT(w.check.excl_trees)} against ${PCT(w.check.excl_else)} overall). <b>c)</b> The Satilla in October 2026, with three USGS gauges against their flood level (shaded where one stood above it), NISAR's passes (magenta) and GFM's scenes (blue, hollow where a scene missed this stretch). ` +
      `Because GFM's mask covers ${pct(Math.min(...mask), 0)}–${pct(Math.max(...mask), 0)} of the estimated flooding on these passes, this is a gap it declares rather than a detection failure, and on Oct 24 it mapped ${ha(sa.gfm_on_wet_ha)} of the Satilla's ${ha(sa.estimated_ha)} ha. ` +
      `Worldwide, ${(w.totals.tree_km2 / 1e6).toFixed(1)} million of ${(w.totals.floodplain_km2 / 1e6).toFixed(1)} million km² of river floodplain (${PCT(w.totals.tree_km2 / w.totals.floodplain_km2)}) lies under trees, which describes the ground rather than how often it floods, and the ${inWords(w.check_areas.length)} areas in b) can't show how well that stand-in holds everywhere.`;
  },
  coverage: (F) => {
    const c = F.cov.summary, L = c.latency_days;
    return `<b>a)</b> For each of the ${c.floods} floods GDACS reported in the ${c.gdacs_window_days} days before ${fmtDay(c.checked_utc)}, the days from the first report to NISAR's first pass over the reported point (solid) and to that scene's arrival in NASA's catalog (dashed). ${pct(c.covered / c.floods, 0)} had a pass while the flood was still being reported, ${c.covered_by_method_kind} had a scene this method can read, and ${c.ready_during_flood} had one in the catalog in time. ` +
      `<b>b)</b> The wait from recording to the catalog for all ${c.scenes} scenes, a median of ${L.median} days, although ${pct(L.share_over_7, 0)} took more than a week (shaded) and the longest took ${L.max}. GDACS gives one point per flood, so a pass can cover that point and still miss the flooding.`;
  },
  fringes: (F) => {
    const [c, f, r] = ["control", "flood", "crest"].map((n) => F.fringes.pairs.find((p) => p.name === n)), at = "-85.99";
    const kmEast = ((-85.99 - F.fringes.bunker[0]) * 111.32 * Math.cos((F.fringes.bunker[1] * Math.PI) / 180)).toFixed(0);
    const m = (v) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2)} m`;
    const unread = (p) => { const k = p.lon.reduce((b, lon, i) => (Math.abs(lon + 85.99) < Math.abs(p.lon[b] + 85.99) ? i : b), 0); return !p.ok[k]; };
    return `<b>a)</b> NISAR interferograms over the Choctawhatchee River delta swamp in Florida during Hurricane Isaias, where color is the change in radar phase between two passes and brightness is coherence. The dry-season control (${c.dates}) shows only a smooth drift from the atmosphere, while both pairs spanning the flood show bands confined to the swamp, in the same place from two directions. ` +
      `<b>b)</b> Those phase steps added up along the dashed box and turned into water-level change (${Math.round(100 * f.m_per_cycle)} cm per cycle), set to zero at the Bunker gauge. ${kmEast} km east of Bunker it reads ${m(c.at[at])} for the control, ${m(f.at[at])} as the water rose and ${m(r.at[at])} at the crest${unread(r) ? ", carried across a stretch it couldn't read" : ""}. ` +
      `The two nearest gauges imply about +0.7 m for the rising pair, which agrees, and about +1.3 m at the crest, which the phase underestimates because only ${pct(r.coherent_columns, 0)} of columns stayed coherent. This is exploratory, made after the frozen tests and not scored.`;
  },
  reference: (F) => {
    const s = F.ref.summary;
    return `The river's answer is itself a model, built by interpolating gauge levels along the river and comparing them with lidar ground height, so we checked it by hiding each gauge in turn (${s.cases} cases) and predicting its level from the others. <b>a)</b> Predicted against measured water level, with the 1:1 line dashed. ` +
      `<b>b)</b> The error against the distance to the nearest gauge used, with a median of ${s.median_abs_error_m.toFixed(2)} m and a worst case of ${s.worst_abs_error_m.toFixed(2)} m. Only ${pct(s.share_within_margin, 0)} of predictions fell within the reference's 0.5 m margin, they ran ${s.mean_signed_error_m.toFixed(2)} m high on average, and a reference built without the hidden gauge matched the full one at ${s.median_agreement.toFixed(2)}, though real passes usually have closer gauges than this test, so these numbers are pessimistic. ` +
      `<b>c)</b> Each judged version-4 pass scored again with the reference's water surface moved by −1 to +1 m, with its own ±0.5 m margin shaded. Raising it changes the scores by at most +${F.gain.toFixed(2)}, but lowering it by 0.5 m cuts every pass, most on the ${siteTitle(F.drop.q.river).split(",")[0]} on ${passDate(F.drop.q.pair)} (${F.drop.q.csi.toFixed(2)} to ${F.at(F.drop.q, -0.5).toFixed(2)}).`;
  },
};

const NUM = {};
function numberItems() {
  document.querySelectorAll("#figures .paper-fig").forEach((f, k) => { NUM[f.id] = `Fig. ${k + 1}`; });
  document.querySelectorAll("#figures .paper-table").forEach((t, k) => { NUM[t.id] = `Table ${k + 1}`; t.querySelector(".fig-no").textContent = NUM[t.id]; });
  document.querySelectorAll("a[data-ref]").forEach((a) => { a.href = `#${a.dataset.ref}`; a.textContent = NUM[a.dataset.ref] + (a.dataset.panel || ""); });
}
const ref = (id) => `<a href="#${id}">${NUM[id]}</a>`;

async function setupCaptions(metrics, F) {
  document.querySelectorAll("figcaption[data-cap]").forEach((cap) => {
    const fig = cap.closest(".paper-fig"), no = NUM[fig.id], title = fig.dataset.title;
    const k = cap.dataset.cap;
    cap.innerHTML = `<b class="cap-lead">${no} | ${title}.</b> <span class="fig-take">${TAKE[k](F, metrics)}</span><details class="fig-more"><summary>Details</summary><p>${CAPTIONS[k](F, metrics)}</p></details>`;
  });
}

function setupPaper() {
  const btn = $("paper-btn"), figs = $("figures");
  const set = (on) => { figs.classList.toggle("paper", on); btn.setAttribute("aria-pressed", String(on)); btn.textContent = on ? "Night colors" : "Print colors"; };
  let on = false;
  try { on = localStorage.getItem("hf.paper") === "on"; } catch {  }
  set(on);
  btn.addEventListener("click", () => { on = !on; set(on); try { localStorage.setItem("hf.paper", on ? "on" : "off"); } catch {  } });
}

function setupLidar(metrics) {
  const judged = metrics.overbank.filter((r) => r.judgeable);
  const signed = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(2)}`;
  $("t-lidar").innerHTML = "<tr><th>River</th><th>NISAR pass</th><th class='num'>NISAR</th><th class='num'>Lidar map</th><th class='num'>Difference (95% interval)</th><th>Reading</th></tr>" +
    judged.map((r) => `<tr><td>${siteTitle(r.site)}</td><td>${passLabel(r)}</td><td class="num">${r.csi.toFixed(2)}</td><td class="num">${r.lidar_csi.toFixed(2)}</td><td class="num">${signed(r.lidar_difference)} (${signed(r.lidar_interval[0])} to ${signed(r.lidar_interval[1])})</td><td>${r.lidar_interval[0] > 0 ? "radar better" : r.lidar_interval[1] < 0 ? "lidar better" : "neither shown better"}</td></tr>`).join("");
  $("lidar-note").textContent = "Radar's real advantage is time, because a lidar map looks the same on every date and can't show when a flood arrives or drains.";
}

function setupElevation() {
  const signed = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(2)}`;
  figJson("figures/elevation.json").then((e) => {
    const m = e.means, r = e.readings, lost = e.rows.filter((x) => x.fabdem_minus_copernicus_ci95[1] < 0).map((x) => x.fabdem_minus_copernicus);
    $("t-elevation").innerHTML = "<tr><th>River</th><th>NISAR pass</th><th class='num'>Lidar</th><th class='num'>Treetops (Copernicus)</th><th class='num'>Bare earth (FABDEM)</th><th class='num'>Bare earth minus treetops (95% interval)</th></tr>" +
      e.rows.map((x) => `<tr><td>${siteTitle(x.site)}</td><td>${passLabel(x)}</td><td class="num">${x.nisar_with_lidar.toFixed(2)}</td><td class="num">${x.nisar_with_copernicus.toFixed(2)}</td><td class="num"><b>${x.nisar_with_fabdem.toFixed(2)}</b></td><td class="num">${signed(x.fabdem_minus_copernicus)} (${signed(x.fabdem_minus_copernicus_ci95[0])} to ${signed(x.fabdem_minus_copernicus_ci95[1])})</td></tr>`).join("") +
      `<tr class="ev-total"><td>Mean</td><td></td><td class="num">${m.nisar_with_lidar.toFixed(2)}</td><td class="num">${m.nisar_with_copernicus.toFixed(2)}</td><td class="num"><b>${m.nisar_with_fabdem.toFixed(2)}</b></td><td class="num">${signed(m.nisar_with_fabdem - m.nisar_with_copernicus)}</td></tr>`;
    $("elevation-note").textContent = `By the rule fixed beforehand, the bare-earth gain is ${r.q1.toLowerCase()}, winning clearly on ${inWords(r.q1_won)} passes and losing on ${inWords(r.q1_lost)}${lost.length ? ` by ${Math.abs(Math.min(...lost)).toFixed(2)}` : ""}. It narrowed the gap to lidar from ${(m.nisar_with_lidar - m.nisar_with_copernicus).toFixed(2)} to ${(m.nisar_with_lidar - m.nisar_with_fabdem).toFixed(2)} without simply mapping more ground, since its maps covered ${r.area_ratio_vs_lidar.toFixed(2)} times the lidar ones' area. A bare-earth height map with no radar averaged ${m.fabdem_height_map.toFixed(2)}, so radar's edge there is thin, and because all seven passes are in the US Southeast and FABDEM's tree correction may have learned from lidar like this, it hasn't been tested in the tropics.`;
  }).catch(() => { $("elevation-note").textContent = "The no-lidar numbers couldn't load."; });
}

function setupSealed() {
  fetch("data/live/sealed.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then((s) => {
    const day = (t) => fmtTime(t), c = s.combined;
    $("sealed-sub").textContent = `On ${fmtDay(s.sealed_utc)}, before NISAR acquired them, we wrote down which of its next ${s.passes.length} passes over flooding US rivers would count and what the trust light predicts for each, green for a match of 0.60 or higher and red for anything lower. Each pass runs once with the frozen method as it reaches NASA's catalog, and none is dropped.`;
    const status = (p) => ({ waiting: "Waiting", missing: "Missing", "not run": "Not run", "not judged": "Not judged", "not judgeable": "Too little flooding to judge", judged: "Judged" })[p.status] || p.status;
    $("t-sealed").innerHTML = "<tr><th>River</th><th>Predicted pass</th><th>Status</th><th>Trust light</th><th class='num'>Match</th><th>Light right?</th></tr>" +
      s.passes.map((p) => `<tr><td>${p.name}, ${p.state}</td><td>${day(p.predicted_utc)}</td><td title="${(p.reason || "").replace(/"/g, "&quot;")}">${status(p)}</td><td>${p.light || "—"}</td>` +
        `<td class="num">${p.csi == null ? "—" : p.csi.toFixed(2)}</td><td>${p.hit == null ? "—" : p.hit ? "Yes" : "No"}</td></tr>`).join("");
    $("sealed-note").textContent = `Checked ${fmtTime(s.checked_utc)}, with ${Object.entries(s.counts).filter(([, n]) => n).map(([k, n]) => `${n} ${k}`).join(", ")}. Together with the earlier test's ${s.overbank_judgeable} judgeable passes, the light has been right on ${c.hits} of ${c.judgeable}, which is ${c.verdict === "too few" ? "still too few to judge, since at least five are needed" : c.verdict}. The rules are in research/SEALED_TEST_PROTOCOL.md.`;
    const waiting = s.passes.every((p) => p.status === "waiting");
    $("t-sealed").closest(".table-wrap").hidden = waiting;
    if (waiting) $("sealed-sub").textContent = `On ${fmtDay(s.sealed_utc)}, before NISAR acquired them, we wrote down which of its next ${s.passes.length} passes over flooding US rivers will count and what the trust light predicts for each, green for a match of 0.60 or higher and red for anything lower. None has reached NASA's catalog yet, and the first is due ${fmtDay(Math.min(...s.passes.map((p) => Date.parse(p.predicted_utc))))}, after which each will run once with the frozen method and none will be dropped.`;
    $("sealed").hidden = false;
  }).catch(() => {});
}

numberItems();
function openTo(hash) {
  const el = hash && hash.length > 1 ? document.getElementById(hash.slice(1)) : null;
  for (let d = el && el.closest("details"); d; d = d.parentElement.closest("details")) d.open = true;
  return el;
}
document.querySelectorAll("details.ev-fold").forEach((d) => d.addEventListener("toggle", () => { if (d.open) d.querySelectorAll(".fig-mount[data-fig]").forEach((m) => drawFigure(m)); }));
const drawOpen = () => Promise.all([...document.querySelectorAll(".fig-mount[data-fig]")].filter((m) => !m.closest("details:not([open])")).map(drawFigure));
function jumpTo(hash) {
  const el = openTo(hash);
  if (!el) return false;
  el.scrollIntoView();
  drawOpen().then(() => setTimeout(() => el.scrollIntoView(), 100));
  return true;
}
document.addEventListener("click", (e) => {
  const a = e.target.closest('a[href^="#"]'), hash = a && a.getAttribute("href");
  if (hash && hash.length > 1 && jumpTo(hash)) { e.preventDefault(); history.pushState(null, "", hash); }
});
addEventListener("hashchange", () => jumpTo(location.hash));
const openAll = () => document.querySelectorAll("main details").forEach((d) => { d.open = true; });
openTo(location.hash);
setupPaper();
setupSealed();
mountFigures();
$("pdf-btn").addEventListener("click", () => { openAll(); drawAllFigures().then(() => setTimeout(() => print(), 300)); });
addEventListener("beforeprint", () => { openAll(); drawAllFigures(); });
loadData().then(async ([, metrics]) => {
  setupLidar(metrics); setupElevation();
  const F = await resultFacts(metrics);
  setupLimits(metrics, F);
  setupAbstract(metrics, F);
  setupCaptions(metrics, F);
  if (location.hash) jumpTo(location.hash);
});
