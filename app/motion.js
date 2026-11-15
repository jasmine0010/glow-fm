// Motion: the shared engine for the site's data animations (the data thread, the act cards, the game result, the
// flood-map gap, the live cut-off). Every mark is a real measurement with its unit stated, motion shows how the number
// comes about (a counter reads what has landed, it isn't tweened), and each settles into a labelled final frame that is
// right as a still. Instruments run once when first seen and hold; with reduced motion they draw the final frame.

const Motion = (() => {
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const clamp = (x) => Math.max(0, Math.min(1, x));
  const ease = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
  const lerp = (a, b, t) => a + (b - a) * t;

  // A canvas that draws draw(ctx, t, w, h) for t from 0 to 1 over ms, once it comes into view. Returns { play, redraw }.
  function instrument(canvas, draw, { ms = 2200, replay = null, threshold = 0.35, start = "view" } = {}) {
    const st = { t: reduced() ? 1 : 0, raf: 0, t0: 0, w: 0, h: 0, ctx: null };
    const size = () => {
      const r = canvas.getBoundingClientRect(), dpr = Math.min(2, devicePixelRatio || 1);
      st.w = r.width; st.h = r.height;
      canvas.width = Math.max(1, Math.round(r.width * dpr)); canvas.height = Math.max(1, Math.round(r.height * dpr));
      st.ctx = canvas.getContext("2d");
      st.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    const paint = () => { if (!st.w || !st.h) return; st.ctx.clearRect(0, 0, st.w, st.h); draw(st.ctx, st.t, st.w, st.h); };
    const frame = (now) => {
      if (!st.t0) st.t0 = now;
      st.t = clamp((now - st.t0) / ms);
      paint();
      st.raf = st.t < 1 ? requestAnimationFrame(frame) : 0;
    };
    const play = () => {
      cancelAnimationFrame(st.raf);
      if (reduced()) { st.t = 1; paint(); return; }
      st.t0 = 0; st.t = 0;
      st.raf = requestAnimationFrame(frame);
    };
    size(); paint();
    if ("ResizeObserver" in window) new ResizeObserver(() => { size(); paint(); }).observe(canvas);
    if (start === "view") {
      const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); play(); } }, { threshold });
      io.observe(canvas);
    }
    if (replay) replay.addEventListener("click", play);
    const finish = () => { cancelAnimationFrame(st.raf); st.raf = 0; st.t = 1; paint(); };
    return { play, finish, redraw: paint, get t() { return st.t; } };
  }

  // How far grain k of n has travelled at time t: grains leave one after another over `spread`, each taking `dur`.
  const stagger = (t, k, n, spread = 0.6, dur = 0.35) => ease(clamp((t - (k / Math.max(1, n)) * spread) / dur));

  // A small "replay" button for an instrument, placed in `parent`.
  function replayButton(parent, label) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "instr-replay"; b.textContent = "↻"; b.title = "Replay"; b.setAttribute("aria-label", `Replay: ${label}`);
    parent.appendChild(b);
    return b;
  }

  // A seeded random number, so every replay looks the same.
  const seeded = (seed = 7) => () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

  // A smooth line through points (Catmull-Rom as cubic Béziers), for curves drawn from data.
  function smoothPath(ctx, pts) {
    if (pts.length < 2) return;
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[Math.max(0, i - 1)], p1 = pts[i], p2 = pts[i + 1], p3 = pts[Math.min(pts.length - 1, i + 2)];
      ctx.bezierCurveTo(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6, p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, p2[0], p2[1]);
    }
  }

  // The area two circles share, radii r1 and r2 with centres d apart.
  function circleOverlap(r1, r2, d) {
    if (d >= r1 + r2) return 0;
    if (d <= Math.abs(r1 - r2)) return Math.PI * Math.min(r1, r2) ** 2;
    const a = r1 * r1 * Math.acos((d * d + r1 * r1 - r2 * r2) / (2 * d * r1)), b = r2 * r2 * Math.acos((d * d + r2 * r2 - r1 * r1) / (2 * d * r2));
    return a + b - 0.5 * Math.sqrt((-d + r1 + r2) * (d + r1 - r2) * (d - r1 + r2) * (d + r1 + r2));
  }

  // How far apart two circles must sit to share exactly `area` (the overlap shrinks as they move apart).
  function distanceForOverlap(r1, r2, area) {
    let lo = Math.abs(r1 - r2), hi = r1 + r2;
    if (area <= 0) return hi;
    if (area >= Math.PI * Math.min(r1, r2) ** 2) return lo;
    for (let k = 0; k < 60; k++) { const mid = (lo + hi) / 2; if (circleOverlap(r1, r2, mid) > area) lo = mid; else hi = mid; }
    return (lo + hi) / 2;
  }

  return { instrument, stagger, replayButton, seeded, ease, clamp, lerp, reduced, smoothPath, circleOverlap, distanceForOverlap };
})();
