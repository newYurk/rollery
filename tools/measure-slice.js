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
ctx.navigator = { userAgent: 'node' }; ctx.performance = { now: () => 0 };
ctx.setTimeout = () => 0; ctx.clearTimeout = () => {};
vm.createContext(ctx);

// Порядок обязателен и повторяет play/index.html — модель на него опирается.
const ФАЙЛЫ = ['model/util.js', 'model/catalog.js', 'state.js', 'model/geometry.js',
               'model/canon.js', 'domain/roll.js', 'ui/layout.js'];

const ЗАМЕР = `
  const P = (kind, u, phase) => ({ kind, u, v: 0.5, z0: 0, z1: 0, phase });
  S.base = 'futo'; S.wrap = null; S.turns = null; S.shape = 'round';
  S.hand = { air: 0, wobble: 0, phase: 0, press: 1, v: 1, cv: 0, hold: 0 };
  // Тот же набор, что у сторожа practice.js (наКаноне): пять начинок по правилу четверти.
  S.lists.futo = [P('denbu', 0.34, 0.7), P('tamago', 0.42, 1.9), P('kanpyo', 0.50, 3.1),
                  P('shiitake', 0.58, 4.4), P('cucumber', 0.66, 5.6)];
  if (typeof touchModel === 'function') touchModel();
  if (typeof layout === 'function') layout();
  const мод = getModel(), ветер = windFor(мод, 0.5), Р = мод.Rmax;
  const N = 400, КОЛЕЦ = 20;
  const счёт = {}, вКольце = new Array(КОЛЕЦ).fill(0), всегоВКольце = new Array(КОЛЕЦ).fill(0);
  let точек = 0, начинок = 0, суммаР = 0, минР = 9, максР = 0;
  for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) {
    const x = (i + 0.5) / N * 2 - 1, y = (j + 0.5) / N * 2 - 1, rr = Math.hypot(x, y);
    if (rr > 1) continue;
    точек++; const b = Math.min(КОЛЕЦ - 1, Math.floor(rr * КОЛЕЦ)); всегоВКольце[b]++;
    const q = materialAt(мод, ветер, 0.5, rr * Р, Math.atan2(y, x));
    const к = q ? (q.cls || '?') : 'null'; счёт[к] = (счёт[к] || 0) + 1;
    if (к === 'patch') { начинок++; суммаР += rr; вКольце[b]++;
      if (rr < минР) минР = rr; if (rr > максР) максР = rr; }
  }
  globalThis.ВЫХОД = {
    диаметрМм: 2 * Р * U_MM,
    длинаСм: мод.g.L * U_MM / 10,
    доли: Object.fromEntries(Object.keys(счёт).map(к => [к, счёт[к] / точек])),
    доляНачинки: начинок / точек,
    начинкаОт: минР, начинкаДо: максР,
    начинкаСредний: начинок ? суммаР / начинок : null,
    начинкаЭквРадиус: Math.sqrt(начинок / точек),
    поКольцам: вКольце.map((n, b) => всегоВКольце[b] ? n / всегоВКольце[b] : 0),
  };
`;

let текст = ФАЙЛЫ.map(f => '\n//══ ' + f + ' ══\n' + fs.readFileSync(path.join(ROOT, 'play', f), 'utf8')).join('\n');
текст += '\n//══ замер ══\n' + ЗАМЕР;
try { vm.runInContext(текст, ctx, { filename: 'модель.js' }); }
catch (e) { console.error('модель не собралась: ' + e.message); process.exit(2); }
const r = ctx.ВЫХОД;

if (JSON_OUT) { console.log(JSON.stringify(r, null, 2)); process.exit(0); }

// ⟦ЧИСЛА ИСТОЧНИКОВ⟧ — коридоры из docs/kitchen-practice.md, раздел «Количественно».
// Менять здесь нельзя: если число расходится с доком, расходится не инструмент, а док.
const ИСТОЧНИК = {
  диаметрМм:   [45, 50,  '太巻 45 · 極太巻 50 мм — TSM-900RSR, SUZUMO ZNS-FRA (φ/□46±2), AUTEC'],
  доляНачинки: [0.23, 0.29, 'выведено из «размер ↔ вес шари» TSM; сходится с правилом четверти'],
  эквРадиус:   [0.48, 0.54, '√доли, будь начинка диском в центре'],
};
const стрелка = (v, [lo, hi]) => v < lo ? '↓ ниже' : v > hi ? '↑ выше' : '✓ в коридоре';
const пц = v => (100 * v).toFixed(1) + ' %';

console.log('\n══ СРЕЗ КАНОНИЧЕСКОГО ФУТОМАКИ ══');
console.log('  ⌀ ролла         ' + r.диаметрМм.toFixed(1) + ' мм    ' +
            стрелка(r.диаметрМм, ИСТОЧНИК.диаметрМм) + ' [' + ИСТОЧНИК.диаметрМм.slice(0,2).join('–') + ' мм]');
console.log('  длина ролла     ' + r.длинаСм.toFixed(1) + ' см    [18–20 см у трёх производителей]');
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
