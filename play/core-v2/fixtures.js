// F01/F02 runner and acceptance. Mutations live in core-v2.test.mjs.

import {
  EPS_AREA_RATIO,
  EPS_CORE_ASYMMETRY_MM,
  EPS_INVERT_MM,
  EPS_LENGTH_MM,
  EPS_RAY_FRACTION,
  F03_U_MM,
  MAX_AREA_RATIO_DELTA,
  MAX_CENTER_DELTA_MM,
  NB,
  TAU,
} from './units.js';
import {
  cucumberCatalogAreaMm2,
  deepClone,
  makeCucumberRecipe,
  makeF01Recipe,
  makeF02Recipe,
  makeF04aRecipe,
  makeF04bRecipe,
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

function dist2d(a, b) {
  const dx = (a.centerXmm ?? 0) - (b.centerXmm ?? 0);
  const dy = (a.centerYmm ?? 0) - (b.centerYmm ?? 0);
  return Math.hypot(dx, dy);
}

export function acceptF03(series) {
  const checks = [];
  const expected = ['valid', 'valid', 'valid', 'outsideModelScope', 'outsideModelScope'];
  const codes = [null, null, null, 'closure_window', 'closure_window'];
  for (let i = 0; i < series.length; i++) {
    const { report, winding, recipe, uMm } = series[i];
    const want = expected[i];
    if (report.status !== want) {
      checks.push(fail(`F03-${uMm}:status`, `${report.status} want ${want}`));
      continue;
    }
    checks.push(ok(`F03-${uMm}:status`));
    const w = report.placementWindowMm;
    checks.push(w.nearEdgeMm === 20 && w.farEdgeMm === 52.5
      ? ok(`F03-${uMm}:window`)
      : fail(`F03-${uMm}:window`, JSON.stringify(w)));
    if (want === 'valid') {
      checks.push(...acceptF02(report, winding, recipe).map((c) => (
        { ...c, name: `F03-${uMm}:${c.name}` }
      )));
    } else {
      const d = report.diagnostics[0];
      checks.push(d?.code === codes[i]
        ? ok(`F03-${uMm}:code`)
        : fail(`F03-${uMm}:code`, d?.code));
      checks.push(report.status !== 'valid'
        ? ok(`F03-${uMm}:no-valid-slice`)
        : fail(`F03-${uMm}:no-valid-slice`));
    }
  }
  const valid = series.filter((s) => s.report.status === 'valid');
  for (let i = 1; i < valid.length; i++) {
    const a = valid[i - 1].report.visiblePatches[0];
    const b = valid[i].report.visiblePatches[0];
    const d = dist2d(a, b);
    checks.push(d <= MAX_CENTER_DELTA_MM
      ? ok(`F03-cont-center-${i}`)
      : fail(`F03-cont-center-${i}`, d));
    const ratio = Math.max(a.areaMm2 / b.areaMm2, b.areaMm2 / a.areaMm2);
    checks.push(ratio - 1 <= MAX_AREA_RATIO_DELTA
      ? ok(`F03-cont-area-${i}`)
      : fail(`F03-cont-area-${i}`, ratio));
  }
  return checks;
}

export function acceptF04a(report, recipe) {
  const checks = [];
  checks.push(report.status === 'invalid' ? ok('status') : fail('status', report.status));
  const d = report.diagnostics[0];
  checks.push(d?.code === 'patch_out_of_sheet' ? ok('code') : fail('code', d?.code));
  checks.push(d?.context?.patchId === recipe.patches[0].id ? ok('patchId') : fail('patchId', d?.context?.patchId));
  checks.push(d?.context?.sheetLengthMm === 105 ? ok('sheet') : fail('sheet', d?.context?.sheetLengthMm));
  const fp = d?.context?.observedFootprintMm;
  checks.push(Array.isArray(fp) && fp[1] > 105 ? ok('footprint') : fail('footprint', JSON.stringify(fp)));
  checks.push(report.status !== 'valid' ? ok('no-valid-slice') : fail('no-valid-slice'));
  return checks;
}

export function acceptF04b(report, recipe) {
  const checks = [];
  checks.push(report.status === 'outsideModelScope' ? ok('status') : fail('status', report.status));
  const d = report.diagnostics[0];
  checks.push(d?.code === 'closure_window' ? ok('code') : fail('code', d?.code));
  checks.push(d?.context?.patchId === recipe.patches[0].id ? ok('patchId') : fail('patchId'));
  const w = d?.context?.placementWindowMm;
  checks.push(w && w.nearEdgeMm === 20 && w.farEdgeMm === 52.5 ? ok('window') : fail('window', JSON.stringify(w)));
  const fp = d?.context?.observedFootprintMm;
  checks.push(Array.isArray(fp) && fp[0] >= 0 && fp[1] <= 105 && fp[0] > 52.5
    ? ok('footprint-on-sheet')
    : fail('footprint-on-sheet', JSON.stringify(fp)));
  checks.push(report.status !== 'valid' ? ok('no-valid-slice') : fail('no-valid-slice'));
  return checks;
}

export function runF03() {
  const series = F03_U_MM.map((uMm) => {
    const recipe = makeCucumberRecipe(uMm);
    const report = runFixture(`F03-${uMm}`, recipe);
    const winding = report.status === 'valid' ? buildWinding(recipe) : null;
    return { uMm, recipe, report, winding };
  });
  const checks = acceptF03(series);
  return { series, checks, report: series[0].report };
}

export function runF04a() {
  const recipe = makeF04aRecipe();
  const report = runFixture('F04a', recipe);
  return { recipe, report, winding: null, checks: acceptF04a(report, recipe) };
}

export function runF04b() {
  const recipe = makeF04bRecipe();
  const report = runFixture('F04b', recipe);
  return { recipe, report, winding: null, checks: acceptF04b(report, recipe) };
}

export function allPassed(checks) {
  return checks.every((c) => c.ok);
}

export {
  makeF01Recipe, makeF02Recipe, makeCucumberRecipe, makeF04aRecipe, makeF04bRecipe,
  deepClone, cucumberCatalogAreaMm2,
};
