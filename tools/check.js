#!/usr/bin/env node
'use strict';
// СТОРОЖ ?check ИЗ ТЕРМИНАЛА (issue #147).
//
// Тот же самый play/checks.js, что открывается в браузере по ?check, — просто запущенный без
// страницы. Никаких отдельных «unit-тестов домена»: одни и те же эталоны, одни и те же мерки,
// один и тот же runChecks().
//
// ⚠ НО НЕ ОДИН И ТОТ ЖЕ НАБОР ПРОВЕРОК: раздел раскладки здесь НЕ ИДЁТ, см. ниже.
//
// ЗАЧЕМ. До 01.09 каждая правка модели проверялась походом в браузер: открыть, дождаться,
// прочитать глазами. За один вечер это поймало три регрессии (урамаки, F02, хосомаки) — и
// столько же раз я забывала сходить. Сторож, который надо помнить открыть, работает вполсилы.
//
// ЧТО ЭТО НЕ ЗАМЕНЯЕТ, И ЭТО ИЗМЕРЕНО. Ширину подписи здесь считает заглушка (7 px на символ),
// а не настоящий `ctx.measureText`: ширина чипов уезжает, за ней панель, рамка листа и ось
// узора. Числа про пиксели, цели касания и переносы отсюда НЕДОСТОВЕРНЫ — за ними в браузер.
//
// ⚠ ДО 03.09 ЭТО ПРЕДУПРЕЖДЕНИЕ БЫЛО ПАССИВНЫМ, И ЭТОГО НЕ ХВАТИЛО (#167). Оно честно
// говорило «не читай отсюда про пиксели», но раздел раскладки всё равно ПРОГОНЯЛСЯ, и его
// записи ложились в общий список «известно» вперемешку с настоящими, без пометки. Терминальный
// прогон печатал 70 против 65 браузерных и показывал пять баз «повёрнут» на 1180×820, где
// браузер не показывает ни одной. Читатель вывода предупреждения из этой шапки не видит.
// Теперь раздел просто не идёт, а в «СДВИГ ⌀» встаёт строка о том, что раскладка не проверена:
// известно 32 здесь против 65 в браузере, и разница объяснена в самом выводе, а не в шапке.
// Прежняя редакция этого абзаца называла числа 22 и 26 — они устарели вчетверо и молча.
//
// Что здесь верно полностью: вся модель, все эталоны REF, слепок, практика, фасад, пазл,
// жест. То есть ровно то, ради чего сторож и открывают после правки геометрии.
//
// УСТРОЙСТВО. Модель — classic scripts с общим скоупом (const из state.js виден в geometry.js),
// поэтому файлы склеиваются в один текст и выполняются одним куском: отдельные runInContext
// дают отдельные скоупы. Тот же приём, что в tools/measure-slice.js, — и список файлов берётся
// ИЗ САМОГО index.html, чтобы порядок не расходился. Добавили скрипт в игру — он приедет сюда
// сам, а не будет забыт.

const fs = require('fs'), vm = require('vm'), path = require('path');
const ROOT = path.resolve(__dirname, '..'), PLAY = path.join(ROOT, 'play');
const JSON_OUT = process.argv.includes('--json');
const ТИХО = process.argv.includes('--quiet');

// ── что грузить: порядок берём из index.html, а не переписываем ──────────────
const html = fs.readFileSync(path.join(PLAY, 'index.html'), 'utf8');
// 1) обычные <script src="...">, 2) отложенный список проверок в конце файла
const внешние = [...html.matchAll(/<script src="([^"?]+)/g)].map(m => m[1]);
const проверки = [...html.matchAll(/'((?:test|inverse)\/[\w./-]+\.js|checks\.js)'/g)].map(m => m[1]);
// 3) встроенный блок — в нём живут SHEET_U0, wrapInNoriList и прочее, без него игра неполна
const встроенные = [...html.matchAll(/<script>\n([\s\S]*?)<\/script>/g)].map(m => m[1])
  .filter(t => t.length > 2000);   // отсекаем маленькие блоки-загрузчики

// ── браузерные заглушки ──────────────────────────────────────────────────────
// Их ровно столько, сколько нужно, чтобы код ДОШЁЛ до проверок. Всё, что рисует, — пустышки:
// проверки меряют модель, а не пиксели. Три подпорки сверх measure-slice.js: Path2D (его зовёт
// отрисовка формы), btoa (сериализация ссылки-пазла), ctx.measureText (раскладка меряет подписи).
const измеритель = (t) => ({ width: String(t).length * 7 });
const ctx2d = () => new Proxy({
  measureText: измеритель,
  createImageData: (w, h) => ({ data: new Uint8ClampedArray(Math.max(1, w * h * 4)), width: w, height: h }),
  getImageData: (x, y, w, h) => ({ data: new Uint8ClampedArray(Math.max(1, w * h * 4)), width: w, height: h }),
  createLinearGradient: () => ({ addColorStop() {} }),
  createRadialGradient: () => ({ addColorStop() {} }),
  createPattern: () => null,
}, { get: (t, k) => (k in t ? t[k] : () => {}), set: () => true });

const узел = (tag) => {
  const el = {
    tagName: tag, style: {}, dataset: {}, width: 800, height: 600,
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    children: [], addEventListener() {}, removeEventListener() {},
    appendChild(c) { el.children.push(c); return c; }, removeChild() {}, remove() {},
    setAttribute() {}, getAttribute: () => null, focus() {}, blur() {}, click() {},
    getContext: () => ctx2d(),
    toDataURL: () => 'data:image/png;base64,',
    getBoundingClientRect: () => ({ width: 800, height: 600, left: 0, top: 0, right: 800, bottom: 600 }),
  };
  return el;
};

const ctx = {
  console, Math, JSON, Map, Set, WeakMap, Array, Object, Number, String, Boolean, Date, RegExp,
  Error, TypeError, Promise, Symbol, isFinite, isNaN, parseFloat, parseInt, structuredClone,
  Float32Array, Float64Array, Uint8Array, Uint8ClampedArray, Int32Array, Uint32Array, Proxy, Reflect,
  encodeURIComponent, decodeURIComponent, escape, unescape,
  btoa: (s) => Buffer.from(s, 'binary').toString('base64'),
  atob: (s) => Buffer.from(s, 'base64').toString('binary'),
  Path2D: class { constructor() {} addPath() {} moveTo() {} lineTo() {} closePath() {} arc() {} rect() {} },
};
ctx.window = ctx; ctx.globalThis = ctx; ctx.self = ctx;
ctx.document = {
  createElement: узел, createElementNS: (_, t) => узел(t),
  getElementById: () => узел('canvas'), querySelector: () => узел('canvas'),
  querySelectorAll: () => [], addEventListener() {}, removeEventListener() {},
  body: узел('body'), documentElement: узел('html'), fonts: { ready: Promise.resolve() },
};
ctx.localStorage = { _: {}, getItem(k) { return this._[k] ?? null; }, setItem(k, v) { this._[k] = String(v); }, removeItem(k) { delete this._[k]; } };
ctx.requestAnimationFrame = () => 0; ctx.cancelAnimationFrame = () => {};
ctx.addEventListener = () => {}; ctx.removeEventListener = () => {};
ctx.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
// ⚠ ?check В АДРЕСЕ ОБЯЗАТЕЛЕН: часть кода игры смотрит на location.search и в обычном режиме
// прячет полный набор баз и начинок (минимальный стенд, #96). Без него проверки меряют не то.
ctx.location = { search: '?check&full', href: 'http://localhost/play/index.html?check&full', hash: '', pathname: '/play/index.html' };
// state.js:65 разбирает ?v2 через URLSearchParams (PR #172). В песочнице vm его нет,
// и сторож падал на загрузке — молча, для всех headless-инструментов сразу.
ctx.URLSearchParams = URLSearchParams;
ctx.navigator = { userAgent: 'node', maxTouchPoints: 0 };
ctx.performance = { now: () => Number(process.hrtime.bigint() / 1000n) / 1000 };
ctx.setTimeout = (f) => { if (typeof f === 'function') f(); return 0; };
ctx.clearTimeout = () => {}; ctx.setInterval = () => 0; ctx.clearInterval = () => {};
ctx.devicePixelRatio = 2; ctx.innerWidth = 390; ctx.innerHeight = 844;
// Флаг для checks.js: раздел раскладки здесь пропускается, потому что measureText ниже —
// выдумка (#167). Не «оптимизация», а отказ мерить величину, которой у нас нет.
ctx.БЕЗ_БРАУЗЕРА = true;
// Звук: проверки его не слушают, но код инициализации ходит по графу узлов и по их полям
// (`o.frequency.exponentialRampToValueAtTime`). Поэтому прокси РЕКУРСИВНЫЙ: любое свойство
// отдаёт такой же прокси, любой вызов — тоже. Это единственный способ не гадать, какие ветки
// звукового кода дойдут до проверок сегодня и какие появятся завтра.
const пустышка = () => new Proxy(function () {}, {
  get: (_, k) => {
    if (k === 'value' || k === 'length' || k === 'sampleRate' || k === 'numberOfChannels') return 0;
    if (k === 'type' || k === 'state') return 'sine';
    if (k === Symbol.toPrimitive || k === 'valueOf') return () => 0;
    if (k === 'then') return undefined;                 // чтобы прокси не сочли Promise
    return пустышка();
  },
  set: () => true,
  apply: () => пустышка(),
  construct: () => пустышка(),
});
ctx.AudioContext = ctx.webkitAudioContext = class {
  constructor() { this.destination = пустышка(); this.sampleRate = 48000; this.currentTime = 0; this.state = 'running'; }
  createBuffer(ch, len, rate) {
    return { length: len, sampleRate: rate, numberOfChannels: ch, getChannelData: () => new Float32Array(Math.max(1, len)) };
  }
  resume() { return Promise.resolve(); }
  close() { return Promise.resolve(); }
  decodeAudioData() { return Promise.resolve(this.createBuffer(1, 1024, 48000)); }
};
for (const m of ['createGain', 'createOscillator', 'createBufferSource', 'createBiquadFilter',
                 'createDynamicsCompressor', 'createStereoPanner', 'createConvolver', 'createDelay',
                 'createWaveShaper', 'createChannelMerger', 'createChannelSplitter', 'createAnalyser',
                 'createPanner', 'createPeriodicWave'])
  ctx.AudioContext.prototype[m] = пустышка;

vm.createContext(ctx);

// ── склейка и прогон ─────────────────────────────────────────────────────────
const части = [];
for (const f of внешние) части.push(`//== play/${f}\n` + fs.readFileSync(path.join(PLAY, f), 'utf8'));
for (const t of встроенные) части.push('//== index.html inline\n' + t);
for (const f of проверки) части.push(`//== play/${f}\n` + fs.readFileSync(path.join(PLAY, f), 'utf8'));

const t0 = Date.now();
try {
  vm.runInContext(части.join('\n;\n'), ctx, { filename: 'rollery-bundle.js' });
} catch (e) {
  console.error('НЕ ЗАГРУЗИЛОСЬ:', e && e.message);
  console.error(e && e.stack ? String(e.stack).split('\n').slice(0, 4).join('\n') : '');
  process.exit(2);
}

// --eval <файл>: выполнить свой код в загруженной игре ВМЕСТЕ С ПРОВЕРКАМИ и слепком, вместо
// прогона сторожа. У tools/measure-slice.js такой ключ есть давно, но он грузит только модель;
// здесь доступны ещё practice, fixtures, baseline и фасадные проверки. Нужно, например, чтобы
// переснять слепок (captureLegacyBaseline) без браузера. Ответ класть в globalThis.ВЫХОД.
const _e = process.argv.indexOf('--eval');
if (_e >= 0) {
  const код = fs.readFileSync(process.argv[_e + 1], 'utf8');
  try { vm.runInContext(код, ctx, { filename: 'eval.js' }); }
  catch (e) { console.error('НЕ ВЫПОЛНИЛОСЬ:', e && e.message); process.exit(2); }
  const out = ctx.ВЫХОД;
  console.log(typeof out === 'string' ? out : JSON.stringify(out));
  process.exit(0);
}

let r;
try { r = ctx.runChecks(true); }
catch (e) { console.error('ПРОВЕРКИ УПАЛИ:', e && e.message); process.exit(2); }

const сек = ((Date.now() - t0) / 1000).toFixed(1);
if (JSON_OUT) {
  console.log(JSON.stringify({ ok: r.ok, fails: r.fails, known: r.known, notes: r.notes, sec: +сек }, null, 2));
} else if (ТИХО) {
  console.log(r.ok ? `ВСЁ ЦЕЛО · известно ${r.known.length} · ${сек} с` : `ПРОВАЛ · ${r.fails.length}`);
  if (!r.ok) for (const f of r.fails) console.log('  ✗ ' + f);
} else {
  console.log(r.text);
  console.log(`\n(прогон ${сек} с, без браузера — tools/check.js. Настоящий холст, DPR и размеры окна` +
              `\n проверяет только play/index.html?check: это второй уровень, а не замена.)`);
}
process.exit(r.ok ? 0 : 1);
