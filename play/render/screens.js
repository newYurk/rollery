'use strict';
// ЭКРАНЫ: раскладка, скрученный ролл, ритуал реза, раскрытие, нарезка, тарелка.
//
// Ритуал реза — часть награды, а не техническая пауза: нож приходит, вдавливается, режет,
// половины разъезжаются, срез поворачивается «дверцей» к камере (docs/design-core.md).
// Срез считается ОДИН раз в offscreen до начала анимации и дальше только рисуется.

// ---------------------------------------------------------------- экраны
let particles = [], shakeUntil = 0;
function spawnParticles(x, y, n) {
  const c = B().spreadRgb;
  for (let i = 0; i < n; i++) particles.push({ x, y, vx: (Math.random() - 0.5) * 160, vy: -Math.random() * 140 - 30, life: 0.5 + Math.random() * 0.3, t: 0, c, s: 2 + Math.random() * 2.5 });
}
function drawParticles(dt) {
  particles = particles.filter(p => (p.t += dt) < p.life);
  for (const p of particles) { p.x += p.vx * dt; p.y += p.vy * dt; p.vy += 500 * dt; ctx.globalAlpha = 1 - p.t / p.life; ctx.fillStyle = rgbCss(p.c); ctx.fillRect(p.x, p.y, p.s, p.s); }
  ctx.globalAlpha = 1;
}
const hints = {
  lay: 'Выбери начинку и тапни по листу · потяни циновку вверх, чтобы скрутить',
  layMove: 'Тащи, чтобы подвинуть · вытащи за лист, чтобы убрать',
  laySel: 'В нори — контур на срезе · поворот — поперёк или по диагонали: рисунок разный в кусочках',
  puzzle: 'Повтори срез: разложи, скрути, разрежь',
  rolled: 'Тапни по роллу там, где резать',
  revealed: 'Вот что ты положил. Хочется ещё?',
  plate: 'Шесть кусочков — тапни, чтобы рассмотреть',
};
// Цель пазла / живой предпросмотр: полосой над листом, накладкой на листе или в боковой колонке.
function drawPreviewArea(p) {
  const pm = L.previewMode; if (pm === 'none' || p > 0) return;
  const pz = S.puzzle, k = pz ? pz.vs.length : 1, tm = pz ? targetModel() : null;
  const label = (x, y, lines, align = 'center') => { ctx.fillStyle = '#b8ad95'; ctx.font = font(12); ctx.textAlign = align; ctx.textBaseline = 'middle'; lines.forEach((t, i) => ctx.fillText(t, x, y + i * 16)); };
  const turnsTxt = () => `${windFor(getModel(), 0.5).turns.toFixed(1).replace('.', ',')} витка`;
  if (pm === 'band') {
    const cx = L.ox + L.cw / 2, y = L.previewY;
    if (pz) { const fs = L.previewSize, x0 = cx - ((k - 1) * (fs + 8)) / 2; drawSlab(Array.from({ length: k }, (_, i) => ({ x: x0 + i * (fs + 8), y, size: fs })), 1, B(), 6); for (let i = 0; i < k; i++) drawFaceImg(face(pz.vs[i], fs, tm), x0 + i * (fs + 8), y, fs); }
    else { drawSlab([{ x: cx - 30, y, size: 116 }], 1, B(), 8); drawFaceImg(face(0.5, 116), cx - 30, y, 116); label(cx + 30 + 14, y - 8, ['живой срез', turnsTxt()], 'left'); }
  } else if (pm === 'overlay') {
    const s = L.sheet;
    if (pz) {
      const fs = Math.min(56, (s.w - 16 - 6 * (k - 1)) / k), x0 = s.x + s.w / 2 - ((k - 1) * (fs + 6)) / 2, y = s.y + fs / 2 + 8;
      drawMat(s.x + 4, s.y + 4, s.w - 8, fs + 8, 10);
      for (let i = 0; i < k; i++) drawFaceImg(face(pz.vs[i], fs, tm), x0 + i * (fs + 6), y, fs);
    } else {
      const fs = 88, x = s.x + s.w - fs / 2 - 8, y = s.y + fs / 2 + 8;
      drawMat(x - fs / 2 - 7, y - fs / 2 - 7, fs + 14, fs + 14, (fs + 14) / 2);
      drawFaceImg(face(0.5, fs), x, y, fs);
    }
  } else if (pm === 'side') {
    const sd = L.side, cx = sd.x + sd.w / 2; let y = sd.y;
    if (pz) {
      if (k === 1) { const fs = L.previewSize; drawSlab([{ x: cx, y: y + fs / 2, size: fs }], 1, B(), 7); drawFaceImg(face(pz.vs[0], fs, tm), cx, y + fs / 2, fs); y += fs + 16; }
      else { const cell = L.targetCell, per = Math.min(k, 3), rows = Math.ceil(k / per), x0 = cx - ((per - 1) * (cell + 8)) / 2; const pos = i => ({ x: x0 + (i % per) * (cell + 8), y: y + cell / 2 + Math.floor(i / per) * (cell + 8), size: cell }); drawSlab(Array.from({ length: k }, (_, i) => pos(i)), 1, B(), 6); for (let i = 0; i < k; i++) { const q = pos(i); drawFaceImg(face(pz.vs[i], cell, tm), q.x, q.y, cell); } y += rows * (cell + 8) + 8; }
      if (L.mode !== 'L') { ctx.fillStyle = '#e0b25a'; ctx.font = font(13, 600); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; const t = levelTitle(pz.lv, pz.level); ctx.fillText(t.length > 34 ? t.slice(0, 33) + '…' : t, cx, y + 8); label(cx, y + 28, ['повтори срез: разложи, скрути, разрежь']); }
    } else {
      const fs = L.previewSize; drawSlab([{ x: cx, y: y + fs / 2, size: fs }], 1, B(), 6); drawFaceImg(face(0.5, fs), cx, y + fs / 2, fs); label(cx, y + fs + 18, ['живой срез · ' + turnsTxt()]);
    }
  }
}
function drawLay() {
  // s — ЛОГИЧЕСКАЯ рамка листа (SB): x вправо = v, y вниз = −u. Весь лист рисуется внутри
  // sheetPush()/sheetPop() — при повёрнутом листе (#23) это один общий поворот на ±90°.
  // Экранные элементы (циновка-фон, ручка, полосы предпросмотра, кнопки) остаются снаружи.
  const s = SB(), p = S.rollP, hd = L.handle;
  drawMat(hd.x, L.sheet.y - 18, hd.w, hd.y + hd.h + 8 - (L.sheet.y - 18));
  sheetPush();
  const yb = s.y + s.h * (1 - p);
  // лист: остаток, ещё не скрученный
  ctx.save(); ctx.beginPath(); ctx.rect(s.x - 8, s.y - 8, s.w + 16, Math.max(0, yb - s.y + 8)); ctx.clip();
  rr(s.x - 5, s.y - 5, s.w + 10, s.h + 10, 6); ctx.fillStyle = B().wrapper; ctx.fill();
  const mdl = getModel(), wd0 = windFor(mdl, 0.5), Lm = mdl.g.L;
  const uClose = wd0.sClose >= 0 ? wd0.sClose / Lm : B().spreadEnd, uEnd = wd0.sEnd < Lm ? wd0.sEnd / Lm : 1;
  const bare = (1 - uClose) * s.h, rimPx = B().spreadEnd < 1 ? RIM_W * s.h : 0;
  ctx.save(); rr(s.x, s.y + bare, s.w, s.h - bare, 4); ctx.clip(); ctx.drawImage(getSpreadTex(s.w, s.h), s.x, s.y, s.w, s.h);
  // КРАЙ РИСА ПРОСВЕЧИВАЕТ, А НЕ ОБВОДИТСЯ. Стенкой рис не обрывается: у самой кромки его
  // остаётся на пару зёрен, и сквозь него видно нори. Раньше здесь рисовалась светлая полоса —
  // валик «нарисованный», а не следствие толщины; владелец на неё и указала. Теперь это просто
  // сход на нет: нори проступает тем сильнее, чем меньше риса. Сам бортик остаётся в МОДЕЛИ
  // (spreadAt), он растит ролл; рисовать его отдельной чертой не надо.
  if (rimPx) {
    const fade = Math.min(rimPx, 0.02 * s.h);   // ≈ 4 мм: рис сходит на нет за пару зёрен
    const gr = ctx.createLinearGradient(0, s.y + bare, 0, s.y + bare + fade);
    gr.addColorStop(0, B().wrapper); gr.addColorStop(1, rgbCss(B().wrapperRgb, 0));
    ctx.fillStyle = gr; ctx.fillRect(s.x, s.y + bare, s.w, fade);
  }
  ctx.restore();
  const zOf = pt => { const i = patches().indexOf(pt), q = i >= 0 ? mdl.list[i] : null; return q ? q.z0 : 0; };   // стопка — из модели, порядок клона тот же
  for (const pt of patches()) if (pt !== drag.patch) drawPatchTop(pt, uEnd < 1 && pt.u > uEnd ? 0.35 : 1, zOf(pt));
  if (uEnd < 1) {   // лишний лист обрезан: ролл замкнулся раньше; что выше линии — не попадёт в ролл
    const yEnd = s.y + (1 - uEnd) * s.h; ctx.fillStyle = 'rgba(23,23,19,0.35)'; ctx.fillRect(s.x - 5, s.y - 5, s.w + 10, yEnd - s.y + 5);
    ctx.setLineDash([6, 4]); ctx.strokeStyle = 'rgba(243,231,202,0.6)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(s.x, yEnd); ctx.lineTo(s.x + s.w, yEnd); ctx.stroke(); ctx.setLineDash([]);
    unrot(s.x + s.w / 2, s.y + 6, () => { ctx.fillStyle = 'rgba(243,231,202,0.7)'; ctx.font = font(10); ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText('лишний нори — обрезан, ролл замкнулся раньше', 0, 0); });
  }
  if (drag.patch) drawPatchTop(drag.patch, 0.85, zOf(drag.patch));
  const sel = S.selPatch && patches().includes(S.selPatch) ? S.selPatch : (S.selPatch = null);
  if (sel && p === 0) {
    ctx.setLineDash([5, 4]); ctx.strokeStyle = '#fff'; ctx.lineWidth = 2;
    if (sel.rot) { const t = patchScreen(sel); ctx.save(); ctx.translate(t.cx, t.cy); ctx.rotate(t.ang); rr(-t.lenPx / 2 - 5, -t.wPx / 2 - 5, t.lenPx + 10, t.wPx + 10, 8); ctx.stroke(); ctx.restore(); }
    else { const r = patchRect(sel), d = ING[sel.kind]; if (d.wave) { r.y -= d.wave.amp * s.h; r.h += 2 * d.wave.amp * s.h; } rr(r.x - 5, r.y - 5, r.w + 10, r.h + 10, 8); ctx.stroke(); }
    ctx.setLineDash([]);
  }
  if (S.preview && p === 0) { ctx.setLineDash([4, 6]); ctx.strokeStyle = 'rgba(40,30,20,0.45)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(s.x + s.w / 2, s.y); ctx.lineTo(s.x + s.w / 2, s.y + s.h); ctx.stroke(); ctx.setLineDash([]); }
  const core = p === 0 && !drag.patch ? getModel().core : null;   // линия подворота: что ниже неё, сомнётся в ядро
  if (core) { const yf = s.y + (1 - core.sFold / getModel().g.L) * s.h; ctx.setLineDash([2, 5]); ctx.strokeStyle = 'rgba(40,30,20,0.5)'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(s.x, yf); ctx.lineTo(s.x + s.w, yf); ctx.stroke(); ctx.setLineDash([]); unrot(s.x + s.w - 6, yf - 2, () => { ctx.fillStyle = 'rgba(40,30,20,0.55)'; ctx.font = font(10); ctx.textAlign = 'right'; ctx.textBaseline = 'bottom'; ctx.fillText('подворот — ядро', 0, 0); }); }
  ctx.restore();
  // ролл в процессе скрутки (внутри трансформа: при повёрнутом листе цилиндр сам встанет вертикально)
  if (p > 0) { const mm = getModel(); const R = windRout(0.5, p * mm.g.L, mm.g, mm.list) * s.h / mm.g.L; drawRollBody(s.x + s.w / 2, yb, R, s.w + 10, [{ a: 0, b: 1, off: 0 }]); }
  sheetPop();
  // циновка-ручка
  rr(hd.x, hd.y, hd.w, hd.h, 10); ctx.fillStyle = 'rgba(0,0,0,0.12)'; ctx.fill();
  ctx.fillStyle = 'rgba(40,30,20,0.55)'; ctx.font = font(13, 600); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  let ht = p > 0 ? 'ещё… ↑' : '↑ потяни циновку вверх — скрутить'; if (ctx.measureText(ht).width > hd.w - 24) ht = '↑ скрутить';
  ctx.fillText(ht, hd.x + hd.w / 2, hd.y + hd.h / 2);
  drawPreviewArea(p);
  buttons = [];
  const area = L.layBtn;
  if (sel && p === 0) {
    const canWrap = sel.kind !== 'nori' && !ING[sel.kind].wave && !ING[sel.kind].paint, canRot = !ING[sel.kind].wave;
    const rotLabel = `⟳ ${Math.round(((sel.rot || 0) * 180 / Math.PI + 45) % 180)}°`;
    // Четыре кнопки в ряду вместо трёх: дублирование — узкой иконкой, чтобы бюджет ширины
    // остался тем же (спецификация раскладки, docs/ui-review.md §2, считает не штуки, а место).
    buttonRow([...(canWrap ? [['wrap', 'В нори', true, 1.2]] : []), ...(canRot ? [['rotate', rotLabel, false, 1.05]] : []),
               ['duplicate', '⧉', false, 0.45], ['remove', 'Убрать', false, 1]], { ...area, max: 4 });
  } else {
    // ↶ и ↷ — история действий, а не «снять последний кусок» (issue #84). Тусклая стрелка
    // означает, что возвращать нечего: кнопка не прыгает, но и не врёт, что что-то сделает.
    const row = [['undo', '↶', false, 0.45, !canUndo()], ['redo', '↷', false, 0.45, !canRedo()],
                 ['mirror', '⇄ Отразить', false, 1.1], ['clear', 'Очистить', false, 1]];
    if (S.puzzle) row.push(['newpuzzle', '⟳', false, 0.45]);
    buttonRow(row, { ...area, max: row.length });
  }
  drawButtons(); drawChips();
  drawTopBar(drag.patch ? hints.layMove : sel ? hints.laySel : S.puzzle ? (L.previewMode === 'side' ? hints.puzzle : levelTitle(S.puzzle.lv, S.puzzle.level)) : hints.lay);
}
// Мост «лист → доска реза»: длина ролла на доске масштабируется от экранной протяжённости оси v
// (длины ролла на листе), радиус — от пикселей на единицу оси u. Раньше тут стояли s.w и s.h —
// верно только пока u вертикальна; после поворота (#23) формула на w/h раздула бы радиус в
// (lenU/lenV)² раз и утянула за собой нож, размах удара и разлёт половин.
function rollDims() { const m = getModel(), s = L.sheet; const k = L.roll.len / s.lenV; return { g: m.g, R: m.Rmax * s.lenU / m.g.L * k, len: L.roll.len }; }
function drawBoard(R, len, alpha = 1) {
  ctx.save(); ctx.globalAlpha = alpha; drawMat(L.roll.x - len / 2 - 26, L.roll.y - R - 36, len + 52, 2 * R + 72); ctx.restore();
}
function drawRolled() {
  const { R, len } = rollDims();
  drawBoard(R, len);
  drawRollBody(L.roll.x, L.roll.y, R, len, [{ a: 0, b: 1, off: 0 }]);
  // риски: где будут резы
  ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.setLineDash([3, 5]); ctx.lineWidth = 1;
  for (let i = 1; i < NPIECES; i++) { const x = L.roll.x - len / 2 + len * i / NPIECES; ctx.beginPath(); ctx.moveTo(x, L.roll.y - R - 14); ctx.lineTo(x, L.roll.y + R + 14); ctx.stroke(); }
  ctx.setLineDash([]);
  buttons = []; buttonRow([['back', '← Ещё начинки']]);
  drawButtons(); drawTopBar(hints.rolled);
}
// Ритуал реза: t — прогресс 0..1 (850 мс), потом zoom (0..1, 500 мс).
let cut = null;
function startCut(v) {
  const { R, len } = rollDims();
  const img = face(v, Math.max(L.faceSize, 2 * R));   // считаем срез заранее, до начала анимации
  cut = { v, x: L.roll.x - len / 2 + v * len, t0: performance.now(), dur: 850, zoom: 0, img, R, len, sounded: false, particled: false };
  S.mode = 'cut'; S.cuts++; S.cutsTotal++; save();
}
function drawCut(now) {
  const c = cut, t = clamp((now - c.t0) / c.dur);
  const press = easeOutCubic(remap(t, 0.18, 0.48)), cutP = easeInOutCubic(remap(t, 0.48, 0.68)), open = easeOutBack(remap(t, 0.68, 1));
  const gap = 18 * open, squash = 1 - 0.07 * press * (1 - cutP) - 0.03 * Math.sin(cutP * Math.PI);
  if (t >= 0.55 && !c.sounded) { c.sounded = true; sfx.cut(); shakeUntil = now + 70; }
  if (t >= 0.58 && !c.particled) { c.particled = true; spawnParticles(c.x, L.roll.y, 14); }
  if (shakeUntil > now) ctx.translate((Math.random() - 0.5) * 5, (Math.random() - 0.5) * 5);
  let zoom = 0;
  if (t >= 1) { zoom = clamp((now - c.t0 - c.dur) / 500); c.zoom = zoom; }
  const rollAlpha = 1 - 0.7 * easeOutCubic(zoom);
  drawBoard(c.R, c.len, 1 - easeOutCubic(zoom));
  drawRollBody(L.roll.x, L.roll.y, c.R, c.len, cutP > 0 ? [{ a: 0, b: c.v, off: -gap }, { a: c.v, b: 1, off: gap }] : [{ a: 0, b: 1, off: 0 }], squash, rollAlpha);
  // срез правой половины «поворачивается» к камере, потом наезжает
  if (open > 0) {
    const reveal = clamp(open), z = easeInOutCubic(zoom);
    const size = lerp(2 * c.R, L.faceSize, z), x = lerp(c.x + gap, L.ox + L.cw / 2, z), y = lerp(L.roll.y, L.faceY, z);
    drawSlab([{ x, y, size }], easeOutCubic(zoom) * reveal, B(), 10);
    drawFaceImg(c.img, x, y, size, reveal);
  }
  if (t < 0.9) {
    const kt = easeInOutCubic(remap(t, 0, 0.68)), yTop = L.roll.y - c.R - c.R * 2.6, yCut = L.roll.y + c.R * 0.95;
    const y = lerp(yTop, yCut, kt) + (t > 0.68 ? -(t - 0.68) / 0.22 * c.R * 2 : 0);
    drawKnife(c.x, y, -0.04 + 0.03 * Math.sin(t * Math.PI), press * (1 - cutP), c.R);
  }
  drawParticles(1 / 60);
  buttons = [];
  drawTopBar('');
  if (t >= 1 && zoom >= 1) { S.mode = 'revealed'; c.revealedAt = now; if (S.puzzle) puzzleEvaluate(); dirty = true; }
}
function drawCompare() {
  const pz = S.puzzle, res = pz.result || puzzleEvaluate(), tm = targetModel(), pm = getModel(), k = pz.vs.length, Rref = Math.max(tm.Rmax, pm.Rmax);
  const cw = L.cw, ch = L.ch, cx = L.ox + cw / 2, top = L.top + 12, wide = L.mode !== 'P';
  ctx.fillStyle = '#8d846f'; ctx.font = font(13); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  let yv;
  if (k === 1) {
    const fs = Math.max(80, Math.min(wide ? 0.3 * cw : (cw - 56) / 2, 0.45 * (L.rowBtn.y - top - 120), 400)), gap = wide ? 40 : 20;
    const p1 = clamp(gap / 2 - 3, 4, 10);
    drawSlab([{ x: cx - fs / 2 - gap / 2, y: top + fs / 2, size: fs }], 1, B(), p1); drawSlab([{ x: cx + fs / 2 + gap / 2, y: top + fs / 2, size: fs }], 1, B(), p1);
    drawFaceImg(face(pz.vs[0], fs, tm, Rref), cx - fs / 2 - gap / 2, top + fs / 2, fs); drawFaceImg(face(pz.vs[0], fs, pm, Rref), cx + fs / 2 + gap / 2, top + fs / 2, fs);
    ctx.fillText('цель', cx - fs / 2 - gap / 2, top + fs + 18); ctx.fillText('твой', cx + fs / 2 + gap / 2, top + fs + 18);
    yv = top + fs + 52;
  } else {
    const fs = Math.max(40, Math.min(wide ? (cw - 160) / k : (cw - 32 - 6 * (k - 1)) / k, 0.26 * ch, 213)), gap = 6;
    const sideLabels = cw - k * (fs + gap) >= 100, x0 = cx - ((k - 1) * (fs + gap)) / 2 + (sideLabels ? 20 : 0);
    const y1 = top + (sideLabels ? 0 : 18) + fs / 2, y2 = y1 + fs + 26;
    const row = yy => Array.from({ length: k }, (_, i) => ({ x: x0 + i * (fs + gap), y: yy, size: fs })), pr = sideLabels ? 8 : 5;
    drawSlab(row(y1), 1, B(), pr); drawSlab(row(y2), 1, B(), pr);
    for (let i = 0; i < k; i++) { drawFaceImg(face(pz.vs[i], fs, tm, Rref), x0 + i * (fs + gap), y1, fs); drawFaceImg(face(pz.vs[i], fs, pm, Rref), x0 + i * (fs + gap), y2, fs); }
    if (sideLabels) { ctx.textAlign = 'right'; ctx.fillText('цель', x0 - fs / 2 - 16, y1); ctx.fillText('твой', x0 - fs / 2 - 16, y2); ctx.textAlign = 'center'; }
    else { ctx.fillText('цель', cx, top + 6); ctx.fillText('твой', cx, y2 - fs / 2 - 10); }
    yv = y2 + fs / 2 + 34;
  }
  ctx.fillStyle = res.pass ? '#8fd18a' : '#e0b25a'; ctx.font = font(22, 700); ctx.fillText(res.pass ? `Совпало · ${Math.round(res.sim * 100)} %` : `Похоже на ${Math.round(res.sim * 100)} %`, cx, yv);
  ctx.fillStyle = '#b8ad95'; ctx.font = font(13);
  res.hints.forEach((h, i) => ctx.fillText(h, cx, yv + 26 + i * 18));
  let ye = yv + 26 + res.hints.length * 18;
  if (res.pass) { ctx.fillText(pz.level + 1 < LEVELS.length ? 'Дальше — следующий уровень' : 'Это был последний уровень', cx, ye); ye += 18; }
  const area = L.rowBtn.y - ye > 120 ? { x: L.rowBtn.x, y: ye + 20, w: L.rowBtn.w, h: L.btnH, max: 3 } : L.rowBtn;
  buttons = []; buttonRow(res.pass ? [['next', 'Дальше →', true], ['back', 'Ещё раз'], ['newpuzzle', '⟳ Другой']] : [['back', 'Ещё раз', true], ['newpuzzle', '⟳ Другой'], ['slice', 'Кусочки']], area);
  drawButtons(); drawTopBar(levelTitle(pz.lv, pz.level));
}
function drawRevealed() {
  if (S.puzzle && performance.now() - (cut.revealedAt || 0) > 900) { drawCompare(); return; }
  if (S.puzzle) dirty = true;
  const c = cut, cx = L.ox + L.cw / 2;
  drawBoard(c.R, c.len, 0.22);   // половинки ролла остаются на своей доске: без неё торчат «культями» из-под среза
  drawRollBody(L.roll.x, L.roll.y, c.R, c.len, [{ a: 0, b: c.v, off: -18 }, { a: c.v, b: 1, off: 18 }], 1, 0.3);
  drawSlab([{ x: cx, y: L.faceY, size: L.faceSize }], 1, B(), 10);
  drawFaceImg(c.img, cx, L.faceY, L.faceSize);
  ctx.fillStyle = '#8d846f'; ctx.font = font(13); ctx.textAlign = 'center'; ctx.textBaseline = 'top';
  ctx.fillText(`срез на ${Math.round(c.v * 100)} % длины`, cx, L.faceY + L.faceSize / 2 + 14);
  const hl = handLabel(); if (hl) { ctx.fillStyle = '#6f6754'; ctx.font = font(12); ctx.fillText(hl, cx, L.faceY + L.faceSize / 2 + 32); }
  buttons = []; buttonRow([['slice', `Нарезать на ${NPIECES}`, true], ['albumsave', S.saved > performance.now() ? '✓ В альбоме' : '★ В альбом'], ['back', 'Ещё начинки']]);
  if (S.saved > performance.now()) dirty = true;
  drawButtons(); drawTopBar(hints.revealed);
}
// Нарезка: быстрые удары, потом кусочки встают срезом и разъезжаются по тарелке.
let slicing = null;
function startSlicing() {
  const { R, len } = rollDims();
  const cutsV = []; for (let i = 1; i < NPIECES; i++) if (Math.abs(i / NPIECES - cut.v) > 1e-3) cutsV.push(i / NPIECES);
  const imgs = []; for (let i = 0; i < NPIECES; i++) imgs.push(face(pieceV(i), L.grid[0].size));
  slicing = { t0: performance.now(), cutsV, chop: 190, done: new Set([cut.v]), R, len, imgs, sounded: new Set() };
  S.mode = 'slicing';
}
function drawSlicing(now) {
  const s = slicing, el = now - s.t0, chopsEnd = s.cutsV.length * s.chop;
  const reveal = remap(el, chopsEnd + 60, chopsEnd + 460), move = easeInOutCubic(remap(el, chopsEnd + 420, chopsEnd + 980));
  // куски: позиции на ролле с зазорами
  const idx = Math.min(s.cutsV.length, Math.floor(el / s.chop));
  for (let i = 0; i < idx; i++) if (!s.sounded.has(i)) { s.sounded.add(i); sfx.chop(); spawnParticles(L.roll.x - s.len / 2 + s.cutsV[i] * s.len, L.roll.y, 6); }
  const doneCuts = new Set([cut.v, ...s.cutsV.slice(0, idx)]);
  const pieces = [];
  for (let i = 0; i < NPIECES; i++) {
    const a = i / NPIECES, b = (i + 1) / NPIECES;
    let gapsLeft = 0; for (const cv of doneCuts) if (cv <= a + 1e-6) gapsLeft++;
    const total = doneCuts.size; pieces.push({ a, b, off: (gapsLeft - total / 2) * 14 });
  }
  if (shakeUntil > now) ctx.translate((Math.random() - 0.5) * 4, (Math.random() - 0.5) * 4);
  if (move < 1) drawBoard(s.R, s.len, 1 - reveal);
  if (move < 1) drawRollBody(L.roll.x, L.roll.y, s.R, s.len, pieces, 1, 1 - reveal * 0.85);
  drawSlab(L.grid, move, B(), 16);
  if (idx < s.cutsV.length) {
    const ph = (el % s.chop) / s.chop, x = L.roll.x - s.len / 2 + s.cutsV[idx] * s.len;
    const y = L.roll.y + s.R * 0.95 - Math.abs(Math.sin(ph * Math.PI)) * s.R * 2.6;
    drawKnife(x, y, -0.03, 0, s.R);
  }
  if (reveal > 0) for (let i = 0; i < NPIECES; i++) {
    const pc = pieces[i], gx = L.grid[i];
    const x0 = L.roll.x - s.len / 2 + (pc.a + pc.b) / 2 * s.len + pc.off, y0 = L.roll.y;
    const x = lerp(x0, gx.x, move), y = lerp(y0, gx.y, move), size = lerp(2 * s.R, gx.size, move);
    drawFaceImg(s.imgs[i], x, y, size, easeOutBack(reveal) * 0.999 + 0.001);
  }
  drawParticles(1 / 60);
  buttons = []; drawTopBar('');
  if (el > chopsEnd + 1000) { S.mode = 'plate'; dirty = true; }
}
function drawPlate() {
  const s = slicing, cx = L.ox + L.cw / 2;
  drawSlab(L.grid, 1, B(), 16);
  for (let i = 0; i < NPIECES; i++) {
    const gx = L.grid[i]; drawFaceImg(s.imgs[i], gx.x, gx.y, gx.size);
    ctx.fillStyle = 'rgba(46,30,14,0.78)'; ctx.font = font(11); ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText(String(i + 1), gx.x, gx.y + gx.size / 2 + 4);
  }
  buttons = []; buttonRow([['albumsave', S.saved > performance.now() ? '✓ В альбоме' : '★ В альбом', true], ['back', 'Ещё начинки'], ['new', 'Новый лист']]);
  if (S.saved > performance.now()) dirty = true;
  drawButtons(); drawTopBar(hints.plate);
  if (S.bigPiece >= 0) {
    ctx.fillStyle = 'rgba(23,23,19,0.92)'; ctx.fillRect(0, 0, W, H);
    const img = face(pieceV(S.bigPiece), L.faceSize);
    ctx.fillStyle = '#b8ad95'; ctx.font = font(13); ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
    ctx.fillText(`кусочек ${S.bigPiece + 1} из ${NPIECES} · тапни, чтобы закрыть`, cx, L.faceY - L.faceSize / 2 - 14);
    drawSlab([{ x: cx, y: L.faceY, size: L.faceSize }], 1, B(), 10);
    drawFaceImg(img, cx, L.faceY, L.faceSize);
  }
}

