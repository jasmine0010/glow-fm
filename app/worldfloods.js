const WORLD_SHOWN = 5;
const ALERT_RANK = { Red: 0, Orange: 1, Green: 2 };
const LEVEL_WORD = { red: "likely blind", amber: "may miss some", green: "trees a small problem", grey: "no large floodplain" };
const world = { events: [], live: null, saved: null, error: false, showAll: false, nisar: new Map(), level: new Map(), busy: 0, queue: [] };

const shortDay = (t) => new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const dayRange = (a, b) => `${shortDay(a)} – ${shortDay(b)}`;


const canRun = (e) => (liveCaseFor(e) ? 0 : 1);
const sortEvents = (list) => list.sort((a, b) => canRun(a) - canRun(b) || (ALERT_RANK[a.alert] ?? 3) - (ALERT_RANK[b.alert] ?? 3) || b.current - a.current || b.to - a.to);

const WORLD_REFRESH_MS = 15 * 60 * 1000;
setInterval(() => {
  if (document.hidden || !world.live) return;
  world.events.filter((e) => e.current).forEach((e) => { if (!cachedNisar(e)) world.nisar.delete(e.id); });
  world.catalogDown = false;
  loadWorld();
}, WORLD_REFRESH_MS);

const WANT_FLOOD = new URLSearchParams(location.search).get("flood");

async function loadWorld() {
  try {
    world.events = sortEvents(await fetchGdacs());
    world.live = Date.now();
  } catch (e) {
    console.warn("GDACS unavailable, using the saved list", e);
    try {
      const snap = await fetch("data/dashboard/world_floods.json").then((r) => r.json());
      world.events = sortEvents(snap.events);
      world.saved = true;
      world.savedAt = Date.parse(snap.saved);
      snap.events.forEach((x) => { if (x.nisar) world.nisar.set(x.id, x.nisar); });
    } catch { world.error = true; }
  }
  renderWorld();
  const hit = WANT_FLOOD && world.events.find((x) => String(x.id) === WANT_FLOOD);
  if (WANT_FLOOD && !world.opened) {
    world.opened = true;
    if (hit) {
      const go = () => { if (map.isMoving() || !map.loaded()) { setTimeout(go, 300); return; } setFloodTab("world"); chooseWorld(hit); };
      setTimeout(go, 400);
    } else if (state.pack && state.sel === "river") { syncUrl(); flyToBounds(state.river.bounds); }
  }
  setWorldLayer();
}

const NISAR_CACHE_MS = 3600 * 1000;
const cacheKey = (e) => `hf-nisar4-${e.id}-${e.to}`;
function cachedNisar(e) {
  try { const c = JSON.parse(localStorage.getItem(cacheKey(e))); return c && Date.now() - c.at < NISAR_CACHE_MS ? c : null; } catch { return null; }
}

let savedCounts = null;
async function savedNisar(e) {
  savedCounts ??= fetch("data/dashboard/world_floods.json").then((r) => r.json()).then((snap) => ({ saved: Date.parse(snap.saved) || true, byId: new Map(snap.events.map((x) => [x.id, x.nisar])) })).catch(() => null);
  const snap = await savedCounts, n = snap && snap.byId.get(e.id);
  return n ? { ...n, saved: snap.saved } : null;
}

async function nisarOver(e) {
  if (world.nisar.has(e.id)) return world.nisar.get(e.id);
  const kept = cachedNisar(e);
  if (kept) { world.nisar.set(e.id, kept); return kept; }
  try { if (world.catalogDown) throw new Error("NASA's catalog didn't answer earlier"); return await nisarLive(e); } catch (err) {
    world.catalogDown = true;
    const saved = await savedNisar(e);
    if (!saved) throw err;
    world.nisar.set(e.id, saved);
    return saved;
  }
}

function quickOf(umm) {
  const link = (umm.RelatedUrls || []).find((u) => u.Type === "GET RELATED VISUALIZATION" && /^https:/.test(u.URL) && /_LATLON\.png$/.test(u.URL));
  const poly = umm.SpatialExtent?.HorizontalSpatialDomain?.Geometry?.GPolygons?.[0]?.Boundary?.Points;
  return link && poly && poly.length >= 4 ? { url: link.URL, corners: poly.slice(0, 4).map((q) => [q.Longitude, q.Latitude]), time: Date.parse(umm.TemporalExtent.RangeDateTime.BeginningDateTime) } : null;
}


async function cmrScenes(short, e, from, to) {
  const q = new URLSearchParams({ short_name: short, point: `${e.lon.toFixed(4)},${e.lat.toFixed(4)}`, temporal: `${new Date(from).toISOString()},${new Date(to).toISOString()}`, sort_key: "-start_date", page_size: "1" });
  const j = await (await withTimeout(`${CMR_URL}?${q}`)).json();
  return { hits: j.hits, item: j.items[0] ? j.items[0].umm : null };
}

async function nisarLive(e) {
  const end = Math.min(e.to + DAY, Date.now()), asks = [];
  if (end > NISAR_SPLIT) asks.push(cmrScenes(NISAR_NEW, e, Math.max(e.from, NISAR_SPLIT), end));
  if (e.from < NISAR_SPLIT) asks.push(cmrScenes(NISAR_OLD, e, e.from, Math.min(end, NISAR_SPLIT)));
  const parts = await Promise.all(asks), newest = parts.map((p) => p.item).find(Boolean);
  const got = { count: parts.reduce((n, p) => n + p.hits, 0), latest: newest ? Date.parse(newest.TemporalExtent.RangeDateTime.BeginningDateTime) : null, quick: newest ? quickOf(newest) : null };
  world.nisar.set(e.id, got);
  try { localStorage.setItem(cacheKey(e), JSON.stringify({ ...got, at: Date.now() })); } catch {}
  return got;
}

async function levelAt(e) {
  if (world.level.has(e.id)) return world.level.get(e.id);
  const got = await atlasLookup(e.lat, e.lon);
  const v = atlasVerdict(got.share, got.floodplain);
  world.level.set(e.id, v);
  return v;
}

function lookUp(e) {
  if ((world.nisar.has(e.id) && world.level.has(e.id)) || world.queue.includes(e)) return;
  world.queue.push(e);
  pump();
}

function pump() {
  while (world.busy < 2 && world.queue.length) {
    const e = world.queue.shift();
    world.busy++;
    Promise.allSettled([nisarOver(e), levelAt(e)]).then((r) => {
      if (r[0].status === "rejected") world.nisar.set(e.id, { failed: true });
      world.busy--;
      renderWorld();
      if (atlas.event && atlas.event.id === e.id) renderAtlasPick();
      pump();
    });
  }
}

const nisarText = (n) => (!n ? "…" : n.failed ? "catalog down" : `${n.count} pass${n.count === 1 ? "" : "es"}${n.saved ? "*" : ""}`);

function renderWorld() {
  const box = $("world-list");
  if (!box) return;
  if (world.error) { box.innerHTML = '<p class="muted">The global flood feed (GDACS) is unavailable right now.</p>'; $("world-source").textContent = ""; return; }
  if (!world.events.length) { box.innerHTML = `<p class="muted">${world.live || world.saved ? `No floods reported in the last ${WORLD_DAYS} days.` : "Loading floods reported worldwide…"}</p>`; return; }
  const shown = world.showAll ? world.events : world.events.slice(0, WORLD_SHOWN), active = atlas.event && atlas.event.token === atlas.token && atlas.event.id;
  const focused = document.activeElement && document.activeElement.closest && document.activeElement.closest("#world-list [data-world]"), focusId = focused && focused.dataset.world;
  box.innerHTML = `<div class="events-head" aria-hidden="true"><span>Flood</span><span>NISAR passes · flood maps</span></div>` + shown.map((e) => {
    const n = world.nisar.get(e.id), v = world.level.get(e.id), dates = `${dayRange(e.from, e.to)}${e.current ? ", ongoing" : ""}`;
    const label = `${e.name}, ${e.alert.toLowerCase()} alert, ${dates}. NISAR: ${nisarText(n)}. Flood maps: ${v ? LEVEL_WORD[v.cls] : "checking"}.`;
    const run = !canRun(e);
    return `<button type="button" class="event-row world-row${e.id === active ? " on" : ""}" data-world="${esc(e.id)}" aria-label="${esc(label + (run ? " You can run GLOWfm on it." : ""))}"><span class="event-main"><i class="status-dot ${v ? v.cls : "grey"}"></i><span class="event-name">${esc(e.country)}</span><span class="event-value">${nisarText(n)}</span></span><span class="event-sub" title="Flood maps here: ${v ? LEVEL_WORD[v.cls] : "checking"}">${dates}</span></button>`;
  }).join("") + (world.events.length > WORLD_SHOWN ? `<button type="button" class="link-btn world-more" id="world-more">${world.showAll ? "Show fewer" : `Show all ${world.events.length}`}</button>` : "");
  if (focusId) { const again = box.querySelector(`[data-world="${focusId}"]`); if (again) again.focus(); }
  const starred = shown.some((e) => (world.nisar.get(e.id) || {}).saved) ? " * A saved count, because NASA's catalog didn't answer just now." : "";
  $("world-source").textContent = (world.live ? `GDACS alerts, last ${WORLD_DAYS} days · passes from NASA's catalog` : `${Number.isFinite(world.savedAt) ? `GDACS list saved ${shortDay(world.savedAt)}` : "A saved GDACS list"}, because the live feed didn't answer. NISAR passes as of then.`) + starred;
  shown.forEach(lookUp);
  if (typeof state === "object" && state.mapReady) renderKey();
}

function chooseWorld(e) {
  setFloodTab("world");
  if (isPhone() && state.panel !== "right") setPanel("right");
  flyToPlace(e.lon, e.lat, 6);
  atlasPickAt(e.lat, e.lon, e.name);
  atlas.event = { ...e, token: atlas.token };
  atlasUrl();
  lookUp(e);
  renderAtlasPick();
  renderWorld();
}

let liveCases = [], liveSkips = new Map(), liveOutside = new Map();
fetch("data/live/index.json").then((r) => (r.ok ? r.json() : { cases: [] })).then((x) => {
  liveCases = x.cases || [];
  liveSkips = new Map(((x.coverage || {}).skipped || []).filter((s) => s.gdacs).map((s) => [String(s.gdacs), s.skip]));
  liveOutside = new Map(liveCases.filter((c) => c.kind === "world" && c.gdacs && c.scope && c.scope.in_scope === false).map((c) => [String(c.gdacs), c.scope]));
  if (atlas.event) renderAtlasPick();
  if (world.events.length) { sortEvents(world.events); renderWorld(); }
}).catch(() => {});
const liveInScope = (c) => !(c.scope && c.scope.in_scope === false);
const liveCaseFor = (e) => liveCases.find((c) => c.kind === "world" && String(c.gdacs) === String(e.id) && !c.superseded_by && liveInScope(c))
  || liveCases.find((c) => c.kind === "world" && String(c.gdacs) === String(e.id) && liveInScope(c));
function whyNotRun(e) {
  const scope = liveOutside.get(String(e.id)), share = scope && scope.tree_share;
  if (scope && scope.too_small) return scope.readable_ha === 0 && scope.late_ha > 0
    ? "Too late to map here. The river was long past its crest when NISAR passed, and GLOWfm holds back on ground like that."
    : `Too little ground to map here. Only ${scope.readable_ha.toLocaleString("en-US")} ha of this valley is ground GLOWfm can read at this pass, and it needs at least 1,000 ha.`;
  if (scope) return `Outside GLOWfm's scope here. Only ${Math.round(100 * (share || 0))}% of the valley floor is forest or wetland, and GLOWfm reads flooding under trees. Open water on fields is what existing flood maps already catch.`;
  const why = liveSkips.get(String(e.id));
  if (!why) return null;
  const few = why.match(/^Only (\d+) earlier pass/);
  if (few) return `Can't run here yet. GLOWfm compares the flood with 3 earlier NISAR passes on the same track, and there ${few[1] === "1" ? "is" : "are"} only ${few[1]}.`;
  if (/^No NISAR pass/.test(why)) return "Can't run here yet. None of NISAR's passes during this flood are the kind GLOWfm reads (40 MHz, HH and HV).";
  return "GLOWfm couldn't be prepared for this flood.";
}
let hasReader = false;
if (document.querySelector('meta[name="glowfm-reader"]')) {
  fetch("/api/health").then((r) => (r.ok ? r.json() : null)).then((x) => { hasReader = !!(x && x.ok); if (hasReader && atlas.event) renderAtlasPick(); }).catch(() => {});
}
function tryHere(e) {
  const dy = 12 / 111.32, dx = dy / Math.max(0.1, Math.cos((e.lat * Math.PI) / 180)), day = (ms) => new Date(ms).toISOString().slice(0, 10);
  const box = [e.lon - dx, e.lat - dy, e.lon + dx, e.lat + dy].map((v) => v.toFixed(4)).join(",");
  return `live.html?box=${box}&from=${day(e.from)}&to=${day(Math.min(e.to, Date.now()))}&flood=${encodeURIComponent(e.id)}&name=${encodeURIComponent(e.name)}`;
}

let waitDays = null;
catalogWait().then((w) => { waitDays = w; });
function worldCard() {
  const e = atlas.event;
  if (!e || e.token !== atlas.token) { if (quick.id) clearQuick(); return null; }
  const n = world.nisar.get(e.id), run = liveCaseFor(e);
  if (n && n.quick && quick.id !== e.id) setTimeout(() => showQuick(e, n.quick), 0);
  const saved = n && n.saved ? ` ${n.saved === true ? "From the saved list" : `As of ${shortDay(n.saved)}`}, because NASA's catalog didn't answer just now.` : "";
  const number = !n ? "…" : n.failed ? "—" : String(n.count);
  const numberSub = !n ? "checking NASA's catalog" : n.failed ? "NASA's catalog didn't answer" : n.count ? `most recently ${shortDay(n.latest)}${saved}` : `none over this spot so far${saved}`;
  const action = run ? `<a class="btn-primary card-primary" href="live.html?case=${encodeURIComponent(run.id)}">Run GLOWfm on this flood</a>`
    : hasReader && n && n.count && !whyNotRun(e) ? `<a class="btn-primary card-primary" href="${tryHere(e)}">Try GLOWfm here</a>` : "";
  const foot = `${action ? `<p class="card-actions">${action}</p>` : ""}${e.report ? `<p class="flood-tools"><a class="link-btn" href="${esc(e.report)}" target="_blank" rel="noopener">GDACS report</a></p>` : ""}`;
  const details = `${n && n.count && e.current ? `<p class="atlas-small">${nextPassText(n.latest, waitDays)}</p>` : ""}${quickLine(n)}` +
    (run ? "" : whyNotRun(e) ? `<p class="atlas-small">${whyNotRun(e)}</p>` : n && n.count ? `<p class="atlas-small">${hasReader ? "Not prepared yet. GLOWfm reads its NISAR radar from NASA when you try it." : "Not prepared yet, so GLOWfm can't run on it here."}</p>`
      : `<p class="atlas-small">We haven't mapped this flood. A pass means NISAR's radar could show it, including under trees.</p>`);
  return { title: e.name, status: `GDACS ${esc(e.alert.toLowerCase())} alert · ${dayRange(e.from, e.to)}, ${new Date(e.to).getUTCFullYear()}${e.current ? ", still reported" : ""}`, number, numberSub, foot, details };
}

const QUICK_FIT_KM = 1, QUICK_TIMEOUT_MS = 45000;
const quick = { id: null, state: null, url: null, blob: null };

function fitExtent(data, w, h, corners) {
  let top = null, bottom = null, left = null, right = null;
  const row = (y) => { let s = 0, n = 0; for (let x = 0; x < w; x++) if (data[(y * w + x) * 4 + 3]) { s += x; n++; } return n ? s / n : null; };
  const col = (x) => { let s = 0, n = 0; for (let y = 0; y < h; y++) if (data[(y * w + x) * 4 + 3]) { s += y; n++; } return n ? s / n : null; };
  for (let y = 0; y < h && !top; y++) { const x = row(y); if (x !== null) top = [x, y]; }
  for (let y = h - 1; y >= 0 && !bottom; y--) { const x = row(y); if (x !== null) bottom = [x, y]; }
  for (let x = 0; x < w && !left; x++) { const y = col(x); if (y !== null) left = [x, y]; }
  for (let x = w - 1; x >= 0 && !right; x--) { const y = col(x); if (y !== null) right = [x, y]; }
  if (!top || !bottom || !left || !right) return null;
  const by = (f) => corners.reduce((a, b) => (f(b, a) ? b : a));
  const geo = [by((a, b) => a[1] > b[1]), by((a, b) => a[1] < b[1]), by((a, b) => a[0] < b[0]), by((a, b) => a[0] > b[0])], px = [top, bottom, left, right];
  const line = (u, v) => { const n = u.length, mu = u.reduce((a, b) => a + b) / n, mv = v.reduce((a, b) => a + b) / n; let sxy = 0, sxx = 0; for (let i = 0; i < n; i++) { sxy += (u[i] - mu) * (v[i] - mv); sxx += (u[i] - mu) ** 2; } const k = sxx ? sxy / sxx : 0; return [mv - k * mu, k]; };
  const [W, dLon] = line(px.map((q) => q[0]), geo.map((g) => g[0])), [N, negLat] = line(px.map((q) => q[1]), geo.map((g) => g[1]));
  const worst = Math.max(...px.map((q, i) => Math.hypot((W + q[0] * dLon - geo[i][0]) * 111.32 * Math.cos(geo[i][1] * Math.PI / 180), (N + q[1] * negLat - geo[i][1]) * 111.32)));
  if (!(dLon > 0) || !(negLat < 0) || worst > QUICK_FIT_KM) return null;
  return { W, E: W + w * dLon, N, S: N + h * negLat, worst };
}

function clearQuick() {
  if (map && map.getLayer && map.getLayer("world-quick")) { map.removeLayer("world-quick"); map.removeSource("world-quick"); }
  if (quick.url) URL.revokeObjectURL(quick.url);
  Object.assign(quick, { id: null, state: null, url: null, blob: null });
}

async function showQuick(e, q) {
  if (quick.id === e.id) return;
  clearQuick();
  quick.id = e.id; quick.state = "loading"; renderAtlasPick();
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), QUICK_TIMEOUT_MS), stop = () => ctl.abort();
  worldLeave.signal.addEventListener("abort", stop);
  try {
    const blob = await (await fetch(q.url, { signal: ctl.signal })).blob();
    const bmp = await createImageBitmap(blob), c = document.createElement("canvas");
    c.width = bmp.width; c.height = bmp.height;
    const g = c.getContext("2d", { willReadFrequently: true });
    g.drawImage(bmp, 0, 0);
    const fit = fitExtent(g.getImageData(0, 0, c.width, c.height).data, c.width, c.height, q.corners);
    if (quick.id !== e.id) return;
    if (!fit) { quick.state = "unplaced"; renderAtlasPick(); return; }
    quick.url = URL.createObjectURL(blob);
    map.addSource("world-quick", { type: "image", url: quick.url, coordinates: [[fit.W, fit.N], [fit.E, fit.N], [fit.E, fit.S], [fit.W, fit.S]] });
    map.addLayer({ id: "world-quick", type: "raster", source: "world-quick", paint: { "raster-opacity": 0.9, "raster-fade-duration": 0 } }, map.getLayer("world-floods-halo") ? "world-floods-halo" : undefined);
    quick.state = "shown";
  } catch (err) {
    if (quick.id === e.id) quick.state = "failed";
    console.warn("NISAR picture unavailable", err);
  } finally { clearTimeout(timer); worldLeave.signal.removeEventListener("abort", stop); }
  if (quick.id === e.id) renderAtlasPick();
}

function quickLine(n) {
  const q = n && n.quick;
  if (!q) return "";
  const day = shortDay(q.time), open = `<a href="${esc(q.url)}" target="_blank" rel="noopener">open it</a>`;
  if (quick.state === "loading") return `<p class="world-quick">Loading NISAR's picture from ${day} (about 5 MB)…</p>`;
  if (quick.state === "shown") return `<p class="world-quick">The map shows NISAR's radar picture from ${day}. Open water looks dark; flooded forest can look bright. <button type="button" class="link-btn" id="quick-hide">Hide it</button></p>`;
  if (quick.state === "unplaced") return `<p class="world-quick">NISAR's picture from ${day} couldn't be placed on the map exactly, so it isn't drawn. You can ${open}.</p>`;
  if (quick.state === "hidden") return `<p class="world-quick">NISAR's picture from ${day} is hidden. <button type="button" class="link-btn" id="quick-show">Show it</button></p>`;
  if (quick.state === "failed") return `<p class="world-quick">NISAR's picture from ${day} didn't load. You can ${open}.</p>`;
  return "";
}

const worldGeo = () => ({ type: "FeatureCollection", features: world.events.map((e) => ({ type: "Feature", geometry: { type: "Point", coordinates: [e.lon, e.lat] }, properties: { id: e.id } })) });

function addWorldLayer(m) {
  m.addSource("world-floods", { type: "geojson", data: worldGeo() });
  m.addLayer({ id: "world-floods-halo", type: "circle", source: "world-floods", paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 6, 6, 12], "circle-color": "#6fe3ef", "circle-opacity": 0.22, "circle-blur": 0.7 } });
  m.addLayer({ id: "world-floods", type: "circle", source: "world-floods", paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 1, 3, 6, 5.5], "circle-color": "#6fe3ef", "circle-stroke-color": "#03060a", "circle-stroke-width": 1.2 } });
}

function setWorldLayer() {
  if (typeof map === "undefined" || !map || !map.getSource || !map.getSource("world-floods")) return;
  map.getSource("world-floods").setData(worldGeo());
}

function worldAt(m, point) {
  if (!m.getLayer("world-floods")) return null;
  const f = m.queryRenderedFeatures([[point.x - 7, point.y - 7], [point.x + 7, point.y + 7]], { layers: ["world-floods"] })[0];
  return f ? world.events.find((x) => x.id === f.properties.id) : null;
}

function setFloodTab(name) {
  document.querySelectorAll(".flood-tabs button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tab === name)));
  ["world", "tested", "blind"].forEach((k) => { $(`tab-${k}`).hidden = name !== k; });
  if (name === "blind" && !atlas.enabled) atlasSetEnabled(true);
}

function wireWorld() {
  $("atlas-pick").addEventListener("click", (ev) => { if (ev.target.id === "quick-hide") { clearQuick(); quick.id = atlas.event && atlas.event.id; quick.state = "hidden"; renderAtlasPick(); } if (ev.target.id === "quick-show") { quick.id = null; renderAtlasPick(); } });
  document.querySelectorAll(".flood-tabs button").forEach((b) => b.addEventListener("click", () => setFloodTab(b.dataset.tab)));
  $("world-list").addEventListener("click", (ev) => {
    if (ev.target.id === "world-more") { world.showAll = !world.showAll; renderWorld(); return; }
    const b = ev.target.closest("[data-world]");
    const e = b && world.events.find((x) => x.id === b.dataset.world);
    if (e) chooseWorld(e);
  });
  map.on("mousemove", (ev) => { if (worldAt(map, ev.point)) map.getCanvas().style.cursor = "pointer"; else if (map.getCanvas().style.cursor === "pointer") map.getCanvas().style.cursor = ""; });
}
