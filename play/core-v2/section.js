// Central slice. Fillings sit in the core (rest-state area). Hard fillings do not stretch.

import { SECTOR_ANGLE, patchCorePos } from './units.js';
import { catalogAreaMm2, cutFillSector } from './recipe.js';

export function sectorTop(t) {
  const c = Math.cos(SECTOR_ANGLE);
  const sn = Math.sin(SECTOR_ANGLE);
  return t <= c ? t / c : Math.sqrt(Math.max(0, 1 - t * t)) / sn;
}

// Сектор берёт ПОЛНОЕ начало координат, а не один originX: в пучке из
// нескольких рядов у куска есть и смещение по y. Раньше сюда приходил только x,
// а centerYmm возвращался нулём — и отчёт расходился с картинкой, потому что
// render.js рисует по patchCorePos. Фикстуры этого не ловили: сектор в них
// только один и ровно в начале координат.
function sampleSector(patch, origin) {
  const N = 320;
  const widthMm = patch.widthMm;
  const heightMm = patch.heightMm;
  const cell = (widthMm / N) * (heightMm / N);
  let area = 0;
  for (let i = 0; i < N; i++) {
    const lu = -0.5 + (i + 0.5) / N;
    const t = lu + 0.5;
    const top = sectorTop(t);
    for (let j = 0; j < N; j++) {
      const hn = (j + 0.5) / N;
      if (hn > top) continue;
      area += cell;
    }
  }
  const catalog = catalogAreaMm2(patch);
  const out = { id: patch.id, areaMm2: catalog, centerXmm: origin.x, centerYmm: origin.y };
  if (area > 0) out._gridAreaMm2 = area;
  return out;
}

function sampleBar(patch, origin) {
  return {
    id: patch.id,
    areaMm2: catalogAreaMm2(patch),
    centerXmm: origin.x,
    centerYmm: origin.y,
  };
}

export function samplePatch(recipe, patch) {
  const origin = patchCorePos(recipe, patch);
  if (patch.cut === 'hosogiri') return sampleBar(patch, origin);
  if (patch.cut === 'сектор') return sampleSector(patch, origin);
  return sampleBar(patch, origin);
}

export function sampleSection(recipe, winding, vSliceMm) {
  const layers = {
    rice: { innerMm: winding.r0b, outerMm: winding.rp },
    nori: { innerMm: winding.rp, outerMm: winding.rn },
  };
  const visiblePatches = recipe.patches.map((p) => samplePatch(recipe, p))
    .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
  return {
    vSliceMm,
    layers,
    visiblePatches,
    angleRad: winding.angleRad,
    riceAreaMm2: riceAnnulusAreaMm2(winding),
    coreGapAreaMm2: coreGapAreaMm2(winding),
  };
}

/**
 * Площадь рисового кольца сеткой 320²: клетка считается рисом, если лежит
 * ЗА границей ядра r0(φ) и внутри rp. Сетка независима от алгебры
 * riceOuterFromAreaMm — она проверяет тождество π·rp² = ядро + T·Lrice,
 * измеряя, а не пересчитывая по той же формуле.
 */
export function riceAnnulusAreaMm2(winding, n = 320) {
  const rp = winding.rp[0];
  const r0b = winding.r0b;
  const half = rp;
  const cell = (2 * half / n) ** 2;
  const NBW = r0b.length;
  let area = 0;
  for (let i = 0; i < n; i++) {
    const x = -half + (i + 0.5) * (2 * half / n);
    for (let j = 0; j < n; j++) {
      const y = -half + (j + 0.5) * (2 * half / n);
      const r = Math.hypot(x, y);
      if (r >= rp || r <= 0) continue;
      const phi = Math.atan2(y, x);
      const b = ((Math.round(phi / (Math.PI * 2) * NBW) % NBW) + NBW) % NBW;
      if (r > r0b[b]) area += cell;
    }
  }
  return area;
}

/**
 * Зазоры между начинками, которые кольцевая модель НЕ умеет назвать рисом.
 * Луч, прошедший между двумя кусками, выходит из дальнего, поэтому всё, что
 * между ними, попадает внутрь r0(φ) и считается ядром. У повара там рис.
 * Это предел представления «одна граница на луч», а не ошибка счёта, —
 * поэтому величина измеряется и печатается, а не прячется (#186, см. #10).
 */
export function coreGapAreaMm2(winding, n = 320) {
  const rp = winding.rp[0];
  const boxes = winding.coreBoxes;
  const r0b = winding.r0b;
  const half = rp;
  const cell = (2 * half / n) ** 2;
  const NBW = r0b.length;
  let gap = 0;
  for (let i = 0; i < n; i++) {
    const x = -half + (i + 0.5) * (2 * half / n);
    for (let j = 0; j < n; j++) {
      const y = -half + (j + 0.5) * (2 * half / n);
      const r = Math.hypot(x, y);
      if (r >= rp || r <= 0) continue;
      const phi = Math.atan2(y, x);
      const b = ((Math.round(phi / (Math.PI * 2) * NBW) % NBW) + NBW) % NBW;
      if (r > r0b[b]) continue; // это рис, не зазор
      let inBox = false;
      for (const bx of boxes) {
        if (Math.abs(x - bx.cx) <= bx.hw && Math.abs(y - bx.cy) <= bx.hh) { inBox = true; break; }
      }
      if (!inBox) gap += cell;
    }
  }
  return gap;
}

export function sectionForHash(section) {
  return {
    vSliceMm: section.vSliceMm,
    visiblePatches: section.visiblePatches.map((p) => ({
      id: p.id,
      areaMm2: p.areaMm2,
      centerXmm: p.centerXmm,
      centerYmm: p.centerYmm,
    })),
    riceInnerMm: section.layers.rice.innerMm,
    riceOuterMm: section.layers.rice.outerMm,
    noriInnerMm: section.layers.nori.innerMm,
    noriOuterMm: section.layers.nori.outerMm,
  };
}
