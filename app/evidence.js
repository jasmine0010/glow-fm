// GLOWfm results page: a computed abstract, the limits, Fig. 1–11 (figures.js) with captions built from the same
// data, and the tables (every fair test, radar against lidar, without lidar, the flood-map gap). Every number here is read from data.

const SHOWN = 8;
const METHOD_NAME = (m) => m.split(",")[0].replace("v", "Method ");
const passLabel = (r) => `${r.pair.split("_")[0]}, ${passDate(r.pair)}`;
const n0 = (x) => Math.round(x).toLocaleString("en-US");
const range = (a, f = (x) => x.toFixed(2)) => `${f(Math.min(...a))}–${f(Math.max(...a))}`;
const dbRange = (a) => { const sg = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(1)}`; return `${sg(Math.min(...a))} to ${sg(Math.max(...a))} dB`; };
const BOOT = "95% intervals from a block bootstrap (2 km blocks along the river, 2,000 resamples), as in the frozen tests";

function setupLimits(metrics, F) {
  const [lo, hi] = scoreRange(metrics), judged = metrics.overbank.filter((r) => r.judgeable), h = metrics.hidden_gauge;
  const failedN = metrics.held_out.filter((r) => r.method.startsWith("v4, median")).length;
  // Each finding leads with its number, then the same wording the page has always used.
  const cards = [
    [`${lo.toFixed(2)}–${hi.toFixed(2)}`, "Results vary.", `Fair-test scores ran from ${lo.toFixed(2)} to ${hi.toFixed(2)}, and on ${inWords(failedN)} rivers GLOWfm failed.`],
    [`${mean(judged.map((r) => r.lidar_csi)).toFixed(2)} vs ${mean(judged.map((r) => r.csi)).toFixed(2)}`, "Lidar did about as well.", `In the latest test, a lidar map averaged ${mean(judged.map((r) => r.lidar_csi)).toFixed(2)} against NISAR's ${mean(judged.map((r) => r.csi)).toFixed(2)}. Radar's clear extra is showing what's flooded on a given date.`],
    [`${h.median_abs_error_m.toFixed(2)} m`, "The reference is a model, not a sighting of water.", `It compares gauge levels with lidar ground height. With one gauge hidden, the others predicted its level with a median error of ${h.median_abs_error_m.toFixed(2)} m across gaps of ${Math.round(h.gap_km[0])}–${Math.round(h.gap_km[1])} km, and the reference built without it matched the full one at only ${F.ref.summary.median_agreement.toFixed(2)}. Scores near that are about as close as this reference can tell.`],
    ["US only", "Fair tests are all on US rivers.", `One unvalidated try in Cambodia didn't transfer, with ${inWords(metrics.tonle_sap.predictions - metrics.tonle_sap.held)} of ${inWords(metrics.tonle_sap.predictions)} predictions failing, and this isn't an operational product.`],
  ];
  $("limits").innerHTML = cards.map(([num, title, text]) => `<div class="stat-card"><span class="stat-num">${num}</span><b class="ev-title">${title}</b><span class="stat-label">${text}</span></div>`).join("");
}

// ---------- the numbers the abstract and captions share ----------
async function resultFacts(metrics) {
  const [sig, sep, strata, study, time, world, ref, elev, cov, fringes, rc, maps] = await Promise.all(["signature", "separability", "strata", "study", "time", "world", "reference", "elevation", "coverage", "fringes", "reference_checks", "maps"].map((f) => figJson(`figures/${f}.json`)));
  const dry = sig.bins.filter((b) => b.hi <= 0).map((b) => b.hh_q[1]);
  const wet = sig.bins.filter((b) => b.lo >= 0 && b.n >= 1000).reduce((a, b) => (b.hh_q[1] > a.hh_q[1] ? b : a));
  const [green, all] = strata.groups, tree = (g) => g.by_landcover.find((c) => c.label === "tree cover");
  const audit = metrics.audit.filter((r) => r.truth_wet_ha >= 100), biggest = audit.reduce((a, b) => (b.truth_wet_ha > a.truth_wet_ha ? b : a));
  const peak = world.lat[world.tree_km2.indexOf(Math.max(...world.tree_km2))];
  // Tests with enough flooding to judge, and the river floods they come from (each river here had one flood).
  const judgedTests = metrics.held_out.filter((r) => r.csi !== null && r.csi !== undefined && (r.confirmed_ha ?? r.estimated_ha) >= JUDGE_HA);
  // Post hoc (scripts/posthoc_reference_checks.py): per-pass numbers under trees, the water-surface shift and wider blocks.
  const greenPasses = rc.passes.filter((q) => q.trust === "green");
  const at = (q, m) => q.shift.find((x) => x.shift_m === m).csi;
  const drop = rc.passes.map((q) => ({ q, d: q.csi - at(q, -0.5) })).reduce((a, b) => (b.d > a.d ? b : a));
  const gain = Math.max(...rc.passes.map((q) => at(q, 0.5) - q.csi));
  // A bootstrap needs enough blocks to resample: passes with fewer than five 10 km blocks are set aside here.
  const width = (ci) => ci[1] - ci[0], enough = rc.passes.filter((q) => q.n_blocks["10000"] >= 5), few = rc.passes.filter((q) => q.n_blocks["10000"] < 5);
  const wider = enough.filter((q) => width(q.ci_by_block["10000"]) > width(q.ci_by_block["2000"]) + 0.02);
  const widest = enough.reduce((a, b) => (width(b.ci_by_block["10000"]) - width(b.ci_by_block["2000"]) > width(a.ci_by_block["10000"]) - width(a.ci_by_block["2000"]) ? b : a));
  const sameFlood = greenPasses.length - new Set(greenPasses.map((q) => q.river)).size;
  return { sig, sep, strata, study, time, world, ref, elev, cov, fringes, rc, maps, dry, wet, green, all, treeGreen: tree(green), treeAll: tree(all), audit, biggest, peak,
    judged: judgedPasses(metrics), rivers: new Set(metrics.held_out.map((r) => r.site)).size, ob: metrics.overbank.filter((o) => o.judgeable),
    judgedTests, judgedRivers: new Set(judgedTests.map((r) => r.site)).size, greenPasses, sameFlood, at, drop, gain, enough, few, wider, widest };
}

function setupAbstract(metrics, F) {
  const [lo, hi] = scoreRange(metrics), px = F.sig.bins.reduce((s, b) => s + b.n, 0);
  $("abstract-text").innerHTML = `Floodwater under a forest canopy is hidden from optical satellites and hard for the C-band radar behind today's global flood maps; the Copernicus Global Flood Monitoring (GFM) map leaves it out by design. We tested whether NISAR's L-band radar can map it. Flooded forest brightens. Across ${n0(px)} forest pixels from ${inWords(F.sig.pooled_from.length)} frozen test passes, the median HH change was ${dbRange(F.dry)} where the water stayed below ground and ${figDb(F.wet.hh_q[1])} under ${F.wet.lo.toFixed(1)}–${F.wet.hi.toFixed(1)} m of water (<a href="#fig2">Fig. 2</a>). Each method was frozen before a flood's data was opened, then run once, ${metrics.held_out.length} tests on ${F.rivers} rivers, of which ${F.judgedTests.length}, on ${F.judgedRivers} rivers, had enough flooding to judge. Their CSI ran from ${lo.toFixed(2)} to ${hi.toFixed(2)} (<a href="#fig5">Fig. 5</a>; maps of three in <a href="#fig4">Fig. 4</a>). On the ${inWords(F.greenPasses.length)} passes the trust light marked green${F.sameFlood ? `, ${inWords(F.sameFlood + 1)} of them the same ${siteTitle(F.greenPasses.find((q, k, a) => a.findIndex((x) => x.river === q.river) !== k).river).split(",")[0]} flood` : ""}, GLOWfm found ${range(F.greenPasses.map((q) => q.trees.recall), PCT)} of the flooding under trees, with ${range(F.greenPasses.map((q) => q.trees.precision), PCT)} precision (<a href="#fig6">Fig. 6</a>). These scores are against a modelled reference that matches itself at only ${F.ref.summary.median_agreement.toFixed(2)} when one gauge is hidden, and lowering its water surface by 0.5 m cuts the ${siteTitle(F.drop.q.river).split(",")[0]}'s ${passDate(F.drop.q.pair)} score from ${F.drop.q.csi.toFixed(2)} to ${F.at(F.drop.q, -0.5).toFixed(2)} (<a href="#fig10">Fig. 10</a>). On ${F.audit.length} audited passes over ${inWords(new Set(F.audit.map((r) => r.site)).size)} Gulf Coast rivers, GFM mapped at most ${Math.max(...F.audit.map((r) => r.gfm_on_wet_ha))} ha where gauges and lidar estimated ${range(F.audit.map((r) => r.truth_wet_ha), n0)} ha (<a href="#fig8">Fig. 8</a>). Worldwide, ${(F.world.totals.tree_km2 / 1e6).toFixed(1)} million km² of river floodplain lies under trees (<a href="#fig9">Fig. 9</a>). A lidar-only map scored about as well; radar's clear extra is the date (<a href="#fig7">Fig. 7</a>, on a river that helped build the method). Without lidar, on the ${inWords(F.elev.rows.length)} passes judged in that test, NISAR averaged ${F.elev.means.nisar_with_copernicus.toFixed(2)} with global elevation data that includes treetops and ${F.elev.means.nisar_with_fabdem.toFixed(2)} with a bare-earth model (FABDEM), against ${F.elev.means.nisar_with_lidar.toFixed(2)} with lidar (<a href="#no-lidar">Table 3</a>). All tests are on US rivers and few, and this is not an operational product.`;
}

// ---------- figure captions ----------
const CAPTIONS = {
  study: (F) => {
    const held = F.study.rivers.filter((r) => r.role === "held-out").length, tested = F.study.rivers.flatMap((r) => r.passes).filter((p) => p.tested).length;
    return `<b>a</b>, The ${F.study.rivers.length} rivers, US Southeast. Circle area grows with the flooding labelled on each river's tested passes. Magenta marks the ${held} rivers with frozen one-time tests, grey those used only in development. <b>b</b>, Every NISAR pass used (ticks, magenta for the ${tested} frozen test passes), every Copernicus GFM scene audited (blue square, ${F.study.gfm.length}) and each river's rise and fall at its USGS gauges (cyan, scaled to that river's own range, a sketch rather than a level).`;
  },
  signature: (F) => {
    const px = F.sig.bins.reduce((s, b) => s + b.n, 0), p = F.sig.pearl;
    return `<b>a</b>, Change in HH backscatter (γ⁰) from a dry pass to the flood pass for forest pixels, in 0.5 m bands of water above the forest floor (negative where the water is below ground). Pooled over ${F.sig.pooled_from.length} frozen test passes (${n0(px)} pixels); each ridge is scaled to its own peak. Ticks mark each band's median, and the diamond the Satilla River on Oct 15. The median is ${dbRange(F.dry)} with the water below ground and peaks at ${figDb(F.wet.hh_q[1])} under ${F.wet.lo.toFixed(1)}–${F.wet.hi.toFixed(1)} m, the double bounce of L-band waves between water and trunks. <b>b</b>, Median change against depth for all ${F.sig.passes.length} passes (thin lines, magenta for frozen tests), with the pooled HH median (bold), its interquartile band and the pooled HV median (dashed). <b>c</b>, The same Pearl River flood seen by Sentinel-1 C-band (VV, ${fkDay(Date.parse(p.c_dates.before))} to ${fkDay(Date.parse(p.c_dates.flood))}) and NISAR L-band (HH, pass ${p.l_pair.split("_")[0]}, ${passDate(p.l_pair)}). Here the shorter C-band wave didn't brighten, but the comparison is rough. Sentinel-1 is measured against a single earlier date and NISAR against a 60-day median, two days apart, and C-band sits about 0.7 dB lower even on dry ground. Elsewhere C-band can brighten in sparse or leafless forest. Backscatter is terrain-flattened γ⁰ for both. Descriptive.`;
  },
  separability: (F) => {
    const s = F.sep.passes;
    return `<b>a</b>, GLOWfm's own signal (HH, or HH minus HV where the frozen method chose it, smoothed as during the test) for pixels the river's answer calls flooded (cyan) and dry (grey), on the scored pixels of one pass; pick the pass above. Magenta marks the cut-off the frozen method set for itself on that pass. <b>b</b>, ROC curves for the ${s.length} judged frozen passes, showing the share of flooded pixels found against the share of dry pixels flagged as a cut-off on the smoothed HH change moves, on forest, wetland and other cover within 6 m of the river. Area under the curve ${range(s.map((p) => p.auc))}; colour and shape show the trust light. The three areas also in the rainfall analysis match its stored values. Descriptive.`;
  },
  maps: (F) => {
    const P = F.maps.passes, name = (p) => `${siteTitle(p.river).split(",")[0]}, ${passDate(p.pair)}`, ha = (x) => n0(x);
    const [strong, typical, failed] = ["strong", "typical", "failed"].map((k) => P.find((p) => p.kind === k));
    const blocks = [...new Set(P.map((p) => p.overview.block_m))].sort((a, b) => a - b);
    return `<b>a–c</b>, GLOWfm's frozen map against the river's answer on a strong pass (${name(strong)}, CSI ${strong.csi.toFixed(2)}), a typical one (${name(typical)}, ${typical.csi.toFixed(2)}) and a failure (${name(failed)}, ${failed.csi.toFixed(2)}). ` +
      `Left, the whole scored reach, each ${blocks.length > 1 ? `${blocks[0]}–${blocks[blocks.length - 1]}` : blocks[0]} m block coloured by its commonest class, with the ${P[0].window.km[0]} × ${P[0].window.km[1]} km window in yellow. Middle, the radar change in that window, smoothed HH (γ⁰) from the dry baseline to the flood pass. Right, every scored 50 m pixel in the window. ` +
      `Blue pixels are hits, flooded in both; magenta are false alarms, flagged by GLOWfm only; cyan are misses, flooded in the reference only; grey are dry in both. Ground the reference didn't score is left clear. ` +
      `On the ${name(strong)}, hits (${ha(strong.hit_ha)} ha) far outweigh misses (${ha(strong.miss_ha)} ha) and false alarms (${ha(strong.false_alarm_ha)} ha). On the ${name(failed)}, false alarms (${ha(failed.false_alarm_ha)} ha) outnumber hits (${ha(failed.hit_ha)} ha) about ${Math.round(failed.false_alarm_ha / failed.hit_ha)} to 1. ` +
      `The reference is itself a model (Fig. 10), so a miss or false alarm can be its error rather than GLOWfm's. Drawn from the frozen runs' saved layers by scripts/posthoc_result_maps.py; nothing is scored again. Descriptive.`;
  },
  accuracy: (F, metrics) => {
    const scored = metrics.held_out.filter((r) => r.recall !== undefined && r.recall !== null);
    return `<b>a</b>, Critical success index (CSI, hits / (hits + misses + false alarms)) against the river's answer for all ${metrics.held_out.length} frozen tests (${F.judgedTests.length} judged), grouped by method version, with ${BOOT}. The dashed cyan line is the reference's agreement with itself when one gauge is hidden (median ${F.ref.summary.median_agreement.toFixed(2)}, Fig. 10); scores near it are about as close as this reference can tell. Post hoc, with 10 km blocks instead of 2 km, the intervals of ${inWords(F.wider.length)} of ${inWords(F.enough.length)} version-4 passes widen (${siteTitle(F.widest.river).split(",")[0]}, ${passDate(F.widest.pair)}, from ${F.widest.ci_by_block["2000"].map((v) => v.toFixed(2)).join("–")} to ${F.widest.ci_by_block["10000"].map((v) => v.toFixed(2)).join("–")})${F.few.length ? `; the ${F.few.map((q) => `${siteTitle(q.river).split(",")[0]}, ${passDate(q.pair)},`).join(" and ")} has too few 10 km blocks to resample` : ""}. Hollow diamonds are a lidar-only map (ground under 2 m above the river) scored on the same pixels in the latest test. Grey marks under ${n0(JUDGE_HA)} ha of flooding, too little to judge, and n/a means the estimate had no flooding to score. <b>b</b>, Precision against recall for the ${scored.length} tests with both; dashed curves join points of equal CSI. Circles and triangles show the trust light (green, red), set before each of the latest tests; squares are earlier tests, from before the trust light existed.`;
  },
  strata: (F) => {
    const right = F.ob.filter((o) => o.signal_right).length, high = F.ob.filter((o) => o.csi >= 0.6).length;
    return `Pooled pixels of the ${F.green.passes.length} passes the trust light marked green (green) and all ${F.all.passes.length} judged frozen passes (grey), with ${BOOT}. Depth and height both come from the reference itself, so these panels describe agreement with it, not water seen independently. <b>a</b>, Recall by depth of water above the forest floor (every labelled pixel deeper than 0.5 m is flooded, so precision there is 1). <b>b</b>, Recall (circles) and precision (squares) by ground height above the river. Precision falls where the ground is 0–2 m above the river, which is also where the reference's own water level is least certain (Fig. 10). <b>c</b>, By land cover (ESA WorldCover 2021). Pooled pixels favour the largest floods${F.sameFlood ? `, and ${inWords(F.sameFlood + 1)} of the green-light passes are one flood` : ""}; pass by pass, the green-light passes found ${range(F.greenPasses.map((q) => q.trees.recall), PCT)} of the flooding under trees at ${range(F.greenPasses.map((q) => q.trees.precision), PCT)} precision. Over all passes, precision falls to ${PCT(F.treeAll.precision)} because the red-light passes carry most false alarms. For the first version-4 test, those red lights were derived afterwards from each run's own check. <b>d</b>, The trust light against the outcome on the ${F.ob.length} judgeable new passes. The rule, fixed before the test, counts green as right when CSI reaches 0.6. It was right on ${right} of ${F.ob.length}; always green would have been right on ${high} and always red on ${F.ob.length - high}. Too few passes to prove it. Descriptive.`;
  },
  time: (F, metrics) => {
    const t = F.time, frozen = t.frames.find((f) => f.frozen), test = metrics.held_out.find((r) => r.site === t.river);
    return `${siteTitle(t.river)}, every NISAR pass of one flood (dotted lines). <b>a</b>, Water level at ${t.gauges.length} USGS gauges (${t.gauges.map((g) => g.name.replace(/^Yellow River /, "")).join(", ")}), change since each gauge's lowest reading in the window, provisional data. <b>b</b>, Flooded area from NISAR (magenta), from the river's answer (cyan) and from the lidar-only map (grey, the same on every date). <b>c</b>, CSI of the current method on each pass with its 95% interval (magenta). These were run after the fact, and the Yellow River helped build the current method, so they are not frozen tests and flatter it. The gauge near Milton rises and falls about once a day before the flood, most likely with the tide, and enters the reference as read. The hollow diamond is the one frozen test on this river, an earlier method (${METHOD_NAME(test.method)}) on ${passDate(frozen.pair)}, ${test.csi.toFixed(2)}. On ${t.frames.filter((f) => f.csi === null).map((f) => passDate(f.pair)).join(" and ")} the river was far past its crest at every gauge, so GLOWfm declined to map it; the ${t.unusable.map((u) => passDate(u.pair)).join(", ")} pass had no valid radar over the reach.`;
  },
  blind: (F) => {
    const b = F.biggest, w = F.world;
    return `<b>a</b>, Flooding estimated from gauges and lidar (cyan) against the area Copernicus GFM mapped on the same pixels (blue squares, hollow where it mapped none), for every audited flood with estimated flooding, log scale. The largest is the ${siteTitle(b.site)} on ${fmtDate(b.date)}, with ${n0(b.truth_wet_ha)} ha against ${b.gfm_on_wet_ha} ha. <b>b</b>, Share of floodplain that GFM's own exclusion mask leaves out, under trees against elsewhere, in the ${w.check_areas.length} areas where we have its masks (thin lines) and all together (bold, ${PCT(w.check.excl_trees)} against ${PCT(w.check.excl_else)}). <b>c</b>, The Satilla River in October 2026, with three USGS gauges against their flood level (dashed), NISAR passes (magenta) and GFM scenes (blue, hollow where the scene didn't reach this stretch). River levels are provisional.`;
  },
  world: (F) => {
    const w = F.world, n = w.countries.length;
    return `From the blind-spot atlas, with river floodplain from the CEMS GloFAS flood-hazard maps, tree cover from ESA WorldCover 2021. <b>a</b>, Floodplain per 1° of latitude (left, grey) and the part under trees (right, green). ${(w.totals.tree_km2 / 1e6).toFixed(2)} million of ${(w.totals.floodplain_km2 / 1e6).toFixed(1)} million km² (${PCT(w.totals.tree_km2 / w.totals.floodplain_km2)}) is under trees, most of it near the equator, peaking at ${F.peak >= 0 ? `${F.peak}–${F.peak + 1}°N` : `${-F.peak - 1}–${-F.peak}°S`}. <b>b</b>, The ${n} countries with at least 1,000 km² of floodplain, their area (log scale) against the share under trees. Circle area grows with the number of towns of 5,000+ people that meet the atlas's high-risk rule. This describes ground, not how often it floods or who is at risk.`;
  },
  coverage: (F) => {
    const c = F.cov.summary, L = c.latency_days;
    return `<b>a</b>, For each of the ${c.floods} floods GDACS reported worldwide in the ${c.gdacs_window_days} days before ${fmtDay(c.checked_utc)}, the days from the first report to NISAR's first pass over the reported point (solid) and to that scene's arrival in NASA's CMR catalog (dashed), as a share of all floods; the plateau is the ${pct(c.covered / c.floods, 0)} that had a pass while GDACS still reported them. ${c.covered_by_method_kind} had a scene of the kind this method reads (40 MHz, HH and HV), and ${c.ready_during_flood} had a scene in the catalog before GDACS's last report. <b>b</b>, Days from recording to the catalog for all ${c.scenes} scenes, a median of ${L.median} (middle half ${L.p25}–${L.p75}), and ${pct(L.share_over_7, 0)} took more than a week, up to ${L.max}. One reported point per flood, so a pass can cover the point but miss the flooding; GDACS's dates are its reporting window, not a measured flood. Descriptive.`;
  },
  fringes: (F) => {
    const [c, f, r] = ["control", "flood", "crest"].map((n) => F.fringes.pairs.find((p) => p.name === n)), at = "-85.99";
    const kmEast = ((-85.99 - F.fringes.bunker[0]) * 111.32 * Math.cos((F.fringes.bunker[1] * Math.PI) / 180)).toFixed(0);
    const m = (v) => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(2)} m`;
    const unread = (p) => { const k = p.lon.reduce((b, lon, i) => (Math.abs(lon + 85.99) < Math.abs(p.lon[b] + 85.99) ? i : b), 0); return !p.ok[k]; };
    return `<b>a</b>, NISAR wrapped interferograms (GUNW, 20 m, shown at 40 m) over the Choctawhatchee River delta swamp, Florida, during Hurricane Isaias. Colour is the change in radar phase between the two passes; brightness is coherence, so dark ground changed too much to read. ` +
      `The dry-season control (${c.dates}) shows only a smooth drift across the whole scene, from the atmosphere. Both pairs spanning the flood show bands confined to the swamp, in the same place from two directions (${f.track}, ${f.direction}; ${r.track}, ${r.direction}). ` +
      `<b>b</b>, Phase steps added up along the dashed box over pixels with coherence above 0.45, converted to vertical change (${Math.round(100 * f.m_per_cycle)} cm per cycle at ${f.incidence_deg}° incidence) and set to zero at the Bunker gauge; gaps are stretches without enough coherent pixels. ` +
      `At ${kmEast} km east of Bunker it reads ${m(c.at[at])} (control), ${m(f.at[at])} (rising) and ${m(r.at[at])} (crest${unread(r) ? ", carried across a stretch it couldn't read" : ""}). ` +
      `<b>Exploratory, made after the frozen tests, and not scored.</b> The Bunker and Bruce gauges, about 19 km apart, imply roughly +0.7 m here for the rising pair, which agrees, and about +1.3 m at the crest, which the phase underestimates, since only ${pct(r.coherent_columns, 0)} of columns were coherent. ` +
      `That expectation assumes a straight-line rise between the two gauges; no gauge sits inside the swamp, and the sign convention is unverified. Upstream, where the flood came and went within 12 days, the floodplain lost coherence and couldn't be read. The gauge readings are in research/FEASIBILITY.md.`;
  },
  reference: (F) => {
    const s = F.ref.summary;
    return `The river's answer is itself a model, built from water levels at river gauges, interpolated along the river and compared with lidar ground height. To check it, each of ${s.cases} cases hides one gauge and predicts its level from the others. <b>a</b>, Predicted against measured water level (m, NAVD88), with the dashed line at 1:1. <b>b</b>, Error against the distance to the nearest gauge used. Median absolute error ${s.median_abs_error_m.toFixed(2)} m; worst ${s.worst_abs_error_m.toFixed(2)} m. Only ${pct(s.share_within_margin, 0)} of predictions fell within the reference's 0.5 m margin, and they ran ${s.mean_signed_error_m.toFixed(2)} m high on average. The reference built without the hidden gauge matched the full one at a median CSI of ${s.median_agreement.toFixed(2)}. On real passes, neighbouring gauges are usually closer than in this test, where one is removed, so these are pessimistic. <b>c</b>, Post hoc: each judged version-4 pass scored again with the reference's whole water surface moved by −1 to +1 m; ground the reference left out for other reasons stays out. Raising it changes the scores by at most +${F.gain.toFixed(2)}, but lowering it by 0.5 m cuts every pass, the ${siteTitle(F.drop.q.river).split(",")[0]} on ${passDate(F.drop.q.pair)} most (${F.drop.q.csi.toFixed(2)} to ${F.at(F.drop.q, -0.5).toFixed(2)}). Built by scripts/posthoc_reference_checks.py; no frozen number changes. Descriptive.`;
  },
};

async function setupCaptions(metrics, F) {
  document.querySelectorAll("figcaption[data-cap]").forEach((cap) => {
    const fig = cap.closest(".paper-fig"), no = `Fig. ${fig.id.slice(3)}`, title = fig.dataset.title;
    cap.innerHTML = `<b class="cap-lead">${no} | ${title}.</b> ${CAPTIONS[cap.dataset.cap](F, metrics)}`;
  });
}

// Print colours: the figures switch to a white page, for downloads, slides and printing. Remembered in this browser only.
function setupPaper() {
  const btn = $("paper-btn"), figs = $("figures");
  const set = (on) => { figs.classList.toggle("paper", on); btn.setAttribute("aria-pressed", String(on)); btn.textContent = on ? "Night colours" : "Print colours"; };
  let on = false;
  try { on = localStorage.getItem("hf.paper") === "on"; } catch { /* private mode */ }
  set(on);
  btn.addEventListener("click", () => { on = !on; set(on); try { localStorage.setItem("hf.paper", on ? "on" : "off"); } catch { /* not remembered */ } });
}

function setupTests(metrics) {
  const judged = new Set(judgedPasses(metrics));
  $("t-tests").innerHTML = "<tr><th>River</th><th>NISAR pass</th><th>Method</th><th class=\"num\">Score (95% interval)</th></tr>" +
    metrics.held_out.map((r, k) => `<tr${k >= SHOWN ? " class=\"ev-extra\" hidden" : ""}><td>${siteTitle(r.site)}</td><td>${passLabel(r)}</td><td>${METHOD_NAME(r.method)}</td><td class="num">${judged.has(r) ? `${r.csi.toFixed(2)} (${r.ci95[0].toFixed(2)}–${r.ci95[1].toFixed(2)})` : "too little estimated flooding to judge"}</td></tr>`).join("");
  // Long tables open at their first rows; the rest is one click away.
  const extra = metrics.held_out.length - SHOWN;
  if (extra > 0) {
    const more = $("tests-more");
    more.hidden = false;
    more.textContent = `Show all ${metrics.held_out.length} tests`;
    more.addEventListener("click", () => {
      const open = more.dataset.open !== "1";
      document.querySelectorAll("#t-tests .ev-extra").forEach((tr) => { tr.hidden = !open; });
      more.dataset.open = open ? "1" : "";
      more.textContent = open ? `Show the first ${SHOWN}` : `Show all ${metrics.held_out.length} tests`;
    });
  }
  const failed = metrics.held_out.filter((r) => r.method.startsWith("v4, median")).map((r) => r.csi);
  $("tests-note").textContent = `On ${inWords(failed.length)} rivers GLOWfm scored ${Math.min(...failed).toFixed(2)}–${Math.max(...failed).toFixed(2)} and mapped mostly false alarms. Rain explains part of that, but not the Pee Dee or lower Sabine. Passes on one river and storm aren't independent.`;
}

function setupLidar(metrics) {
  const judged = metrics.overbank.filter((r) => r.judgeable);
  const signed = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(2)}`;
  $("t-lidar").innerHTML = "<tr><th>River</th><th>NISAR pass</th><th class='num'>NISAR</th><th class='num'>Lidar map</th><th class='num'>Difference (95% interval)</th><th>Reading</th></tr>" +
    judged.map((r) => `<tr><td>${siteTitle(r.site)}</td><td>${passLabel(r)}</td><td class="num">${r.csi.toFixed(2)}</td><td class="num">${r.lidar_csi.toFixed(2)}</td><td class="num">${signed(r.lidar_difference)} (${signed(r.lidar_interval[0])} to ${signed(r.lidar_interval[1])})</td><td>${r.lidar_interval[0] > 0 ? "radar better" : r.lidar_interval[1] < 0 ? "lidar better" : "neither shown better"}</td></tr>`).join("");
  $("lidar-note").textContent = "A lidar map looks the same on every date, so it can't show when a flood arrives or drains. Radar can, on the passes where it works.";
}

function setupElevation() {
  const signed = (x) => `${x >= 0 ? "+" : "−"}${Math.abs(x).toFixed(2)}`;   // keeps the sign of tiny values: −0.00 is a loss
  figJson("figures/elevation.json").then((e) => {
    const m = e.means, r = e.readings, lost = e.rows.filter((x) => x.fabdem_minus_copernicus_ci95[1] < 0).map((x) => x.fabdem_minus_copernicus);
    $("t-elevation").innerHTML = "<tr><th>River</th><th>NISAR pass</th><th class='num'>Lidar</th><th class='num'>Treetops (Copernicus)</th><th class='num'>Bare earth (FABDEM)</th><th class='num'>Bare earth minus treetops (95% interval)</th></tr>" +
      e.rows.map((x) => `<tr><td>${siteTitle(x.site)}</td><td>${passLabel(x)}</td><td class="num">${x.nisar_with_lidar.toFixed(2)}</td><td class="num">${x.nisar_with_copernicus.toFixed(2)}</td><td class="num"><b>${x.nisar_with_fabdem.toFixed(2)}</b></td><td class="num">${signed(x.fabdem_minus_copernicus)} (${signed(x.fabdem_minus_copernicus_ci95[0])} to ${signed(x.fabdem_minus_copernicus_ci95[1])})</td></tr>`).join("") +
      `<tr class="ev-total"><td>Mean</td><td></td><td class="num">${m.nisar_with_lidar.toFixed(2)}</td><td class="num">${m.nisar_with_copernicus.toFixed(2)}</td><td class="num"><b>${m.nisar_with_fabdem.toFixed(2)}</b></td><td class="num">${signed(m.nisar_with_fabdem - m.nisar_with_copernicus)}</td></tr>`;
    $("elevation-note").textContent = `Frozen and run once. By the rule fixed beforehand, the bare-earth gain is ${r.q1.toLowerCase()}. It won clearly on ${inWords(r.q1_won)} passes and lost on ${inWords(r.q1_lost)}${lost.length ? `, by ${Math.abs(Math.min(...lost)).toFixed(2)}` : ""}. The gap to lidar shrank from ${(m.nisar_with_lidar - m.nisar_with_copernicus).toFixed(2)} to ${(m.nisar_with_lidar - m.nisar_with_fabdem).toFixed(2)}, and the gain didn't come from mapping more ground; the bare-earth maps covered ${r.area_ratio_vs_lidar.toFixed(2)} times the lidar ones' area. A bare-earth height map with no radar averaged ${m.fabdem_height_map.toFixed(2)}, or ${m.best_limit_csi.toFixed(2)} if its height cut-off were picked for each pass using the answer, so radar's edge over it is thin. All seven passes are in the US Southeast, and FABDEM's tree correction may have learned from lidar like this; it isn't tested in the tropics.`;
  }).catch(() => { $("elevation-note").textContent = "The no-lidar numbers couldn't load."; });
}

function setupGap(metrics) {
  const rows = metrics.audit.filter((r) => r.truth_wet_ha >= 100), areas = rows.map((r) => r.truth_wet_ha), mask = rows.map((r) => r.wet_share_in_mask), a = metrics.satilla_audit;
  $("gap-audit").textContent = `On ${rows.length} audited passes over ${inWords(new Set(rows.map((r) => r.site)).size)} Gulf Coast rivers, gauges and lidar estimated ${ha(Math.min(...areas))}–${ha(Math.max(...areas))} ha of flooding, and GFM mapped at most ${Math.max(...rows.map((r) => r.gfm_on_wet_ha))} ha. GFM's mask covers ${pct(Math.min(...mask), 0)}–${pct(Math.max(...mask), 0)} of that flooding, so this is a declared gap and not a detection failure. On the Satilla, GFM mapped ${ha(a.gfm_on_wet_ha)} of ${ha(a.estimated_ha)} ha on Oct 24, in a check run after the one-time test.`;
  fetch("data/atlas/summary.json").then((r) => r.json()).then((s) => {
    const c = s.check;
    $("t-blind").innerHTML = "<tr><th>Area</th><th class='num'>GFM excludes, under trees</th><th class='num'>GFM excludes, elsewhere</th></tr>" +
      c.areas.map((x) => `<tr><td>${x.area}</td><td class="num">${pct(x.gfm_excludes_share_under_trees, 0)}</td><td class="num">${pct(x.gfm_excludes_share_elsewhere, 0)}</td></tr>`).join("") +
      `<tr class="ev-total"><td>All ${c.areas.length}</td><td class="num">${pct(c.gfm_excludes_share_under_trees, 0)}</td><td class="num">${pct(c.gfm_excludes_share_elsewhere, 0)}</td></tr>`;
    $("blind-note").textContent = `Worldwide, ${(s.tree_km2 / 1e6).toFixed(1)} million km² of mapped river floodplain (${pct(s.share, 0)}) is under trees, and ${s.towns.high.toLocaleString("en-US")} of ${s.towns.checked.toLocaleString("en-US")} towns of 5,000+ people meet our high-risk rule. That describes nearby ground, not flooding or people at risk. These areas are where we already had GFM's masks, so this doesn't establish how well the stand-in works worldwide.`;
  }).catch(() => { $("blind-note").textContent = "The blind-spot numbers couldn't load."; });
}

// Table 5: the trust light on NISAR passes named before they happened (research/SEALED_TEST_PROTOCOL.md, scripts/score_sealed.py).
function setupSealed() {
  fetch("data/live/sealed.json").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }).then((s) => {
    const day = (t) => fmtTime(t), c = s.combined;
    $("sealed-sub").textContent = `On ${fmtDay(s.sealed_utc)}, before NISAR acquired them, we wrote down which of its next ${s.passes.length} passes over US rivers in flood would count, and fixed what the trust light predicts, green for a match of 0.60 or higher and red for below. Each pass is run once with the frozen method as it reaches NASA's catalog, and none is dropped.`;
    const status = (p) => ({ waiting: "Waiting", missing: "Missing", "not run": "Not run", "not judged": "Not judged", "not judgeable": "Too little flooding to judge", judged: "Judged" })[p.status] || p.status;
    $("t-sealed").innerHTML = "<tr><th>River</th><th>Predicted pass</th><th>Status</th><th>Trust light</th><th class='num'>Match</th><th>Light right?</th></tr>" +
      s.passes.map((p) => `<tr><td>${p.name}, ${p.state}</td><td>${day(p.predicted_utc)}</td><td title="${(p.reason || "").replace(/"/g, "&quot;")}">${status(p)}</td><td>${p.light || "—"}</td>` +
        `<td class="num">${p.csi == null ? "—" : p.csi.toFixed(2)}</td><td>${p.hit == null ? "—" : p.hit ? "Yes" : "No"}</td></tr>`).join("");
    $("sealed-note").textContent = `Checked ${fmtTime(s.checked_utc)}, with ${Object.entries(s.counts).filter(([, n]) => n).map(([k, n]) => `${n} ${k}`).join(", ")}. ` +
      `With the earlier test's ${s.overbank_judgeable} judgeable passes, the light is right on ${c.hits} of ${c.judgeable}, ${c.verdict === "too few" ? "still too few to judge (at least 5 needed)" : c.verdict}. ` +
      "NISAR scenes reach the catalog a median of about 2 days after a pass. The rules are in research/SEALED_TEST_PROTOCOL.md.";
    $("sealed").hidden = false;
  }).catch(() => {});
}

setupPaper();
setupSealed();
mountFigures();
// Printing or saving as PDF: draw every figure first, since those far down the page draw only when scrolled near.
$("pdf-btn").addEventListener("click", () => drawAllFigures().then(() => setTimeout(() => print(), 300)));
addEventListener("beforeprint", () => { drawAllFigures(); });
loadData().then(async ([, metrics]) => {
  setupTests(metrics); setupLidar(metrics); setupElevation(); setupGap(metrics);
  const F = await resultFacts(metrics);
  setupLimits(metrics, F);
  setupAbstract(metrics, F);
  setupCaptions(metrics, F);
  // A link to a figure: the figures above it grow as they draw, so scroll again once they all have.
  if (location.hash) { const go = () => document.querySelector(location.hash)?.scrollIntoView(); go(); drawAllFigures().then(() => setTimeout(go, 100)); }
});
