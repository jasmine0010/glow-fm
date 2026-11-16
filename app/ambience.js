
const Amb = { ac: null, master: null, verb: null, drone: null, hum: null, wind: null, built: false, scene: "", key: "", y: 0, v: 0, dir: 0, last: 0,
  pulse: 0, chatter: 0, density: 0, bright: 0, nextPulse: 0, nextStep: 0, step: 0, lastLight: 0 };
const AMB_LEVEL = 0.8;
const AMB_PERIOD = 4.2;
const AMB_STEP = 0.3;

const AMB_SCALE = [146.83, 164.81, 185, 220, 246.94, 293.66, 329.63, 369.99, 440, 493.88, 587.33, 659.25];
const AMB_PATTERN = [0, -1, 2, -1, 4, -1, 2, 5, -1, 3, -1, 4, 6, -1, 4, -1];

const AMB_SCENES = {
  finding: { pulse: 0.5, hum: 0.4, chatter: 0.2, density: 0.45, bright: 0.45, shift: 2 },
  "act-1": { pulse: 0.5, hum: 0.1, chatter: 0, density: 0.3, bright: 0.3, shift: 0 },
  orbit: { pulse: 0.4, hum: 1, chatter: 0.8, density: 0.55, bright: 0.75, shift: 4 },
  scale: { pulse: 0.4, hum: 0.8, chatter: 0.6, density: 0.6, bright: 0.65, shift: 4 },
  people: { pulse: 0.45, hum: 0.5, chatter: 0.4, density: 0.65, bright: 0.6, shift: 3 },
  blind: { pulse: 0.6, hum: 0.3, chatter: 0.2, density: 0.4, bright: 0.4, shift: 1 },
  river: { pulse: 0.35, hum: 0, chatter: 0, density: 0.35, bright: 0.35, shift: 0 },
  pixel: { pulse: 0.7, hum: 0, chatter: 0.3, density: 0.7, bright: 0.55, shift: 2 },
  tree: { pulse: 0.4, hum: 0, chatter: 0.1, density: 0.5, bright: 0.45, shift: 1 },
  "act-2": { pulse: 0.8, hum: 0.2, chatter: 0.3, density: 0.7, bright: 0.6, shift: 3 },
  timeline: { pulse: 0.4, hum: 0, chatter: 0.1, density: 0.45, bright: 0.4, shift: 1 },
  game: { pulse: 0.5, hum: 0, chatter: 0.2, density: 0.65, bright: 0.6, shift: 3 },
  "act-3": { pulse: 0.4, hum: 0.2, chatter: 0.2, density: 0.55, bright: 0.55, shift: 2 },
  "act-4": { pulse: 0.5, hum: 0.2, chatter: 0.3, density: 0.6, bright: 0.6, shift: 4 },
  foot: { pulse: 0.4, hum: 1, chatter: 0.8, density: 0.4, bright: 0.7, shift: 4 },
};
const AMB_ORDER = [["finding", "finding"], ["act-1", "act-1"], ["journey", "journey"], ["act-2", "act-2"], ["why", "act-2"], ["timeline", "timeline"],
  ["game", "game"], ["act-3", "act-3"], ["where", "act-3"], ["run", "act-3"], ["act-4", "act-4"], ["deeper", "act-4"]];

function ambNoise(ac, secs, brown = false) {
  const n = Math.round(secs * ac.sampleRate), buf = ac.createBuffer(1, n, ac.sampleRate), d = buf.getChannelData(0);
  let last = 0;
  for (let i = 0; i < n; i++) { const w = Math.random() * 2 - 1; if (brown) { last = (last + 0.02 * w) / 1.02; d[i] = last * 3.5; } else d[i] = w; }
  return buf;
}
const ambPanner = (ac) => (ac.createStereoPanner ? ac.createStereoPanner() : ac.createGain());

function ambBuild(ac) {
  Amb.ac = ac;
  const comp = ac.createDynamicsCompressor();
  comp.threshold.value = -24; comp.ratio.value = 3;
  Amb.master = ac.createGain(); Amb.master.gain.value = 0;
  Amb.master.connect(comp).connect(ac.destination);
  const dl = ac.createDelay(2), fb = ac.createGain(), damp = ac.createBiquadFilter(), wet = ac.createGain();
  dl.delayTime.value = AMB_STEP * 1.5; fb.gain.value = 0.38; damp.type = "lowpass"; damp.frequency.value = 2600; wet.gain.value = 0.45;
  dl.connect(damp).connect(fb).connect(dl); damp.connect(wet).connect(Amb.master);
  Amb.verb = dl;
  const df = ac.createBiquadFilter(), dg = ac.createGain(), lfo = ac.createOscillator(), lfoAmt = ac.createGain();
  df.type = "lowpass"; df.frequency.value = 420; df.Q.value = 3; dg.gain.value = 0.011;
  lfo.frequency.value = 0.07; lfoAmt.gain.value = 140; lfo.connect(lfoAmt).connect(df.frequency); lfo.start();
  [[73.42, -6], [73.42, 6], [110, 0]].forEach(([f, c]) => { const o = ac.createOscillator(); o.type = "sawtooth"; o.frequency.value = f; o.detune.value = c; o.connect(df); o.start(); });
  df.connect(dg).connect(Amb.master);
  Amb.drone = { filter: df, gain: dg };
  const hg = ac.createGain(), hf = ac.createBiquadFilter();
  hg.gain.value = 0; hf.type = "lowpass"; hf.frequency.value = 2200;
  [[880, -4], [880, 4], [1318.5, 0]].forEach(([f, c]) => { const o = ac.createOscillator(); o.type = "sine"; o.frequency.value = f; o.detune.value = c; o.connect(hf); o.start(); });
  hf.connect(hg); hg.connect(Amb.master);
  Amb.hum = hg;
  const src = ac.createBufferSource(), lp = ac.createBiquadFilter(), wg = ac.createGain(), pan = ambPanner(ac);
  src.buffer = ambNoise(ac, 3, true); src.loop = true; lp.type = "lowpass"; lp.frequency.value = 600; wg.gain.value = 0;
  src.connect(lp).connect(wg).connect(pan).connect(Amb.master); src.start();
  Amb.wind = { lp, gain: wg, pan };
  Amb.nextPulse = ac.currentTime + 1;
  Amb.nextStep = ac.currentTime + 0.5;
  Amb.built = true;
}

function ambTone(type, f, t, len, gain, { pan = 0, to = null, verb = 0.6, attack = 0.005, cutoff = null } = {}) {
  const ac = Amb.ac, o = ac.createOscillator(), g = ac.createGain(), p = ac.createStereoPanner ? ac.createStereoPanner() : null;
  o.type = type; o.frequency.setValueAtTime(f, t); if (to) o.frequency.exponentialRampToValueAtTime(to, t + len);
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(gain, t + Math.min(attack, len / 4)); g.gain.exponentialRampToValueAtTime(0.0001, t + len);
  let node = o;
  if (cutoff) { const lf = ac.createBiquadFilter(); lf.type = "lowpass"; lf.frequency.value = cutoff; lf.Q.value = 2; node = node.connect(lf); }
  node = node.connect(g);
  if (p) { p.pan.value = pan; node = node.connect(p); }
  node.connect(Amb.master);
  if (verb) { const s = ac.createGain(); s.gain.value = verb; node.connect(s).connect(Amb.verb); }
  o.start(t); o.stop(t + len + 0.05);
}

function ambPulse(t, k) {
  if (k <= 0.01) return;
  ambTone("sine", 1174.66, t, 0.5, 0.02 * k, { to: 1046.5, verb: 0.7, attack: 0.004 });
  ambTone("sine", 147, t, 0.8, 0.04 * k, { to: 138, verb: 0.2, attack: 0.01 });
  const ac = Amb.ac, src = ac.createBufferSource(), bp = ac.createBiquadFilter(), g = ac.createGain(), p = ambPanner(ac), len = 2.4;
  src.buffer = ambNoise(ac, len); bp.type = "bandpass"; bp.frequency.value = 2200; bp.Q.value = 3;
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.012 * k, t + len * 0.5); g.gain.exponentialRampToValueAtTime(0.0001, t + len);
  if (p.pan) { p.pan.setValueAtTime(-0.85, t); p.pan.linearRampToValueAtTime(0.85, t + len); }
  src.connect(bp).connect(g).connect(p).connect(Amb.master);
  src.start(t); src.stop(t + len + 0.05);
}

function ambSeqStep(t, s) {
  const k = Amb.step++ % AMB_PATTERN.length, deg = AMB_PATTERN[k];
  if (deg < 0 || Math.random() > Amb.density + 0.15) return;
  const f = AMB_SCALE[Math.min(AMB_SCALE.length - 1, deg + s.shift)];
  ambTone("square", f, t, 0.22, 0.011, { pan: k % 2 ? 0.35 : -0.35, verb: 0.55, cutoff: 500 + 2200 * Amb.bright });
  if (k % 4 === 0) ambTone("triangle", f / 2, t, 0.35, 0.012, { verb: 0.2, cutoff: 600 });
}

function ambChatter() {
  const ac = Amb.ac, n = 3 + Math.floor(Math.random() * 4), pan = Math.random() * 1.6 - 0.8;
  let t = ac.currentTime + 0.02;
  for (let i = 0; i < n; i++) { ambTone("sine", 1800 + Math.random() * 1800, t, 0.035, 0.005, { pan, verb: 0.3 }); t += 0.05 + Math.random() * 0.05; }
}

function ambSwell() {
  const t = Amb.ac.currentTime + 0.05;
  ambTone("sawtooth", 220, t, 1.3, 0.012, { to: 440, verb: 0.5, attack: 0.6, cutoff: 1400 });
  [0, 2, 4].forEach((d, i) => ambTone("square", AMB_SCALE[d + 5], t + 1.1 + i * 0.09, 0.18, 0.01, { pan: (i - 1) * 0.4, verb: 0.8, cutoff: 2400 }));
}
function ambRush() {
  const ac = Amb.ac, t = ac.currentTime + 0.02, src = ac.createBufferSource(), bp = ac.createBiquadFilter(), g = ac.createGain();
  src.buffer = ambNoise(ac, 1.6); bp.type = "bandpass"; bp.Q.value = 1.2;
  bp.frequency.setValueAtTime(300, t); bp.frequency.exponentialRampToValueAtTime(2400, t + 1.1);
  g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.015, t + 0.9); g.gain.exponentialRampToValueAtTime(0.0001, t + 1.5);
  src.connect(bp).connect(g).connect(Amb.master); g.connect(Amb.verb);
  src.start(t); src.stop(t + 1.6);
}

function ambLight(pan = 0) {
  if (!Amb.built || !Sound.on || Sound.waiting) return;
  const t = Amb.ac.currentTime;
  if (t - Amb.lastLight < 0.12) return;
  Amb.lastLight = t;
  const f = AMB_SCALE[6 + Math.floor(Math.random() * 6)] * 2, p = Math.max(-0.9, Math.min(0.9, pan));
  ambTone("sine", f, t + 0.02, 0.06, 0.009, { pan: p, verb: 0.5 });
  ambTone("sine", f * 1.5, t + 0.07, 0.05, 0.005, { pan: p, verb: 0.4 });
}

function ambWhere() {
  const foot = document.querySelector("footer.foot");
  if (foot && foot.getBoundingClientRect().top < innerHeight * 0.5) return ["foot", "foot"];
  let id = "finding", scene = "finding";
  for (const [sid, sc] of AMB_ORDER) { const el = document.getElementById(sid); if (el && el.getBoundingClientRect().top < innerHeight * 0.5) { id = sid; scene = sc; } }
  if (scene === "journey") { const k = document.getElementById("lantern-stage")?.dataset.act; scene = AMB_SCENES[k] ? k : "orbit"; }
  return [id, scene];
}

function ambFrame(ts) {
  requestAnimationFrame(ambFrame);
  const dt = Math.min(100, ts - (Amb.last || ts)) / 1000;
  Amb.last = ts;
  const dy = scrollY - Amb.y; Amb.y = scrollY;
  const speed = dt > 0 ? Math.abs(dy) / Math.max(1, innerHeight) / dt : 0;
  Amb.v += (Math.min(3, speed) - Amb.v) * (1 - Math.exp(-dt / (speed > Amb.v ? 0.08 : 0.5)));
  if (dy) Amb.dir = Math.sign(dy);
  const live = Sound.on && !Sound.waiting && Amb.built && Amb.ac.state === "running" && !document.hidden;
  if (Amb.built) Amb.master.gain.setTargetAtTime(live ? AMB_LEVEL : 0, Amb.ac.currentTime, live ? 1.2 : 0.25);
  if (!live) return;
  const [id, scene] = ambWhere(), s = AMB_SCENES[scene], t = Amb.ac.currentTime;
  if (scene !== Amb.scene) {
    const swell = Amb.scene && id.startsWith("act-") && Amb.key !== id, rush = Amb.scene && id === "journey" && Amb.key === "journey";
    Amb.scene = scene;
    if (swell) ambSwell(); else if (rush) ambRush();
  }
  Amb.key = id;
  const k = 1 - Math.exp(-dt / 1.5);
  Amb.pulse += (s.pulse - Amb.pulse) * k; Amb.chatter += (s.chatter - Amb.chatter) * k;
  Amb.density += (s.density - Amb.density) * k; Amb.bright += (s.bright - Amb.bright) * k;
  Amb.hum.gain.setTargetAtTime(0.004 * s.hum, t, 1.5);
  Amb.drone.filter.frequency.setTargetAtTime(300 + 500 * s.bright, t, 1.5);
  if (t > Amb.nextPulse - 0.15) { if (Amb.nextPulse < t) Amb.nextPulse = t + 0.05; ambPulse(Amb.nextPulse, Amb.pulse); Amb.nextPulse += AMB_PERIOD; }
  if (Amb.nextStep < t) Amb.nextStep = t + 0.05;
  while (Amb.nextStep < t + 0.15) { ambSeqStep(Amb.nextStep, s); Amb.nextStep += AMB_STEP; }
  const w = Math.min(1, Amb.v / 2.5);
  Amb.wind.gain.gain.setTargetAtTime(0.025 * w ** 1.5, t, 0.35);
  Amb.wind.lp.frequency.setTargetAtTime(450 + 450 * w + (Amb.dir < 0 ? 120 : 0), t, 0.4);
  if (Amb.wind.pan.pan) Amb.wind.pan.pan.setTargetAtTime(0.25 * Math.sin(ts / 3700), t, 0.8);
  if (Math.random() < Amb.chatter * 0.35 * dt) ambChatter();
}

function ambienceSwitch(on) {
  if (!on) return;
  const ac = soundContext();
  if (ac && !Amb.built) ambBuild(ac);
}

(function setupAmbience() {
  Amb.y = scrollY;
  requestAnimationFrame(ambFrame);
})();
