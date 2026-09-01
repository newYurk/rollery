// Примитивы inverse design: схема, проверка, габариты, минимальный элемент.
//
// ЧИСТЫЙ МОДУЛЬ. Ничего не читает снаружи, ничего не меняет, не знает ни про S, ни про
// BASES, ни про модель. Всё, что нужно, приходит аргументами. Поэтому его можно гонять
// отдельно от страницы — и поэтому он не может молча разойтись с игрой: расходиться не с чем.
//
// ЕДИНИЦЫ. Те же, что в модели: 1 единица = 5 мм. Миллиметры сюда не заходят вовсе, поэтому
// и множителя здесь НЕТ — модуль считает габариты, а не переводит меры. Раньше тут стояла
// собственная константа PRIM_U_MM = 5: не использованная ни разу внутри файла, но
// экспортированная наружу, то есть третье место, где живёт то же число (issue #119).
// Убрана. Если миллиметры однажды понадобятся, брать U_MM из каталога, а не заводить своё.
//
// ЧЕГО ЗДЕСЬ НЕТ НАМЕРЕННО: порогов. Модуль отвечает, КАКОЙ у примитива самый узкий размер,
// а решает, достаточно ли этого, — feasibility, потому что порог зависит от материала.
// Разделение не косметическое: минимальный элемент у риса и у нори разный.

const PRIM_TYPES = ['circle', 'ellipse', 'rect', 'triangle', 'strip'];

// Полугабариты примитива в его СОБСТВЕННЫХ осях, до поворота: [по u, по v].
// Для strip длина идёт по направлению `direction`, ширина — поперёк.
function primHalfExtents(p) {
  const q = p.params || {};
  switch (p.type) {
    case 'circle':   return [q.radius, q.radius];
    case 'ellipse':  return [q.radiusU, q.radiusV];
    case 'rect':     return [q.widthU / 2, q.heightV / 2];
    // Треугольник: основание по u, высота по v. Габарит — прямоугольник вокруг него;
    // это ЗАВЫШЕНИЕ площади, и оно намеренное: пересечения по габаритам должны ошибаться
    // в сторону «перекрываются», иначе поиск отдаст раскладку, которая на самом деле слиплась.
    case 'triangle': return [q.baseU / 2, q.heightV / 2];
    case 'strip':    return q.direction === 'v' ? [q.widthV / 2, q.lengthU / 2]
                                                : [q.lengthU / 2, q.widthV / 2];
    default:         return [0, 0];
  }
}

// Габаритный прямоугольник с учётом поворота. Повёрнутый прямоугольник описывается
// прямоугольником со сторонами |cos|·a + |sin|·b — обычная опорная функция, без тригонометрии
// в цикле поиска: угол приходит готовым.
function primBounds(p) {
  const [a, b] = primHalfExtents(p);
  const rot = p.rotation || 0, c = Math.abs(Math.cos(rot)), s = Math.abs(Math.sin(rot));
  const hu = a * c + b * s, hv = a * s + b * c;
  const u = p.anchor ? p.anchor.u : 0, v = p.anchor ? p.anchor.v : 0;
  return { u0: u - hu, u1: u + hu, v0: v - hv, v1: v + hv };
}

// САМЫЙ УЗКИЙ РАЗМЕР — то, что физически не может быть тоньше зерна.
// У полосы это ШИРИНА, а не длина: полоса в 3,5 мм шириной и 10 см длиной — нормальный
// ингредиент (полоса тамаго), а вот полоса тоньше зерна не существует ни при какой длине.
// Ошибка «взять длину» превратила бы законные длинные полосы в невыполнимые.
function primMinFeature(p) {
  const q = p.params || {};
  switch (p.type) {
    case 'circle':   return 2 * q.radius;
    case 'ellipse':  return 2 * Math.min(q.radiusU, q.radiusV);
    case 'rect':     return Math.min(q.widthU, q.heightV);
    // У треугольника узкое место — не сторона, а высота у вершины: она сходит в ноль.
    // Берём меньшую из основания и высоты как оценку СВЕРХУ и помечаем это честно:
    // настоящий минимальный элемент треугольника меньше, и если он окажется важен,
    // считать надо вписанную окружность, а не габариты.
    // ⚑ inferred: оценка сверху, не точный минимум.
    case 'triangle': return Math.min(q.baseU, q.heightV);
    case 'strip':    return q.widthV;
    default:         return 0;
  }
}

// Пересекаются ли габариты. Касание не считается пересечением: два бруска встык — законная
// раскладка, и повара так и кладут (marron: несколько кусочков собирают в один брусок).
function primBoxesOverlap(a, b) {
  const A = primBounds(a), B = primBounds(b);
  return A.u0 < B.u1 && B.u0 < A.u1 && A.v0 < B.v1 && B.v0 < A.v1;
}

// Проверка схемы. Возвращает список ошибок — пустой означает «схема соблюдена».
// Здесь только СХЕМА: типы, знаки, обязательные поля. Помещается ли это на лист и не тоньше
// ли зерна — вопрос feasibility, у которого есть контекст.
function primValidate(p) {
  const e = [];
  if (!p || typeof p !== 'object') return ['примитив не объект'];
  if (typeof p.id !== 'string' || !p.id) e.push('нет id');
  if (PRIM_TYPES.indexOf(p.type) < 0) e.push(`тип «${p.type}» неизвестен, ожидается один из: ${PRIM_TYPES.join(', ')}`);
  if (typeof p.materialId !== 'string' || !p.materialId) e.push('нет materialId');
  if (!p.anchor || !isFinite(p.anchor.u) || !isFinite(p.anchor.v)) e.push('anchor должен быть { u, v } из чисел');
  if (p.rotation !== undefined && !isFinite(p.rotation)) e.push('rotation не число');
  if (p.layer !== undefined && !Number.isInteger(p.layer)) e.push('layer должен быть целым');
  const q = p.params || {};
  const pos = (name) => { const x = q[name];
    if (!isFinite(x)) e.push(`params.${name} отсутствует или не число`);
    else if (x <= 0) e.push(`params.${name} должен быть > 0, получено ${x}`); };
  switch (p.type) {
    case 'circle':   pos('radius'); break;
    case 'ellipse':  pos('radiusU'); pos('radiusV'); break;
    case 'rect':     pos('widthU'); pos('heightV'); break;
    case 'triangle': pos('baseU'); pos('heightV'); break;
    case 'strip':    pos('lengthU'); pos('widthV');
      if (q.direction !== 'u' && q.direction !== 'v') e.push("params.direction должен быть 'u' или 'v'");
      break;
  }
  return e;
}

// Площадь примитива — нужна поиску, чтобы не тратить бюджет на кандидатов, у которых
// суммарная площадь начинок заведомо больше площади грядки.
function primArea(p) {
  const q = p.params || {};
  switch (p.type) {
    case 'circle':   return Math.PI * q.radius * q.radius;
    case 'ellipse':  return Math.PI * q.radiusU * q.radiusV;
    case 'rect':     return q.widthU * q.heightV;
    case 'triangle': return q.baseU * q.heightV / 2;
    case 'strip':    return q.lengthU * q.widthV;
    default:         return 0;
  }
}

if (typeof module !== 'undefined' && module.exports)
  module.exports = { PRIM_TYPES, primHalfExtents, primBounds, primMinFeature, primBoxesOverlap, primValidate, primArea };
