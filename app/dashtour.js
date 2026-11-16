
const TOUR_STEPS = [
  { at: ["#show-switch"], title: "What the map shows", text: "NISAR's flood map, the estimate from river gauges and lidar, or both laid over each other to see where they agree." },
  { at: [".flood-tabs", "[data-panel='left']"], title: "Choose a flood", text: "Floods reported worldwide now, the US rivers GLOWfm was tested on, or any place's risk of floods hidden under trees." },
  { at: ["#sel-river .readouts", "[data-panel='right']"], title: "NISAR's answer", text: "How much NISAR mapped as flooded, how well it matched the river's gauges, and a trust light that says how far to trust it." },
  { at: ["#sel-river .what-if"], title: "What if the river rose?", text: "Drag to raise every gauge and watch the estimated flooding and the roads under it grow." },
  { at: ["#time-bar"], title: "Through time", text: "Drag back through the flood one NISAR pass at a time, where each map is scored. The right end is today's river levels, live." },
  { at: ["#layers-box"], title: "Map layers", text: "Roads under water, river gauges, reported floods and the blind-spot map, each on or off." },
  { at: ["#bar-more"], title: "More", text: "Copy a link to this view, download the gauge readings, or take this tour again." },
];
const TOUR_SEEN = "glowfm-dash-tour-seen";
const tourState = { k: -1, steps: [], box: null, pop: null, opener: null };

function tourTarget(step) {
  for (const sel of step.at) {
    const el = document.querySelector(sel);
    if (!el || el.closest("[hidden]")) continue;
    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < innerHeight) return el;
  }
  return null;
}

function tourPlace() {
  const step = tourState.steps[tourState.k], el = tourTarget(step);
  if (!el) return tourGo(tourState.k + (tourState.dir || 1));
  const r = el.getBoundingClientRect(), pad = 6, { box, pop } = tourState;
  Object.assign(box.style, { left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + 2 * pad}px`, height: `${r.height + 2 * pad}px` });
  pop.querySelector(".tour-count").textContent = `${tourState.k + 1} of ${tourState.steps.length}`;
  pop.querySelector(".tour-title").textContent = step.title;
  pop.querySelector(".tour-text").textContent = step.text;
  pop.querySelector(".tour-back").hidden = tourState.k === 0;
  pop.querySelector(".tour-skip").hidden = tourState.k === tourState.steps.length - 1;
  pop.querySelector(".tour-next").textContent = tourState.k === tourState.steps.length - 1 ? "Done" : "Next";
  const W = pop.offsetWidth, H = pop.offsetHeight, gap = 14, m = 10;
  const fitsY = (y) => Math.max(m, Math.min(innerHeight - H - m, y)), fitsX = (x) => Math.max(m, Math.min(innerWidth - W - m, x));
  let x, y, side;
  if (r.top < 70 && r.bottom + gap + H + m <= innerHeight) { x = fitsX(r.left + r.width / 2 - W / 2); y = r.bottom + gap; side = "below"; }
  else if (r.right + gap + W + m <= innerWidth) { x = r.right + gap; y = fitsY(r.top + r.height / 2 - H / 2); side = "right"; }
  else if (r.left - gap - W - m >= 0) { x = r.left - gap - W; y = fitsY(r.top + r.height / 2 - H / 2); side = "left"; }
  else if (r.bottom + gap + H + m <= innerHeight) { x = fitsX(r.left + r.width / 2 - W / 2); y = r.bottom + gap; side = "below"; }
  else { x = fitsX(r.left + r.width / 2 - W / 2); y = Math.max(m, r.top - gap - H); side = "above"; }
  pop.dataset.side = side;
  pop.style.left = `${x}px`; pop.style.top = `${y}px`;
  const ax = Math.max(16, Math.min(W - 16, r.left + r.width / 2 - x)), ay = Math.max(16, Math.min(H - 16, r.top + r.height / 2 - y));
  pop.style.setProperty("--ax", `${ax}px`); pop.style.setProperty("--ay", `${ay}px`);
  pop.querySelector(".tour-next").focus({ preventScroll: true });
}

function tourGo(k) {
  if (k < 0) return;
  if (k >= tourState.steps.length) return tourEnd();
  tourState.dir = k < tourState.k ? -1 : 1;
  tourState.k = k;
  tourPlace();
}

function tourEnd() {
  tourState.k = -1;
  tourState.box?.remove(); tourState.pop?.remove();
  tourState.box = tourState.pop = null;
  removeEventListener("resize", tourPlace);
  removeEventListener("keydown", tourKeys, true);
  try { localStorage.setItem(TOUR_SEEN, "1"); } catch {  }
  if (tourState.opener && tourState.opener.isConnected) tourState.opener.focus({ preventScroll: true });
}

function tourKeys(e) {
  if (tourState.k < 0) return;
  if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); tourEnd(); }
  else if (e.key === "ArrowRight") { e.preventDefault(); tourGo(tourState.k + 1); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); tourGo(tourState.k - 1); }
}

function tourStart() {
  if (tourState.k >= 0) return;
  if (typeof setPanel === "function" && state.panel) setPanel(state.panel);
  tourState.opener = document.activeElement;
  tourState.steps = TOUR_STEPS.filter((s) => tourTarget(s));
  if (!tourState.steps.length) return;
  const box = document.createElement("div");
  box.className = "tour-spot";
  box.setAttribute("aria-hidden", "true");
  const pop = document.createElement("div");
  pop.className = "tour-pop";
  pop.setAttribute("role", "dialog");
  pop.setAttribute("aria-live", "polite");
  pop.setAttribute("aria-label", "Dashboard tour");
  pop.innerHTML = `<p class="tour-count"></p><button type="button" class="tour-close" aria-label="Close the tour">×</button>
    <h2 class="tour-title"></h2><p class="tour-text"></p>
    <p class="tour-nav"><button type="button" class="link-btn tour-skip">Skip tour</button><button type="button" class="link-btn tour-back">Back</button><button type="button" class="btn-primary tour-next">Next</button></p>`;
  document.body.append(box, pop);
  pop.querySelector(".tour-close").addEventListener("click", tourEnd);
  pop.querySelector(".tour-skip").addEventListener("click", tourEnd);
  pop.querySelector(".tour-back").addEventListener("click", () => tourGo(tourState.k - 1));
  pop.querySelector(".tour-next").addEventListener("click", () => tourGo(tourState.k + 1));
  Object.assign(tourState, { box, pop, k: -1 });
  addEventListener("resize", tourPlace);
  addEventListener("keydown", tourKeys, true);
  tourGo(0);
}

(function wireTour() {
  document.querySelectorAll("[data-tour]").forEach((b) => b.addEventListener("click", () => { const m = document.getElementById("bar-more"); if (m) m.open = false; tourStart(); }));
  let seen = false;
  try { seen = localStorage.getItem(TOUR_SEEN) === "1"; } catch { seen = true; }
  const asked = new URLSearchParams(location.search).get("tour") === "1";
  if (asked || !seen) {
    let tries = 0;
    const wait = setInterval(() => {
      const ready = typeof state === "object" && state.mapReady && state.pack && !state.flying;
      if (ready || ++tries > 60) { clearInterval(wait); if (ready) setTimeout(settled, 1200); }
    }, 250);
    const settled = () => { if (state.flying) return setTimeout(settled, 300); tourStart(); };
  }
})();
