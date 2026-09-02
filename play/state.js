'use strict';
// СОСТОЯНИЕ СЕССИИ: что игрок выбрал и что положил, плюс сохранение в localStorage.
//
// Вынесено из play/index.html 29.08.2026 дословно. Это НЕ модель: модель считает геометрию
// и ничего не знает про игрока; здесь наоборот — текущая база, обёртка, форма, рука, списки
// патчей, альбом. Единственное место в стенде, которое трогает localStorage.
//
// Подключается ПОСЛЕ каталога (нужны WRAPPERS, BASES) и ДО модели: модель читает S и B().

// ---------------------------------------------------------------- состояние
const S = {
  mode: 'lay',                 // lay | rolled | cut | revealed | slicing | plate
  base: 'hoso',
  lists: { hoso: [], futo: [], ura: [] },
  sel: 'salmon',
  preview: false,
  mute: true,
  // ⚠ ОТЛАДОЧНЫЕ КОНТУРЫ, клавиша L. Идея владельца 31.08: пиксели оставить, а границу
  // рисовать ВЕКТОРОМ поверх — «чтобы вот так прямо нарисовать, где контур». Это режим
  // проверки глазом, а не арт: увидеть, где на самом деле проходит граница куска, когда
  // пиксельная сетка её округляет. По умолчанию выключен, в слепок не входит.
  lines: false,
  cuts: 0,                     // срезов за сессию — замер 1
  cutsTotal: 0,
  rollP: 0,                    // прогресс скрутки 0..1 (в режиме lay)
  bigPiece: -1,
  selPatch: null,              // выделенная начинка на листе
  // «Почерк»: как игрок тянул циновку. air — воздух между витками (быстрая тяга),
  // wobble — неравномерность толщины по длине (рывки), press — множитель прижима (удержание в конце).
  // Нейтральные значения {0, 0, 1} дают ровно ту же намотку, что и раньше.
  hand: handOf(),
  wrap: null,     // во что заворачиваем: null = по умолчанию для базы, см. WRAPPERS
  turns: null,                 // число витков (пазл задаёт длину листа); null — по базе
  shape: 'round',              // форма прессовки: round | square | triangle
  puzzle: null,                // режим «Пазл»: { level, seed, target, vs, result }
  album: [],                   // сохранённые роллы: рецепт + почерк, картинки пересчитываются
  albumOpen: -1,               // раскрытая запись альбома
  albumScroll: 0,
  saved: 0,                    // время подсветки «сохранено»
};
const patches = () => S.lists[S.base];

// ── МИНИМАЛЬНЫЙ СТЕНД (issue #96, решение владельца 30.08) ───────────────────
// По умолчанию игра показывает только основные механики тем же набором, что
// лаборатория: базы футомаки/хосомаки, начинки её раскладок (тамаго, лосось,
// огурец) + нори + две краски (розовый и зелёный — главные цвета кадзаримаки).
// Каждая проба в игре тогда сверяема с прогоном лаборатории тем же материалом.
// ?full возвращает всё: остальные базы, полную палитру, пазл, альбом, обёртки.
// Это фильтр ВИТРИНЫ, не модели: модель, регрессия ?check и сохранённые
// раскладки знают полный каталог; ссылки ?puzzle продолжают работать.
// Полный интерфейс: ?full, вход в пазл (?puzzle) или ссылка-пазл (#p=… — хэш, не query).
const FULL_UI = /[?&](full|puzzle)/.test(location.search) || /#p=/.test(location.hash);
// Одна база: хосомаки и футомаки для тестирования механик неразличимы (та же скрутка,
// подворот, ~1,4 оборота — different только масштаб). Футомаки — потому что раскладки
// лаборатории гоняются на нём, и рис толще (узору больше места). Хосомаки — в ?full.
const MIN_BASES = ['futo'];
// Набор выбран владельцем: как можно разнообразнее по форме и при этом удобен для проверок.
// Брусок (лосось), сектор (огурец), полумесяц-долька (авокадо), короткий полукруг (креветка — лежит не на
// всю длину ролла и потому видна не в каждом кусочке, dv 0,3), жидкое волной
// (майо), плоский широкий (тамаго — раскладки лаборатории), нори + две краски.
const MIN_ING = new Set(['salmon', 'cucumber', 'avocado', 'shrimp', 'mayo', 'tamago', 'nori', 'ricePink', 'riceGreen']);
const uiBases = () => FULL_UI ? Object.keys(BASES) : MIN_BASES;
const uiIngredients = () => FULL_UI ? B().ingredients : B().ingredients.filter(k => MIN_ING.has(k));

// ── ИСТОРИЯ ДЕЙСТВИЙ (issue #84, §5.3 контракта) ─────────────────────────────
// «Отменить» раньше делало patches().pop() — снимало последний ДОБАВЛЕННЫЙ кусок, а не
// последнее ДЕЙСТВИЕ. Подвинул огурец, нажал «Отменить» — исчезал лосось, положенный до него,
// а сдвиг не откатывался. Сдвиг, поворот, удаление и «в нори» не откатывались вообще.
//
// Храним СНИМКИ раскладки, а не команды: раскладка — это плоский массив патчей без ссылок,
// её клон стоит микросекунды, а обратная операция для каждой команды писалась бы отдельно и
// разъезжалась бы с прямой. Цена — память: 60 снимков по ~20 патчей это десятки килобайт.
//
// Снимок кладётся ПЕРЕД изменением (pushHistory), поэтому undo возвращает состояние «как было».
const HIST_MAX = 60;
const hist = { past: [], future: [], base: null };
const histSnap = () => JSON.stringify(patches());
function pushHistory() {
  // при смене базы история не переносится: раскладки у баз разные, и откат в чужую был бы ложью
  if (hist.base !== S.base) { hist.past.length = 0; hist.future.length = 0; hist.base = S.base; }
  hist.past.push(histSnap());
  if (hist.past.length > HIST_MAX) hist.past.shift();
  hist.future.length = 0;                       // новое действие обрывает ветку «вперёд»
}
function histApply(json) { S.lists[S.base] = JSON.parse(json); S.selPatch = null; touchModel(); }
function undo() {
  if (hist.base !== S.base || !hist.past.length) return false;
  hist.future.push(histSnap());
  histApply(hist.past.pop());
  return true;
}
function redo() {
  if (hist.base !== S.base || !hist.future.length) return false;
  hist.past.push(histSnap());
  histApply(hist.future.pop());
  return true;
}
const canUndo = () => hist.base === S.base && hist.past.length > 0;
const canRedo = () => hist.base === S.base && hist.future.length > 0;
// ВО ЧТО ЗАВОРАЧИВАТЬ — ТЕПЕРЬ ВЫБОР, А НЕ СВОЙСТВО ТИПА. Решение владельца 27.08: вместо нори
// можно положить другой лист — обёртка становится тем, что игрок выбирает сам.
// ⚠ ОБОСНОВАНИЕ ЗАМЕНЕНО 31.08. Раньше здесь стояли французские «Makis de crêpes» и испанский
// клубничный лист — под правилом «только японская тематика» они больше не доводы. Приём
// держится на японском: 薄焼き卵 (омлетом крутят 変わり巻き), 湯葉, лента дайкона 桂剥き,
// 求肥 в вагаси. Обёртка, кроме нори, — это не вольность, а отдельный названный приём.
// Толщина решает многое: она входит в шаг витка (T + w), то есть меняет число оборотов и ⌀.
// ⚑ inferred: замер есть только у нори. Остальные — оценка по продукту, отмечено honestly.
const WRAPPERS = {
  nori:  { name: 'Нори',            mm: 0.10, color: '#22342b', src: 'выведено: FAO даёт 21×19 см и ≈3 г → 75 г/м² ÷ ρ 0,7–1,0; толщину источник не называет (#107)' },
  rice:  { name: 'Рисовая бумага',  mm: 0.50, color: '#efe6d4', src: 'inferred' },
  soy:   { name: 'Соевая',          mm: 0.20, color: '#e3c069', src: 'inferred' },
  egg:   { name: 'Омлет',           mm: 1.50, color: '#e8b551', src: 'inferred (薄焼き卵)' },
  // 求肥 (гюхи) — мягкий лист из моти-муки с сахаром и сиропом; не черствеет, поэтому его
  // и раскатывают в лист и заворачивают в него сладкое. Это японская замена бисквиту, снятому
  // 31.08: сладкий ролл остаётся, европейский рулет — нет. Толщины в источниках нет.
  gyuhi: { name: 'Гюхи (моти)',     mm: 1.50, color: '#f7f0e6', src: 'inferred (求肥); источник подтверждает лист и заворачивание, миллиметров не даёт' },
};
for (const k in WRAPPERS) WRAPPERS[k].rgb = hexRgb(WRAPPERS[k].color);
// Начинки общие для всех: один экран, сладкое и несладкое рядом. Деление на типы отложено
// до игровых стратегий — владелец 27.08 отложила это на потом: разделить на типы можно будет позже.
const ALL_INGREDIENTS = ['salmon', 'tuna', 'cucumber', 'tamago', 'avocado', 'shrimp', 'nori', 'mayo', 'eggsheet',
  // Канон футомаки, заведён 31.08 (#10): без него собрать настоящий футомаки было нечем.
  'shiitake', 'kanpyo', 'anago', 'denbu',
  'ricePink', 'riceYellow', 'riceGreen', 'riceBlack',
  // Рис как ИНСТРУМЕНТ РИСОВАНИЯ (#17, 01.09): грядка добавляет толщину постели, ложбинка
  // снимает. Белое поле между начинками — это и есть рис, и теперь его толщиной управляет игрок.
  'riceRidge', 'riceDip',
  'strawberry', 'kiwi', 'mango', 'banana', 'jam', 'nut'];
// Активная база = тип (лист, грядка) + выбранная обёртка поверх него.
// ⚠ Ключ — только база и обёртка. Правка BASES на лету через него НЕ ПРОХОДИТ: при опытах
// в консоли меняй базу туда-обратно, иначе намеряешь старое. Дважды на этом попался.
let _bCache = null, _bKey = '';
const B = () => {
  const base = BASES[S.base];
  // У рулета «обёртка» — это САМ БИСКВИТ, из него ролл и состоит. Подменить его на нори значит
  // разрушить базу: длина листа у рулета выводится из числа витков и толщины бисквита.
  const wk = base.wrapFixed ? null : (S.wrap && WRAPPERS[S.wrap] ? S.wrap : (base.wrapKey || 'nori'));
  const key = S.base + '|' + wk;
  if (_bKey !== key) {
    const ings = ALL_INGREDIENTS.filter(i => ING[i]);
    _bCache = wk ? Object.assign({}, base, { w: WRAPPERS[wk].mm / U_MM, wrapper: WRAPPERS[wk].color,
                                             wrapperRgb: WRAPPERS[wk].rgb, wrapKey: wk, ingredients: ings })
                 : Object.assign({}, base, { ingredients: ings });
    _bKey = key;
  }
  return _bCache;
};
// ЧИСЛО КУСКОВ ТЕКУЩЕЙ БАЗЫ. Само число живёт в каталоге, у базы (BASES[...].pieces) —
// здесь только чтение, чтобы одно определение осталось одним. Запасные 6 — на случай базы
// без поля; такой в каталоге нет, но чтение состояния переживает и старый localStorage.
const npieces = () => (BASES[S.base] && BASES[S.base].pieces) || 6;

function load() {
  try {
    const m = JSON.parse(localStorage.getItem('rollery.model.v2') || 'null');
    if (m && m.lists) { S.base = m.base in BASES ? m.base : 'hoso'; S.lists = m.lists; S.wrap = (m.wrap && WRAPPERS[m.wrap]) ? m.wrap : null; }
    for (const k in BASES) if (!S.lists[k]) S.lists[k] = [];
    S.preview = localStorage.getItem('rollery.preview') === '1';
    // Ключа нет — новый игрок, звук молчит. Сравнение с '1' давало обратное:
    // отсутствие ключа читалось как «не выключено» и игра начинала со звуком.
    S.mute = localStorage.getItem('rollery.mute') !== '0';
    S.shape = localStorage.getItem('rollery.shape') || 'round';
    S.cutsTotal = +(localStorage.getItem('rollery.cuts') || 0);
    S.album = JSON.parse(localStorage.getItem('rollery.album') || '[]');
    if (!Array.isArray(S.album)) S.album = [];
  } catch (e) {}
  // Минимальный стенд: сохранённая база/начинка может быть спрятана (#96) — раскладки при этом
  // НЕ трогаем, они переживут и вернутся с ?full.
  if (!uiBases().includes(S.base)) S.base = 'futo';
  S.sel = uiIngredients()[0] || B().ingredients[0];
  for (const b in S.lists) S.lists[b] = S.lists[b].filter(p => ING[p.kind]);
}
function save() {
  try {
    localStorage.setItem('rollery.model.v2', JSON.stringify({ base: S.base, lists: S.lists, wrap: S.wrap }));
    localStorage.setItem('rollery.preview', S.preview ? '1' : '0');
    localStorage.setItem('rollery.mute', S.mute ? '1' : '0');
    localStorage.setItem('rollery.shape', S.shape);
    localStorage.setItem('rollery.cuts', String(S.cutsTotal));
  } catch (e) {}
}

