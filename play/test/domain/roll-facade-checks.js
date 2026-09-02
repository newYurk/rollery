'use strict';
// FACADE ПРОТИВ LEGACY: то же самое, посчитанное двумя путями, обязано совпасть.
//
// Единственный потребитель facade в этом PR — вот этот тестовый адаптер. Ни один
// production-файл на facade ещё не переведён: сперва доказательство эквивалентности,
// потом переезд по одному потребителю (issue #72).
//
// Слева: fixtures → legacy geometry (buildModel напрямую).
// Справа: fixtures → createRecipe → evaluateRoll → sliceAt.
// Инварианты считаются ОДНОЙ меркой (play/test/probe.js), различается только путь.

// Инварианты, собранные ИЗ DTO facade — намеренно не из roll.legacyModel: иначе сравнение
// свелось бы к «один и тот же объект равен сам себе» и ничего бы не проверяло.
function facadeInvariants(fx) {
  const r4 = x => Math.round(x * 1e4) / 1e4;
  const recipe = createRecipe(fx.recipe);
  const roll = evaluateRoll(recipe);
  if (!roll.ok) return { error: roll.errors.map(e => e.field + ': ' + e.message).join('; ') };
  const mt = roll.metrics;
  const inv = {
    turns: r4(mt.turns), outerDiameterMm: r4(mt.outerDiameterMm), closePoint: r4(mt.closePoint),
    sheetEnd: r4(mt.sheetEnd), sheetLength: r4(mt.sheetLength), hasCore: mt.hasCore,
    shape: mt.shape,
    coreRadius: r4(mt.coreRadius), coreFold: r4(mt.coreFold), patchCount: recipe.list.length,
    materialFractions: {}, probes: [],
  };
  const counts = {}; let total = 0;
  for (const v of PROBE_SLICES) {
    const sl = sliceAt(roll, v, { rings: PROBE_RINGS, rays: PROBE_RAYS });
    for (let ri = 0; ri < PROBE_RINGS; ri++) for (let ai = 0; ai < PROBE_RAYS; ai++) {
      const cls = sl.cells[ri * PROBE_RAYS + ai];
      counts[cls] = (counts[cls] || 0) + 1; total++;
      if (ri % 4 === 1 && ai % 6 === 0) inv.probes.push(v + '|' + ri + '|' + ai + '=' + cls);
    }
  }
  for (const k of Object.keys(counts).sort()) inv.materialFractions[k] = r4(counts[k] / total);
  // Карта материалов и самоподобие — через DTO facade, а не через roll.legacyModel.
  inv.map = sliceMaterialMap(roll, 0.5);
  inv.selfSimilarity = r4(compareRolls(roll, roll, [0.5]));
  return inv;
}

function runRollFacadeChecks() {
  const cases = [], failures = [];
  const fail = (id, msg) => failures.push(`${id}: ${msg}`);

  // 0. Межмодельные пары: facade обязан давать те же похожести, что legacy. Пара РАЗНЫХ
  // моделей — единственное, что реально проверяет тело similarityOf (ревью PR #102).
  {
    const wantP = pairSimilarities(r => withLegacyRecipe(r, m => m), similarity);
    const gotP = pairSimilarities(r => evaluateRoll(createRecipe(r)),
                                  (a, b, vs) => compareRolls(a, b, vs));
    for (const k of Object.keys(wantP))
      if (Math.abs((wantP[k] || 0) - (gotP[k] || 0)) > 1e-6)
        fail('пары', `${k}: legacy ${wantP[k]} ≠ facade ${gotP[k]}`);
  }

  // 1. Эквивалентность на всех fixtures.
  for (const fx of ROLL_FIXTURES) {
    const legacy = evaluateLegacyFixture(fx);
    const facade = facadeInvariants(fx);
    if (facade.error) { fail(fx.id, 'facade не принял рецепт — ' + facade.error); continue; }
    const diff = invariantsDiff(legacy, facade);
    cases.push({ id: fx.id, ok: diff.length === 0 });
    for (const d of diff) fail(fx.id, d);
  }

  // 2. Facade не отдаёт геометрии ЧУЖОЙ массив. Проверяется ТОЖДЕСТВОМ ссылки, а не мутацией.
  //
  // ⚠ Первая редакция этой проверки сравнивала рецепт до и после вызова — и не могла упасть
  // никогда, что доказал ревьюер PR #100 экспериментом: снимаешь оба клона в facade — зелено,
  // снимаешь ещё и клон внутри buildModel — всё равно зелено. Причин было
  // четыре сразу, и худшая — КЕШ: проверка брала тот же fixture, что и проверка №1 выше, поэтому
  // buildModel возвращался на кеш-хите, не доходя до restack вовсе. Мутации просто негде было
  // случиться, а проверка выглядела строгой.
  //
  // Тождество ссылки от кеша не зависит и от чужих клонов тоже: если facade передаст массив
  // вызывающего, шпион это увидит независимо от того, склонирует ли его геометрия потом.
  {
    const src = JSON.parse(JSON.stringify(ROLL_FIXTURES[1].recipe));
    const recipe = createRecipe(src);
    if (recipe.list === src.list) fail('клон', 'createRecipe вернул рецепт, делящий массив с вызывающим');
    const orig = buildModel;
    let sameRef = null;
    try {
      buildModel = function (list, only) { sameRef = (list === recipe.list) || (list === src.list); return orig(list, only); };
      evaluateRoll(recipe);
    } finally { buildModel = orig; }
    if (sameRef === null) fail('клон', 'шпион не сработал — evaluateRoll не позвал buildModel');
    else if (sameRef) fail('клон', 'facade отдал геометрии массив вызывающего, а не копию');
  }

  // 3. Глобальное состояние возвращается как было — включая S.wrap, который альбом теряет.
  {
    const keep = JSON.stringify({ b: S.base, w: S.wrap, t: S.turns, s: S.shape, h: S.hand });
    evaluateRoll(createRecipe(ROLL_FIXTURES[2].recipe));
    const now = JSON.stringify({ b: S.base, w: S.wrap, t: S.turns, s: S.shape, h: S.hand });
    if (keep !== now) fail('состояние', 'после evaluateRoll глобальное S не вернулось как было');
  }

  // 4. Обёртка ВХОДИТ в геометрию: блин 2 мм и нори 0,1 мм не могут дать один диаметр.
  // Это тот самый дефект, на котором в августе горел кеш модели (см. §2 в checks.js).
  {
    const withCrepe = evaluateRoll(createRecipe(ROLL_FIXTURES[2].recipe));
    const asNori = evaluateRoll(createRecipe(Object.assign({}, ROLL_FIXTURES[2].recipe, { wrap: null })));
    if (Math.abs(withCrepe.metrics.outerDiameterMm - asNori.metrics.outerDiameterMm) < 0.05)
      fail('обёртка', 'блин и нори дали одинаковый ⌀ — facade потерял wrap по дороге');
  }

  // 5. Рука меняет намотку: F02 и F05 — один рецепт, разный почерк.
  {
    const calm = evaluateRoll(createRecipe(ROLL_FIXTURES[1].recipe));
    const quick = evaluateRoll(createRecipe(ROLL_FIXTURES[4].recipe));
    if (Math.abs(calm.metrics.outerDiameterMm - quick.metrics.outerDiameterMm) < 1e-6)
      fail('рука', 'почерк не изменил намотку — facade потерял hand');
  }

  // 6. Круговая сериализация: рецепт → payload → рецепт даёт ту же геометрию.
  for (const fx of [ROLL_FIXTURES[2], ROLL_FIXTURES[3]]) {
    const a = createRecipe(fx.recipe);
    const b = deserializeRecipe(serializeRecipe(a));
    const ia = evaluateRoll(a).metrics, ib = evaluateRoll(b).metrics;
    if (Math.abs(ia.outerDiameterMm - ib.outerDiameterMm) > 1e-6 || Math.abs(ia.turns - ib.turns) > 1e-6)
      fail(fx.id, 'круговая сериализация изменила геометрию');
  }

  // 7. Валидация ловит битое: неизвестная база и неизвестная начинка.
  {
    if (validateRecipe(createRecipe({ base: 'неттакой', list: [] })).ok)
      fail('валидация', 'неизвестная база прошла проверку');
    if (validateRecipe(createRecipe({ base: 'futo', list: [{ kind: 'неттакой', u: 0.5, v: 0.5 }] })).ok)
      fail('валидация', 'неизвестная начинка прошла проверку');
  }

  // 8. Раскладка листа: сверка с legacy И возврат глобалов.
  //
  // ⚠ Прежняя редакция проверяла только «рамка не пустая» и была слепа к тому, ради чего
  // deriveSheetLayout вообще опасна: ревьюер PR #100 снял в ней восстановление W/H/DPR — и
  // проверки остались зелёными, хотя окно после вызова оставалось чужим. Второе условие про
  // uAxis было и вовсе тавтологией: layout() пишет w и lenU из одной переменной.
  //
  // Теперь: (а) DTO facade сверяется с прямым вызовом layout() на тех же размерах;
  // (б) глобалы снимаются ДО и сверяются ПОСЛЕ — на размерах, ЗАВЕДОМО ОТЛИЧНЫХ от текущих,
  // иначе утечка не видна (совпадение маскирует невозврат).
  for (const [vw, vh] of [[1440, 900], [390, 844]]) {
    const keepG = JSON.stringify({ W, H, DPR, base: S.base, wrap: S.wrap, turns: S.turns,
                                   mode: L.mode, sheet: L.sheet });
    const recipe = createRecipe(ROLL_FIXTURES[1].recipe);
    const lay = deriveSheetLayout(recipe, { width: vw, height: vh, dpr: 2 });
    const tag = `раскладка ${vw}×${vh}`;
    if (!lay.ok || !(lay.sheet.lenU > 0) || !(lay.sheet.lenV > 0)) { fail(tag, 'пустая рамка'); continue; }
    if (JSON.stringify({ W, H, DPR, base: S.base, wrap: S.wrap, turns: S.turns,
                         mode: L.mode, sheet: L.sheet }) !== keepG)
      fail(tag, 'после вызова глобалы (W/H/DPR, S, L) не вернулись как были');
    // Legacy-путь: то же самое руками, как это делает игра.
    const kW = W, kH = H, kD = DPR, kb = S.base, kw = S.wrap, kt = S.turns, kL = JSON.stringify(L);
    let want;
    try {
      W = vw; H = vh; DPR = 2;
      S.base = recipe.base; S.wrap = recipe.wrap || null; S.turns = turnsOf(recipe.turns);
      layout();
      want = { mode: L.mode, x: L.sheet.x, y: L.sheet.y, w: L.sheet.w, h: L.sheet.h,
               uAxis: L.sheet.uAxis, lenU: L.sheet.lenU, lenV: L.sheet.lenV,
               hx: L.handle.x, hy: L.handle.y, hw: L.handle.w, hh: L.handle.h };
    } finally {
      W = kW; H = kH; DPR = kD; S.base = kb; S.wrap = kw; S.turns = kt;
      Object.assign(L, JSON.parse(kL)); layout();
    }
    const got = { mode: lay.mode, x: lay.sheet.x, y: lay.sheet.y, w: lay.sheet.w, h: lay.sheet.h,
                  uAxis: lay.sheet.uAxis, lenU: lay.sheet.lenU, lenV: lay.sheet.lenV,
                  hx: lay.handle.x, hy: lay.handle.y, hw: lay.handle.w, hh: lay.handle.h };
    for (const k of Object.keys(want))
      if (JSON.stringify(want[k]) !== JSON.stringify(got[k]))
        fail(tag, `${k}: legacy ${want[k]} ≠ facade ${got[k]}`);
  }

  // 9. Согласованность DTO: поля, которые ничем не сверялись (найдено ревью PR #100).
  {
    const roll = evaluateRoll(createRecipe(ROLL_FIXTURES[1].recipe));
    const mt = roll.metrics;
    if (Math.abs(mt.outerRadius * U_MM * 2 - mt.outerDiameterMm) > 1e-9)
      fail('DTO', 'outerRadius разошёлся с outerDiameterMm');
    if (mt.closed !== (mt.turns >= 1)) fail('DTO', 'closed не следует из turns');
    const sl = sliceAt(roll, 0.5);
    if (Math.abs(sl.radius - mt.outerRadius) > 1e-9) fail('DTO', 'sliceAt.radius разошёлся с моделью');
    if (sl.position !== 0.5) fail('DTO', 'sliceAt.position не совпал с запрошенным');
    const recount = {};
    for (const c of sl.cells) recount[c] = (recount[c] || 0) + 1;
    for (const k of Object.keys(sl.fractions))
      if (Math.abs(sl.fractions[k] - recount[k] / sl.cells.length) > 1e-9)
        fail('DTO', `sliceAt.fractions[${k}] не совпал с пересчётом по cells`);
  }

  return { passed: failures.length === 0, cases, failures };
}
