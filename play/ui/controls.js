'use strict';
// UI: кнопки, чипы ингредиентов, иконки верхней панели.
//
// Рисуется на том же canvas, DOM здесь нет вовсе. Кнопки собираются в массив buttons на
// каждый кадр и там же ловят попадание — поэтому порядок отрисовки и порядок попаданий
// всегда совпадают.

// ---------------------------------------------------------------- UI: кнопки и чипы
let buttons = [];
function fitText(label, w) {
  for (const px of [15, 13, 12]) { ctx.font = font(px, 600); if (ctx.measureText(label).width <= w) return label; }
  let t = label; while (t.length > 1 && ctx.measureText(t + '…').width > w) t = t.slice(0, -1); return t + '…';
}
function drawButtons() {
  for (const b of buttons) {
    rr(b.x, b.y, b.w, b.h, 12);
    ctx.fillStyle = b.primary ? '#e0b25a' : '#2a2a25'; ctx.fill();
    ctx.strokeStyle = b.dim ? '#332f27' : b.primary ? '#f0cb7d' : '#4d4838'; ctx.lineWidth = 1; ctx.stroke();
    ctx.fillStyle = b.dim ? '#5c5749' : b.primary ? '#171713' : '#efe4cd'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const t = fitText(b.label, b.w - 20);   // fitText выставляет шрифт
    ctx.fillText(t, b.x + b.w / 2, b.y + b.h / 2 + 1);
  }
}
// Ряд кнопок: не больше max в ряд (по умолчанию 3), лишние переносятся; area — где рисовать (по умолчанию нижний ряд).
function buttonRow(list, area) {
  const a = area || L.rowBtn, gap = 10, max = a.max || 3, h = a.h || L.btnH;
  const rows = []; for (let i = 0; i < list.length; i += max) rows.push(list.slice(i, i + max));
  rows.forEach((row, ri) => {
    const wsum = row.reduce((sum, b) => sum + (b[3] || 1), 0), unit = (a.w - gap * (row.length - 1)) / wsum;
    let x = a.x; const y = a.y + ri * (h + 8);
    // Пятый элемент — «нечего делать»: кнопка рисуется тусклой, но остаётся на месте, чтобы
    // ряд не прыгал (история действий, issue #84).
    for (const [id, label, primary, wt, dim] of row) { const w = unit * (wt || 1); buttons.push({ id, label, x, y, w, h, primary, dim }); x += w + gap; }
  });
}
let chips = [], chipScrollX = 0;
function drawChips() {
  chips = []; const c = L.chips, ings = uiIngredients(), n = ings.length, gap = 8, size = c.size;
  const perRow = c.perRow || n, rowH = size + (c.labels ? 18 : 6), rowW = perRow * (size + gap) - gap;
  // Подпись шире чипа, а полоса отсекается по своей рамке, поэтому содержимое живёт с отступом
  // pad от краёв: иначе крайняя подпись («Огурец» → «гурец») срезана даже при нулевой прокрутке.
  const pad = c.pad || 0, inner = Math.max(size, c.w - 2 * pad);
  const maxScroll = Math.max(0, rowW - inner); chipScrollX = clamp(chipScrollX, 0, L.chipScroll ? maxScroll : 0);
  ctx.save(); ctx.beginPath(); ctx.rect(c.x - 2, c.y - 4, c.w + 4, c.rows * rowH + 8); ctx.clip();
  const x0 = c.x + pad + (L.chipScroll ? -chipScrollX : Math.max(0, (inner - rowW) / 2));
  ings.forEach((kind, i) => {
    const row = Math.floor(i / perRow), col = i % perRow, x = x0 + col * (size + gap), y = c.y + row * rowH, d = ING[kind], selected = kind === S.sel;
    chips.push({ kind, x, y, w: size, h: rowH });
    rr(x, y, size, size, 12); ctx.fillStyle = '#26261f'; ctx.fill();
    if (selected) { ctx.strokeStyle = '#f3e7ca'; ctx.lineWidth = 2.5; ctx.stroke(); }
    ctx.save(); rr(x + 4, y + 4, size - 8, size - 8, 9); ctx.clip();
    const gw = Math.max(8, (d.wU / 2.6) * (size - 16)), gh = d.dv >= 1 ? size - 16 : (size - 16) * 0.5;
    ctx.translate(x + size / 2, y + size / 2);
    if (d.paint) { ctx.fillStyle = d.color; rr(-gh / 2, -gw / 2, gh, gw, 6); ctx.fill(); } else drawPatchShape(d, -gh / 2, -gw / 2, gh, gw, true);
    ctx.restore();
    if (c.labels) { ctx.fillStyle = selected ? '#f3e7ca' : '#a79d86'; ctx.font = font(11); ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText(d.name, x + size / 2, y + size + 3); }
  });
  ctx.restore();
  if (L.chipScroll) {   // край прокрутки: гасим и ставим шеврон — и только с той стороны, где чипы ЕСТЬ
    const fw = 26;
    for (const [xx, dir, more] of [[c.x, 1, chipScrollX > 0.5], [c.x + c.w, -1, chipScrollX < maxScroll - 0.5]]) {
      if (!more) continue;
      const gr = ctx.createLinearGradient(xx, 0, xx + dir * fw, 0);
      gr.addColorStop(0, '#171713'); gr.addColorStop(0.5, 'rgba(23,23,19,0.86)'); gr.addColorStop(1, 'rgba(23,23,19,0)');
      ctx.fillStyle = gr; ctx.fillRect(Math.min(xx, xx + dir * fw), c.y - 4, fw, c.rows * rowH + 8);
      ctx.fillStyle = '#c8bda2'; ctx.font = font(17, 700); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(dir > 0 ? '‹' : '›', xx + dir * 7, c.y + (c.rows * rowH - (c.labels ? 18 : 6)) / 2);
    }
  }
  if (!c.labels) { ctx.fillStyle = '#f3e7ca'; ctx.font = font(12); ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText(ING[S.sel].name, c.x + c.w / 2, c.y + c.rows * rowH + 2); }
}
let icons = [];
let wrapNote = '', wrapNoteT = 0;   // имя выбранной обёртки: на кнопке оно не помещается
function drawTopBar(hint) {
  const T0 = SAFE.top, ox = L.ox, cw = L.cw, narrow = cw < 480;
  ctx.fillStyle = '#f3e7ca'; ctx.font = font(17, 700); ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  ctx.fillText('Ролльня', ox + 16, 24 + T0);
  // Обёртка — кнопка-образец: глиф не эмодзи, а кружок цвета самой обёртки, так видно выбор
  // не читая. Перебором, а не списком: раскладку только что перебрали, и лишний ряд сейчас
  // рискован. Настоящий выбор — образцы на циновке вплотную к листу, issue #13.
  // Минимальный стенд (#96): альбом, пазл и выбор обёртки — только с ?full (пазл остаётся,
  // если игрок пришёл по ссылке ?puzzle — тогда FULL_UI и так включён).
  const items = [...(uiBases().length > 1 ? [['base', B().emoji]] : []), ['shape', SHAPES[S.shape].glyph],
                 ...(FULL_UI ? [['album', '★'], ['puzzle', '🧩']] : []),
                 ['preview', '👁'], ['mute', S.mute ? '🔇' : '🔊']];
  if (FULL_UI && !B().wrapFixed) items.splice(1, 0, ['sheet', '●']);
  if (S.puzzle || S.mode === 'revealed' || S.mode === 'plate') items.splice(3, 0, ['share', '🔗']);
  const iconsW = items.length * ((narrow ? 34 : 40) + (narrow ? 4 : 6));
  ctx.save(); ctx.beginPath(); ctx.rect(ox, T0, cw - iconsW - 20, 50); ctx.clip();
  ctx.fillStyle = '#8d846f'; ctx.font = font(12); ctx.textAlign = 'left'; ctx.fillText((narrow ? 'стенд' : 'стенд · лист → спираль → срез') + ` · срезов: ${S.cuts}`, ox + 92, 25 + T0);
  ctx.restore();
  let x = ox + cw - 12;
  for (const [id, glyph] of items) {
    const w = narrow ? 34 : 40; x -= w; icons.push({ id, x, y: 4 + T0, w, h: 40 });
    rr(x, 6 + T0, w, 36, 10); ctx.fillStyle = ((id === 'preview' && S.preview) || (id === 'puzzle' && S.puzzle) || (id === 'album' && S.mode === 'album')) ? '#4a4331' : '#26261f'; ctx.fill();
    ctx.font = id === 'share' ? '16px system-ui' : id === 'album' ? font(19, 600) : id === 'sheet' ? font(22, 700) : '18px system-ui';
    ctx.textAlign = 'center';
    ctx.fillStyle = id === 'album' ? '#e0b25a' : id === 'sheet' ? (WRAPPERS[B().wrapKey] || WRAPPERS.nori).color : '#f3e7ca';
    ctx.globalAlpha = (id === 'preview' && !S.preview) ? 0.45 : 1; ctx.fillText(glyph, x + w / 2, 25 + T0); ctx.globalAlpha = 1;
    x -= narrow ? 4 : 6;
  }
  const arrows = S.puzzle && S.mode === 'lay';
  // Имя выбранной обёртки на пару секунд поверх подсказки: на кнопке-образце оно не помещается
  // («Шоколадный блин» — 72,5 px при кнопке 34), а знать, что выбрал, надо.
  if (wrapNote && performance.now() - wrapNoteT < 2600) hint = wrapNote;
  else if (wrapNote) wrapNote = '';
  if (hint) {
    ctx.fillStyle = '#b8ad95'; ctx.font = font(13); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const maxW = cw - 24 - (arrows ? 88 : 0), parts = hint.split(' · '), lines = []; let cur = '';
    for (const pt of parts) { const t = cur ? cur + ' · ' + pt : pt; if (cur && ctx.measureText(t).width > maxW) { lines.push(cur); cur = pt; } else cur = t; }
    if (cur) lines.push(cur);
    const shown = lines.slice(0, L.hint2 ? 2 : 1);
    shown.forEach((ln, i) => { let t = ln; while (t.length > 4 && ctx.measureText(t).width > maxW) t = t.slice(0, -2) + '…'; ctx.fillText(t, ox + cw / 2, 49 + T0 + i * 16); });
  }
  if (arrows) {
    const y = 49 + T0;
    icons.push({ id: 'lvprev', x: ox + 4, y: y - 22, w: 44, h: 44 }, { id: 'lvnext', x: ox + cw - 48, y: y - 22, w: 44, h: 44 });
    ctx.fillStyle = '#efe4cd'; ctx.font = font(22, 600); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('‹', ox + 26, y); ctx.fillText('›', ox + cw - 26, y);
  }
  if (shareNote > performance.now()) { ctx.font = font(13, 600); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; rr(ox + cw / 2 - 120, L.oy + L.ch - 60, 240, 34, 12); ctx.fillStyle = '#2a2a25'; ctx.fill(); ctx.fillStyle = '#e0b25a'; ctx.fillText('Ссылка на пазл скопирована', ox + cw / 2, L.oy + L.ch - 43); dirty = true; }
}

