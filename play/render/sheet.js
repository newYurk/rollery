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
  // В пиксельном режиме текстура считается в PIX раз крупнее и растягивается без сглаживания:
  // фотографический рис рядом с блочными начинками спорил сильнее, чем помогал (31.08).
  const cw = Math.round(w * DPR / (PIX || 1)), ch = Math.round(h * DPR / (PIX || 1)),
        key = S.base + '|' + (B().wrapKey || '-') + '|' + (S.turns || '-') + '|' + cw + 'x' + ch + (PIX ? '|p' : '');
  if (spreadTex && spreadTexKey === key) return spreadTex;
  const b = B(), base = b.spreadRgb, c = document.createElement('canvas'); c.width = cw; c.height = ch;
  const x = c.getContext('2d'); const img = x.createImageData(cw, ch); const d = img.data;
  // Тот же LOD, что на срезе (зерно тут меряется по ширине листа: cw device-px на Wv/GRAIN зёрен),
  // но с потолком 0,5. ПОЧЕМУ потолок: сверху видно ЦЕЛЫЕ зёрна в постели, а борозда между зёрнами —
  // это признак РЕЗА, её в полную силу видно только на срезе. На полную амплитуду лист превращался
  // в мозаику (снято на скриншоте: 54 зерна поперёк, каждое с бороздой) и спорил с начинками.
  // ⚠ Порог в АРТ-пикселях: в пиксельном режиме текстура считается в PIX раз мельче, и по
  // старому порогу зерно гасло совсем — лист становился ровным кремовым полем (та же ловушка,
  // что уже чинилась в срезе, issue #104). Умножаем обратно на PIX.
  const sheetLod = Math.min(0.5, clamp((cw * (PIX || 1) / (b.Wv / GRAIN) - 6) / 8));
  for (let j = 0; j < ch; j++) for (let i = 0; i < cw; i++) {
    const col = spreadColor(i / cw * b.Wv / GRAIN, j / ch * sheetLen(b) / GRAIN, b, undefined, undefined, sheetLod), k = (j * cw + i) * 4;
    let r0 = base[0] + (col[0] - base[0]) * 0.7, g0 = base[1] + (col[1] - base[1]) * 0.7, b0 = base[2] + (col[2] - base[2]) * 0.7;
    if (PIX) { const q = pixSnap(r0, g0, b0); r0 = q[0]; g0 = q[1]; b0 = q[2]; }
    d[k] = r0; d[k + 1] = g0; d[k + 2] = b0; d[k + 3] = 255;
  }
  x.putImageData(img, 0, 0); spreadTex = c; spreadTexKey = key;
  return c;
}
// ── СИСТЕМА КООРДИНАТ ЛИСТА (#23) ─────────────────────────────────────────────
// Вся математика листа ниже написана в ЛОГИЧЕСКОМ пространстве: x вправо = ось v,
// y вниз = убывание u (u = 1 сверху). Пока лист лежит осью u по вертикали
// (L.sheet.uAxis === 'y'), логическое пространство совпадает с экранным и всё ниже —
// тождество. Когда лист повёрнут ('x'), между ними встаёт ЧИСТЫЙ ПОВОРОТ на ±90°
// (не зеркало: зеркало перевернуло бы фактуры начинок; и изометрия: HIT_PAD в
// пикселях остаётся честным ореолом). Направление поворота задаёт SHEET_U0 — с какой
// стороны экрана окажется начало скрутки u = 0; выбор за владельцем (issue #23).
//
// Правило для нового кода: геометрия листа пишется по SB() и рисуется внутри
// sheetPush()/sheetPop(); ввод переводится через toSheet(); подписи, которые должны
// остаться горизонтальными, рисуются через unrot(). L.sheet.{x,y,w,h} — ЭКРАННАЯ
// рамка, к осям листа она отношения больше не имеет.
const SHEET_U0 = 'left';   // 'left' | 'right' — вступает в силу только при uAxis 'x'
function SB() { const s = L.sheet; return { x: s.x, y: s.y, w: s.lenV, h: s.lenU }; }
const sheetAng = () => L.sheet.uAxis !== 'x' ? 0 : (SHEET_U0 === 'left' ? Math.PI / 2 : -Math.PI / 2);
// Экран → логическое (для ввода) и обратно (для подписей и якорей вне трансформа).
function toSheet(x, y) {
  const s = L.sheet; if (s.uAxis !== 'x') return { x, y };
  return SHEET_U0 === 'left'
    ? { x: s.x + (y - s.y), y: s.y + (s.x + s.lenU - x) }    // экран ← поворот +90°
    : { x: s.x + (s.y + s.lenV - y), y: s.y + (x - s.x) };   // экран ← поворот −90°
}
function toScreen(px, py) {
  const s = L.sheet; if (s.uAxis !== 'x') return { x: px, y: py };
  return SHEET_U0 === 'left'
    ? { x: s.x + s.lenU - (py - s.y), y: s.y + (px - s.x) }
    : { x: s.x + (py - s.y), y: s.y + s.lenV - (px - s.x) };
}
function sheetPush() {
  ctx.save(); const s = L.sheet; if (s.uAxis !== 'x') return;
  if (SHEET_U0 === 'left') { ctx.translate(s.x + s.lenU, s.y); ctx.rotate(Math.PI / 2); }
  else { ctx.translate(s.x, s.y + s.lenV); ctx.rotate(-Math.PI / 2); }
  ctx.translate(-s.x, -s.y);
}
function sheetPop() { ctx.restore(); }
// Подпись внутри трансформа, но горизонтальная: якорь едет с листом, текст — нет.
function unrot(px, py, fn) { ctx.save(); ctx.translate(px, py); ctx.rotate(-sheetAng()); fn(); ctx.restore(); }

// ── ВИД СВЕРХУ: РИСУЕМ ТЕЛО, А НЕ КАРТИНКУ (issue #105) ─────────────────────
// Здесь больше НЕТ собственного описания того, как выглядит начинка. Раньше их было два:
// drawPatchShape рисовала градиентом с полосками, её пиксельный двойник — ступеньками
// светлоты, и обе ничего не знали о patchColor, которая красит срез. Три описания одного
// вещества расходились, и на листе кусок выглядел не тем, чем оказывался в разрезе.
// Теперь вид сверху ВЫВОДИТСЯ: спрашиваем у тела (geometry.js) вещество и свет в каждой
// точке и складываем из ответов картинку. Стиль — единственное, что решается тут, и решается
// он ОДНИМ числом: размером клетки. Крупная клетка без сглаживания — пиксель-арт; мелкая
// со сглаживанием — гладкий вид. Чтобы сменить стиль, переписывать нечего.
const TOP_CACHE = new Map();

// Спрайт куска размером cols×rows клеток. Кэш нужен: лист перерисовывается на каждое
// движение мыши, а спрайт зависит только от вида начинки и размера — от кадра к кадру он тот же.
function pieceTopSprite(p, d, wPx, hPx, cell) {
  const cols = Math.max(2, Math.round(wPx / cell)), rows = Math.max(2, Math.round(hPx / cell));
  const key = `${d.tex}|${d.rgb}|${cols}|${rows}|${((p && p.phase) || 0).toFixed(2)}`;
  const hit = TOP_CACHE.get(key);
  if (hit) return hit;

  const cv = document.createElement('canvas');
  cv.width = cols; cv.height = rows;
  const g = cv.getContext('2d'), img = g.createImageData(cols, rows), data = img.data;
  // Кусок длиннее, чем шире: ВДОЛЬ (lv) — большая сторона, ПОПЕРЁК (lu) — меньшая.
  const horiz = cols >= rows;
  const nAlong = horiz ? cols : rows, nAcross = horiz ? rows : cols;
  const pp = p || { phase: 0 };

  for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) {
    const along = horiz ? i : j, across = horiz ? j : i;
    const lu = nAcross > 1 ? across / (nAcross - 1) - 0.5 : 0;   // −0.5…0.5 поперёк
    const lv = nAlong > 1 ? along / (nAlong - 1) : 0.5;          // 0…1 вдоль
    // Кромка — это БОКОВЫЕ ГРАНИ тела, которые и правда видно, когда смотришь сверху.
    // Ближняя (нижняя) грань темнее дальней: свет падает с той стороны.
    // ⚠ ГРАНИ РИСУЮТСЯ, ТОЛЬКО ЕСЛИ КУСКУ ЕСТЬ ЧЕМ ИХ ПОКАЗАТЬ. Правка 31.08 по замечанию
    // владельца: «креветка выглядит коричневой». Замер объяснил почему. Кромка занимает
    // РОВНО ОДНУ клетку с каждой стороны, а куски тонкие: лосось на листе — 3 клетки поперёк,
    // креветка — 2. У лосося две трети куска оказывались боковой гранью, а у креветки
    // ВЕРХА НЕ БЫЛО ВОВСЕ: обе клетки — грани, одна из них ×0,62. Дальше пиксельная палитра
    // сажала потемневший розовый на ближайшую ступень, и та оказывалась коричневой
    // (#f4a48c × 0,55 = #865a4d). Замер с холста: у лосося #321d16 на 240 пикселях из 576.
    // Кромка задумана как ТОНКАЯ подсказка объёма, а не как сам кусок. Порог: грань имеет
    // смысл, когда после неё остаётся хотя бы одна клетка верха с каждой стороны.
    // Порог 6, а не 4: при четырёх клетках поперёк две из них — грани, то есть ПОЛОВИНА куска.
    // Кромка должна быть подсказкой объёма, а не самим куском; оставляем её, когда после
    // двух граней остаётся хотя бы четыре клетки верха.
    const есть_грани = nAcross >= 6, есть_торцы = nAlong >= 6;
    const near = есть_грани && across === nAcross - 1, far = есть_грани && across === 0;
    const cap = есть_торцы && (along === 0 || along === nAlong - 1);
    // И ближняя грань посветлела: 0,62 задумывалось как «в тени», но на палитре из четырёх
    // ступеней это прыжок через ступень вниз, а 0,78 попадает в свою же вторую ступень.
    const c = near ? pieceSideColor(pp, d, lu, lv, i, j, 0.78)
            : far  ? pieceSideColor(pp, d, lu, lv, i, j, 1.22)
            : cap  ? pieceSideColor(pp, d, lu, lv, i, j, 0.90)
            :        pieceTopColor(pp, d, lu, lv, i, j);
    const o = (j * cols + i) * 4;
    data[o] = c[0]; data[o + 1] = c[1]; data[o + 2] = c[2]; data[o + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  if (TOP_CACHE.size > 96) TOP_CACHE.clear();     // размеры меняются с масштабом — не копим
  TOP_CACHE.set(key, cv);
  return cv;
}

// Фигура патча в ЛОГИЧЕСКИХ координатах листа (см. блок выше): x, y — верхний левый угол;
// w — вдоль v, h — вдоль u. p нужен для фазы фактуры и может отсутствовать (иконки в панели).
// ВЕКТОРНЫЙ КОНТУР ПОВЕРХ ПИКСЕЛЕЙ — отладка, клавиша L (идея владельца 31.08).
// Пиксельная сетка округляет край куска до клетки, и на глаз не видно, где граница проходит
// НА САМОМ ДЕЛЕ. Контур рисуется по настоящим координатам, дробным: расхождение с пиксельной
// кромкой и есть та ошибка округления, которую хотелось увидеть. Не арт и не часть модели —
// поэтому вне слепка и по умолчанию выключен.
function strokeOutline(x, y, w, h) {
  ctx.save();
  ctx.setLineDash([]); ctx.lineJoin = 'miter'; ctx.lineCap = 'butt';
  ctx.shadowColor = 'transparent';
  ctx.strokeStyle = 'rgba(255,60,120,0.95)'; ctx.lineWidth = 1;
  ctx.strokeRect(x + 0.5, y + 0.5, w - 1, h - 1);
  ctx.restore();
}

function drawPatchShape(d, x, y, w, h, flat, p) {
  const cell = PIX || 2;
  const spr = pieceTopSprite(p, d, w, h, cell);
  ctx.save();
  ctx.imageSmoothingEnabled = !PIX;
  if (PIX) {
    // Тень тоже по сетке. Размытая тень вокруг цельного спрайта сразу выдаёт, что это
    // картинка поверх пикселей: в 16-битной графике тень — сдвинутый силуэт, а не градиент.
    ctx.shadowBlur = 0; ctx.shadowOffsetX = PIX; ctx.shadowOffsetY = PIX;
    // Прижать к сетке арт-пикселей: иначе спрайт ложится между клетками, кромка мылится,
    // и весь смысл пиксельного режима теряется — клетка должна быть видна как клетка.
    const x0 = Math.round(x / PIX) * PIX, y0 = Math.round(y / PIX) * PIX;
    ctx.drawImage(spr, x0, y0, spr.width * PIX, spr.height * PIX);
  } else ctx.drawImage(spr, x, y, w, h);
  ctx.restore();
}

function patchRect(p) {
  const m = dims(p), s = SB();
  return { x: s.x + (p.v - m.dv / 2) * s.w, y: s.y + (1 - p.u - m.du / 2) * s.h, w: m.dv * s.w, h: m.du * s.h };
}
// Экранная трансформация повёрнутого патча: центр, угол и размеры в пикселях (лист анизотропен: px/единица разные по осям).
function patchScreen(p) {
  const m = dims(p), b = B(), s = SB(), Lu = sheetLen(b), rot = p.rot || 0, c = Math.cos(rot), sn = Math.sin(rot);
  const pxV = s.w / b.Wv, pxU = s.h / Lu, w = m.du * Lu, len = m.dv * b.Wv;
  const cx = s.x + p.v * s.w, cy = s.y + (1 - p.u) * s.h;
  const ang = Math.atan2(sn * pxU, c * pxV);   // ось длины патча: (dv, du) = (cos, -sin) → экран (x вправо, y вниз = -u)
  const lenPx = len * Math.hypot(c * pxV, sn * pxU), wPx = w * Math.hypot(sn * pxV, c * pxU);
  return { cx, cy, ang, lenPx, wPx };
}
// z0 — высота патча в стопке; она ЖИВЁТ В МОДЕЛИ (buildModel считает restack на своей копии
// и вход не мутирует), поэтому вызывающий передаёт её сюда, а не читает из самого патча.
function drawPatchTop(p, alpha = 1, z0 = 0) {
  const d = ING[p.kind], m = dims(p), s = SB();
  if (p.rot) {
    const t = patchScreen(p);
    ctx.save(); ctx.globalAlpha = alpha * (p.kind === 'nori' ? 0.82 : d.paint ? 0.92 : 1);
    ctx.shadowColor = d.paint ? 'transparent' : 'rgba(0,0,0,0.35)'; ctx.shadowBlur = 4 + z0 * 6; ctx.shadowOffsetY = 2 + z0 * 3;
    ctx.translate(t.cx, t.cy); ctx.rotate(t.ang);
    if (d.paint) { ctx.fillStyle = d.color; rr(-t.lenPx / 2, -t.wPx / 2, t.lenPx, t.wPx, 3); ctx.fill(); }
    else drawPatchShape(d, -t.lenPx / 2, -t.wPx / 2, t.lenPx, t.wPx, false, p);
    if (S.lines) strokeOutline(-t.lenPx / 2, -t.wPx / 2, t.lenPx, t.wPx);
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
    const r = patchRect(p); drawPatchShape(d, r.x, r.y, r.w, r.h, false, p);
    if (S.lines) strokeOutline(r.x, r.y, r.w, r.h);
  }
  ctx.restore();
}
// vert — прутья вертикально: у настоящей макису прутья ПОПЕРЁК направления скрутки, поэтому
// при повёрнутом листе (#23, скрутка по горизонтали) циновка под листом рисуется с vert=true.
// Функция общая с доской реза — там ролл всегда горизонтален и флаг не передаётся.
function drawMat(x, y, w, h, r = 14, b = B(), vert = false) {
  rr(x, y, w, h, r); ctx.fillStyle = b.mat; ctx.fill();
  ctx.save(); rr(x, y, w, h, r); ctx.clip();
  ctx.strokeStyle = b.matLine; ctx.lineWidth = 1.2;
  if (vert) for (let xx = x + 3; xx < x + w; xx += 7) { ctx.beginPath(); ctx.moveTo(xx, y); ctx.lineTo(xx, y + h); ctx.stroke(); }
  else for (let yy = y + 3; yy < y + h; yy += 7) { ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x + w, yy); ctx.stroke(); }
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
function drawRollBody(xc, yc, R, len, pieces, squash = 1, alpha = 1, axis = 'h') {
  const b = B(), wr = b.wrapperRgb;
  ctx.save(); ctx.globalAlpha = alpha;
  ctx.translate(xc, yc);
  if (axis === 'v') {
    // Вертикальный валик (повёрнутый лист, #23). Рисовать его внутри поворота листа нельзя:
    // градиент света повернулся бы вместе с геометрией, и блик лёг бы сбоку при тенях сверху.
    // Здесь свой свет: блик у левой образующей, тень падает вправо — на ещё не скрученный лист.
    ctx.scale(squash, 1);
    ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.beginPath(); ctx.ellipse(R + 8, 0, R * 0.35, len / 2 + 6, 0, 0, TAU); ctx.fill();
    const gv = ctx.createLinearGradient(-R, 0, R, 0);
    gv.addColorStop(0, rgbCss(shade(wr, 0.55))); gv.addColorStop(0.28, rgbCss(mix(wr, [255, 255, 255], 0.22)));
    gv.addColorStop(0.55, rgbCss(wr)); gv.addColorStop(1, rgbCss(shade(wr, 0.4)));
    for (const pc of pieces) {
      const y0 = -len / 2 + pc.a * len + pc.off, h = (pc.b - pc.a) * len;
      ctx.fillStyle = gv; rr(-R, y0, 2 * R, h, 6); ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.35)'; ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.10)'; rr(-R * 0.62, y0 + 4, R * 0.22, h - 8, 4); ctx.fill();
    }
    ctx.restore(); return;
  }
  ctx.scale(1, squash);
  // тень
  ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.beginPath(); ctx.ellipse(0, R + 8, len / 2 + 6, R * 0.35, 0, 0, TAU); ctx.fill();
  const g = ctx.createLinearGradient(0, -R, 0, R);
  g.addColorStop(0, rgbCss(shade(wr, 0.55))); g.addColorStop(0.28, rgbCss(mix(wr, [255, 255, 255], 0.22)));
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
// Силуэт картинки, залитый одним тёмным цветом, — для пиксельной тени. Кешируется: срез
// меняется редко, а рисуется каждый кадр.
const _silCache = new Map();
function pixSilhouette(img) {
  let s = _silCache.get(img);
  if (!s) {
    if (_silCache.size > 40) _silCache.clear();
    s = document.createElement('canvas'); s.width = img.width; s.height = img.height;
    const c = s.getContext('2d');
    c.imageSmoothingEnabled = false; c.drawImage(img, 0, 0);
    c.globalCompositeOperation = 'source-in'; c.fillStyle = '#0d0c0a';
    c.fillRect(0, 0, s.width, s.height);
    _silCache.set(img, s);
  }
  return s;
}
// `безТени` — для отладочного окна «что внутри»: там срез растянут почти на весь лист, и
// тень съедала бы поле, которое нужнее под сам рисунок (решение владельца 31.08).
// Линии границ поверх среза. Считаются один раз на картинку и живут на ней же — картинка
// уже кеширована по ключу модели, значит и линии пересчитываются ровно тогда, когда надо.
function strokeSliceLines(img, size) {
  if (!img._m) return;
  if (!img._lines) img._lines = sliceLines(img._m, img._v);
  const R = size / 2;
  ctx.save();
  ctx.lineWidth = 1; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  for (const { петли, code } of img._lines) {
    // ЦВЕТ ПО МАТЕРИАЛУ — то, чего лучевой приём дать не мог: он строил линии, не зная,
    // ЧЬЯ это граница. Обход ячеек идёт по маске одного класса, поэтому знает всегда.
    //
    // ⚑ ТРИ ЯВНО РАЗНЫХ ТОНА (правка 01.09 по просьбе владельца: «я хочу видеть разными
    // цветами линии»). Прежде рис и обёртка были двумя оттенками одного голубовато-зелёного
    // и на срезе не различались. Теперь тона разведены по кругу: начинки розовые, обёртка
    // голубая, рис янтарный — и каждый выбран так, чтобы читаться на СВОЁМ фоне. Голубой
    // берётся поверх тёмной нори по краю, янтарный — поверх белого риса, розовый — поверх
    // цветных начинок. Белую линию по белому рису и зелёную по зелёной нори не видно.
    ctx.strokeStyle = code === 1 ? 'rgba(255,170,50,0.75)'      // рис — янтарный
                    : code === 2 ? 'rgba(80,225,255,0.95)'      // обёртка — голубой
                    : 'rgba(255,60,120,0.95)';                  // начинки — розовый
    for (const петля of петли) {
      ctx.beginPath();
      петля.forEach(([x, y], i) => (i ? ctx.lineTo(x * R, y * R) : ctx.moveTo(x * R, y * R)));
      ctx.closePath();          // петля замкнута по построению — замыкаем и на холсте
      ctx.stroke();
    }
  }
  ctx.restore();
}
function drawFaceImg(img, x, y, size, scaleX = 1, alpha = 1, безТени = false) {
  ctx.save(); ctx.globalAlpha = alpha; ctx.translate(x, y); ctx.scale(Math.max(0.01, scaleX), 1);
  if (безТени) {
    if (PIX) { const q = v => Math.round(v / PIX) * PIX, sz = Math.max(PIX, q(size));
      ctx.imageSmoothingEnabled = false; ctx.drawImage(img, q(-sz / 2), q(-sz / 2), sz, sz); }
    else ctx.drawImage(img, -size / 2, -size / 2, size, size);
    if (S.lines) strokeSliceLines(img, size);
    ctx.restore(); return;
  }
  if (PIX) {
    // Пиксельный режим: размытые тени — единственный источник мыла вокруг готовой картинки,
    // поэтому вместо них СМЕЩЁННАЯ КОПИЯ силуэта (так тень делали на приставках), позиция и
    // размер прижаты к сетке арт-пикселей, сглаживание при выводе выключено (issue #104).
    const q = v => Math.round(v / PIX) * PIX;
    const sz = Math.max(PIX, q(size)), x0 = q(-sz / 2), y0 = q(-sz / 2);
    ctx.imageSmoothingEnabled = false;
    // ⚠ ТЕНЬ — СПЛОШНОЙ СИЛУЭТ, А НЕ КОПИЯ КАРТИНКИ. Первая редакция рисовала со смещением сам
    // срез вполупрозрачности — и он читался как ПРИЗРАК второго ролла, а не как тень
    // (владелец 31.08 увидела внизу непонятный артефакт — будто ролл обёрнут ещё раз). Силуэт
    // получается заливкой по маске картинки: source-in красит только непрозрачные точки.
    const sil = pixSilhouette(img);
    ctx.globalAlpha = alpha * 0.55; ctx.drawImage(sil, x0 + PIX, y0 + 2 * PIX, sz, sz);
    ctx.globalAlpha = alpha;        ctx.drawImage(img, x0, y0, sz, sz);
    // ⚠ Линия кладётся по размеру ВЫВОДА (sz), а не по запрошенному size: в пиксельном режиме
    // картинка прижата к сетке и может быть чуть крупнее. Иначе контур не совпал бы с тем,
    // что нарисовано, — и показывал бы не ошибку модели, а мою ошибку в наложении.
    if (S.lines) strokeSliceLines(img, sz);
    ctx.restore(); return;
  }
  ctx.shadowColor = 'rgba(0,0,0,0.5)'; ctx.shadowBlur = 18; ctx.shadowOffsetY = 8;
  ctx.drawImage(img, -size / 2, -size / 2, size, size);
  // контактная тень: узкий тёмный ореол по силуэту — граница светлой обёртки на светлой доске
  ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = 3; ctx.shadowOffsetY = 1;
  ctx.drawImage(img, -size / 2, -size / 2, size, size);
  if (S.lines) { ctx.shadowColor = 'transparent'; strokeSliceLines(img, size); }
  ctx.restore();
}

