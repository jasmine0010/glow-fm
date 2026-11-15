// The orbit rail: NISAR's ground track down the right edge of the page. A satellite travels it as you scroll, through
// a major station at the opening and at each act, and a smaller one per section (the journey's parts too); each jumps
// there when clicked.
// The track is a smooth wave, an illustration of an orbit swinging pole to pole, not NISAR's position. (Its real
// latitude at 98.4° inclination is nearly a triangle wave, which drew as straight runs with sharp corners.) On phones it becomes a thin progress line under the top bar, with a sections menu.

const ORBIT = { stops: [], nav: null, sat: null, done: null, line: null, active: -1, queued: false, pts: [] };
const ORBIT_W = 28;

// The track: a sine wave, so it swings side to side and back with no corners.
function orbitTrack(n = 400, waves = 1.5) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const s = i / n;
    pts.push([ORBIT_W / 2 + (ORBIT_W / 2 - 5) * Math.sin(s * waves * 2 * Math.PI), s * 1000]);
  }
  return pts;
}

function orbitStops() {
  const stops = [];
  // Pages without acts keep one major station per section.
  const acts = document.querySelector("[data-act-card]") !== null;
  document.querySelectorAll("[data-station]").forEach((el) => {
    const major = !acts || "actCard" in el.dataset || el.id === "finding" || el.tagName === "FOOTER";
    if (el.id === "journey" && typeof LANTERN_ACTS !== "undefined") {
      LANTERN_ACTS.forEach((a, k) => stops.push({ el, act: k, label: k ? a.label : `${el.dataset.station}: ${a.label}`, weight: k || acts ? 0.5 : 1, sub: k > 0 || acts, part: k > 0 }));
    } else stops.push({ el, label: el.dataset.station, weight: major ? 1 : 0.5, sub: !major });
  });
  const total = stops.reduce((s, x, k) => s + (k ? x.weight : 0), 0);
  let acc = 0;
  stops.forEach((s, k) => { if (k) acc += s.weight; s.pos = acc / total; });
  return stops;
}

// Where on the page each station is reached: a section when its top passes 40% of the screen; a journey part where
// lanternJump would put it.
function orbitMeasure() {
  const top = (el) => el.getBoundingClientRect().top + scrollY;
  ORBIT.stops.forEach((s, k) => {
    if (s.act !== undefined) {
      const sec = s.el, total = LANTERN_ACTS.reduce((a, b) => a + b.weight, 0), before = LANTERN_ACTS.slice(0, s.act).reduce((a, b) => a + b.weight, 0) / total;
      s.y = top(sec) + before * (sec.offsetHeight - $("lantern-stage").offsetHeight) - (s.act ? 0 : innerHeight * 0.4);
    } else s.y = k === 0 ? 0 : top(s.el) - innerHeight * 0.4;
  });
  const last = ORBIT.stops[ORBIT.stops.length - 1];
  last.y = Math.min(last.y, document.documentElement.scrollHeight - innerHeight);
  for (let k = 1; k < ORBIT.stops.length; k++) ORBIT.stops[k].y = Math.max(ORBIT.stops[k].y, ORBIT.stops[k - 1].y + 1);
  orbitUpdate();
}

function orbitAt(p) {
  const pts = ORBIT.pts, i = Math.min(pts.length - 2, Math.floor(p * (pts.length - 1))), f = p * (pts.length - 1) - i;
  return pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f;
}

function orbitUpdate() {
  ORBIT.queued = false;
  const S = ORBIT.stops, s = scrollY;
  if (!S.length) return;
  let k = 0;
  while (k < S.length - 1 && S[k + 1].y <= s) k++;
  const next = S[k + 1], p = next ? S[k].pos + (next.pos - S[k].pos) * Math.max(0, Math.min(1, (s - S[k].y) / (next.y - S[k].y))) : 1;
  const h = ORBIT.nav.clientHeight;
  ORBIT.sat.style.transform = `translate(${orbitAt(p) - 5}px, ${p * h - 5}px)`;
  ORBIT.done.style.strokeDasharray = `${p} 1`;
  ORBIT.line.style.setProperty("--p", p.toFixed(4));
  if (k !== ORBIT.active) {
    const was = ORBIT.active;
    ORBIT.active = k;
    ORBIT.nav.querySelectorAll(".orbit-stop").forEach((b, i) => { b.classList.toggle("on", i === k); b.classList.toggle("past", i < k); if (i === k) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current"); });
    if (was >= 0) {
      const b = ORBIT.nav.querySelectorAll(".orbit-stop")[k];
      b.classList.remove("flare"); void b.offsetWidth; b.classList.add("flare");
      if (typeof soundTick === "function") soundTick(S[k].sub ? 0.012 : 0.022);
    }
  }
}

function orbitGo(s) {
  if (s.act !== undefined) { lanternJump(s.act); return; }
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (s.el.id === "finding") scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
  else s.el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
}

function setupOrbit() {
  ORBIT.stops = orbitStops();
  ORBIT.pts = orbitTrack();
  const d = ORBIT.pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(1)}`).join(" ");
  const nav = document.createElement("nav");
  nav.className = "orbit";
  nav.setAttribute("aria-label", "Sections of the page, along NISAR's orbit");
  nav.innerHTML = `<svg class="orbit-track" viewBox="0 0 ${ORBIT_W} 1000" preserveAspectRatio="none" aria-hidden="true"><path class="orbit-path" d="${d}" pathLength="1"/><path class="orbit-done" d="${d}" pathLength="1"/></svg>
    <ol>${ORBIT.stops.map((s, k) => `<li style="top:${(100 * s.pos).toFixed(2)}%"><button type="button" class="orbit-stop${s.sub ? " sub" : ""}" data-k="${k}" style="--x:${(orbitAt(s.pos) - ORBIT_W / 2).toFixed(1)}px"><i aria-hidden="true"></i><span class="orbit-label">${s.label}</span></button></li>`).join("")}</ol>
    <span class="orbit-sat" aria-hidden="true"></span>`;
  document.body.appendChild(nav);
  ORBIT.nav = nav;
  ORBIT.sat = nav.querySelector(".orbit-sat");
  ORBIT.done = nav.querySelector(".orbit-done");
  nav.addEventListener("click", (e) => { const b = e.target.closest("[data-k]"); if (b) orbitGo(ORBIT.stops[Number(b.dataset.k)]); });

  // Phones: a progress line under the top bar, with a tick per section, and a menu of the sections.
  const line = document.createElement("div");
  line.className = "orbit-line";
  line.setAttribute("aria-hidden", "true");
  line.innerHTML = ORBIT.stops.filter((s) => !s.sub).map((s) => `<i style="left:${(100 * s.pos).toFixed(2)}%"></i>`).join("");
  document.querySelector(".topbar").appendChild(line);
  ORBIT.line = line;
  const menu = document.getElementById("sections-menu");
  if (menu) {
    // Acts as headings, their sections under them; the journey's parts stay on the rail only.
    menu.querySelector(".menu-list").innerHTML = ORBIT.stops.map((s, k) => (s.part ? "" : `<button type="button" data-k="${k}"${s.sub ? ' class="menu-sub"' : ""}>${s.el.dataset.station}</button>`)).join("") + '<a class="menu-page" href="evidence.html">Results: figures and tables</a>';
    menu.addEventListener("click", (e) => { const b = e.target.closest("[data-k]"); if (b) { menu.open = false; orbitGo(ORBIT.stops[Number(b.dataset.k)]); } });
  }

  const queue = () => { if (!ORBIT.queued) { ORBIT.queued = true; requestAnimationFrame(orbitUpdate); } };
  addEventListener("scroll", queue, { passive: true });
  let again;
  const remeasure = () => { clearTimeout(again); again = setTimeout(orbitMeasure, 120); };
  addEventListener("resize", remeasure);
  if ("ResizeObserver" in window) new ResizeObserver(remeasure).observe(document.body);
  orbitMeasure();
}
