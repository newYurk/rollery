'use strict';
// Настоящие ING и BASES из play/model/catalog.js — для тестов переводчика.
//
// Ядро каталог не импортирует и не будет. Но ПРОВЕРЯТЬ переводчик на выдуманных
// данных бессмысленно: разойдётся с каталогом — никто не заметит. Поэтому тест
// берёт живой catalog.js, а не его пересказ.
//
// Классические скрипты работают в глобальной области, поэтому поднимаем их в vm
// с минимальной заглушкой браузера — тем же приёмом, что load-legacy.cjs.

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.resolve(__dirname, '../..');
const FILES = ['model/util.js', 'model/catalog.js'];

function load() {
  const ctx = {
    console, Math, JSON, Map, Set, Array, Object, Number, String, Boolean, Date,
    isFinite, isNaN, parseFloat, parseInt, structuredClone,
    Int32Array, Float32Array, Float64Array,
  };
  ctx.window = ctx;
  ctx.globalThis = ctx;
  ctx.self = ctx;
  vm.createContext(ctx);
  const text = FILES
    .map((f) => '\n//== ' + f + ' ==\n' + fs.readFileSync(path.join(ROOT, 'play', f), 'utf8'))
    .join('\n')
    // Верхнеуровневые const в скрипте — лексические привязки, они НЕ становятся
    // свойствами globalThis. Забрать их можно только изнутри того же скрипта.
    + '\n//== выдача ==\nglobalThis.__CATALOG__ = { ING, BASES, U_MM };\n';
  vm.runInContext(text, ctx, { filename: 'catalog.js' });
  return ctx.__CATALOG__;
}

module.exports = { load };
