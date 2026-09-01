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

// ⛔ СЕМЬ ПОЛЕЙ НИЖЕ НЕ ЧИТАЕТ НИКТО — ПРОВЕРЕНО ЗАМЕРОМ 01.09 (#74, #143).
//
// Подсчёт обращений к каждому полю во ВСЁМ play/, включая сам этот файл:
//   baseThickness 5 · ingKey 3 · minFeatureSize 1 · hUConvention 1  — живые, их читает
//     matVerifyAgainstING, который зовёт play/checks.js;
//   placementClass 0 · compressibility 0 · preferFarEdge 0 · preferNearEdge 0 ·
//     mustBeInsideRice 0 · allowOuterTurn 0 · minBundleMM 0  — НОЛЬ обращений.
//
// Это данные без потребителя — тот же сорт тишины, что `heightAt` без результата (#143):
// сущность объявлена, выглядит действующей, и не влияет ни на что. Открывший файл решит,
// что размещение уже описано, и ошибётся.
//
// ⚑ И `placementClass` вдобавок ОТМЕНЁН по существу: 01.09 решено (#74, domain-contract §5.5),
// что классов вещества не будет — свойства живут полями в каталоге продуктов, а классы
// выводятся из них функцией. Довод измерен: тамаго мягкий (stiff 0,18) и при этом осевой,
// класса под него не существует. Значит `placementClass` не «ждёт подключения» — он описывает
// отменённый замысел, и оставлять его как есть значит врать читателю.
//
// НЕ УДАЛЯЮ СЕЙЧАС, и вот почему: удаление — правка на десяток строк, а решение, что делать
// с инверсным каталогом целиком (он весь про инверсный дизайн, #80), не принято. Пометка
// честнее тихого удаления и честнее тихого сохранения. Дом решения — #74.
//
// placementClass — из спецификации ред. 2 (ОТМЕНЕНО, см. выше):
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
    // 0,10 мм. ⚠ ЭТО ВЫВОД, А НЕ ЗАМЕР: толщину нори НЕ НАЗЫВАЕТ ни один источник. FAO и
    // Nisizawa дают размер листа (21×19 см) и массу (≈3 г) — толщина получена делением через
    // плотность. Прежняя подпись ставила два имени вплотную к числу, как будто они его дают;
    // в play/state.js это исправили ещё 30.08, а здесь копия числа осталась с прежней подписью
    // (найдено вечерней сверкой 31.08, #109). Тот же класс, что 20–25 мм в catalog.js.
    baseThickness: 0.02,
    compressibility: 0.0,        // лист нерастяжим и несжимаем: на этом стоит вывод про складки
    // Нори РИСУЕТ ЛИНИЮ, а не пятно: её минимальный элемент — толщина листа, а не зерно.
    // Отсюда же и ограничение сверху: нори не гнётся туже некоторого радиуса.
    minFeatureSize: 0.02,
    minRadius: GRAIN_ACROSS,     // ⚑ inferred: замера радиуса излома нори нет
    mustBeInsideRice: true, allowOuterTurn: true,
    note: 'нерастяжима — складок не бывает, пока лист удерживают (docs/reality-check.md)',
    // ⚠ УСЛОВНОСТЬ ЧИТАЕМОСТИ, ОБЪЯВЛЕННАЯ ЯВНО. Нори-патч в ING нарисован толщиной 0,15 ед.
    // (0,75 мм) — в 7,5 раза толще физической. Причина: 0,02 ед. на срезе меньше пикселя, и
    // патч исчезал бы совсем. Обёртка ту же беду решает минимумом на отрисовке (WRAP_MIN_CSS),
    // патч — пока нет, поэтому толщина завышена в самой модели.
    // Раньше сторож просто пропускал весь класс 'contour' — и расхождение было НЕВИДИМЫМ.
    // Теперь условность объявлена данными и проверяется: уедет любое из двух чисел — упадёт.
    hUConvention: { drawn: 0.15, real: 0.02,
      why: 'патч тоньше пикселя на срезе; довести до 0,02 можно, добавив минимум отрисовки — #109' },
  },
  cucumber: {
    id: 'cucumber', name: 'Огурец', color: '#79b55c', ingKey: 'cucumber',
    placementClass: 'rigid',
    // ⚠ Толщина ДОЛЖНА совпадать с hU в ING — сторож это проверяет. 1,98 вместо прежних 1,6:
    // огурец переописан сектором по источнику (см. catalog.js): ⌀28 мм на 8 долей = 14 × 9,9 мм.
    baseThickness: 1.98, compressibility: 0.15,
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
    // ⚠ Толщина ДОЛЖНА совпадать с hU в ING — сторож это проверяет. 2,0 вместо прежних 1,6:
    // лосось переописан бруском 「1cm角の棒状」 по рецептам (abc5505, catalog.js), сюда правка
    // не доехала, и ?check краснел с того коммита до вечера 01.09 — его не открывали.
    baseThickness: 2.0, compressibility: 0.6,
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
    // Условность читаемости объявляется В ДАННЫХ (hUConvention) и от этого не перестаёт
    // проверяться: сверяем ING с ОБЪЯВЛЕННЫМ значением, а саму условность — с физическим.
    // Прежняя редакция пропускала весь класс 'contour' целиком, и нори с толщиной в 7,5 раза
    // больше физической проходила молча — ровно то, от чего сторож и заведён.
    const conv = m.hUConvention;
    const expect = conv ? conv.drawn : m.baseThickness;
    if (isFinite(d.hU) && Math.abs(d.hU - expect) > 1e-6)
      bad.push(`${id}: ожидалось hU ${expect}${conv ? ' (условность)' : ''}, в ING ${d.hU}`);
    if (conv && Math.abs(conv.real - m.baseThickness) > 1e-9)
      bad.push(`${id}: условность объявляет real ${conv.real}, а baseThickness ${m.baseThickness}`);
  }
  const w = wrappers && wrappers.nori;
  if (w && Math.abs(w.mm / MAT_U_MM - MATERIALS.nori.baseThickness) > 1e-9)
    bad.push(`nori: baseThickness ${MATERIALS.nori.baseThickness} против ${w.mm} мм в WRAPPERS`);
  // ЗЕРНО СВЕРЯЕТСЯ ЗДЕСЬ ЖЕ (issue #119). Шапка модуля обещает, что дублирование чисел
  // прикрыто этой проверкой, — а зерно мимо неё проходило: сверялись только цвета и толщины.
  // GRAIN_ACROSS считается из 3,5 мм, GRAIN в игре записан числом 0,7; сойтись они обязаны,
  // и молчаливое расхождение здесь означало бы, что порог «тоньше рисинки не выложить»
  // в поиске раскладки и в отрисовке зерна — разные пороги.
  if (typeof GRAIN === 'number' && Math.abs(GRAIN_ACROSS - GRAIN) > 1e-9)
    bad.push(`зерно: GRAIN_ACROSS ${GRAIN_ACROSS} (из ${GRAIN_ACROSS_MM} мм) против GRAIN ${GRAIN} в модели`);
  return bad;
}

if (typeof module !== 'undefined' && module.exports)
  module.exports = { MAT_U_MM, GRAIN_ACROSS_MM, GRAIN_ALONG_MM, GRAIN_ACROSS,
                     MATERIALS, MAT_STARTER_PALETTE, matGet, matMinFeature, matVerifyAgainstING };
