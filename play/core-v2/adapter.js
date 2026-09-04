// Snapshot adapter. The only object a renderer may read from V2.
// ADR-001 migration §4: debug route / flag → snapshot, not geometry.js.

import { makeF01Recipe, makeF02Recipe, makeHosogiriRecipe } from './recipe.js';
import { validateRecipe } from './validate.js';
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
