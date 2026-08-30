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

const PROBE_RINGS = 12;     // радиусов в сетке проб
const PROBE_RAYS = 24;      // лучей
const PROBE_SLICES = [0.25, 0.5, 0.75];   // ломтики, по которым берём пробы

// Класс материала в точке (r, φ) одного ломтика — строкой, пригодной для сравнения.
function probeClassAt(m, wd, vSlice, r, phi) {
  const q = materialAt(m, wd, vSlice, r, phi);
  if (!q) return 'null';
  if (q.cls === 'patch') return 'patch:' + (q.mt && q.mt.p ? q.mt.p.kind : '?');
  return q.cls;
}

// Карта материалов среза, свёрнутая в сравнимый вид: сколько пикселей каждого класса
// плюс выборка значений в фиксированных точках. Полная карта 56×56 в слепок не кладётся —
// её и незачем хранить целиком: счётчики ловят сдвиг долей, выборка ловит сдвиг узора.
// Это характеризация ЧИТАЮЩЕГО пути (materialMap → similarity), который переезжает за
// facade: слепок снят ДО переезда, поэтому проверка после него — настоящая, а не тавтология.
function mapSignature(m, vSlice) {
  const size = 56, map = materialMap(size, vSlice, m, m.Rmax);
  const counts = {}, probe = [];
  for (let i = 0; i < map.length; i++) counts[map[i]] = (counts[map[i]] || 0) + 1;
  for (let i = 0; i < map.length; i += 337) probe.push(map[i]);   // 337 — взаимно простое с 56²
  const out = { counts: {}, probe: probe.join('') };
  for (const k of Object.keys(counts).sort((a, b) => a - b)) out.counts[k] = counts[k];
  return out;
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
  // Карта материалов и самоподобие: путь, который переезжает за facade (issue #72, шаг 2).
  // similarity(m, m) обязана давать ровно 1 — модель похожа на себя; если переезд что-то
  // сдвинет, это первое, что перестанет быть единицей.
  inv.map = mapSignature(m, 0.5);
  inv.selfSimilarity = r4(similarity(m, m, [0.5]));
  return inv;
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
      let bad = 0;
      for (let i = 0; i < Math.max(a.map.probe.length, b.map.probe.length); i++)
        if (a.map.probe[i] !== b.map.probe[i]) bad++;
      out.push(`карта среза: ${bad} проб из ${a.map.probe.length} не совпали`);
    }
  } else if (!!a.map !== !!b.map) out.push('карта среза есть только у одной стороны');
  const n = Math.max(a.probes.length, b.probes.length);
  let bad = 0;
  for (let i = 0; i < n; i++) if (a.probes[i] !== b.probes[i]) bad++;
  if (bad) out.push(`пробы среза: ${bad} из ${n} не совпали (первая: ${a.probes.find((p, i) => p !== b.probes[i])} ≠ ${b.probes.find((p, i) => p !== a.probes[i])})`);
  return out;
}
