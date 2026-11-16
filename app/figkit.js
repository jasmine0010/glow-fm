
const FK_NS = "http://www.w3.org/2000/svg";
const FK_TICK = 4;

function fkEl(parent, tag, attrs = {}, text) {
  const el = document.createElementNS(FK_NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) el.setAttribute(k, v);
  if (text !== undefined) el.textContent = text;
  if (parent) parent.appendChild(el);
  return el;
}

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
const fkMinus = (s) => String(s).replace(/^-/, "−");

function fkFigure(box, spec) {
  box.classList.add("fk");
  const stage = box.querySelector(".fk-stage") || fkMount(box, spec);
  const render = (again = false) => {
    const W = Math.max(300, Math.round(stage.clientWidth)), H = Math.round(spec.height(W));
    stage.querySelector("svg")?.remove();
    const svg = fkEl(null, "svg", { width: W, height: H, viewBox: `0 0 ${W} ${H}`, class: "fk-svg", role: "img", "aria-label": spec.label || spec.name });
    fkEl(svg, "rect", { x: 0, y: 0, width: W, height: H, class: "fk-bg" });
    stage.prepend(svg);
    svg.fk = { keys: ((spec.keysAbove ||= {})[W] ||= {}), panels: 0, jobs: [], reflow: false };
    spec.draw(svg, W, H, box.querySelector(".fk-tip"));
    svg.fk.jobs.forEach((job) => job());
    if (svg.fk.reflow && !again) { render(true); return; }
    fkFit(svg, W, H);
  };
  render();
  let again, lastW = stage.clientWidth;
  addEventListener("resize", () => { clearTimeout(again); again = setTimeout(() => { if (Math.abs(stage.clientWidth - lastW) > 4) { lastW = stage.clientWidth; render(); } }, 160); });
  return { render: () => { spec.keysAbove = {}; render(); } };
}

function fkFit(svg, W, H) {
  const bb = svg.getBBox(), pad = 2;
  const x0 = Math.min(0, Math.floor(bb.x) - (bb.x < 0 ? pad : 0)), y0 = Math.min(0, Math.floor(bb.y) - (bb.y < 0 ? pad : 0));
  const x1 = Math.max(W, Math.ceil(bb.x + bb.width) + (bb.x + bb.width > W ? pad : 0)), y1 = Math.max(H, Math.ceil(bb.y + bb.height + 6));
  if (x0 === 0 && y0 === 0 && x1 === W && y1 === H) return;
  const vw = x1 - x0, vh = y1 - y0, bg = svg.querySelector(".fk-bg");
  svg.setAttribute("viewBox", `${x0} ${y0} ${vw} ${vh}`);
  svg.setAttribute("height", Math.round((vh * W) / vw));
  Object.entries({ x: x0, y: y0, width: vw, height: vh }).forEach(([k, v]) => bg.setAttribute(k, v));
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

function fkPanel(svg, { x, y, w, h, letter, title, m = { t: 30, r: 18, b: 42, l: 56 } }) {
  const st = svg.fk, id = st ? ++st.panels : 0, above = st && st.keys[id];
  if (above) m = { ...m, t: m.t + above.h + FK_KEY_GAP };
  const g = fkEl(svg, "g", { transform: `translate(${x},${y})` });
  let tx = 0;
  if (letter) tx = fkEl(g, "text", { x: 0, y: 15, class: "fk-letter" }, `${letter})`).getComputedTextLength() + 6;
  if (title) {
    const t = fkEl(g, "text", { x: tx, y: 15, class: "fk-ptitle" }, title), room = w - tx - 2, len = t.getComputedTextLength();
    if (len > room) t.style.fontSize = `${Math.max(9, (12 * room) / len).toFixed(1)}px`;
  }
  const inner = fkEl(g, "g", { transform: `translate(${m.l},${m.t})` });
  return { g: inner, w: w - m.l - m.r, h: h - m.t - m.b, x: x + m.l, y: y + m.t, svg, id, above };
}

function fkTextWidth(svg, text, cls = "fk-tick") {
  const t = fkEl(svg, "text", { x: 0, y: -100, class: cls }, text), w = t.getComputedTextLength();
  t.remove();
  return w;
}

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

function fkShade(p, x0, x1, label, cls = "f-ink", { y0 = 0, y1 = p.h, opacity = 0.09 } = {}) {
  const L = Math.max(0, Math.min(x0, x1)), R = Math.min(p.w, Math.max(x0, x1)), T = Math.max(0, Math.min(y0, y1)), B = Math.min(p.h, Math.max(y0, y1));
  if (R - L < 1 || B - T < 1) return null;
  const r = fkEl(null, "rect", { x: L, y: T, width: R - L, height: B - T, class: `fk-shade ${cls}`, "fill-opacity": opacity });
  p.g.insertBefore(r, p.g.firstChild);
  if (label) {
    const t = fkEl(p.g, "text", { class: "fk-tick fk-shade-label" }, label), len = t.getComputedTextLength(), cx = (L + R) / 2 + 3.5;
    const spots = [
      len + 10 <= R - L && { x: L + 5, y: T + 13 },
      len + 10 <= R - L && { x: L + 5, y: B - 6 },
      R - L >= 14 && len + 12 <= B - T && { x: cx, y: T + 6, "text-anchor": "end", transform: `rotate(-90 ${cx} ${T + 6})` },
      R - L >= 14 && len + 12 <= B - T && { x: cx, y: B - 6, transform: `rotate(-90 ${cx} ${B - 6})` },
    ].filter(Boolean);
    const set = (a) => { ["x", "y", "text-anchor", "transform"].forEach((k) => t.removeAttribute(k)); Object.entries(a).forEach(([k, v]) => t.setAttribute(k, v)); };
    const place = () => {
      const free = spots.find((a) => { set(a); const [x, y, w, h] = fkRectIn(p, t); return !fkOccupied(p, t, x, y, w, h); });
      if (free) set(free); else t.remove();
    };
    if (p.svg && p.svg.fk) p.svg.fk.jobs.unshift(place);
  }
  return r;
}

const fkPath = (pts) => pts.filter((p) => p && Number.isFinite(p[0]) && Number.isFinite(p[1])).map((p, k) => `${k ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");

function fkMark(g, shape, x, y, cls, r = 3.5, extra = {}) {
  if (shape === "s") return fkEl(g, "rect", { x: x - r * 0.9, y: y - r * 0.9, width: r * 1.8, height: r * 1.8, class: cls, ...extra });
  if (shape === "^") return fkEl(g, "path", { d: `M${x} ${y - r * 1.15}L${x + r * 1.1} ${y + r * 0.8}L${x - r * 1.1} ${y + r * 0.8}Z`, class: cls, ...extra });
  if (shape === "D") return fkEl(g, "path", { d: `M${x} ${y - r * 1.2}L${x + r} ${y}L${x} ${y + r * 1.2}L${x - r} ${y}Z`, class: cls, ...extra });
  return fkEl(g, "circle", { cx: x, cy: y, r, class: cls, ...extra });
}

function fkErr(g, x1, y1, x2, y2, cls, cap = 3) {
  fkEl(g, "line", { x1, y1, x2, y2, class: cls, "stroke-width": 1 });
  const vertical = Math.abs(x2 - x1) < Math.abs(y2 - y1);
  [[x1, y1], [x2, y2]].forEach(([x, y]) => fkEl(g, "line", vertical ? { x1: x - cap, x2: x + cap, y1: y, y2: y, class: cls, "stroke-width": 1 } : { x1: x, x2: x, y1: y - cap, y2: y + cap, class: cls, "stroke-width": 1 }));
}

function fkGlyph(g, kind, cls, dash) {
  if (kind === "line") fkEl(g, "line", { x1: 0, x2: 18, y1: -4, y2: -4, class: cls, "stroke-width": 1.5, "stroke-dasharray": dash });
  else if (kind === "patch") fkEl(g, "rect", { x: 1, y: -9, width: 16, height: 9, class: cls, "fill-opacity": 0.55 });
  else if (kind === "errbar") { fkErr(g, 2, -4, 16, -4, cls.split(" ").find((c) => c.startsWith("s-")) || "s-ink"); fkMark(g, "o", 9, -4, cls); }
  else fkMark(g, kind, 9, -4, cls);
}

const FK_KEY_PAD = 7, FK_KEY_ROW = 17, FK_KEY_GAP = 8;
function fkKey(p, items, corner = "tr") {
  const g = fkEl(p.g, "g", { class: "fk-legend" });
  if (p.above) {
    fkKeyRows(g, items, p.w);
    const bb = g.getBBox();
    g.setAttribute("transform", `translate(0,${(-FK_KEY_GAP - bb.height - bb.y).toFixed(1)})`);
    return g;
  }
  const frame = fkEl(g, "rect", { class: "fk-legend-box", rx: 2 }), body = fkEl(g, "g");
  items.forEach(([kind, cls, text, dash], k) => {
    const it = fkEl(body, "g", { transform: `translate(0,${k * FK_KEY_ROW})` });
    fkGlyph(it, kind, cls, dash);
    fkEl(it, "text", { x: 24, y: 0, class: "fk-tick" }, text);
  });
  const cb = body.getBBox(), bw = cb.width + 2 * FK_KEY_PAD, bh = cb.height + 2 * FK_KEY_PAD, gap = 7;
  Object.entries({ x: cb.x - FK_KEY_PAD, y: cb.y - FK_KEY_PAD, width: bw, height: bh }).forEach(([k, v]) => frame.setAttribute(k, v.toFixed(1)));
  const at = (c) => [c.endsWith("l") ? gap : p.w - bw - gap, c.startsWith("t") ? gap : c.startsWith("c") ? (p.h - bh) / 2 : p.h - bh - gap];
  const place = (c) => { const [x, y] = at(c); g.setAttribute("transform", `translate(${(x - cb.x + FK_KEY_PAD).toFixed(1)},${(y - cb.y + FK_KEY_PAD).toFixed(1)})`); };
  place(corner);
  const st = p.svg && p.svg.fk;
  if (st) st.jobs.push(() => {
    const free = [corner, ...["tr", "tl", "br", "bl"].filter((c) => c !== corner)].find((c) => !fkOccupied(p, g, ...at(c), bw, bh));
    p.g.appendChild(g);
    if (free) place(free);
    else if (bh < p.h) { st.keys[p.id] = { h: fkKeyRowsHeight(p, items) }; st.reflow = true; }
  });
  return g;
}

function fkKeyRows(g, items, maxW) {
  let dx = 0, dy = 0;
  items.forEach(([kind, cls, text, dash]) => {
    const it = fkEl(g, "g");
    fkGlyph(it, kind, cls, dash);
    const w = 24 + fkEl(it, "text", { x: 24, y: 0, class: "fk-tick" }, text).getComputedTextLength();
    if (dx > 0 && dx + w > maxW) { dx = 0; dy += FK_KEY_ROW; }
    it.setAttribute("transform", `translate(${dx},${dy})`);
    dx += w + 18;
  });
}
function fkKeyRowsHeight(p, items) {
  const g = fkEl(p.g, "g");
  fkKeyRows(g, items, p.w);
  const h = g.getBBox().height;
  g.remove();
  return Math.ceil(h);
}

function fkRectIn(p, el) {
  const b = el.getBBox(), toP = p.g.getScreenCTM().inverse().multiply(el.getScreenCTM());
  const c = [[b.x, b.y], [b.x + b.width, b.y], [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]].map(([u, v]) => new DOMPoint(u, v).matrixTransform(toP));
  const xs = c.map((q) => q.x), ys = c.map((q) => q.y), x = Math.min(...xs), y = Math.min(...ys);
  return [x, y, Math.max(...xs) - x, Math.max(...ys) - y];
}

function fkOccupied(p, key, x, y, w, h) {
  const inv = p.g.getScreenCTM().inverse(), m = 2;
  const inBox = (q) => q.x > x - m && q.x < x + w + m && q.y > y - m && q.y < y + h + m;
  const grid = [];
  for (let i = 0; i <= 4; i++) for (let j = 0; j <= 3; j++) grid.push(new DOMPoint(x + (w * i) / 4, y + (h * j) / 3));
  for (const e of p.g.querySelectorAll("path, line, polyline, polygon, circle, ellipse, rect, image, text")) {
    if (key.contains(e) || e.closest(".fk-legend") || /(^|\s)fk-(spine|grid|bg|legend-box|hit|mark|ref|shade)(\s|$)/.test(e.getAttribute("class") || "") || e.getAttribute("visibility") === "hidden") continue;
    const ctm = e.getScreenCTM();
    if (!ctm) continue;
    const toP = inv.multiply(ctm);
    if (["path", "line", "polyline", "polygon"].includes(e.tagName) && e.getTotalLength) {
      const len = e.getTotalLength();
      for (let d = 0; d <= len; d += Math.max(2, len / 800)) if (inBox(e.getPointAtLength(d).matrixTransform(toP))) return true;
      if (e.tagName !== "line" && getComputedStyle(e).fill !== "none" && e.isPointInFill) {
        const back = toP.inverse();
        if (grid.some((q) => e.isPointInFill(q.matrixTransform(back)))) return true;
      }
      continue;
    }
    const b = e.getBBox(), c = [[b.x, b.y], [b.x + b.width, b.y + b.height]].map(([u, v]) => new DOMPoint(u, v).matrixTransform(toP));
    const L = Math.min(c[0].x, c[1].x), R = Math.max(c[0].x, c[1].x), T = Math.min(c[0].y, c[1].y), B = Math.max(c[0].y, c[1].y);
    if (R > x - m && L < x + w + m && B > y - m && T < y + h + m && R > 0 && L < p.w && B > 0 && T < p.h) return true;
  }
  return false;
}

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

const FK_STYLE_PROPS = ["fill", "fill-opacity", "stroke", "stroke-width", "stroke-dasharray", "stroke-opacity", "opacity", "font-family", "font-size", "font-weight", "font-style", "letter-spacing", "visibility"];
function fkSerialize(svg) {
  const clone = svg.cloneNode(true), src = svg.querySelectorAll("*"), dst = clone.querySelectorAll("*"), drop = [];
  src.forEach((el, k) => {
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
