/* Courtroom sound, synthesised with the Web Audio API (no files to download).
 *   door()      a suspense riser and a deep drum boom as the courtroom doors open
 *   intro()     about eight seconds of strings, timpani and brass the first time you enter
 *   score()     a light, moving score under the trial: plucked strings over soft pads and a gentle pulse
 *   ending(win) the verdict theme: dark if the Accuser wins, warm and relieved if the Defender wins
 *   sting()     a short tension hit for objections; gavel(), whoosh(), stamp() for the action
 * Music runs through its own bus with a user volume, and ducks under the voices so speech stays clear.
 * Browsers only allow audio after a click, so unlock() is called from the "Enter the courtroom" press.
 */
"use strict";

window.Sound = (() => {
  const AC = window.AudioContext || window.webkitAudioContext;
  let ctx = null, master, musicBus, sfxBus, featureBus, reverb, duckGain;
  let target = null; // when set, instruments play on this bus instead of the music bus (louder feature moments)
  const T = () => target ?? musicBus;
  let volume = 1, ducked = false;
  try { const v = parseFloat(localStorage.getItem("court-music-volume-v2")); if (v >= 0 && v <= 1) volume = v; } catch { /* storage blocked */ }
  let schedTimer = null, startTimer = null, nextBar = 0, barNo = 0;

  function init() {
    if (ctx) return true;
    if (!AC) return false;
    ctx = new AC();
    master = ctx.createGain(); master.gain.value = 0.9;
    const comp = ctx.createDynamicsCompressor(); // glue, and a safety net against clipping
    comp.threshold.value = -14; comp.ratio.value = 3; comp.attack.value = 0.01; comp.release.value = 0.25;
    const limiter = ctx.createDynamicsCompressor(); // a hard ceiling so loud moments never distort
    limiter.threshold.value = -2; limiter.knee.value = 0; limiter.ratio.value = 20; limiter.attack.value = 0.001; limiter.release.value = 0.1;
    master.connect(comp).connect(limiter).connect(ctx.destination);
    musicBus = ctx.createGain(); musicBus.gain.value = volume;
    duckGain = ctx.createGain(); duckGain.gain.value = 1;
    musicBus.connect(duckGain).connect(master);
    sfxBus = ctx.createGain(); sfxBus.gain.value = 0.85; sfxBus.connect(master);
    featureBus = ctx.createGain(); featureBus.gain.value = 1.5; featureBus.connect(master); // the opening logo and the verdict theme
    reverb = ctx.createConvolver();
    const len = ctx.sampleRate * 3, ir = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let ch = 0; ch < 2; ch++) {
      const d = ir.getChannelData(ch);
      for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3);
    }
    reverb.buffer = ir;
    const wet = ctx.createGain(); wet.gain.value = 0.5;
    reverb.connect(wet).connect(musicBus);
    return true;
  }
  const hz = (m) => 440 * Math.pow(2, (m - 69) / 12);
  /* a voice output: dry to a bus, plus a send to the hall reverb */
  function out(bus, dry = 1, wet = 0.6) {
    const g = ctx.createGain(), d = ctx.createGain(), w = ctx.createGain();
    d.gain.value = dry; w.gain.value = wet;
    g.connect(d).connect(bus); g.connect(w).connect(reverb);
    return g;
  }
  function noise(dur) {
    const b = ctx.createBuffer(1, Math.max(1, ctx.sampleRate * dur), ctx.sampleRate), d = b.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    const s = ctx.createBufferSource(); s.buffer = b; return s;
  }
  function env(g, t, a, peak, hold, rel) {
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(peak, t + a);
    g.gain.setValueAtTime(peak, t + a + hold);
    g.gain.exponentialRampToValueAtTime(0.0001, t + a + hold + rel);
  }

  /* ---------------------------------------------------------------- instruments */
  function pad(notes, t, dur, vol, attack = 1.2, bright = 2200) {
    const bus = out(T(), 0.55, 0.9);
    const f = ctx.createBiquadFilter(); f.type = "lowpass"; f.Q.value = 0.6;
    f.frequency.setValueAtTime(500, t); f.frequency.linearRampToValueAtTime(bright, t + attack + 0.3); f.frequency.linearRampToValueAtTime(800, t + dur);
    const g = ctx.createGain(); env(g, t, attack, vol, Math.max(0.1, dur - attack - 1), 1);
    f.connect(g).connect(bus);
    for (const n of notes) for (const det of [-8, 0, 7]) {
      const o = ctx.createOscillator(); o.type = "sawtooth"; o.frequency.value = hz(n); o.detune.value = det;
      const lfo = ctx.createOscillator(), lg = ctx.createGain(); lfo.frequency.value = 4.5 + Math.random(); lg.gain.value = 5;
      lfo.connect(lg).connect(o.detune); lfo.start(t); lfo.stop(t + dur + 0.1);
      o.connect(f); o.start(t); o.stop(t + dur + 0.1);
    }
  }
  function pluck(note, t, vol = 0.06, dur = 0.45) {
    const bus = out(T(), 0.8, 0.45);
    const o = ctx.createOscillator(), o2 = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    o.type = "triangle"; o.frequency.value = hz(note);
    o2.type = "sine"; o2.frequency.value = hz(note + 12);
    f.type = "lowpass"; f.frequency.setValueAtTime(3200, t); f.frequency.exponentialRampToValueAtTime(700, t + dur);
    env(g, t, 0.004, vol, 0, dur);
    o.connect(f); o2.connect(f); f.connect(g).connect(bus);
    o.start(t); o2.start(t); o.stop(t + dur + 0.05); o2.stop(t + dur + 0.05);
  }
  function drum(t, midi = 38, vol = 0.5, bus = T(), decay = 1.4) {
    const b = out(bus, 1, 0.5);
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.setValueAtTime(hz(midi) * 1.6, t); o.frequency.exponentialRampToValueAtTime(hz(midi), t + 0.07);
    env(g, t, 0.006, vol, 0, decay);
    o.connect(g).connect(b); o.start(t); o.stop(t + decay + 0.1);
    const n = noise(0.2), nf = ctx.createBiquadFilter(), ng = ctx.createGain();
    nf.type = "lowpass"; nf.frequency.value = 800; env(ng, t, 0.003, vol * 0.4, 0, 0.18);
    n.connect(nf).connect(ng).connect(b); n.start(t);
  }
  function brass(notes, t, dur, vol = 0.08) {
    const bus = out(T(), 0.8, 0.8);
    const f = ctx.createBiquadFilter(); f.type = "lowpass";
    f.frequency.setValueAtTime(300, t); f.frequency.linearRampToValueAtTime(1900, t + 0.12); f.frequency.exponentialRampToValueAtTime(500, t + dur);
    const g = ctx.createGain(); env(g, t, 0.05, vol, dur * 0.3, dur * 0.7);
    f.connect(g).connect(bus);
    for (const n of notes) for (const det of [-5, 5]) { const o = ctx.createOscillator(); o.type = "sawtooth"; o.detune.value = det; o.frequency.value = hz(n); o.connect(f); o.start(t); o.stop(t + dur + 0.1); }
  }
  function riser(t, dur, vol = 0.12, bus = T()) {
    const n = noise(dur), f = ctx.createBiquadFilter(), g = ctx.createGain();
    f.type = "bandpass"; f.Q.value = 2; f.frequency.setValueAtTime(300, t); f.frequency.exponentialRampToValueAtTime(5000, t + dur);
    g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(vol, t + dur * 0.95); g.gain.linearRampToValueAtTime(0.0001, t + dur);
    n.connect(f).connect(g).connect(out(bus, 1, 0.5)); n.start(t);
  }
  function boom(t, vol = 0.9, bus = T()) {
    const b = out(bus, 1, 0.9);
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.setValueAtTime(90, t); o.frequency.exponentialRampToValueAtTime(32, t + 0.9);
    env(g, t, 0.005, vol, 0.05, 2.2);
    o.connect(g).connect(b); o.start(t); o.stop(t + 2.4);
    const n = noise(0.6), nf = ctx.createBiquadFilter(), ng = ctx.createGain();
    nf.type = "lowpass"; nf.frequency.value = 400; env(ng, t, 0.003, vol * 0.6, 0, 0.6);
    n.connect(nf).connect(ng).connect(b); n.start(t);
  }

  /* ---------------------------------------------------------------- the score (lookahead scheduler) */
  const BPM = 88, BEAT = 60 / BPM, BAR = BEAT * 4;
  // i - VI - III - VII  /  i - iv - V - i  in D minor: hopeful, moving, never stuck
  const PROG = [
    { bass: 38, chord: [50, 53, 57], arp: [62, 65, 69, 65] },
    { bass: 34, chord: [50, 53, 58], arp: [62, 65, 70, 65] },
    { bass: 41, chord: [53, 57, 60], arp: [65, 69, 72, 69] },
    { bass: 36, chord: [52, 55, 60], arp: [64, 67, 72, 67] },
    { bass: 38, chord: [50, 53, 57], arp: [62, 65, 69, 74] },
    { bass: 43, chord: [50, 55, 58], arp: [62, 67, 70, 67] },
    { bass: 45, chord: [49, 52, 57], arp: [61, 64, 69, 64] },
    { bass: 38, chord: [50, 53, 57], arp: [62, 65, 69, 62] },
  ];
  function scheduleBar(t, n) {
    const b = PROG[n % PROG.length];
    pad([b.bass, ...b.chord], t, BAR + 0.6, 0.042, 0.9, 2000);
    const pattern = n % 4 === 3 ? [0, 1, 2, 3, 2, 1, 0, 1] : [0, 2, 1, 3, 0, 2, 1, 2];
    pattern.forEach((k, i) => { if (!(n < 2 && i % 2)) pluck(b.arp[k], t + i * BEAT / 2, i % 2 ? 0.075 : 0.11); });
    drum(t, b.bass + 12, 0.36, musicBus, 0.9);
    drum(t + BEAT * 2, b.bass + 12, 0.18, musicBus, 0.6);
    if (n % 8 === 7) riser(t + BAR - BEAT * 2, BEAT * 2, 0.04);
  }
  function tick() {
    while (nextBar < ctx.currentTime + 0.5) { scheduleBar(nextBar, barNo++); nextBar += BAR; }
  }

  function applyMusicGain(slow = 0.15) {
    if (!ctx) return;
    musicBus.gain.setTargetAtTime(volume, ctx.currentTime, slow);
    duckGain.gain.cancelScheduledValues(ctx.currentTime);
    duckGain.gain.setTargetAtTime(ducked ? 0.45 : 1, ctx.currentTime, ducked ? 0.08 : 0.6);
  }

  return {
    get on() { return volume > 0.001; },
    get volume() { return volume; },
    set volume(v) {
      volume = Math.max(0, Math.min(1, v));
      try { localStorage.setItem("court-music-volume-v2", String(volume)); } catch { /* storage blocked */ }
      applyMusicGain();
    },
    unlock() { if (init() && ctx.state === "suspended") ctx.resume(); },
    duck(on) { ducked = on; applyMusicGain(); },

    /* first entry: "ta... DUM", then a big warm chord that blooms open and fades over ~7 s */
    logo() {
      if (!init()) return;
      const t = ctx.currentTime + 0.05;
      target = featureBus;
      try {
        // hit one: a short, tight punch
        const p1 = out(featureBus, 1, 0.4), o1 = ctx.createOscillator(), g1 = ctx.createGain();
        o1.frequency.setValueAtTime(120, t); o1.frequency.exponentialRampToValueAtTime(48, t + 0.25);
        env(g1, t, 0.004, 0.7, 0, 0.35); o1.connect(g1).connect(p1); o1.start(t); o1.stop(t + 0.45);
        // hit two: the big one, with body and air
        const t2 = t + 0.42;
        boom(t2, 1.0);
        drum(t2, 38, 0.8, featureBus, 1.6);
        const body = ctx.createOscillator(), bg = ctx.createGain(); body.type = "triangle"; body.frequency.value = 110;
        env(bg, t2, 0.003, 0.35, 0, 0.9); body.connect(bg).connect(out(featureBus, 1, 0.8)); body.start(t2); body.stop(t2 + 1);
        // the bloom: a wide D major (add 9) chord sliding up into tune while the filter opens
        const bloom = out(featureBus, 0.7, 1.2), f = ctx.createBiquadFilter(), g = ctx.createGain();
        f.type = "lowpass"; f.Q.value = 1.2;
        f.frequency.setValueAtTime(220, t2); f.frequency.exponentialRampToValueAtTime(5200, t2 + 2.6); f.frequency.exponentialRampToValueAtTime(900, t2 + 7);
        g.gain.setValueAtTime(0.0001, t2); g.gain.exponentialRampToValueAtTime(0.05, t2 + 1.6); g.gain.setValueAtTime(0.05, t2 + 3.6); g.gain.exponentialRampToValueAtTime(0.0001, t2 + 7.2);
        f.connect(g).connect(bloom);
        [26, 38, 45, 50, 54, 57, 64, 69, 74].forEach((m, i) => {
          for (const det of [-14, -5, 5, 14]) {
            const o = ctx.createOscillator(), pan = ctx.createStereoPanner();
            o.type = "sawtooth"; o.frequency.value = hz(m);
            o.detune.setValueAtTime(det - 45, t2); o.detune.linearRampToValueAtTime(det, t2 + 1.4);
            pan.pan.value = Math.max(-1, Math.min(1, det / 16 + (i % 2 ? 0.15 : -0.15)));
            o.connect(pan).connect(f); o.start(t2); o.stop(t2 + 7.4);
          }
        });
        // a shimmer on top
        [86, 93].forEach((m, i) => { pluck(m, t2 + 1.2 + i * 0.35, 0.05, 2.5); pluck(m, t2 + 2.6 + i * 0.35, 0.03, 2.5); });
        // a low sub under everything
        const sub = ctx.createOscillator(), sg = ctx.createGain(); sub.frequency.value = hz(26);
        env(sg, t2, 1.2, 0.25, 2.5, 3); sub.connect(sg).connect(featureBus); sub.start(t2); sub.stop(t2 + 7);
      } finally { target = null; }
    },
    door() {
      if (!init()) return;
      const t = ctx.currentTime + 0.02;
      riser(t, 1.0, 0.16);
      boom(t + 1.0, 0.85);
      drum(t + 1.0, 33, 0.5, musicBus, 2.2);
    },
    intro(delay = 0) {
      if (!init()) return;
      const t = ctx.currentTime + delay;
      pad([38, 45], t, 8.5, 0.03, 2.2, 1400);                  // low D drone
      drum(t + 0.2, 38, 0.45); drum(t + 0.75, 38, 0.32);
      pad([50, 53, 57, 62], t + 1.2, 2.3, 0.045);             // D minor
      pad([46, 50, 53, 58], t + 3.2, 1.9, 0.05);              // B flat
      for (let i = 0; i < 7; i++) drum(t + 4.4 + i * 0.12, 45, 0.1 + i * 0.05, musicBus, 0.5); // roll
      pad([45, 49, 52, 57, 61], t + 4.9, 1.7, 0.055, 0.5);    // A major: the question
      brass([50, 57, 62], t + 6.6, 1.8, 0.09);                // the answer
      pad([38, 50, 53, 57, 62], t + 6.6, 2.4, 0.045, 0.15);
      drum(t + 6.6, 38, 0.75); boom(t + 6.6, 0.5);
    },
    score(delay = 0) {
      if (!init()) return;
      this.stopScore(true);
      startTimer = setTimeout(() => {
        barNo = 0; nextBar = ctx.currentTime + 0.1;
        tick(); schedTimer = setInterval(tick, 120);
      }, delay * 1000);
    },
    stopScore(quick) {
      clearTimeout(startTimer); clearInterval(schedTimer); schedTimer = startTimer = null;
      if (ctx && !quick) { // notes already scheduled fade under a quick dip, then the level comes back for what's next
        duckGain.gain.cancelScheduledValues(ctx.currentTime);
        duckGain.gain.setTargetAtTime(0.0001, ctx.currentTime, 0.12);
        setTimeout(() => applyMusicGain(0.2), 700);
      }
    },
    /* the verdict theme */
    ending(accuserWins) {
      if (!init()) return;
      const t = ctx.currentTime + 0.03;
      target = featureBus;
      try { this._ending(accuserWins, t); } finally { target = null; }
    },
    _ending(accuserWins, t) {
      if (accuserWins) { // dark and final: timpani, a falling bass, D minor with brass
        drum(t, 38, 0.45); drum(t + 0.35, 38, 0.35); drum(t + 0.7, 38, 0.5);
        pad([46, 50, 53, 58], t + 0.7, 2.0, 0.05, 0.3);
        pad([43, 50, 55, 58], t + 2.6, 1.9, 0.05, 0.3);
        pad([45, 49, 52, 57], t + 4.4, 1.6, 0.055, 0.3);
        brass([38, 50, 57, 62], t + 6.0, 3.0, 0.08); drum(t + 6.0, 33, 0.55); boom(t + 6.0, 0.4);
        pad([38, 50, 53, 57, 62], t + 6.0, 4.2, 0.045, 0.1);
      } else { // relief: a rising melody resolving to D major
        pad([50, 54, 57], t, 2.2, 0.045, 0.8);
        pad([43, 55, 59, 62], t + 2.0, 2.0, 0.045, 0.5);
        pad([45, 52, 57, 61], t + 3.8, 1.8, 0.05, 0.4);
        pad([38, 50, 54, 57, 62, 66], t + 5.5, 4.5, 0.05, 0.6, 2800);
        [62, 66, 69, 74, 73, 71, 69, 74].forEach((m, i) => pluck(m, t + 0.4 + i * 0.68, 0.07, 0.9));
        drum(t + 5.5, 38, 0.45); brass([50, 57, 62, 66], t + 5.5, 2.6, 0.07);
      }
    },
    sting() {
      if (!init()) return;
      const t = ctx.currentTime;
      drum(t, 33, 0.35, musicBus, 1.0);
      pad([51, 52, 58], t, 1.3, 0.035, 0.05, 3000); // a tight, uneasy cluster
    },
    gavel() {
      if (!init()) return;
      const t = ctx.currentTime, bus = out(sfxBus, 1, 0.3);
      const n = noise(0.12), f = ctx.createBiquadFilter(), g = ctx.createGain();
      f.type = "bandpass"; f.frequency.value = 900; f.Q.value = 1.2;
      env(g, t, 0.002, 0.9, 0, 0.12);
      n.connect(f).connect(g).connect(bus); n.start(t);
      const o = ctx.createOscillator(), og = ctx.createGain();
      o.frequency.setValueAtTime(180, t); o.frequency.exponentialRampToValueAtTime(90, t + 0.15);
      env(og, t, 0.002, 0.5, 0, 0.18);
      o.connect(og).connect(bus); o.start(t); o.stop(t + 0.22);
    },
    whoosh() {
      if (!init()) return;
      const t = ctx.currentTime, n = noise(0.5), f = ctx.createBiquadFilter(), g = ctx.createGain();
      f.type = "bandpass"; f.Q.value = 0.8; f.frequency.setValueAtTime(400, t); f.frequency.exponentialRampToValueAtTime(2500, t + 0.35);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.16, t + 0.12); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.45);
      n.connect(f).connect(g).connect(out(sfxBus, 1, 0.2)); n.start(t);
    },
    stamp(good) {
      if (!init()) return;
      const t = ctx.currentTime, bus = out(sfxBus, 1, 0.3);
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.frequency.setValueAtTime(good ? 140 : 110, t); o.frequency.exponentialRampToValueAtTime(55, t + 0.12);
      env(g, t, 0.002, 0.7, 0, 0.22);
      o.connect(g).connect(bus); o.start(t); o.stop(t + 0.25);
      if (good) pluck(81, t + 0.05, 0.05, 0.6); // a small bright ping when evidence is accepted
    },
  };
})();
