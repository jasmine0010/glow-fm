
const Sound = { on: false, ac: null, waiting: false };

function soundStored(fallback = false) { try { const v = localStorage.getItem("hf.sound"); return v ? v === "on" : fallback; } catch { return fallback; } }
function soundStore(on) { try { localStorage.setItem("hf.sound", on ? "on" : "off"); } catch {  } }

function soundContext() {
  if (!Sound.ac) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    Sound.ac = new Ctx();
  }
  if (Sound.ac.state === "suspended") Sound.ac.resume();
  return Sound.ac.state === "running" || Sound.ac.state === "suspended" ? Sound.ac : null;
}

function soundPing({ gain = 0.09, from = 1400, to = 520, at = 0, len = 0.6, force = false } = {}) {
  if ((!Sound.on || Sound.waiting) && !force) return;
  const ac = soundContext();
  if (!ac) return;
  const t = ac.currentTime + 0.03 + at, o = ac.createOscillator(), g = ac.createGain();
  o.type = "sine";
  o.frequency.setValueAtTime(from, t);
  o.frequency.exponentialRampToValueAtTime(to, t + len * 0.6);
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(Math.max(0.0002, gain), t + 0.012);
  g.gain.exponentialRampToValueAtTime(0.0001, t + len);
  o.connect(g).connect(ac.destination);
  o.start(t);
  o.stop(t + len + 0.05);
}

const soundTick = (gain = 0.025) => soundPing({ gain, from: 2400, to: 1900, len: 0.07 });

function soundChirp(ms = 1600, gain = 0.035) {
  if (!Sound.on || Sound.waiting) return;
  const ac = soundContext();
  if (!ac) return;
  const t = ac.currentTime + 0.03, s = ms / 1000, o = ac.createOscillator(), f = ac.createBiquadFilter(), g = ac.createGain();
  o.type = "triangle";
  o.frequency.setValueAtTime(260, t);
  o.frequency.linearRampToValueAtTime(2200, t + s);
  f.type = "lowpass"; f.frequency.value = 2600;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(gain, t + 0.08);
  g.gain.setValueAtTime(gain, t + s - 0.15);
  g.gain.exponentialRampToValueAtTime(0.0001, t + s);
  o.connect(f).connect(g).connect(ac.destination);
  o.start(t);
  o.stop(t + s + 0.05);
}

function soundReturn({ gain, ring = 0, at = 0, force = false }) {
  if ((!Sound.on || Sound.waiting) && !force) return;
  const ac = soundContext();
  if (!ac) return;
  const t = ac.currentTime + 0.03 + at, n = Math.round(ac.sampleRate * 0.45), buf = ac.createBuffer(1, n, ac.sampleRate), d = buf.getChannelData(0);
  for (let i = 0; i < n; i++) d[i] = (Math.random() * 2 - 1) * Math.exp(-i / (ac.sampleRate * 0.09)) * (Math.random() < 0.08 ? 2.2 : 1);
  const src = ac.createBufferSource(), bp = ac.createBiquadFilter(), g = ac.createGain();
  src.buffer = buf; bp.type = "bandpass"; bp.frequency.value = 1300; bp.Q.value = 1.4;
  g.gain.value = 2.4 * gain * (1 - 0.65 * ring);
  src.connect(bp).connect(g).connect(ac.destination);
  src.start(t);
  if (ring > 0.02) {
    soundPing({ gain: gain * ring, from: 1500, to: 980, at, len: 0.95, force });
    soundPing({ gain: gain * ring * 0.3, from: 1500, to: 980, at: at + 0.12, len: 0.7, force });
  }
}

function soundEcho(powerRatio, { force = true, gap = 0.9 } = {}) {
  const ring = Math.max(0, Math.min(1, (10 * Math.log10(powerRatio)) / 3));
  soundReturn({ gain: 0.11, force });
  soundReturn({ gain: 0.11 * Math.sqrt(powerRatio), ring, at: gap, force });
}

const River = { src: null, filter: null, gain: null, owner: null };
function riverFade(to, secs = 0.35) {
  if (River.gain && Sound.ac) River.gain.gain.setTargetAtTime(to, Sound.ac.currentTime, secs);
}
function riverSound(owner, level) {
  if (level === null) { if (River.owner === owner) { River.owner = null; riverFade(0); } return; }
  River.owner = owner;
  if (!Sound.on || Sound.waiting) { riverFade(0); return; }
  const ac = soundContext();
  if (!ac) return;
  if (!River.src) {
    const n = 2 * ac.sampleRate, buf = ac.createBuffer(1, n, ac.sampleRate), d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < n; i++) { last = (last + 0.02 * (Math.random() * 2 - 1)) / 1.02; d[i] = last * 3.5; }
    River.src = ac.createBufferSource(); River.src.buffer = buf; River.src.loop = true;
    River.filter = ac.createBiquadFilter(); River.filter.type = "lowpass"; River.filter.Q.value = 0.4;
    River.gain = ac.createGain(); River.gain.gain.value = 0;
    River.src.connect(River.filter).connect(River.gain).connect(ac.destination);
    River.src.start();
  }
  const v = Math.max(0, Math.min(1, level)), t = ac.currentTime;
  River.filter.frequency.setTargetAtTime(180 + 1500 * v * v, t, 0.3);
  River.gain.gain.setTargetAtTime(0.02 + 0.13 * v, t, 0.3);
}

function setupSoundToggle(btn) {
  if (!btn) return;
  const render = () => {
    const playing = Sound.on && !Sound.waiting;
    btn.setAttribute("aria-pressed", String(playing));
    btn.querySelector(".sound-word").textContent = playing ? "Sound on" : "Sound off";
    btn.classList.toggle("on", playing);
  };
  const start = () => {
    const ac = soundContext();
    if (!ac) return Promise.resolve();
    return ac.resume().then(() => {
      if (ac.state !== "running" || !Sound.waiting) return;
      Sound.waiting = false;
      if (typeof ambienceSwitch === "function") ambienceSwitch(true);
      render();
    });
  };
  Sound.on = soundStored(btn.dataset.default === "on");
  Sound.waiting = Sound.on;
  render();
  btn.addEventListener("click", () => {
    if (Sound.waiting) { start().then(() => soundPing({ gain: 0.07 })); return; }
    Sound.on = !Sound.on;
    soundStore(Sound.on);
    render();
    if (Sound.on) soundPing({ gain: 0.07 }); else riverFade(0, 0.1);
    if (typeof ambienceSwitch === "function") ambienceSwitch(Sound.on);
  });
}

setupSoundToggle(document.getElementById("sound-btn"));
