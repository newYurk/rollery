'use strict';
// Раскладка игрока → RecipeV2. Единственное место, где ядро V2 встречается
// с S, ING, BASES и HAND_NEUTRAL.
//
// Ядро их НЕ импортирует и не увидит: чистая часть перевода лежит в
// play/core-v2/from-layout.js и получает каталог аргументом. Здесь только сбор
// данных — то есть ровно та работа, которую классическая сторона обязана делать сама.

/** Всё, что ядру нужно знать о текущем состоянии игры. Простые данные, без функций. */
function v2LayoutInput() {
  return {
    baseKey: S.base,
    base: BASES[S.base],
    patches: S.lists[S.base] || [],
    ing: ING,
    wrap: S.wrap,
    hand: S.hand,
    handNeutral: HAND_NEUTRAL,
    shape: S.shape,
    turns: S.turns,
  };
}

/**
 * Снимок V2 для текущего состояния.
 * null — мост ещё не загрузился: bridge.js это модуль, он выполняется позже
 * классических скриптов, и первый кадр может успеть раньше.
 *
 * S.v2Scenario === 'layout' (голый ?v2) — считаем раскладку игрока.
 * Остальные значения — заготовленные фикстуры, они раскладку игнорируют.
 */
function v2Snap() {
  if (!window.CoreV2) return null;
  if (S.v2Scenario && S.v2Scenario !== 'layout') {
    CoreV2.clearLayout();
    CoreV2.scenario = S.v2Scenario;
  } else {
    CoreV2.setLayout(v2LayoutInput());
  }
  return CoreV2.snap;
}

/** Первая диагностика отказа — её показывает экран вместо картинки. */
function v2Refusal(snap) {
  if (!snap || snap.ok) return null;
  const d = snap.diagnostics && snap.diagnostics[0];
  if (!d) return { code: snap.status, text: snap.status };
  const c = d.context || {};
  const text =
    d.code === 'closure_window' ? 'След начинки вне окна раскладки — идеальный ролл не рисуем.'
    : d.code === 'patch_out_of_sheet' ? 'След начинки уходит за край листа.'
    : d.code === 'patch_material_overlap' ? 'Два куска одного вещества налезают друг на друга.'
    : d.code === 'patch_cut_unsupported' ? `Срез V2 пока не считает нарезку «${c.observedCut}» (${c.patchKind}).`
    : d.code === 'patch_is_paint' ? 'Краска риса — не начинка ядра.'
    : d.code === 'patch_axial_profile' ? `У «${c.patchKind}» профиль вдоль оси, а срез V2 один, центральный.`
    : d.code === 'base_unsupported' ? 'V2 пока считает только хосомаки и футомаки.'
    : d.code === 'shape_unsupported' ? 'V2 прессует только круглый ролл.'
    : d.code === 'wrap_unsupported' ? 'V2 заворачивает только в нори.'
    : d.code === 'sheet_too_short' ? 'Ядро выросло — листа не хватает на оборот.'
    : d.code === 'chef_corridor' ? 'Диаметр вышел за коридор повара 28–32 мм.'
    : d.code === 'core_overflow' ? 'Начинка не помещается в ядро.'
    : d.code === 'non_neutral_hand' ? 'V2 считает только нейтральную руку.'
    : (d.message || d.code);
  return { code: d.code, text, context: c };
}
