#!/usr/bin/env node
// Все числа из ревью PR core-v2/f01-f02, одним прогоном.
//   node tools/core-v2-review-probes.mjs
// Ничего не мутирует и не пишет — только читает ядро как есть.
// Мутационная таблица — отдельно: bash tools/core-v2-mutation-gate.sh

import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const K = join(dirname(fileURLToPath(import.meta.url)), '..', 'play', 'core-v2');
const { makeF01Recipe, makeF02Recipe, makeF05Recipe, makeCucumberRecipe, deepFreeze } = await import(join(K, 'recipe.js'));
const { buildWinding, independentLayerArcs } = await import(join(K, 'winding.js'));
const { validateRecipe } = await import(join(K, 'validate.js'));
const { sampleSection } = await import(join(K, 'section.js'));
const { measure } = await import(join(K, 'measure.js'));
const { runFixture, acceptF01 } = await import(join(K, 'fixtures.js'));
const { HOSOMAKI, CUCUMBER, TAMAGO, SALMON, patchCorePos } = await import(join(K, 'units.js'));

const h = (t) => console.log('\n' + t + '\n' + '-'.repeat(t.length));
const f = (n, d = 3) => Number(n).toFixed(d);

h('M1 — оракул дуги это и есть ядро (fixtures.js:100)');
const w01 = buildWinding(makeF01Recipe());
const oracle = independentLayerArcs({ Wc: w01.Wc, Hc: w01.Hc, T: w01.T, W: w01.W, Lrice: w01.Lrice });
console.log('rice: kernel', w01.riceArcMm, '| oracle', oracle.riceArcMm, '| diff', w01.riceArcMm - oracle.riceArcMm);
console.log('nori: kernel', w01.noriArcMm, '| oracle', oracle.noriArcMm, '| diff', w01.noriArcMm - oracle.noriArcMm);
console.log('порог EPS_LENGTH_MM = 0,15 мм; разница ровно 0, а не «в пределах допуска»');

h('M4 — длина листа не сохраняется (winding.js:139-143), issue #165');
const spent = w01.noriPerimeter + w01.phiOverlap * w01.Ravg;
console.log('L =', w01.sheetLengthMm, '| noriPerimeter =', f(w01.noriPerimeter, 4), '| Ravg =', f(w01.Ravg, 4));
console.log('Lbare (голые кромки) =', f(w01.Lbare, 4), '-> phiOverlap =', f(w01.phiOverlap, 5), 'рад,', w01.overlapBins, 'бинов');
const cons = (w01.sheetLengthMm - w01.noriPerimeter) / w01.Ravg;
console.log('L - perimeter        =', f(w01.sheetLengthMm - w01.noriPerimeter, 4), '-> phi        =', f(cons, 5), 'рад,', Math.round(cons / (2 * Math.PI / 1440)), 'бинов');
console.log('израсходовано листа =', f(spent), 'из', w01.sheetLengthMm, '-> лишних', f(spent - w01.sheetLengthMm), 'мм;', w01.overlapBins - Math.round(cons / (2 * Math.PI / 1440)), 'лучей из 1440 врут о двух слоях');
const rep01 = measure(makeF01Recipe(), w01, sampleSection(makeF01Recipe(), w01, 95), 'F01', 'valid', []);
console.log('arcByLayerMm =', JSON.stringify(rep01.sheet.arcByLayerMm.map((r) => ({ ...r, arcMm: +f(r.arcMm) }))));
console.log('  ^ строка nori несёт u-диапазон РИСА; нори занимает весь лист [0; 105]');

h('M2 — валидный рецепт даёт невозможный ролл (winding.js:142-143)');
const sheet = { lengthMm: HOSOMAKI.lengthMm, widthMm: HOSOMAKI.widthMm };
const P = (id, spec, u) => ({
  id, materialId: spec.materialId, cut: spec.cut, uMm: u, vMm: sheet.widthMm / 2,
  widthMm: spec.widthMm, lengthMm: sheet.widthMm, heightMm: spec.heightMm, placement: 'embedded',
});
const crowd = deepFreeze({
  version: 2, baseId: HOSOMAKI.baseId, sheet, wrap: { materialId: 'nori' }, rice: { profileId: 'standard' },
  windDirection: 'fromUZero', winding: 'ring', hand: { mode: 'neutral', seed: 0 },
  patches: [P('cucumber-0', CUCUMBER, 25), P('tamago-0', TAMAGO, 35), P('salmon-0', SALMON, 46)],
});
const vc = validateRecipe(crowd);
console.log('три начинки в окне [20; 52,5] хосомаки ->', vc.status + ',', vc.diagnostics.length, 'диагностик');
const wc = buildWinding(crowd);
console.log('Wc x Hc =', wc.Wc, 'x', wc.Hc, '| rp =', f(wc.rp[0]), '| noriPerimeter =', f(wc.noriPerimeter), 'при листе', wc.sheetLengthMm, '-> не хватает', f(wc.noriPerimeter - wc.sheetLengthMm), 'мм');
console.log('enough = false -> phiOverlap =', wc.phiOverlap, ', но seam.overlapMm =', f(wc.seam.overlapMm), '(отчёт противоречит сам себе)');
console.log('диаметр =', f(wc.diameterMinMm, 2), 'мм при коридоре повара 28-32');
const rc = measure(crowd, wc, sampleSection(crowd, wc, 95), 'crowd', 'valid', []);
console.log('acceptF01 упал бы на:', acceptF01(rc, wc).filter((c) => !c.ok).map((c) => c.name).join(', ') || 'НИ НА ЧЁМ');
console.log('но фикстуры такой нет, а app.js гейтит только validateRecipe -> страница это нарисует');

h('M3 — начинка помещается в ядро? проверки нет (winding.js:30-34)');
const one = deepFreeze({ ...crowd, patches: [P('cucumber-0', CUCUMBER, 36)] });
const w1 = buildWinding(one);
console.log('огурец 8x8 -> Wc x Hc =', w1.Wc, 'x', f(w1.Hc, 2), '| габарит патча 8,0 x 8,0');
console.log('инварианта «патч не пересекает r0b» нет; тест core-v2.test.mjs:270 сравнивает с ВНЕШНИМ радиусом риса');

h('m6 — пучок начинок смещён вниз на gap/2 (units.js:275)');
const r05 = makeF05Recipe();
const pos = r05.patches.map((p) => ({ id: p.id, w: p.widthMm, h: p.heightMm, ...patchCorePos(r05, p) }));
for (const p of pos) console.log(' ', p.id.padEnd(12), 'x =', String(p.x).padStart(5), ' y =', String(p.y).padStart(5));
const yT = Math.max(...pos.map((p) => p.y + p.h / 2));
const yB = Math.min(...pos.map((p) => p.y - p.h / 2));
const xR = Math.max(...pos.map((p) => p.x + p.w / 2));
const xL = Math.min(...pos.map((p) => p.x - p.w / 2));
console.log('габарит по y:', yB, '..', yT, '-> центр смещён на', (yT + yB) / 2, 'мм (= CORE_PACK_GAP_MM/2)');
console.log('габарит по x:', xL, '..', xR, '-> центр', (xR + xL) / 2, 'мм (по x верно)');
const w05 = buildWinding(r05);
console.log('из-за этого Hc =', w05.Hc, 'вместо 21,2 -> диаметр', f(w05.diameterMinMm, 2), 'вместо ~48,51');

h('m9 — парадная дверь: падает вместо честного отказа (validate.js)');
const t = (name, fn) => {
  let r;
  try { r = fn(); } catch (e) { r = 'THROWS ' + e.constructor.name + ': ' + e.message.slice(0, 58); }
  console.log(' ', name.padEnd(22), '->', r);
};
t('uMm = NaN', () => validateRecipe(makeCucumberRecipe(NaN)).status);
t('  ... затем runFixture', () => runFixture('x', makeCucumberRecipe(NaN)).status);
t('нет sheet', () => { const r = { ...makeF01Recipe() }; delete r.sheet; return validateRecipe(r).status; });
t('patches: [null]', () => validateRecipe({ ...makeF01Recipe(), patches: [null] }).status);
t('widthMm = -8', () => { const r = structuredClone(makeCucumberRecipe(36)); r.patches[0].widthMm = -8; return validateRecipe(r).status; });
t('uMm = Infinity', () => validateRecipe(makeCucumberRecipe(Infinity)).status);
t("version = '2'", () => validateRecipe({ ...makeF01Recipe(), version: '2' }).status);

h('M5 — чип F03 на странице всегда отказ (app.js:21 и app.js:46)');
console.log('ни один элемент FIXTURES не имеет поля .slider -> sliderVal навсегда 0');
const v03 = validateRecipe(makeCucumberRecipe(0));
console.log('makeCucumberRecipe(0) ->', v03.status, '/', v03.diagnostics[0]?.code, 'след', JSON.stringify(v03.diagnostics[0]?.context?.observedFootprintMm));
console.log('ожидалось u = 36,25 и рабочий ползунок; #sliderWrap навсегда hidden');

h('контроль: F01/F02 как есть');
console.log('F01', runFixture('F01', makeF01Recipe()).status, '| F02', runFixture('F02', makeF02Recipe()).status,
  '| ⌀', f(w01.diameterMinMm, 2), '-', f(w01.diameterMaxMm, 2), 'мм');
