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

// ── ИКОНКИ-СПРАЙТЫ (issue #104) ─────────────────────────────────────────────
// Чипы рисовались тем же кодом, что и начинки на листе, — то есть вычислялись. Но иконка
// изображает ПРЕДМЕТ («кусок лосося»), а не его укладку, и вот её как раз можно нарисовать
// заранее. Спрайты 40×40 с альфой лежат в play/assets/icons/, сделаны в Draw Things и
// посажены на пиксельную сетку (tools/pixel-icons.py).
//
// Загрузка ленивая и НЕблокирующая: пока картинка не пришла, чип рисуется по-старому, а
// как придёт — просим кадр. Никаких ожиданий: стенд обязан открываться сразу.
const ICONS = {};
function iconImg(kind) {
  let im = ICONS[kind];
  if (im === undefined) {
    im = new Image();
    im.onload = () => { dirty = true; requestFrame(); };
    im.onerror = () => { ICONS[kind] = null; };          // нет файла — молча рисуем по-старому
    im.src = 'assets/icons/' + kind + '.png';
    ICONS[kind] = im;
  }
  return im && im.complete && im.naturalWidth ? im : null;
}
// ПОСЛЕДНИЙ РЯД ПАЛИТРЫ — ОБЩИЙ СЛОТ С КНОПКАМИ ДЕЙСТВИЙ (#157, 02.09). Пока кусок выбран,
// в этом слоте стоят «⟳» и «Убрать», и ряд чипов не рисуется. Пропускать надо не только
// РИСОВАНИЕ, но и запись в `chips`: иначе под кнопкой остались бы живые цели касания, и тап
// по «Убрать» менял бы заодно выбранную начинку.
function drawChips(скрытьПоследний) {
  chips = []; const c = L.chips, ings = uiIngredients(), n = ings.length, gap = 8, size = c.size;
  const perRow = c.perRow || n, rowH = size + (c.labels ? 18 : 6), rowW = perRow * (size + gap) - gap;
  const видимыхРядов = скрытьПоследний ? Math.max(0, c.rows - 1) : c.rows;
  // Подпись шире чипа, а полоса отсекается по своей рамке, поэтому содержимое живёт с отступом
  // pad от краёв: иначе крайняя подпись («Огурец» → «гурец») срезана даже при нулевой прокрутке.
  const pad = c.pad || 0, inner = Math.max(size, c.w - 2 * pad);
  const maxScroll = Math.max(0, rowW - inner); chipScrollX = clamp(chipScrollX, 0, L.chipScroll ? maxScroll : 0);
  ctx.save(); ctx.beginPath(); ctx.rect(c.x - 2, c.y - 4, c.w + 4, видимыхРядов * rowH + 8); ctx.clip();
  const x0 = c.x + pad + (L.chipScroll ? -chipScrollX : Math.max(0, (inner - rowW) / 2));
  ings.forEach((kind, i) => {
    const row = Math.floor(i / perRow), col = i % perRow, x = x0 + col * (size + gap), y = c.y + row * rowH, d = ING[kind], selected = kind === S.sel;
    if (row >= видимыхРядов) return;
    chips.push({ kind, x, y, w: size, h: rowH });
    rr(x, y, size, size, 12); ctx.fillStyle = '#26261f'; ctx.fill();
    if (selected) { ctx.strokeStyle = '#f3e7ca'; ctx.lineWidth = 2.5; ctx.stroke(); }
    ctx.save(); rr(x + 4, y + 4, size - 8, size - 8, 9); ctx.clip();
    const sprite = iconImg(kind);
    if (sprite) {
      // Спрайт вписывается ЦЕЛЫМ множителем и без сглаживания — дробное растяжение вернуло бы
      // мыло, ради борьбы с которым спрайт и рисовался.
      const inner = size - 10, k = Math.max(1, Math.floor(inner / sprite.width)), sz = sprite.width * k;
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(sprite, Math.round(x + (size - sz) / 2), Math.round(y + (size - sz) / 2), sz, sz);
    } else {
      const gw = Math.max(8, (d.wU / 2.6) * (size - 16)), gh = d.dv >= 1 ? size - 16 : (size - 16) * 0.5;
      ctx.translate(x + size / 2, y + size / 2);
      if (d.paint) { ctx.fillStyle = d.color; rr(-gh / 2, -gw / 2, gh, gw, 6); ctx.fill(); } else drawPatchShape(d, -gh / 2, -gw / 2, gh, gw, true);
    }
    ctx.restore();
    if (c.labels) { ctx.fillStyle = selected ? '#f3e7ca' : '#a79d86'; ctx.font = font(11); ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText(chipLabel(kind, size + gap), x + size / 2, y + size + 3); }
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
// «ОЧИСТИТЬ» В ДВА КАСАНИЯ И С ВОЗВРАТОМ (#157, 02.09).
//
// Действие разрушительное и необратимое: история пишется (`pushHistory`), но отмена висела
// ТОЛЬКО на ⌘Z и Backspace — то есть на телефоне, с которого владелец и смотрит игру, отмены
// не было вовсе. Отсюда два предохранителя вместо одного: первое касание взводит на 2,5 с
// (иконка загорается, в подсказке сказано, что будет), второе чистит; после очистки на пять
// секунд выходит плашка «Лист очищен · ↶ Вернуть», и тап по ней возвращает раскладку.
let clearArm = 0, undoNote = 0;
// ОБРАЗЕЦ БАЗЫ НА КНОПКЕ (#158, 02.09) — тем же приёмом, что уже стоит у обёртки: там глиф не
// эмодзи, а кружок цвета самой обёртки, «так видно выбор не читая».
//
// Эмодзи этого не умели и молча врали: 🍥 стояло И у тюмаки, И у футомаки, 🌀 — И у урамаки,
// И у узумаки. Две базы, заведённые в #142 и #145, проверяются сторожем и для игрока не
// существовали: переключившись, он не узнавал, куда попал.
//
// Образец говорит ТРИ вещи разом, и все три — правда из каталога, а не украшение:
//   · РАЗМЕР кружка ∝ √(L·T) — ровно та величина, что задаёт радиус ролла в модели
//     (площадь материала → радиус). Хосомаки мельче футомаки, и это видно до нажатия;
//   · ЦВЕТ кольца — обёртка базы, цвет заливки — её намазка;
//   · УСТРОЙСТВО: у вывернутого рис снаружи, а тёмное внутри; у спирали — виток, а не кольцо.
function рисоватьОбразецБазы(cx, cy, ключ) {
  const b = BASES[ключ], мера = k => Math.sqrt(BASES[k].L * BASES[k].T);
  const макс = Math.max(...uiBases().map(мера)) || 1;
  const R = 5.5 + 6.5 * (мера(ключ) / макс);
  const обёртка = (WRAPPERS[b.wrapKey] || WRAPPERS.nori).color, намазка = b.spread || '#e4ded6';
  ctx.save(); ctx.lineWidth = 2.2;
  if (b.winding === 'spiral') {                       // виток, а не кольцо: у спирали ядра нет
    ctx.strokeStyle = обёртка; ctx.beginPath();
    for (let t = 0; t <= 1.001; t += 0.02) {
      const a = t * TAU * 1.75, r = 1.5 + (R - 1.5) * t;
      const px = cx + r * Math.cos(a), py = cy + r * Math.sin(a);
      t ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.stroke();
  } else if (b.inverted) {                            // рис снаружи, обёртка внутри
    ctx.fillStyle = намазка; ctx.beginPath(); ctx.arc(cx, cy, R, 0, TAU); ctx.fill();
    ctx.fillStyle = обёртка; ctx.beginPath(); ctx.arc(cx, cy, R * 0.52, 0, TAU); ctx.fill();
  } else {
    ctx.fillStyle = намазка; ctx.beginPath(); ctx.arc(cx, cy, R, 0, TAU); ctx.fill();
    ctx.strokeStyle = обёртка; ctx.beginPath(); ctx.arc(cx, cy, R, 0, TAU); ctx.stroke();
  }
  ctx.restore();
}
function drawTopBar(hint) {
  const T0 = SAFE.top, ox = L.ox, cw = L.cw, narrow = cw < 480;
  ctx.font = font(17, 700);
  const заголовокW = 16 + ctx.measureText('Ролльня').width + 12;   // с зазором до первой иконки
  // Обёртка — кнопка-образец: глиф не эмодзи, а кружок цвета самой обёртки, так видно выбор
  // не читая. Перебором, а не списком: раскладку только что перебрали, и лишний ряд сейчас
  // рискован. Настоящий выбор — образцы на циновке вплотную к листу, issue #13.
  // Минимальный стенд (#96): альбом, пазл и выбор обёртки — только с ?full (пазл остаётся,
  // если игрок пришёл по ссылке ?puzzle — тогда FULL_UI и так включён).
  const items = [...(uiBases().length > 1 ? [['base', B().emoji]] : []), ['shape', SHAPES[S.shape].glyph],
                 ...(FULL_UI ? [['album', '★'], ['puzzle', '🧩']] : []),
                 ['preview', '👁'], ['lines', '📐'],
                 // ⚑ РЕЖИМ НАМОТКИ ВИДЕН И ПЕРЕКЛЮЧАЕТСЯ (правка 02.09, просьба владельца).
                 // Три положения: авто (модель решает по охвату начинок) · кольцо · спираль.
                 // Глиф показывает ТЕКУЩЕЕ состояние, а не следующее: ◎ авто, ○ кольцо, ◍ спираль.
                 ['winding', S.winding === 'ring' ? '○' : S.winding === 'spiral' ? '◍' : '◎'],
                 ...(S.mode === 'lay' ? [['clear', '🗑']] : []),
                 ['mute', S.mute ? '🔇' : '🔊']];
  // ⚠ КНОПКА, А НЕ ТОЛЬКО КЛАВИША. Контуры сделаны 31.08 с переключателем на клавише L —
  // и это была ошибка: владелец смотрит игру с телефона, где клавиатуры нет вовсе. Режим
  // существовал, работал и был невидим для того единственного человека, ради кого сделан.
  // Клавиша осталась (на маке ей удобнее), но включать можно и пальцем.
  // ⚑ ОБЁРТКА ВИДНА ВСЕГДА (правка 01.09, просьба владельца). Была спрятана за ?full как
  // «лишний ряд для минимального стенда» — но с появлением узумаки (#142) обёртка перестала
  // быть украшением: у спирали носитель ОМЛЕТ, у маки НОРИ, и это разные блюда, а не разный
  // цвет. Прятать переключатель между ними значит прятать половину модели.
  if (!B().wrapFixed) items.splice(1, 0, ['sheet', '●']);
  if (S.puzzle || S.mode === 'revealed' || S.mode === 'plate') items.splice(3, 0, ['share', '🔗']);
  // ⚑ ИКОНКИ УЖИМАЮТСЯ, А НЕ НАЕЗЖАЮТ НА ЗАГОЛОВОК (02.09, #158). Ширина иконки была
  // константой, и ряд просто рос вправо-влево от неё: с открытием всех шести баз иконок стало
  // восемь, ряд занял 304 px из 393, и «Ролльня» уехала под первую кнопку. Теперь ряд знает,
  // сколько места оставил заголовок, и сужается до 30 px; если и этого мало — заголовок
  // уступает целиком. Обрезанное слово хуже отсутствующего, это уже разбиралось с подписью.
  let шир = narrow ? 34 : 40, зазор = narrow ? 4 : 6;
  while (шир > 30 && заголовокW + items.length * (шир + зазор) > cw) шир--;
  const iconsW = items.length * (шир + зазор);
  const заголовокВлез = заголовокW + iconsW <= cw;
  if (заголовокВлез) {
    ctx.fillStyle = '#f3e7ca'; ctx.font = font(17, 700); ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
    ctx.fillText('Ролльня', ox + 16, 24 + T0);
  }
  // ⚑ ПОДПИСЬ УСТУПАЕТ ИКОНКАМ, А НЕ ОБРЕЗАЕТСЯ (02.09, #157). Она рисовалась всегда и просто
  // резалась рамкой: с седьмой иконкой (🗑) на iPhone 15 Pro от неё оставалось 15 px, и в шапке
  // читалось «Ролльня ст». Обрезанное слово хуже отсутствующего — оно выглядит поломкой.
  // Теперь смотрим, сколько места ОСТАЛОСЬ, и берём ту редакцию, которая в него влезает.
  const свободно = cw - iconsW - 20 - (заголовокВлез ? 92 : 16);
  if (свободно >= 60) {
    ctx.save(); ctx.beginPath(); ctx.rect(ox, T0, cw - iconsW - 20, 50); ctx.clip();
    ctx.fillStyle = '#8d846f'; ctx.font = font(12); ctx.textAlign = 'left';
    const полная = 'стенд · лист → спираль → срез' + ` · срезов: ${S.cuts}`;
    const средняя = 'стенд' + ` · срезов: ${S.cuts}`;
    const текст = ctx.measureText(полная).width <= свободно ? полная
                : ctx.measureText(средняя).width <= свободно ? средняя
                : `срезов: ${S.cuts}`;
    ctx.fillText(текст, ox + (заголовокВлез ? 92 : 16), 25 + T0);
    ctx.restore();
  }
  let x = ox + cw - 12;
  for (const [id, glyph] of items) {
    const w = шир; x -= w; icons.push({ id, x, y: 4 + T0, w, h: 40 });
    rr(x, 6 + T0, w, 36, 10); ctx.fillStyle = ((id === 'preview' && S.preview) || (id === 'lines' && S.lines) || (id === 'puzzle' && S.puzzle) || (id === 'album' && S.mode === 'album') || (id === 'clear' && clearArm > performance.now())) ? '#4a4331' : '#26261f'; ctx.fill();
    ctx.font = id === 'share' ? '16px system-ui' : id === 'album' ? font(19, 600) : id === 'sheet' ? font(22, 700) : '18px system-ui';
    ctx.textAlign = 'center';
    ctx.fillStyle = id === 'album' ? '#e0b25a' : id === 'sheet' ? (WRAPPERS[B().wrapKey] || WRAPPERS.nori).color : '#f3e7ca';
    ctx.globalAlpha = (id === 'preview' && !S.preview) ? 0.45 : 1;
    if (id === 'base') рисоватьОбразецБазы(x + w / 2, 24 + T0, S.base);
    else ctx.fillText(glyph, x + w / 2, 25 + T0);
    ctx.globalAlpha = 1;
    x -= зазор;
  }
  const arrows = S.puzzle && S.mode === 'lay';
  // Имя выбранной обёртки на пару секунд поверх подсказки: на кнопке-образце оно не помещается
  // («Шоколадный блин» — 72,5 px при кнопке 34), а знать, что выбрал, надо.
  if (wrapNote && performance.now() - wrapNoteT < 2600) hint = wrapNote;
  else if (wrapNote) wrapNote = '';
  // Взведённое «Очистить» говорит вслух, что случится, и просит кадр — чтобы через 2,5 с
  // иконка сама погасла, а не осталась гореть до следующего касания.
  if (clearArm > performance.now()) { hint = 'Ещё раз — очистить весь лист'; dirty = true; }
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
  if (undoNote > performance.now() && S.mode === 'lay') {
    const w = 236, h = 36, x0 = ox + cw / 2 - w / 2, y0 = L.top + 8;
    icons.push({ id: 'undo', x: x0, y: y0, w, h });
    rr(x0, y0, w, h, 12); ctx.fillStyle = '#2a2a25'; ctx.fill();
    ctx.strokeStyle = '#4a4331'; ctx.lineWidth = 1; ctx.stroke();
    ctx.font = font(13, 600); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#b8ad95'; ctx.fillText('Лист очищен', x0 + 74, y0 + h / 2);
    ctx.fillStyle = '#e0b25a'; ctx.fillText('↶ Вернуть', x0 + 172, y0 + h / 2);
    dirty = true;
  }
  if (shareNote > performance.now()) { ctx.font = font(13, 600); ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; rr(ox + cw / 2 - 120, L.oy + L.ch - 60, 240, 34, 12); ctx.fillStyle = '#2a2a25'; ctx.fill(); ctx.fillStyle = '#e0b25a'; ctx.fillText('Ссылка на пазл скопирована', ox + cw / 2, L.oy + L.ch - 43); dirty = true; }
}

