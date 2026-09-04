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

/** Серия F03, шаг 1 мм через границу следа (erratum-004). */
export const F03_U_MM = Object.freeze([43.5, 44.5, 45.5, 46.5, 47.5]);

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
});

/**
 * Снимок огурца F02 в мм. catalog.js:305.
 * catalogAreaMm2 считается cutFill в recipe.js, не здесь: формула зависит от профиля.
 */
export const CUCUMBER = Object.freeze({
  materialId: 'cucumber',
  widthMm: 14,            // 2.8 × 5
  heightMm: 9.9,          // 1.98 × 5
  lengthFactor: 1,        // dv: на всю ширину ролла
  cut: 'сектор',
  wU: 2.8,
  hU: 1.98,
});

export function placementWindowMm(sheet) {
  return {
    nearEdgeMm: PLACEMENT_EDGE_MARGIN_MM,
    farEdgeMm: sheet.lengthMm / 2,
  };
}

export function riceSpanMm(sheetLengthMm, spreadStart = SPREAD_START, spreadEnd = HOSOMAKI.spreadEnd) {
  const sRice0 = spreadStart * sheetLengthMm;
  const sRice1 = spreadEnd * sheetLengthMm;
  return { sRice0, sRice1, Lrice: sRice1 - sRice0 };
}
