(function (root) {
  const MIN = 0.5, LC_TREE = 1, LC_WETLAND = 2, LC_OPEN = 3;

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

  const inScope = (s) => s !== null && s >= MIN;
  const why = (s) => s === null ? "There's no forest, wetland or field on this valley floor for GLOWfm to read." : `Only ${Math.round(100 * s)}% of this valley floor is forest or wetland, and GLOWfm reads flooding under trees. Open water on fields is what existing flood maps already catch.`;

  const api = { MIN, share, inScope, why };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LiveScope = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
