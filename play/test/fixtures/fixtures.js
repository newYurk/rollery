'use strict';
// ХАРАКТЕРИЗАЦИОННЫЕ FIXTURES: входы, на которых снят слепок нынешнего поведения геометрии.
//
// ЗАЧЕМ. Перед тем как заводить facade над play/model/geometry.js, надо зафиксировать, что
// геометрия считает СЕЙЧАС. Иначе «facade ничего не сломал» — утверждение без доказательства.
// Слепок ожидаемых чисел лежит отдельно (play/test/legacy/baseline-data.js) и снят прогоном.
//
// ФОРМАТ РЕЦЕПТА ЗДЕСЬ — НЕ НОВЫЙ. Это ровно то, что проект уже сохраняет в альбом
// (albumSave в play/ui/album.js): { base, wrap, turns, shape, hand, list }. Новую схему
// (Recipe v2, слои от центра к краю) в этом PR НЕ вводим — она обсуждается отдельным RFC,
// и предрешать её тестами нельзя.
//
// ⚠ ДЕТЕРМИНИЗМ. Ни одного Math.random: phase у каждого куска задан числом. placeAt() в игре
// ставит случайную фазу, и слепок от неё поплыл бы; здесь фаза — часть входа.
//
// Подключается как обычный classic script (сборки в проекте нет), объявляет ROLL_FIXTURES.

const ROLL_FIXTURES = [
  {
    id: 'F01-hosomaki-basic',
    note: 'Простая базовая раскладка: один брусок в середине полулиста',
    recipe: {
      base: 'hoso', wrap: null, turns: null, shape: 'round',
      hand: { air: 0, wobble: 0, phase: 0, press: 1 },
      list: [{ kind: 'cucumber', u: 0.45, v: 0.5, z0: 0, z1: 1, phase: 0.5 }],
    },
  },
  {
    id: 'F02-futomaki-basic',
    note: 'Толстая база и несколько начинок разных классов: брусок, линза, кружок',
    recipe: {
      base: 'futo', wrap: null, turns: null, shape: 'round',
      hand: { air: 0, wobble: 0, phase: 0, press: 1 },
      list: [
        { kind: 'salmon', u: 0.30, v: 0.50, z0: 0, z1: 1, phase: 1.2 },
        { kind: 'avocado', u: 0.45, v: 0.35, z0: 0, z1: 1, phase: 0.4 },
        { kind: 'shrimp', u: 0.60, v: 0.65, z0: 0, z1: 1, phase: 2.1 },
      ],
    },
  },
  {
    id: 'F03-wrapper-roundtrip',
    note: 'Нестандартная обёртка (омлет 1,5 мм): она входит в шаг витка, значит меняет ⌀ и число ' +
          'оборотов. Здесь же ловится потеря wrap при сериализации — см. baseline-данные.',
    recipe: {
      base: 'futo', wrap: 'egg', turns: null, shape: 'round',
      hand: { air: 0, wobble: 0, phase: 0, press: 1 },
      list: [{ kind: 'tamago', u: 0.40, v: 0.50, z0: 0, z1: 1, phase: 0.9 }],
    },
  },
  {
    id: 'F04-puzzle-recipe',
    note: 'Формат режима «Пазл»: заданное число витков (turns меняет длину листа) и ' +
          'квадратная прессовка — то, что приходит из ссылки-пазла',
    recipe: {
      base: 'futo', wrap: null, turns: 3, shape: 'square',
      hand: { air: 0, wobble: 0, phase: 0, press: 1 },
      list: [
        { kind: 'ricePink', u: 0.35, v: 0.5, z0: 0, z1: 1, phase: 0, dv: 1 },
        { kind: 'salmon', u: 0.62, v: 0.5, z0: 0, z1: 1, phase: 0.3 },
      ],
    },
  },
  {
    id: 'F05-hand-variation',
    note: 'Тот же рецепт, что F02, но рука другая: быстрая тяга с воздухом и лёгким прижимом. ' +
          'Почерк обязан менять намотку — иначе он ничего не значит.',
    recipe: {
      base: 'futo', wrap: null, turns: null, shape: 'round',
      hand: { air: 0.20, wobble: 0.05, phase: 1.0, press: 0.87 },
      list: [
        { kind: 'salmon', u: 0.30, v: 0.50, z0: 0, z1: 1, phase: 1.2 },
        { kind: 'avocado', u: 0.45, v: 0.35, z0: 0, z1: 1, phase: 0.4 },
        { kind: 'shrimp', u: 0.60, v: 0.65, z0: 0, z1: 1, phase: 2.1 },
      ],
    },
  },
  {
    id: 'F06-rotated-patch',
    note: 'Кусок, положенный по диагонали (rot = 45°): patchSRange считает его сечение отдельно, ' +
          'и в каждом ломтике он оказывается на другом месте',
    recipe: {
      base: 'futo', wrap: null, turns: null, shape: 'round',
      hand: { air: 0, wobble: 0, phase: 0, press: 1 },
      list: [
        { kind: 'cucumber', u: 0.45, v: 0.45, z0: 0, z1: 1, phase: 0.7, rot: Math.PI / 4 },
        { kind: 'tamago', u: 0.65, v: 0.55, z0: 0, z1: 1, phase: 1.9 },
      ],
    },
  },
  {
    id: 'F07-edge-overload',
    note: 'Крайний случай: всё свалено к ближнему краю. Подворот вынужден ужиматься, чтобы ' +
          'остатка листа хватило на оборот с нахлёстом (см. computeCore). Детерминированный ' +
          'сценарий известной проблемы «ролл не замыкается» (issue #3).',
    recipe: {
      base: 'ura', wrap: null, turns: null, shape: 'round',
      hand: { air: 0, wobble: 0, phase: 0, press: 1 },
      list: [
        { kind: 'salmon', u: 0.06, v: 0.5, z0: 0, z1: 1, phase: 0.2 },
        { kind: 'avocado', u: 0.12, v: 0.5, z0: 0, z1: 1, phase: 0.8 },
        { kind: 'cucumber', u: 0.18, v: 0.5, z0: 0, z1: 1, phase: 1.4 },
      ],
    },
  },
];
