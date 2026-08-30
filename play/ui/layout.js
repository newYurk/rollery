'use strict';
// ХОЛСТ И РАСКЛАДКА ЭКРАНА: canvas, ctx, размеры, safe-area, режимы P/L/T/D.
//
// Здесь объявлены canvas, ctx, W, H, DPR, SAFE и L — их читает всё остальное, поэтому файл
// подключается ДО рендера и UI. Спецификация раскладки — docs/ui-review.md, раздел 2.
//
// sheetFloor и HIT_PAD связаны одним числом намеренно: цель касания = брусок + ореол, и
// пол листа выводится из неё, а не задаётся отдельной константой (иначе они разъезжаются).

// ---------------------------------------------------------------- холст и раскладка экрана
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
let W = 0, H = 0, DPR = 1, dirty = true;
const SAFE = { top: 0, bottom: 0, left: 0, right: 0 };   // safe-area: статус-бар, чёлка, индикатор «домой»
const L = {};   // раскладка: sheet, handle, chips, buttons, roll, face, grid
function resize() {
  DPR = Math.min(2, window.devicePixelRatio || 1);
  try { const cs = getComputedStyle(document.getElementById('probe')); SAFE.top = parseFloat(cs.paddingTop) || 0; SAFE.bottom = parseFloat(cs.paddingBottom) || 0; SAFE.left = parseFloat(cs.paddingLeft) || 0; SAFE.right = parseFloat(cs.paddingRight) || 0; } catch (e) {}
  W = window.innerWidth; H = window.innerHeight;
  canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
  canvas.style.width = W + 'px'; canvas.style.height = H + 'px';
  layout(); dirty = true;
}
// Подпись под чипом шире самого чипа («Креветка» ≈ 52 px при чипе 44), а полоса чипов
// отсекается по своей рамке. Отсюда отступ: на сколько содержимое полосы надо отодвинуть
// от края, чтобы крайняя подпись целиком осталась внутри.
function chipLabelPad(size, list) {
  ctx.font = font(11);
  let w = 0; for (const k of list) w = Math.max(w, ctx.measureText(ING[k].name).width);
  return Math.max(0, Math.ceil((w - size) / 2));
}
// ПОЛ ЛИСТА — ФОРМУЛА, А НЕ ЧИСЛО. На листе кладут начинки пальцем: hitPatch расширяет патч
// на HIT_PAD с каждой стороны, значит экранная высота патча должна быть ≥ TOUCH − 2·HIT_PAD.
// Обычный брусок (лосось/авокадо/креветка) — wU = 2 единицы; на листе длиной L единиц он
// занимает 2/L высоты. Отсюда пол = (TOUCH − 2·HIT_PAD) · L / 2.
// ⚠ ЧИСЛОМ ЭТУ ВЕЛИЧИНУ ПИСАТЬ НЕЛЬЗЯ. Здесь стояло 252 — оно выведено из ПОЛУЛИСТА хосомаки
// (L = 21) и устарело ровно вдвое, как только лист стал единым (L = 42): пол должен был стать
// 504, а остался 252, и на 390x844 брусок получал цель касания 36,8 px при норме 44.
// Длина берётся у sheetLen(): в «Пазле» её меняет уровень, и лист там действительно длиннее.
const HIT_PAD = 14;   // ореол вокруг патча, px с каждой стороны (см. hitPatch)
const TOUCH = 44;     // норма цели касания
const sheetFloor = () => (TOUCH - 2 * HIT_PAD) * sheetLen(B()) / 2;
// ОТБОР РАСКЛАДОК ДВУХСТУПЕНЧАТЫЙ, и это не украшение. Чистый максимум площади ошибается:
// два ряда чипов с прокруткой дают лист выше, чем три ряда без неё, и правило само отдало бы
// видимость палитры за пиксели листа. Порядок такой:
//   1) жёсткий фильтр — лист не ниже пола пальца (ниже него класть начинки просто нечем);
//   2) среди прошедших — БОЛЬШЕ ВИДНЫХ ЧИПОВ (сколько начинок помещается без прокрутки);
//   3) при равенстве — больше ПОЛЕЗНОЙ площади листа (то, что закрывает накладка, вычтено).
// Если пол не берёт никто — берём самый высокий лист: это единственное, что там ещё улучшишь.
// ⚠ На второй ступени стояло «больше РЯДОВ» — и это ошибка, замеренная на 1440x900: там лист
// шириной 1240 берёт все двадцать чипов в ОДИН ряд без прокрутки, а боковая колонка сужает
// его до 896 и требует двух рядов. По числу рядов выигрывала колонка, и лист падал с 58,7 %
// до 37,6 % ради ряда, который ничего не показывал сверх первого. Считать надо видимость,
// а не строки: два ряда по шесть лучше одного ряда по шесть, но не лучше одного ряда по двадцать.
const betterFit = floor => (a, c) => {
  const rank = x => (x.sh >= floor ? [1, x.vis, x.area] : [0, 0, x.sh]);
  const ra = rank(a), rc = rank(c);
  for (let i = 0; i < 3; i++) if (Math.abs(rc[i] - ra[i]) > 0.5) return rc[i] > ra[i] ? c : a;
  return a;
};
// Раскладка экрана. Режимы: P — телефон портрет, L — телефон альбом, T — планшет, D — широкий десктоп.
// Всё считается в рамке cw × ch внутри safe-area; лист — в приоритете, предпросмотр/цель — полосой, накладкой или в боковой колонке.
function layout() {
  const cw = W - SAFE.left - SAFE.right, ch = H - SAFE.top - SAFE.bottom, ox = SAFE.left, oy = SAFE.top;
  const n = B().ingredients.length, pz = S.puzzle, k = pz ? pz.vs.length : 1, showPrev = !!(pz || S.preview);
  const mode = ch < 500 ? 'L' : cw >= 1100 ? 'D' : cw >= 600 ? 'T' : 'P';
  const hint2 = mode === 'P' && cw < 480, panelH = hint2 ? 78 : 62, btnH = 44;
  Object.assign(L, { mode, cw, ch, ox, oy, hint2, top: oy + panelH, side: null, previewMode: 'none', previewSize: 116, chipScroll: false, btnH , targetCell: 0});
  L.rowBtn = { x: ox + (cw - Math.min(cw - 32, 560)) / 2, y: oy + ch - 12 - btnH, w: Math.min(cw - 32, 560), h: btnH, max: 3 };
  if (mode === 'L') {
    const handleH = 32, sh = Math.max(90, ch - panelH - 22 - handleH - 8 - 8), sw = Math.max(120, Math.min(1.3 * sh, 0.55 * cw));
    L.sheet = { x: ox + 16, y: L.top + 22, w: sw, h: sh };
    L.handle = { x: L.sheet.x - 12, y: L.sheet.y + sh + 8, w: sw + 24, h: handleH };
    const sx = L.sheet.x + sw + 28, swid = Math.max(200, cw - sw - 60);
    L.side = { x: sx, y: L.top + 8, w: swid, h: ch - panelH - 16 };
    L.previewMode = showPrev ? 'side' : 'none'; L.targetCell = Math.min(72, (swid - 8 * (Math.min(k, 3) - 1)) / Math.min(k, 3));
    // БЮДЖЕТ БОКОВОЙ КОЛОНКИ. Раньше y просто копился и ни с чем не сверялся, поэтому лишнее
    // уезжало за низ экрана МОЛЧА: на 844x390 сумма выходила 328 при высоте колонки 312 —
    // подпись выбранного чипа рисовалась на 16 px ниже рамки. На коротком ландшафте (667x375)
    // за край уходили и сами чипы: в этой ветке chipScroll не выставлялся ВООБЩЕ, а drawChips
    // отсекает ленту по своей рамке — двадцать начинок в колонке 291 px обрезались без всякого
    // признака. Теперь всё, что кладём в колонку, обязано в неё влезть, уступки идут лестницей
    // (по одной, в порядке возрастания потери), а в конце стоит зажим, а не пожелание.
    const chipSizeL = 36, chipRowL = chipSizeL + 6, selLabelH = 16, gapAfterBtn = 12;
    const perRowFit = Math.max(1, Math.floor((swid + 8) / (chipSizeL + 8)));
    const prevBlock = ps => (showPrev ? (k > 1 ? Math.ceil(k / 3) * (L.targetCell + 8) : ps + 8) + 24 : 0);
    const btnBlock = rb => rb * 40 + (rb - 1) * 8 + gapAfterBtn;
    const need = (ps, rb, rc) => prevBlock(ps) + btnBlock(rb) + rc * chipRowL + selLabelH;
    let prevSize = 96, btnRows = 2, chipRows = Math.max(1, Math.min(3, Math.ceil(n / perRowFit)));
    if (need(prevSize, btnRows, chipRows) > L.side.h) btnRows = 1;          // 1) кнопки в один ряд по три
    if (need(prevSize, btnRows, chipRows) > L.side.h) prevSize = 64;        // 2) кружок предпросмотра меньше
    while (chipRows > 1 && need(prevSize, btnRows, chipRows) > L.side.h) chipRows--;   // 3) ряды — в прокрутку
    L.previewSize = prevSize;
    let y = L.side.y + prevBlock(prevSize);
    L.layBtn = { x: sx, y, w: swid, h: 40, max: btnRows === 1 ? 3 : 2 };
    y += btnBlock(btnRows);
    // Зажим, а не проверка: сколько рядов помещается от текущего y до низа колонки, столько
    // и рисуем. После этой строки y + высота ленты + подпись ≤ side.y + side.h тождественно.
    chipRows = Math.min(chipRows, Math.max(1, Math.floor((L.side.y + L.side.h - y - selLabelH) / chipRowL)));
    const perRowL = Math.ceil(n / chipRows);
    L.chips = { x: sx, y, w: swid, size: chipSizeL, rows: chipRows, labels: false, perRow: perRowL };
    L.chipScroll = perRowL * (chipSizeL + 8) - 8 > swid;   // не влезло — прокрутка с шевроном, не обрез
  } else if (mode === 'P') {
    const handleH = 40, chipSize = 44, chipGap = 8, chipRow = chipSize + 18;
    const bandFull = showPrev && ch >= 800 ? (k > 1 ? 118 : 136) : 0;
    // Ниже листа стопка жёсткая: лист→циновка 8, циновка 40, →кнопки 12, кнопки 44,
    // →чипы 12, чипы rows × 62, нижний отступ 12. Что не съедено ею — отдаётся листу.
    // (Прежний расчёт чипы не резервировал: его «chipsH = 64» уходило на зазоры ниже листа,
    //  один ряд оставлял под собой 6 px вместо 12, а второй ряд брался только из случайного
    //  остатка — которого при упёршемся в потолок листе как раз и не оставалось.)
    const belowSheet = 8 + handleH + 12 + btnH + 12, bottomPad = 12;
    const stripW = cw - 24, pad = chipLabelPad(chipSize, B().ingredients);
    const inner = Math.max(chipSize, stripW - 2 * pad);
    // Сколько рядов НУЖНО, чтобы показать все начинки без прокрутки. Один ряд из 11 чипов
    // требует окна ≥ 596 px, из 12 → ≥ 648 px (с местом под подписи): портретных телефонов
    // такой ширины не бывает, поэтому один ряд на телефоне гарантированно прячет начинки —
    // прокрутка здесь не запасной вариант, а потеря. Прежнее условие n > 7 не блокировало
    // никогда (минимум среди баз — 8 у рулета) и решало не то: остаток, а не влезание.
    const wantRows = Math.max(1, Math.min(2, Math.ceil(n / Math.max(1, Math.floor((inner + chipGap) / (chipSize + chipGap))))));
    // Лист занимает рамку целиком: ширину даёт окно, высоту — то, что осталось после панели,
    // полосы, циновки, кнопок и ленты. Кламп «0,8…1,15» отсюда убран вместе с ph в ветке T/D
    // и по той же причине — пропорция листа больше не изображает физику (см. комментарий там).
    const sw = Math.min(cw - 32, 560);
    const FLOOR = sheetFloor();
    // Одна раскладка: сколько остаётся листу при данной полосе и данном числе рядов чипов.
    // Площадь — ПОЛЕЗНАЯ: то, что закрывает накладка, вычитается по её же рисовальщику
    // (drawPreviewArea, ветка 'overlay'), иначе «накладка ничего не стоит» и она выигрывает всегда.
    const perFitP = Math.max(1, Math.floor((inner + chipGap) / (chipSize + chipGap)));
    const fitP = (bnd, rowsC) => {
      const rem = ch - (panelH + 26 + belowSheet + bottomPad) - bnd - rowsC * chipRow;
      const sh = Math.max(90, rem);
      const eaten = (!bnd && showPrev) ? (k > 1 ? sw * (Math.min(56, (sw - 16 - 6 * (k - 1)) / k) + 16) : 102 * 102) : 0;
      return { band: bnd, rows: rowsC, sh, vis: Math.min(n, rowsC * perFitP), area: sw * sh - eaten };
    };
    // Здесь стоял ЖЁСТКИЙ ПОРЯДОК УСТУПОК: первый план с остатком ≥ пола и выиграл. Из-за него
    // полоса предпросмотра оставалась всегда, пока лист формально дотягивал до пола, — на 390x844
    // это 116-пиксельный кружок за 136 px листа. Теперь, как и в T/D, считаются все кандидаты
    // и сравниваются по существу (betterFit): пол пальца → число рядов чипов → полезная площадь.
    const candsP = [];
    for (let r = wantRows; r >= 1; r--) { if (bandFull) candsP.push(fitP(bandFull, r)); candsP.push(fitP(0, r)); }
    const plP = candsP.reduce(betterFit(FLOOR));
    const band = plP.band, rows = plP.rows, sh = plP.sh, perRow = Math.ceil(n / rows);
    L.previewMode = showPrev ? (band ? 'band' : 'overlay') : 'none';
    L.sheet = { x: ox + (cw - sw) / 2, y: L.top + 26 + band, w: sw, h: sh };
    L.handle = { x: L.sheet.x - 18, y: L.sheet.y + sh + 8, w: sw + 36, h: handleH };
    L.layBtn = { x: L.rowBtn.x, y: L.handle.y + handleH + 12, w: L.rowBtn.w, h: btnH, max: 3 };
    L.chips = { x: ox + 12, y: L.layBtn.y + btnH + 12, w: stripW, size: chipSize, rows, labels: true, perRow, pad };
    L.chipScroll = perRow * (chipSize + chipGap) - chipGap > inner;
    L.previewY = L.top + 12 + band / 2; L.previewSize = k > 1 ? Math.min(84, (cw - 32 - 8 * (k - 1)) / k) : 116;
  } else {
    const handleH = 40, chipSize = 52, chipRow = 70, scol = mode === 'D' ? 320 : 260;
    const pad = chipLabelPad(chipSize, B().ingredients);
    // ПРОПОРЦИЯ ЛИСТА — ЭТО ПРОПОРЦИЯ РАМКИ, и больше ничего. Здесь стояло ph = L / Wv, то есть
    // честная физика листа, и это было верно, пока лист был признаком ТИПА: хосомаки из полулиста
    // реально широкий и низкий, футомаки из целого — почти квадратный. Типы отменены, обёртка
    // стала обычным выбором на одном экране — и та же формула превратилась в дефект: смена
    // обёртки или базы переставляла архитектуру экрана и меняла площадь листа в 2,4 раза
    // (1024x768: 980x482 с накладкой против 485x412 с боковой колонкой — один тап).
    // Решение владельца: «реальные размеры не обязательно должны совпадать… отмасштабировать
    // пять сантиметров на весь экран и десять сантиметров на весь экран. Зачем пользователю знать
    // какие-то реальные размеры?» Физика осталась в модели ЦЕЛИКОМ — длина листа, толщина обёртки,
    // шаг витка, число оборотов, ⌀ считаются по-настоящему и ничего не потеряли; на экране лист
    // просто занимает отведённую рамку. Скачок при смене обёртки теперь НОЛЬ ПО ПОСТРОЕНИЮ:
    // в расчёте рамки не осталось ни одной величины, зависящей от обёртки или базы.
    // Чем платим — лист не показывает пропорций: на ландшафтном окне рамка 0,42, честное — 1,1,
    // то есть ось u (вдоль скрутки, она же решает узор) сплющена в 2,6 раза. Страховкой был бы
    // фиксированный, от обёртки не зависящий коридор sh/sw ∈ [0,55; 1,40] — он стоит 20–24 %
    // площади на 1024x768 и 1440x900 и ноль на остальных; сознательно НЕ включён, ждём практики.
    // Полоса цели над листом: цели идут одним рядом, поэтому размер клетки ограничен шириной окна.
    const fsBand = k > 1 ? Math.min(180, (cw - 60 - 8 * (k - 1)) / k) : 116;
    const bandH = showPrev ? Math.round(k > 1 ? fsBand + 40 : 136) : 0;
    // Пол листа — тот же, что на телефоне, и считается одной формулой на всех (sheetFloor).
    const FLOOR = sheetFloor();
    // Одна раскладка при заданном месте предпросмотра и потолке рядов чипов.
    // Возвращает лист и его ПОЛЕЗНУЮ площадь: накладка часть листа закрывает, и эта часть
    // из площади вычитается — иначе «накладка ничего не стоит» и она выигрывала бы всегда.
    const fit = (bnd, side, maxRows) => {
      const bw = (mode === 'D' ? Math.min(cw - 44, 1240) : cw - 44) - (side ? scol + 24 : 0);
      if (bw < 240) return null;   // колонке негде стоять: узкое окно
      // Рамка целиком: ширина листа — вся ширина блока, высота — весь остаток. Ширина больше
      // не зависит от числа рядов (раньше зависела через target), поэтому считается один раз.
      const sw = Math.max(120, bw);
      let rows = 1, sh = 0, bh = 0;
      for (;;) {
        bh = ch - panelH - 26 - bnd - handleH - 8 - 12 - btnH - 12 - rows * chipRow - 12;
        // Ряд чипов проверяется на ИТОГОВУЮ полосу (sw + 36), а не на bw: они расходятся до 680 px
        // (1440x900, рулет: bw 1240 при sw 561), а лишний чип просто обрезался бы молча.
        if (rows >= maxRows || n * (chipSize + 8) - 8 <= Math.max(chipSize, sw + 36 - 2 * pad)) break;
        rows++;
      }
      sh = Math.max(90, bh);
      // Что накладка съедает у листа — по её же рисовальщику (drawPreviewArea, ветка 'overlay').
      const eaten = (!bnd && !side && showPrev)
        ? (k > 1 ? sw * (Math.min(56, (sw - 16 - 6 * (k - 1)) / k) + 16) : 102 * 102)
        : 0;
      // Сколько чипов видно без прокрутки в ЭТОЙ раскладке — вторая ступень отбора.
      const innerC = Math.max(chipSize, sw + 36 - 2 * pad);
      const vis = Math.min(n, rows * Math.max(1, Math.floor((innerC + 8) / (chipSize + 8))));
      return { band: bnd, side, rows, sw, sh, boxH: bh, vis, area: sw * sh - eaten };
    };
    // Где предпросмотру стоять — решает СРАВНЕНИЕ ПО СУЩЕСТВУ, а не доля высоты. Прежний потолок
    // «полоса не больше пятой части высоты» был угаданным числом и решал судьбу листа: на 1024x768
    // 136 px полосы против порога 141 — полоса оставалась, лист складывался в колонку 325x276
    // вместо 485x412 (−55 %). Считаются три раскладки — полоса сверху, накладка на листе, боковая
    // колонка, — каждая с потолком в два ряда чипов и с одним, и все шесть сравниваются разом.
    // Раньше здесь был чистый максимум площади плюс отдельная заплата «если ниже пола — попробуй
    // один ряд». Максимум площади в этом месте ошибается: один ряд с прокруткой всегда даёт лист
    // выше двух рядов без неё, и правило само отдавало бы видимость палитры. Отбор — betterFit.
    const cands = [];
    for (const maxRows of [2, 1]) {
      if (showPrev) cands.push(fit(bandH, false, maxRows), fit(0, true, maxRows), fit(0, false, maxRows));
      else cands.push(fit(0, false, maxRows));
    }
    const pl = cands.filter(Boolean).reduce(betterFit(FLOOR));
    const band = pl.band, sideOn = pl.side, rows = pl.rows, sw = pl.sw, sh = pl.sh, boxH = pl.boxH;
    const perRow = rows === 1 ? n : Math.ceil(n / rows);
    // Остаток по вертикали делим пополам: лист физически широкий и низкий, весь экран ему не нужен,
    // и блок «лист + циновка + кнопки + лента» стоит по центру, а не прижат к панели.
    const spare = Math.max(0, boxH - sh);
    const groupW = sw + (sideOn ? 24 + scol : 0);
    const bx = Math.max(ox + 22, ox + (cw - groupW) / 2);
    L.sheet = { x: bx, y: L.top + 26 + band + spare / 2, w: sw, h: sh };
    L.handle = { x: bx - 18, y: L.sheet.y + sh + 8, w: sw + 36, h: handleH };
    L.layBtn = { x: bx - 18, y: L.handle.y + handleH + 12, w: sw + 36, h: btnH, max: 3 };
    L.chips = { x: bx - 18, y: L.layBtn.y + btnH + 12, w: sw + 36, size: chipSize, rows, labels: true, perRow, pad };
    // Страховка от молчаливого обреза: если полоса уже ряда — включаем прокрутку.
    L.chipScroll = perRow * (chipSize + 8) - 8 > Math.max(chipSize, sw + 36 - 2 * pad);
    if (sideOn) L.side = { x: bx + sw + 24, y: L.top + 16, w: scol, h: ch - panelH - 32 };
    L.previewMode = showPrev ? (sideOn ? 'side' : band ? 'band' : 'overlay') : 'none';
    L.previewY = L.top + 12 + band / 2;
    // Боковая колонка на планшете уже десктопной (260 против 320): и кружок среза, и клетки целей
    // считаются от неё, иначе три цели в ряд (3 x 84 + 16 = 268) вылезают за колонку.
    L.previewSize = sideOn ? scol - 60 : fsBand; L.targetCell = mode === 'D' ? 100 : 80;
  }
  // общие экраны: ролл, срез, тарелка — в области между панелью и нижним рядом кнопок
  const areaTop = L.top, ah = Math.max(120, L.rowBtn.y - 12 - areaTop);
  L.roll = { x: ox + cw / 2, y: areaTop + ah * 0.5, len: Math.min(cw - 80, 640) };
  L.faceSize = Math.min(0.78 * cw, ah * 0.72, 520); L.faceY = areaTop + ah * 0.5;
  const cols = (mode === 'L' || cw >= 900) ? 6 : (mode === 'P' ? 2 : 3), rows = NPIECES / cols;
  const cell = Math.max(40, Math.min((cw - 40) / cols - 10, (ah - 30) / rows - 10));
  const gx = ox + (cw - cols * (cell + 10)) / 2 + 5, gy = areaTop + (ah - rows * (cell + 10)) / 2 + 5;
  L.grid = []; for (let i = 0; i < NPIECES; i++) L.grid.push({ x: gx + (i % cols) * (cell + 10) + cell / 2, y: gy + Math.floor(i / cols) * (cell + 10) + cell / 2, size: cell });
}
function rr(x, y, w, h, r) {
  r = Math.min(r, w / 2, h / 2);
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}
const font = (px, w = 500) => `${w} ${px}px -apple-system, system-ui, Segoe UI, Roboto, sans-serif`;

