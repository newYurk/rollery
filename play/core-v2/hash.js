// Canonicalize + digest. Erratum 011.
// Domain: recipe / winding / section — never FixtureReport.
//
// ⚑ ХЕШ КВАНТУЕТСЯ, КАНОНИЗАЦИЯ — НЕТ. Это разные задачи, и смешивать их нельзя:
//
//   canonicalize — ТОЧНОЕ представление. По нему ловят мутацию рецепта ядром
//                  (fixtures.js) и строят ключ кеша снимка (bridge.js). Там
//                  важно любое различие, вплоть до последнего бита.
//   hashValue    — ПЕРЕНОСИМЫЙ отпечаток. По нему сравнивают прогоны, в том
//                  числе на разных машинах, и последний бит там — шум.
//
// Почему шум. r0At считает границу ядра через Math.cos / Math.sin. IEEE-754
// требует бит-в-бит воспроизводимости от sqrt, но НЕ от тригонометрии: разные
// libm и разные сборки V8 расходятся в последнем ULP. Один такой бит менял
// SHA-256 целиком, и закоммиченные reports/*.json оказывались машинно-зависимыми:
// перегенерировал на другой платформе — получил ложный дифф (#175).

import { createHash } from 'node:crypto';
import { canonicalize } from './canonical.js';

export { canonicalize } from './canonical.js';

/**
 * Шаг сетки хеша, мм. 1e-6 — на пять порядков ниже EPS_LENGTH_MM (0,15) и
 * на девять порядков выше ULP величин порядка миллиметров (≈9e-16), поэтому
 * настоящее изменение по-прежнему меняет хеш, а шум платформы — нет.
 *
 * Остаточный риск: значение, попавшее ровно на границу округления, может
 * округлиться в разные стороны. При шаге 1e-6 это требует совпадения примерно
 * до девятого знака и на практике не встречается; при шаге 1e-9 риск был бы
 * в тысячу раз выше — поэтому мельче не берём.
 */
export const HASH_QUANTUM_MM = 1e-6;
const SCALE = 1 / HASH_QUANTUM_MM;

/**
 * Округление до сетки. Умножение и деление IEEE-754 округляет корректно и
 * одинаково на любой платформе, а Math.round над целым — точен, пока
 * |x · SCALE| < 2^53; наши длины миллиметровые, запас огромный.
 */
export function quantize(value) {
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return value; // пусть ругается canonicalize
    const q = Math.round(value * SCALE) / SCALE;
    return q === 0 ? 0 : q; // −0 и 0 обязаны хешироваться одинаково
  }
  if (value === null || typeof value !== 'object') return value;
  if (ArrayBuffer.isView(value)) return Array.from(value, quantize);
  if (Array.isArray(value)) return value.map(quantize);
  const out = {};
  for (const k of Object.keys(value)) out[k] = quantize(value[k]);
  return out;
}

export function digest(canonicalString) {
  return createHash('sha256').update(canonicalString, 'utf8').digest('hex');
}

export function hashValue(value) {
  return digest(canonicalize(quantize(value)));
}
