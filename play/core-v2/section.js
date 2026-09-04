// Central slice. F01: rice+nori rings, no filling. F02: cucumber sector in the core box.
// Area is the rest-state sector in core coordinates — the filling sits in the core,
// not in the winding wall, so #134 (stretch vs slip on the sheet) does not apply.

import { SECTOR_ANGLE } from './units.js';
import { cutFillSector } from './recipe.js';

function sectorTop(t) {
  const c = Math.cos(SECTOR_ANGLE);
  const sn = Math.sin(SECTOR_ANGLE);
  return t <= c ? t / c : Math.sqrt(Math.max(0, 1 - t * t)) / sn;
}

/** Grid integral of the cucumber sector, centered in the core box / roll frame. */
export function sampleCucumberSector(patch, winding) {
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
    const x = lu * widthMm;
    for (let j = 0; j < N; j++) {
      const hn = (j + 0.5) / N;
      if (hn > top) continue;
      const y = hn * heightMm - heightMm / 2;
      area += cell;
      sx += x * cell;
      sy += y * cell;
    }
  }
  const fill = cutFillSector();
  const catalog = widthMm * heightMm * fill;
  // Prefer the closed catalog area for the visible patch; grid is for the centroid.
  // Ratio grid/catalog is a sanity check that the profile matches cutFill.
  if (area <= 0) {
    return { id: patch.id, areaMm2: catalog, centerXmm: 0, centerYmm: 0 };
  }
  return {
    id: patch.id,
    areaMm2: catalog,
    centerXmm: sx / area,
    centerYmm: sy / area,
    _gridAreaMm2: area,
    coreWc: winding.Wc,
    coreHc: winding.Hc,
  };
}

export function sampleSection(recipe, winding, vSliceMm) {
  const layers = {
    rice: { innerMm: winding.r0b, outerMm: winding.rp },
    nori: { innerMm: winding.rp, outerMm: winding.rn },
  };
  const visiblePatches = recipe.patches.map((p) => sampleCucumberSector(p, winding));
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
