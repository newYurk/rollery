'use strict';
// УТИЛИТЫ: математика без состояния — интерполяции, сглаживания, цвет, хеш.
//
// Вынесено из play/index.html 29.08.2026 дословно. Здесь нет ни модели, ни отрисовки, ни
// состояния: чистые функции, от которых зависит всё остальное. Поэтому файл подключается
// ПЕРВЫМ — до каталога и до модели.
//
// hash() детерминирован намеренно: текстура риса и «почерк» руки не имеют права зависеть от
// Math.random, иначе одна раскладка перестанет давать один и тот же срез.

const TAU = Math.PI * 2;
const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const remap = (t, a, b) => clamp((t - a) / (b - a));
const fract = x => x - Math.floor(x);
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const easeOutCubic = x => 1 - Math.pow(1 - x, 3);
const easeInOutCubic = x => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
const easeOutBack = x => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2); };
const hexRgb = h => { const n = parseInt(h.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
const rgbCss = (c, a = 1) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`;
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const shade = (c, k) => [c[0] * k, c[1] * k, c[2] * k];
function hash(x, y) {
  let h = (Math.imul(x | 0, 374761393) + Math.imul(y | 0, 668265263)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}

