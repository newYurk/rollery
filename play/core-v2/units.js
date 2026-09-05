// Core V2 — именованные константы и снимок каталога в мм.
// Внутри kernel все длины уже мм, углы — радианы, площади — мм².
// Перевод из единиц каталога (U_MM) делается ровно один раз, здесь.
// Не импортирует play/model/**.

export const TAU = Math.PI * 2;

/** Одна единица каталога = 5 мм. Источник: catalog.js:205. */
export const U_MM = 5;

/** Сетка лучей намотки. Тот же NB, что geometry.js:380 — независимое интегрирование дуги
 *  на этой сетке сравнивается с kernel; более грубая сетка заведомо не ловит tautology. */
export const NB = 1440;
export const DPHI = TAU / NB;

/** Голая полоса у ближнего края (доли листа). geometry.js:774. */
export const SPREAD_START = 0.048;

/**
 * Режим намотки. Не выводится из длины начинки (легаси #141 так делал).
 * ring — маки: рис кольцом вокруг 芯, нори снаружи один оборот.
 * spiral — узумаки/датемаки: лента носителя, ядра нет. V2 alpha не считает.
 * inverted — урамаки: начинка → нори → рис. V2 alpha не считает.
 */
export const WINDING = Object.freeze({
  ring: 'ring',
  spiral: 'spiral',
  inverted: 'inverted',
});

/** Абсолютные 2 см от ближней кромки (marron 「手前2cm位」). Не доля листа.
 *  Дальний клапан склейки масштабируется; этот зазор — нет. erratum-022. */
export const PLACEMENT_EDGE_MARGIN_MM = 20;

/**
 * Допуск длины листа и независимой дуги.
 * На сетке 1440 бинов дуга нори ~90 мм даёт шаг ~0,06 мм; 0,15 мм — запас на
 * квадратуру √(r²+dr²) и не скрывает ошибку единиц ×5 (~18 мм).
 */
export const EPS_LENGTH_MM = 0.15;

/** По умолчанию = EPS_LENGTH_MM (erratum-010). */
export const EPS_INVERT_MM = EPS_LENGTH_MM;

/**
 * Нижняя граница асимметрии ядра, мм (erratum-014/020).
 * Проверка F01: max(r0)−min(r0) > EPS. Верное пустое ядро даёт ≈1,88 мм по всем
 * лучам (угол коробки, не осевые 1,1). Скаляр → 0. Забытый ×U_MM → ≈0,377.
 * 0,50 лежит в (0,377; 1,88) и ловит обе мутации.
 */
export const EPS_CORE_ASYMMETRY_MM = 0.5;

/** Допуск доли лучей с 1 vs 2 пересечениями нори. ±4 бина на 1440. */
export const EPS_RAY_FRACTION = 4 / NB;

/**
 * Мультипликативный якорь площади к каталогу (erratum-006). ≥ 1, обязан быть
 * существенно меньше 1,18. 1,05 — шум сетки покоящегося куска. Развилка #134
 * закрыта источниками (erratum-022): твёрдая начинка не растягивается с листом.
 */
export const EPS_AREA_RATIO = 1.05;

/**
 * Площадь рисового кольца (сетка r0(φ)…rp) vs T·Lrice.
 * Не EPS_AREA_RATIO: та — якорь начинки к каталогу (#134).
 */
export const EPS_RICE_AREA_RATIO = 1.03;

/**
 * F03: соседние валидные uMm. В окне огурец — ядро, u не двигает срез (#139).
 * Порог = EPS_LENGTH_MM, чтобы шаг 1 мм, отображённый в срез, покраснел.
 */
export const MAX_CENTER_DELTA_MM = EPS_LENGTH_MM;
/** |a/b − 1| площадей соседних валидных F03. */
export const MAX_AREA_RATIO_DELTA = 0.02;

/** Полный угол сектора огурца. geometry.js:514. */
export const SECTOR_ANGLE = Math.PI / 4;

/**
 * Снимок базы хосомаки в мм на дату PR1.
 * Источник: catalog.js BASES.hoso, перевод × U_MM один раз.
 * Ключ каталога — `hoso`; RecipeV2.baseId для F01/F02 — `hosomaki` (fixtures.md).
 */
export const HOSOMAKI = Object.freeze({
  catalogKey: 'hoso',
  baseId: 'hosomaki',
  lengthMm: 105,          // sheetCm 10.5 → 105 мм
  widthMm: 190,           // Wv 38 × 5
  riceThicknessMm: 7,     // T 1.4 × 5
  noriThicknessMm: 0.1,   // w 0.02 × 5
  spreadStart: SPREAD_START,
  spreadEnd: 0.88,
  wrapMaterialId: 'nori',
  riceProfileId: 'standard',
  emptyCoreWidthMm: 5,    // Wc = max(0, 1) × 5
  emptyCoreHeightMm: 7.2, // Hc = T + 2w = 1.44 × 5
  pieces: 6,              // catalog.js BASES.hoso; AUTEC 6 на 180–190 мм
});

/**
 * Коридор 職人 для готового хосомаки. 江戸前 「直径3cm程度」.
 * Не калибр SUZUMO □25. Пустой ролл V2 уже внутри; каппамаки — после 芯.
 */
export const HOSOMAKI_DIAMETER_MM = Object.freeze({ min: 28, max: 32 });

/**
 * Снимок огурца F02 в мм.
 * После 板ずり + продольный рез + 種取り это палка, не сектор плода.
 * 築地 / norecipes: ~8 мм, семенное гнездо срезано; 鉄火 7–8 мм 角 — тот же калибр.
 * Live catalog.js (14 × 9,9, сектор) не трогаем.
 */
export const CUCUMBER = Object.freeze({
  materialId: 'cucumber',
  widthMm: 8,
  heightMm: 8,
  lengthFactor: 1,
  cut: 'брусок',
  wU: 8 / U_MM,
  hU: 8 / U_MM,
});

/**
 * 細切り: 2–4 мм (kitchen-practice). Один патч — пучок, не шесть overlapping
 * cucumber (F07 same-material overlap = invalid). 3×2 × 3 мм + зазор 0,4.
 */
export const HOSOGIRI = Object.freeze({
  materialId: 'cucumber',
  cut: 'hosogiri',
  stickMm: 3,
  cols: 3,
  rows: 2,
  gapMm: 0.4,
  lengthFactor: 1,
});

export function hosogiriBox(spec = HOSOGIRI) {
  const { stickMm, cols, rows, gapMm } = spec;
  return {
    widthMm: cols * stickMm + (cols - 1) * gapMm,
    heightMm: rows * stickMm + (rows - 1) * gapMm,
    stickCount: cols * rows,
    stickMm,
  };
}

export function hosogiriSticks(originX = 0, spec = HOSOGIRI) {
  const { stickMm, cols, rows, gapMm } = spec;
  const box = hosogiriBox(spec);
  const x0 = originX - box.widthMm / 2;
  const y0 = -box.heightMm / 2;
  const sticks = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      sticks.push({
        x: x0 + c * (stickMm + gapMm),
        y: y0 + r * (stickMm + gapMm),
        s: stickMm,
      });
    }
  }
  return sticks;
}

/**
 * F03: шаг 1 мм через границу следа. erratum-004 фиксировал 43.5–47.5 под огурец
 * 14 мм; серия следует из farEdge − width/2, иначе тонкий 芯 зеленеет за старой
 * границей, хотя окно L/2 не двигалось.
 */
export const F03_U_MM = Object.freeze((() => {
  const far = HOSOMAKI.lengthMm / 2;
  const lastValid = Math.floor((far - CUCUMBER.widthMm / 2) * 2) / 2;
  return [lastValid - 2, lastValid - 1, lastValid, lastValid + 1, lastValid + 2];
})());

export function placementWindowMm(sheet) {
  return {
    nearEdgeMm: PLACEMENT_EDGE_MARGIN_MM,
    farEdgeMm: sheet.lengthMm / 2,
  };
}

/** u куска, чтобы след остался в окне раскладки. */
export function clampPatchU(sheet, patch, uMm) {
  const win = placementWindowMm(sheet);
  const half = patch.widthMm / 2;
  return Math.min(win.farEdgeMm - half, Math.max(win.nearEdgeMm + half, uMm));
}

/**
 * Снимок тамаго. catalog.js:306. Брусок.
 */
export const TAMAGO = Object.freeze({
  materialId: 'tamago',
  widthMm: 12,
  heightMm: 10,
  lengthFactor: 1,
  cut: 'брусок',
  wU: 2.4,
  hU: 2.0,
});

/**
 * Снимок лосося. catalog.js:296. Брусок 10×10.
 */
export const SALMON = Object.freeze({
  materialId: 'salmon',
  widthMm: 10,
  heightMm: 10,
  lengthFactor: 1,
  cut: 'брусок',
  wU: 2.0,
  hU: 2.0,
});

/**
 * Снимок футомаки. catalog.js BASES.futo, × U_MM один раз.
 * spreadEnd = 0.89 (назначение, #109). T = 1.57 из 200 г шари, не паспорт SUZUMO.
 */
export const FUTOMAKI = Object.freeze({
  catalogKey: 'futo',
  baseId: 'futomaki',
  lengthMm: 210,
  widthMm: 190,
  riceThicknessMm: 7.85,
  noriThicknessMm: 0.1,
  spreadStart: SPREAD_START,
  spreadEnd: 0.89,
  wrapMaterialId: 'nori',
  riceProfileId: 'standard',
  emptyCoreWidthMm: 5,
  emptyCoreHeightMm: 8.05,
  pieces: 8,              // catalog.js BASES.futo; AUTEC 8 на 180–190 мм
});

export function baseOf(recipe) {
  return recipe?.baseId === FUTOMAKI.baseId ? FUTOMAKI : HOSOMAKI;
}

/**
 * Ядро: твёрдые палки не проходят друг сквозь друга.
 * Порядок по u (меньший u — левее, 芯). Зазор 1 мм.
 * Лист может перекрываться (F07 разные вещества); срез пакует встык.
 */
export const CORE_PACK_GAP_MM = 1;
export const CORE_PACK_ROW_MM = 24;

function packCoreRows(patches) {
  const sorted = [...patches].sort((a, b) => a.uMm - b.uMm || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  const gap = CORE_PACK_GAP_MM;
  const rows = [];
  let row = [];
  let rowW = 0;
  for (const p of sorted) {
    const add = p.widthMm + (row.length ? gap : 0);
    if (row.length && rowW + add > CORE_PACK_ROW_MM) {
      rows.push(row);
      row = [];
      rowW = 0;
    }
    row.push(p);
    rowW += p.widthMm + (row.length > 1 ? gap : 0);
  }
  if (row.length) rows.push(row);

  const placed = [];
  let y = 0;
  for (const items of rows) {
    const rowH = Math.max(...items.map((p) => p.heightMm));
    const width = items.reduce((s, p, i) => s + p.widthMm + (i ? gap : 0), 0);
    let x = -width / 2;
    for (const p of items) {
      placed.push({ id: p.id, x: x + p.widthMm / 2, y: y + rowH / 2 });
      x += p.widthMm + gap;
    }
    y += rowH + gap;
  }
  const midY = placed.length ? (y - gap) / 2 : 0;
  const out = new Map();
  for (const p of placed) out.set(p.id, { x: p.x, y: p.y - midY });
  return out;
}

/** Зазор AABB соседних рядов. Ловит rowH×k: короб растёт, начинки расходятся. */
export function packRowGapMm(recipe) {
  const items = recipe.patches.map((p) => {
    const { x, y } = patchCorePos(recipe, p);
    return { y0: y - p.heightMm / 2, y1: y + p.heightMm / 2, y };
  });
  if (items.length < 2) return [];
  const rows = [];
  for (const p of [...items].sort((a, b) => a.y - b.y)) {
    const row = rows.find((r) => Math.abs(r.y - p.y) < 0.5);
    if (row) {
      row.items.push(p);
      row.y = row.items.reduce((s, q) => s + q.y, 0) / row.items.length;
    } else rows.push({ y: p.y, items: [p] });
  }
  const gaps = [];
  for (let i = 0; i < rows.length - 1; i++) {
    const hi = Math.max(...rows[i].items.map((p) => p.y1));
    const lo = Math.min(...rows[i + 1].items.map((p) => p.y0));
    gaps.push(lo - hi);
  }
  return gaps;
}

/** Положение патча в ядре. Один патч — начало координат. Несколько — упаковка без пересечения. */
export function patchCorePos(recipe, patch) {
  const list = recipe.patches;
  if (!list || list.length <= 1) return { x: 0, y: 0 };
  return packCoreRows(list).get(patch.id) || { x: 0, y: 0 };
}

export function patchCoreXmm(recipe, patch) {
  return patchCorePos(recipe, patch).x;
}

export function riceSpanMm(sheetLengthMm, spreadStart = SPREAD_START, spreadEnd = HOSOMAKI.spreadEnd) {
  const sRice0 = spreadStart * sheetLengthMm;
  const sRice1 = spreadEnd * sheetLengthMm;
  return { sRice0, sRice1, Lrice: sRice1 - sRice0 };
}
