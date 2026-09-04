import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  runF01, runF02, runF03, runF04a, runF04b, runF05, runF06, runF07,
  acceptF01, acceptF02, allPassed,
  makeF01Recipe, makeCucumberRecipe, cucumberCatalogAreaMm2,
} from './fixtures.js';
import { validateRecipe } from './validate.js';
import { buildWinding, independentLayerArcs } from './winding.js';
import { CUCUMBER, EPS_AREA_RATIO, EPS_CORE_ASYMMETRY_MM, HOSOMAKI_DIAMETER_MM, NB, hosogiriBox, placementWindowMm } from './units.js';
import {
  cutFractions, firstCutFraction, pieceCountOf, pieceLeftOfCut,
  pieceLengthMm, snapCutFraction,
} from './knife.js';
import { catalogAreaMm2, cutFillSector, makeF05Recipe, makeHosogiriRecipe } from './recipe.js';
import { sampleSection } from './section.js';
import { adapt, adaptScenario } from './adapter.js';

function clone(x) { return structuredClone(x); }

test('F01 green', () => {
  const r = runF01();
  assert.equal(r.report.status, 'valid');
  assert.ok(allPassed(r.checks), r.checks.filter((c) => !c.ok).map((c) => c.name + ':' + c.detail).join('; '));
});

test('F02 green', () => {
  const r = runF02();
  assert.equal(r.report.status, 'valid');
  assert.ok(allPassed(r.checks), r.checks.filter((c) => !c.ok).map((c) => c.name + ':' + c.detail).join('; '));
});

test('adapter snapshot: F01/F02, refuse stays refuse', () => {
  const a = adaptScenario('empty');
  assert.equal(a.ok, true);
  assert.ok(a.winding.diameterMinMm >= HOSOMAKI_DIAMETER_MM.min);
  const b = adaptScenario('kappa');
  assert.equal(b.ok, true);
  assert.equal(b.recipe.patches[0].cut, 'брусок');
  assert.ok(b.winding.diameterMaxMm <= HOSOMAKI_DIAMETER_MM.max);
  const bad = adapt(makeCucumberRecipe(70));
  assert.equal(bad.ok, false);
  assert.equal(bad.winding, null);
});

test('hosomaki diameter in chef corridor 28-32 mm', () => {
  const check = (name, w) => {
    const dmin = 2 * Math.min(...w.rn);
    const dmax = 2 * w.Rout;
    assert.ok(dmin >= HOSOMAKI_DIAMETER_MM.min, `${name} dmin ${dmin}`);
    assert.ok(dmax <= HOSOMAKI_DIAMETER_MM.max, `${name} dmax ${dmax}`);
  };
  check('F01', buildWinding(makeF01Recipe()));
  check('F02', buildWinding(makeCucumberRecipe(36.25)));
  check('hosogiri', buildWinding(makeHosogiriRecipe()));
});

test('hosogiri: six 3 mm sticks, not a sector', () => {
  const recipe = makeHosogiriRecipe();
  assert.equal(validateRecipe(recipe).status, 'valid');
  const box = hosogiriBox();
  const patch = recipe.patches[0];
  assert.equal(patch.cut, 'hosogiri');
  assert.equal(patch.stickCount, 6);
  assert.equal(patch.widthMm, box.widthMm);
  assert.equal(catalogAreaMm2(patch), 6 * 3 * 3);
  const sectorish = patch.widthMm * patch.heightMm * 0.5;
  assert.ok(catalogAreaMm2(patch) !== sectorish);
  const winding = buildWinding(recipe);
  const section = sampleSection(recipe, winding, recipe.sheet.widthMm / 2);
  assert.equal(section.visiblePatches[0].areaMm2, 54);
});

test('F06 hashes repeat', () => {
  const a = runF01();
  const b = runF01();
  assert.equal(a.report.hashes.recipe, b.report.hashes.recipe);
  assert.equal(a.report.hashes.winding, b.report.hashes.winding);
  assert.equal(a.report.hashes.section, b.report.hashes.section);
  const c = runF02();
  const d = runF02();
  assert.equal(c.report.hashes.winding, d.report.hashes.winding);
});

test('mutation: recorded hand on F01', () => {
  const recipe = { ...makeF01Recipe(), hand: { mode: 'recorded', seed: 1, press: 1, speed: 1, wobble: 0 } };
  const v = validateRecipe(recipe);
  assert.equal(v.status, 'invalid');
  assert.equal(v.diagnostics[0].code, 'non_neutral_hand');
  assert.notEqual(v.diagnostics[0].code, 'non_neutral_hand_in_puzzle');
});

test('mutation: missing hand', () => {
  const recipe = { ...makeF01Recipe() };
  delete recipe.hand;
  const v = validateRecipe(recipe);
  assert.equal(v.status, 'invalid');
  assert.equal(v.diagnostics[0].code, 'non_neutral_hand');
  assert.equal(v.diagnostics[0].context.observedHandMode, 'missing');
});

test('mutation: missing windDirection', () => {
  const recipe = { ...makeF01Recipe() };
  delete recipe.windDirection;
  const v = validateRecipe(recipe);
  assert.equal(v.diagnostics[0].code, 'recipe_missing_wind_direction');
});

test('mutation: copy nori arc into rice', () => {
  const r = runF01();
  const report = clone(r.report);
  const rice = report.sheet.arcByLayerMm.find((x) => x.layerId === 'rice');
  const nori = report.sheet.arcByLayerMm.find((x) => x.layerId === 'nori');
  rice.arcMm = nori.arcMm;
  const checks = acceptF01(report, r.winding);
  assert.ok(checks.some((c) => !c.ok && c.name.startsWith('arc:rice')));
});

test('mutation: arcMm in catalog units (forget ×U_MM)', () => {
  const r = runF01();
  const report = clone(r.report);
  for (const row of report.sheet.arcByLayerMm) row.arcMm /= 5;
  const checks = acceptF01(report, r.winding);
  assert.ok(checks.some((c) => !c.ok && c.name.startsWith('arc:')));
});

test('mutation: innerBoundaryByRay scalar', () => {
  const r = runF01();
  const report = clone(r.report);
  const mean = report.roll.innerBoundaryByRay.reduce((a, b) => a + b, 0) / NB;
  report.roll.innerBoundaryByRay = report.roll.innerBoundaryByRay.map(() => mean);
  const checks = acceptF01(report, r.winding);
  assert.ok(checks.some((c) => !c.ok && c.name === 'core'));
});

test('mutation: sector cutFill on a cucumber bar', () => {
  const r = runF02();
  const catalog = cucumberCatalogAreaMm2();
  const fake = r.report.visiblePatches[0].areaMm2 * cutFillSector();
  const ratio = Math.max(fake / catalog, catalog / fake);
  assert.ok(ratio > EPS_AREA_RATIO, ratio);
});

test('mutation: scale all areaMm2 by 0.83', () => {
  const r = runF02();
  const report = clone(r.report);
  report.visiblePatches[0].areaMm2 *= 0.83;
  const checks = acceptF02(report, r.winding, r.recipe);
  assert.ok(checks.some((c) => !c.ok && c.name === 'catalog-anchor'));
});

test('mutation: corrupt inner u on two-layer nori rays', () => {
  const r = runF01();
  const report = clone(r.report);
  for (let i = 0; i < NB; i++) {
    if (report.roll.wrapIntersectionsByRay[i] === 2) report.sheetMap.uAtRayMm[i] = 40;
  }
  const checks = acceptF01(report, r.winding);
  assert.ok(checks.some((c) => !c.ok && c.name === 'invertibility'));
});

test('mutation: write outer tail u on two-layer rays', () => {
  const r = runF01();
  const report = clone(r.report);
  for (let i = 0; i < NB; i++) {
    if (report.roll.wrapIntersectionsByRay[i] === 2) {
      report.sheetMap.uAtRayMm[i] = 105 - (i / r.winding.overlapBins) * r.winding.Lbare;
    }
  }
  const checks = acceptF01(report, r.winding);
  assert.ok(checks.some((c) => !c.ok && c.name === 'invertibility'));
});

test('mutation: use nori radius as rice integral', () => {
  const r = runF01();
  const fake = independentLayerArcs({
    Wc: r.winding.Wc, Hc: r.winding.Hc, T: r.winding.T, W: r.winding.W, Lrice: r.winding.Lrice,
  });
  const report = clone(r.report);
  report.sheet.arcByLayerMm.find((x) => x.layerId === 'rice').arcMm = fake.noriArcMm;
  const checks = acceptF01(report, r.winding);
  assert.ok(checks.some((c) => !c.ok && c.name === 'arc:rice'));
});

test('empty core asymmetry exceeds EPS_CORE_ASYMMETRY_MM', () => {
  const r = runF01();
  const r0 = r.report.roll.innerBoundaryByRay;
  assert.ok(Math.max(...r0) - Math.min(...r0) > EPS_CORE_ASYMMETRY_MM);
});

test('F03 series: last three-minus-two valid, then refuse, continuous inside', () => {
  const r = runF03();
  assert.ok(allPassed(r.checks), r.checks.filter((c) => !c.ok).map((c) => c.name + ':' + c.detail).join('; '));
  assert.equal(r.series[2].report.status, 'valid');
  assert.equal(r.series[3].report.status, 'outsideModelScope');
  assert.equal(r.series[3].report.diagnostics[0].code, 'closure_window');
});

test('F04a: footprint past sheet is invalid, not outsideModelScope', () => {
  const r = runF04a();
  assert.ok(allPassed(r.checks), r.checks.filter((c) => !c.ok).map((c) => c.name + ':' + c.detail).join('; '));
  assert.equal(r.report.status, 'invalid');
  assert.equal(r.report.diagnostics[0].code, 'patch_out_of_sheet');
});

test('F04b: on-sheet but past L/2 is outsideModelScope, not invalid', () => {
  const r = runF04b();
  assert.ok(allPassed(r.checks), r.checks.filter((c) => !c.ok).map((c) => c.name + ':' + c.detail).join('; '));
  assert.equal(r.report.status, 'outsideModelScope');
  assert.equal(r.report.diagnostics[0].code, 'closure_window');
});

test('mutation: full-sheet window would legalize F04b', () => {
  const w = placementWindowMm({ lengthMm: 105 });
  assert.notEqual(w.nearEdgeMm, 0);
  assert.notEqual(w.farEdgeMm, 105);
  const v = validateRecipe(makeCucumberRecipe(70));
  assert.equal(v.status, 'outsideModelScope');
});

test('F04a/F04b diagnostics repeat', () => {
  assert.equal(runF04a().report.diagnostics[0].code, runF04a().report.diagnostics[0].code);
  assert.equal(runF04b().report.diagnostics[0].code, runF04b().report.diagnostics[0].code);
});

test('F05 array order does not change hashes', () => {
  const r = runF05();
  assert.ok(allPassed(r.checks), r.checks.filter((c) => !c.ok).map((c) => c.name + ':' + c.detail).join('; '));
  assert.equal(r.abc.report.hashes.winding, r.cab.report.hashes.winding);
  assert.equal(r.abc.report.hashes.section, r.cab.report.hashes.section);
});

test('F06 round-trip and new instance', () => {
  const r = runF06();
  assert.ok(allPassed(r.checks), r.checks.filter((c) => !c.ok).map((c) => c.name + ':' + c.detail).join('; '));
});

test('F07 coordinate not ordinal; same-material overlap is invalid', () => {
  const r = runF07();
  assert.ok(allPassed(r.checks), r.checks.filter((c) => !c.ok).map((c) => c.name + ':' + c.detail).join('; '));
  assert.equal(r.overlap.report.diagnostics[0].code, 'patch_material_overlap');
});

test('knife: 6/8 pieces, first cut at half, snap interior only', () => {
  const hoso = makeF01Recipe();
  const futo = makeF05Recipe();
  assert.equal(pieceCountOf(hoso), 6);
  assert.equal(pieceCountOf(futo), 8);
  assert.equal(firstCutFraction(6), 0.5);
  assert.equal(firstCutFraction(8), 0.5);
  assert.equal(snapCutFraction(0.48, 6), 0.5);
  assert.equal(snapCutFraction(0.02, 6), 1 / 6);
  assert.equal(snapCutFraction(0.99, 6), 5 / 6);
  assert.deepEqual(cutFractions(6), [1, 2, 3, 4, 5].map((i) => i / 6));
  assert.equal(pieceLeftOfCut(0.5, 6), 3);
  assert.equal(+pieceLengthMm(hoso).toFixed(2), 31.67);
  assert.equal(pieceLengthMm(futo), 190 / 8);
});

