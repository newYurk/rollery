// Ring winding in millimetres. Formulas from geometry.js (ring branch), no import.
// F01/F02 only: hosomaki, fromUZero, one optional core filling.

import {
  DPHI,
  EPS_LENGTH_MM,
  NB,
  TAU,
  baseOf,
  patchCorePos,
  riceSpanMm,
} from './units.js';

export function riceOuterMm(Wc, Hc, T, Lrice) {
  return riceOuterFromAreaMm(Math.max(0, Wc * Hc), T, Lrice);
}

/** Внешний радиус риса из сохранения площади: π·rp² = площадь ядра + T·Lrice. */
export function riceOuterFromAreaMm(coreAreaMm2, T, Lrice) {
  return Math.sqrt((Math.max(0, coreAreaMm2) + T * Lrice) / Math.PI);
}

export function r0At(phi, Wc, Hc) {
  const c = Math.abs(Math.cos(phi));
  const s = Math.abs(Math.sin(phi));
  const rx = c > 1e-12 ? (Wc / 2) / c : Infinity;
  const ry = s > 1e-12 ? (Hc / 2) / s : Infinity;
  return Math.min(rx, ry);
}

/**
 * Где луч φ выходит из прямоугольника, СМЕЩЁННОГО от центра. 0 — не задевает.
 * Обычный slab-тест: по каждой оси считаем вход и выход, берём пересечение.
 */
export function boxExitAt(phi, box) {
  const dx = Math.cos(phi);
  const dy = Math.sin(phi);
  let t0 = -Infinity;
  let t1 = Infinity;
  for (const [d, c, h] of [[dx, box.cx, box.hw], [dy, box.cy, box.hh]]) {
    if (Math.abs(d) < 1e-12) {
      if (Math.abs(c) > h) return 0; // луч параллелен полосе и вне её
      continue;
    }
    const a = (c - h) / d;
    const b = (c + h) / d;
    t0 = Math.max(t0, Math.min(a, b));
    t1 = Math.min(t1, Math.max(a, b));
  }
  if (t1 < Math.max(t0, 0)) return 0;
  return Math.max(0, t1);
}

/**
 * Граница ядра на луче φ — там, где кончается ОБЪЕДИНЕНИЕ кусков, а не
 * описанный вокруг них прямоугольник (#186). У прямоугольника пустые углы:
 * у футомаки они занимали 36 % ядра, входили в бюджет площади и раздували
 * ролл на 2,2 мм. Рис обязан обтекать начинки, а не отступать от рамки.
 */
export function r0AtBoxes(phi, boxes) {
  let r = 0;
  for (const b of boxes) {
    const t = boxExitAt(phi, b);
    if (t > r) r = t;
  }
  return r;
}

/** Площадь, охваченная границей r0(φ): ∫ r²/2 dφ. Ровно то, что не рис. */
export function coreAreaOf(r0b) {
  let acc = 0;
  for (let b = 0; b < NB; b++) acc += r0b[b] * r0b[b];
  return acc * DPHI / 2;
}

/**
 * Куски ядра как прямоугольники. Пустой ролл — один прямоугольник базы;
 * с начинками — по прямоугольнику на кусок, и рис обтекает их объединение.
 */
export function coreBoxesMm(recipe) {
  const base = baseOf(recipe);
  if (!recipe.patches.length) {
    return [{ cx: 0, cy: 0, hw: base.emptyCoreWidthMm / 2, hh: base.emptyCoreHeightMm / 2 }];
  }
  return recipe.patches.map((p) => {
    const { x, y } = patchCorePos(recipe, p);
    return { cx: x, cy: y, hw: p.widthMm / 2, hh: p.heightMm / 2 + base.noriThicknessMm };
  });
}

/** Описанный прямоугольник — для отказа core_overflow и для отчёта. */
function coreBoxMm(recipe) {
  const boxes = coreBoxesMm(recipe);
  let halfW = 0;
  let halfH = 0;
  for (const b of boxes) {
    halfW = Math.max(halfW, Math.abs(b.cx) + b.hw);
    halfH = Math.max(halfH, Math.abs(b.cy) + b.hh);
  }
  return { Wc: 2 * halfW, Hc: 2 * halfH };
}

function r0MeanOf(r0b) {
  let acc = 0;
  for (let b = 0; b < NB; b++) acc += r0b[b];
  return acc / NB;
}

/** Лента риса длины Lrice в кольце площади T·Lrice. Шаг ≈ T, витков = Lrice / (2π r̄).
 *  Средняя линия: r̄0+pitch/2 → rp−pitch/2, свип turns·TAU.
 *  Не grown+pitch/2 (это +pitch/2 наружу и 111 мм вместо Lrice).
 *  Длина = turns·2π·(r̄0+rp)/2 = Lrice. */
export function riceSpiralSpec(r0b, rpCircle, Lrice) {
  const r0m = r0MeanOf(r0b);
  const meanR = Math.max(1e-6, (r0m + rpCircle) / 2);
  const turns = Lrice / (TAU * meanR);
  const pitch = turns > 1e-9 ? (rpCircle - r0m) / turns : rpCircle - r0m;
  const steps = Math.max(1, Math.round(turns * NB));
  const dtheta = turns * TAU / steps;
  const rin = new Float64Array(steps);
  const rout = new Float64Array(steps);
  const mid0 = r0m + pitch / 2;
  const mid1 = rpCircle - pitch / 2;
  let pathMm = 0;
  for (let i = 0; i < steps; i++) {
    const t = steps === 1 ? 0.5 : i / (steps - 1);
    const mid = mid0 + (mid1 - mid0) * t;
    pathMm += mid * dtheta;
    rin[i] = mid - pitch / 2;
    rout[i] = mid + pitch / 2;
  }
  return { turns, pitch, steps, rin, rout, r0Mean: r0m, pathMm };
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
  const rpCircle = riceOuterMm(Wc, Hc, T, Lrice);
  const r0s = [];
  for (let i = 0; i <= steps; i++) r0s.push(r0At(i * dphi, Wc, Hc));
  let r0m = 0;
  for (let i = 0; i < steps; i++) r0m += r0s[i];
  r0m /= steps;
  const spec = riceSpiralSpec(
    Float64Array.from({ length: NB }, (_, b) => r0At(b * DPHI, Wc, Hc)),
    rpCircle,
    Lrice,
  );
  const rMidNori = [];
  const noriSteps = steps;
  for (let i = 0; i <= noriSteps; i++) rMidNori.push(rpCircle + W / 2);
  const integrate = (r, d) => {
    let acc = 0;
    for (let i = 0; i < r.length - 1; i++) {
      const a = r[i], b = r[i + 1];
      const dr = (b - a) / d;
      acc += Math.sqrt(a * a + dr * dr) * d;
    }
    return acc;
  };
  return {
    riceArcMm: spec.pathMm,
    noriArcMm: integrate(rMidNori, TAU / noriSteps),
  };
}

export function buildWinding(recipe) {
  const base = baseOf(recipe);
  const L = recipe.sheet.lengthMm;
  const T = base.riceThicknessMm;
  const W = base.noriThicknessMm;
  const { sRice0, sRice1, Lrice } = riceSpanMm(L, base.spreadStart, base.spreadEnd);
  const boxes = coreBoxesMm(recipe);
  const { Wc, Hc } = coreBoxMm(recipe);
  const fromUZero = recipe.windDirection !== 'fromULength';

  const r0b = new Float64Array(NB);
  const rp = new Float64Array(NB);
  const rn = new Float64Array(NB);
  const uInnerMm = new Float64Array(NB);
  const angleRad = new Float64Array(NB);

  // Граница ядра — сначала, потому что из неё берётся площадь, а из площади rp.
  for (let b = 0; b < NB; b++) r0b[b] = r0AtBoxes(b * DPHI, boxes);
  const coreAreaMm2 = coreAreaOf(r0b);
  const rpCircle = riceOuterFromAreaMm(coreAreaMm2, T, Lrice);
  let Rout = 0;
  for (let b = 0; b < NB; b++) {
    const phi = b * DPHI;
    angleRad[b] = phi;
    rp[b] = rpCircle;
    rn[b] = rp[b] + W;
    if (rn[b] > Rout) Rout = rn[b];
    const s = sRice0 + Lrice * (b / NB);
    uInnerMm[b] = fromUZero ? s : sRice0 + sRice1 - s;
  }

  const spiral = riceSpiralSpec(r0b, rpCircle, Lrice);

  const Lbare = (L - sRice1) + sRice0;
  const Ravg = Rout - W / 2;
  const noriPerimeter = midArc((b) => rn[b] - W / 2);
  const enough = noriPerimeter <= L + EPS_LENGTH_MM;
  // ⚑ НАХЛЁСТ — ЭТО ОСТАТОК ЛИСТА, А НЕ ГОЛЫЕ ПОЛЯ (#165).
  // Стояло Lbare / Ravg: длина полей без риса. Но лист расходуется не на поля,
  // а на оборот; сколько осталось после оборота — столько и лежит внахлёст.
  // Прежняя формула не сходилась ни в одну сторону: хосомаки ВЫДУМЫВАЛ лист
  // (108,16 израсходовано из 105), футомаки ТЕРЯЛ (185,27 из 210 — 11,8 % не
  // лежали нигде). Теперь по построению: периметр + нахлёст = длина листа.
  const overlapMm = L - noriPerimeter;
  const phiOverlap = enough && Ravg > 1e-9 ? Math.min(TAU, overlapMm / Ravg) : 0;
  // Клампом длина перестала бы сохраняться: лист длиннее двух оборотов — это
  // третий слой, а модель различает только один и два. Честно назвать, не молча.
  const wrapsBeyondTwo = enough && Ravg > 1e-9 && overlapMm / Ravg > TAU;
  const overlapBins = Math.round(phiOverlap / DPHI);

  const wrapIntersectionsByRay = new Int32Array(NB);
  const turnIndexAtRay = new Int32Array(NB);
  const innerBoundaryByRay = new Float64Array(NB);
  for (let b = 0; b < NB; b++) {
    wrapIntersectionsByRay[b] = b < overlapBins ? 2 : 1;
    // Индекс ВНЕШНЕГО витка риса на этом луче. Лента делает turns оборотов,
    // поэтому на части лучей она лежит вторым слоем, а на остальных — одним.
    // Раньше стояло min(1, floor(turns)) — одинаково по всем лучам, то есть
    // поле в отчёте было, а информации в нём не было.
    turnIndexAtRay[b] = Math.max(0, Math.floor((spiral.steps - 1 - b) / NB));
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

  const riceArcMm = spiral.pathMm;
  const noriArcMm = noriPerimeter;

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
    coreBoxes: boxes,
    coreAreaMm2,
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
    riceTurns: spiral.turns,
    ricePitchMm: spiral.pitch,
    riceSteps: spiral.steps,
    riceRin: spiral.rin,
    riceRout: spiral.rout,
    wrapsBeyondTwo,
    seam: {
      // Шов идёт от места, где кончился первый оборот, до конца листа.
      uStartMm: Math.min(L, noriPerimeter),
      uEndMm: L,
      angleStartRad: 0,
      angleEndRad: phiOverlap,
      overlapMm: phiOverlap * Ravg,
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
    riceTurns: w.riceTurns,
    ricePitchMm: w.ricePitchMm,
    seam: w.seam,
  };
}
