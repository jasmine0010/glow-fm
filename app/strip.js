// The pass strip: river levels over time, every satellite look marked on it, and a playhead. The journey's river and
// "Watch it move" both use it. Plain SVG. With `scrub`, it's also a control: drag along it, or use the arrow keys.
//
// rows:   one array per gauge of [time ms, value], already in the unit the caption names
// zero:   a reference line at value 0 and its label, e.g. "Flood level" (optional)
// events: { t, who: "nisar" | "gfm", covered } for each satellite look
// key:    legend items [[class, text]]

function passStrip(box, { t0, t1, rows, zero = null, events = [], key = [], scrub = null, onKey = null, label = "" }) {
  const W = 1000, H = 120, top = 18, bottom = 78;
  const x = (t) => ((t - t0) / (t1 - t0)) * W;
  const all = rows.flatMap((r) => r.map((p) => p[1]));
  const lo = Math.min(...all, zero ? 0 : Infinity), hi = Math.max(...all, zero ? 0.5 : -Infinity);
  const y = (v) => top + ((hi - v) / Math.max(1e-6, hi - lo)) * (bottom - top);
  const dashes = ["", "7 5", "2 4"];
  const lines = rows.map((r, k) => `<path class="ls-gauge" ${dashes[k % 3] ? `stroke-dasharray="${dashes[k % 3]}"` : ""} d="${r.map(([tt, v], i) => `${i ? "L" : "M"}${x(tt).toFixed(1)} ${y(v).toFixed(1)}`).join(" ")}"/>`).join("");
  // The passes' lines stretch with the strip; their markers sit on top as HTML, so circles stay circles at any width.
  const shown = events.map((e, k) => [e, k]).filter(([e]) => e.t >= t0 && e.t <= t1);
  const marks = shown.map(([e, k]) => `<g class="ls-pass ls-${e.who}" data-k="${k}" transform="translate(${x(e.t).toFixed(1)},0)"><line y1="${top - 6}" y2="${bottom + 4}"/></g>`).join("");
  const dots = shown.map(([e, k]) => `<i class="ls-mark ls-mark-${e.who}${e.who !== "nisar" && !e.covered ? " ls-miss" : ""}" data-k="${k}" style="left:${((x(e.t) / W) * 100).toFixed(2)}%;top:${(((bottom + 16) / H) * 100).toFixed(2)}%"></i>`).join("");
  box.innerHTML = `<div class="ls-plot"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${zero ? `<line class="ls-flood" x1="0" x2="${W}" y1="${y(0)}" y2="${y(0)}"/>` : ""}${lines}${marks}<line class="ls-head" y1="4" y2="${H - 4}"/></svg>${dots}</div>` +
    (key.length ? `<div class="ls-key">${key.map(([cls, text]) => `<span><i class="${cls}"></i>${text}</span>`).join("")}</div>` : "");
  const head = box.querySelector(".ls-head");
  const strip = {
    x: (t) => (x(t) / W) * 100,
    head(t) { const px = x(Math.max(t0, Math.min(t1, t))); head.setAttribute("x1", px); head.setAttribute("x2", px); },
    select(k) { box.querySelectorAll(".ls-pass, .ls-mark").forEach((g) => g.classList.toggle("on", Number(g.dataset.k) === k)); },
  };
  if (scrub) {
    const svg = box.querySelector("svg");
    box.classList.add("ls-scrub");
    box.tabIndex = 0;
    box.setAttribute("role", "slider");
    if (label) box.setAttribute("aria-label", label);
    const at = (ev) => { const r = svg.getBoundingClientRect(); return t0 + Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width)) * (t1 - t0); };
    box.addEventListener("pointerdown", (ev) => { box.setPointerCapture(ev.pointerId); scrub(at(ev)); });
    box.addEventListener("pointermove", (ev) => { if (box.hasPointerCapture(ev.pointerId)) scrub(at(ev)); });
    box.addEventListener("keydown", (ev) => {
      const step = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }[ev.key];
      if (!step || !onKey) return;
      ev.preventDefault();
      onKey(step);
    });
  }
  return strip;
}
