// Debug slice. Presentation only — does not feed hashes or acceptance.
// Colors from catalog.js (hoso wrapper / spread / ING), not from geometry.js.

import { DPHI, NB, TAU, patchCoreXmm, placementWindowMm } from './units.js';
import { sectorTop } from './section.js';

export const MAT = {
  cucumber: { fill: '#79b55c', skin: '#3f6b38' },
  tamago: { fill: '#f3c94f', edge: '#c4922a' },
  salmon: { fill: '#ef8a66', edge: '#c45a3a' },
  rice: '#e4ded6',
  nori: '#22342b',
  hollow: '#1a1814',
};

function binAt(phi) {
  let b = Math.round(((phi % TAU) + TAU) % TAU / DPHI) % NB;
  return b;
}

function ringPath(ctx, inner, outer, n = 360) {
  ctx.beginPath();
  for (let i = 0; i <= n; i++) {
    const phi = (i / n) * TAU;
    const r = outer[binAt(phi)];
    if (i === 0) ctx.moveTo(r * Math.cos(phi), r * Math.sin(phi));
    else ctx.lineTo(r * Math.cos(phi), r * Math.sin(phi));
  }
  for (let i = n; i >= 0; i--) {
    const phi = (i / n) * TAU;
    const r = inner[binAt(phi)];
    ctx.lineTo(r * Math.cos(phi), r * Math.sin(phi));
  }
  ctx.closePath();
}

function cucumberPath(ctx, patch, ox) {
  const w = patch.widthMm;
  const h = patch.heightMm;
  ctx.beginPath();
  const steps = 48;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    const x = ox + (t - 0.5) * w;
    const y = -h / 2 + sectorTop(t) * h;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.lineTo(ox + w / 2, -h / 2);
  ctx.lineTo(ox - w / 2, -h / 2);
  ctx.closePath();
}

function barPath(ctx, patch, ox) {
  const w = patch.widthMm;
  const h = patch.heightMm;
  const r = Math.min(1.2, w / 6, h / 6);
  const x0 = ox - w / 2;
  const y0 = -h / 2;
  ctx.beginPath();
  ctx.roundRect(x0, y0, w, h, r);
}

function seed(n) {
  let x = (n * 374761393 + 668265263) >>> 0;
  x = Math.imul(x ^ (x >>> 13), 1274126177);
  return ((x ^ (x >>> 16)) >>> 0) / 4294967296;
}

export function drawSlice(ctx, recipe, winding, css) {
  const W = css;
  const H = css;
  ctx.save();
  ctx.fillStyle = '#171713';
  ctx.fillRect(0, 0, W, H);

  const Rout = winding.Rout + winding.W;
  const scale = (css * 0.78) / (2 * Rout);
  ctx.translate(W / 2, H / 2);
  ctx.scale(scale, -scale);

  ctx.save();
  ctx.fillStyle = 'rgba(0,0,0,0.45)';
  ctx.beginPath();
  ctx.ellipse(0, -Rout * 0.08, Rout * 1.02, Rout * 0.22, 0, 0, TAU);
  ctx.fill();
  ctx.restore();

  ringPath(ctx, winding.r0b, winding.rp);
  ctx.fillStyle = MAT.rice;
  ctx.fill();

  ctx.save();
  ctx.clip();
  for (let i = 0; i < 90; i++) {
    const u = seed(i + 1);
    const v = seed(i + 17);
    const phi = u * TAU;
    const r0 = winding.r0b[binAt(phi)];
    const rp = winding.rp[binAt(phi)];
    const r = r0 + (rp - r0) * (0.12 + 0.76 * v);
    ctx.fillStyle = i % 3 === 0 ? '#d9d1c4' : '#efe8dc';
    ctx.beginPath();
    ctx.ellipse(r * Math.cos(phi), r * Math.sin(phi), 0.55, 0.32, phi, 0, TAU);
    ctx.fill();
  }
  ctx.restore();

  ringPath(ctx, winding.rp, winding.rn);
  ctx.fillStyle = MAT.nori;
  ctx.fill();

  if (winding.overlapBins > 0) {
    ctx.beginPath();
    const n = winding.overlapBins;
    for (let b = 0; b <= n; b++) {
      const phi = b * DPHI;
      const r = winding.rn[b] + winding.W;
      if (b === 0) ctx.moveTo(r * Math.cos(phi), r * Math.sin(phi));
      else ctx.lineTo(r * Math.cos(phi), r * Math.sin(phi));
    }
    for (let b = n; b >= 0; b--) {
      const phi = b * DPHI;
      const r = winding.rn[b];
      ctx.lineTo(r * Math.cos(phi), r * Math.sin(phi));
    }
    ctx.closePath();
    ctx.fillStyle = MAT.nori;
    ctx.fill();
  }

  ctx.beginPath();
  for (let i = 0; i <= 360; i++) {
    const phi = (i / 360) * TAU;
    const extra = binAt(phi) < winding.overlapBins ? winding.W : 0;
    const r = winding.rn[binAt(phi)] + extra;
    if (i === 0) ctx.moveTo(r * Math.cos(phi), r * Math.sin(phi));
    else ctx.lineTo(r * Math.cos(phi), r * Math.sin(phi));
  }
  ctx.closePath();
  ctx.strokeStyle = '#1a211c';
  ctx.lineWidth = Math.max(winding.W, 3.4 / scale);
  ctx.stroke();

  ctx.fillStyle = MAT.hollow;
  ctx.beginPath();
  for (let i = 0; i <= 360; i++) {
    const phi = (i / 360) * TAU;
    const r = winding.r0b[binAt(phi)];
    if (i === 0) ctx.moveTo(r * Math.cos(phi), r * Math.sin(phi));
    else ctx.lineTo(r * Math.cos(phi), r * Math.sin(phi));
  }
  ctx.closePath();
  ctx.fill();

  ctx.save();
  ctx.clip();
  for (const p of recipe.patches) {
    const ox = patchCoreXmm(recipe, p);
    const mat = MAT[p.materialId] || { fill: '#888', edge: '#444' };
    ctx.beginPath();
    if (p.materialId === 'cucumber') cucumberPath(ctx, p, ox);
    else barPath(ctx, p, ox);
    ctx.fillStyle = mat.fill;
    ctx.fill();
    ctx.strokeStyle = mat.skin || mat.edge;
    ctx.lineWidth = 0.45;
    ctx.stroke();
  }
  ctx.restore();

  ctx.restore();
}

export function drawSheet(ctx, recipe, winding, cssW, cssH) {
  const L = recipe.sheet.lengthMm;
  const pad = 18;
  const y0 = 28;
  const h = cssH - 44;
  const x0 = pad;
  const innerW = cssW - pad * 2;
  const uToX = (u) => x0 + (u / L) * innerW;

  ctx.fillStyle = '#171713';
  ctx.fillRect(0, 0, cssW, cssH);

  ctx.fillStyle = MAT.nori;
  ctx.fillRect(uToX(0), y0, innerW, h);

  ctx.fillStyle = MAT.rice;
  ctx.fillRect(uToX(winding.sRice0), y0 + 3, uToX(winding.sRice1) - uToX(winding.sRice0), h - 6);

  const win = placementWindowMm(recipe.sheet);
  ctx.fillStyle = 'rgba(224,178,95,0.16)';
  ctx.fillRect(uToX(win.nearEdgeMm), y0, uToX(win.farEdgeMm) - uToX(win.nearEdgeMm), h);

  ctx.strokeStyle = 'rgba(224,178,95,0.55)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(uToX(win.nearEdgeMm), y0);
  ctx.lineTo(uToX(win.nearEdgeMm), y0 + h);
  ctx.moveTo(uToX(win.farEdgeMm), y0);
  ctx.lineTo(uToX(win.farEdgeMm), y0 + h);
  ctx.stroke();

  for (const p of recipe.patches) {
    const mat = MAT[p.materialId] || { fill: '#888' };
    const half = p.widthMm / 2;
    ctx.fillStyle = mat.fill;
    ctx.fillRect(uToX(p.uMm - half), y0 + 8, uToX(p.uMm + half) - uToX(p.uMm - half), h - 16);
  }

  ctx.fillStyle = '#9a9280';
  ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, monospace';
  ctx.fillText('0', uToX(0), cssH - 6);
  ctx.fillText(`${L}`, uToX(L) - 18, cssH - 6);
  ctx.fillText('окно', uToX((win.nearEdgeMm + win.farEdgeMm) / 2) - 12, 16);
}
