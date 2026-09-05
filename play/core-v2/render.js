// Debug slice. Presentation only — does not feed hashes or acceptance.
// Colors from catalog.js (hoso wrapper / spread / ING), not from geometry.js.

import { DPHI, HOSOGIRI, NB, TAU, hosogiriSticks, patchCorePos, placementWindowMm } from './units.js';
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

function hosogiriPath(ctx, patch, ox) {
  const spec = {
    stickMm: patch.stickMm ?? HOSOGIRI.stickMm,
    cols: HOSOGIRI.cols,
    rows: HOSOGIRI.rows,
    gapMm: HOSOGIRI.gapMm,
  };
  const sticks = hosogiriSticks(ox, spec);
  ctx.beginPath();
  for (const st of sticks) {
    const r = Math.min(0.45, st.s / 6);
    ctx.roundRect(st.x, st.y, st.s, st.s, r);
  }
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

function r0Path(ctx, winding) {
  ctx.beginPath();
  for (let i = 0; i <= 360; i++) {
    const phi = (i / 360) * TAU;
    const r = winding.r0b[binAt(phi)];
    if (i === 0) ctx.moveTo(r * Math.cos(phi), r * Math.sin(phi));
    else ctx.lineTo(r * Math.cos(phi), r * Math.sin(phi));
  }
  ctx.closePath();
}

function riceGrains(ctx, winding, inner, outer, n) {
  for (let i = 0; i < n; i++) {
    const u = seed(i + 1);
    const v = seed(i + 17);
    const phi = u * TAU;
    const r0 = inner[binAt(phi)];
    const r1 = outer[binAt(phi)];
    const r = r0 + (r1 - r0) * (0.12 + 0.76 * v);
    ctx.fillStyle = i % 3 === 0 ? '#d9d1c4' : '#efe8dc';
    ctx.beginPath();
    ctx.ellipse(r * Math.cos(phi), r * Math.sin(phi), 0.55, 0.32, phi, 0, TAU);
    ctx.fill();
  }
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

  const packed = recipe.patches.length > 0;
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

  ctx.beginPath();
  ctx.arc(0, 0, winding.rp[0], 0, TAU);
  ctx.fillStyle = MAT.rice;
  ctx.fill();

  if (winding.riceSteps > NB) {
    ctx.fillStyle = '#d8d0c6';
    ctx.beginPath();
    for (let i = NB; i < winding.riceSteps; i++) {
      const phi0 = i * DPHI;
      const phi1 = (i + 1) * DPHI;
      const j = Math.min(i + 1, winding.riceSteps - 1);
      const a0 = winding.riceRin[i];
      const a1 = winding.riceRout[i];
      const b0 = winding.riceRin[j];
      const b1 = winding.riceRout[j];
      ctx.moveTo(a0 * Math.cos(phi0), a0 * Math.sin(phi0));
      ctx.lineTo(a1 * Math.cos(phi0), a1 * Math.sin(phi0));
      ctx.lineTo(b1 * Math.cos(phi1), b1 * Math.sin(phi1));
      ctx.lineTo(b0 * Math.cos(phi1), b0 * Math.sin(phi1));
      ctx.closePath();
    }
    ctx.fill();
  }

  ctx.save();
  ctx.beginPath();
  ctx.arc(0, 0, winding.rp[0], 0, TAU);
  ctx.clip();
  riceGrains(ctx, winding, winding.r0b, winding.rp, packed ? 110 : 90);
  ctx.restore();

  ctx.save();
  ctx.strokeStyle = 'rgba(90, 82, 70, 0.45)';
  ctx.lineWidth = Math.max(0.35, 1.1 / scale);
  ctx.lineCap = 'round';
  ctx.beginPath();
  for (let i = 0; i < winding.riceSteps; i++) {
    const phi = i * DPHI;
    const r = winding.riceRin[i];
    const x = r * Math.cos(phi);
    const y = r * Math.sin(phi);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  const last = winding.riceSteps - 1;
  const phiEnd = last * DPHI;
  ctx.lineTo(winding.riceRout[last] * Math.cos(phiEnd), winding.riceRout[last] * Math.sin(phiEnd));
  ctx.stroke();
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

  if (!packed) {
    r0Path(ctx, winding);
    ctx.fillStyle = MAT.hollow;
    ctx.fill();
  }

  ctx.save();
  ctx.beginPath();
  ctx.arc(0, 0, winding.rp[0], 0, TAU);
  ctx.clip();
  for (const p of recipe.patches) {
    const pos = patchCorePos(recipe, p);
    ctx.save();
    ctx.translate(pos.x, pos.y);
    const mat = MAT[p.materialId] || { fill: '#888', edge: '#444' };
    if (p.cut === 'hosogiri') {
      hosogiriPath(ctx, p, 0);
      ctx.fillStyle = mat.fill;
      ctx.fill();
      ctx.strokeStyle = mat.skin || mat.edge;
      ctx.lineWidth = 0.45;
      ctx.stroke();
    } else if (p.materialId === 'cucumber' && p.cut !== 'сектор') {
      barPath(ctx, p, 0);
      ctx.fillStyle = mat.fill;
      ctx.fill();
      const w = p.widthMm;
      const h = p.heightMm;
      ctx.fillStyle = mat.skin;
      ctx.fillRect(-w / 2, h / 2 - 0.7, w, 0.7);
      ctx.strokeStyle = mat.skin;
      ctx.lineWidth = 0.45;
      barPath(ctx, p, 0);
      ctx.stroke();
    } else {
      ctx.beginPath();
      if (p.materialId === 'cucumber') cucumberPath(ctx, p, 0);
      else barPath(ctx, p, 0);
      ctx.fillStyle = mat.fill;
      ctx.fill();
      ctx.strokeStyle = mat.skin || mat.edge;
      ctx.lineWidth = 0.45;
      ctx.stroke();
    }
    ctx.restore();
  }
  ctx.restore();

  ctx.restore();
}

export function drawSheet(ctx, recipe, winding, cssW, cssH) {
  const L = recipe.sheet.lengthMm;
  const T = winding.T || 7;
  const pad = 16;
  const x0 = pad;
  const innerW = cssW - pad * 2;
  const uToX = (u) => x0 + (u / L) * innerW;

  ctx.fillStyle = '#171713';
  ctx.fillRect(0, 0, cssW, cssH);

  const labelH = 13;
  const noriH = Math.max(7, Math.min(11, (cssH - labelH) * 0.2));
  const riceH = Math.max(14, (cssH - labelH) * 0.42);
  const noriY = cssH - labelH - noriH;
  const riceY = noriY - riceH + 3;

  ctx.fillStyle = '#151c18';
  ctx.beginPath();
  ctx.roundRect(uToX(0), noriY + 2, innerW, noriH, 3);
  ctx.fill();
  ctx.fillStyle = MAT.nori;
  ctx.beginPath();
  ctx.roundRect(uToX(0), noriY, innerW, noriH - 1, 3);
  ctx.fill();

  const rx = uToX(winding.sRice0);
  const rw = Math.max(4, uToX(winding.sRice1) - rx);
  ctx.fillStyle = '#cfc6b8';
  ctx.beginPath();
  ctx.moveTo(rx, noriY + 2);
  ctx.lineTo(rx, riceY + 7);
  ctx.quadraticCurveTo(rx, riceY, rx + 10, riceY);
  ctx.lineTo(rx + rw - 10, riceY);
  ctx.quadraticCurveTo(rx + rw, riceY, rx + rw, riceY + 7);
  ctx.lineTo(rx + rw, noriY + 2);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = MAT.rice;
  ctx.beginPath();
  ctx.moveTo(rx + 2, noriY + 2);
  ctx.lineTo(rx + 2, riceY + 9);
  ctx.quadraticCurveTo(rx + 2, riceY + 3, rx + 12, riceY + 3);
  ctx.lineTo(rx + rw - 12, riceY + 3);
  ctx.quadraticCurveTo(rx + rw - 2, riceY + 3, rx + rw - 2, riceY + 9);
  ctx.lineTo(rx + rw - 2, noriY + 2);
  ctx.closePath();
  ctx.fill();

  const win = placementWindowMm(recipe.sheet);
  const wx0 = uToX(win.nearEdgeMm);
  const wx1 = uToX(win.farEdgeMm);
  ctx.strokeStyle = 'rgba(224,178,95,0.7)';
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.moveTo(wx0, riceY - 3);
  ctx.lineTo(wx0, riceY + riceH * 0.45);
  ctx.moveTo(wx1, riceY - 3);
  ctx.lineTo(wx1, riceY + riceH * 0.45);
  ctx.stroke();

  const surface = riceY + 2;
  for (const p of recipe.patches) {
    const mat = MAT[p.materialId] || { fill: '#888', edge: '#444' };
    const half = p.widthMm / 2;
    const x = uToX(p.uMm - half);
    const w = Math.max(5, uToX(p.uMm + half) - x);
    const chipH = Math.max(9, Math.min(riceH * 1.05, (p.heightMm / T) * riceH * 0.95));
    const chipY = surface - chipH + 4;
    ctx.fillStyle = 'rgba(0,0,0,0.28)';
    ctx.beginPath();
    ctx.roundRect(x + 1.2, chipY + 2, w, chipH, 2.5);
    ctx.fill();
    ctx.fillStyle = mat.fill;
    ctx.beginPath();
    ctx.roundRect(x, chipY, w, chipH, 2.5);
    ctx.fill();
    ctx.fillStyle = 'rgba(255,255,255,0.14)';
    ctx.fillRect(x + 1, chipY + 1, w - 2, 2);
    ctx.strokeStyle = mat.skin || mat.edge || '#444';
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  ctx.fillStyle = '#9a9280';
  ctx.font = '10px ui-monospace, SFMono-Regular, Menlo, monospace';
  ctx.textBaseline = 'bottom';
  ctx.fillText('0', uToX(0), cssH - 1);
  ctx.textAlign = 'right';
  ctx.fillText(String(L), uToX(L), cssH - 1);
  ctx.textAlign = 'left';
  ctx.fillText('окно', (wx0 + wx1) / 2 - 12, riceY - 4);
}

export function rollSideLayout(cssW, cssH) {
  const pad = 28;
  return { x0: pad, y0: cssH / 2, innerW: cssW - pad * 2, pad };
}

export function sheetShare(cssH) {
  return Math.round(cssH * 0.62);
}

export function drawBar(ctx, recipe, winding, cssW, cssH, cuts, vFrac, knifeY) {
  const sheetH = sheetShare(cssH);
  const rollH = cssH - sheetH;
  drawRollSide(ctx, winding, cssW, rollH, cuts, vFrac, knifeY);
  ctx.save();
  ctx.translate(0, rollH);
  drawSheet(ctx, recipe, winding, cssW, sheetH);
  ctx.restore();
}

export function drawRollSide(ctx, winding, cssW, cssH, cuts, vFrac, knifeY) {
  const Rout = winding.Rout + winding.W;
  const { x0, y0, innerW } = rollSideLayout(cssW, cssH);
  const Rpx = Math.min(22, cssH * 0.28);

  ctx.fillStyle = '#171713';
  ctx.fillRect(0, 0, cssW, cssH);

  ctx.fillStyle = 'rgba(0,0,0,0.4)';
  ctx.beginPath();
  ctx.ellipse(x0 + innerW / 2, y0 + Rpx + 6, innerW / 2 + 4, 7, 0, 0, TAU);
  ctx.fill();

  const g = ctx.createLinearGradient(0, y0 - Rpx, 0, y0 + Rpx);
  g.addColorStop(0, '#3a4a40');
  g.addColorStop(0.45, '#2a3a32');
  g.addColorStop(1, '#1a241e');
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.roundRect(x0, y0 - Rpx, innerW, Rpx * 2, Rpx);
  ctx.fill();
  ctx.strokeStyle = '#1a211c';
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.fillStyle = 'rgba(255,255,255,0.08)';
  ctx.beginPath();
  ctx.roundRect(x0 + 8, y0 - Rpx * 0.55, innerW - 16, Rpx * 0.28, 6);
  ctx.fill();

  ctx.strokeStyle = 'rgba(243,231,202,0.22)';
  ctx.lineWidth = 1;
  for (const c of cuts) {
    const x = x0 + c * innerW;
    ctx.beginPath();
    ctx.moveTo(x, y0 - Rpx - 4);
    ctx.lineTo(x, y0 + Rpx + 4);
    ctx.stroke();
  }

  const kx = x0 + vFrac * innerW;
  const ky = knifeY != null ? knifeY : y0 - Rpx - 18;
  drawYanagiba(ctx, kx, ky, Rpx);
}

function drawYanagiba(ctx, x, y, Rpx) {
  const bl = Rpx * 3.4;
  const bw = Math.max(5, Rpx * 0.28);
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(-0.08);
  ctx.fillStyle = '#d9e5e8';
  ctx.beginPath();
  ctx.moveTo(-bw * 0.15, -bl);
  ctx.lineTo(bw * 0.45, -bl * 0.08);
  ctx.lineTo(bw * 0.12, 8);
  ctx.lineTo(-bw * 0.35, 4);
  ctx.closePath();
  ctx.fill();
  ctx.fillStyle = 'rgba(255,255,255,0.7)';
  ctx.fillRect(-bw * 0.02, -bl + 10, bw * 0.12, bl - 18);
  ctx.fillStyle = '#2c2420';
  ctx.beginPath();
  ctx.roundRect(-bw * 0.55, -bl - Rpx * 1.05, bw * 1.15, Rpx * 1.05, 4);
  ctx.fill();
  ctx.fillStyle = '#4a3a30';
  ctx.fillRect(-bw * 0.55, -bl - 2, bw * 1.15, 4);
  ctx.restore();
}

