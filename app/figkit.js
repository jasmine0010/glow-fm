// figkit: a small SVG plotting kit for the site's scientific figures (figures.js), styled like a journal figure made
// with matplotlib: boxed axes with outward ticks, minor ticks on log and date axes, no gridlines, one sans-serif face,
// thin lines, small markers, capped error bars and framed legends inside the axes. No library. Figures are drawn at the
// container's real width, so text stays readable on a phone, and redraw when it changes. Colours come from CSS tokens,
// so a figure follows the night theme or, inside .paper, the white print theme. Downloads: SVG, PNG (2x) and CSV.

const FK_NS = "http://www.w3.org/2000/svg";
const FK_TICK = 4;     // major tick length, px (outward)

function fkEl(parent, tag, attrs = {}, text) {
  const el = document.createElementNS(FK_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  if (parent) parent.appendChild(el);
  return el;
}

// ---------- scales ----------
function fkNice(lo, hi, n = 5) {
  const span = hi - lo || 1, step0 = span / n, mag = 10 ** Math.floor(Math.log10(step0)), err = step0 / mag;
  const step = (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1) * mag;
  const ticks = [];
  for (let t = Math.ceil(lo / step - 1e-9) * step; t <= hi + 1e-9; t += step) ticks.push(+t.toFixed(10));
  return ticks;
}
function fkLinear(d0, d1, r0, r1) {
  const f = (v) => r0 + ((v - d0) / (d1 - d0)) * (r1 - r0);
  f.invert = (p) => d0 + ((p - r0) / (r1 - r0)) * (d1 - d0);
  f.ticks = (n = 5) => fkNice(Math.min(d0, d1), Math.max(d0, d1), n);
  f.domain = [d0, d1];
  return f;
}
function fkLog(d0, d1, r0, r1) {
  const l0 = Math.log10(d0), l1 = Math.log10(d1), f = (v) => r0 + ((Math.log10(Math.max(v, d0)) - l0) / (l1 - l0)) * (r1 - r0);
  f.invert = (p) => 10 ** (l0 + ((p - r0) / (r1 - r0)) * (l1 - l0));
  f.ticks = () => { const t = []; for (let e = Math.ceil(l0); e <= Math.floor(l1); e++) t.push(10 ** e); return t; };
  f.minor = () => { const t = []; for (let e = Math.floor(l0); e <= Math.ceil(l1); e++) for (let m = 2; m <= 9; m++) { const v = m * 10 ** e; if (v > d0 && v < d1) t.push(v); } return t; };
  f.domain = [d0, d1];
  return f;
}
function fkTime(t0, t1, r0, r1) {
  const f = fkLinear(t0, t1, r0, r1), day = 864e5;
  f.ticks = (n = 6) => {
    const span = (t1 - t0) / day, step = [1, 2, 3, 7, 14, 30].find((s) => span / s <= n) || 30, out = [];
    for (let t = Math.ceil(t0 / day) * day; t <= t1; t += step * day) out.push(t);
    return out;
  };
  f.minor = () => { const out = []; if ((t1 - t0) / day > 62) return out; for (let t = Math.ceil(t0 / day) * day; t <= t1; t += day) out.push(t); return out; };
  return f;
}
const fkFmt = (v) => (Math.abs(v) >= 1e6 ? `${+(v / 1e6).toFixed(1)}M` : Math.abs(v) >= 1e4 ? `${+(v / 1e3).toFixed(0)}k` : Math.abs(v) >= 1000 ? v.toLocaleString("en-US") : +v.toFixed(Math.abs(v) < 1 && v !== 0 ? 2 : 1) + "");
const fkDay = (t) => new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const fkMinus = (s) => String(s).replace(/^-/, "−");   // a true minus sign, as typeset

// ---------- a figure and its panels ----------
// fkFigure(box, { name, height(W) -> px, draw(svg, W, H, tip), csv() -> rows }) draws now and on resize, and adds the downloads.
function fkFigure(box, spec) {
  box.classList.add("fk");
  const stage = box.querySelector(".fk-stage") || fkMount(box, spec);
  const render = () => {
    const W = Math.max(300, Math.round(stage.clientWidth)), H = Math.round(spec.height(W));
    stage.querySelector("svg")?.remove();
    const svg = fkEl(null, "svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "fk-svg", role: "img", "aria-label": spec.label || spec.name });
    fkEl(svg, "rect", { x: 0, y: 0, width: W, height: H, class: "fk-bg" });
    stage.prepend(svg);
    spec.draw(svg, W, H, box.querySelector(".fk-tip"));
    // a legend that wrapped onto another row can reach past the planned height: grow to fit what was drawn
    const bb = svg.getBBox(), need = Math.ceil(bb.y + bb.height + 6);
    if (need > H) { svg.setAttribute("height", need); svg.setAttribute("viewBox", `0 0 ${W} ${need}`); svg.querySelector(".fk-bg").setAttribute("height", need); }
  };
  render();
  let again, lastW = stage.clientWidth;
  addEventListener("resize", () => { clearTimeout(again); again = setTimeout(() => { if (Math.abs(stage.clientWidth - lastW) > 4) { lastW = stage.clientWidth; render(); } }, 160); });
  return { render };
}

function fkMount(box, spec) {
  const stage = document.createElement("div");
  stage.className = "fk-stage";
  const tip = document.createElement("div");
  tip.className = "fk-tip";
  tip.hidden = true;
  stage.appendChild(tip);
  box.prepend(stage);
  if (spec.downloads !== false) {
    const bar = document.createElement("div");
    bar.className = "fk-downloads";
    bar.innerHTML = `Download <button type="button" data-k="svg">SVG</button> · <button type="button" data-k="png">PNG</button>${spec.csv ? ' · <button type="button" data-k="csv">data (CSV)</button>' : ""}`;
    bar.addEventListener("click", (e) => { const b = e.target.closest("[data-k]"); if (b) fkDownload(box, spec, b.dataset.k); });
    box.appendChild(bar);
  }
  return stage;
}

// A panel: an inner plotting area, with a bold panel letter and a short title above it.
function fkPanel(svg, { x, y, w, h, letter, title, m = { t: 30, r: 18, b: 42, l: 56 } }) {
  const g = fkEl(svg, "g", { transform: `translate(${x},${y})` });
  if (letter) fkEl(g, "text", { x: 0, y: 13, class: "fk-letter" }, letter);
  if (title) {
    // a title wider than its panel (on a phone) is set smaller rather than cut off
    const t = fkEl(g, "text", { x: letter ? 16 : 0, y: 13, class: "fk-ptitle" }, title), room = w - (letter ? 16 : 0) - 2, len = t.getComputedTextLength();
    if (len > room) t.style.fontSize = `${Math.max(9, (12 * room) / len).toFixed(1)}px`;
  }
  const inner = fkEl(g, "g", { transform: `translate(${m.l},${m.t})` });
  return { g: inner, w: w - m.l - m.r, h: h - m.t - m.b, x: x + m.l, y: y + m.t };
}

// Axes as matplotlib draws them: a box, outward major ticks with labels on the left and bottom, minor ticks on log and
// date axes, gridlines off unless asked for. xticks/yticks: [] hides that axis's ticks.
function fkAxes(p, sx, sy, { xlabel, ylabel, xticks, yticks, xfmt = fkFmt, yfmt = fkFmt, grid = false, ylabelX = -42 } = {}) {
  const inX = (v) => sx(v) >= -0.5 && sx(v) <= p.w + 0.5, inY = (v) => sy(v) >= -0.5 && sy(v) <= p.h + 0.5;
  const xs = (xticks || sx.ticks(Math.max(3, Math.round(p.w / 80)))).filter(inX), ys = (yticks || sy.ticks(Math.max(3, Math.round(p.h / 45)))).filter(inY);
  if (grid) ys.forEach((v) => fkEl(p.g, "line", { x1: 0, x2: p.w, y1: sy(v), y2: sy(v), class: "fk-grid" }));
  fkEl(p.g, "rect", { x: 0, y: 0, width: p.w, height: p.h, class: "fk-spine" });
  xs.forEach((v) => { fkEl(p.g, "line", { x1: sx(v), x2: sx(v), y1: p.h, y2: p.h + FK_TICK, class: "fk-spine" }); fkEl(p.g, "text", { x: sx(v), y: p.h + FK_TICK + 12, class: "fk-tick", "text-anchor": "middle" }, fkMinus(xfmt(v))); });
  ys.forEach((v) => { fkEl(p.g, "line", { x1: -FK_TICK, x2: 0, y1: sy(v), y2: sy(v), class: "fk-spine" }); fkEl(p.g, "text", { x: -FK_TICK - 3, y: sy(v) + 4, class: "fk-tick", "text-anchor": "end" }, fkMinus(yfmt(v))); });
  if (!xticks && sx.minor) sx.minor().filter(inX).forEach((v) => fkEl(p.g, "line", { x1: sx(v), x2: sx(v), y1: p.h, y2: p.h + 2, class: "fk-spine" }));
  if (!yticks && sy.minor) sy.minor().filter(inY).forEach((v) => fkEl(p.g, "line", { x1: -2, x2: 0, y1: sy(v), y2: sy(v), class: "fk-spine" }));
  if (xlabel) fkEl(p.g, "text", { x: p.w / 2, y: p.h + 32, class: "fk-label", "text-anchor": "middle" }, xlabel);
  if (ylabel) fkEl(p.g, "text", { x: -p.h / 2, y: ylabelX, class: "fk-label", "text-anchor": "middle", transform: "rotate(-90)" }, ylabel);
}

const fkPath = (pts) => pts.filter((p) => p && Number.isFinite(p[0]) && Number.isFinite(p[1])).map((p, k) => `${k ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");

// Markers, named as in matplotlib: o circle, s square, ^ triangle, D diamond. r is the half-size in px.
function fkMark(g, shape, x, y, cls, r = 3.5, extra = {}) {
  if (shape === "s") return fkEl(g, "rect", { x: x - r * 0.9, y: y - r * 0.9, width: r * 1.8, height: r * 1.8, class: cls, ...extra });
  if (shape === "^") return fkEl(g, "path", { d: `M${x} ${y - r * 1.15}L${x + r * 1.1} ${y + r * 0.8}L${x - r * 1.1} ${y + r * 0.8}Z`, class: cls, ...extra });
  if (shape === "D") return fkEl(g, "path", { d: `M${x} ${y - r * 1.2}L${x + r} ${y}L${x} ${y + r * 1.2}L${x - r} ${y}Z`, class: cls, ...extra });
  return fkEl(g, "circle", { cx: x, cy: y, r, class: cls, ...extra });
}

// An error bar from (x1, y1) to (x2, y2) with short end caps.
function fkErr(g, x1, y1, x2, y2, cls, cap = 3) {
  fkEl(g, "line", { x1, y1, x2, y2, class: cls, "stroke-width": 1 });
  const vertical = Math.abs(x2 - x1) < Math.abs(y2 - y1);
  [[x1, y1], [x2, y2]].forEach(([x, y]) => fkEl(g, "line", vertical ? { x1: x - cap, x2: x + cap, y1: y, y2: y, class: cls, "stroke-width": 1 } : { x1: x, x2: x, y1: y - cap, y2: y + cap, class: cls, "stroke-width": 1 }));
}

// One legend glyph. Item: [kind, class, text, dash]; kind is "line", "patch", "errbar" or a marker shape (o s ^ D).
function fkGlyph(g, kind, cls, dash) {
  if (kind === "line") fkEl(g, "line", { x1: 0, x2: 18, y1: -4, y2: -4, class: cls, "stroke-width": 1.5, "stroke-dasharray": dash });
  else if (kind === "patch") fkEl(g, "rect", { x: 1, y: -9, width: 16, height: 9, class: cls, "fill-opacity": 0.55 });
  else if (kind === "errbar") { fkErr(g, 2, -4, 16, -4, cls.split(" ").find((c) => c.startsWith("s-")) || "s-ink"); fkMark(g, "o", 9, -4, cls); }
  else fkMark(g, kind, 9, -4, cls);
}

// A framed legend inside the axes, one entry per row, like matplotlib's ax.legend(loc=...). corner: tl tr bl br cl cr.
function fkKey(p, items, corner = "tr") {
  const g = fkEl(p.g, "g", { class: "fk-legend" }), frame = fkEl(g, "rect", { class: "fk-legend-box", rx: 2 });
  let wmax = 0;
  items.forEach(([kind, cls, text, dash], k) => {
    const it = fkEl(g, "g", { transform: `translate(8,${18 + k * 17})` });
    fkGlyph(it, kind, cls, dash);
    const t = fkEl(it, "text", { x: 24, y: 0, class: "fk-tick" }, text);
    wmax = Math.max(wmax, 24 + (t.getComputedTextLength() || text.length * 6));
  });
  const bw = wmax + 16, bh = items.length * 17 + 9, pad = 7;
  frame.setAttribute("width", bw); frame.setAttribute("height", bh);
  const x = corner.endsWith("l") ? pad : p.w - bw - pad, y = corner.startsWith("t") ? pad : corner.startsWith("c") ? (p.h - bh) / 2 : p.h - bh - pad;
  g.setAttribute("transform", `translate(${x.toFixed(1)},${y.toFixed(1)})`);
  return g;
}

// A frameless legend row from (x, y) in figure coordinates, for a legend outside the axes. It wraps onto further rows.
function fkLegend(svg, x, y, items, maxW) {
  const g = fkEl(svg, "g", { transform: `translate(${x},${y})`, class: "fk-legend" }), limit = maxW || +svg.getAttribute("width") - x - 4;
  let dx = 0, dy = 0;
  items.forEach(([kind, cls, text, dash]) => {
    const it = fkEl(g, "g");
    fkGlyph(it, kind, cls, dash);
    const t = fkEl(it, "text", { x: 24, y: 0, class: "fk-tick" }, text), w = 24 + (t.getComputedTextLength() || text.length * 6);
    if (dx > 0 && dx + w > limit) { dx = 0; dy += 17; }
    it.setAttribute("transform", `translate(${dx},${dy})`);
    dx += w + 18;
  });
  return g;
}

// ---------- hover ----------
// Calls find(px, py) on pointer moves inside a panel; it returns { html, x, y } in panel coordinates, or null.
function fkHover(p, tip, find) {
  const hit = fkEl(p.g, "rect", { x: 0, y: 0, width: Math.max(0, p.w), height: Math.max(0, p.h), class: "fk-hit" });
  const mark = fkEl(p.g, "circle", { r: 5, class: "fk-mark", visibility: "hidden" });
  const box = tip.parentElement;
  const move = (e) => {
    const r = hit.getBoundingClientRect(), px = e.clientX - r.left, py = e.clientY - r.top, got = find(px, py);
    if (!got) return leave();
    mark.setAttribute("cx", got.x); mark.setAttribute("cy", got.y); mark.setAttribute("visibility", "visible");
    tip.innerHTML = got.html;
    tip.hidden = false;
    const b = box.getBoundingClientRect();
    tip.style.left = `${Math.min(b.width - tip.offsetWidth - 4, Math.max(4, r.left - b.left + got.x + 12))}px`;
    tip.style.top = `${Math.max(4, r.top - b.top + got.y - tip.offsetHeight - 10)}px`;
  };
  const leave = () => { tip.hidden = true; mark.setAttribute("visibility", "hidden"); };
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerdown", move);
  hit.addEventListener("pointerleave", leave);
}
const fkNearest = (pts, px, py, max = 40) => {
  let best = null, d2 = max * max;
  pts.forEach((p) => { const d = (p.x - px) ** 2 + (p.y - py) ** 2; if (d < d2) { d2 = d; best = p; } });
  return best;
};

// ---------- downloads ----------
const FK_STYLE_PROPS = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-dasharray", "stroke-opacity", "opacity", "font-family", "font-size", "font-weight", "font-style", "letter-spacing", "visibility"];
function fkSerialize(svg) {
  const clone = svg.cloneNode(true), src = svg.querySelectorAll("*"), dst = clone.querySelectorAll("*"), drop = [];
  src.forEach((el, k) => {
    // the hover target and marker are interface, not figure
    if (el.classList.contains("fk-hit") || el.classList.contains("fk-mark")) { drop.push(dst[k]); return; }
    const cs = getComputedStyle(el);
    dst[k].setAttribute("style", FK_STYLE_PROPS.map((p) => `${p}:${cs.getPropertyValue(p)}`).join(";"));
    dst[k].removeAttribute("class");
  });
  drop.forEach((el) => el.remove());
  clone.setAttribute("xmlns", FK_NS);
  return new XMLSerializer().serializeToString(clone);
}
function fkSave(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function fkBlob(box, spec, kind) {
  const svg = box.querySelector(".fk-svg");
  if (kind === "csv") {
    const rows = spec.csv();
    const text = rows.map((r) => r.map((v) => (v === null || v === undefined ? "" : /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v))).join(",")).join("\n");
    return Promise.resolve(new Blob([text + "\n"], { type: "text/csv" }));
  }
  const xml = fkSerialize(svg);
  if (kind === "svg") return Promise.resolve(new Blob([xml], { type: "image/svg+xml" }));
  return new Promise((ok, fail) => {
    const img = new Image(), W = +svg.getAttribute("width"), H = +svg.getAttribute("height"), c = document.createElement("canvas");
    c.width = W * 2; c.height = H * 2;
    img.onload = () => { const ctx = c.getContext("2d"); ctx.scale(2, 2); ctx.drawImage(img, 0, 0); c.toBlob((b) => (b ? ok(b) : fail(new Error("png"))), "image/png"); };
    img.onerror = fail;
    img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
  });
}
function fkDownload(box, spec, kind) {
  fkBlob(box, spec, kind).then((b) => fkSave(b, `glowfm-${spec.name}.${kind}`));
}
