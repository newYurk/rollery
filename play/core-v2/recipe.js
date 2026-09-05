// RecipeV2 constructors for F01/F02. Errata 002, 004, 008, 015, 018.
// F02 vMm / placement: F07 cites «как в F02» — vMm = sheet.widthMm/2, placement: 'embedded'.
// Зафиксировано здесь, не в fixtures.md (minor Слоя 6).

import {
  WINDING,
  CUCUMBER,
  FUTOMAKI,
  HOSOMAKI,
  HOSOGIRI,
  SALMON,
  SECTOR_ANGLE,
  TAMAGO,
  U_MM,
  hosogiriBox,
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
  if (CUCUMBER.cut === 'сектор') {
    return CUCUMBER.wU * CUCUMBER.hU * cutFillSector() * U_MM * U_MM;
  }
  return CUCUMBER.widthMm * CUCUMBER.heightMm;
}

export function catalogAreaMm2(patch) {
  if (patch.cut === 'hosogiri') {
    const n = patch.stickCount;
    const s = patch.stickMm;
    return n * s * s;
  }
  if (patch.cut === 'сектор') {
    return patch.widthMm * patch.heightMm * cutFillSector();
  }
  return patch.widthMm * patch.heightMm;
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
    winding: WINDING.ring,
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
    winding: WINDING.ring,
    patches: [
      {
        id: 'cucumber-0',
        materialId: CUCUMBER.materialId,
        cut: CUCUMBER.cut,
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

/** Каппамаки 細切り: пучок тонких палок, один патч. */
export function makeHosogiriRecipe(uMm) {
  const sheet = { lengthMm: HOSOMAKI.lengthMm, widthMm: HOSOMAKI.widthMm };
  const box = hosogiriBox();
  const u = uMm ?? (placementWindowMm(sheet).nearEdgeMm + placementWindowMm(sheet).farEdgeMm) / 2;
  return deepFreeze({
    version: 2,
    baseId: HOSOMAKI.baseId,
    sheet,
    wrap: { materialId: HOSOMAKI.wrapMaterialId },
    rice: { profileId: HOSOMAKI.riceProfileId },
    windDirection: 'fromUZero',
    winding: WINDING.ring,
    patches: [
      {
        id: 'cucumber-hogi-0',
        materialId: HOSOGIRI.materialId,
        cut: HOSOGIRI.cut,
        uMm: u,
        vMm: sheet.widthMm / 2,
        widthMm: box.widthMm,
        heightMm: box.heightMm,
        lengthMm: sheet.widthMm * HOSOGIRI.lengthFactor,
        stickMm: box.stickMm,
        stickCount: box.stickCount,
        placement: 'embedded',
      },
    ],
    hand: { mode: 'neutral', seed: 0 },
  });
}

/** Три палки в окне хосомаки — лист короче кольца нори. */
export function makeCrowdedHosoRecipe() {
  const sheet = { lengthMm: HOSOMAKI.lengthMm, widthMm: HOSOMAKI.widthMm };
  const patch = (id, spec, uMm) => ({
    id,
    materialId: spec.materialId,
    cut: spec.cut,
    uMm,
    vMm: sheet.widthMm / 2,
    widthMm: spec.widthMm,
    lengthMm: sheet.widthMm * spec.lengthFactor,
    heightMm: spec.heightMm,
    placement: 'embedded',
  });
  return deepFreeze({
    version: 2,
    baseId: HOSOMAKI.baseId,
    sheet,
    wrap: { materialId: HOSOMAKI.wrapMaterialId },
    rice: { profileId: HOSOMAKI.riceProfileId },
    windDirection: 'fromUZero',
    winding: WINDING.ring,
    patches: [
      patch('cucumber-0', CUCUMBER, 25),
      patch('tamago-0', TAMAGO, 35),
      patch('salmon-0', SALMON, 46),
    ],
    hand: { mode: 'neutral', seed: 0 },
  });
}

/** F04a: след выходит за лист. u = L − width/2 + 2, чтобы короткий 芯 не остался на листе. */
export function makeF04aRecipe() {
  const L = HOSOMAKI.lengthMm;
  return makeCucumberRecipe(L - CUCUMBER.widthMm / 2 + 2);
}

/** F04b: на листе, за farEdge (L/2). */
export function makeF04bRecipe() {
  return makeCucumberRecipe(70);
}

function futoSheet() {
  return { lengthMm: FUTOMAKI.lengthMm, widthMm: FUTOMAKI.widthMm };
}

function futoPatch(id, spec, uMm) {
  const sheet = futoSheet();
  return {
    id,
    materialId: spec.materialId,
    cut: spec.cut,
    uMm,
    vMm: sheet.widthMm / 2,
    widthMm: spec.widthMm,
    lengthMm: sheet.widthMm * spec.lengthFactor,
    heightMm: spec.heightMm,
    placement: 'embedded',
  };
}

function freezeFuto(patches) {
  return deepFreeze({
    version: 2,
    baseId: FUTOMAKI.baseId,
    sheet: futoSheet(),
    wrap: { materialId: FUTOMAKI.wrapMaterialId },
    rice: { profileId: FUTOMAKI.riceProfileId },
    windDirection: 'fromUZero',
    winding: WINDING.ring,
    patches,
    hand: { mode: 'neutral', seed: 0 },
  });
}

/** F05: три непересекающихся патча внутри окна футомаки [20, 105]. */
export function makeF05Recipe(order = ['cucumber', 'tamago', 'salmon']) {
  const byId = {
    cucumber: futoPatch('cucumber-0', CUCUMBER, 35),
    tamago: futoPatch('tamago-0', TAMAGO, 55),
    salmon: futoPatch('salmon-0', SALMON, 80),
  };
  return freezeFuto(order.map((k) => byId[k]));
}

export function makeF07Recipe(probeUMm, orderCucumberFirst = true, swap = false) {
  const cuU = swap ? 56 : 60;
  const prU = swap ? 60 : probeUMm;
  const cucumber = futoPatch('cucumber-0', CUCUMBER, cuU);
  const probe = futoPatch('tamago-0', TAMAGO, prU);
  return freezeFuto(orderCucumberFirst ? [cucumber, probe] : [probe, cucumber]);
}

export function makeF07SameMaterialOverlap() {
  return freezeFuto([
    futoPatch('cucumber-0', CUCUMBER, 60),
    futoPatch('cucumber-1', CUCUMBER, 60),
  ]);
}

export { placementWindowMm, TAMAGO, SALMON, FUTOMAKI };
