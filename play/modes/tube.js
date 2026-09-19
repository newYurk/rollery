'use strict';
// Режим ?tube — пять авторских раскладок из tube-levels.js. 19.09.2026.
//
// Живёт РЯДОМ с ?puzzle. LEVELS и genTarget не зовёт. Состояние то же S.puzzle,
// плюс флаги tube и palette: оценка, цель и рез — существующий код пазла.
// Прогресс пазла (rollery.puzzle) не трогает.

function tubeStart(level) {
  level = Math.max(0, Math.min(TUBE_LEVELS.length - 1, level | 0));
  const spec = TUBE_LEVELS[level];
  S.base = TUBE_BASE;
  palSync();
  const lv = { sheets: TUBE_SHEETS, pieces: spec.pieces, n: spec.palette.length, tube: true };
  S.turns = levelTurns(lv);
  S.selPatch = null;
  S.shape = 'round';
  const target = spec.target.map(p => Object.assign({}, p));
  S.puzzle = {
    level, seed: 0, lv,
    target, target0: target.map(p => Object.assign({}, p)),
    vs: puzzleSlices(spec.pieces),
    result: null,
    tube: true,
    palette: spec.palette.slice(),
  };
  S.sel = spec.palette[0];
  palSync();
  selOnRice();
  S.lists[S.base] = [];
  histReset();
  touchModel();
  layout();
  try { localStorage.setItem('rollery.tube', JSON.stringify({ level })); } catch (e) {}
  if (S.mode !== 'lay') action('back');
  dirty = true;
  requestFrame();
}

function tubeStop() {
  puzzleStop();
}

function tubeTitle(pz) {
  return (pz.level + 1) + ' / ' + TUBE_LEVELS.length;
}

function tubeDone() {
  return S.puzzle && S.puzzle.tube && S.puzzle.level + 1 >= TUBE_LEVELS.length;
}
