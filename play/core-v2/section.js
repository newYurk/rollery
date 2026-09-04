// Central slice. Fillings sit in the core (rest-state area). Hard fillings do not stretch.

import { SECTOR_ANGLE, patchCoreXmm } from './units.js';
import { catalogAreaMm2, cutFillSector } from './recipe.js';

function sectorTop(t) {
  const c = Math.cos(SECTOR_ANGLE);
  const sn = Math.sin(SECTOR_ANGLE);
  return t <= c ? t / c : Math.sqrt(Math.max(0, 1 - t * t)) / sn;
}

function sampleSector(patch, originX) {
  const N = 320;
  const widthMm = patch.widthMm;
  const heightMm = patch.heightMm;
  const cell = (widthMm / N) * (heightMm / N);
  let area = 0;
  let sx = 0;
  let sy = 0;
  for (let i = 0; i < N; i++) {
    const lu = -0.5 + (i + 0.5) / N;
    const t = lu + 0.5;
    const top = sectorTop(t);
    const x = originX + lu * widthMm;
    for (let j = 0; j < N; j++) {
      const hn = (j + 0.5) / N;
      if (hn > top) continue;
      const y = hn * heightMm - heightMm / 2;
      area += cell;
      sx += x * cell;
      sy += y * cell;
    }
  }
  const catalog = catalogAreaMm2(patch);
  if (area <= 0) return { id: patch.id, areaMm2: catalog, centerXmm: originX, centerYmm: 0 };
  return { id: patch.id, areaMm2: catalog, centerXmm: originX, centerYmm: 0, _gridAreaMm2: area };
}

function sampleBar(patch, originX) {
  return {
    id: patch.id,
    areaMm2: catalogAreaMm2(patch),
    centerXmm: originX,
    centerYmm: 0,
  };
}

export function samplePatch(recipe, patch) {
  const originX = patchCoreXmm(recipe, patch);
  if (patch.materialId === 'cucumber') return sampleSector(patch, originX);
  return sampleBar(patch, originX);
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
  };
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
