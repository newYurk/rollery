import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  runF01, runF02, runF03, runF04a, runF04b, runF05, runF06, runF07,
  acceptF01, acceptF02, allPassed,
  makeF01Recipe, makeCucumberRecipe, cucumberCatalogAreaMm2,
} from './fixtures.js';
import { validateRecipe, assessWinding } from './validate.js';
import { buildWinding, independentLayerArcs } from './winding.js';
import { CUCUMBER, CORE_PACK_GAP_MM, EPS_AREA_RATIO, EPS_CORE_ASYMMETRY_MM, HOSOMAKI_DIAMETER_MM, NB, WINDING, clampPatchU, hosogiriBox, packRowGapMm, patchCorePos, placementWindowMm } from './units.js';
import {
  cutFractions, firstCutFraction, pieceCountOf, pieceLeftOfCut,
  pieceLengthMm, snapCutFraction,
} from './knife.js';
import { catalogAreaMm2, cutFillSector, makeF02Recipe, makeF05Recipe, makeF07Recipe, makeHosogiriRecipe, makeCrowdedHosoRecipe } from './recipe.js';
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

test('winding mode is a recipe field, not inferred', () => {
  assert.equal(makeF01Recipe().winding, WINDING.ring);
  const spiral = clone(makeF01Recipe());
  spiral.winding = WINDING.spiral;
  const v = validateRecipe(spiral);
  assert.equal(v.status, 'unsupported');
  assert.equal(v.diagnostics[0].context.requestedFeature, 'spiral');
  const inverted = clone(makeF01Recipe());
  inverted.winding = WINDING.inverted;
  assert.equal(validateRecipe(inverted).status, 'unsupported');
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

test('rice spiral meets nori and stays in the chef corridor', () => {
  const w = buildWinding(makeF01Recipe());
  assert.ok(w.riceTurns > 1.2 && w.riceTurns < 2, w.riceTurns);
  const last = w.riceSteps - 1;
  assert.ok(Math.abs(w.riceRout[last] - w.rp[0]) < 1.5, `${w.riceRout[last]} vs ${w.rp[0]}`);
  assert.ok(Math.abs(w.ricePitchMm - w.T) < 0.5, w.ricePitchMm);
  assert.ok(Math.abs(w.riceArcMm - w.Lrice) < 0.15, `${w.riceArcMm} vs ${w.Lrice}`);
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

test('rice annulus grid area matches T·Lrice, not the path identity', () => {
  const r = runF01();
  assert.ok(r.checks.every((c) => c.ok || c.name !== 'rice-area'));
  const w = { ...r.winding, rp: r.winding.rp.map(() => 9) };
  const checks = acceptF01(r.report, w);
  assert.ok(checks.some((c) => !c.ok && c.name === 'rice-area'));
});

test('F05 fillings stay a bundle on x, not a winding orbit', () => {
  const recipe = makeF05Recipe();
  const pos = recipe.patches.map((p) => ({ id: p.materialId, u: p.uMm, w: p.widthMm, h: p.heightMm, ...patchCorePos(recipe, p) }));
  for (let i = 0; i < pos.length; i++) {
    for (let j = i + 1; j < pos.length; j++) {
      const a = pos[i];
      const b = pos[j];
      const ox = Math.abs(a.x - b.x) + 0.05 < (a.w + b.w) / 2;
      const oy = Math.abs(a.y - b.y) + 0.05 < (a.h + b.h) / 2;
      assert.ok(!(ox && oy), `overlap ${a.id}/${b.id}`);
    }
  }
  const w = buildWinding(recipe);
  const rRice = w.rp[0];
  let maxR = 0;
  for (const p of pos) {
    const ext = Math.hypot(Math.abs(p.x) + p.w / 2, Math.abs(p.y) + p.h / 2);
    assert.ok(ext < rRice - 0.2, JSON.stringify({ p, rRice, ext }));
    maxR = Math.max(maxR, Math.hypot(p.x, p.y));
  }
  assert.ok(maxR < 16, maxR);
});

test('F05 row gap is CORE_PACK_GAP_MM, not inflated rowH', () => {
  const gaps = packRowGapMm(makeF05Recipe());
  assert.ok(gaps.length >= 1, gaps);
  for (const g of gaps) assert.ok(Math.abs(g - CORE_PACK_GAP_MM) < 0.15, g);
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

test('F07 probe sits beside cucumber, swaps side at u=60, never overlaps', () => {
  const left = makeF07Recipe(56);
  const right = makeF07Recipe(64);
  const box = (r, id) => {
    const p = r.patches.find((x) => x.materialId === id);
    const c = patchCorePos(r, p);
    return { ...c, w: p.widthMm, h: p.heightMm };
  };
  const overlap = (a, b) => Math.abs(a.x - b.x) + 0.05 < (a.w + b.w) / 2 && Math.abs(a.y - b.y) + 0.05 < (a.h + b.h) / 2;
  const L = { c: box(left, 'cucumber'), t: box(left, 'tamago') };
  const R = { c: box(right, 'cucumber'), t: box(right, 'tamago') };
  assert.ok(!overlap(L.c, L.t));
  assert.ok(!overlap(R.c, R.t));
  assert.ok(L.t.x < L.c.x);
  assert.ok(R.t.x > R.c.x);
  assert.ok(Math.abs(patchCorePos(left, left.patches[0]).x - patchCorePos(makeF07Recipe(59), makeF07Recipe(59).patches.find((p) => p.materialId === 'cucumber')).x) < 1e-9);
});

test('clampPatchU keeps footprint inside the window', () => {
  const sheet = { lengthMm: 105, widthMm: 185 };
  const p = { widthMm: 14 };
  const win = placementWindowMm(sheet);
  assert.equal(clampPatchU(sheet, p, 0), win.nearEdgeMm + 7);
  assert.equal(clampPatchU(sheet, p, 80), win.farEdgeMm - 7);
  assert.equal(clampPatchU(sheet, p, 36), 36);
});

test('play chips open valid recipes', () => {
  for (const make of [
    makeF01Recipe,
    makeF02Recipe,
    makeHosogiriRecipe,
    () => makeCucumberRecipe(36.25),
    makeF05Recipe,
  ]) {
    assert.equal(validateRecipe(make()).status, 'valid', make.name);
  }
  assert.equal(validateRecipe(makeCucumberRecipe(0)).status, 'invalid');
});

test('three fillings on hosomaki: sheet too short or corridor, not silent', () => {
  const recipe = makeCrowdedHosoRecipe();
  assert.equal(validateRecipe(recipe).status, 'valid');
  const winding = buildWinding(recipe);
  const phys = assessWinding(recipe, winding);
  assert.notEqual(phys.status, 'valid');
  assert.ok(['sheet_too_short', 'chef_corridor'].includes(phys.diagnostics[0].code), phys.diagnostics[0].code);
});

test('validateRecipe refuses NaN, missing sheet, null patch, negative width', () => {
  const nan = { ...makeF01Recipe(), patches: makeF02Recipe().patches.map((p) => ({ ...p, uMm: NaN })) };
  assert.equal(validateRecipe(nan).status, 'invalid');
  const noSheet = { ...makeF01Recipe(), sheet: undefined };
  assert.equal(validateRecipe(noSheet).status, 'invalid');
  const nullPatch = { ...makeF01Recipe(), patches: [null] };
  assert.equal(validateRecipe(nullPatch).status, 'invalid');
  const neg = { ...makeF02Recipe(), patches: makeF02Recipe().patches.map((p) => ({ ...p, widthMm: -8 })) };
  assert.equal(validateRecipe(neg).status, 'invalid');
});

test('F05 bundle AABB is centred on the origin', () => {
  const recipe = makeF05Recipe();
  const pos = recipe.patches.map((p) => ({ ...patchCorePos(recipe, p), w: p.widthMm, h: p.heightMm }));
  const x0 = Math.min(...pos.map((p) => p.x - p.w / 2));
  const x1 = Math.max(...pos.map((p) => p.x + p.w / 2));
  const y0 = Math.min(...pos.map((p) => p.y - p.h / 2));
  const y1 = Math.max(...pos.map((p) => p.y + p.h / 2));
  assert.ok(Math.abs((x0 + x1) / 2) < 1e-9);
  assert.ok(Math.abs((y0 + y1) / 2) < 1e-9);
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


// ── раскладка игрока → RecipeV2 ────────────────────────────────────────────
// Каталог берём ЖИВОЙ, а не пересказанный: переводчик обязан ломаться, когда
// catalog.js уедет, иначе он бесполезен именно тогда, когда нужен.
import { createRequire } from 'node:module';
import { recipeFromLayout, SUPPORTED_CUTS } from './from-layout.js';

const { ING, BASES, U_MM: CATALOG_U_MM } = createRequire(import.meta.url)('./load-catalog.cjs').load();
const lay = (baseKey, patches, over = {}) => recipeFromLayout({
  baseKey, base: BASES[baseKey], patches, ing: ING,
  wrap: null, hand: null, shape: 'round', turns: null, ...over,
});

test('переводчик: единица каталога в ядре и в игре — одна и та же', () => {
  assert.equal(CATALOG_U_MM, 5);
  assert.equal(BASES.hoso.sheetCm * 10, 105);
  assert.equal(BASES.hoso.Wv * CATALOG_U_MM, 190);
  assert.equal(BASES.futo.sheetCm * 10, 210);
});

test('переводчик: пустой лист даёт валидный рецепт', () => {
  const r = lay('hoso', []);
  assert.equal(r.status, 'valid');
  assert.deepEqual(r.recipe.sheet, { lengthMm: 105, widthMm: 190 });
  assert.equal(r.recipe.baseId, 'hosomaki');
  assert.equal(r.recipe.patches.length, 0);
  assert.equal(validateRecipe(r.recipe).status, 'valid');
});

test('переводчик: размеры берутся из каталога, а не из снимка units.js', () => {
  const r = lay('hoso', [{ kind: 'cucumber', u: 0.35, v: 0.5 }]);
  assert.equal(r.status, 'valid');
  const p = r.recipe.patches[0];
  // Живой огурец — сектор 2,8 × 1,98 ед = 14 × 9,9 мм. Снимок V2 (8 × 8 брусок)
  // описывает фикстуру F02 и на раскладку игрока не распространяется.
  assert.equal(p.cut, 'сектор');
  assert.equal(p.widthMm, 14);
  assert.equal(p.heightMm, 9.9);
  assert.notEqual(p.widthMm, CUCUMBER.widthMm);
  assert.equal(p.uMm, 0.35 * 105);
  assert.equal(p.vMm, 0.5 * 190);
  assert.equal(validateRecipe(r.recipe).status, 'valid');
});

test('переводчик: рецепт из раскладки проходит весь конвейер', () => {
  const r = lay('futo', [
    { kind: 'cucumber', u: 0.25, v: 0.5 },
    { kind: 'tamago', u: 0.35, v: 0.5 },
    { kind: 'salmon', u: 0.45, v: 0.5 },
  ]);
  assert.equal(r.status, 'valid');
  const snap = adapt(r.recipe);
  assert.equal(snap.ok, true);
  assert.equal(snap.section.visiblePatches.length, 3);
  assert.ok(snap.winding.diameterMinMm > 0);
});

test('сектор в многорядном пучке: отчёт совпадает с положением в ядре', () => {
  // Регрессия: sampleSector терял origin.y и всегда рапортовал centerYmm = 0,
  // поэтому отчёт расходился с картинкой (render.js рисует по patchCorePos).
  // Фикстуры не ловили — сектор в них один и ровно в начале координат.
  const r = lay('futo', [
    { kind: 'cucumber', u: 0.25, v: 0.5 },
    { kind: 'tamago', u: 0.35, v: 0.5 },
    { kind: 'salmon', u: 0.45, v: 0.5 },
  ]);
  const snap = adapt(r.recipe);
  const cuc = snap.section.visiblePatches.find((p) => p.id.startsWith('cucumber'));
  const truth = patchCorePos(r.recipe, r.recipe.patches.find((p) => p.id === cuc.id));
  assert.ok(Math.abs(truth.y) > 1, `пучок должен быть многорядным, y=${truth.y}`);
  assert.equal(cuc.centerXmm, truth.x);
  assert.equal(cuc.centerYmm, truth.y);
});

test('переводчик отказывает поимённо, а не приближает молча', () => {
  const cases = [
    ['mayo', 'паста', 'unsupported', 'patch_cut_unsupported'],
    ['nori', 'лист', 'unsupported', 'patch_cut_unsupported'],
    ['ricePink', 'краска', 'unsupported', 'patch_is_paint'],
    ['avocado', 'профиль вдоль оси', 'unsupported', 'patch_axial_profile'],
  ];
  for (const [kind, why, status, code] of cases) {
    const r = lay('hoso', [{ kind, u: 0.3, v: 0.5 }]);
    assert.equal(r.status, status, `${kind} (${why})`);
    assert.equal(r.diagnostics[0].code, code, `${kind} (${why})`);
  }
  assert.equal(lay('ura', []).diagnostics[0].code, 'base_unsupported');
  assert.equal(lay('uzumaki', []).diagnostics[0].code, 'base_unsupported');
  assert.equal(lay('hoso', [], { wrap: 'egg' }).diagnostics[0].code, 'wrap_unsupported');
  assert.equal(lay('hoso', [], { shape: 'square' }).diagnostics[0].code, 'shape_unsupported');
  assert.equal(lay('hoso', [], { turns: 3 }).diagnostics[0].code, 'turns_override');
  assert.equal(lay('hoso', [{ kind: 'salmon', u: 0.3, v: 0.5, rot: 0.7 }]).diagnostics[0].code, 'patch_rotated');
  assert.equal(lay('hoso', [{ kind: 'wasabi', u: 0.3, v: 0.5 }]).diagnostics[0].code, 'patch_unknown_kind');
  assert.equal(lay('hoso', [{ kind: 'salmon', u: NaN, v: 0.5 }]).diagnostics[0].code, 'patch_shape');
});

test('переводчик: нейтральная рука сравнивается с эталоном каталога, а не с {mode,seed}', () => {
  const neutral = { air: 0, wobble: 0, phase: 0, press: 1, v: 1, cv: 0, hold: 0 };
  assert.equal(lay('hoso', [], { hand: { ...neutral }, handNeutral: neutral }).status, 'valid');
  const off = lay('hoso', [], { hand: { ...neutral, press: 1.4 }, handNeutral: neutral });
  assert.equal(off.status, 'invalid');
  assert.equal(off.diagnostics[0].code, 'non_neutral_hand');
  assert.deepEqual(off.diagnostics[0].context.deviatingFields, [{ field: 'press', observed: 1.4, neutral: 1 }]);
});

test('переводчик: класс нарезки поддержан ровно тот, что моделирует срез', () => {
  assert.deepEqual([...SUPPORTED_CUTS].sort(), ['брусок', 'сектор']);
  const cuts = new Set(Object.values(ING).map((d) => d.cut));
  for (const c of SUPPORTED_CUTS) assert.ok(cuts.has(c), `каталог потерял класс ${c}`);
});

// ── переносимость хешей (#175) ─────────────────────────────────────────────
import { hashValue, quantize, HASH_QUANTUM_MM } from './hash.js';
import { windingForHash } from './winding.js';
import { coreGapAreaMm2 } from './section.js';
import { sectionForHash } from './section.js';

/** Следующее представимое double вверх. Ровно один ULP, без приближений. */
function nextUp(x) {
  const b = new DataView(new ArrayBuffer(8));
  b.setFloat64(0, x);
  const hi = b.getUint32(0);
  const lo = b.getUint32(4);
  if (lo === 0xffffffff) { b.setUint32(0, hi + 1); b.setUint32(4, 0); } else { b.setUint32(4, lo + 1); }
  return b.getFloat64(0);
}

test('хеш переживает сдвиг на один ULP — это шум платформы, а не изменение', () => {
  // Math.cos/Math.sin не бит-в-бит одинаковы у разных сборок V8, и раньше один
  // такой бит менял SHA-256 целиком: reports/*.json становились машинно-зависимыми.
  const w = buildWinding(makeF02Recipe());
  const before = hashValue(windingForHash(w));

  const nudged = { ...w, r0b: Float64Array.from(w.r0b, nextUp), rp: Float64Array.from(w.rp, nextUp) };
  assert.notEqual(nudged.r0b[7], w.r0b[7], 'сдвиг обязан быть настоящим');
  assert.ok(Math.abs(nudged.r0b[7] - w.r0b[7]) < 1e-14, 'и при этом ровно ULP');

  assert.equal(hashValue(windingForHash(nudged)), before, 'ULP не должен менять хеш');
});

test('хеш ловит настоящее изменение, много мельче допуска', () => {
  const w = buildWinding(makeF02Recipe());
  const before = hashValue(windingForHash(w));
  // 1e-3 мм — в 150 раз меньше EPS_LENGTH_MM и в тысячу раз крупнее сетки хеша.
  const real = { ...w, r0b: Float64Array.from(w.r0b, (v) => v + 1e-3) };
  assert.notEqual(hashValue(windingForHash(real)), before);
});

test('quantize: −0 и 0 неразличимы, типизированные массивы переживают', () => {
  assert.equal(Object.is(quantize(-0), 0), true);
  assert.equal(quantize(1 / 3), 0.333333);
  assert.deepEqual(quantize(Float64Array.from([1.0000004, -0])), [1, 0]);
  assert.equal(HASH_QUANTUM_MM, 1e-6);
  // Сетка обязана лежать глубоко под допуском длины (иначе хеш начнёт врать)
  // и глубоко над ULP миллиметровых величин (иначе вернётся шум платформы).
  assert.ok(0.15 / HASH_QUANTUM_MM > 1e4, "квант слишком крупный: ближе четырёх порядков к допуску");
  assert.ok(HASH_QUANTUM_MM / (2 ** -52 * 4.15) > 1e6, "квант слишком мелкий: ближе шести порядков к ULP");
});

test('срез хешируется так же устойчиво, как намотка', () => {
  const r = makeF02Recipe();
  const w = buildWinding(r);
  const sec = sampleSection(r, w, r.sheet.widthMm / 2);
  const before = hashValue(sectionForHash(sec));
  const nudged = { ...sec, layers: { rice: { innerMm: Float64Array.from(w.r0b, nextUp), outerMm: Float64Array.from(w.rp, nextUp) }, nori: { innerMm: Float64Array.from(w.rp, nextUp), outerMm: Float64Array.from(w.rn, nextUp) } } };
  assert.equal(hashValue(sectionForHash(nudged)), before);
});

// ── снимок каталога обязан сверяться с каталогом (#174) ────────────────────
// units.js называет себя «снимком каталога в мм». Снимок, который не с чем
// сверить, — просто число: шесть мутаций входных констант проходили шлюз
// насквозь, потому что приёмка проверяет соотношения ВЫЧИСЛЕННЫХ величин,
// а скопированные руками не проверяет никто.
import { readFileSync } from 'node:fs';
import { FUTOMAKI, SPREAD_START, TAMAGO, SALMON, U_MM as UNITS_U_MM, CORE_PACK_ROW_MM, HOSOMAKI as HOSO } from './units.js';

const HERE = new URL('.', import.meta.url).pathname;
const src = (rel) => readFileSync(HERE + rel, 'utf8');

test('снимок базы сходится с ЖИВЫМ каталогом, поле за полем', () => {
  for (const [key, snap] of [['hoso', HOSO], ['futo', FUTOMAKI]]) {
    const b = BASES[key];
    assert.equal(snap.catalogKey, key);
    assert.equal(snap.lengthMm, b.sheetCm * 10, `${key}.lengthMm`);
    assert.equal(snap.widthMm, b.Wv * CATALOG_U_MM, `${key}.widthMm`);
    // 1.57 × 5 в double даёт 7.8500000000000005 — снимок хранит корректно
    // округлённое число, поэтому сравниваем по сетке, а не побитово.
    const q9 = (x) => +x.toFixed(9);
    assert.equal(snap.riceThicknessMm, q9(b.T * CATALOG_U_MM), `${key}.riceThicknessMm`);
    assert.equal(snap.noriThicknessMm, q9(b.w * CATALOG_U_MM), `${key}.noriThicknessMm`);
    assert.equal(snap.spreadEnd, b.spreadEnd, `${key}.spreadEnd`);
    assert.equal(snap.pieces, b.pieces, `${key}.pieces`);
    // Тождество, которое комментарий units.js утверждает словами: Hc = T + 2w.
    assert.equal(snap.emptyCoreHeightMm, q9((b.T + 2 * b.w) * CATALOG_U_MM), `${key}.emptyCoreHeightMm`);
  }
  assert.equal(UNITS_U_MM, CATALOG_U_MM, 'единица каталога у ядра и у игры одна');
});

test('SPREAD_START взят из geometry.js, а не выдуман', () => {
  // Снимок ссылается на geometry.js:774. Проверяем саму ссылку: уедет число
  // в модели — тест назовёт расхождение, а не промолчит.
  const m = src('../model/geometry.js').match(/^const SPREAD_START = ([\d.]+);/m);
  assert.ok(m, 'в geometry.js больше нет const SPREAD_START — ссылка снимка протухла');
  assert.equal(SPREAD_START, Number(m[1]));
  assert.equal(HOSO.spreadStart, SPREAD_START);
  assert.equal(FUTOMAKI.spreadStart, SPREAD_START);
});

test('снимок начинок сходится с каталогом — кроме огурца, и это НАМЕРЕННО', () => {
  for (const [kind, snap] of [['tamago', TAMAGO], ['salmon', SALMON]]) {
    const d = ING[kind];
    assert.equal(snap.widthMm, d.wU * CATALOG_U_MM, `${kind}.widthMm`);
    assert.equal(snap.heightMm, d.hU * CATALOG_U_MM, `${kind}.heightMm`);
    assert.equal(snap.cut, d.cut, `${kind}.cut`);
  }
  // Огурец расходится СОЗНАТЕЛЬНО: после 板ずり и 種取り это палка, не сектор
  // плода. Прибиваем и расхождение тоже — чтобы «починка» вслепую покраснела
  // и заставила сначала переписать обоснование в units.js.
  assert.notEqual(CUCUMBER.widthMm, ING.cucumber.wU * CATALOG_U_MM);
  assert.equal(CUCUMBER.cut, 'брусок');
  assert.equal(ING.cucumber.cut, 'сектор');
  assert.match(src('units.js'), /Live catalog\.js \(14 × 9,9, сектор\) не трогаем/,
    'расхождение по огурцу обязано оставаться объяснённым в units.js');
});

test('снимок производных: числа фикстур прибиты и выводятся из каталога', () => {
  // Отчёт квантуется на 1e-6 мм (#175), поэтому сравниваем точно, а не «примерно».
  // Числа СНЯТЫ, а не придуманы; чтобы снимок не оказался тавтологией, каждое
  // рядом выводится из каталога независимой формулой.
  const want = {
    F01: { Wc: 5, Hc: 7.2, Lrice: 87.36, rp: 14.356603, dMin: 28.913206, dMax: 29.113206, core: 36 },
    F02: { Wc: 8, Hc: 8.2, Lrice: 87.36, rp: 14.681077, dMin: 29.562153, dMax: 29.762153, core: 65.6 },
  };
  const q = (x) => Math.round(x * 1e6) / 1e6;
  for (const [id, w] of [['F01', buildWinding(makeF01Recipe())], ['F02', buildWinding(makeF02Recipe())]]) {
    const e = want[id];
    assert.equal(w.Wc, e.Wc, `${id}.Wc`);
    assert.equal(q(w.Hc), e.Hc, `${id}.Hc`);
    assert.equal(q(w.Lrice), e.Lrice, `${id}.Lrice`);
    assert.equal(q(w.rp[0]), e.rp, `${id}.rp`);
    assert.equal(q(w.diameterMinMm), e.dMin, `${id}.diameterMin`);
    assert.equal(q(w.diameterMaxMm), e.dMax, `${id}.diameterMax`);

    // Вывод из каталога, мимо ядра: длина намазки — доля листа.
    const b = BASES.hoso;
    assert.equal(q((b.spreadEnd - SPREAD_START) * b.sheetCm * 10), e.Lrice, `${id}: Lrice из каталога`);
    // Внешний радиус риса — из сохранения площади: π·rp² = ядро + T·Lrice.
    // Площадь ядра берётся по ГРАНИЦЕ r0(φ), а не как Wc·Hc: у прямоугольника
    // пустые углы, и они раздували ролл (#186). У этих двух фикстур ядро —
    // один прямоугольник, поэтому величины совпадают, и это стоит проверить.
    assert.ok(Math.abs(w.coreAreaMm2 - e.core) < 0.05, `${id}: площадь ядра ${w.coreAreaMm2}`);
    const rp = Math.sqrt((e.core + b.T * CATALOG_U_MM * e.Lrice) / Math.PI);
    // Допуск 1e-4 мм, а не 1e-6: ядро берёт площадь дискретным интегралом
    // Σ r0²·dφ по 1440 лучам, вывод — точным прямоугольником. Разница сеток
    // честная и лежит на четыре порядка ниже EPS_LENGTH_MM.
    assert.ok(Math.abs(rp - e.rp) < 1e-4, `${id}: rp из площади ${rp} vs ${e.rp}`);
    // И диаметр обязан лежать в коридоре повара, иначе снимок прибил бы неедобное.
    assert.ok(e.dMin >= HOSOMAKI_DIAMETER_MM.min && e.dMax <= HOSOMAKI_DIAMETER_MM.max, `${id}: ⌀ вне коридора`);
  }
});

test('F05: ядро в ДВА ряда, и это часть картинки', () => {
  // CORE_PACK_ROW_MM перекладывает весь срез, а приёмка этого не видит:
  // она проверяет неперекрытие и порядок, но не число рядов.
  const r = makeF05Recipe();
  const pos = r.patches.map((p) => ({ id: p.id, ...patchCorePos(r, p) }));
  const rows = new Set(pos.map((p) => p.y.toFixed(6)));
  assert.equal(rows.size, 2, `рядов должно быть 2, стало ${rows.size} — проверь CORE_PACK_ROW_MM`);
  assert.equal(CORE_PACK_ROW_MM, 24);
  const by = Object.fromEntries(pos.map((p) => [p.id, p]));
  assert.deepEqual(by['cucumber-0'], { id: 'cucumber-0', x: -6.5, y: -5.5 });
  assert.deepEqual(by['tamago-0'], { id: 'tamago-0', x: 4.5, y: -5.5 });
  assert.deepEqual(by['salmon-0'], { id: 'salmon-0', x: 0, y: 5.5 });
  // Пучок обязан быть центрирован: это чинилось в #176 и молча уехало бы обратно.
  const yTop = Math.max(...r.patches.map((p) => patchCorePos(r, p).y + p.heightMm / 2));
  const yBot = Math.min(...r.patches.map((p) => patchCorePos(r, p).y - p.heightMm / 2));
  assert.ok(Math.abs(yTop + yBot) < 1e-9, `пучок смещён на ${(yTop + yBot) / 2} мм`);
});

test('turnIndexAtRay несёт информацию, а не константу (#173)', () => {
  // Раньше min(1, floor(turns)) — одинаково по всем 1440 лучам: поле в отчёте
  // было, информации в нём не было. Лента риса делает turns оборотов, значит
  // на части лучей она лежит вторым слоем, а на остальных — одним.
  const w = buildWinding(makeF01Recipe());
  const idx = [...w.turnIndexAtRay];
  const uniq = new Set(idx);
  assert.ok(uniq.size > 1, `индекс витка одинаков по всем лучам: ${[...uniq]}`);
  assert.deepEqual([...uniq].sort(), [0, 1]);
  // Граница обязана стоять там, где лента уходит на второй виток.
  const second = idx.filter((v) => v >= 1).length;
  assert.equal(second, Math.max(0, w.riceSteps - NB));
  assert.ok(w.riceTurns > 1 && second > 0, 'при turns > 1 второй виток обязан быть');
});

test('ядро обтягивает пучок, а не описанный прямоугольник (#186)', () => {
  // У прямоугольника, описанного вокруг трёх начинок, пустые углы: они входили
  // в бюджет площади и раздували ролл. Граница теперь идёт по объединению.
  const r = makeF05Recipe();
  const w = buildWinding(r);
  const fill = r.patches.reduce((s, p) => s + catalogAreaMm2(p), 0);
  const frame = w.Wc * w.Hc;
  assert.ok(w.coreAreaMm2 < frame * 0.75, `ядро ${w.coreAreaMm2} против рамки ${frame}`);
  // Пустоты внутри границы должно остаться немного — только зазоры упаковки.
  const voidFrac = (w.coreAreaMm2 - fill) / w.coreAreaMm2;
  assert.ok(voidFrac < 0.10, `пустота ${(voidFrac * 100).toFixed(1)} % ядра`);
  // Диаметр обязан УПАСТЬ: пустота больше не платит за себя площадью.
  assert.ok(w.diameterMinMm < 47, `⌀ ${w.diameterMinMm}`);
});

test('зазор кольцевой модели измеряется, а не прячется (#186)', () => {
  // Луч между двумя кусками выходит из дальнего, поэтому промежуток попадает
  // внутрь r0(φ). У повара там рис. Это предел «одной границы на луч».
  const one = buildWinding(makeF02Recipe());
  assert.equal(coreGapAreaMm2(one), 0, 'у одного куска зазоров нет');
  const many = buildWinding(makeF05Recipe());
  assert.ok(coreGapAreaMm2(many) > 5, 'у пучка зазор обязан быть назван числом');
  assert.ok(coreGapAreaMm2(many) < many.coreAreaMm2 * 0.1, 'и оставаться малым');
});
