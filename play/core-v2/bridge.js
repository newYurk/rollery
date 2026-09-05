// Classic-play bridge. ESM → window.CoreV2. Does not import geometry.js.
//
// Мост отдаёт классической игре снимок V2 и принимает от неё раскладку игрока.
// Данные ходят только в одну сторону через adapter.js: игра кладёт простые числа,
// забирает снимок. Ядро про игру по-прежнему не знает.
//
// hash.js сюда импортировать нельзя — он тянет node:crypto и в браузере не грузится.
// Ключ кеша поэтому канонический, а не хеш; для сравнения этого достаточно.

import { adapt, adaptScenario } from './adapter.js';
import { recipeFromLayout } from './from-layout.js';
import { canonicalize } from './canonical.js';
import { drawSlice } from './render.js';
import { U_MM } from './units.js';

function refusedSnap(verdict) {
  return Object.freeze({
    ok: false,
    status: verdict.status,
    diagnostics: verdict.diagnostics,
    recipe: null,
    winding: null,
    section: null,
  });
}

const CoreV2 = {
  ready: true,
  U_MM,
  scenario: 'F02',
  _cache: null,
  _cacheKey: null,
  _layout: null,

  /**
   * Раскладка игрока вместо фикстуры. Возвращает вердикт целиком, чтобы игра
   * могла показать честный отказ с кодом, а не пустой экран.
   */
  setLayout(input) {
    const verdict = recipeFromLayout(input);
    this._layout = verdict;
    return verdict;
  },

  /** Вернуться к заготовленным фикстурам (?v2=empty и прочие). */
  clearLayout() {
    this._layout = null;
  },

  get snap() {
    // Ключ обязан зависеть от РЕЦЕПТА, а не от имени сценария: иначе игрок
    // двигает начинку, ключ прежний, и картинка молча не меняется.
    const key = this._layout
      ? (this._layout.status === 'valid'
        ? 'L' + canonicalize(this._layout.recipe)
        : 'X' + this._layout.status + ':' + this._layout.diagnostics[0].code)
      : 'S' + this.scenario;
    if (this._cacheKey !== key) {
      this._cache = this._layout
        ? (this._layout.status === 'valid' ? adapt(this._layout.recipe) : refusedSnap(this._layout))
        : adaptScenario(this.scenario);
      this._cacheKey = key;
    }
    return this._cache;
  },

  faceCanvas(px) {
    const s = this.snap;
    if (!s.ok) return null;
    const cv = document.createElement('canvas');
    cv.width = cv.height = px;
    drawSlice(cv.getContext('2d'), s.recipe, s.winding, px);
    return cv;
  },
};

window.CoreV2 = CoreV2;
if (typeof dirty !== 'undefined') dirty = true;
if (typeof requestFrame === 'function') requestFrame();
