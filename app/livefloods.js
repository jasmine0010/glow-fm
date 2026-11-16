const GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH";
const CMR_TITLES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json";
const WORLD_DAYS = 60, WORLD_TIMEOUT_MS = 8000;

const ymd = (t) => new Date(t).toISOString().slice(0, 10);

const worldLeave = new AbortController();
addEventListener("pagehide", () => worldLeave.abort());

async function withTimeout(url) {
  const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), WORLD_TIMEOUT_MS), stop = () => ctl.abort();
  worldLeave.signal.addEventListener("abort", stop);
  try { return await fetch(url, { signal: ctl.signal }); } finally { clearTimeout(timer); worldLeave.signal.removeEventListener("abort", stop); }
}

function toEvent(f) {
  const p = f.properties, g = f.geometry;
  const [lon, lat] = g && g.type === "Point" ? g.coordinates : [(f.bbox[0] + f.bbox[2]) / 2, (f.bbox[1] + f.bbox[3]) / 2];
  return { id: String(p.eventid), name: p.name || `Flood in ${p.country}`, country: p.country, alert: p.alertlevel, current: String(p.iscurrent) === "true",
    from: Date.parse(`${p.fromdate}Z`), to: Date.parse(`${p.todate}Z`), lat, lon, report: p.url && p.url.report };
}

async function fetchGdacs() {
  const to = Date.now(), from = to - WORLD_DAYS * 864e5, out = new Map();
  for (let page = 1; page <= 5; page++) {
    const q = `eventlist=FL&fromdate=${ymd(from)}&todate=${ymd(to)}&alertlevel=green;orange;red&pagesize=100&pagenumber=${page}`;
    const r = await withTimeout(`${GDACS_URL}?${q}`);
    if (r.status === 204 || r.status === 404) break;
    if (!r.ok) throw new Error(`GDACS answered ${r.status}`);
    const features = (await r.json()).features || [];
    for (const f of features) { const e = toEvent(f); if (Number.isFinite(e.lat) && (!out.has(e.id) || e.to > out.get(e.id).to)) out.set(e.id, e); }
    if (features.length < 100) break;
  }
  return [...out.values()];
}

const NISAR_SPLIT = Date.parse("2026-10-21T17:07:00Z");
const NISAR_OLD = "NISAR_L2_GCOV_PROVISIONAL_V1", NISAR_NEW = "NISAR_L2_GCOV_V1";

const METHOD_KIND = /_4005_DHDH_/;
const COVERAGE_CACHE_MS = 3600 * 1000;

async function scenesOver(e, end) {
  const key = `glowfm-cov1-${e.id}-${e.to}`;
  try { const c = JSON.parse(localStorage.getItem(key)); if (c && Date.now() - c.at < COVERAGE_CACHE_MS) return c; } catch {}
  const asks = [];
  if (end > NISAR_SPLIT) asks.push([NISAR_NEW, Math.max(e.from, NISAR_SPLIT), end]);
  if (e.from < NISAR_SPLIT) asks.push([NISAR_OLD, e.from, Math.min(end, NISAR_SPLIT)]);
  let passes = 0, method = 0;
  for (const [short, a, b] of asks) {
    if (b <= a) continue;
    const q = new URLSearchParams({ short_name: short, point: `${e.lon.toFixed(4)},${e.lat.toFixed(4)}`, temporal: `${new Date(a).toISOString()},${new Date(b).toISOString()}`, page_size: "200" });
    const r = await withTimeout(`${CMR_TITLES_URL}?${q}`);
    if (!r.ok) throw new Error(`NASA's catalog answered ${r.status}`);
    const names = ((await r.json()).feed.entry || []).map((x) => x.title || x.producer_granule_id || "");
    passes += names.length;
    method += names.filter((n) => METHOD_KIND.test(n)).length;
  }
  const got = { passes, method_passes: method, at: Date.now() };
  try { localStorage.setItem(key, JSON.stringify(got)); } catch {}
  return got;
}

async function liveCoverage() {
  const now = Date.now(), events = (await fetchGdacs()).filter((e) => Math.min(e.to, now) > e.from);
  if (!events.length) throw new Error("GDACS listed no floods");
  const floods = new Array(events.length);
  let next = 0;
  const worker = async () => {
    while (next < events.length) {
      const k = next++, e = events[k], s = await scenesOver(e, Math.min(e.to, now));
      floods[k] = { id: e.id, country: e.country, lon: e.lon, lat: e.lat, passes: s.passes, method_passes: s.method_passes };
    }
  };
  await Promise.all([0, 1, 2, 3].map(worker));
  return { live: true, floods, summary: { floods: floods.length, covered: floods.filter((f) => f.passes).length,
    covered_by_method_kind: floods.filter((f) => f.method_passes).length, gdacs_window_days: WORLD_DAYS, checked_utc: new Date(now).toISOString() } };
}
