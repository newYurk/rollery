// RecipeV2 constructors for F01/F02. Errata 002, 004, 008, 015, 018.
// F02 vMm / placement: F07 cites «как в F02» — vMm = sheet.widthMm/2, placement: 'embedded'.
// Зафиксировано здесь, не в fixtures.md (minor Слоя 6).

import {
  CUCUMBER,
  HOSOMAKI,
  SECTOR_ANGLE,
  U_MM,
  placementWindowMm,
} from './units.js';

export function deepFreeze(value) {
  if (value === null || typeof value !== 'object') return value;
  if (Object.isFrozen(value)) return value;
  if (ArrayBuffer.isView(value)) return value;
  for (const key of Object.keys(value)) deepFreeze(value[key]);
  return Object.freeze(value);
}

export function deepClone(value) {
  return structuredClone(value);
}

/** cutFill(d) для сектора — та же квадратура, что geometry.js:570-579, без импорта. */
export function cutFillSector() {
  const N = 512;
  const c = Math.cos(SECTOR_ANGLE);
  const sn = Math.sin(SECTOR_ANGLE);
  let s = 0;
  for (let i = 0; i < N; i++) {
    const lu = -0.5 + (i + 0.5) / N;
    const a = Math.min(1, Math.max(-1, lu * 2));
    const t = (a + 1) / 2;
    const top = t <= c ? t / c : Math.sqrt(Math.max(0, 1 - t * t)) / sn;
    s += Math.max(0, top);
  }
  return s / N;
}

export function cucumberCatalogAreaMm2() {
  return CUCUMBER.wU * CUCUMBER.hU * cutFillSector() * U_MM * U_MM;
}

export function makeF01Recipe() {
  const sheet = { lengthMm: HOSOMAKI.lengthMm, widthMm: HOSOMAKI.widthMm };
  return deepFreeze({
    version: 2,
    baseId: HOSOMAKI.baseId,
    sheet,
    wrap: { materialId: HOSOMAKI.wrapMaterialId },
    rice: { profileId: HOSOMAKI.riceProfileId },
    windDirection: 'fromUZero',
    patches: [],
    hand: { mode: 'neutral', seed: 0 },
  });
}

export function makeCucumberRecipe(uMm) {
  const sheet = { lengthMm: HOSOMAKI.lengthMm, widthMm: HOSOMAKI.widthMm };
  return deepFreeze({
    version: 2,
    baseId: HOSOMAKI.baseId,
    sheet,
    wrap: { materialId: HOSOMAKI.wrapMaterialId },
    rice: { profileId: HOSOMAKI.riceProfileId },
    windDirection: 'fromUZero',
    patches: [
      {
        id: 'cucumber-0',
        materialId: CUCUMBER.materialId,
        uMm,
        vMm: sheet.widthMm / 2,
        widthMm: CUCUMBER.widthMm,
        lengthMm: sheet.widthMm * CUCUMBER.lengthFactor,
        heightMm: CUCUMBER.heightMm,
        placement: 'embedded',
      },
    ],
    hand: { mode: 'neutral', seed: 0 },
  });
}

export function makeF02Recipe() {
  const window = placementWindowMm({ lengthMm: HOSOMAKI.lengthMm });
  return makeCucumberRecipe((window.nearEdgeMm + window.farEdgeMm) / 2);
}

/** F04a: след [93, 107] на листе 105 мм. */
export function makeF04aRecipe() {
  return makeCucumberRecipe(100);
}

/** F04b: след [63, 77] на листе, вне окна [20, 52.5]. */
export function makeF04bRecipe() {
  return makeCucumberRecipe(70);
}

export { placementWindowMm };
