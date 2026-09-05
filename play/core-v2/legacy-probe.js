// Eval for `node tools/measure-slice.js --eval play/core-v2/legacy-probe.js`
// Same physical inputs as V2 F01 / F02. Units converted with U_MM once, here.

function layerArcMm(wd, k) {
  let acc = 0;
  for (let b = 0; b < NB; b++) {
    const i = k * NB + b, i2 = k * NB + ((b + 1) % NB);
    if (!(wd.rin[i] >= 0 && wd.rout[i] > 0)) continue;
    const r = (wd.rin[i] + wd.rout[i]) / 2;
    const r2 = (wd.rin[i2] >= 0 && wd.rout[i2] > 0) ? (wd.rin[i2] + wd.rout[i2]) / 2 : r;
    const dr = (r2 - r) / DPHI;
    acc += Math.sqrt(r * r + dr * dr) * DPHI;
  }
  return acc * U_MM;
}

function snap(list) {
  const keep = { base: S.base, wrap: S.wrap, turns: S.turns, shape: S.shape, hand: S.hand, list: S.lists.hoso };
  S.base = 'hoso'; S.wrap = null; S.turns = null; S.shape = 'round';
  S.hand = handOf();
  S.lists.hoso = JSON.parse(JSON.stringify(list));
  const m = buildModel(S.lists.hoso);
  const wd = windFor(m, 0.5);
  const g = m.g;
  const Lmm = g.L * U_MM;
  const s0Bare = g.spreadStart === undefined ? SPREAD_START : g.spreadStart;
  const sRice0 = Math.max(g.sStart || 0, s0Bare * g.L) * U_MM;
  const sRice1 = Math.min(g.L, g.spreadEnd * g.L) * U_MM;
  let dMin = Infinity, dMax = 0;
  for (let b = 0; b < NB; b++) {
    const r = wd.top[b] * U_MM;
    if (r < dMin) dMin = r;
    if (r > dMax) dMax = r;
  }
  let two = 0;
  for (let b = 0; b < NB; b++) {
    const nori = wd.rin[NB + b] >= 0;
    const extra = wd.rin[2 * NB + b] >= 0;
    if (nori && extra) two++;
    else if (nori) { /* 1 */ }
  }
  let patchArea = 0, sx = 0, sy = 0;
  const cell = (2 * m.Rmax / 320) ** 2;
  for (let i = 0; i < 320; i++) for (let j = 0; j < 320; j++) {
    const x = ((i + 0.5) / 320 * 2 - 1) * m.Rmax;
    const y = ((j + 0.5) / 320 * 2 - 1) * m.Rmax;
    if (x * x + y * y > m.Rmax * m.Rmax) continue;
    const q = materialAt(m, wd, 0.5, Math.hypot(x, y), Math.atan2(y, x));
    if (q && q.cls === 'patch') {
      patchArea += cell;
      sx += x * cell;
      sy += y * cell;
    }
  }
  const out = {
    lengthMm: Lmm,
    diameterMinMm: 2 * dMin,
    diameterMaxMm: 2 * dMax,
    diameterRmaxMm: 2 * m.Rmax * U_MM,
    turns: wd.turns,
    sRice0Mm: sRice0,
    sRice1Mm: sRice1,
    overlapMm: ((g.L - Math.min(g.L, g.spreadEnd * g.L)) + Math.max(g.sStart || 0, s0Bare * g.L)) * U_MM,
    riceArcMm: layerArcMm(wd, 0),
    noriArcMm: layerArcMm(wd, 1),
    coreWcMm: (m.core ? m.core.Wc : 0) * U_MM,
    coreHcMm: (m.core ? m.core.Hc : 0) * U_MM,
    r0Mm: g.r0 * U_MM,
    twoIntersectionCount: two,
    twoIntersectionFraction: two / NB,
    cucumberAreaMm2: patchArea * U_MM * U_MM,
    cucumberCenterXmm: patchArea > 0 ? (sx / patchArea) * U_MM : 0,
    cucumberCenterYmm: patchArea > 0 ? (sy / patchArea) * U_MM : 0,
    perimeterUnits: wd.периметр,
    shortageUnits: wd.нехватка,
  };
  S.base = keep.base; S.wrap = keep.wrap; S.turns = keep.turns; S.shape = keep.shape;
  S.hand = keep.hand; S.lists.hoso = keep.list;
  return out;
}

const uF02 = 36.25 / 105;
globalThis.ВЫХОД = {
  F01: snap([]),
  F02: snap([{ kind: 'cucumber', u: uF02, v: 0.5, z0: 0, z1: 1, phase: 0.5 }]),
};
