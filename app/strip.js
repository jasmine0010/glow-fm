
function passStrip(box, { t0, t1, rows, zero = null, events = [], key = [], scrub = null, onKey = null, label = "", tail = null }) {
  const W = 1000, H = 120, top = 18, bottom = 78;
  const fa = tail ? 0.8 : 1, fg = tail ? 0.06 : 0;
  const xa = (t) => ((t - t0) / (t1 - t0)) * W * fa;
  const xb = (t) => W * (fa + fg) + ((Math.min(tail.t1, Math.max(tail.t0, t)) - tail.t0) / Math.max(1, tail.t1 - tail.t0)) * W * (1 - fa - fg);
  const x = (t) => (tail && t > t1 ? xb(t) : xa(t));
  const part = (t) => (t >= t0 && t <= t1 ? 1 : tail && t >= tail.t0 && t <= tail.t1 ? 2 : 0);
  const all = rows.flatMap((r) => r.filter((p) => !tail || part(p[0])).map((p) => p[1]));
  const lo = Math.min(...all, zero ? 0 : Infinity), hi = Math.max(...all, zero ? 0.5 : -Infinity);
  const y = (v) => top + ((hi - v) / Math.max(1e-6, hi - lo)) * (bottom - top);
  const dashes = ["", "7 5", "2 4"];
  const pathOf = (r) => {
    if (!tail) return r.map(([tt, v], i) => `${i ? "L" : "M"}${x(tt).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
    let prev = 0;
    return r.map(([tt, v]) => { const p = part(tt); if (!p) { prev = 0; return ""; } const s = `${p !== prev ? "M" : "L"}${x(tt).toFixed(1)} ${y(v).toFixed(1)}`; prev = p; return s; }).join(" ");
  };
  const lines = rows.map((r, k) => `<path class="ls-gauge" ${dashes[k % 3] ? `stroke-dasharray="${dashes[k % 3]}"` : ""} d="${pathOf(r)}"/>`).join("");
  const shown = events.map((e, k) => [e, k]).filter(([e]) => e.t >= t0 && e.t <= t1);
  const marks = shown.map(([e, k]) => `<g class="ls-pass ls-${e.who}" data-k="${k}" transform="translate(${x(e.t).toFixed(1)},0)"><line y1="${top - 6}" y2="${bottom + 4}"/></g>`).join("");
  const dots = shown.map(([e, k]) => `<i class="ls-mark ls-mark-${e.who}${e.who !== "nisar" && !e.covered ? " ls-miss" : ""}" data-k="${k}" style="left:${((x(e.t) / W) * 100).toFixed(2)}%;top:${(((bottom + 16) / H) * 100).toFixed(2)}%"></i>`).join("");
  const pct = (f) => `${(f * 100).toFixed(2)}%`;
  const tailHtml = tail ? `<span class="ls-break" style="left:${pct(fa)};width:${pct(fg)}" title="${tail.gap || ""}">${tail.gap ? `<b>${tail.gap}</b>` : ""}</span>` +
    `<span class="ls-tail" style="left:${pct(fa + fg)};width:${pct(1 - fa - fg)}">${tail.text || ""}</span>` : "";
  box.innerHTML = `<div class="ls-plot"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">${zero ? `<line class="ls-flood" x1="0" x2="${W}" y1="${y(0)}" y2="${y(0)}"/>` : ""}${lines}${marks}<line class="ls-head" y1="4" y2="${H - 4}"/></svg>${dots}${tailHtml}</div>` +
    (key.length ? `<div class="ls-key">${key.map(([cls, text]) => `<span><i class="${cls}"></i>${text}</span>`).join("")}</div>` : "");
  const head = box.querySelector(".ls-head");
  const strip = {
    x: (t) => (x(t) / W) * 100,
    head(t) { const px = tail && t > t1 ? xb(t) : xa(Math.max(t0, Math.min(t1, t))); head.setAttribute("x1", px); head.setAttribute("x2", px); },
    select(k) { box.querySelectorAll(".ls-pass, .ls-mark").forEach((g) => g.classList.toggle("on", Number(g.dataset.k) === k)); },
  };
  if (box._stripListeners) box._stripListeners.abort();
  if (scrub) {
    const svg = box.querySelector("svg"), on = { signal: (box._stripListeners = new AbortController()).signal };
    box.classList.add("ls-scrub");
    box.tabIndex = 0;
    box.setAttribute("role", "slider");
    if (label) box.setAttribute("aria-label", label);
    const at = (ev) => { const r = svg.getBoundingClientRect(), f = Math.max(0, Math.min(1, (ev.clientX - r.left) / r.width)); return tail && f > fa ? tail.t1 : t0 + (f / fa) * (t1 - t0); };
    box.addEventListener("pointerdown", (ev) => { box.setPointerCapture(ev.pointerId); scrub(at(ev)); }, on);
    box.addEventListener("pointermove", (ev) => { if (box.hasPointerCapture(ev.pointerId)) scrub(at(ev)); }, on);
    box.addEventListener("keydown", (ev) => {
      const step = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }[ev.key];
      if (!step || !onKey) return;
      ev.preventDefault();
      onKey(step);
    }, on);
  }
  return strip;
}
