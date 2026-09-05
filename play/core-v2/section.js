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
  };
}

/** Cartesian 320² of the rice ring r0(φ) < r < rp. Independent of riceOuterMm's algebra. */
export function riceAnnulusAreaMm2(winding, n = 320) {
  const rp = winding.rp[0];
  const Wc = winding.Wc;
  const Hc = winding.Hc;
  const half = rp;
  const cell = (2 * half / n) ** 2;
  let area = 0;
  for (let i = 0; i < n; i++) {
    const x = -half + (i + 0.5) * (2 * half / n);
    for (let j = 0; j < n; j++) {
      const y = -half + (j + 0.5) * (2 * half / n);
      const r = Math.hypot(x, y);
      if (r >= rp || r <= 0) continue;
      const phi = Math.atan2(y, x);
      const c = Math.abs(Math.cos(phi));
      const s = Math.abs(Math.sin(phi));
      const rx = c > 1e-12 ? (Wc / 2) / c : Infinity;
      const ry = s > 1e-12 ? (Hc / 2) / s : Infinity;
      if (r > Math.min(rx, ry)) area += cell;
    }
  }
  return area;
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
