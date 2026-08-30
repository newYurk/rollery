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
  lists: { hoso: [], futo: [], ura: [], cake: [] },
  sel: 'salmon',
  preview: false,
  mute: false,
  cuts: 0,                     // срезов за сессию — замер 1
  cutsTotal: 0,
  rollP: 0,                    // прогресс скрутки 0..1 (в режиме lay)
  bigPiece: -1,
  selPatch: null,              // выделенная начинка на листе
  // «Почерк»: как игрок тянул циновку. air — воздух между витками (быстрая тяга),
  // wobble — неравномерность толщины по длине (рывки), press — множитель прижима (удержание в конце).
  // Нейтральные значения {0, 0, 1} дают ровно ту же намотку, что и раньше.
  hand: { air: 0, wobble: 0, phase: 0, press: 1, v: 1, cv: 0, hold: 0 },
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
// ВО ЧТО ЗАВОРАЧИВАТЬ — ТЕПЕРЬ ВЫБОР, А НЕ СВОЙСТВО ТИПА. Решение владельца 27.08: «вместо
// нори мы можем положить блинную, рисовую бумагу… во что заворачивать мы можем выбирать».
// Формат не выдуман: во Франции «Makis de crêpes» кладут блин вместо нори, в Испании — лист
// из застывшей клубники, в Вакаяме フルーツ寿司 крутят на настоящем суши-рисе.
// Толщина решает многое: она входит в шаг витка (T + w), то есть меняет число оборотов и ⌀.
// ⚑ inferred: замер есть только у нори. Остальные — оценка по продукту, отмечено honestly.
const WRAPPERS = {
  nori:  { name: 'Нори',            mm: 0.10, color: '#22342b', src: 'FAO, Nisizawa: лист 21×19 см ≈ 3 г' },
  rice:  { name: 'Рисовая бумага',  mm: 0.50, color: '#efe6d4', src: 'inferred' },
  soy:   { name: 'Соевая',          mm: 0.20, color: '#e3c069', src: 'inferred' },
  egg:   { name: 'Омлет',           mm: 1.50, color: '#e8b551', src: 'inferred (薄焼き卵)' },
  crepe: { name: 'Блин',            mm: 2.00, color: '#d8a05c', src: 'inferred; якорь — лаваш 2,0 мм, Rodríguez-Noriega, Foods 10(7):1473' },
  choco: { name: 'Шоколадный блин', mm: 2.00, color: '#4a2c20', src: 'inferred, как блин' },
};
for (const k in WRAPPERS) WRAPPERS[k].rgb = hexRgb(WRAPPERS[k].color);
// Начинки общие для всех: один экран, сладкое и несладкое рядом. Деление на типы отложено
// до игровых стратегий — владелец 27.08: «а потом мы уже… либо разделим на типы».
const ALL_INGREDIENTS = ['salmon', 'cucumber', 'tamago', 'avocado', 'shrimp', 'nori', 'mayo', 'eggsheet',
  'ricePink', 'riceYellow', 'riceGreen', 'riceBlack',
  'strawberry', 'kiwi', 'mango', 'banana', 'choco', 'jam', 'nut', 'pinkcream'];
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
const NPIECES = 6;

function load() {
  try {
    const m = JSON.parse(localStorage.getItem('rollery.model.v2') || 'null');
    if (m && m.lists) { S.base = m.base in BASES ? m.base : 'hoso'; S.lists = m.lists; S.wrap = (m.wrap && WRAPPERS[m.wrap]) ? m.wrap : null; }
    for (const k in BASES) if (!S.lists[k]) S.lists[k] = [];
    S.preview = localStorage.getItem('rollery.preview') === '1';
    S.mute = localStorage.getItem('rollery.mute') === '1';
    S.shape = localStorage.getItem('rollery.shape') || 'round';
    S.cutsTotal = +(localStorage.getItem('rollery.cuts') || 0);
    S.album = JSON.parse(localStorage.getItem('rollery.album') || '[]');
    if (!Array.isArray(S.album)) S.album = [];
  } catch (e) {}
  S.sel = B().ingredients[0];
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

