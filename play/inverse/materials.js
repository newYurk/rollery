// Каталог материалов inverse design: стартовый набор и его физические ограничения.
//
// ЧИСТЫЙ МОДУЛЬ, как и primitives.js: ничего не читает из игры. Числа продублированы сюда
// НАМЕРЕННО и с указанием, откуда они взяты, — потому что модуль обязан работать без страницы.
// Расхождение с игрой ловится проверкой `matVerifyAgainstING`, которую зовут из стенда: она
// сверяет каталог с живым ING и падает, если числа разъехались. Дублирование без такой сверки
// было бы ровно тем дрейфом двух реализаций, от которого предостерегает спецификация.
//
// ЕДИНИЦЫ: 1 = 5 мм, как в модели.

const MAT_U_MM = 5;

// ЗЕРНО. Минимальный элемент задан размером рисинки — ничего тоньше в рисе не выложить.
// Числа из docs/reality-check.md и docs/geometry-audit.md; в игре это GRAIN = 0,7 ед.
// ВАЖНО И НЕСИММЕТРИЧНО: 3,5 мм — ШИРИНА зерна, 7,7 мм — ДЛИНА. Полоса тоньше 3,5 мм
// невозможна ни при какой длине, а вот КОРОЧЕ 7,7 мм элемент быть может — он просто
// придётся на одно зерно. Поэтому порог один, поперечный, и берётся от ширины.
const GRAIN_ACROSS_MM = 3.5;
const GRAIN_ALONG_MM = 7.7;
const GRAIN_ACROSS = GRAIN_ACROSS_MM / MAT_U_MM;   // 0,7 ед.

// placementClass — из спецификации ред. 2:
//   support — рис: держит форму, на нём всё лежит;
//   contour — нори: лист, рисует линию, не объём;
//   filling — мягкая начинка: мнётся, принимает форму соседей;
//   rigid   — твёрдая: держит сечение, работает сердечником.
const MATERIALS = {
  riceWhite: {
    id: 'riceWhite', name: 'Рис', color: '#f4ecda', ingKey: null,
    placementClass: 'support',
    baseThickness: 1.0,          // ед. = толщина грядки, задаётся базой (hoso 1,4 · futo 2,4)
    compressibility: 0.55,       // = beta у суши-баз
    minFeatureSize: GRAIN_ACROSS,
    mustBeInsideRice: false, allowOuterTurn: true,
    note: 'фон и материал рисования: локальная толщина задаёт белые прокладки узора (issue #17)',
  },
  ricePink:   { id: 'ricePink',   name: 'Розовый рис', color: '#f2b3c2', ingKey: 'ricePink',
    placementClass: 'support', baseThickness: 1.0, compressibility: 0.55,
    minFeatureSize: GRAIN_ACROSS, mustBeInsideRice: false, allowOuterTurn: true },
  riceGreen:  { id: 'riceGreen',  name: 'Зелёный рис', color: '#b7cf86', ingKey: 'riceGreen',
    placementClass: 'support', baseThickness: 1.0, compressibility: 0.55,
    minFeatureSize: GRAIN_ACROSS, mustBeInsideRice: false, allowOuterTurn: true },
  nori: {
    id: 'nori', name: 'Нори', color: '#22342b', ingKey: 'nori',
    placementClass: 'contour',
    baseThickness: 0.02,         // 0,10 мм — FAO/Nisizawa: лист 21×19 см ≈ 3 г
    compressibility: 0.0,        // лист нерастяжим и несжимаем: на этом стоит вывод про складки
    // Нори РИСУЕТ ЛИНИЮ, а не пятно: её минимальный элемент — толщина листа, а не зерно.
    // Отсюда же и ограничение сверху: нори не гнётся туже некоторого радиуса.
    minFeatureSize: 0.02,
    minRadius: GRAIN_ACROSS,     // ⚑ inferred: замера радиуса излома нори нет
    mustBeInsideRice: true, allowOuterTurn: true,
    note: 'нерастяжима — складок не бывает, пока лист удерживают (docs/reality-check.md)',
  },
  cucumber: {
    id: 'cucumber', name: 'Огурец', color: '#79b55c', ingKey: 'cucumber',
    placementClass: 'rigid',
    baseThickness: 1.6, compressibility: 0.15,
    minFeatureSize: GRAIN_ACROSS,
    // Повара кладут твёрдое ближе к себе — оно работает СЕРДЕЧНИКОМ (marron, Сираи).
    // И отдельно: несколько тонких кусочков рассеивают усилие скрутки и раскалывают центр,
    // поэтому их собирают в один брусок (magickitchen.blog). Порог 1 см — оттуда же.
    preferNearEdge: true, minBundleMM: 10,
    mustBeInsideRice: true, allowOuterTurn: false,
  },
  salmon: {
    id: 'salmon', name: 'Лосось', color: '#ef8a66', ingKey: 'salmon',
    placementClass: 'filling',
    baseThickness: 1.6, compressibility: 0.6,
    minFeatureSize: GRAIN_ACROSS,
    // Мягкое кладут СВЕРХУ (OSUSHI STUDIO), и рассыпчатое — к ДАЛЬНЕМУ краю, потому что при
    // скрутке поднимают ближний и там его не удержать (gourmet-note.jp).
    preferFarEdge: false, mustBeInsideRice: true, allowOuterTurn: false,
  },
};

const MAT_STARTER_PALETTE = ['riceWhite', 'ricePink', 'riceGreen', 'nori', 'cucumber', 'salmon'];

function matGet(id) { return MATERIALS[id] || null; }

// Порог минимального элемента для конкретного материала — то, чем feasibility меряет
// примитив. Вынесено сюда, а не в primitives.js: порог зависит от материала, а геометрия нет.
function matMinFeature(id) { const m = MATERIALS[id]; return m ? m.minFeatureSize : GRAIN_ACROSS; }

// СВЕРКА С ЖИВОЙ ИГРОЙ. Числа в каталоге продублированы, и единственное, что защищает их от
// расхождения, — эта функция. Зовётся из стенда, где ING доступен; сама ING не импортирует,
// чтобы модуль оставался чистым. Возвращает список расхождений: пустой = сошлось.
function matVerifyAgainstING(ing, wrappers) {
  const bad = [];
  for (const id in MATERIALS) {
    const m = MATERIALS[id]; if (!m.ingKey) continue;
    const d = ing && ing[m.ingKey];
    if (!d) { bad.push(`${id}: в ING нет ключа ${m.ingKey}`); continue; }
    if (d.color !== m.color) bad.push(`${id}: цвет ${m.color} против ${d.color} в ING`);
    if (m.placementClass !== 'contour' && isFinite(d.hU) && Math.abs(d.hU - m.baseThickness) > 1e-6)
      bad.push(`${id}: baseThickness ${m.baseThickness} против hU ${d.hU} в ING`);
  }
  const w = wrappers && wrappers.nori;
  if (w && Math.abs(w.mm / MAT_U_MM - MATERIALS.nori.baseThickness) > 1e-9)
    bad.push(`nori: baseThickness ${MATERIALS.nori.baseThickness} против ${w.mm} мм в WRAPPERS`);
  return bad;
}

if (typeof module !== 'undefined' && module.exports)
  module.exports = { MAT_U_MM, GRAIN_ACROSS_MM, GRAIN_ALONG_MM, GRAIN_ACROSS,
                     MATERIALS, MAT_STARTER_PALETTE, matGet, matMinFeature, matVerifyAgainstING };
