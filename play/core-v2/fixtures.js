// F01/F02 runner and acceptance. Mutations live in core-v2.test.mjs.

import {
  EPS_AREA_RATIO,
  EPS_CORE_ASYMMETRY_MM,
  EPS_INVERT_MM,
  EPS_LENGTH_MM,
  EPS_RAY_FRACTION,
  NB,
  TAU,
} from './units.js';
import {
  cucumberCatalogAreaMm2,
  deepClone,
  makeF01Recipe,
  makeF02Recipe,
} from './recipe.js';
import { validateRecipe } from './validate.js';
import { buildWinding, independentLayerArcs } from './winding.js';
import { sampleSection } from './section.js';
import { measure, rejectReport } from './measure.js';
import { canonicalize } from './hash.js';

export function runFixture(fixtureId, recipe) {
  const before = canonicalize(recipe);
  const verdict = validateRecipe(recipe);
  if (verdict.status !== 'valid') {
    const report = rejectReport(recipe, fixtureId, verdict.status, verdict.diagnostics);
    if (canonicalize(recipe) !== before) {
      throw new Error('kernel mutated the input recipe');
    }
    return report;
  }
  const winding = buildWinding(recipe);
  const vSliceMm = recipe.sheet.widthMm / 2;
  const section = sampleSection(recipe, winding, vSliceMm);
  const report = measure(recipe, winding, section, fixtureId, 'valid', []);
  if (canonicalize(recipe) !== before) {
    throw new Error('kernel mutated the input recipe');
  }
  return report;
}

function finite(n) {
  return typeof n === 'number' && Number.isFinite(n);
}

function fail(name, detail) {
  return { ok: false, name, detail };
}

function ok(name) {
  return { ok: true, name };
}

function innerUMonotone(report) {
  const u = report.sheetMap.uAtRayMm;
  const n = u.length;
  let worstDrop = { i: -1, du: 0 };
  const drops = [];
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n;
    const du = u[j] - u[i];
    if (du <= 0) drops.push({ i, du });
    if (du < worstDrop.du) worstDrop = { i, du };
  }
  // Exactly one discontinuity (the inner-u jump). Every other adjacent pair,
  // including the circular pair if it is not the jump, must increase.
  if (drops.length !== 1) {
    return fail('invertibility', `inner-u discontinuities: ${drops.length}, expected 1`);
  }
  if (worstDrop.i !== drops[0].i) {
    return fail('invertibility', 'jump pair mismatch');
  }
  return ok('invertibility');
}

export function acceptF01(report, winding) {
  const checks = [];
  const push = (c) => checks.push(c);
  if (report.status !== 'valid') push(fail('status', report.status));
  else push(ok('status'));

  const cov = Math.abs(report.sheet.coveredLengthMm - 105);
  push(cov <= EPS_LENGTH_MM ? ok('coverage') : fail('coverage', report.sheet.coveredLengthMm));
  push(report.sheet.phantomLengthMm <= EPS_LENGTH_MM ? ok('phantom') : fail('phantom', report.sheet.phantomLengthMm));
  push(report.sheet.uncoveredLengthMm <= EPS_LENGTH_MM ? ok('uncovered') : fail('uncovered', report.sheet.uncoveredLengthMm));

  const oracle = independentLayerArcs({
    Wc: winding.Wc, Hc: winding.Hc, T: winding.T, W: winding.W, Lrice: winding.Lrice,
  });
  for (const row of report.sheet.arcByLayerMm) {
    const want = row.layerId === 'rice' ? oracle.riceArcMm : oracle.noriArcMm;
    const d = Math.abs(row.arcMm - want);
    push(d <= EPS_LENGTH_MM
      ? ok(`arc:${row.layerId}`)
      : fail(`arc:${row.layerId}`, `${row.arcMm} vs ${want}`));
  }
  const rice = report.sheet.arcByLayerMm.find((r) => r.layerId === 'rice');
  const nori = report.sheet.arcByLayerMm.find((r) => r.layerId === 'nori');
  if (rice && nori && Math.abs(rice.arcMm - nori.arcMm) <= EPS_LENGTH_MM) {
    push(fail('arc:layers-equal', 'rice and nori arcs must differ'));
  } else push(ok('arc:layers-differ'));

  push(report.sheet.uMinMm >= 0 && report.sheet.uMaxMm <= 105 ? ok('bounds') : fail('bounds'));

  const seam = report.seam;
  const seamOk = seam
    && seam.uStartMm >= 0 && seam.uStartMm <= 105
    && seam.uEndMm >= 0 && seam.uEndMm <= 105
    && seam.angleStartRad >= 0 && seam.angleStartRad < TAU
    && seam.angleEndRad >= 0 && seam.angleEndRad < TAU
    && Math.abs(seam.overlapMm - seam.overlapArcRad * winding.Ravg) <= EPS_LENGTH_MM;
  push(seamOk ? ok('seam') : fail('seam', JSON.stringify(seam)));

  const twoFrac = report._meta.twoIntersectionFraction;
  const wantTwo = seam.overlapArcRad / TAU;
  push(Math.abs(twoFrac - wantTwo) <= EPS_RAY_FRACTION
    ? ok('nori-rays')
    : fail('nori-rays', `${twoFrac} vs ${wantTwo}`));
  const oneFrac = [...report.roll.wrapIntersectionsByRay].filter((n) => n === 1).length / NB;
  push(Math.abs(oneFrac - (1 - wantTwo)) <= EPS_RAY_FRACTION ? ok('nori-rays-one') : fail('nori-rays-one', oneFrac));
  const bad = [...report.roll.wrapIntersectionsByRay].some((n) => n !== 1 && n !== 2);
  push(!bad ? ok('nori-rays-01') : fail('nori-rays-01', '0 or ≥3 intersections'));

  push(innerUMonotone(report));
  push(report.sheetMap.maxRoundTripErrMm <= EPS_INVERT_MM
    ? ok('roundtrip')
    : fail('roundtrip', report.sheetMap.maxRoundTripErrMm));

  const r0 = report.roll.innerBoundaryByRay;
  const dR = Math.max(...r0) - Math.min(...r0);
  push(r0.every(finite) && dR > EPS_CORE_ASYMMETRY_MM
    ? ok('core')
    : fail('core', dR));

  return checks;
}

export function acceptF02(report, winding, recipe) {
  const checks = acceptF01(report, winding);
  const vis = report.visiblePatches;
  checks.push(vis.length === 1 && vis[0].id === recipe.patches[0].id
    ? ok('visible')
    : fail('visible', vis.map((p) => p.id).join(',')));
  const area = vis[0]?.areaMm2 ?? 0;
  checks.push(area > 0 ? ok('area-sign') : fail('area-sign', area));
  const catalog = cucumberCatalogAreaMm2();
  const ratio = Math.max(area / catalog, catalog / area);
  checks.push(ratio <= EPS_AREA_RATIO
    ? ok('catalog-anchor')
    : fail('catalog-anchor', `${area} / ${catalog} = ${ratio}`));
  checks.push(finite(vis[0]?.centerXmm) && finite(vis[0]?.centerYmm)
    ? ok('center')
    : fail('center'));
  const w = report.placementWindowMm;
  checks.push(w.nearEdgeMm === 20 && w.farEdgeMm === 52.5
    ? ok('window')
    : fail('window', JSON.stringify(w)));
  return checks;
}

export function runF01() {
  const recipe = makeF01Recipe();
  const report = runFixture('F01', recipe);
  const winding = report.status === 'valid' ? buildWinding(recipe) : null;
  const checks = report.status === 'valid' ? acceptF01(report, winding) : [fail('status', report.status)];
  return { recipe, report, winding, checks };
}

export function runF02() {
  const recipe = makeF02Recipe();
  const report = runFixture('F02', recipe);
  const winding = report.status === 'valid' ? buildWinding(recipe) : null;
  const checks = report.status === 'valid' ? acceptF02(report, winding, recipe) : [fail('status', report.status)];
  return { recipe, report, winding, checks };
}

export function allPassed(checks) {
  return checks.every((c) => c.ok);
}

export { makeF01Recipe, makeF02Recipe, deepClone, cucumberCatalogAreaMm2 };
