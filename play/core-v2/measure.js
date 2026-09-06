// FixtureReport from winding + section. Named EPS values are copied onto the report.

import {
  EPS_CORE_ASYMMETRY_MM,
  EPS_INVERT_MM,
  EPS_LENGTH_MM,
  EPS_RAY_FRACTION,
  EPS_AREA_RATIO,
  NB,
  PLACEMENT_EDGE_MARGIN_MM,
  placementWindowMm,
} from './units.js';
import { hashValue, quantize } from './hash.js';
import { windingForHash } from './winding.js';
import { sectionForHash } from './section.js';

export function measure(recipe, winding, section, fixtureId, status, diagnostics) {
  const L = recipe.sheet.lengthMm;
  const window = placementWindowMm(recipe.sheet);
  const two = [...winding.wrapIntersectionsByRay].filter((n) => n === 2).length;

  const report = {
    fixtureId,
    status,
    diagnostics,
    placementWindowMm: window,
    sheet: {
      lengthMm: L,
      coveredLengthMm: L,
      uncoveredLengthMm: 0,
      phantomLengthMm: 0,
      uMinMm: 0,
      uMaxMm: L,
      // ── НОРИ РАЗДЕЛЕНА НА ВИТОК И НАХЛЁСТ (#205, пункт 4) ─────────────────────
      // Стояло одной строкой: `u0Mm: 0, u1Mm: L, arcMm: winding.noriArcMm`. Объявленный
      // диапазон — весь лист, а дуга — ОДИН ОБОРОТ, и разница молчала в отчёте:
      //   F01  объявлено 105 мм, дуга 90,519 → 14,481 мм листа нигде  (97 × EPS)
      //   F02  объявлено 105 мм, дуга 92,558 → 12,442 мм              (83 × EPS)
      //   F05  объявлено 210 мм, дуга 146,227 → 63,773 мм — 30 % листа (425 × EPS)
      // Замер показал, чем именно была недостача: на всех трёх она РАВНА `seam.overlapMm`
      // до последнего знака. То есть отчёт умалчивал не о погрешности, а о втором заходе
      // нахлёста — который сам же и посчитал, в `seam`.
      //
      // Теперь у каждой строки объявленный диапазон совпадает с её дугой, как давно совпадал
      // у риса, а две строки нори в сумме дают лист.
      //
      // ⚠ ЭТА СУММА — ТОЖДЕСТВО, А НЕ ЗАМЕР, и сторожа на неё ставить нельзя. `overlapMm`
      // определён как `L − noriPerimeter`, а `noriArcMm` и есть `noriPerimeter`; значит
      // «виток + нахлёст = L» сокращается в `L = L` при любых числах — ровно та тавтология,
      // на которой сгорела приёмка шва в #204. Независимая проверка дуги здесь одна и она
      // уже есть: `arc:nori` в fixtures.js сверяет интеграл по лучам с замкнутой формулой
      // `τ·(rp + W/2)` — два разных пути к одному числу.
      arcByLayerMm: [
        { layerId: 'rice', u0Mm: winding.sRice0, u1Mm: winding.sRice1, arcMm: winding.riceArcMm },
        { layerId: 'nori', u0Mm: 0, u1Mm: winding.seam.uStartMm, arcMm: winding.noriArcMm },
        { layerId: 'nori-overlap', u0Mm: winding.seam.uStartMm, u1Mm: winding.seam.uEndMm, arcMm: winding.seam.overlapMm },
      ],
    },
    seam: { ...winding.seam },
    rays: { angleRad: Array.from(winding.angleRad) },
    roll: {
      diameterMinMm: winding.diameterMinMm,
      diameterMaxMm: winding.diameterMaxMm,
      wrapIntersectionsByRay: Array.from(winding.wrapIntersectionsByRay),
      innerBoundaryByRay: Array.from(winding.innerBoundaryByRay),
    },
    sheetMap: {
      uAtRayMm: Array.from(winding.uInnerMm),
      turnIndexAtRay: Array.from(winding.turnIndexAtRay),
      maxRoundTripErrMm: winding.maxRoundTripErrMm,
    },
    visiblePatches: section.visiblePatches.map((p) => ({
      id: p.id,
      areaMm2: p.areaMm2,
      centerXmm: p.centerXmm,
      centerYmm: p.centerYmm,
    })),
    hashes: {
      recipe: hashValue(recipe),
      winding: hashValue(windingForHash(winding)),
      section: hashValue(sectionForHash(section)),
    },
    eps: {
      EPS_LENGTH_MM,
      EPS_INVERT_MM,
      EPS_CORE_ASYMMETRY_MM,
      EPS_RAY_FRACTION,
      EPS_AREA_RATIO,
      PLACEMENT_EDGE_MARGIN_MM,
      NB,
    },
    _meta: {
      twoIntersectionCount: two,
      twoIntersectionFraction: two / NB,
      overlapArcFraction: winding.seam.overlapArcRad / (Math.PI * 2),
      RavgMm: winding.Ravg,
    },
  };
  // Отчёт — публикуемый артефакт: его кладут в git и сравнивают между прогонами,
  // в том числе на разных машинах. Сырые числа тригонометрии расходятся в
  // последнем бите, поэтому на сетку кладём не только хеши, но и всё тело (#175).
  return quantize(report);
}

export function rejectReport(recipe, fixtureId, status, diagnostics) {
  const window = recipe?.sheet ? placementWindowMm(recipe.sheet) : { nearEdgeMm: 20, farEdgeMm: 52.5 };
  return {
    fixtureId,
    status,
    diagnostics,
    placementWindowMm: window,
    sheet: {
      lengthMm: recipe?.sheet?.lengthMm ?? 0,
      coveredLengthMm: 0,
      uncoveredLengthMm: 0,
      phantomLengthMm: 0,
      uMinMm: 0,
      uMaxMm: 0,
      arcByLayerMm: [],
    },
    visiblePatches: [],
    hashes: {
      recipe: recipe ? hashValue(recipe) : '',
      winding: '',
      section: '',
    },
    eps: {
      EPS_LENGTH_MM,
      EPS_INVERT_MM,
      EPS_CORE_ASYMMETRY_MM,
      EPS_RAY_FRACTION,
      EPS_AREA_RATIO,
      PLACEMENT_EDGE_MARGIN_MM,
      NB,
    },
  };
}
