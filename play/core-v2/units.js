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
 * Было: catalog.js:305, плод ⌀28 мм / 8 долей → 14 × 9,9. Это магазинный
 * огурец, не 芯 хосомаки. 白ごはん.com: 6–8 долей, 「細めに」; 鉄火 7–8 мм 角.
 * Сектор 45° лежит на одном срезе: короткая сторона = 8 мм (= верх 鉄火),
 * длинная = 8√2 ≈ 11,3 мм. Live catalog.js не трогаем.
 * catalogAreaMm2 считается cutFill в recipe.js, не здесь.
 */
export const CUCUMBER = Object.freeze({
  materialId: 'cucumber',
  widthMm: 11.3,          // 8√2, округление как у старых 9,9
  heightMm: 8,            // короткая сторона = 鉄火 7–8 мм
  lengthFactor: 1,        // dv: на всю ширину ролла
  cut: 'сектор',
  wU: 11.3 / U_MM,
  hU: 8 / U_MM,
});

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
 * Половина ядра, на которую отображается placement window.
 * k=1 копировал зазоры листа в срез: F05 давал щель 69 мм («распидорасило»).
 * Подворот собирает окно в пучок; масштаб — свойство окна, не соседей (erratum-007).
 */
export const WINDOW_CORE_HALF_MM = 10;

/** Положение патча в ядре. Один патч — начало координат (F01–F04).
 *  Несколько — чистая функция собственного uMm, без переупаковки соседями. */
export function patchCoreXmm(recipe, patch) {
  if (!recipe.patches || recipe.patches.length <= 1) return 0;
  const w = placementWindowMm(recipe.sheet);
  const mid = (w.nearEdgeMm + w.farEdgeMm) / 2;
  const half = (w.farEdgeMm - w.nearEdgeMm) / 2;
  return (patch.uMm - mid) * (WINDOW_CORE_HALF_MM / half);
}

export function riceSpanMm(sheetLengthMm, spreadStart = SPREAD_START, spreadEnd = HOSOMAKI.spreadEnd) {
  const sRice0 = spreadStart * sheetLengthMm;
  const sRice1 = spreadEnd * sheetLengthMm;
  return { sRice0, sRice1, Lrice: sRice1 - sRice0 };
}
