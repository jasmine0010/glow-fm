
const CLEAR_TILE = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";
const ATLAS_FADE = ["interpolate", ["linear"], ["zoom"], 6, 0.92, 7.5, 0.09];
const ATLAS_RADIUS_KM = 25, ATLAS_WORLD = [-170, -56, 179, 74], ATLAS_NEARBY_KM = 300;
const atlas = { enabled: true, summary: null, tiles: null, loading: null, places: null, placesLoading: null, cells: new Map(), pick: null, hits: [], token: 0 };
const km2 = (x) => `${Math.round(x).toLocaleString("en-US")} km²`;
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const fold = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

function loadAtlas() {
  atlas.loading ??= Promise.all([fetch("data/atlas/summary.json").then((r) => r.json()), fetch("data/atlas/tiles.json").then((r) => r.json())]).then(([summary, tiles]) => {
    atlas.summary = summary;
    atlas.tiles = new Set(tiles);
    return summary;
  });
  return atlas.loading;
}

maplibregl.addProtocol("atlas", async (params, abort) => {
  await loadAtlas();
  const key = params.url.replace("atlas://", "");
  if (atlas.tiles.has(key)) {
    try {
      const r = await fetch(`data/atlas/tiles/${key}.png`, { signal: abort.signal });
      if (r.ok) return { data: await r.arrayBuffer() };
    } catch (e) {
      if (abort.signal.aborted) throw e;
    }
  }
  return { data: Uint8Array.from(atob(CLEAR_TILE), (c) => c.charCodeAt(0)).buffer };
});

function addAtlasLayer(m) {
  m.addSource("atlas", { type: "raster", tiles: ["atlas://{z}/{x}/{y}"], tileSize: 256, minzoom: 0, maxzoom: 6, attribution: "© EU · ESA WorldCover" });
  m.addLayer({ id: "atlas", type: "raster", source: "atlas", layout: { visibility: atlas.enabled ? "visible" : "none" }, paint: { "raster-opacity": ATLAS_FADE, "raster-resampling": "nearest", "raster-fade-duration": 0 } });
}

function addAtlasPick(m) {
  m.addSource("atlas-pick", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  m.addLayer({ id: "atlas-pick", type: "line", source: "atlas-pick", layout: { visibility: atlas.enabled ? "visible" : "none" }, paint: { "line-color": "#e8eef2", "line-width": 1.5 } });
}

function atlasUrl() {
  if (atlas.event) { history.replaceState(null, "", `?flood=${encodeURIComponent(atlas.event.id)}`); return; }
  const q = new URLSearchParams({ view: "place" });
  const p = atlas.pick;
  if (p && p.at) {
    q.set("at", p.at.map((x) => x.toFixed(2)).join(","));
    if (p.short) { q.set("name", p.name); q.set("short", p.short); }
  } else if (p) q.set("country", p.name);
  history.replaceState(null, "", `?${q}`);
}

function atlasSetEnabled(on) {
  atlas.enabled = on;
  $("lyr-atlas").checked = on;
  if (!state.mapReady) return;
  map.setLayoutProperty("atlas", "visibility", on ? "visible" : "none");
  map.setLayoutProperty("atlas-pick", "visibility", on ? "visible" : "none");
  state.keyView = null;
  renderKey();
  if (state.pack) { renderTag(currentTime()); syncUrl(); }
  $("announce").textContent = `Blind-spot map ${on ? "on" : "off"}.`;
}

function atlasKey() {
  const s = atlas.summary;
  if (!s) return "";
  return `${100 * s.breaks[0]}% <span class="ramp">${s.colors.map((c) => `<i style="background:${c}"></i>`).join("")}</span> ${100 * s.breaks[3]}%+ under trees`;
}

const atlasPeople = (s) => `about ${Math.round(s.towns.people.total / 5e6) * 5} million people`;
const atlasTownsText = (s) => `About ${(Math.round(s.towns.high / 100) * 100).toLocaleString("en-US")} towns, home to ${atlasPeople(s)}, sit beside large forested floodplains where satellite flood maps are likely blind`;

function atlasVerdict(share, floodplain) {
  const rule = atlas.summary.towns.rule, tree = share * floodplain;
  if (floodplain < rule.min_floodplain_km2) return { cls: "grey", level: "No large floodplain mapped", label: "No large river floodplain is mapped", text: "Small streams can still flood, and this map doesn't cover them." };
  if (share >= rule.high_share && tree >= rule.high_tree_km2) return { cls: "red", level: "Flood maps likely to miss water here", label: "Flood map blank? Don't trust it", text: "Most of this floodplain is under trees. A flood here could look like dry ground on today's flood maps.", act: "If the flood map here is blank during a flood, don't treat it as an all-clear. Check river gauges or radar first." };
  if (share >= rule.moderate_share && tree >= rule.moderate_tree_km2) return { cls: "amber", level: "Flood maps may miss some water here", label: "Flood map blank? Be careful", text: "Part of this floodplain is under trees, so a flood map could miss some of the water here.", act: "If the flood map here is blank during a flood, check river gauges before trusting it." };
  return { cls: "green", level: "Trees hide little of this floodplain", label: "Flood map blank? Trees are a smaller problem", text: "Little of this floodplain is under trees, so trees are less likely to hide a flood. Flood maps can still miss water for other reasons." };
}

function renderAtlas() {
  const s = atlas.summary;
  if (!s) return;
  state.keyView = null;
  renderKey();
  $("atlas-lede").textContent = `${pct(s.share, 0)} of river floodplain worldwide is under trees, where flood maps can miss water. It shows where a flood could hide, not where one is.`;
  $("atlas-try").innerHTML = `<span class="atlas-try-label">Try</span>${s.towns.examples.slice(0, 4).map((e, k) => `<button type="button" class="atlas-chip" data-try="${k}">${esc(e.name)}</button>`).join("")}`;
  $("atlas-countries").innerHTML = s.countries.slice(0, 5).map((x) => `<button type="button" class="atlas-row" data-country="${esc(x.name)}"><span>${esc(x.name)}</span><span>${km2(x.tree_km2)}</span></button>`).join("");
  if (state.sel === "pick") renderAtlasPick();
}

function atlasLabelText(p, v) {
  const who = p.short || (p.at ? null : p.name), where = p.at ? "near" : "in";
  return v.cls === "grey" ? `${v.label} ${who ? `${where} ${who}` : "here"}.` : `${v.label.replace("Flood map blank?", `Flood map blank ${who ? `${where} ${who}` : "here"}?`)}${v.cls === "green" ? " here." : "."}`;
}

function renderAtlasPick() {
  const box = $("atlas-pick"), p = atlas.pick, ev = typeof worldCard === "function" ? worldCard() : null;
  if (!p && !ev) { box.innerHTML = '<p class="muted">Choose a flood, or check a place.</p>'; return; }
  const v = p && !p.loading && !p.failed ? atlasVerdict(p.share, p.floodplain) : null, big = v && p.floodplain >= atlas.summary.towns.rule.min_floodplain_km2;
  const near = p && p.at && !ev ? nearestTested(p.at) : null, label = v ? atlasLabelText(p, v) : "";
  const reading = !p ? "" : p.failed ? `<div class="estimate"><p class="muted">Couldn't check the floodplain here just now. <button type="button" class="link-btn" id="atlas-retry">Try again</button></p></div>`
    : p.loading ? '<div class="estimate"><p class="muted">Checking the floodplain here…</p></div>'
      : `<div class="estimate"><p class="atlas-level"><i class="status-dot ${v.cls}"></i>${v.level}</p>` +
        (big ? `<div class="est-pair"><div class="est"><span class="kpi-label">Under trees</span><span class="est-num est-forest">${pct(p.share, 0)}</span><span class="kpi-sub">of the floodplain</span></div>` +
          `<div class="est"><span class="kpi-label">${p.at ? "Floodplain nearby" : "Floodplain"}</span><span class="est-num">${km2(p.floodplain)}</span><span class="kpi-sub">${p.at ? "within 25 km" : "mapped in the country"}</span></div></div>` : "") + "</div>";
  const explain = !v ? "" : `<p class="atlas-why">${v.text}</p>${v.act ? `<p class="atlas-act"><b>What to do:</b> ${v.act}</p>` : ""}<p class="atlas-not">Not a flood forecast. It says how well flood maps can see the ground here.</p>`;
  if (ev) {
    box.innerHTML = `<h2 class="river-title">${esc(ev.title)}</h2><p class="dash-sub">${ev.status}</p>` +
      `<div class="readouts"><div class="kpi kpi-lead"><span class="kpi-label">NISAR passes during this flood</span><span class="kpi-num">${ev.number}</span><span class="kpi-sub">${ev.numberSub}</span></div></div>` +
      reading + `<div class="card-foot">${ev.foot}</div>` +
      `<details class="collapse"><summary>Details</summary>${ev.details}${explain}</details>`;
  } else {
    box.innerHTML = `<h2 class="river-title">${esc(p.name)}</h2><p class="dash-sub">${esc(label || (p.loading ? "Checking…" : ""))}</p>` + reading +
      (near ? `<div class="card-foot"><p class="flood-tools"><button type="button" class="link-btn atlas-near" data-river="${near.r.id}">The nearest tested flood: ${esc(shortRiver(near.r))}, ${Math.round(near.km)} km away</button></p></div>` : "") +
      (explain ? `<details class="collapse"><summary>Details</summary>${explain}</details>` : "");
  }
  if ($("atlas-retry")) $("atlas-retry").addEventListener("click", () => atlasPickAt(p.at[0], p.at[1], p.name, p.short));
  if (label) $("announce").textContent = label;
}

const distanceKm = (a, b) => { const r = Math.PI / 180, x = (b[1] - a[1]) * r * Math.cos((a[0] + b[0]) * r / 2), y = (b[0] - a[0]) * r; return 6371 * Math.hypot(x, y); };

function nearestTested(at) {
  const rows = rivers.map((r) => ({ r, km: distanceKm(at, [(r.bounds[1] + r.bounds[3]) / 2, (r.bounds[0] + r.bounds[2]) / 2]) })).sort((a, b) => a.km - b.km);
  return rows[0] && rows[0].km <= ATLAS_NEARBY_KM ? rows[0] : null;
}

async function atlasCells(lat0, lon0) {
  const name = `${lat0}_${lon0}`;
  if (!atlas.summary.cell_files.includes(name)) return null;
  if (!atlas.cells.has(name)) {
    const load = async () => {
      for (let attempt = 1; ; attempt++) {
        try { const r = await fetch(`data/atlas/cells/${name}.bin`); if (!r.ok) throw new Error(`${r.status}`); return new Uint16Array(await r.arrayBuffer()); } catch (err) {
          if (attempt >= 3) { atlas.cells.delete(name); throw err; }
          await new Promise((ok) => setTimeout(ok, 500 * attempt));
        }
      }
    };
    atlas.cells.set(name, load());
  }
  return atlas.cells.get(name);
}

async function atlasLookup(lat, lon) {
  await loadAtlas();
  const dLat = ATLAS_RADIUS_KM / 111.32, dLon = dLat / Math.max(0.1, Math.cos(lat * Math.PI / 180));
  let floodplain = 0, tree = 0;
  for (let y = Math.floor((lat - dLat) * 10); y <= Math.floor((lat + dLat) * 10); y++) {
    for (let x = Math.floor((lon - dLon) * 10); x <= Math.floor((lon + dLon) * 10); x++) {
      const cLat = (y + 0.5) / 10, cLon = (x + 0.5) / 10;
      if (distanceKm([lat, lon], [cLat, cLon]) > ATLAS_RADIUS_KM) continue;
      const wrapped = ((x + 1800) % 3600 + 3600) % 3600, lat0 = Math.floor(y / 100) * 10, lon0 = Math.floor(wrapped / 100) * 10 - 180;
      const cells = await atlasCells(lat0, lon0);
      if (!cells) continue;
      const k = (99 - (y - lat0 * 10)) * 100 + (wrapped - (lon0 + 180) * 10);
      floodplain += cells[k] / 100;
      tree += cells[10000 + k] / 100;
    }
  }
  return { floodplain, share: floodplain > 0 ? tree / floodplain : 0 };
}

function atlasRing(lat, lon) {
  const pts = [];
  for (let k = 0; k <= 64; k++) {
    const a = 2 * Math.PI * k / 64;
    pts.push([lon + ATLAS_RADIUS_KM / 111.32 * Math.sin(a) / Math.max(0.1, Math.cos(lat * Math.PI / 180)), lat + ATLAS_RADIUS_KM / 111.32 * Math.cos(a)]);
  }
  map.getSource("atlas-pick").setData({ type: "Feature", geometry: { type: "LineString", coordinates: pts }, properties: {} });
}

async function atlasPickAt(lat, lon, name, short) {
  const token = ++atlas.token;
  atlas.pick = { name: name || `${coordText(lat, "N", "S", 2)} ${coordText(lon, "E", "W", 2)}`, short, at: [lat, lon], loading: true };
  showSel("pick");
  atlasRing(lat, lon);
  renderAtlasPick();
  let got;
  try { got = await atlasLookup(lat, lon); } catch (err) {
    console.warn("Place check failed", err);
    if (token === atlas.token) { atlas.pick = { ...atlas.pick, loading: false, failed: true }; renderAtlasPick(); }
    return;
  }
  if (token !== atlas.token) return;
  atlas.pick = { ...atlas.pick, ...got, loading: false };
  renderAtlasPick();
  atlasUrl();
}

function atlasPickCountry(name) {
  const c = atlas.summary.countries.find((x) => x.name === name);
  if (!c) return;
  atlas.token++;
  atlas.pick = { name: c.name, floodplain: c.floodplain_km2, share: c.share, at: null, loading: false };
  atlas.event = null;
  showSel("pick");
  map.getSource("atlas-pick").setData({ type: "FeatureCollection", features: [] });
  renderAtlasPick();
  atlasUrl();
  if (c.bbox) map.fitBounds(c.bbox, { padding: viewPadding(), maxZoom: 6, duration: document.hidden ? 0 : 1600 });
}

function loadPlaces() {
  atlas.placesLoading ??= fetch("data/atlas/places.json").then((r) => r.json()).then((d) => {
    atlas.places = [...d.places, ...d.rivers].map((p) => ({ name: p[0], where: p[1], lat: p[2], lon: p[3], key: fold(p[0]) }));
    return atlas.places;
  });
  return atlas.placesLoading;
}

function atlasMatches(q) {
  const countries = atlas.summary.countries.filter((c) => ` ${fold(c.name)}`.includes(` ${q}`)).map((c) => ({ country: c.name, name: c.name, where: "country" }));
  const exact = [], rivers = [], starts = [], words = [];
  for (const p of atlas.places) {
    if (p.key === q || p.key === `${q} river`) exact.push(p);
    else if (p.key.startsWith(q)) (p.where === "river" ? rivers : starts).push(p);
    else if (p.key.includes(` ${q}`)) words.push(p);
  }
  const named = countries.filter((c) => fold(c.name) === q);
  return [...named, ...exact.slice(0, 3), ...countries.filter((c) => !named.includes(c)), ...rivers.slice(0, 2), ...starts, ...words].slice(0, 6);
}

async function atlasSearch(text) {
  const q = fold(text.trim()), box = $("atlas-results");
  if (q.length < 2) { box.innerHTML = ""; atlas.hits = []; return; }
  await loadPlaces();
  if (fold($("atlas-q").value.trim()) !== q) return;
  atlas.hits = atlasMatches(q);
  box.innerHTML = atlas.hits.length ? atlas.hits.map((p, k) => `<button type="button" class="atlas-row atlas-hit" data-hit="${k}"><span>${esc(p.name)}</span><span>${esc(p.where)}</span></button>`).join("") : '<p class="muted">No match. Try a nearby town, or click the map.</p>';
}

function atlasChoose(hit) {
  atlas.event = null;
  $("atlas-results").innerHTML = "";
  $("atlas-q").value = "";
  atlas.hits = [];
  if (isPhone() && state.panel !== "right") setPanel("right");
  if (hit.country) return atlasPickCountry(hit.country);
  flyToPlace(hit.lon, hit.lat, 6);
  atlasPickAt(hit.lat, hit.lon, hit.where === "river" ? hit.name : `${hit.name}, ${hit.where}`, hit.name);
}

function wireAtlas() {
  $("lyr-atlas").addEventListener("change", (e) => atlasSetEnabled(e.target.checked));
  $("atlas-q").addEventListener("input", (e) => atlasSearch(e.target.value));
  $("atlas-q").addEventListener("keydown", (e) => { if (e.key === "Enter" && atlas.hits.length) { e.preventDefault(); atlasChoose(atlas.hits[0]); } });
  $("atlas-results").addEventListener("click", (e) => { const b = e.target.closest("[data-hit]"); if (b) atlasChoose(atlas.hits[Number(b.dataset.hit)]); });
  $("atlas-countries").addEventListener("click", (e) => { const b = e.target.closest("[data-country]"); if (b) atlasPickCountry(b.dataset.country); });
  $("atlas-try").addEventListener("click", (e) => { const b = e.target.closest("[data-try]"); if (b) atlasChoose(atlas.summary.towns.examples[Number(b.dataset.try)]); });
  $("atlas-pick").addEventListener("click", (e) => {
    const b = e.target.closest("[data-river]");
    if (b) { setFloodTab("tested"); activate(b.dataset.river); }
  });
}
