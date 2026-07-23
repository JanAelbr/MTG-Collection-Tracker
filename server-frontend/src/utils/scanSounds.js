let audioCtx = null;

function getCtx() {
  if (!audioCtx) {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) {
      return null;
    }
    audioCtx = new Ctx();
  }
  if (audioCtx.state === "suspended") {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
}

function tone({ frequency, duration, type = "sine", gain = 0.08, slideTo = null }) {
  const ctx = getCtx();
  if (!ctx) {
    return;
  }
  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  const amp = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(frequency, now);
  if (slideTo != null) {
    osc.frequency.linearRampToValueAtTime(slideTo, now + duration);
  }
  amp.gain.setValueAtTime(0.0001, now);
  amp.gain.exponentialRampToValueAtTime(gain, now + 0.01);
  amp.gain.exponentialRampToValueAtTime(0.0001, now + duration);
  osc.connect(amp);
  amp.connect(ctx.destination);
  osc.start(now);
  osc.stop(now + duration + 0.02);
}

export function playScanSuccess() {
  tone({ frequency: 880, duration: 0.07, type: "sine", gain: 0.07 });
  window.setTimeout(() => {
    tone({ frequency: 1174, duration: 0.1, type: "sine", gain: 0.06 });
  }, 70);
}

export function playScanFail() {
  tone({ frequency: 220, duration: 0.16, type: "square", gain: 0.045, slideTo: 140 });
}
