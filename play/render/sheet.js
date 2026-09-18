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

// ── ШКУРА ВИДА СВЕРХУ: РИСУНОК ПОВЕРХ ВЫВЕДЕННОЙ ФОРМЫ (issue #256, 17.09) ───
//
// Владелец 17.09: «у каждой начинки должна быть картинка того, как она лежит на листе».
// С #105 вид сверху ВЫВОДИТСЯ из тела, и подменять его картинкой нельзя — лист и срез
// разойдутся ровно так, как уже расходились. Поэтому картинка входит сюда ОДНИМ КАНАЛОМ.
//
// ЧТО БЕРЁТСЯ ОТ МОДЕЛИ И ЧТО ОТ КАРТИНКИ.
//   · форма, размер, место куска — модель (patchRect / patchScreen), как и было;
//   · вещество и цвет в каждой клетке — модель (patchColor через pieceTopColor/pieceSideColor);
//   · от картинки — ТОЛЬКО отношение яркости её клетки к её же средней яркости.
// Среднее этого отношения приведено к единице (см. skinField), поэтому СРЕДНИЙ ЦВЕТ куска
// остаётся тем, что посчитала модель: шкура его не сдвигает, она его РАЗБИВАЕТ на рисунок.
// «Арт — шкура поверх математики» (владелец 31.08) здесь буквально множитель.
//
// ⚠ НО СРЕДНИЙ ЦВЕТ КУСКА НА ЛИСТЕ ВСЁ РАВНО ИЗМЕНИЛСЯ — не от шкуры, а от того, что клетка
// стала вчетверо мельче (topCell ниже). Раньше у бруска было 2 клетки поперёк, и обе были
// боковыми гранями; теперь их 9, и тело опрашивается по всей ширине, а не только по краям.
// Замер 17.09 по 198 случаям (6 баз × канон, канон-7, бруски, по одному куску каждого вида):
// и перебором фаз (у куска phase = Math.random()·TAU, и от неё зависит рисунок): сильнее всех
// уехал тунец на футомаки — 50,5 из 255 при фазе 0,39, лосось на узумаки 40,1, огурец 35,1,
// киви 32,6, клубника 29,0. Уехал К СРЕЗУ: расхождение листа со срезом по яркости в среднем
// по 21 виду упало с 18,0 % до 15,8 %. Подробности и восемь видов, у которых оно выросло, — в
// docs/design-core.md. Здесь важно одно: «цвет куска не изменился» сказать нельзя.
//
// ПОЧЕМУ НЕ ЦВЕТ ИЗ КАРТИНКИ. Тогда розовая спираль наруто и красная плёнка краба приехали бы
// ДВАЖДЫ — из каталога и из PNG, — и разошлись бы при первой же правке каталога. Это та самая
// болезнь «одно свойство, два описания», от которой избавлялся #105.
const SKIN_DIR = 'assets/topview/';
// КОНТРАСТ ШКУРЫ ЗАЖАТ, и нижняя граница — то же решение, что AMBIENT = 0,62 (31.08,
// «креветка выглядит коричневой»): тёмный контур спрайта — это 24,22,20 при средней яркости
// полосы около 200, то есть множитель 0,11. Умноженный на розовый он даёт не «розовый в тени»,
// а чёрный. Ниже 0,62 кусок перестаёт быть своего цвета — это уже измерено и записано.
// Верхняя граница — ЗЕРКАЛО нижней вокруг единицы (2 − 0,62): осветлить клетку шкуре позволено
// ровно настолько, насколько позволено затемнить. Не 1/0,62 = 1,61 — множитель тут живёт
// в яркости, а не в отношениях, и среднее обязано остаться единицей.
// ⚠ ЧЕГО ЭТО НЕ ЛЕЧИТ: потолка 255. Светлый материал (наруто 246,244,238) на 1,38 не
// умножается — излишек срезается, и средний цвет куска уезжает ВНИЗ. Замер по каталогу:
// наруто 8,2 из 255, креветка 6,5, манго 4,3, остальные меньше 1,6. Это цена умножения,
// названная вслух; сторож §5а-секст держит её под порогом, а не делает вид, что её нет.
const SKIN_K = [0.62, 1.38];
const SKIN_IMG = {};       // kind → Image (или null, если файла нет)
const SKIN_FIELD = {};     // kind → {w, h, k: Float32Array} (или null)
// ?noskin — тот же лист, но вычислением, без шкур. Нужен не для красоты: это единственный
// способ посмотреть глазами, что именно даёт картинка, и сравнить два вида на одном экране.
const SKINS = !/[?&]noskin\b/.test(location.search);
// Начинка по её записи каталога: pieceTopSprite получает d, а шкура лежит под ИМЕНЕМ вида.
// Через tex нельзя: tex у тамаго, омлета и шиитакэ один, а шкуры у них разные.
let _kindOf = null;
function kindOf(d) {
  if (!_kindOf) { _kindOf = new Map(); for (const k in ING) _kindOf.set(ING[k], k); }
  return _kindOf.get(d) || null;
}
// Ленивая НЕблокирующая загрузка — как у иконок чипов (ui/controls.js): пока PNG не пришёл,
// кусок рисуется вычислением; пришёл — сбрасываем кэш спрайтов и просим кадр. Нет файла —
// молча остаёмся на вычислении (п. 3 задачи: «нет файла — нет беды»).
function skinImg(kind) {
  if (!kind) return null;
  let im = SKIN_IMG[kind];
  if (im === undefined) {
    if (typeof Image !== 'function') { SKIN_IMG[kind] = null; SKIN_FIELD[kind] = null; return null; }
    im = new Image();
    im.onload = () => { SKIN_FIELD[kind] = undefined; TOP_CACHE.clear(); dirty = true; requestFrame(); };
    im.onerror = () => { SKIN_IMG[kind] = null; SKIN_FIELD[kind] = null; };
    im.src = SKIN_DIR + kind + '.png';
    SKIN_IMG[kind] = im;
  }
  return im && im.complete && im.naturalWidth ? im : null;
}
// Пиксели картинки. В браузере их отдаёт только холст. В tools/check.js холст — заглушка
// (getImageData отдаёт нули), и там картинка приносит пиксели с собой, полем `пиксели`
// (см. ЗАГЛУШКА_КАРТИНОК в tools/check.js). Это не поддавка сторожу: байты те же, из того же
// PNG, просто разжаты не браузером — иначе сторож на шкуру был бы проверяем только руками.
function skinPixels(im) {
  if (im.пиксели) return im.пиксели;
  const c = document.createElement('canvas');
  c.width = im.naturalWidth; c.height = im.naturalHeight;
  const g = c.getContext('2d');
  g.imageSmoothingEnabled = false; g.drawImage(im, 0, 0);
  return { w: c.width, h: c.height, data: g.getImageData(0, 0, c.width, c.height).data };
}
// Поле множителей яркости. Прозрачные клетки шкуры дают 0 — «здесь рисунка нет», и там
// остаётся чистый модельный цвет: у коротких кусочков (креветка, орех) между ними виден
// сам кусок, а не дыра. Дыры в форме шкура прорезать не имеет права — форма из модели.
//
// ⚑ НОРМИРОВКА — ПО РЯДАМ ПОПЕРЁК КУСКА, А НЕ ПО ВСЕЙ КАРТИНКЕ, И ЭТО ЗАМЕР, А НЕ ВКУС.
// Сначала стояла одна нормировка на весь спрайт: среднее множителя ровно 1, а средний цвет
// куска всё равно уезжал — до 14,5 из 255 (наруто), 13,2 (майо), 10,9 (лосось). Причина
// арифметическая: средний цвет куска — это среднее ПРОИЗВЕДЕНИЯ, а модельный цвет и шкура
// СВЯЗАНЫ поперёк. У шкуры тёмная кромка ровно там, где у модели боковая грань, и свет под
// верхней кромкой ровно там, где у модели макушка. Среднее произведения связанных величин
// не равно произведению средних, и никакая общая нормировка этого не лечит.
// Лечит разделение обязанностей: СВЕТ ПОПЕРЁК — дело модели (наклон поверхности тела,
// pieceLight), РИСУНОК ВДОЛЬ — дело картинки. Поэтому каждый ряд шкуры нормируется сам:
// его среднее — единица, и он не может ни осветлить, ни затемнить свой ряд куска.
function skinField(kind) {
  const готово = SKIN_FIELD[kind];
  if (готово !== undefined) return готово;
  const im = skinImg(kind);
  if (!im) return null;                       // ещё грузится или файла нет — не запоминаем
  const px = skinPixels(im), w = px.w, h = px.h, d = px.data, n = w * h;
  if (!(w > 0 && h > 0) || d.length < n * 4) return (SKIN_FIELD[kind] = null);
  const k = new Float32Array(n);
  let всего = 0;
  for (let y = 0; y < h; y++) {
    let сумма = 0, их = 0;
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (d[i * 4 + 3] < 128) continue;
      const l = 0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2];
      k[i] = l > 0 ? l : 1e-3; сумма += k[i]; их++;
    }
    if (!их || !(сумма > 0)) { for (let x = 0; x < w; x++) k[y * w + x] = 0; continue; }
    const средняя = сумма / их;
    let после = 0;
    for (let x = 0; x < w; x++) { const i = y * w + x; if (k[i]) { k[i] = clamp(k[i] / средняя, SKIN_K[0], SKIN_K[1]); после += k[i]; } }
    // ⚑ ВТОРАЯ НОРМИРОВКА РЯДА — НЕ ПРИДИРКА. Зажим по краям сам сдвигает среднее: у наруто
    // тёмный ободок уводил его на 3,8 %. Делим на среднее ПОСЛЕ зажима — тогда единица по
    // построению, а не «почти единица».
    const поправка = их / после;
    for (let x = 0; x < w; x++) { const i = y * w + x; if (k[i]) k[i] *= поправка; }
    всего += их;
  }
  if (!всего) return (SKIN_FIELD[kind] = null);
  return (SKIN_FIELD[kind] = { w, h, k });
}

// КЛЕТКА КУСКА — ВДВОЕ МЕЛЬЧЕ КЛЕТКИ РИСА (issue #256, п. 4; владелец 17.09: «больше пикселей»).
//
// ⚠ И ЗДЕСЬ БЫЛА НЕСОГЛАСОВАННОСТЬ, которая и есть причина «рваных» кусков. Рис считается в
// ЭКРАННЫХ точках: getSpreadTex делит w·DPR на PIX, то есть клетка риса = PIX точек экрана
// (4 css px при DPR 2). А кусок рисовался в CSS-пикселях — cell = PIX css px, то есть PIX·DPR
// точек экрана, В DPR РАЗ крупнее клетки риса: вдвое при DPR 2. (Вчетверо — это другое
// отношение, старой клетки куска к новой: 2·DPR. Числа разные, и путать их нельзя.)
// Замер на футомаки (390×844, DPR 2): брусок лосося 10 мм = 18,8 css px укладывался в 2 клетки
// поперёк, огурец 14 мм = 26,4 px — в 3. Никакой фактуры в двух клетках не бывает.
// ⚠ И порог `есть_грани >= 6` ниже СРАБАТЫВАЛ, но только у шести видов из двадцати одного —
// у широких: омлет-лист 12 клеток поперёк, киви 10, манго 9, банан 8, клубника и наруто по 6.
// У остальных пятнадцати, то есть у всех брусков и полос, грани не рисовались вовсе, и объём
// им показывать было нечем. (Первая редакция этого абзаца говорила «ни на одном куске» — это
// было неверно, поймано независимой проверкой 17.09.)
// Теперь клетка куска = PIX/2 точек экрана: ровно вдвое мельче риса при ЛЮБОМ DPR (2 css px
// при DPR 2 — то самое число, под которое сняты спрайты). Поперёк стало 9 и 13 клеток, и на
// широком листе грани есть у всех кусков каталога; на узумаки лист узкий, и у ореха и тунца
// поперёк по 4 клетки — порог nAcross >= 6 у них не срабатывает и теперь.
function topCell() { return PIX ? PIX / (2 * DPR) : 1; }

// Спрайт куска размером cols×rows клеток. Кэш нужен: лист перерисовывается на каждое
// движение мыши, а спрайт зависит только от вида начинки и размера — от кадра к кадру он тот же.
function pieceTopSprite(p, d, wPx, hPx, cell) {
  const cols = Math.max(2, Math.round(wPx / cell)), rows = Math.max(2, Math.round(hPx / cell));
  // ⚠ ВИД НАЧИНКИ — В КЛЮЧЕ КЭША. Прежде ключ держался на tex и rgb, и этого хватало, пока
  // рисунок выводился только из них. Шкура лежит под ИМЕНЕМ вида, а tex у тамаго, омлета и
  // шиитакэ один; совпади у двух видов ещё и цвет — они получили бы чужую картинку из кэша.
  const вид = kindOf(d);
  const шкура = SKINS ? skinField(вид) : null;
  const key = `${вид || d.tex}|${d.rgb}|${cols}|${rows}|${((p && p.phase) || 0).toFixed(2)}|${шкура ? 's' : '-'}`;
  const hit = TOP_CACHE.get(key);
  if (hit) return hit;

  const cv = document.createElement('canvas');
  cv.width = cols; cv.height = rows;
  const g = cv.getContext('2d'), img = g.createImageData(cols, rows);
  pieceTopFill(img.data, p, d, cols, rows, шкура);
  g.putImageData(img, 0, 0);
  if (TOP_CACHE.size > 96) TOP_CACHE.clear();     // размеры меняются с масштабом — не копим
  TOP_CACHE.set(key, cv);
  return cv;
}

// Клетки куска в RGBA. Отдельно от холста НАМЕРЕННО: сторож шкуры (checks.js, §5а-квинт)
// обязан читать эти байты, а без браузера холст их не отдаёт — getImageData там нули.
function pieceTopFill(data, p, d, cols, rows, шкура) {
  // Кусок длиннее, чем шире: ВДОЛЬ (lv) — большая сторона, ПОПЕРЁК (lu) — меньшая.
  const horiz = cols >= rows;
  const nAlong = horiz ? cols : rows, nAcross = horiz ? rows : cols;
  const pp = p || { phase: 0 };
  // ШКУРА ПОВТОРЯЕТСЯ ПО ДЛИНЕ БЕЗ ЗЕРКАЛА (issue #256, п. 5): отражение даёт симметричные
  // узоры, которых в еде не бывает, — на длинном футомаки это видно сразу. Период равен ширине
  // спрайта в клетках, и поле вдоль куска строго периодично: клетка i совпадает с i % период.
  // Масштаб ОДИН на обе оси — клетка шкуры остаётся квадратной, иначе фактуру тянет.
  // Короткие кусочки (креветка, орех, клубника) — тот же повтор: их спрайт и есть рядок,
  // и он выкладывается рядком по длине куска.
  const шаг = шкура ? nAcross / шкура.h : 0;                      // клеток на пиксель шкуры
  const период = шкура ? Math.max(1, Math.round(шкура.w * шаг)) : 0;
  // ⚑ И ЕЩЁ ОДНА НОРМИРОВКА — УЖЕ НА КЛЕТКАХ ЭТОГО КУСКА. Нормированный ряд шкуры даёт среднее
  // 1 на СВОЮ ширину, а на кусок ложится целое число периодов плюс огрызок: у лосося 2×74 из
  // 179 клеток, то есть 31 клетка огрызка — 17 % ряда с чужим средним. Замер: до этой поправки
  // огрызок уводил средний цвет куска на 3,9 из 255. Считаем среднее по ТЕМ клеткам, которые
  // действительно нарисуются, и делим на него: тогда ряд куска не осветлён и не затемнён.
  const попр = шкура ? new Float32Array(nAcross) : null;
  if (шкура) for (let a = 0; a < nAcross; a++) {
    const sy = Math.min(шкура.h - 1, Math.floor(a / шаг)) * шкура.w;
    let сумма = 0, их = 0;
    for (let l = 0; l < nAlong; l++) {
      const v = шкура.k[sy + Math.min(шкура.w - 1, Math.floor((l % период) / шаг))];
      if (v) { сумма += v; их++; }
    }
    попр[a] = их && сумма > 0 ? их / сумма : 1;
  }

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
    // ВОТ ЗДЕСЬ И ТОЛЬКО ЗДЕСЬ входит картинка: одним множителем яркости на модельный цвет.
    let k = 1;
    if (шкура) {
      const sy = Math.min(шкура.h - 1, Math.floor(across / шаг));
      const sx = Math.min(шкура.w - 1, Math.floor((along % период) / шаг));
      const v = шкура.k[sy * шкура.w + sx];
      if (v) k = v * попр[across];                // 0 — прозрачная клетка шкуры, рисунка тут нет
    }
    const o = (j * cols + i) * 4;
    data[o] = c[0] * k; data[o + 1] = c[1] * k; data[o + 2] = c[2] * k; data[o + 3] = 255;
  }
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
  const cell = topCell();
  const spr = pieceTopSprite(p, d, w, h, cell);
  ctx.save();
  ctx.imageSmoothingEnabled = !PIX;
  if (PIX) {
    // Тень тоже по сетке. Размытая тень вокруг цельного спрайта сразу выдаёт, что это
    // картинка поверх пикселей: в 16-битной графике тень — сдвинутый силуэт, а не градиент.
    // ⚠ Сдвиг — по клетке РИСА, а не куска (17.09, #256). Тень лежит НА РИСЕ, и шагать ей
    // положено его сеткой; со сдвигом в клетку куска (вдвое мельче) она из сдвинутого силуэта
    // превратилась бы в тёмную кромку в один пиксель — то есть в обводку, которой здесь не надо.
    const тень = PIX / DPR;
    ctx.shadowBlur = 0; ctx.shadowOffsetX = тень; ctx.shadowOffsetY = тень;
    // Прижать к сетке арт-пикселей: иначе спрайт ложится между клетками, кромка мылится,
    // и весь смысл пиксельного режима теряется — клетка должна быть видна как клетка.
    const x0 = Math.round(x / cell) * cell, y0 = Math.round(y / cell) * cell;
    ctx.drawImage(spr, x0, y0, spr.width * cell, spr.height * cell);
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
// ── КРОМКА СВЕТЛОЙ ОБЁРТКИ НА СВЕТЛОЙ ДОСКЕ (#76, решено 06.09.2026) ────────────
// Не-текстовый минимум — 3:1 (WCAG 2.2, критерий 1.4.11). Нори #22342b на циновке #c9a96c
// даёт 5,88:1 и ничего не просит. Тонкий омлет #e8b551 на ТОЙ ЖЕ циновке — 1,19:1: силуэт
// не читается вовсе. (В ui-review стояли 1,80 и 1,65 — это числа баз «рулет» и «лаваш»,
// которых в каталоге больше нет; замер устарел вместе с ними.)
//
// В обычном режиме границу держит контактная тень — замерено 3,73:1 к доске и 4,44:1 к
// обёртке, порог выполнен. В ПИКСЕЛЬНОМ её снимают вместе со всеми полупрозрачными кромками,
// и остаётся только смещённая копия силуэта: она даёт кромку справа и снизу, а сверху и
// слева — ничего. Именно там светлая обёртка и сливается с доской.
//
// Кромка возвращается пиксель-артовым способом: непрозрачный контур в один арт-пиксель (так
// его и делали в 16 битах), и ТОЛЬКО там, где этого требует замер. Порог — не вкус: contrast
// (обёртка, доска) < 3. У нори условие ложно, и её вид не меняется ни на пиксель.
//
// Доску НЕ трогаем: правило «срез лежит на доске своей базы» остаётся в силе. И это не
// отвергнутое кольцо-обводка — то было СВЕТЛОЕ кольцо поверх, читавшееся как вторая нори;
// здесь тёмный контур под срезом, по силуэту, который посчитала модель.
const _lin = c => (c /= 255) <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
function _lum(hex) {
  const h = String(hex).replace('#', '');
  if (h.length < 6) return 0;
  return 0.2126 * _lin(parseInt(h.slice(0, 2), 16)) + 0.7152 * _lin(parseInt(h.slice(2, 4), 16)) + 0.0722 * _lin(parseInt(h.slice(4, 6), 16));
}
// Контур в один арт-пиксель по всем четырём сторонам. Кладётся ДО картинки и до тени: тень ляжет
// поверх и не будет с ним спорить.
function рисоватьКромку(img, x0, y0, sz) {
  const sil = pixSilhouette(img);
  for (const [dx, dy] of [[-PIX, 0], [PIX, 0], [0, -PIX], [0, PIX]]) ctx.drawImage(sil, x0 + dx, y0 + dy, sz, sz);
}
const _kCache = new Map();
function нужнаКромка(b) {
  if (!b || !b.wrapper || !b.mat) return false;
  const key = b.wrapper + b.mat;
  let v = _kCache.get(key);
  if (v === undefined) {
    const a = _lum(b.wrapper), c = _lum(b.mat), hi = Math.max(a, c), lo = Math.min(a, c);
    v = (hi + 0.05) / (lo + 0.05) < 3;
    _kCache.set(key, v);
  }
  return v;
}
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
function drawFaceImg(img, x, y, size, scaleX = 1, alpha = 1, безТени = false, b = B()) {
  ctx.save(); ctx.globalAlpha = alpha; ctx.translate(x, y); ctx.scale(Math.max(0.01, scaleX), 1);
  if (безТени) {
    // ⚠ БЕЗ ТЕНИ — НЕ ЗНАЧИТ БЕЗ КРОМКИ (находка ревью PR #219). Здесь снята тень, потому что срез
    // растянут почти на весь лист и тень съедала бы поле; но кромка — не тень, а единственное, что
    // отделяет светлую обёртку от подложки. Подложка здесь ДРУГАЯ — не циновка, а лист `#e4ded6`, и
    // порог формально считается не по ней. Проверено, что это ничего не меняет: набор непроходящих
    // обёрток совпадает — нори 5,88:1 на циновке и 9,86:1 на листе, остальные четыре не держат ни
    // там, ни там (рисовая бумага 1,81 / 1,08 · гюхи 1,98 / 1,18 · соевая 1,28 / 1,31 · омлет
    // 1,19 / 1,41). Порядок между ними меняется, решение «да/нет» — нет.
    if (PIX) { const q = v => Math.round(v / PIX) * PIX, sz = Math.max(PIX, q(size));
      const x0 = q(-sz / 2), y0 = q(-sz / 2);
      ctx.imageSmoothingEnabled = false;
      if (нужнаКромка(b)) рисоватьКромку(img, x0, y0, sz);
      ctx.drawImage(img, x0, y0, sz, sz); }
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
    if (нужнаКромка(b)) рисоватьКромку(img, x0, y0, sz);
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

