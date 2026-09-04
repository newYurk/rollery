// validateRecipe. Честный отказ, без silent fallback.
// Коды: erratum-004, 008, 012, 016, 018.

import { placementWindowMm } from './units.js';

function diagnostic(code, message, context) {
  return { code, message, context };
}

function patchFootprint(patch) {
  const half = patch.widthMm / 2;
  return [patch.uMm - half, patch.uMm + half];
}

export function validateRecipe(recipe) {
  const diagnostics = [];

  if (!recipe || recipe.version !== 2) {
    diagnostics.push(diagnostic('section_shape', 'RecipeV2.version must be 2', {
      requestedFeature: recipe && recipe.version != null ? String(recipe.version) : 'missing',
    }));
    return { status: 'unsupported', diagnostics };
  }

  if (recipe.windDirection !== 'fromUZero' && recipe.windDirection !== 'fromULength') {
    diagnostics.push(diagnostic('recipe_missing_wind_direction', 'windDirection required', {
      observedValue: recipe.windDirection == null ? null : String(recipe.windDirection),
    }));
    return { status: 'invalid', diagnostics };
  }

  const hand = recipe.hand;
  if (!hand || hand.mode !== 'neutral' || hand.seed !== 0) {
    diagnostics.push(diagnostic('non_neutral_hand', 'V2 alpha accepts only NeutralHand', {
      observedHandMode: hand == null ? 'missing' : String(hand.mode),
    }));
    return { status: 'invalid', diagnostics };
  }

  if (!Array.isArray(recipe.patches)) {
    diagnostics.push(diagnostic('section_shape', 'patches must be an array', {
      requestedFeature: 'patches',
    }));
    return { status: 'unsupported', diagnostics };
  }

  const sheet = recipe.sheet;
  const L = sheet && sheet.lengthMm;
  const window = placementWindowMm(sheet);

  for (const patch of recipe.patches) {
    if (patch.rotationDeg != null && patch.rotationDeg !== 0) {
      diagnostics.push(diagnostic('patch_rotated', 'rotationDeg is not in Patch', {
        patchId: String(patch.id),
        observedRotationDeg: Number(patch.rotationDeg),
      }));
      return { status: 'invalid', diagnostics };
    }
    const [u0, u1] = patchFootprint(patch);
    if (u0 < 0 || u1 > L) {
      diagnostics.push(diagnostic('patch_out_of_sheet', 'patch footprint leaves the sheet', {
        patchId: String(patch.id),
        sheetLengthMm: L,
        observedFootprintMm: [u0, u1],
      }));
      return { status: 'invalid', diagnostics };
    }
    if (u0 < window.nearEdgeMm || u1 > window.farEdgeMm) {
      diagnostics.push(diagnostic('closure_window', 'patch footprint outside placementWindowMm', {
        patchId: String(patch.id),
        placementWindowMm: { nearEdgeMm: window.nearEdgeMm, farEdgeMm: window.farEdgeMm },
        observedFootprintMm: [u0, u1],
      }));
      return { status: 'outsideModelScope', diagnostics };
    }
  }

  return { status: 'valid', diagnostics: [], placementWindowMm: window };
}
