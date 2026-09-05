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
      arcByLayerMm: [
        { layerId: 'rice', u0Mm: winding.sRice0, u1Mm: winding.sRice1, arcMm: winding.riceArcMm },
        { layerId: 'nori', u0Mm: 0, u1Mm: L, arcMm: winding.noriArcMm },
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
