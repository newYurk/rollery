'use strict';
// РИСОВАНИЕ ЛИСТА (вид сверху): текстура риса, патчи начинок, выделение, циновка.
//
// Текстура кешируется (getSpreadTex), и её ключ обязан видеть витки и обёртку: масштаб зерна
// берётся от sheetLen (issue #89, починено 29.08).
//
// Зерно рисуется в РАЗМЕРЕ ЗЕРНА, а не в пикселях экрана: 7,7 × 3,5 мм по Мацуи 2001
// (docs/geometry-audit.md). У листа потолок детализации ниже, чем у среза, — сверху видно
// целые зёрна в постели, а борозда между ними это признак РЕЗА.

// ---------------------------------------------------------------- рисование листа (вид сверху)
let spreadTex = null, spreadTexKey = '';
function getSpreadTex(w, h) {
  // ⚠ turns и обёртка ОБЯЗАНЫ быть в ключе: масштаб зерна ниже берётся от sheetLen(b), а тот
  // читает S.turns и толщину обёртки b.w. Без них переход между уровнями пазла с одинаковым
  // числом кусков и той же базой (например 4 → 5, turns 3 → 2) не менял ключ, и лист оставался
  // нарисован в масштабе прошлого уровня — расхождение в 2,1 раза. Ровно так же устроен ключ
  // модели в buildModel, и по той же причине (issue #89).
  const cw = Math.round(w * DPR), ch = Math.round(h * DPR),
        key = S.base + '|' + (B().wrapKey || '-') + '|' + (S.turns || '-') + '|' + cw + 'x' + ch;
  if (spreadTex && spreadTexKey === key) return spreadTex;
  const b = B(), base = b.spreadRgb, c = document.createElement('canvas'); c.width = cw; c.height = ch;
  const x = c.getContext('2d'); const img = x.createImageData(cw, ch); const d = img.data;
  // Тот же LOD, что на срезе (зерно тут меряется по ширине листа: cw device-px на Wv/GRAIN зёрен),
  // но с потолком 0,5. ПОЧЕМУ потолок: сверху видно ЦЕЛЫЕ зёрна в постели, а борозда между зёрнами —
  // это признак РЕЗА, её в полную силу видно только на срезе. На полную амплитуду лист превращался
  // в мозаику (снято на скриншоте: 54 зерна поперёк, каждое с бороздой) и спорил с начинками.
  const sheetLod = Math.min(0.5, clamp((cw / (b.Wv / GRAIN) - 6) / 8));
  for (let j = 0; j < ch; j++) for (let i = 0; i < cw; i++) {
    const col = spreadColor(i / cw * b.Wv / GRAIN, j / ch * sheetLen(b) / GRAIN, b, undefined, undefined, sheetLod), k = (j * cw + i) * 4;
    d[k] = base[0] + (col[0] - base[0]) * 0.7; d[k + 1] = base[1] + (col[1] - base[1]) * 0.7; d[k + 2] = base[2] + (col[2] - base[2]) * 0.7; d[k + 3] = 255;
  }
  x.putImageData(img, 0, 0); spreadTex = c; spreadTexKey = key;
  return c;
}
// Фигура патча в экранных координатах: x, y — верхний левый угол; w — вдоль v, h — вдоль u.
function drawPatchShape(d, x, y, w, h, flat) {
  const c = d.color, rgb = d.rgb;
  const r = d.round ? h / 2 : d.lens ? h / 2.5 : 3;
  if (d.round) {
    const g = ctx.createLinearGradient(0, y, 0, y + h);
    g.addColorStop(0, rgbCss(shade(rgb, 0.75))); g.addColorStop(0.35, rgbCss(mix(rgb, [255, 255, 255], 0.25))); g.addColorStop(0.7, c); g.addColorStop(1, rgbCss(shade(rgb, 0.6)));
    ctx.fillStyle = g;
  } else ctx.fillStyle = c;
  rr(x, y, w, h, r); ctx.fill();
  ctx.save(); rr(x, y, w, h, r); ctx.clip();
  switch (d.tex) {
    case 'salmon': ctx.strokeStyle = 'rgba(255,246,236,0.6)'; ctx.lineWidth = Math.max(1.5, h * 0.12);
      for (let i = -h; i < w + h; i += Math.max(7, w * 0.11)) { ctx.beginPath(); ctx.moveTo(x + i, y + h); ctx.lineTo(x + i + h * 0.9, y); ctx.stroke(); } break;
    case 'shrimp': ctx.fillStyle = 'rgba(250,236,224,0.85)';
      for (let i = 0; i < w; i += Math.max(6, w * 0.2)) ctx.fillRect(x + i, y, Math.max(3, w * 0.09), h); break;
    case 'tamago': ctx.strokeStyle = 'rgba(200,150,50,0.5)'; ctx.lineWidth = 1;
      for (let k = 1; k < 4; k++) { ctx.beginPath(); ctx.moveTo(x, y + h * k / 4); ctx.lineTo(x + w, y + h * k / 4); ctx.stroke(); } break;
    case 'strawberry': ctx.fillStyle = 'rgba(248,230,120,0.9)';
      for (let k = 0; k < 7; k++) ctx.fillRect(x + w * hash(k, 3) * 0.9 + 1, y + h * hash(k, 9) * 0.8 + 1, 2, 2); break;
    case 'kiwi': ctx.fillStyle = 'rgba(236,240,190,0.9)'; ctx.beginPath(); ctx.ellipse(x + w / 2, y + h / 2, w * 0.22, h * 0.3, 0, 0, TAU); ctx.fill();
      ctx.fillStyle = '#1e1914'; for (let k = 0; k < 8; k++) { const a = k / 8 * TAU; ctx.fillRect(x + w / 2 + Math.cos(a) * w * 0.28 - 1, y + h / 2 + Math.sin(a) * h * 0.36 - 1, 2, 2); } break;
    case 'cucumber': ctx.fillStyle = 'rgba(214,232,178,0.55)'; ctx.fillRect(x, y + h * 0.35, w, h * 0.25); break;
    case 'gloss': ctx.fillStyle = 'rgba(255,255,255,0.35)'; ctx.fillRect(x, y + h * 0.2, w, h * 0.2); break;
    case 'flat': if (!flat) { ctx.fillStyle = 'rgba(255,255,255,0.05)'; for (let i = 0; i < w; i += 5) ctx.fillRect(x + i, y, 2, h); } break;
  }
  ctx.restore();
  ctx.strokeStyle = 'rgba(0,0,0,0.28)'; ctx.lineWidth = 1; rr(x, y, w, h, r); ctx.stroke();
}
function patchRect(p) {
  const m = dims(p), s = L.sheet;
  return { x: s.x + (p.v - m.dv / 2) * s.w, y: s.y + (1 - p.u - m.du / 2) * s.h, w: m.dv * s.w, h: m.du * s.h };
}
// Экранная трансформация повёрнутого патча: центр, угол и размеры в пикселях (лист анизотропен: px/единица разные по осям).
function patchScreen(p) {
  const m = dims(p), b = B(), s = L.sheet, Lu = sheetLen(b), rot = p.rot || 0, c = Math.cos(rot), sn = Math.sin(rot);
  const pxV = s.w / b.Wv, pxU = s.h / Lu, w = m.du * Lu, len = m.dv * b.Wv;
  const cx = s.x + p.v * s.w, cy = s.y + (1 - p.u) * s.h;
  const ang = Math.atan2(sn * pxU, c * pxV);   // ось длины патча: (dv, du) = (cos, -sin) → экран (x вправо, y вниз = -u)
  const lenPx = len * Math.hypot(c * pxV, sn * pxU), wPx = w * Math.hypot(sn * pxV, c * pxU);
  return { cx, cy, ang, lenPx, wPx };
}
// z0 — высота патча в стопке; она ЖИВЁТ В МОДЕЛИ (buildModel считает restack на своей копии
// и вход не мутирует), поэтому вызывающий передаёт её сюда, а не читает из самого патча.
function drawPatchTop(p, alpha = 1, z0 = 0) {
  const d = ING[p.kind], m = dims(p), s = L.sheet;
  if (p.rot) {
    const t = patchScreen(p);
    ctx.save(); ctx.globalAlpha = alpha * (p.kind === 'nori' ? 0.82 : d.paint ? 0.92 : 1);
    ctx.shadowColor = d.paint ? 'transparent' : 'rgba(0,0,0,0.35)'; ctx.shadowBlur = 4 + z0 * 6; ctx.shadowOffsetY = 2 + z0 * 3;
    ctx.translate(t.cx, t.cy); ctx.rotate(t.ang);
    if (d.paint) { ctx.fillStyle = d.color; rr(-t.lenPx / 2, -t.wPx / 2, t.lenPx, t.wPx, 3); ctx.fill(); }
    else drawPatchShape(d, -t.lenPx / 2, -t.wPx / 2, t.lenPx, t.wPx, false);
    ctx.restore(); return;
  }
  if (d.paint) {
    const r = patchRect(p); ctx.save(); ctx.globalAlpha = alpha * 0.92; ctx.fillStyle = d.color; rr(r.x, r.y, r.w, r.h, 3); ctx.fill();
    ctx.globalAlpha = alpha * 0.25; ctx.fillStyle = '#fff'; for (let k = 0; k < r.w * r.h / 60; k++) ctx.fillRect(r.x + hash(k, 1) * r.w, r.y + hash(k, 2) * r.h, 2, 1.5);
    ctx.restore(); return;
  }
  ctx.save(); ctx.globalAlpha = alpha * (p.kind === 'nori' ? 0.82 : 1);
  ctx.shadowColor = 'rgba(0,0,0,0.35)'; ctx.shadowBlur = 4 + z0 * 6; ctx.shadowOffsetY = 2 + z0 * 3;
  if (d.wave) {
    const lw = m.du * s.h, x0 = s.x + (p.v - m.dv / 2) * s.w, x1 = s.x + (p.v + m.dv / 2) * s.w;
    ctx.beginPath();
    for (let i = 0; i <= 40; i++) { const v = lerp(p.v - m.dv / 2, p.v + m.dv / 2, i / 40); const uc = p.u + d.wave.amp * Math.sin(TAU * d.wave.freq * v + p.phase); const x = lerp(x0, x1, i / 40), y = s.y + (1 - uc) * s.h; i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }
    ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.lineWidth = lw; ctx.strokeStyle = d.color; ctx.stroke();
    ctx.shadowColor = 'transparent'; ctx.lineWidth = lw * 0.3; ctx.strokeStyle = 'rgba(255,255,255,0.35)';
    ctx.save(); ctx.translate(0, -lw * 0.22); ctx.stroke(); ctx.restore();
  } else {
    const r = patchRect(p); drawPatchShape(d, r.x, r.y, r.w, r.h, false);
  }
  ctx.restore();
}
function drawMat(x, y, w, h, r = 14, b = B()) {
  rr(x, y, w, h, r); ctx.fillStyle = b.mat; ctx.fill();
  ctx.save(); rr(x, y, w, h, r); ctx.clip();
  ctx.strokeStyle = b.matLine; ctx.lineWidth = 1.2;
  for (let yy = y + 3; yy < y + h; yy += 7) { ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x + w, yy); ctx.stroke(); }
  ctx.restore();
}
// Кусочки лежат на той же доске, на которой сворачивали. Без неё тёмная нори (#22342b) тонет
// в фоне (#171713): контраст 1,36:1 — внешнего контура ролла просто не видно. На циновке — 5,9:1.
// items — [{x, y, size}] центры срезов; доска одна, по их общей рамке.
function drawSlab(items, alpha = 1, b = B(), pad = null) {
  if (!items || !items.length || alpha <= 0.02) return;
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, mn = Infinity;
  for (const it of items) { const h = it.size / 2; if (!(h > 0)) continue; x0 = Math.min(x0, it.x - h); y0 = Math.min(y0, it.y - h); x1 = Math.max(x1, it.x + h); y1 = Math.max(y1, it.y + h); mn = Math.min(mn, it.size); }
  if (!(x1 > x0)) return;
  const p = pad == null ? clamp(0.08 * mn, 5, 14) : pad;
  ctx.save(); ctx.globalAlpha *= alpha;
  drawMat(x0 - p, y0 - p, x1 - x0 + 2 * p, y1 - y0 + 2 * p, Math.min(14, (mn + 2 * p) / 2), b);
  ctx.restore();
}
// Цилиндр ролла (вид сверху). pieces: [{a, b, off}] в долях длины, off — сдвиг по x; squash — сплющивание.
function drawRollBody(xc, yc, R, len, pieces, squash = 1, alpha = 1) {
  const b = B(), wr = b.wrapperRgb;
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.translate(xc, yc); ctx.scale(1, squash);
  // тень
  ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.beginPath(); ctx.ellipse(0, R + 8, len / 2 + 6, R * 0.35, 0, 0, TAU); ctx.fill();
  const g = ctx.createLinearGradient(0, -R, 0, R);
  g.addColorStop(0, rgbCss(shade(wr, 0.55))); g.addColorStop(0.28, rgbCss(mix(wr, [255, 255, 255], S.base === 'cake' ? 0.35 : 0.22)));
  g.addColorStop(0.55, rgbCss(wr)); g.addColorStop(1, rgbCss(shade(wr, 0.4)));
  for (const pc of pieces) {
    const x0 = -len / 2 + pc.a * len + pc.off, w = (pc.b - pc.a) * len;
    ctx.fillStyle = g; rr(x0, -R, w, 2 * R, 6); ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.35)'; ctx.lineWidth = 1; ctx.stroke();
    // блик и фактура
    ctx.fillStyle = 'rgba(255,255,255,0.10)'; rr(x0 + 4, -R * 0.62, w - 8, R * 0.22, 4); ctx.fill();
  }
  ctx.restore();
}
function drawKnife(x, y, angle, press, R) {
  const bl = R * 3.2, bw = R * 0.34;
  ctx.save(); ctx.translate(x, y); ctx.rotate(angle);
  ctx.shadowColor = 'rgba(0,0,0,0.45)'; ctx.shadowBlur = 8; ctx.shadowOffsetX = 4; ctx.shadowOffsetY = 4;
  ctx.fillStyle = '#d9e5e8'; ctx.beginPath(); ctx.moveTo(-bw / 2, -bl); ctx.lineTo(bw / 2, -bl); ctx.lineTo(bw / 2, 0); ctx.lineTo(-bw / 2, -bw * 0.9); ctx.closePath(); ctx.fill();
  ctx.shadowColor = 'transparent';
  ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.fillRect(-bw * 0.3, -bl + 6, bw * 0.16, bl - 14);
  ctx.fillStyle = '#2c2420'; rr(-bw * 0.7, -bl - R * 0.9, bw * 1.4, R * 0.95, 5); ctx.fill();
  ctx.fillStyle = '#4a3a30'; ctx.fillRect(-bw * 0.7, -bl - 2, bw * 1.4, 5);
  if (press > 0) { ctx.globalAlpha = press * 0.4; ctx.fillStyle = '#fff'; ctx.fillRect(-1.5, -bl + 8, 3, bl - 12); }
  ctx.restore();
}
function drawFaceImg(img, x, y, size, scaleX = 1, alpha = 1) {
  ctx.save(); ctx.globalAlpha = alpha; ctx.translate(x, y); ctx.scale(Math.max(0.01, scaleX), 1);
  ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 18; ctx.shadowOffsetY = 8;
  ctx.drawImage(img, -size / 2, -size / 2, size, size);
  // контактная тень: узкий тёмный ореол по силуэту — граница светлой обёртки на светлой доске
  ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = 3; ctx.shadowOffsetY = 1;
  ctx.drawImage(img, -size / 2, -size / 2, size, size);
  ctx.restore();
}

