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
  // ⚑ ПОСТОЯННАЯ ПОДСКАЗКА НА ЛИСТЕ СНЯТА 02.09 по просьбе владельца («можно подсказку про
  // скручивание и раскладку убрать пока»). Пустая строка, а не удалённый ключ: подсказку
  // спрашивают три ветки в drawLay, и вернуть её — это вписать текст обратно сюда.
  lay: '', layR: '', layL: '',
  layMove: 'Тащи · вытащи за лист — убрать',
  // ⚑ «В НОРИ» УБРАНО ИЗ ПОДСКАЗКИ (02.09). Кнопки «Кусок в нори» нет с 31.08 (canWrap = false
  // ниже), а подсказка продолжала обещать приём, которого игрок сделать не может.
  laySel: 'Поворот меняет рисунок в кусочках',
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
      // ОКОШКО «ЧТО ВНУТРИ» — КРУГЛАЯ ВРЕЗКА В УГЛУ ЛИСТА.
      //
      // Две правки 31.08, обе по замечаниям владельца. Первая: тень в пиксельном режиме —
      // это смещённый силуэт на (PIX, 2·PIX), а поле подложки было плоские 7 px, и тень
      // вываливалась на рис. Вторая: попытка развести их отступом дала кривой зазор справа —
      // кружок повис не пойми где.
      //
      // Правильно — не разводить, а ОБРЕЗАТЬ: тень принадлежит окошку и не должна из него
      // торчать, как не торчит ничто из иллюминатора. Кружок при этом садится в угол плотно
      // и с равным полем с обеих сторон, то есть выглядит поставленным, а не сдвинутым.
      // ОТЛАДОЧНОЕ ОКНО «ЧТО ВНУТРИ» — крупный срез в правом верхнем углу листа.
      //
      // ⚑ Это инструмент проверки, а не элемент игры (решение владельца 31.08): она сверяет
      // глазами, то ли легло, что положили, и туда ли попало. Отсюда все решения ниже:
      //   • срез занимает почти весь лист по меньшей стороне — разглядеть важнее, чем не мешать;
      //   • ТЕНИ НЕТ. Она съедала поле, которое нужнее под сам рисунок, и нигде больше в этом
      //     окне не работает: тонкое кольцо циновки и так отделяет срез от риса;
      //   • включается и выключается кнопкой-глазом; когда сверка станет не нужна — снять целиком.
      const fs = Math.round(Math.min(s.w, s.h) * 0.62);
      const поле = 6, дШир = fs + 2 * поле, поля = 10;
      const x = s.x + s.w - дШир / 2 - поля, y = s.y + дШир / 2 + поля;
      drawMat(x - дШир / 2, y - дШир / 2, дШир, дШир, дШир / 2);
      drawFaceImg(face(0.5, fs), x, y, fs, 1, 1, true);
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
// РАДИУС РОЛЛА ПО ХОДУ ПРОТЯЖКИ — ПО ПЛОЩАДИ НАМОТАННОГО, А НЕ ПО МАКСИМУМУ ВИТКА.
//
// ⚠ Здесь стоял `windRout(0.5, p·L, …)`, то есть МАКСИМУМ радиуса по всем угловым бинам.
// Владелец 31.08: «ролл сматывается скачком». Так и было, и замер это показал числом: доля
// финального радиуса шла 0 → 0,33 → 0,46 → **1,00** между 20 % и 30 % протяжки, дальше не
// менялась вовсе. Причина простая: как только лёг ПЕРВЫЙ бин первого витка, максимум по бинам
// сразу равен «ядро + толщина слоя», а это уже почти финальный радиус. Остальные 70 % тяги
// ролл стоял на месте.
//
// Физически ролл растёт не по максимуму, а по тому, СКОЛЬКО В НЁМ ВЕЩЕСТВА. Это тот же закон,
// которым 31.08 починили ядро (#1) и подворот (#113): размер идёт от площади. До конца сгиба
// растёт ядро (оно сминается), дальше добавляется намотанное.
function rollRadiusAtPull(p, m) {
  const g = m.g, sMax = p * g.L, s0 = g.sStart || 0;
  if (!m.core) return Math.sqrt(Math.max(0, sMax * g.T) / Math.PI);      // спираль без подворота
  if (sMax <= s0) return m.core.R * Math.sqrt(Math.max(0.04, s0 ? sMax / s0 : 1));
  const prof = thicknessProfile(0.5, g, m.list), ds = g.L / (prof.length - 1);
  let A = m.core.A || Math.PI * m.core.R * m.core.R;
  for (let i = 0; i < prof.length; i++) { const s = i * ds; if (s >= s0 && s <= sMax) A += prof[i] * ds; }
  return Math.sqrt(A / Math.PI);
}
function drawLay() {
  // s — ЛОГИЧЕСКАЯ рамка листа (SB): x вправо = v, y вниз = −u. Весь лист рисуется внутри
  // sheetPush()/sheetPop() — при повёрнутом листе (#23) это один общий поворот на ±90°.
  // Экранные элементы (циновка-фон, ручка, полосы предпросмотра, кнопки) остаются снаружи.
  const s = SB(), p = S.rollP, hd = L.handle;
  if (L.sheet.uAxis === 'x') {   // циновка-фон: от ручки сбоку через весь лист, прутья поперёк скрутки
    const x0 = Math.min(hd.x, L.sheet.x - 8), x1 = Math.max(hd.x + hd.w, L.sheet.x + L.sheet.w + 8);
    drawMat(x0, L.sheet.y - 18, x1 - x0, L.sheet.h + 36, 14, B(), true);
  } else drawMat(hd.x, L.sheet.y - 18, hd.w, hd.y + hd.h + 8 - (L.sheet.y - 18));
  sheetPush();
  const yb = s.y + s.h * (1 - p);
  // лист: остаток, ещё не скрученный
  ctx.save(); ctx.beginPath(); ctx.rect(s.x - 8, s.y - 8, s.w + 16, Math.max(0, yb - s.y + 8)); ctx.clip();
  rr(s.x - 5, s.y - 5, s.w + 10, s.h + 10, 6); ctx.fillStyle = B().wrapper; ctx.fill();
  const mdl = getModel(), wd0 = windFor(mdl, 0.5), Lm = mdl.g.L;
  const uClose = wd0.sClose >= 0 ? wd0.sClose / Lm : B().spreadEnd, uEnd = wd0.sEnd < Lm ? wd0.sEnd / Lm : 1;
  const bare = (1 - uClose) * s.h, rimPx = B().spreadEnd < 1 ? RIM_W * s.h : 0;
  // ⚑ БЛИЖНЯЯ ГОЛАЯ ПОЛОСА. Рис начинается не от кромки, а отступив: 「手前2cm位」.
  // Раньше он доходил до самого низа, и лист читался как «полоска нори сверху плюс
  // отдельный прямоугольник риса» — владелец на это и указала («непонятно, как лежит
  // нори»). Полоса маленькая, но именно с неё начинается скрутка, и именно она
  // объясняет окно раскладки: ближе к себе класть нечего, там подворот.
  const nearBare = (B().spreadStart === undefined ? SPREAD_START : B().spreadStart) * s.h;
  ctx.save(); rr(s.x, s.y + bare, s.w, s.h - bare - nearBare, 4); ctx.clip();
  if (PIX) ctx.imageSmoothingEnabled = false;   // растягиваем крупную текстуру ступеньками, а не мылом
  ctx.drawImage(getSpreadTex(s.w, s.h), s.x, s.y, s.w, s.h);
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
    // У ближнего края рис сходит так же: кромка не обрывается стенкой.
    const yn = s.y + s.h - nearBare;
    const gn = ctx.createLinearGradient(0, yn, 0, yn - fade);
    gn.addColorStop(0, B().wrapper); gn.addColorStop(1, rgbCss(B().wrapperRgb, 0));
    ctx.fillStyle = gn; ctx.fillRect(s.x, yn - fade, s.w, fade);
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
  // ⚑ «БУДЕТ СПИРАЛЬ» ВИДНО ДО СКРУТКИ (правка 02.09, просьба владельца).
  //
  // Она сказала: «если добавишь обозначение в тот момент, когда я что-то положила и всё, это
  // перешло уже в спираль, было бы здорово. Хотя я увижу это на срезе, можно и не обозначать».
  // Обозначать надо: на срезе — это ПОСЛЕ, а решение принимается ДО, когда ещё можно подвинуть
  // начинку. Переход считается по охвату (см. buildModel), и игрок должен видеть, что перешёл
  // черту, в тот же миг, а не после скрутки.
  //
  // ⚠ Подпись только у спирали. У кольца молчим: «кольцо» — это обычное дело, а надпись на
  // каждом ролле превращается в шум и перестаёт читаться тогда, когда она важна.
  if (p === 0 && !drag.patch) {
    const mm = getModel();
    if (mm.g.winding === 'spiral') {
      unrot(s.x + s.w - 6, s.y + 14, () => {
        ctx.fillStyle = 'rgba(150,90,30,0.85)'; ctx.font = font(11, 600);
        ctx.textAlign = 'right'; ctx.textBaseline = 'top';
        ctx.fillText('начинка по всему листу — свернётся спиралью', 0, 0);
      });
    }
  }
  ctx.restore();
  sheetPop();
  // Ролл в процессе скрутки — ВНЕ трансформа: у цилиндра свой свет (блик, тень), и внутри
  // поворота листа он лёг бы набок. Позиция фронта переводится в экран через toScreen.
  if (p > 0) {
    const mm = getModel(), R = rollRadiusAtPull(p, mm) * s.h / mm.g.L;
    if (L.sheet.uAxis === 'x') { const c = toScreen(s.x + s.w / 2, yb); drawRollBody(c.x, c.y, R, s.w + 10, [{ a: 0, b: 1, off: 0 }], 1, 1, 'v'); }
    else drawRollBody(s.x + s.w / 2, yb, R, s.w + 10, [{ a: 0, b: 1, off: 0 }]);
  }
  // циновка-ручка: подпись и стрелка — по направлению тяги
  rr(hd.x, hd.y, hd.w, hd.h, 10); ctx.fillStyle = 'rgba(0,0,0,0.12)'; ctx.fill();
  ctx.fillStyle = 'rgba(40,30,20,0.55)'; ctx.font = font(13, 600); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  if (L.sheet.uAxis === 'x') {   // ручка — вертикальная полоса сбоку, текст кладётся вдоль неё
    const arr = SHEET_U0 === 'left' ? '→' : '←', dir = SHEET_U0 === 'left' ? 'вправо' : 'влево';
    let ht = p > 0 ? `ещё… ${arr}` : arr;
    ctx.save(); ctx.translate(hd.x + hd.w / 2, hd.y + hd.h / 2); ctx.rotate(-Math.PI / 2);
    if (ctx.measureText(ht).width > hd.h - 24) ht = `${arr} скрутить`;
    ctx.fillText(ht, 0, 0); ctx.restore();
  } else {
    // Надпись на циновке снята вместе с подсказкой (02.09, просьба владельца). Стрелка
    // осталась: без неё циновка — просто полоса, и потянуть её никто не догадается.
    let ht = p > 0 ? 'ещё… ↑' : '↑';
    ctx.fillText(ht, hd.x + hd.w / 2, hd.y + hd.h / 2);
  }
  drawPreviewArea(p);
  buttons = [];
  const area = L.layBtn;
  if (sel && p === 0) {
    // ⚠ ОБЁРТЫВАНИЕ КУСКА В НОРИ УБРАНО ИЗ ИНТЕРФЕЙСА 31.08.2026 по решению владельца:
    // «мы ещё не знаем, как именно внутри будем оборачивать… можно пока просто не оборачивать
    // то, что внутри — давай обычный оттестируем до идеального состояния хотя бы».
    // Причина не только в незнании приёма: нынешняя реализация собрана из четырёх
    // несходящихся плашек и считается моделью как четыре отдельных тела (#115). Убрать
    // кнопку дешевле, чем каждый раз объяснять, почему на срезе щели.
    // Код механики жив (wrapInNoriList в play/index.html) — вернуть одна правка здесь.
    const canWrap = WRAP_PIECE_ON;   // один выключатель на кнопку и на генератор пазла (#159)
    const canRot = !ING[sel.kind].wave;
    // Подпись показывает, КУДА повернётся, и по тому же диапазону, что и само действие.
    const rotSpan = cutSymmetric(ING[sel.kind]) ? 180 : 360;
    const rotLabel = `⟳ ${Math.round(((sel.rot || 0) * 180 / Math.PI + 45) % rotSpan)}°`;
    buttonRow([...(canWrap ? [['wrap', 'Кусок в нори', true, 1.2]] : []), ...(canRot ? [['rotate', rotLabel, false, 1.05]] : []),
               ['remove', 'Убрать', false, 1]], { ...area, max: 3 });
  } else {
    // ↶ и ↷ — история действий, а не «снять последний кусок» (issue #84). Тусклая стрелка
    // означает, что возвращать нечего: кнопка не прыгает, но и не врёт, что что-то сделает.
    // ⚠ ОТМЕНА И ВОЗВРАТ УБРАНЫ ИЗ РЯДА 31.08 по решению владельца: «эти рядом с "Очистить"
    // абсолютно не нужные». Ряд из трёх кнопок читался как три равнозначных действия, тогда
    // как две из них — служебные. Сама история НЕ снята: ⌘/Ctrl+Z и Backspace работают
    // (обработчик в play/index.html), и pushHistory по-прежнему пишет каждый шаг — вернуть
    // кнопки это одна строка. Убрана кнопка, а не возможность.
    // ⚑ «ОЧИСТИТЬ» УЕХАЛА В ВЕРХНЮЮ ПАНЕЛЬ (02.09, #157, просьба владельца: «кнопка очистить
    // занимает очень много места лишнего сейчас на экране»). Она стояла здесь одна во всю
    // ширину — разрушительное и редкое действие размером с главное, — и держала под собой
    // ряд в 56 px, который оплатил теперь третий ряд палитры. Наверху у неё подтверждение в
    // два касания и возврат плашкой: на телефоне отмены не было вовсе (см. `clearArm`).
    if (S.puzzle) buttonRow([['newpuzzle', '⟳ Другой', false, 1]], { ...area, max: 1 });
  }
  // Кнопки и палитра делят один слот — последний ряд чипов. Если в слоте кто-то стоит,
  // ряд палитры прячется; лист и остальные ряды при этом не двигаются.
  drawButtons(); drawChips(L.chipsShareBtn && buttons.length > 0);
  const hintLay = L.sheet.uAxis === 'x' ? (SHEET_U0 === 'left' ? hints.layR : hints.layL) : hints.lay;
  drawTopBar(drag.patch ? hints.layMove : sel ? hints.laySel : S.puzzle ? (L.previewMode === 'side' ? hints.puzzle : levelTitle(S.puzzle.lv, S.puzzle.level)) : hintLay);
}
// Мост «лист → доска реза»: длина ролла на доске масштабируется от экранной протяжённости оси v
// (длины ролла на листе), радиус — от пикселей на единицу оси u. Раньше тут стояли s.w и s.h —
// верно только пока u вертикальна; после поворота (#23) формула на w/h раздула бы радиус в
// (lenU/lenV)² раз и утянула за собой нож, размах удара и разлёт половин.
function rollDims() {
  const s = L.sheet;
  const k = L.roll.len / s.lenV;
  if (S.v2 && window.CoreV2) {
    const snap = v2Snap();
    const u = window.CoreV2.U_MM;
    const R = snap && snap.ok ? snap.winding.Rout / u * s.lenU / B().L * k : 40;
    return { g: { L: B().L }, R, len: L.roll.len };
  }
  const m = getModel();
  return { g: m.g, R: m.Rmax * s.lenU / m.g.L * k, len: L.roll.len };
}
function drawBoard(R, len, alpha = 1) {
  ctx.save(); ctx.globalAlpha = alpha; drawMat(L.roll.x - len / 2 - 26, L.roll.y - R - 36, len + 52, 2 * R + 72); ctx.restore();
}
// Честный отказ ядра — словами и на месте ролла. Игрок должен понять, ЧТО править,
// а не разглядывать пустой стол: отказ здесь такая же часть модели, как картинка.
// Причину словами несёт верхняя строка — там светлый текст на тёмном и он читается.
// На циновке остаётся только код диагностики, и ТЁМНЫМ: светлое по светлому дереву
// (#c9a96c) не читается вовсе, а невидимая надпись хуже отсутствующей.
function drawV2Refusal(refusal) {
  ctx.save();
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillStyle = '#6b5334'; ctx.font = font(11);
  ctx.fillText(refusal.code, L.roll.x, L.roll.y);
  ctx.restore();
}
function drawRolled() {
  if (S.v2 && !window.CoreV2) return;
  const refusal = S.v2 ? v2Refusal(v2Snap()) : null;
  const { R, len } = rollDims();
  drawBoard(R, len);
  if (refusal) {
    drawV2Refusal(refusal);
  } else {
    drawRollBody(L.roll.x, L.roll.y, R, len, [{ a: 0, b: 1, off: 0 }]);
    // риски: где будут резы
    ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.setLineDash([3, 5]); ctx.lineWidth = 1;
    for (let i = 1; i < npieces(); i++) { const x = L.roll.x - len / 2 + len * i / npieces(); ctx.beginPath(); ctx.moveTo(x, L.roll.y - R - 14); ctx.lineTo(x, L.roll.y + R + 14); ctx.stroke(); }
    ctx.setLineDash([]);
  }
  buttons = [];
  // В режиме своей раскладки возврат к начинкам обязателен: именно правкой
  // раскладки игрок и снимает отказ. У фикстур править нечего — там кнопки нет.
  if (!S.v2 || S.v2Scenario === 'layout') buttonRow([['back', '← Ещё начинки']]);
  drawButtons(); drawTopBar(refusal ? refusal.text : hints.rolled);
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
  // ⚑ ЧИСЛО ВИТКОВ СКАЗАНО ВСЛУХ (02.09, #162, просьба владельца ещё от 02.09: «а какое
  // количество? можно как-то обозначать?»). Без него срез спирали неотличим от среза кольца
  // на глаз: и там и там видно тёмные дуги, и разница в том, СКОЛЬКО их — 2,31 у футомаки
  // против 9,85 у узумаки. Владелец трижды приняла второй виток с хвостом за сломанную
  // спираль, и была права в жалобе: спирали там нет, просто числа этого не говорили.
  {
    const mm = getModel(), wd = windFor(mm, c.v);
    const вит = +wd.turns;
    const режим = mm.g.winding === 'spiral' ? 'спираль' : 'кольцо';
    const хвост = вит < 3 && mm.g.winding === 'spiral' ? ' — мало для узора' : '';
    ctx.fillText(`срез на ${Math.round(c.v * 100)} % длины · ${режим}, ${вит.toFixed(1).replace('.', ',')} витка${хвост}`,
                 cx, L.faceY + L.faceSize / 2 + 14);
  }
  const hl = handLabel(); if (hl) { ctx.fillStyle = '#6f6754'; ctx.font = font(12); ctx.fillText(hl, cx, L.faceY + L.faceSize / 2 + 32); }
  buttons = []; buttonRow([['slice', `Нарезать на ${npieces()}`, true], ['albumsave', S.saved > performance.now() ? '✓ В альбоме' : '★ В альбом'], ['back', 'Ещё начинки']]);
  if (S.saved > performance.now()) dirty = true;
  drawButtons(); drawTopBar(hints.revealed);
}
// Нарезка: быстрые удары, потом кусочки встают срезом и разъезжаются по тарелке.
let slicing = null;
function startSlicing() {
  const { R, len } = rollDims();
  const cutsV = []; for (let i = 1; i < npieces(); i++) if (Math.abs(i / npieces() - cut.v) > 1e-3) cutsV.push(i / npieces());
  const imgs = []; for (let i = 0; i < npieces(); i++) imgs.push(face(pieceV(i), L.grid[0].size));
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
  for (let i = 0; i < npieces(); i++) {
    const a = i / npieces(), b = (i + 1) / npieces();
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
  if (reveal > 0) for (let i = 0; i < npieces(); i++) {
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
  for (let i = 0; i < npieces(); i++) {
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
    ctx.fillText(`кусочек ${S.bigPiece + 1} из ${npieces()} · тапни, чтобы закрыть`, cx, L.faceY - L.faceSize / 2 - 14);
    drawSlab([{ x: cx, y: L.faceY, size: L.faceSize }], 1, B(), 10);
    drawFaceImg(img, cx, L.faceY, L.faceSize);
  }
}

