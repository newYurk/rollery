'use strict';
// Режим ?tube — пять авторских раскладок из tube-levels.js. 19.09.2026.
//
// Живёт РЯДОм с ?puzzle. LEVELS и genTarget не зовёт.
// Перехват действий ставит tubeInstall() из точки входа — после actions.js.
//
// Намотка в трубке — спираль, не кольцо. У хосомаки один огурец иначе уезжает в ядро
// (#98 / #152): положение на листе меняет только угол, срез один и тот же. Спираль
// везёт начинку вместе с листом — u читается радиусом, «сюда / туда» работает.

const TUBE_U_TOL = 0.08;

function tubeStart(level) {
  level = Math.max(0, Math.min(TUBE_LEVELS.length - 1, level | 0));
  const spec = TUBE_LEVELS[level];
  S.base = TUBE_BASE;
  S.winding = 'spiral';
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

function tubeStop() { S.winding = null; puzzleStop(); }
function tubeTitle(pz) { return (pz.level + 1) + ' / ' + TUBE_LEVELS.length; }
function tubeDone() { return S.puzzle && S.puzzle.tube && S.puzzle.level + 1 >= TUBE_LEVELS.length; }

function tubeUOff() {
  const pz = S.puzzle, pm = getModel();
  if (!pz || !pm) return true;
  for (const t of pz.target) {
    if (t.kind === 'nori') continue;
    const mine = pm.list.filter(p => p.kind === t.kind);
    if (!mine.length) return true;
    let bd = 9;
    for (const p of mine) bd = Math.min(bd, Math.abs(p.u - t.u));
    if (bd > TUBE_U_TOL) return true;
  }
  return false;
}

function tubeInstall() {
  const origAction = action;
  action = function (id) {
    if (id === 'tube') {
      if (S.puzzle && S.puzzle.tube) tubeStop();
      else { let st = {}; try { st = JSON.parse(localStorage.getItem('rollery.tube') || '{}'); } catch (e) {} tubeStart(st.level || 0); }
      requestFrame(); return;
    }
    if (S.puzzle && S.puzzle.tube) {
      if (id === 'next' && S.puzzle.result && S.puzzle.result.pass) {
        if (S.puzzle.level + 1 < TUBE_LEVELS.length) tubeStart(S.puzzle.level + 1); else tubeStop();
        requestFrame(); return;
      }
      if (id === 'lvprev') { if (S.puzzle.level > 0) tubeStart(S.puzzle.level - 1); requestFrame(); return; }
      if (id === 'lvnext') { if (S.puzzle.level + 1 < TUBE_LEVELS.length) tubeStart(S.puzzle.level + 1); requestFrame(); return; }
      if (id === 'newpuzzle') { tubeStart(S.puzzle.level); requestFrame(); return; }
      if (id === 'base') { requestFrame(); return; }
    }
    return origAction(id);
  };
  const origTitle = levelTitle;
  levelTitle = function (lv, i) {
    if (S.puzzle && S.puzzle.tube) return tubeTitle(S.puzzle);
    return origTitle(lv, i);
  };
  const origPal = uiPalette;
  uiPalette = function () {
    const p = origPal();
    const allow = S.puzzle && S.puzzle.tube && S.puzzle.palette;
    if (!allow) return p;
    const groups = [], flat = [];
    for (const g of p.groups) {
      const ings = g.ings.filter(k => allow.indexOf(k) >= 0);
      if (!ings.length) continue;
      groups.push(Object.assign({}, g, { ings: ings, icon: ings.indexOf(g.icon) >= 0 ? g.icon : ings[0] }));
      for (const k of ings) flat.push(k);
    }
    return { groups: groups, flat: flat, max: groups.reduce((m, g) => Math.max(m, g.ings.length), 0) };
  };
  const origEval = puzzleEvaluate;
  puzzleEvaluate = function () {
    if (!(S.puzzle && S.puzzle.tube)) return origEval();
    let keep = null;
    try { keep = localStorage.getItem('rollery.puzzle'); } catch (e) {}
    const r = origEval();
    try { if (keep !== null) localStorage.setItem('rollery.puzzle', keep); } catch (e) {}
    if (tubeUOff()) S.puzzle.result.pass = false;
    return S.puzzle.result;
  };
}
