// Opt-in sound for the story page: radar pings, a chirp and soft ticks, made with the Web Audio API (no audio files).
// It stays silent until the reader switches it on, and the switch is remembered in this browser only. "Hear the echo"
// always plays, because pressing it is the request. Browsers only start audio after a click or key press, so a stored
// "on" waits for the reader's first one.

const Sound = { on: false, ac: null };

function soundStored() { try { return localStorage.getItem("hf.sound") === "on"; } catch { return false; } }
function soundStore(on) { try { localStorage.setItem("hf.sound", on ? "on" : "off"); } catch { /* private mode: not remembered */ } }

function soundContext() {
  if (!Sound.ac) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    Sound.ac = new Ctx();
  }
  if (Sound.ac.state === "suspended") Sound.ac.resume();
  return Sound.ac.state === "running" || Sound.ac.state === "suspended" ? Sound.ac : null;
}

// One ping: a short falling tone, like a radar return. gain is amplitude (0 to 1).
function soundPing({ gain = 0.09, from = 1400, to = 520, at = 0, len = 0.6, force = false } = {}) {
  if (!Sound.on && !force) return;
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

// A soft tick, for passing a station or lighting a step.
const soundTick = (gain = 0.025) => soundPing({ gain, from: 2400, to: 1900, len: 0.07 });

// A rising linear chirp: the shape of the pulse a radar like NISAR transmits, slowed down into hearing range.
function soundChirp(ms = 1600, gain = 0.035) {
  if (!Sound.on) return;
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

// Two echoes: a reference, then one with `powerRatio` times the power (amplitude is the square root of power).
function soundEcho(powerRatio, { force = true, gap = 0.9 } = {}) {
  soundPing({ gain: 0.12, force });
  soundPing({ gain: 0.12 * Math.sqrt(powerRatio), at: gap, force });
}

// The river: a soft rush of water whose loudness and depth follow the river's measured level, as the reader scrolls
// through a flood. It's a sonification of the gauges (filtered noise made here), not a recording. Only the journey's
// river and "Watch it move" use it; each passes level 0..1, or null when it leaves the screen.
const River = { src: null, filter: null, gain: null, owner: null };
function riverFade(to, secs = 0.35) {
  if (River.gain && Sound.ac) River.gain.gain.setTargetAtTime(to, Sound.ac.currentTime, secs);
}
function riverSound(owner, level) {
  if (level === null) { if (River.owner === owner) { River.owner = null; riverFade(0); } return; }
  River.owner = owner;
  if (!Sound.on) { riverFade(0); return; }
  const ac = soundContext();
  if (!ac) return;
  if (!River.src) {
    // two seconds of brown noise, looped: the low, even rush of moving water
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
  River.filter.frequency.setTargetAtTime(180 + 1500 * v * v, t, 0.3);   // a higher river sounds fuller and brighter
  River.gain.gain.setTargetAtTime(0.02 + 0.13 * v, t, 0.3);
}

// The speaker switch in the top bar (wired below, on any page that has one).
function setupSoundToggle(btn) {
  if (!btn) return;
  const render = () => {
    btn.setAttribute("aria-pressed", String(Sound.on));
    btn.querySelector(".sound-word").textContent = Sound.on ? "Sound on" : "Sound off";
    btn.classList.toggle("on", Sound.on);
  };
  Sound.on = soundStored();
  if (Sound.on) {
    const wake = () => { soundContext(); removeEventListener("pointerdown", wake); removeEventListener("keydown", wake); };
    addEventListener("pointerdown", wake);
    addEventListener("keydown", wake);
  }
  render();
  btn.addEventListener("click", () => {
    Sound.on = !Sound.on;
    soundStore(Sound.on);
    render();
    if (Sound.on) soundPing({ gain: 0.07 }); else riverFade(0, 0.1);
  });
}

setupSoundToggle(document.getElementById("sound-btn"));
