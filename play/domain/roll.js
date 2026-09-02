'use strict';
// COMPATIBILITY FACADE НАД ГЕОМЕТРИЕЙ (issue #72, шаг 3 плана миграции).
//
// ЧТО ЭТО. Тонкий переходник: снаружи — доменные вызовы (рецепт → ролл → срез), внутри —
// нынешний монолит play/model/geometry.js, слово в слово. Facade НИЧЕГО не считает сам и
// ничего не исправляет: он только даёт границу, за которую потребители будут переезжать
// по одному, и точку, где однажды поменяются внутренности, а вызовы останутся теми же.
//
// ЧЕМ ЭТО НЕ ЯВЛЯЕТСЯ. Это не новая модель рецепта. Формат здесь — тот, что проект уже
// сохраняет в альбом (albumSave в play/ui/album.js): { base, wrap, turns, shape, hand, list }.
// Обсуждаемая Recipe v2 (construction/topology + placements) сюда НЕ вводится: упорядоченный
// массив «слоёв от центра к краю» не описывает раскладку на плоском листе, а радиальный порядок
// возникает из скрутки. Решение — отдельным RFC (docs/architecture/recipe-model-rfc.md).
//
// ⚠ ГЛАВНЫЙ ШОВ. Геометрия читает ГЛОБАЛЬНОЕ состояние: buildModel берёт базу, обёртку, форму,
// витки и руку из S (buildModel, паспорт `g`). Поэтому «посчитать рецепт» здесь — это временно
// поставить S и вернуть как было (withRollRecipeState). Это цена совместимости, и именно её
// снимают следующие шаги: пока шов внутри facade, он один, а не размазан по вызывающим.
//
// ЗАВИСИМОСТИ, ЧЕСТНО. Classic script: сборки нет, файлы делят одно лексическое окружение.
// Facade опирается не только на геометрию:
//   model/catalog.js — BASES, ING, WRAPPERS, U_MM, TAU;
//   state.js         — S, B();
//   model/geometry.js — buildModel, windFor, materialAt, sheetLen;
//   ui/layout.js     — W, H, DPR, L, layout()  (нужны deriveSheetLayout);
//   render/slice.js  — SHAPES                  (нужен validateRecipe).
// Две последние загружаются ПОЗЖЕ этого файла (index.html:26,27 против :25) — на объявление
// это не влияет, обращения происходят при ВЫЗОВЕ, к тому времени всё на месте. Но зависеть
// домену от рендера неправильно: SHAPES живёт в render/slice.js только исторически. Поэтому
// проверка формы ниже мягкая (если списка нет — не браковать), а сам список должен переехать
// в домен отдельным шагом миграции.

const ROLL_FACADE_VERSION = 1;
const ROLL_HAND_NEUTRAL = { air: 0, wobble: 0, phase: 0, press: 1, v: 1, cv: 0, hold: 0 };
const ROLL_SLICE_RINGS = 12, ROLL_SLICE_RAYS = 24;

// ── рецепт ───────────────────────────────────────────────────────────────────

// Нормализация входа в совместимый DTO. Ничего не выдумывает: недостающее берёт по
// умолчанию так же, как это делает игра при загрузке (state.js load, album.js albumLoad).
function createRecipe(input) {
  const src = input || {};
  const hand = Object.assign({}, ROLL_HAND_NEUTRAL, src.hand || {});
  return {
    base: src.base || 'hoso',
    wrap: src.wrap || null,
    turns: turnsOf(src.turns),
    shape: src.shape || 'round',
    hand,
    // Клон: рецепт не должен делить массив с вызывающим — restack и computeCore пишут в
    // элементы списка (z0/z1, inCore), и чужой объект молча пропитался бы результатом.
    list: JSON.parse(JSON.stringify(src.list || [])),
  };
}

// Проверка совместимого рецепта. Возвращает структурированные ошибки, не бросает:
// вызывающему обычно нужно показать причину, а не поймать исключение.
function validateRecipe(recipe) {
  const errors = [];
  if (!recipe || typeof recipe !== 'object') return { ok: false, errors: [{ field: '', message: 'рецепт не объект' }] };
  if (!BASES[recipe.base]) errors.push({ field: 'base', message: `неизвестная база «${recipe.base}»` });
  if (recipe.wrap && !WRAPPERS[recipe.wrap]) errors.push({ field: 'wrap', message: `неизвестная обёртка «${recipe.wrap}»` });
  if (recipe.shape && typeof SHAPES !== 'undefined' && !SHAPES[recipe.shape]) errors.push({ field: 'shape', message: `неизвестная форма «${recipe.shape}»` });
  if (recipe.turns != null && !(recipe.turns > 0)) errors.push({ field: 'turns', message: 'витки должны быть положительным числом или null' });
  if (!Array.isArray(recipe.list)) errors.push({ field: 'list', message: 'list должен быть массивом' });
  else recipe.list.forEach((p, i) => {
    if (!p || !ING[p.kind]) errors.push({ field: `list[${i}].kind`, message: `неизвестная начинка «${p && p.kind}»` });
    else if (!(p.u >= 0 && p.u <= 1) || !(p.v >= 0 && p.v <= 1)) errors.push({ field: `list[${i}]`, message: 'u и v должны лежать в 0..1' });
  });
  return { ok: errors.length === 0, errors };
}

// ── шов с глобальным состоянием ──────────────────────────────────────────────

// Временно применить рецепт к S, вызвать fn(model), вернуть S как было — включая S.wrap.
function withRollRecipeState(recipe, hand, fn) {
  const keep = { base: S.base, wrap: S.wrap, turns: S.turns, shape: S.shape, hand: S.hand,
                 list: S.lists[recipe.base] };
  try {
    S.base = recipe.base;
    S.wrap = recipe.wrap || null;
    S.turns = recipe.turns || null;
    S.shape = (typeof SHAPES !== 'undefined' && SHAPES[recipe.shape]) ? recipe.shape : 'round';
    S.hand = Object.assign({}, ROLL_HAND_NEUTRAL, recipe.hand || {}, hand || {});
    const list = JSON.parse(JSON.stringify(recipe.list || []));
    S.lists[recipe.base] = list;
    return fn(buildModel(list));
  } finally {
    S.base = keep.base; S.wrap = keep.wrap; S.turns = keep.turns; S.shape = keep.shape;
    S.hand = keep.hand; S.lists[recipe.base] = keep.list;
  }
}

// ── ролл и срез ──────────────────────────────────────────────────────────────

// Посчитать ролл по рецепту. Возвращает DTO с доменными числами; сама legacy-модель лежит
// в legacyModel — это НАМЕРЕННО видное место шва: когда потребители перестанут её читать,
// поле уйдёт, и это будет видно в диффе, а не случится молча.
function evaluateRoll(recipe, handParams, options) {
  const v = validateRecipe(recipe);
  if (!v.ok) return { ok: false, errors: v.errors, metrics: null, legacyModel: null };
  const opt = options || {};
  return withRollRecipeState(recipe, handParams, m => {
    const wd = windFor(m, opt.metricsSlice === undefined ? 0.5 : opt.metricsSlice);
    return {
      ok: true,
      errors: [],
      recipe,
      metrics: {
        turns: wd.turns,
        outerDiameterMm: 2 * m.Rmax * U_MM,
        outerRadius: m.Rmax,
        closePoint: wd.sClose,
        sheetEnd: wd.sEnd,
        sheetLength: m.g.L,
        hasCore: !!m.core,
        coreRadius: m.core ? m.core.R : 0,
        coreFold: m.core ? m.core.sFold : 0,
        closed: wd.turns >= 1,
        // Форма прессовки едет в модель через S.shape и живёт в m.shape. Без неё в метриках
        // ни один инвариант не отличал круглый ролл от квадратного — F04 обещал покрыть
        // квадрат и не покрывал (найдено ревью PR #100).
        shape: m.shape,
      },
      legacyModel: m,
    };
  });
}

// КАК ЗОВЁТСЯ МАТЕРИАЛ В ТОЧКЕ — ОДНО ОПРЕДЕЛЕНИЕ. Важно не «есть ли что-то», а ЧТО именно
// лежит в точке, поэтому патч сворачивается в 'patch:<kind>'. До 31.08 это выражение стояло
// дважды — здесь и в play/test/probe.js, — и слепок регрессии сравнивал модель с самим собой
// через ВТОРУЮ редакцию той же логики. Ровно то, что уже случалось со свёрткой карты.
const rollProbeClass = (q) => !q ? 'null'
  : q.cls === 'patch' ? 'patch:' + (q.mt && q.mt.p ? q.mt.p.kind : '?') : q.cls;

// Срез ролла в точке position (доля длины ролла, 0..1) — ДАННЫЕ, не картинка.
// Возвращает сетку классов материала и их доли; рисует это renderer (drawSlice), не facade.
function sliceAt(roll, position, options) {
  if (!roll || !roll.ok) return { ok: false, cells: [], fractions: {} };
  const opt = options || {};
  const rings = opt.rings || ROLL_SLICE_RINGS, rays = opt.rays || ROLL_SLICE_RAYS;
  const m = roll.legacyModel, v = position === undefined ? 0.5 : position;
  // Модель уже посчитана; windFor кеширует намотку ломтика внутри модели, глобальное S
  // здесь не нужно — материал берётся из m и wd.
  const wd = windFor(m, v);
  const cells = [], counts = {};
  for (let ri = 0; ri < rings; ri++) for (let ai = 0; ai < rays; ai++) {
    const r = (ri + 0.5) / rings * m.Rmax, phi = ai / rays * TAU;
    const cls = rollProbeClass(materialAt(m, wd, v, r, phi));
    cells.push(cls); counts[cls] = (counts[cls] || 0) + 1;
  }
  const fractions = {};
  for (const k of Object.keys(counts).sort()) fractions[k] = counts[k] / cells.length;
  return { ok: true, position: v, rings, rays, radius: m.Rmax, cells, fractions };
}

// ── карта материалов и сравнение (первый переезд потребителя, issue #72) ─────
//
// Это ЧИТАЮЩИЙ путь, вынесенный из play/render/slice.js: он ничего не рисует и ничего не
// мутирует — считает, из какого материала каждая точка среза, и насколько два ролла похожи.
// В рендере он оказался исторически (там же лежит face()), а по существу это домен: его
// потребитель — оценка пазла, а не отрисовка. Вычисление перенесено ДОСЛОВНО; в slice.js
// остались тонкие обёртки прежних имён, поэтому вызывающие не тронуты.
//
// ⚠ Одна зависимость осталась в рендере намеренно: shapeInfo/shapeK (форма прессовки).
// Они нужны и рисованию, и карте; тащить их сюда — это уже второй переезд, а этот PR
// сознательно узкий. Обращения происходят при вызове, порядок подключения не мешает.
//
// ⚠ Совместимость: `m.shape || S.shape` сохранён как был. Это чтение глобального состояния
// внутри «чистой» функции — тот самый шов, который снимается не здесь, а когда S перестанет
// быть источником рецепта. Записано, чтобы не выглядело недосмотром.

const ROLL_MAP_SIZE = 56;                 // сторона карты сравнения, px
const ROLL_KIND_IDS = Object.keys(ING);   // 0 — вне, 1 — рис/сердцевина, 2 — обёртка, 3+ — начинка

// Карта материалов среза как Uint8Array size×size. Rref — общий масштаб (у двух моделей он
// обязан быть один, иначе карты несравнимы).
function materialMapOf(size, vSlice, m, Rref) {
  const si = shapeInfo(m.shape || S.shape, m.Rmax, m.g.press), wd = windFor(m, vSlice);
  const out = new Uint8Array(size * size), half = size / 2, scale = (half - 1) / (Rref * si.margin);
  for (let py = 0; py < size; py++) for (let px = 0; px < size; px++) {
    const dx = (px + 0.5 - half) / scale, dy = (py + 0.5 - half) / scale;
    let phi = Math.atan2(dy, dx); if (phi < 0) phi += TAU;
    const r = Math.hypot(dx, dy) * shapeK(phi, si);
    if (r > wd.Rout) continue;
    const mat = materialAt(m, wd, vSlice, r, phi);
    out[py * size + px] = mat.cls === 'out' ? 0 : mat.cls === 'wrap' ? 2 : mat.cls === 'patch' ? 3 + ROLL_KIND_IDS.indexOf(mat.mt.p.kind) : 1;
  }
  return out;
}

// Похожесть двух моделей по срезам vs — Dice по классам начинок с допуском в пиксель.
// Рис и обёртка в счёт не идут (a[i] >= 3): считается узор, а не фон.
// total намеренно считает каждую карту отдельно: total = |A| + |B|, hits = 2·|A ∧ B|.
// Ревью 26.08 сочло двойной счёт ошибкой — это неверно: со «счётом один раз» полное
// совпадение даёт 1,33, а не 1. Не «чинить».
function similarityOf(mA, mB, vs) {
  const size = ROLL_MAP_SIZE, Rref = Math.max(mA.Rmax, mB.Rmax);
  let hits = 0, total = 0;
  const near = (map, i, id) => { const x = i % size, y = (i / size) | 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const xx = x + dx, yy = y + dy;
      if (xx >= 0 && yy >= 0 && xx < size && yy < size && map[yy * size + xx] === id) return true; }
    return false; };
  for (const v of vs) {
    const a = materialMapOf(size, v, mA, Rref), b = materialMapOf(size, v, mB, Rref);
    for (let i = 0; i < a.length; i++) {
      if (a[i] >= 3) { total++; if (near(b, i, a[i])) hits++; }
      if (b[i] >= 3) { total++; if (near(a, i, b[i])) hits++; }
    }
  }
  return total ? hits / total : 1;
}

// Доменный вход: карта среза по DTO ролла, свёрнутая в сравнимый вид (счётчики + выборка).
// Полную карту наружу не отдаём: её единственный потребитель — сравнение, а хранить 3136
// байт на срез в слепке незачем.
// ИМЯ КЛАССА КАРТЫ. Число класса — это «3 + индекс в ROLL_KIND_IDS», то есть оно зависит от
// ПОРЯДКА КАТАЛОГА: стоило 31.08 завести канон футомаки, как слепок упал с «класс 11: 194 ≠ 0 ·
// класс 16: 0 ≠ 194» — те же точки того же розового риса, просто индекс уехал на пять. Сторож,
// падающий от переучёта каталога, приучает пересниматься не глядя.
// Класс 1 — 'rice', а не 'spread': карта сливает в него и постель, и ядро подворота.
const rollMapClassName = (c) => c === 0 ? 'out' : c === 1 ? 'rice' : c === 2 ? 'wrap'
                                               : (ROLL_KIND_IDS[c - 3] || ('kind' + (c - 3)));
// СВЁРТКА КАРТЫ В СРАВНИМЫЙ ВИД — ОДНО ОПРЕДЕЛЕНИЕ НА ВСЕХ.
// Раньше эта же логика жила ДВАЖДЫ: здесь и в play/test/probe.js (mapSignature). Копии
// разошлись при первой же правке — домен считал классы числами, проба именами, и регрессия
// «facade ≠ legacy» дала 75 расхождений на пустом месте. Теперь обе зовут это.
// ⚠ Шаг пробы 313 — по модулю СТОРОНЫ карты (313 mod 56 = 33), а не по длине массива:
// при шаге 337 (337 mod 56 = 1) точки шли по диагонали и попадали в углы, где всегда пусто.
function rollMapDigest(map) {
  const counts = {}, probe = [];
  for (let i = 0; i < map.length; i++) counts[map[i]] = (counts[map[i]] || 0) + 1;
  for (let i = 0; i < map.length; i += 313) probe.push(rollMapClassName(map[i]));
  const out = { counts: {}, probe: probe.join(',') };
  for (const k of Object.keys(counts).sort((a, b) => a - b)) out.counts[rollMapClassName(+k)] = counts[k];
  return out;
}
function sliceMaterialMap(roll, position, options) {
  if (!roll || !roll.ok) return { counts: {}, probe: '' };
  const opt = options || {}, size = opt.size || ROLL_MAP_SIZE, m = roll.legacyModel;
  return rollMapDigest(materialMapOf(size, position === undefined ? 0.5 : position, m, opt.Rref || m.Rmax));
}

// Доменный вход: насколько похожи два ролла на заданных срезах. 1 — совпали.
function compareRolls(rollA, rollB, positions) {
  if (!rollA || !rollA.ok || !rollB || !rollB.ok) return 0;
  return similarityOf(rollA.legacyModel, rollB.legacyModel, positions || [0.5]);
}

// ── раскладка листа ──────────────────────────────────────────────────────────

// Геометрия вида сверху для заданного окна — ДАННЫЕ (рамка листа, ручка циновки, ориентация).
// Имя намеренно derive*, а не render*: слой домена ВЫЧИСЛЯЕТ DTO, рисует его renderer.
// ⚠ Внутри зовётся legacy layout(), который пишет в глобальный L и меряет ширину подписей
// через ctx.measureText — canvas при этом не рисуется, но контекст должен существовать.
// Оба глобала (W/H/DPR и L) восстанавливаются.
function deriveSheetLayout(recipe, viewport, options) {
  const v = validateRecipe(recipe);
  if (!v.ok) return { ok: false, errors: v.errors, sheet: null };
  const vp = viewport || {};
  const keep = { W, H, DPR, base: S.base, wrap: S.wrap, turns: S.turns, L: JSON.parse(JSON.stringify(L)) };
  try {
    if (vp.width) W = vp.width;
    if (vp.height) H = vp.height;
    if (vp.dpr) DPR = vp.dpr;
    S.base = recipe.base; S.wrap = recipe.wrap || null; S.turns = recipe.turns || null;
    layout();
    const s = L.sheet, h = L.handle;
    return {
      ok: true, errors: [],
      mode: L.mode,
      sheet: { x: s.x, y: s.y, w: s.w, h: s.h, uAxis: s.uAxis, lenU: s.lenU, lenV: s.lenV },
      handle: { x: h.x, y: h.y, w: h.w, h: h.h },
      chips: { rows: L.chips.rows, perRow: L.chips.perRow, scroll: L.chipScroll },
    };
  } finally {
    W = keep.W; H = keep.H; DPR = keep.DPR;
    S.base = keep.base; S.wrap = keep.wrap; S.turns = keep.turns;
    Object.assign(L, keep.L);
    layout();   // вернуть L в согласие с восстановленным окном
  }
}

// ── сериализация ─────────────────────────────────────────────────────────────

// Сериализация совместимого рецепта: обёртка (wrap) сохраняется — как и в альбоме.
// Обёртка сохраняется — как и в альбоме (albumSave пишет wrap, withRecipe его возвращает).
function serializeRecipe(recipe) {
  const r = createRecipe(recipe);
  return { v: ROLL_FACADE_VERSION, base: r.base, wrap: r.wrap, turns: r.turns, shape: r.shape,
           hand: { air: r.hand.air, wobble: r.hand.wobble, phase: r.hand.phase, press: r.hand.press },
           list: r.list };
}

// Восстановление рецепта. Здесь же — единственное место, где разбираются старые форматы:
// запись альбома без wrap и без версии читается как совместимый рецепт.
function deserializeRecipe(payload) {
  if (!payload || typeof payload !== 'object') return createRecipe(null);
  return createRecipe({ base: payload.base, wrap: payload.wrap || null, turns: payload.turns || null,
                        shape: payload.shape, hand: payload.hand, list: payload.list });
}
