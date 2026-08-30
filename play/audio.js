'use strict';
// ЗВУК: процедурный, без файлов. Шуршание циновки при тяге, хруст ножа, стук доски.
//
// Тактильность игры держится на звуке, а не на картинке (принцип из design-core) — поэтому
// он собран синтезом на Web Audio и не тянет ни одного ассета.

// ---------------------------------------------------------------- звук (процедурный, минимальный)
const sfx = {
  ac: null, master: null, noise: null, rustleGain: null,
  ensure() {
    if (this.ac) { if (this.ac.state === 'suspended') this.ac.resume(); return; }
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
    this.ac = new AC(); this.master = this.ac.createGain(); this.master.gain.value = S.mute ? 0 : 1; this.master.connect(this.ac.destination);
    const n = this.ac.sampleRate; const buf = this.ac.createBuffer(1, n, n); const ch = buf.getChannelData(0);
    for (let i = 0; i < n; i++) ch[i] = Math.random() * 2 - 1;
    this.noise = buf;
  },
  setMute(m) { if (this.master) this.master.gain.value = m ? 0 : 1; },
  burst(freq, q, dur, vol, t0 = 0) {
    if (!this.ac) return; const t = this.ac.currentTime + t0;
    const src = this.ac.createBufferSource(); src.buffer = this.noise;
    const f = this.ac.createBiquadFilter(); f.type = 'bandpass'; f.frequency.value = freq; f.Q.value = q;
    const g = this.ac.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + 0.006); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(f); f.connect(g); g.connect(this.master); src.start(t); src.stop(t + dur + 0.05);
  },
  tone(f0, f1, dur, vol, t0 = 0) {
    if (!this.ac) return; const t = this.ac.currentTime + t0;
    const o = this.ac.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(f1, t + dur);
    const g = this.ac.createGain(); g.gain.setValueAtTime(vol, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(g); g.connect(this.master); o.start(t); o.stop(t + dur + 0.02);
  },
  place() { this.ensure(); this.tone(170, 90, 0.09, 0.22); this.burst(1200, 0.7, 0.03, 0.12); },
  cut() { this.ensure(); this.burst(2200, 0.6, 0.18, 0.5); this.burst(600, 1.2, 0.12, 0.25, 0.05); this.tone(80, 50, 0.09, 0.35, 0.09); },
  chop() { this.ensure(); this.burst(2000, 0.7, 0.09, 0.4); this.tone(90, 55, 0.06, 0.28, 0.04); },
  rustleStart() {
    this.ensure(); if (!this.ac || this.rustleGain) return;
    const src = this.ac.createBufferSource(); src.buffer = this.noise; src.loop = true;
    const f = this.ac.createBiquadFilter(); f.type = 'bandpass'; f.frequency.value = 900; f.Q.value = 0.5;
    const g = this.ac.createGain(); g.gain.value = 0;
    src.connect(f); f.connect(g); g.connect(this.master); src.start();
    this.rustleGain = g; this.rustleSrc = src;
  },
  rustle(v) { if (this.rustleGain) this.rustleGain.gain.setTargetAtTime(clamp(v) * 0.25, this.ac.currentTime, 0.03); },
  rustleStop() { if (!this.rustleGain) return; const g = this.rustleGain, s = this.rustleSrc; g.gain.setTargetAtTime(0, this.ac.currentTime, 0.05); setTimeout(() => { try { s.stop(); } catch (e) {} }, 300); this.rustleGain = null; },
};

