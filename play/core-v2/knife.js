// Нож. Число кусков — свойство базы (#116), не игры.
// Первый рез — середина. Тянущий 引き切り: вес лезвия, без нажима.
// Не импортирует play/model/**.

import { baseOf } from './units.js';

export function pieceCountOf(recipe) {
  return baseOf(recipe).pieces;
}

export function pieceLengthMm(recipe) {
  return recipe.sheet.widthMm / pieceCountOf(recipe);
}

/** Внутренние плоскости реза: 1/n … (n−1)/n. Концы не режутся. */
export function cutFractions(n) {
  const out = [];
  for (let i = 1; i < n; i++) out.push(i / n);
  return out;
}

export function snapCutFraction(v, n) {
  const cuts = cutFractions(n);
  let best = cuts[0];
  let d = Infinity;
  for (const c of cuts) {
    const ad = Math.abs(c - v);
    if (ad < d) { d = ad; best = c; }
  }
  return best;
}

/** Первый рез повара — пополам. Для 6 и 8 это ровно 1/2. */
export function firstCutFraction(n) {
  return snapCutFraction(0.5, n);
}

export function vSliceMm(recipe, vFrac) {
  return vFrac * recipe.sheet.widthMm;
}

/** Кусок слева от плоскости (1-based). Рез 3/6 лежит между 3 и 4. */
export function pieceLeftOfCut(vFrac, n) {
  return Math.round(vFrac * n);
}
