// Classic-play bridge. ESM → window.CoreV2. Does not import geometry.js.

import { adaptScenario } from './adapter.js';
import { drawSlice } from './render.js';
import { U_MM } from './units.js';

const CoreV2 = {
  ready: true,
  U_MM,
  scenario: 'F02',
  _cache: null,
  _cacheId: null,
  get snap() {
    if (!this._cache || this._cacheId !== this.scenario) {
      this._cache = adaptScenario(this.scenario);
      this._cacheId = this.scenario;
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
