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
  return inv;
}

function runRollFacadeChecks() {
  const cases = [], failures = [];
  const fail = (id, msg) => failures.push(`${id}: ${msg}`);

  // 1. Эквивалентность на всех fixtures.
  for (const fx of ROLL_FIXTURES) {
    const legacy = evaluateLegacyFixture(fx);
    const facade = facadeInvariants(fx);
    if (facade.error) { fail(fx.id, 'facade не принял рецепт — ' + facade.error); continue; }
    const diff = invariantsDiff(legacy, facade);
    cases.push({ id: fx.id, ok: diff.length === 0 });
    for (const d of diff) fail(fx.id, d);
  }

  // 2. Facade не трогает переданный рецепт. Ловит классическую ошибку переходника:
  // restack/computeCore пишут в элементы списка, и общий по ссылке массив «пропитался» бы.
  {
    const src = JSON.parse(JSON.stringify(ROLL_FIXTURES[1].recipe));
    const before = JSON.stringify(src);
    const roll = evaluateRoll(createRecipe(src));
    sliceAt(roll, 0.5);
    if (JSON.stringify(src) !== before) fail('мутации', 'evaluateRoll изменил переданный рецепт');
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

  // 8. Раскладка листа: DTO не пустой и согласован с ориентацией (#23).
  {
    const lay = deriveSheetLayout(createRecipe(ROLL_FIXTURES[1].recipe), { width: 1440, height: 900, dpr: 2 });
    if (!lay.ok || !(lay.sheet.lenU > 0) || !(lay.sheet.lenV > 0)) fail('раскладка', 'deriveSheetLayout вернул пустую рамку');
    else if (lay.sheet.uAxis === 'x' && lay.sheet.lenU !== lay.sheet.w) fail('раскладка', 'при повёрнутом листе lenU разошёлся с шириной рамки');
  }

  return { passed: failures.length === 0, cases, failures };
}
