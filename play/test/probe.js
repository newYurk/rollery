'use strict';
// ИНВАРИАНТЫ СРЕЗА: одна мерка для обоих путей — legacy и facade.
//
// ЗАЧЕМ ОТДЕЛЬНЫМ ФАЙЛОМ. Сравнение «facade не изменил поведение» честно только тогда, когда
// обе стороны меряются ОДНИМ кодом, а различается лишь то, КАК добыта модель: напрямую
// (buildModel) или через facade. Если мерки разные, расхождение спишется на мерку.
//
// ПОЧЕМУ НЕ ХЭШ КАРТИНКИ. Canvas рисует по-разному на разных машинах и в разных браузерах
// (сглаживание, субпиксели), поэтому пиксельный хэш — плохой эталон. Меряем ДОМЕННОЕ:
// числа намотки, доли материалов на срезе и точечные пробы в фиксированных точках.
//
// Классы материала (materialAt): 'out' | 'core' | 'wrap' | 'spread' | { cls:'patch', mt }.
// Патч сворачивается в 'patch:<kind>' — важно не «есть ли что-то», а ЧТО именно лежит в точке.

// ⚠ СЕТКА И ИМЕНА КЛАССОВ БЕРУТСЯ У ДОМЕНА, А НЕ ЗАДАЮТСЯ ЗДЕСЬ (правка 31.08).
// Держать свои 12 и 24 значило сравнивать модель со слепком по ДРУГОЙ сетке, чем считает
// домен: правка ROLL_SLICE_RINGS до слепка бы не дошла, и регрессия молча перестала бы
// стеречь то, что стережёт. Та же болезнь, что уже случилась со свёрткой карты (ниже).
const PROBE_RINGS = ROLL_SLICE_RINGS;
const PROBE_RAYS = ROLL_SLICE_RAYS;
const PROBE_SLICES = [0.25, 0.5, 0.75];   // ломтики, по которым берём пробы — это выбор пробы

// Класс материала в точке (r, φ) одного ломтика. Само правило — в домене (rollProbeClass).
const probeClassAt = (m, wd, vSlice, r, phi) => rollProbeClass(materialAt(m, wd, vSlice, r, phi));

// Карта материалов среза, свёрнутая в сравнимый вид: сколько пикселей каждого класса
// плюс выборка значений в фиксированных точках. Полная карта 56×56 в слепок не кладётся —
// её и незачем хранить целиком: счётчики ловят сдвиг долей, выборка ловит сдвиг узора.
// Это характеризация ЧИТАЮЩЕГО пути (materialMap → similarity), который переезжает за
// facade: слепок снят ДО переезда, поэтому проверка после него — настоящая, а не тавтология.
function mapSignature(m, vSlice) {
  // ⚠ СВЁРТКА ЖИВЁТ В ДОМЕНЕ (play/domain/roll.js, rollMapDigest) — здесь только вызов.
  // До 31.08 тут лежала вторая копия той же логики, и копии разошлись при первой правке:
  // домен считал классы числами, проба именами, регрессия дала 75 расхождений на пустом месте.
  return rollMapDigest(materialMap(ROLL_MAP_SIZE, vSlice, m, m.Rmax));
}

// Полный набор инвариантов модели: числа намотки + доли материалов + пробы.
// round4 держит сравнение устойчивым к последнему биту double.
function rollInvariants(m) {
  const r4 = x => Math.round(x * 1e4) / 1e4;
  const wd = windFor(m, 0.5);
  const inv = {
    turns: r4(wd.turns),
    outerDiameterMm: r4(2 * m.Rmax * U_MM),
    closePoint: r4(wd.sClose),
    sheetEnd: r4(wd.sEnd),
    sheetLength: r4(m.g.L),
    hasCore: !!m.core,
    // Форма прессовки — часть модели (m.shape). Без неё круглый и квадратный ролл давали
    // одинаковый набор инвариантов, и F04 «квадратная прессовка» проверял не то, что обещал.
    shape: m.shape,
    coreRadius: r4(m.core ? m.core.R : 0),
    coreFold: r4(m.core ? m.core.sFold : 0),
    patchCount: m.list.length,
    materialFractions: {},
    probes: [],
  };
  const counts = {};
  let total = 0;
  for (const v of PROBE_SLICES) {
    const w = windFor(m, v);
    for (let ri = 0; ri < PROBE_RINGS; ri++) {
      for (let ai = 0; ai < PROBE_RAYS; ai++) {
        const r = (ri + 0.5) / PROBE_RINGS * m.Rmax, phi = ai / PROBE_RAYS * TAU;
        const cls = probeClassAt(m, w, v, r, phi);
        counts[cls] = (counts[cls] || 0) + 1; total++;
        // В подробные пробы кладём разрежённую выборку — её сравнивают поточечно,
        // и она ловит СДВИГ узора, который доли материалов могли бы усреднить.
        if (ri % 4 === 1 && ai % 6 === 0) inv.probes.push(v + '|' + ri + '|' + ai + '=' + cls);
      }
    }
  }
  for (const k of Object.keys(counts).sort()) inv.materialFractions[k] = r4(counts[k] / total);
  // Карта материалов: путь, который переехал за facade (issue #72, шаг 2).
  inv.map = mapSignature(m, 0.5);
  // ⚠ selfSimilarity стережёт УЗКОЕ место и не притворяется большим: similarity(m, m) на одном
  // срезе вырождает почти всё тело функции — ревью PR #102 показало, что пять мутаций внутри
  // (границы near, схлопывание 3×3 в точку, счёт одного среза вместо всех, Rref max→min,
  // порог a[i] >= 3) при таком входе ВЫЖИВАЮТ. Что она реально фиксирует — симметрию двойного
  // счёта (total = |A| + |B|), то самое место, которое ревью 26.08 предлагало «починить».
  // За остальное отвечают map.counts и межмодельные пары ниже.
  inv.selfSimilarity = r4(similarity(m, m, [0.5]));
  return inv;
}

// ── МЕЖМОДЕЛЬНЫЕ ПАРЫ ────────────────────────────────────────────────────────
// Похожесть модели с СОБОЙ почти ничего не проверяет: обе карты совпадают пиксель в пиксель,
// и допуск near(), общий масштаб Rref, перебор срезов и порог класса в этом случае не влияют
// ни на что. Ревью PR #102 доказало это мутациями — пять правок внутри similarityOf выжили.
//
// Пара РАЗНЫХ моделей на НЕСКОЛЬКИХ срезах убивает все пять сразу: числа расходятся, если
// схлопнуть окрестность (0,456 → 0,288), если потерять общий масштаб (→ 0,415), если считать
// один срез вместо трёх или сдвинуть порог класса.
const ROLL_PAIR_SLICES = [0.25, 0.5, 0.75];
// ⚠ Пары строятся ВОЗМУЩЕНИЕМ, а не выбором двух разных fixtures. Первые две попытки взяли
// готовые пары — и обе дали ровно 0: у разных баз даже общая начинка попадает в совсем другое
// место, пересечения нет. А ноль стережёт немногим лучше единицы, он держится при большинстве
// мутаций. Нужны числа В СЕРЕДИНЕ — их даёт близкая, но не тождественная пара.
const rcp = id => JSON.parse(JSON.stringify(ROLL_FIXTURES.find(f => f.id === id).recipe));
const ROLL_PAIRS = [
  // тот же рецепт, другая рука: узор совпадает, намотка разная
  { key: 'F02~F05 рука', a: () => rcp('F02-futomaki-basic'), b: () => rcp('F05-hand-variation') },
  // один кусок сдвинут вдоль скрутки на 0,06 листа: узор почти тот же, но поехал
  { key: 'F02~сдвиг', a: () => rcp('F02-futomaki-basic'),
    b: () => { const r = rcp('F02-futomaki-basic'); r.list[0].u += 0.06; return r; } },
  // та же раскладка, другая прессовка: круг против квадрата. Число близко к единице (0,989)
  // намеренно — форма меняет карту слабо, но если её потерять, станет РОВНО 1, и это видно.
  { key: 'F04~форма', a: () => rcp('F04-puzzle-recipe'),
    b: () => { const r = rcp('F04-puzzle-recipe'); r.shape = 'round'; return r; } },
];

// Похожести всех пар по моделям, добытым переданной функцией (у legacy и facade она разная).
function pairSimilarities(modelOfRecipe, simOf) {
  const out = {};
  for (const p of ROLL_PAIRS)
    out[p.key] = Math.round(simOf(modelOfRecipe(p.a()), modelOfRecipe(p.b()), ROLL_PAIR_SLICES) * 1e4) / 1e4;
  return out;
}

// Сравнение двух наборов инвариантов. Возвращает список расхождений (пустой — совпало).
// Допуск нужен: facade клонирует рецепт, и порядок операций с плавающей точкой может
// отличаться в последнем бите. 1e-6 — заведомо меньше любого содержательного изменения.
function invariantsDiff(a, b, tol) {
  const t = tol === undefined ? 1e-6 : tol, out = [];
  const num = (k, x, y) => { if (Math.abs(x - y) > t) out.push(`${k}: ${x} ≠ ${y}`); };
  num('turns', a.turns, b.turns);
  num('outerDiameterMm', a.outerDiameterMm, b.outerDiameterMm);
  num('closePoint', a.closePoint, b.closePoint);
  num('sheetEnd', a.sheetEnd, b.sheetEnd);
  num('sheetLength', a.sheetLength, b.sheetLength);
  num('coreRadius', a.coreRadius, b.coreRadius);
  num('coreFold', a.coreFold, b.coreFold);
  if (a.hasCore !== b.hasCore) out.push(`hasCore: ${a.hasCore} ≠ ${b.hasCore}`);
  if (a.shape !== b.shape) out.push(`shape: ${a.shape} ≠ ${b.shape}`);
  if (a.patchCount !== b.patchCount) out.push(`patchCount: ${a.patchCount} ≠ ${b.patchCount}`);
  const keys = new Set([...Object.keys(a.materialFractions), ...Object.keys(b.materialFractions)]);
  for (const k of keys) num('доля ' + k, a.materialFractions[k] || 0, b.materialFractions[k] || 0);
  num('selfSimilarity', a.selfSimilarity, b.selfSimilarity);
  if (a.map && b.map) {
    const mk = new Set([...Object.keys(a.map.counts), ...Object.keys(b.map.counts)]);
    for (const k of mk) num('карта, класс ' + k, a.map.counts[k] || 0, b.map.counts[k] || 0);
    if (a.map.probe !== b.map.probe) {
      const pa = String(a.map.probe).split(','), pb = String(b.map.probe).split(',');
      let bad = 0;
      for (let i = 0; i < Math.max(pa.length, pb.length); i++) if (pa[i] !== pb[i]) bad++;
      out.push(`карта среза: ${bad} проб из ${pa.length} не совпали`);
    }
  } else if (!!a.map !== !!b.map) out.push('карта среза есть только у одной стороны');
  const n = Math.max(a.probes.length, b.probes.length);
  let bad = 0;
  for (let i = 0; i < n; i++) if (a.probes[i] !== b.probes[i]) bad++;
  if (bad) out.push(`пробы среза: ${bad} из ${n} не совпали (первая: ${a.probes.find((p, i) => p !== b.probes[i])} ≠ ${b.probes.find((p, i) => p !== a.probes[i])})`);
  return out;
}
