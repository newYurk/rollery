#!/usr/bin/env node
'use strict';
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const FILES = ['model/util.js', 'model/catalog.js', 'state.js', 'model/geometry.js'];
const узел = () => ({
  getContext: () => ({ save() {}, restore() {}, clearRect() {}, fillRect() {}, beginPath() {},
    arc() {}, fill() {}, stroke() {}, moveTo() {}, lineTo() {}, closePath() {}, translate() {},
    rotate() {}, scale() {}, createImageData: () => ({ data: [] }), putImageData() {},
    drawImage() {}, setTransform() {} }),
  style: {}, dataset: {}, width: 800, height: 600,
  classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
  addEventListener() {}, appendChild() {}, setAttribute() {}, remove() {},
  getBoundingClientRect: () => ({ width: 800, height: 600, left: 0, top: 0 }),
});
const ctx = { console, Math, JSON, Map, Set, Array, Object, Number, String, Boolean, Date,
  isFinite, isNaN, parseFloat, parseInt, structuredClone, Int32Array, Float32Array, Float64Array };
ctx.window = ctx; ctx.globalThis = ctx; ctx.self = ctx;
ctx.document = { createElement: узел, createElementNS: узел, getElementById: узел,
  querySelector: узел, querySelectorAll: () => [], addEventListener() {},
  body: узел(), documentElement: узел() };
ctx.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
ctx.requestAnimationFrame = () => 0; ctx.addEventListener = () => {};
ctx.matchMedia = () => ({ matches: false, addEventListener() {} });
ctx.location = { search: '', href: '', hash: '' };
// Третья песочница с тем же пробелом, что чинился в #176: state.js:65
// разбирает ?v2 через URLSearchParams, и без него сюда не грузится ничего.
ctx.URLSearchParams = URLSearchParams;
ctx.navigator = { userAgent: 'node' }; ctx.performance = { now: () => 0 };
ctx.setTimeout = () => 0; ctx.clearTimeout = () => {};
vm.createContext(ctx);

let text = FILES.map((f) => '\n//══ ' + f + ' ══\n' + fs.readFileSync(path.join(ROOT, 'play', f), 'utf8')).join('\n');
text += '\n//══ probe ══\n' + fs.readFileSync(path.join(__dirname, 'legacy-probe.js'), 'utf8');
vm.runInContext(text, ctx, { filename: 'legacy-probe.js' });
process.stdout.write(JSON.stringify(ctx.ВЫХОД));
