// Snapshot adapter. The only object a renderer may read from V2.
// ADR-001 migration §4: debug route / flag → snapshot, not geometry.js.

import { makeF01Recipe, makeF02Recipe, makeHosogiriRecipe } from './recipe.js';
import { validateRecipe, assessWinding } from './validate.js';
import { buildWinding } from './winding.js';
import { sampleSection } from './section.js';

export const SCENARIOS = Object.freeze({
  F01: makeF01Recipe,
  empty: makeF01Recipe,
  F02: makeF02Recipe,
  kappa: makeF02Recipe,
  hosogiri: makeHosogiriRecipe,
});

export function adapt(recipe, vSliceMm) {
  const verdict = validateRecipe(recipe);
  if (verdict.status !== 'valid') {
    return Object.freeze({
      ok: false,
      status: verdict.status,
      diagnostics: verdict.diagnostics,
      recipe,
      winding: null,
      section: null,
    });
  }
  const winding = buildWinding(recipe);
  // ⚑ ФИЗИЧЕСКАЯ ПРИЁМКА ЗДЕСЬ ЖЕ, А НЕ ТОЛЬКО В ПЕСОЧНИЦЕ (#209, пункт 3).
  //
  // `adapt` — путь, по которому раскладка игрока под `?v2` попадает в ядро. Он проверял
  // рецепт и строил намотку, а `assessWinding` не звал; звали её только `app.js` (песочница
  // ядра), `fixtures.js` и тесты. Следствие: отказы `sheet_too_short`, `wraps_beyond_two`,
  // `chef_corridor` и `core_overflow` в ИГРЕ не срабатывали, хотя в песочнице срабатывали, —
  // то есть игра на том же ядре была защищена слабее, чем его же демонстрация.
  //
  // Порядок повторяет `runFixture` дословно: рецепт → намотка → физика → срез. Иначе два
  // пути к одному ядру расходились бы уже последовательностью проверок, а не только набором.
  const phys = assessWinding(recipe, winding);
  if (phys.status !== 'valid') {
    return Object.freeze({
      ok: false,
      status: phys.status,
      diagnostics: phys.diagnostics,
      recipe,
      winding,
      section: null,
    });
  }
  const v = vSliceMm ?? recipe.sheet.widthMm / 2;
  const section = sampleSection(recipe, winding, v);
  return Object.freeze({
    ok: true,
    status: 'valid',
    diagnostics: [],
    recipe,
    winding,
    section,
  });
}

export function adaptScenario(id, vSliceMm) {
  const make = SCENARIOS[id];
  if (!make) throw new Error('unknown scenario: ' + id);
  return adapt(make(), vSliceMm);
}
