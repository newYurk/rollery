// Ring winding in millimetres. Formulas from geometry.js (ring branch), no import.
// F01/F02 only: hosomaki, fromUZero, one optional core filling.

import {
  DPHI,
  EPS_LENGTH_MM,
  NB,
  TAU,
  baseOf,
  patchCoreXmm,
  riceSpanMm,
} from './units.js';

export function r0At(phi, Wc, Hc) {
  const c = Math.abs(Math.cos(phi));
  const s = Math.abs(Math.sin(phi));
  const rx = c > 1e-12 ? (Wc / 2) / c : Infinity;
  const ry = s > 1e-12 ? (Hc / 2) / s : Infinity;
  return Math.min(rx, ry);
}

function coreBoxMm(recipe) {
  const base = baseOf(recipe);
  let Wc = base.emptyCoreWidthMm;
  let Hc = base.emptyCoreHeightMm;
  for (const p of recipe.patches) {
    const x = patchCoreXmm(recipe, p);
    Wc = Math.max(Wc, 2 * (Math.abs(x) + p.widthMm / 2));
    Hc = Math.max(Hc, p.heightMm + 2 * base.noriThicknessMm);
  }
  return { Wc, Hc };
}

function midArc(rAtBin) {
  let acc = 0;
  for (let b = 0; b < NB; b++) {
    const r = rAtBin(b);
    const r2 = rAtBin((b + 1) % NB);
    const dr = (r2 - r) / DPHI;
    acc += Math.sqrt(r * r + dr * dr) * DPHI;
  }
  return acc;
}

/** Closed-form independent integral — finer grid than kernel NB (erratum-010). */
export function independentLayerArcs({ Wc, Hc, T, W, Lrice }, steps = NB * 4) {
  const dphi = TAU / steps;
  const rMidRice = [];
  const rMidNori = [];
  for (let i = 0; i <= steps; i++) {
    const r0 = r0At(i * dphi, Wc, Hc);
    const rp = Math.sqrt(r0 * r0 + 2 * T * Lrice / TAU);
    rMidRice.push((r0 + rp) / 2);
    rMidNori.push(rp + W / 2);
  }
  const integrate = (r) => {
    let acc = 0;
    for (let i = 0; i < steps; i++) {
      const a = r[i], b = r[i + 1];
      const dr = (b - a) / dphi;
      acc += Math.sqrt(a * a + dr * dr) * dphi;
    }
    return acc;
  };
  return { riceArcMm: integrate(rMidRice), noriArcMm: integrate(rMidNori) };
}

export function buildWinding(recipe) {
  const base = baseOf(recipe);
  const L = recipe.sheet.lengthMm;
  const T = base.riceThicknessMm;
  const W = base.noriThicknessMm;
  const { sRice0, sRice1, Lrice } = riceSpanMm(L, base.spreadStart, base.spreadEnd);
  const { Wc, Hc } = coreBoxMm(recipe);
  const fromUZero = recipe.windDirection !== 'fromULength';

  const r0b = new Float64Array(NB);
  const rp = new Float64Array(NB);
  const rn = new Float64Array(NB);
  const uInnerMm = new Float64Array(NB);
  const angleRad = new Float64Array(NB);

  let Rout = 0;
  for (let b = 0; b < NB; b++) {
    const phi = b * DPHI;
    angleRad[b] = phi;
    r0b[b] = r0At(phi, Wc, Hc);
    rp[b] = Math.sqrt(r0b[b] * r0b[b] + 2 * T * Lrice / TAU);
    rn[b] = rp[b] + W;
    if (rn[b] > Rout) Rout = rn[b];
    const s = sRice0 + Lrice * (b / NB);
    uInnerMm[b] = fromUZero ? s : sRice0 + sRice1 - s;
  }

  const Lbare = (L - sRice1) + sRice0;
  const Ravg = Rout - W / 2;
  const noriPerimeter = midArc((b) => rn[b] - W / 2);
  const enough = noriPerimeter <= L + EPS_LENGTH_MM;
  const phiOverlap = enough && Ravg > 1e-9 ? Math.min(TAU, Lbare / Ravg) : 0;
  const overlapBins = Math.round(phiOverlap / DPHI);

  const wrapIntersectionsByRay = new Int32Array(NB);
  const turnIndexAtRay = new Int32Array(NB);
  const innerBoundaryByRay = new Float64Array(NB);
  for (let b = 0; b < NB; b++) {
    wrapIntersectionsByRay[b] = b < overlapBins ? 2 : 1;
    turnIndexAtRay[b] = 0;
    innerBoundaryByRay[b] = r0b[b];
  }

  let outerMin = Infinity;
  let outerMax = 0;
  for (let b = 0; b < NB; b++) {
    let outer = rn[b];
    if (b < overlapBins) outer += W;
    if (outer < outerMin) outerMin = outer;
    if (outer > outerMax) outerMax = outer;
  }

  const fine = independentLayerArcs({ Wc, Hc, T, W, Lrice });
  const riceArcMm = fine.riceArcMm;
  const noriArcMm = fine.noriArcMm;

  let maxRoundTripErrMm = 0;
  for (let b = 0; b < NB; b++) {
    const u = uInnerMm[b];
    const frac = (u - sRice0) / Lrice;
    const phiFromU = fromUZero ? frac * TAU : (1 - frac) * TAU;
    const dPhi = Math.atan2(Math.sin(phiFromU - angleRad[b]), Math.cos(phiFromU - angleRad[b]));
    const errMm = Math.abs(dPhi) * Lrice / TAU;
    if (errMm > maxRoundTripErrMm) maxRoundTripErrMm = errMm;
  }

  const winding = {
    sheetLengthMm: L,
    sRice0,
    sRice1,
    Lrice,
    Lbare,
    T,
    W,
    Wc,
    Hc,
    Rout,
    Ravg,
    phiOverlap,
    overlapBins,
    noriPerimeter,
    riceArcMm,
    noriArcMm,
    angleRad,
    r0b,
    rp,
    rn,
    uInnerMm,
    innerBoundaryByRay,
    wrapIntersectionsByRay,
    turnIndexAtRay,
    maxRoundTripErrMm,
    diameterMinMm: 2 * outerMin,
    diameterMaxMm: 2 * outerMax,
    seam: {
      uStartMm: sRice1,
      uEndMm: sRice0,
      angleStartRad: 0,
      angleEndRad: phiOverlap,
      overlapMm: Lbare,
      overlapArcRad: phiOverlap,
      turnsMeasured: 1 + phiOverlap / TAU,
    },
  };
  return winding;
}

/** Hash domain: full sample arrays, not FixtureReport aggregates. */
export function windingForHash(w) {
  return {
    sheetLengthMm: w.sheetLengthMm,
    sRice0: w.sRice0,
    sRice1: w.sRice1,
    Wc: w.Wc,
    Hc: w.Hc,
    angleRad: w.angleRad,
    r0b: w.r0b,
    rp: w.rp,
    rn: w.rn,
    uInnerMm: w.uInnerMm,
    wrapIntersectionsByRay: w.wrapIntersectionsByRay,
    seam: w.seam,
  };
}
