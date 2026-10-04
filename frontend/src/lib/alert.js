let ctx;

export function playNewOrderSound() {
  try {
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume();
    [0, 0.18, 0.36].forEach((off, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = i === 2 ? 1320 : 880;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime + off);
      gain.gain.exponentialRampToValueAtTime(0.4, ctx.currentTime + off + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + off + 0.16);
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + off);
      osc.stop(ctx.currentTime + off + 0.18);
    });
  } catch (_) {}
}
