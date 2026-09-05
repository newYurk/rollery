// F01/F02 runner and acceptance. Mutations live in core-v2.test.mjs.

import {
  EPS_AREA_RATIO,
  EPS_CORE_ASYMMETRY_MM,
  EPS_INVERT_MM,
  EPS_LENGTH_MM,
  EPS_RAY_FRACTION,
  EPS_RICE_AREA_RATIO,
  F03_U_MM,
  MAX_AREA_RATIO_DELTA,
  MAX_CENTER_DELTA_MM,
  NB,
  TAU,
  CORE_PACK_GAP_MM,
  packRowGapMm,
} from './units.js';
import {
  cucumberCatalogAreaMm2,
  catalogAreaMm2,
  deepClone,
  makeCucumberRecipe,
  makeF01Recipe,
  makeF02Recipe,
  makeF04aRecipe,
  makeF04bRecipe,
  makeF05Recipe,
  makeF07Recipe,
  makeF07SameMaterialOverlap,
} from './recipe.js';
import { validateRecipe, assessWinding } from './validate.js';
import { buildWinding } from './winding.js';
import { riceAnnulusAreaMm2, sampleSection } from './section.js';
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
  const phys = assessWinding(recipe, winding);
  if (phys.status !== 'valid') {
    const report = rejectReport(recipe, fixtureId, phys.status, phys.diagnostics);
    if (canonicalize(recipe) !== before) {
      throw new Error('kernel mutated the input recipe');
    }
    return report;
  }
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

  const L = report.sheet.lengthMm;
  const cov = Math.abs(report.sheet.coveredLengthMm - L);
  push(cov <= EPS_LENGTH_MM ? ok('coverage') : fail('coverage', report.sheet.coveredLengthMm));
  push(report.sheet.phantomLengthMm <= EPS_LENGTH_MM ? ok('phantom') : fail('phantom', report.sheet.phantomLengthMm));
  push(report.sheet.uncoveredLengthMm <= EPS_LENGTH_MM ? ok('uncovered') : fail('uncovered', report.sheet.uncoveredLengthMm));

  const nori = report.sheet.arcByLayerMm.find((r) => r.layerId === 'nori');
  const rice = report.sheet.arcByLayerMm.find((r) => r.layerId === 'rice');
  const rp = winding.rp[0];
  const noriWant = TAU * (rp + winding.W / 2);
  push(nori && Math.abs(nori.arcMm - noriWant) <= EPS_LENGTH_MM
    ? ok('arc:nori')
    : fail('arc:nori', `${nori?.arcMm} vs ${noriWant}`));
  // Oracle is sheet rice length, not a second integral. Do not widen EPS.
  push(rice && Math.abs(rice.arcMm - winding.Lrice) <= EPS_LENGTH_MM
    ? ok('arc:rice')
    : fail('arc:rice', `${rice?.arcMm} vs Lrice ${winding.Lrice}`));
  const riceArea = riceAnnulusAreaMm2(winding);
  const wantArea = winding.T * winding.Lrice;
  const riceRatio = Math.max(riceArea / wantArea, wantArea / riceArea);
  push(riceRatio <= EPS_RICE_AREA_RATIO
    ? ok('rice-area')
    : fail('rice-area', `${riceArea} / ${wantArea} = ${riceRatio}`));

  push(report.sheet.uMinMm >= 0 && report.sheet.uMaxMm <= L ? ok('bounds') : fail('bounds'));

  const seam = report.seam;
  const seamOk = seam
    && seam.uStartMm >= 0 && seam.uStartMm <= L
    && seam.uEndMm >= 0 && seam.uEndMm <= L
    && seam.angleStartRad >= 0 && seam.angleStartRad < TAU
    && seam.angleEndRad >= 0 && seam.angleEndRad < TAU
    && Math.abs(seam.overlapMm - seam.overlapArcRad * winding.Ravg) <= EPS_LENGTH_MM;
  push(seamOk ? ok('seam') : fail('seam', JSON.stringify(seam)));

  // ⚑ ЛИСТ СОХРАНЯЕТСЯ. Инварианта не было вовсе, и потому не было видно, что
  // нахлёст считался от голых полей: хосомаки выдумывал 3,16 мм листа, футомаки
  // терял 24,73 мм (11,8 %). Проверка не тавтология — периметр меряется дугой,
  // нахлёст берётся из остатка, и сойтись они обязаны с длиной листа (#165).
  const spent = winding.noriPerimeter + seam.overlapMm;
  push(Math.abs(spent - L) <= EPS_LENGTH_MM
    ? ok('sheet-conserved')
    : fail('sheet-conserved', `периметр ${winding.noriPerimeter} + нахлёст ${seam.overlapMm} = ${spent} против листа ${L}`));

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
  const wantFar = (report.sheet.lengthMm || recipe.sheet.lengthMm) / 2;
  checks.push(w.nearEdgeMm === 20 && w.farEdgeMm === wantFar
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

function visById(report) {
  const m = new Map();
  for (const p of report.visiblePatches) m.set(p.id, p);
  return m;
}

export function acceptF05(abc, cab) {
  const checks = [];
  for (const [name, run] of [['ABC', abc], ['CAB', cab]]) {
    if (run.report.status !== 'valid') {
      checks.push(fail(`${name}:status`, run.report.status));
      continue;
    }
    checks.push(ok(`${name}:status`));
    checks.push(...acceptF01(run.report, run.winding).map((c) => ({ ...c, name: `${name}:${c.name}` })));
    checks.push(run.report.visiblePatches.length === 3
      ? ok(`${name}:count`)
      : fail(`${name}:count`, run.report.visiblePatches.length));
    for (const p of run.recipe.patches) {
      const vis = run.report.visiblePatches.find((v) => v.id === p.id);
      const catalog = catalogAreaMm2(p);
      const ratio = vis ? Math.max(vis.areaMm2 / catalog, catalog / vis.areaMm2) : Infinity;
      checks.push(vis && ratio <= EPS_AREA_RATIO
        ? ok(`${name}:area:${p.id}`)
        : fail(`${name}:area:${p.id}`, ratio));
    }
    const gaps = packRowGapMm(run.recipe);
    for (const g of gaps) {
      checks.push(Math.abs(g - CORE_PACK_GAP_MM) <= EPS_LENGTH_MM
        ? ok(`${name}:pack-gap`)
        : fail(`${name}:pack-gap`, g));
    }
  }
  checks.push(abc.report.hashes.winding === cab.report.hashes.winding
    ? ok('order:winding')
    : fail('order:winding', `${abc.report.hashes.winding} vs ${cab.report.hashes.winding}`));
  checks.push(abc.report.hashes.section === cab.report.hashes.section
    ? ok('order:section')
    : fail('order:section', `${abc.report.hashes.section.slice(0, 8)} vs ${cab.report.hashes.section.slice(0, 8)}`));
  const a = visById(abc.report);
  const b = visById(cab.report);
  for (const id of a.keys()) {
    const pa = a.get(id);
    const pb = b.get(id);
    if (!pb) {
      checks.push(fail(`order:id:${id}`, 'missing'));
      continue;
    }
    const d = Math.hypot(pa.centerXmm - pb.centerXmm, pa.centerYmm - pb.centerYmm);
    checks.push(d <= EPS_LENGTH_MM ? ok(`order:center:${id}`) : fail(`order:center:${id}`, d));
    const ratio = Math.max(pa.areaMm2 / pb.areaMm2, pb.areaMm2 / pa.areaMm2);
    checks.push(ratio <= EPS_AREA_RATIO ? ok(`order:area:${id}`) : fail(`order:area:${id}`, ratio));
  }
  return checks;
}

export function runF05() {
  const abc = (() => {
    const recipe = makeF05Recipe(['cucumber', 'tamago', 'salmon']);
    const report = runFixture('F05-ABC', recipe);
    const winding = report.status === 'valid' ? buildWinding(recipe) : null;
    return { recipe, report, winding };
  })();
  const cab = (() => {
    const recipe = makeF05Recipe(['salmon', 'cucumber', 'tamago']);
    const report = runFixture('F05-CAB', recipe);
    const winding = report.status === 'valid' ? buildWinding(recipe) : null;
    return { recipe, report, winding };
  })();
  return { abc, cab, report: abc.report, checks: acceptF05(abc, cab) };
}

export function runF06() {
  const checks = [];
  const once = (id, make) => {
    const recipe = make();
    const json = JSON.parse(JSON.stringify(recipe));
    const a = runFixture(id, recipe);
    const b = runFixture(`${id}-b`, json);
    const c = runFixture(`${id}-c`, make());
    checks.push(a.hashes.recipe === b.hashes.recipe ? ok(`${id}:roundtrip-recipe`) : fail(`${id}:roundtrip-recipe`));
    checks.push(a.hashes.winding === b.hashes.winding && a.hashes.winding === c.hashes.winding
      ? ok(`${id}:winding`)
      : fail(`${id}:winding`, `${a.hashes.winding.slice(0, 8)}`));
    checks.push(a.hashes.section === b.hashes.section && a.hashes.section === c.hashes.section
      ? ok(`${id}:section`)
      : fail(`${id}:section`));
    return a;
  };
  once('F01', makeF01Recipe);
  once('F02', makeF02Recipe);
  once('F05', () => makeF05Recipe());
  return { checks, report: runF01().report };
}

function findVis(report, id) {
  return report.visiblePatches.find((p) => p.id === id);
}

export function acceptF07(steps, swapped, overlap) {
  const checks = [];
  for (const step of steps) {
    const { uMm, a, b } = step;
    for (const [tag, run] of [['AB', a], ['BA', b]]) {
      checks.push(run.report.status === 'valid'
        ? ok(`F07-${uMm}-${tag}:status`)
        : fail(`F07-${uMm}-${tag}:status`, run.report.status));
    }
    if (a.report.status !== 'valid' || b.report.status !== 'valid') continue;
    const pa = findVis(a.report, 'tamago-0');
    const pb = findVis(b.report, 'tamago-0');
    const d = Math.hypot(pa.centerXmm - pb.centerXmm, pa.centerYmm - pb.centerYmm);
    checks.push(d <= EPS_LENGTH_MM ? ok(`F07-${uMm}:probe-order`) : fail(`F07-${uMm}:probe-order`, d));
    const ca = findVis(a.report, 'cucumber-0');
    const cb = findVis(b.report, 'cucumber-0');
    const dc = Math.hypot(ca.centerXmm - cb.centerXmm, ca.centerYmm - cb.centerYmm);
    checks.push(dc <= EPS_LENGTH_MM ? ok(`F07-${uMm}:cuc-order`) : fail(`F07-${uMm}:cuc-order`, dc));
    checks.push(pa.areaMm2 > 0 && ca.areaMm2 > 0
      ? ok(`F07-${uMm}:areas`)
      : fail(`F07-${uMm}:areas`));
  }
  const valid = steps.filter((s) => s.a.report.status === 'valid');
  const side = (u) => (u < 60 ? -1 : 1);
  for (let i = 1; i < valid.length; i++) {
    const p0 = findVis(valid[i - 1].a.report, 'tamago-0');
    const p1 = findVis(valid[i].a.report, 'tamago-0');
    const d = Math.hypot(p1.centerXmm - p0.centerXmm, p1.centerYmm - p0.centerYmm);
    const same = side(valid[i].uMm) === side(valid[i - 1].uMm);
    if (same) {
      checks.push(d <= EPS_LENGTH_MM ? ok(`F07-cont-${valid[i].uMm}`) : fail(`F07-cont-${valid[i].uMm}`, d));
    } else {
      checks.push(d > EPS_LENGTH_MM ? ok(`F07-swap-side-${valid[i].uMm}`) : fail(`F07-swap-side-${valid[i].uMm}`, d));
    }
  }
  const bySide = new Map();
  for (const s of valid) {
    const k = side(s.uMm);
    if (!bySide.has(k)) bySide.set(k, s);
    const c0 = findVis(bySide.get(k).a.report, 'cucumber-0');
    const c = findVis(s.a.report, 'cucumber-0');
    const d = Math.hypot(c.centerXmm - c0.centerXmm, c.centerYmm - c0.centerYmm);
    checks.push(d <= EPS_LENGTH_MM ? ok(`F07-neigh-${s.uMm}`) : fail(`F07-neigh-${s.uMm}`, d));
  }
  const step56 = steps.find((s) => s.uMm === 56);
  if (swapped.report.status === 'valid' && step56?.a.report.status === 'valid') {
    const probeS = findVis(swapped.report, 'tamago-0');
    const cucS = findVis(swapped.report, 'cucumber-0');
    const probe56 = findVis(step56.a.report, 'tamago-0');
    const cuc56 = findVis(step56.a.report, 'cucumber-0');
    checks.push(probe56.centerXmm < cuc56.centerXmm ? ok('F07-swap-order-56') : fail('F07-swap-order-56', `${probe56.centerXmm} ${cuc56.centerXmm}`));
    checks.push(cucS.centerXmm < probeS.centerXmm ? ok('F07-swap-order-rev') : fail('F07-swap-order-rev', `${cucS.centerXmm} ${probeS.centerXmm}`));
    const ar1 = Math.max(cucS.areaMm2 / cuc56.areaMm2, cuc56.areaMm2 / cucS.areaMm2);
    const ar2 = Math.max(probeS.areaMm2 / probe56.areaMm2, probe56.areaMm2 / probeS.areaMm2);
    checks.push(ar1 <= EPS_AREA_RATIO && ar2 <= EPS_AREA_RATIO
      ? ok('F07-swap-area')
      : fail('F07-swap-area', `${ar1} ${ar2}`));
  } else {
    checks.push(fail('F07-swap', swapped.report.status));
  }
  const cross = steps.find((s) => s.uMm === 60);
  checks.push(cross?.a.report.status === 'valid' && cross.a.report.visiblePatches.length === 2
    ? ok('F07-cross-valid')
    : fail('F07-cross-valid', cross?.a.report.status));
  checks.push(overlap.report.status === 'invalid' && overlap.report.diagnostics[0]?.code === 'patch_material_overlap'
    ? ok('F07-same-material')
    : fail('F07-same-material', overlap.report.status + ' ' + overlap.report.diagnostics[0]?.code));
  return checks;
}

export function runF07() {
  const steps = [];
  for (let uMm = 56; uMm <= 64; uMm += 1) {
    const ra = makeF07Recipe(uMm, true);
    const rb = makeF07Recipe(uMm, false);
    const a = { recipe: ra, report: runFixture(`F07-${uMm}-AB`, ra), winding: null };
    const b = { recipe: rb, report: runFixture(`F07-${uMm}-BA`, rb), winding: null };
    if (a.report.status === 'valid') a.winding = buildWinding(ra);
    if (b.report.status === 'valid') b.winding = buildWinding(rb);
    steps.push({ uMm, a, b });
  }
  const swapRecipe = makeF07Recipe(60, true, true);
  const swapped = { recipe: swapRecipe, report: runFixture('F07-swap', swapRecipe) };
  const ovRecipe = makeF07SameMaterialOverlap();
  const overlap = { recipe: ovRecipe, report: runFixture('F07-overlap', ovRecipe) };
  return {
    steps, swapped, overlap,
    report: steps[0].a.report,
    checks: acceptF07(steps, swapped, overlap),
  };
}

export function allPassed(checks) {
  return checks.every((c) => c.ok);
}

export {
  makeF01Recipe, makeF02Recipe, makeCucumberRecipe, makeF04aRecipe, makeF04bRecipe,
  makeF05Recipe, makeF07Recipe,
  deepClone, cucumberCatalogAreaMm2,
};
