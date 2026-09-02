'use strict';
// LEGACY BASELINE: прогон fixtures ПРЯМО через монолит geometry.js, без facade.
//
// Это точка опоры всей миграции (issue #72): пока не доказано, что мы умеем воспроизводить
// нынешнее поведение числами, любое «facade ничего не сломал» — слова.
//
// ⚠ ГЕОМЕТРИЯ ЧИТАЕТ ГЛОБАЛЬНОЕ СОСТОЯНИЕ. buildModel берёт базу, обёртку, форму, витки и руку
// из S (см. buildModel и паспорт `g`), а не из аргументов. Поэтому «прогнать рецепт» — это
// временно ПОСТАВИТЬ S и вернуть как было. Ровно этот шов и есть предмет будущей миграции:
// пока он здесь, facade вынужден делать то же самое (play/domain/roll.js).
//
// Прецедент не выдуман: так уже устроен альбом — withRecipe (play/ui/album.js).
// Оба пути ведут себя одинаково: withRecipe тоже снимает и возвращает S.wrap (#86).

// ⚑ КОПИЯ ROLL_HAND_NEUTRAL, И ОНА НАМЕРЕННАЯ (issue #119). Побайтово то же, что в
// play/domain/roll.js, и порядок загрузки позволяет читать домен напрямую — но читать его
// здесь НЕЛЬЗЯ. Слепок регрессии существует, чтобы поймать изменение домена; слепок,
// берущий из домена свою опорную точку, изменится вместе с ним и промолчит. Независимость
// эталона от того, что он проверяет, — не дублирование, а его назначение.
//
// Отсюда и разница с probe.js, который в тот же вечер чинили в обратную сторону: probe
// ИЗМЕРЯЕТ модель и обязан брать её числа, baseline СРАВНИВАЕТ с зафиксированным прошлым
// и обязан их не брать.
const LEGACY_HAND_NEUTRAL = handOf();

// Временно применить рецепт к глобальному S, посчитать fn(model), вернуть S как было.
function withLegacyRecipe(recipe, fn) {
  const keep = { base: S.base, wrap: S.wrap, turns: S.turns, shape: S.shape, hand: S.hand,
                 list: S.lists[recipe.base] };
  try {
    S.base = recipe.base;
    S.wrap = recipe.wrap || null;
    S.turns = turnsOf(recipe.turns);
    S.shape = SHAPES[recipe.shape] ? recipe.shape : 'round';
    S.hand = Object.assign({}, LEGACY_HAND_NEUTRAL, recipe.hand || {});
    // Клон списка: модель не должна получить ссылку на fixture — restack проставляет z0/z1,
    // computeCore ставит inCore, и fixture молча «пропитался» бы результатом прошлого прогона.
    const list = JSON.parse(JSON.stringify(recipe.list || []));
    S.lists[recipe.base] = list;
    return fn(buildModel(list));
  } finally {
    S.base = keep.base; S.wrap = keep.wrap; S.turns = keep.turns; S.shape = keep.shape;
    S.hand = keep.hand; S.lists[recipe.base] = keep.list;
  }
}

// Инварианты одного fixture по legacy-пути.
function evaluateLegacyFixture(fx) { return withLegacyRecipe(fx.recipe, m => rollInvariants(m)); }

// Слепок всех fixtures — тем же кодом, которым он записывался. Печать этого объекта в
// консоли даёт содержимое play/test/legacy/baseline-data.js: слепок ПЕРЕСНИМАЕТСЯ осознанно,
// вместе с коммитом, где сказано, что изменилось в модели (то же правило, что у REF в checks.js).
function captureLegacyBaseline() {
  const out = {};
  for (const fx of ROLL_FIXTURES) out[fx.id] = evaluateLegacyFixture(fx);
  // Межмодельные пары — отдельным ключом: они не про одну модель, а про сравнение двух.
  // Служебные ключи начинаются с «__», перебор fixtures их не трогает.
  out.__pairs = pairSimilarities(r => withLegacyRecipe(r, m => m), similarity);
  return out;
}

// Проверка: нынешнее поведение совпадает с записанным слепком.
function runLegacyBaselineChecks() {
  const cases = [], failures = [];
  if (typeof ROLL_BASELINE === 'undefined') {
    failures.push('нет слепка: play/test/legacy/baseline-data.js не подключён');
    return { passed: false, cases, failures };
  }
  const wantPairs = ROLL_BASELINE.__pairs;
  if (wantPairs) {
    const got = pairSimilarities(r => withLegacyRecipe(r, m => m), similarity);
    for (const k of Object.keys(wantPairs))
      if (Math.abs((wantPairs[k] || 0) - (got[k] || 0)) > 1e-6)
        failures.push(`пара ${k}: ${wantPairs[k]} ≠ ${got[k]}`);
  } else failures.push('в слепке нет межмодельных пар — переснять');
  for (const fx of ROLL_FIXTURES) {
    const want = ROLL_BASELINE[fx.id];
    if (!want) { failures.push(`${fx.id}: нет записи в слепке`); continue; }
    const got = evaluateLegacyFixture(fx);
    const diff = invariantsDiff(want, got);
    cases.push({ id: fx.id, ok: diff.length === 0 });
    for (const d of diff) failures.push(`${fx.id}: ${d}`);
  }
  return { passed: failures.length === 0, cases, failures };
}
