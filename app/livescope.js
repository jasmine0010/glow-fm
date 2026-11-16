(function (root) {
  const MIN = 0.5, MIN_HA = 1000, LC_TREE = 1, LC_WETLAND = 2, LC_OPEN = 3;

  function share(d, rule = {}) {
    const handMax = rule.hand_max_m ?? 6, valley = rule.valley_m ?? 4000;
    let trees = 0, land = 0;
    for (let i = 0; i < d.landcover.length; i++) {
      if (!(d.hand[i] < handMax) || !(d.dist[i] < valley)) continue;
      const lc = d.landcover[i];
      if (lc === LC_TREE || lc === LC_WETLAND) { trees++; land++; } else if (lc === LC_OPEN) land++;
    }
    return land ? trees / land : null;
  }

  // Ground GLOWfm could flag at this pass, settled before any run: radar on both dates, a land cover it reads,
  // low enough above the river, not permanent water, and not held back as long past the crest.
  function readable(d, rule = {}, pixelHa = 0.25) {
    const handMax = rule.hand_max_m ?? 6, lc = new Set(rule.landcover ?? [1, 2, 0]), held = new Set(rule.abstain_timing ?? [4]);
    let n = 0, late = 0;
    for (let i = 0; i < d.landcover.length; i++) {
      if (!(d.wet_hh[i] === d.wet_hh[i]) || !(d.median_hh[i] === d.median_hh[i])) continue;
      if (!lc.has(d.landcover[i]) || !(d.hand[i] < handMax) || (d.water && d.water[i])) continue;
      if (d.timing && held.has(d.timing[i])) late++; else n++;
    }
    return { ha: Math.round(n * pixelHa), late_ha: Math.round(late * pixelHa) };
  }

  const inScope = (s) => s !== null && s >= MIN;
  const bigEnough = (r) => r.ha >= MIN_HA;
  const why = (s) => s === null ? "There's no forest, wetland or field on this valley floor for GLOWfm to read." : `Only ${Math.round(100 * s)}% of this valley floor is forest or wetland, and GLOWfm reads flooding under trees. Open water on fields is what existing flood maps already catch.`;
  const whyArea = (r) => r.ha === 0 && r.late_ha > 0
    ? "The river was long past its crest when NISAR passed, and GLOWfm holds back on ground like that, so there's nothing left here for it to map."
    : `Only ${r.ha.toLocaleString("en-US")} ha of this valley is ground GLOWfm can read at this pass, too little for a map worth showing. It needs at least ${MIN_HA.toLocaleString("en-US")} ha (10 km²).`;
  const short = (r) => r.ha === 0 && r.late_ha > 0 ? "long past its crest when NISAR passed" : `only ${r.ha.toLocaleString("en-US")} ha of ground GLOWfm can read`;

  const api = { MIN, MIN_HA, share, readable, inScope, bigEnough, why, whyArea, short };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LiveScope = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
