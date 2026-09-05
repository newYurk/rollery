// validateRecipe. Честный отказ, без silent fallback.
// Коды: erratum-004, 008, 012, 016, 018. sheet_too_short / chef_corridor — этот PR.

import {
  EPS_LENGTH_MM,
  HOSOMAKI_DIAMETER_MM,
  WINDING,
  baseOf,
  patchCorePos,
  placementWindowMm,
} from './units.js';

function diagnostic(code, message, context) {
  return { code, message, context };
}

function patchFootprint(patch) {
  const half = patch.widthMm / 2;
  return [patch.uMm - half, patch.uMm + half];
}

function finite(n) {
  return typeof n === 'number' && Number.isFinite(n);
}

export function validateRecipe(recipe) {
  const diagnostics = [];

  if (!recipe || recipe.version !== 2) {
    diagnostics.push(diagnostic('section_shape', 'RecipeV2.version must be 2', {
      requestedFeature: recipe && recipe.version != null ? String(recipe.version) : 'missing',
    }));
    return { status: 'unsupported', diagnostics };
  }

  const winding = recipe.winding;
  if (winding !== WINDING.ring && winding !== WINDING.spiral && winding !== WINDING.inverted) {
    diagnostics.push(diagnostic('section_shape', 'winding must be ring, spiral, or inverted', {
      requestedFeature: winding == null ? 'missing' : String(winding),
    }));
    return { status: 'unsupported', diagnostics };
  }
  if (winding !== WINDING.ring) {
    diagnostics.push(diagnostic('section_shape', 'V2 alpha winds only ring (maki)', {
      requestedFeature: winding,
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
  if (!sheet || !finite(sheet.lengthMm) || sheet.lengthMm <= 0) {
    diagnostics.push(diagnostic('section_shape', 'sheet.lengthMm must be a finite positive length', {
      requestedFeature: 'sheet',
    }));
    return { status: 'invalid', diagnostics };
  }
  const L = sheet.lengthMm;
  const window = placementWindowMm(sheet);

  for (const patch of recipe.patches) {
    if (patch == null || typeof patch !== 'object') {
      diagnostics.push(diagnostic('section_shape', 'patch must be an object', {
        requestedFeature: 'patches',
      }));
      return { status: 'invalid', diagnostics };
    }
    if (!finite(patch.uMm) || !finite(patch.widthMm) || patch.widthMm <= 0) {
      diagnostics.push(diagnostic('patch_out_of_sheet', 'patch uMm/widthMm must be finite, widthMm > 0', {
        patchId: patch.id == null ? null : String(patch.id),
        sheetLengthMm: L,
      }));
      return { status: 'invalid', diagnostics };
    }
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

  for (let i = 0; i < recipe.patches.length; i++) {
    for (let j = i + 1; j < recipe.patches.length; j++) {
      const a = recipe.patches[i];
      const b = recipe.patches[j];
      if (a.materialId !== b.materialId) continue;
      if ((a.placement ?? 'embedded') !== 'embedded') continue;
      if ((b.placement ?? 'embedded') !== 'embedded') continue;
      const [a0, a1] = patchFootprint(a);
      const [b0, b1] = patchFootprint(b);
      if (a0 < b1 && b0 < a1) {
        diagnostics.push(diagnostic('patch_material_overlap', 'same-material embedded footprints overlap', {
          patchIds: [String(a.id), String(b.id)],
          materialId: String(a.materialId),
        }));
        return { status: 'invalid', diagnostics };
      }
    }
  }

  return { status: 'valid', diagnostics: [], placementWindowMm: window };
}

/** Физика намотки после buildWinding. Не silent fallback. */
export function assessWinding(recipe, winding) {
  const L = recipe.sheet.lengthMm;
  if (winding.noriPerimeter > L + EPS_LENGTH_MM) {
    return {
      status: 'invalid',
      diagnostics: [diagnostic('sheet_too_short', 'nori ring longer than the sheet', {
        noriPerimeterMm: winding.noriPerimeter,
        sheetLengthMm: L,
      })],
    };
  }
  // Лист длиннее двух оборотов — это третий слой нори, а модель различает только
  // один и два. Кламп молча сломал бы сохранение длины, поэтому отказываем.
  if (winding.wrapsBeyondTwo) {
    return {
      status: 'outsideModelScope',
      diagnostics: [diagnostic('wraps_beyond_two', 'лист даёт больше двух слоёв нори', {
        noriPerimeterMm: winding.noriPerimeter,
        sheetLengthMm: L,
      })],
    };
  }
  if (baseOf(recipe).baseId === 'hosomaki') {
    const d = (winding.diameterMinMm + winding.diameterMaxMm) / 2;
    if (d < HOSOMAKI_DIAMETER_MM.min - 0.5 || d > HOSOMAKI_DIAMETER_MM.max + 0.5) {
      return {
        status: 'outsideModelScope',
        diagnostics: [diagnostic('chef_corridor', 'hosomaki diameter outside 28–32 mm', {
          diameterMm: d,
          corridorMm: HOSOMAKI_DIAMETER_MM,
        })],
      };
    }
  }
  for (const p of recipe.patches) {
    const pos = patchCorePos(recipe, p);
    const ox = Math.abs(pos.x) + p.widthMm / 2 - winding.Wc / 2;
    const oy = Math.abs(pos.y) + p.heightMm / 2 - winding.Hc / 2;
    if (ox > EPS_LENGTH_MM || oy > EPS_LENGTH_MM) {
      return {
        status: 'invalid',
        diagnostics: [diagnostic('core_overflow', 'filling AABB leaves the core box', {
          patchId: String(p.id),
          overflowMm: { x: ox, y: oy },
        })],
      };
    }
  }
  return { status: 'valid', diagnostics: [] };
}
