#!/usr/bin/env node
// Замер среза БЕЗ БРАУЗЕРА: грузит модель игры в node и печатает числа,
// которые сравниваются с промышленными спецификациями (docs/kitchen-practice.md,
// раздел «Количественно»).
//
// ЗАЧЕМ: до 01.09.2026 любое число модели можно было увидеть только глазами в
// браузере — открыть ?check, посмотреть. Это значит, что расхождение с реальностью
// замечалось, только если кто-то смотрел. Здесь то же меряется командой, поэтому
// годится и для сторожа, и для сравнения двух правок между собой.
//
// ЧТО МЕРЯЕТ (всё в срезе v = 0,5, рука неподвижна, канонический футомаки):
//   ⌀ ролла в мм         — против 太巻 45 мм / 極太巻 50 мм (三 производителя)
//   доля начинки         — против 23–29 % (выведено из таблицы «размер ↔ вес шари»)
//   радиусы начинок      — против «начинка в центре, до 0,48…0,74 R»
//   профиль по кольцам   — видно, диск это или кольцо
//
//   node tools/measure-slice.js            канонический футомаки
//   node tools/measure-slice.js --json     то же машиночитаемо
//
// Модель — classic scripts с общим скоупом: в браузере `const` из state.js виден
// в geometry.js. В node так работает ТОЛЬКО если склеить файлы в один текст и
// выполнить одним куском; отдельные runInContext дают отдельные скоупы, и модель
// разваливается на «S is not defined». Отсюда склейка ниже.

const fs = require('fs'), vm = require('vm'), path = require('path');
const ROOT = path.resolve(__dirname, '..');
const JSON_OUT = process.argv.includes('--json');
// --eval <файл>: выполнить свой замер в той же модели вместо стандартного. Нужен инструментам,
// которым нужна загруженная игра, но другой вопрос к ней (tools/variants.js) — чтобы загрузчик
// жил в одном месте, а не копировался. Скрипт кладёт ответ в globalThis.ВЫХОД.
const _e = process.argv.indexOf('--eval');
const EVAL = _e >= 0 ? process.argv[_e + 1] : null;

// ── браузерные заглушки: модели нужен только document, рисование не вызывается ──
const узел = () => ({
  getContext: () => ({ save(){}, restore(){}, clearRect(){}, fillRect(){}, beginPath(){},
    arc(){}, fill(){}, stroke(){}, moveTo(){}, lineTo(){}, closePath(){}, translate(){},
    rotate(){}, scale(){}, createImageData: () => ({ data: [] }), putImageData(){},
    drawImage(){}, setTransform(){} }),
  style: {}, dataset: {}, width: 800, height: 600,
  classList: { add(){}, remove(){}, toggle(){}, contains: () => false },
  addEventListener(){}, appendChild(){}, setAttribute(){}, remove(){},
  getBoundingClientRect: () => ({ width: 800, height: 600, left: 0, top: 0 }),
});
const ctx = { console, Math, JSON, Map, Set, Array, Object, Number, String, Boolean, Date,
  isFinite, isNaN, parseFloat, parseInt, structuredClone };
ctx.window = ctx; ctx.globalThis = ctx; ctx.self = ctx;
ctx.document = { createElement: узел, createElementNS: узел, getElementById: узел,
  querySelector: узел, querySelectorAll: () => [], addEventListener(){},
  body: узел(), documentElement: узел() };
ctx.localStorage = { getItem: () => null, setItem(){}, removeItem(){} };
ctx.requestAnimationFrame = () => 0; ctx.addEventListener = () => {};
ctx.matchMedia = () => ({ matches: false, addEventListener(){} });
ctx.location = { search: '', href: '', hash: '' };
// Тот же URLSearchParams из state.js:65 — без него мерка не снимает числа (PR #172).
ctx.URLSearchParams = URLSearchParams;
ctx.navigator = { userAgent: 'node' }; ctx.performance = { now: () => 0 };
ctx.setTimeout = () => 0; ctx.clearTimeout = () => {};
vm.createContext(ctx);

// Порядок обязателен и повторяет play/index.html — модель на него опирается.
// render/slice.js нужен ради touchModel — он живёт там, а не в модели. Порядок тот же,
// что в play/index.html: менять нельзя, скрипты классические и делят один скоуп.
const ФАЙЛЫ = ['model/util.js', 'model/catalog.js', 'state.js', 'model/geometry.js',
               'model/canon.js', 'domain/roll.js', 'render/slice.js', 'ui/layout.js'];

const ЗАМЕР = `
  S.base = 'futo'; S.wrap = null; S.turns = null; S.shape = 'kamaboko';   // форма канона — как у сторожа (#19)
  S.hand = handOf();
  // Тот же набор, что у сторожа practice.js (наКаноне): пять начинок по правилу четверти.
  // Позиции по правилу четверти (手前板前): набор занимает 0,31 ширины постели. Прежние
  // 0,34…0,66 давали 0,50 — вдвое шире источника, и «канон» канону не следовал.
  S.lists.futo = canonLayout();   // одно определение — play/model/canon.js (#129)
  if (typeof touchModel === 'function') touchModel();
  if (typeof layout === 'function') layout();
  const мод = getModel(), ветер = windFor(мод, 0.5), Р = мод.Rmax;
  const N = 400, КОЛЕЦ = 20;
  const счёт = {}, вКольце = new Array(КОЛЕЦ).fill(0), всегоВКольце = new Array(КОЛЕЦ).fill(0);
  let точек = 0, начинок = 0, суммаР = 0, минР = 9, максР = 0;
  for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
    const x = (i + 0.5) / N * 2 - 1, y = (j + 0.5) / N * 2 - 1, rr = Math.hypot(x, y);
    if (rr > 1) continue;
    const b = Math.min(КОЛЕЦ - 1, Math.floor(rr * КОЛЕЦ));
    const q = materialAt(мод, ветер, 0.5, rr * Р, Math.atan2(y, x));
    const к = q ? (q.cls || '?') : 'null'; счёт[к] = (счёт[к] || 0) + 1;
    // ⚑ ЗНАМЕНАТЕЛЬ — САМ РОЛЛ, А НЕ ОПИСАННЫЙ КРУГ (01.09, #19). Та же правка, что в
    // play/test/practice.js: у формы с плоскими гранями в круг радиуса Rmax входит воздух, и
    // доля начинки «падала» на четыре пункта, хотя ни один кусок не сдвинулся. Тут и там
    // одна величина — считать её надо одинаково.
    if (к === 'out') continue;
    точек++; всегоВКольце[b]++;
    if (к === 'patch') { начинок++; суммаР += rr; вКольце[b]++;
      if (rr < минР) минР = rr; if (rr > максР) максР = rr; }
  }
  globalThis.ВЫХОД = {
    диаметрМм: 2 * Р * U_MM,
    нориМм: BASES.futo.sheetCm * 10,
    некруглость: (() => { const N2 = 720, rs = [];
      for (let i = 0; i < N2; i++) rs.push(topAt(ветер, i / N2 * TAU));
      rs.sort((a, b) => a - b); return (rs[N2 - 1] - rs[0]) / rs[N2 >> 1]; })(),
    доли: Object.fromEntries(Object.keys(счёт).map(к => [к, счёт[к] / точек])),
    доляНачинки: начинок / точек,
    начинкаОт: минР, начинкаДо: максР,
    начинкаСредний: начинок ? суммаР / начинок : null,
    начинкаЭквРадиус: Math.sqrt(начинок / точек),
    поКольцам: вКольце.map((n, b) => всегоВКольце[b] ? n / всегоВКольце[b] : 0),
  };
`;

let текст = ФАЙЛЫ.map(f => '\n//══ ' + f + ' ══\n' + fs.readFileSync(path.join(ROOT, 'play', f), 'utf8')).join('\n');
текст += '\n//══ замер ══\n' + (EVAL ? fs.readFileSync(EVAL, 'utf8') : ЗАМЕР);
try { vm.runInContext(текст, ctx, { filename: 'модель.js' }); }
catch (e) { console.error('модель не собралась: ' + e.message); process.exit(2); }
const r = ctx.ВЫХОД;

if (EVAL) { console.log(JSON.stringify(r)); process.exit(0); }
if (JSON_OUT) { console.log(JSON.stringify(r, null, 2)); process.exit(0); }

// ⟦ЧИСЛА ИСТОЧНИКОВ⟧ — коридоры из docs/kitchen-practice.md, раздел «Количественно».
// Менять здесь нельзя: если число расходится с доком, расходится не инструмент, а док.
const ИСТОЧНИК = {
  нориМм:      [200, 210, 'AUTEC ASM890: 太巻き（Ｌ）45mm角 при нори 200～210mm'],
  доляНачинки: [0.23, 0.29, 'выведено из «размер ↔ вес шари» TSM; сходится с правилом четверти'],
  эквРадиус:   [0.48, 0.54, '√доли, будь начинка диском в центре; замер по кадру дал медиану 0,48'],
  некруглость: [0.15, 0.38, 'замер по кадру 42VeWXl2S9E: 0,195 и 0,270; круг 0,004, квадрат 0,383'],
};
// ⚠ ГАБАРИТ СЕЧЕНИЯ ЗДЕСЬ НЕ СРАВНИВАЕТСЯ, и это не упущение. Промышленные 45 мм — это
// 「45mm角」, сторона квадрата; наш ⌀ — диаметр круга. Один рабочий периметр 180 мм даёт либо
// квадрат 45,0 мм, либо круг ⌀57,3 мм: это один и тот же ролл. Сравнивать габариты можно
// только после того, как совпадёт форма, поэтому мерится длина нори (от формы не зависит),
// а форма — отдельно, некруглостью.

const стрелка = (v, [lo, hi]) => v < lo ? '↓ ниже' : v > hi ? '↑ выше' : '✓ в коридоре';
const пц = v => (100 * v).toFixed(1) + ' %';

console.log('\n══ СРЕЗ КАНОНИЧЕСКОГО ФУТОМАКИ ══');
console.log('  нори по обхвату ' + r.нориМм.toFixed(0) + ' мм    ' +
            стрелка(r.нориМм, ИСТОЧНИК.нориМм) + ' [' + ИСТОЧНИК.нориМм.slice(0,2).join('–') + ' мм]');
console.log('  ⌀ ролла         ' + r.диаметрМм.toFixed(1) + ' мм    (круг того же листа; ' +
            'квадратом это сторона ' + (Math.PI * r.диаметрМм / 4).toFixed(1) + ' мм)');
console.log('  некруглость     ' + r.некруглость.toFixed(3) + '      ' +
            стрелка(r.некруглость, ИСТОЧНИК.некруглость) + ' [' + ИСТОЧНИК.некруглость.slice(0,2).join('–') + ']');
console.log('\n  материал среза:');
for (const к of Object.keys(r.доли).sort((a, b) => r.доли[b] - r.доли[a]))
  console.log('    ' + к.padEnd(8) + пц(r.доли[к]).padStart(7));
const рис = (r.доли.spread || 0) + (r.доли.core || 0);
console.log('    ' + '— рис'.padEnd(8) + пц(рис).padStart(7) + '   [71–77 % по источнику]');
console.log('\n  начинка         ' + пц(r.доляНачинки) + '   ' +
            стрелка(r.доляНачинки, ИСТОЧНИК.доляНачинки) + ' [' +
            ИСТОЧНИК.доляНачинки.slice(0,2).map(пц).join('–') + ']');
console.log('  √доли           ' + r.начинкаЭквРадиус.toFixed(3) + ' R   ' +
            стрелка(r.начинкаЭквРадиус, ИСТОЧНИК.эквРадиус) + ' [' + ИСТОЧНИК.эквРадиус.slice(0,2).join('–') + ' R]');
console.log('  лежит в кольце  ' + r.начинкаОт.toFixed(2) + ' … ' + r.начинкаДо.toFixed(2) +
            ' R   (средний ' + r.начинкаСредний.toFixed(2) + ')');
console.log('\n  доля начинки по кольцам — диск или кольцо:');
r.поКольцам.forEach((f, b) => console.log('    ' + (b * 0.05).toFixed(2) + '  ' +
  '█'.repeat(Math.round(f * 36)).padEnd(37) + (100 * f).toFixed(0) + ' %'));

// Главный вывод — не число, а форма: источник хочет ДИСК в центре, а не кольцо.
const пустоВЦентре = r.поКольцам.slice(0, 8).every(f => f < 0.02);
console.log('\n  ' + (пустоВЦентре
  ? '⚠ центр среза (0…0,40 R) БЕЗ НАЧИНКИ — источник кладёт её именно туда (issue #98)'
  : '✓ начинка есть в центре среза'));
console.log('');
