'use strict';
// РЕЖИМ «ПАЗЛ»: повтори показанный срез.
//
// Единственный игровой режим поверх модели. Цель — не картинка, а РАСКЛАДКА (S.puzzle.target):
// поэтому подсказку можно получить вычитанием координат, а цель — пересобрать рукой игрока,
// чтобы рука не влияла на оценку (docs/noise-floor.md, issue #8).
//
// ⚠ Пазл живёт по СВОЕЙ физике листа: длина выводится из числа витков уровня, а не из
// физического листа. Это несведённое противоречие двух решений — issue #83.
//
// По решению владельца 29.08 режимы отложены: milestone «Оболочка и режимы».

// ---------------------------------------------------------------- пазл: повтори срез
// Уровень: n — начинок, turns — витков (длина листа), pieces — сколько кусочков показано, wrap — обёрнутых нори,
// local — коротких начинок (видны не во всех кусочках), sheet — разрешён длинный ингредиент (лист омлета / крем-роза).
const LEVELS = [
  { n: 1, turns: 3, pieces: 1 },
  { n: 2, turns: 3, pieces: 1 },
  { n: 3, turns: 3, pieces: 1 },
  { n: 2, turns: 3, pieces: 1, wrap: 1 },
  { n: 3, turns: 2, pieces: 1, shape: 'square' },
  { n: 3, turns: 3, pieces: 3, local: 1 },
  { n: 4, turns: 4, pieces: 1, shape: 'triangle' },
  { n: 3, turns: 3, pieces: 6, local: 2 },
  { n: 3, turns: 3, pieces: 6, rot: 1 },
  { n: 3, turns: 3, pieces: 3, local: 1, wrap: 1 },
  { n: 4, turns: 4, pieces: 6, local: 2, wrap: 1 },
  { n: 4, turns: 2, pieces: 3, local: 1, wrap: 1, sheet: 1, shape: 'square' },
  { n: 3, turns: 3, pieces: 1, paint: 1, shape: 'triangle' },
  { n: 4, turns: 3, pieces: 1, paint: 2, wrap: 1 },
  { n: 4, turns: 3, pieces: 6, rot: 2, paint: 1 },
  { n: 5, turns: 4, pieces: 6, local: 2, wrap: 2, sheet: 1, paint: 1 },
];
const PASS = 0.72;   // порог «совпало» по похожести
function mulberry32(a) { return function () { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const puzzleSlices = k => { const vs = []; for (let i = 0; i < k; i++) vs.push((i + 0.5) / k); return vs; };
// Цель — случайная достижимая раскладка из палитры базы: те же виды, те же размеры, что у игрока.
function genTarget(lv, seed) {
  const rnd = mulberry32(seed), b = B(), L = sheetLen(b);
  const isLong = k => ING[k].wU >= 6, isLocal = k => ING[k].dv < 1;
  const base = b.ingredients.filter(k => k !== 'nori' && !ING[k].wave && !isLong(k) && !ING[k].paint);
  const paints = b.ingredients.filter(k => ING[k].paint);
  const full = base.filter(k => !isLocal(k)), local = base.filter(isLocal);
  const kinds = [];
  for (let i = 0; i < (lv.local || 0) && local.length; i++) kinds.push(local[Math.floor(rnd() * local.length)]);
  if (lv.sheet && rnd() < 0.7) kinds.push(b.ingredients.find(isLong));
  for (let i = 0; i < (lv.paint || 0) && paints.length; i++) kinds.push(paints[Math.floor(rnd() * paints.length)]);
  while (kinds.length < lv.n) kinds.push(full[Math.floor(rnd() * full.length)]);
  const items = kinds.map(kind => ({ kind, half: ING[kind].wU / L / 2 + 0.012 }));
  const uMax = 0.92;   // суши: только то, что точно намотается до замыкания (ядро + первый оборот)
  let us = null;
  for (let tries = 0; tries < 80 && !us; tries++) {
    const cand = items.map(it => it.half + rnd() * (uMax - 2 * it.half));
    const order = cand.map((u, i) => i).sort((a, c) => cand[a] - cand[c]); let ok = true;
    for (let j = 1; j < order.length; j++) { const a = order[j - 1], c = order[j]; if (cand[c] - cand[a] < items[a].half + items[c].half) { ok = false; break; } }
    if (ok) us = cand;
  }
  if (!us) { let u = 0.03; us = items.map(it => { const x = u + it.half; u += 2 * it.half + 0.02; return x; }); }
  const list = items.map((it, i) => { const d = ING[it.kind]; const p = { kind: it.kind, u: clamp(us[i], it.half, 1 - it.half), v: 0.5, z0: 0, z1: 0, phase: rnd() * TAU }; if (d.dv < 1) p.v = d.dv / 2 + rnd() * (1 - d.dv); return p; });
  if (lv.rot) for (let r = 0, n0 = 0; r < list.length && n0 < lv.rot; r++) { const p = list[r]; if (ING[p.kind].wave || isLong(p.kind)) continue; p.rot = rnd() < 0.5 ? Math.PI / 4 : Math.PI / 2; p.dv = 0.22; p.v = 0.25 + rnd() * 0.5; n0++; }
  for (let w = 0; w < (lv.wrap || 0); w++) {
    const cands = list.filter(p => p.kind !== 'nori' && !isLong(p.kind) && !p.wrapped); if (!cands.length) break;
    const F = cands[Math.floor(rnd() * cands.length)]; F.wrapped = true; wrapInNoriList(F, list, rnd);
  }
  for (const p of list) delete p.wrapped;
  return list;
}
function puzzleStart(level, seed) {
  level = clamp(level, 0, LEVELS.length - 1); const lv = LEVELS[level];
  S.turns = lv.turns; S.selPatch = null; S.shape = lv.shape || 'round';
  S.puzzle = { level, seed, lv, target: null, vs: puzzleSlices(lv.pieces), result: null };
  S.puzzle.target = genTarget(lv, seed * 7919 + level * 131 + (S.base === 'cake' ? 17 : 0));
  // СРЕЗЫ ОБЯЗАНЫ ПРОХОДИТЬ ЧЕРЕЗ КАЖДУЮ НАЧИНКУ. Иначе часть цели невидима, и её можно
  // класть куда угодно: замерено на уровне 5 — клубника занимала v 0,331…0,456, а резы
  // стояли на 0,167 / 0,5 / 0,833, и сдвиг её на 10 мм давал ЧЕСТНЫЕ 100 %. Лосось и огурец
  // на тех же 10 мм давали 51 % и 59 % — то есть метрика исправна, просто не туда смотрела.
  // Локальные по оси начинки (dv < 1) — клубника, креветка — прячутся между резами.
  for (const t of S.puzzle.target) {
    const d = ING[t.kind]; if (!d || d.dv >= 1) continue;
    const half = d.dv / 2, lo = t.v - half, hi = t.v + half;
    if (S.puzzle.vs.some(v => v >= lo && v <= hi)) continue;
    // ни один рез не задевает — двигаем ближайший внутрь начинки, а не добавляем новый:
    // число кусочков задано уровнем и менять его нельзя.
    let bi = 0, bd = 9;
    for (let i = 0; i < S.puzzle.vs.length; i++) { const dd = Math.abs(S.puzzle.vs[i] - t.v); if (dd < bd) { bd = dd; bi = i; } }
    S.puzzle.vs[bi] = clamp(t.v, 0.03, 0.97);
  }
  S.lists[S.base] = []; touchModel(); layout();
  try { localStorage.setItem('rollery.puzzle', JSON.stringify({ level, seed, max: Math.max(level, puzzleMax()) })); } catch (e) {}
  if (S.mode !== 'lay') action('back'); dirty = true; requestFrame();
}
function puzzleMax() { try { return (JSON.parse(localStorage.getItem('rollery.puzzle') || '{}').max) || 0; } catch (e) { return 0; } }
function puzzleStop() { S.puzzle = null; S.turns = null; touchModel(); layout(); if (S.mode !== 'lay') action('back'); dirty = true; requestFrame(); }
function targetModel() { return buildModel(S.puzzle.target); }
function puzzleEvaluate() {
  const pz = S.puzzle, tm = targetModel(), pm = getModel();
  const sim = similarity(tm, pm, pz.vs);
  const hints = [];
  const L = pm.g.L;
  for (const t of pz.target) {
    if (t.kind === 'nori') continue;
    const mine = pm.list.filter(p => p.kind === t.kind);
    if (!mine.length) { hints.push(`нет: ${ING[t.kind].name.toLowerCase()}`); continue; }
    let best = mine[0], bd = 9; for (const p of mine) { const dd = Math.abs(p.u - t.u); if (dd < bd) { bd = dd; best = p; } }
    if (bd > 0.04) hints.push(`${ING[t.kind].name.toLowerCase()}: ${best.u < t.u ? 'дальше от края' : 'ближе к краю'} на ${Math.round(bd * L * 5)} мм`);
    else if (Math.abs((best.rot || 0) - (t.rot || 0)) > 0.1) hints.push(`${ING[t.kind].name.toLowerCase()}: другой поворот`);
    else if (ING[t.kind].dv < 1 && Math.abs(best.v - t.v) > 0.12) hints.push(`${ING[t.kind].name.toLowerCase()}: не в тех кусочках`);
  }
  for (const p of pm.list) if (p.kind !== 'nori' && !pz.target.some(t => t.kind === p.kind)) hints.push(`лишнее: ${ING[p.kind].name.toLowerCase()}`);
  const tw = pz.target.filter(p => p.kind === 'nori').length, mw = pm.list.filter(p => p.kind === 'nori').length;
  if (tw && !mw) hints.push('в цели есть нори-обёртка'); else if (!tw && mw) hints.push('в цели нет нори');
  pz.result = { sim, pass: sim >= PASS, hints: hints.slice(0, 3) };
  if (pz.result.pass) { try { const st = JSON.parse(localStorage.getItem('rollery.puzzle') || '{}'); st.max = Math.max(st.max || 0, pz.level + 1); localStorage.setItem('rollery.puzzle', JSON.stringify(st)); } catch (e) {} }
  return pz.result;
}
// Ссылка на пазл: раскладка (цель) в хэше адреса; друг видит только срез.
function encodePuzzle(list, turns) {
  const h = S.hand || {}; const data = { b: S.base, t: turns || null, s: S.shape, h: (h.air || h.wobble || (h.press !== 1)) ? [+h.air.toFixed(3), +h.wobble.toFixed(3), +h.phase.toFixed(2), +h.press.toFixed(2)] : null, l: list.map(p => [p.kind, +p.u.toFixed(4), +p.v.toFixed(3), p.wU ?? null, p.hU ?? null, p.dv ?? null, +p.phase.toFixed(3), p.rot ? +p.rot.toFixed(4) : null]) };
  return location.origin + location.pathname + '#p=' + btoa(unescape(encodeURIComponent(JSON.stringify(data)))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function decodePuzzle(hash) {
  try {
    const mm = /#p=([A-Za-z0-9_-]+)/.exec(hash); if (!mm) return null;
    const json = decodeURIComponent(escape(atob(mm[1].replace(/-/g, '+').replace(/_/g, '/'))));
    const data = JSON.parse(json); if (!data.l || !BASES[data.b]) return null;
    const list = data.l.map(a => { const p = { kind: a[0], u: a[1], v: a[2], z0: 0, z1: 0, phase: a[6] || 0 }; if (a[3] != null) p.wU = a[3]; if (a[4] != null) p.hU = a[4]; if (a[5] != null) p.dv = a[5]; if (a[7]) p.rot = a[7]; return p; }).filter(p => ING[p.kind]);
    const hh = Array.isArray(data.h) ? { air: data.h[0], wobble: data.h[1], phase: data.h[2], press: data.h[3], v: 1, cv: 0, hold: 0 } : null;
    return { base: data.b, turns: data.t, shape: SHAPES[data.s] ? data.s : 'round', hand: hh, list };
  } catch (e) { return null; }
}
function puzzleFromLink(pz) {
  S.base = pz.base; S.sel = B().ingredients[0]; S.turns = pz.turns || null; S.selPatch = null; S.shape = pz.shape || 'round';
  if (pz.hand) S.hand = pz.hand;
  const local = pz.list.some(p => (p.dv ?? ING[p.kind].dv) < 1), n = pz.list.filter(p => p.kind !== 'nori').length;
  const lv = { n, turns: S.turns || B().turns, pieces: local ? 3 : 1, custom: true };
  S.puzzle = { level: -1, seed: 0, lv, target: pz.list, vs: puzzleSlices(lv.pieces), result: null };
  S.lists[S.base] = []; touchModel(); layout(); if (S.mode !== 'lay') action('back'); dirty = true; requestFrame();
}
let shareNote = 0;
function sharePuzzle() {
  const list = S.puzzle ? S.puzzle.target : patches(); if (!list.length) return;
  const url = encodePuzzle(list, S.turns);
  const done = () => { shareNote = performance.now() + 2200; dirty = true; requestFrame(); };
  if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, () => { location.hash = url.slice(url.indexOf('#')); done(); });
  else { location.hash = url.slice(url.indexOf('#')); done(); }
}
function levelTitle(lv, i) {
  if (lv.custom) return `Пазл по ссылке · ${lv.n} нач. · ${lv.pieces > 1 ? lv.pieces + ' кус.' : '1 срез'}`;
  const parts = [`Уровень ${i + 1}`, `${lv.n} нач.`, `${lv.turns} вит.`, lv.pieces > 1 ? `${lv.pieces} кус.` : '1 срез'];
  if (lv.wrap) parts.push('нори'); if (lv.local) parts.push('короткие'); if (lv.paint) parts.push('цв. рис'); if (lv.rot) parts.push('поворот'); if (lv.shape && lv.shape !== 'round') parts.push(SHAPES[lv.shape].glyph);
  return parts.join(' · ');
}
function action(id) {
  switch (id) {
    case 'undo': if (S.mode === 'lay' && patches().length) { patches().pop(); S.selPatch = null; touchModel(); } break;
    case 'clear': if (S.mode === 'lay') { S.lists[S.base] = []; S.selPatch = null; touchModel(); } break;
    case 'wrap': if (S.mode === 'lay' && S.selPatch) wrapInNori(S.selPatch); break;
    case 'rotate': if (S.mode === 'lay' && S.selPatch) { const p = S.selPatch; p.rot = ((p.rot || 0) + Math.PI / 4) % Math.PI; if (p.rot < 1e-6) delete p.rot; const bb = bounds(p), hu = (bb.u1 - bb.u0) / 2, hv = (bb.v1 - bb.v0) / 2; p.u = clamp(p.u, Math.min(0.5, hu), Math.max(0.5, 1 - hu)); p.v = clamp(p.v, Math.min(0.5, hv), Math.max(0.5, 1 - hv)); touchModel(); sfx.place(); } break;
    case 'remove': if (S.mode === 'lay' && S.selPatch) { const l = patches(), i = l.indexOf(S.selPatch); if (i >= 0) l.splice(i, 1); S.selPatch = null; touchModel(); } break;
    case 'deselect': S.selPatch = null; dirty = true; break;
    case 'back': S.mode = 'lay'; S.rollP = 0; S.bigPiece = -1; S.albumOpen = -1; cut = null; slicing = null; if (S.puzzle) S.puzzle.result = null; dirty = true; break;
    case 'new': S.lists[S.base] = []; touchModel(); action('back'); break;
    case 'slice': if (S.mode === 'revealed') startSlicing(); break;
    case 'preview': S.preview = !S.preview; save(); layout(); dirty = true; break;
    case 'puzzle': if (S.puzzle) puzzleStop(); else { let st = {}; try { st = JSON.parse(localStorage.getItem('rollery.puzzle') || '{}'); } catch (e) {} puzzleStart(st.level || 0, st.seed || 1); } break;
    case 'newpuzzle': if (S.puzzle) puzzleStart(Math.max(0, S.puzzle.level), S.puzzle.seed + 1); break;
    case 'share': sharePuzzle(); break;
    case 'albumsave': albumSave(); break;
    case 'album': if (S.mode === 'album') { S.mode = 'lay'; S.albumOpen = -1; } else { S.albumOpen = -1; S.albumScroll = 0; S.mode = 'album'; } dirty = true; break;
    case 'albumclear': if (S.album.length) { S.album = []; try { localStorage.setItem('rollery.album', '[]'); } catch (e) {} dirty = true; } break;
    case 'albumopen_load': albumLoad(S.albumOpen); break;
    case 'albumopen_share': albumShare(S.albumOpen); break;
    case 'albumopen_del': albumRemove(S.albumOpen); break;
    case 'albumopen_close': S.albumOpen = -1; dirty = true; break;
    // ⚠ Имя 'wrap' уже занято: так называется «обернуть НАЧИНКУ в нори». Первый совпавший
    // case выигрывает, поэтому моя ветка была недостижима и кнопка молча ничего не делала.
    case 'sheet': {
      const ks = Object.keys(WRAPPERS), cur = B().wrapKey || 'nori';
      S.wrap = ks[(ks.indexOf(cur) + 1) % ks.length];
      wrapNote = WRAPPERS[S.wrap].name + ' · ' + WRAPPERS[S.wrap].mm + ' мм';
      wrapNoteT = performance.now();
      save(); touchModel(); layout(); dirty = true; break;
    }
    case 'shape': { const ks = Object.keys(SHAPES); S.shape = ks[(ks.indexOf(S.shape) + 1) % ks.length]; save(); if (S.puzzle && S.puzzle.result) S.puzzle.result = null; dirty = true; break; }
    case 'next': if (S.puzzle && S.puzzle.result && S.puzzle.result.pass) puzzleStart(Math.max(0, S.puzzle.level + 1), S.puzzle.seed + 1); break;
    case 'lvprev': if (S.puzzle && S.puzzle.level > 0) puzzleStart(S.puzzle.level - 1, S.puzzle.seed); else if (S.puzzle && S.puzzle.level < 0) puzzleStart(0, 1); break;
    case 'lvnext': if (S.puzzle && S.puzzle.level + 1 < LEVELS.length && S.puzzle.level + 1 <= puzzleMax()) puzzleStart(S.puzzle.level + 1, S.puzzle.seed); break;
    case 'mute': S.mute = !S.mute; sfx.ensure(); sfx.setMute(S.mute); save(); dirty = true; break;
    case 'base': { const keys = Object.keys(BASES); S.base = keys[(keys.indexOf(S.base) + 1) % keys.length]; S.sel = B().ingredients[0]; S.selPatch = null; touchModel(); layout(); if (S.puzzle) puzzleStart(S.puzzle.level, S.puzzle.seed); else if (S.mode !== 'lay') action('back'); break; }
  }
  requestFrame();
}
function chipsRect() { const c = L.chips; return { x: c.x - 4, y: c.y - 4, w: c.w + 8, h: c.rows * (c.size + (c.labels ? 18 : 6)) + 8 }; }
function onDown(x, y, id) {
  sfx.ensure();
  for (const ic of icons) if (inRect(x, y, ic)) { action(ic.id); return; }
  for (const b of buttons) if (inRect(x, y, b)) { action(b.id); return; }
  if (S.mode === 'lay') {
    if (anim) return;
    if (inRect(x, y, chipsRect())) {
      if (L.chipScroll) { drag.id = id; drag.kind = 'chips'; drag.x0 = x; drag.s0 = chipScrollX; drag.moved = false; return; }
      for (const c of chips) if (inRect(x, y, c)) { S.sel = c.kind; dirty = true; requestFrame(); return; }
      return;
    }
    const s = L.sheet;
    if (inRect(x, y, L.handle) || (S.rollP > 0 && inRect(x, y, s))) { drag.id = id; drag.kind = 'roll'; drag.y0 = y; drag.p0 = S.rollP; drag.lastY = y; drag.lastT = performance.now(); drag.samples = []; drag.moveT = drag.lastT; drag.sampT = drag.lastT; sfx.rustleStart(); return; }
    if (inRect(x, y, s)) {
      const p = hitPatch(x, y);
      drag.id = id; drag.x0 = x; drag.y0 = y; drag.moved = false;
      if (p) { drag.kind = 'move'; drag.patch = p; const uv = sheetUV(x, y); drag.ou = p.u - uv.u; drag.ov = p.v - uv.v; }
      else drag.kind = 'place';
      dirty = true; requestFrame();
    }
    return;
  }
  if (S.mode === 'rolled') {
    const { R, len } = rollDims();
    if (Math.abs(y - L.roll.y) < R + 30 && Math.abs(x - L.roll.x) < len / 2 + 20) {
      const v = clamp((x - (L.roll.x - len / 2)) / len);
      const snapped = clamp(Math.round(v * NPIECES), 1, NPIECES - 1) / NPIECES;
      startCut(snapped); requestFrame();
    }
    return;
  }
  if (S.mode === 'album') {
    if (S.albumOpen >= 0) { S.albumOpen = -1; dirty = true; requestFrame(); return; }   // тап по фону закрывает
    for (const c of albumCells) if (inRect(x, y, c)) { S.albumOpen = c.i; dirty = true; requestFrame(); return; }
    drag.id = id; drag.kind = 'albumscroll'; drag.y0 = y; drag.s0 = S.albumScroll; drag.moved = false;
    return;
  }
  if (S.mode === 'plate') {
    if (S.bigPiece >= 0) { S.bigPiece = -1; dirty = true; requestFrame(); return; }
    for (let i = 0; i < NPIECES; i++) { const g = L.grid[i]; if (Math.hypot(x - g.x, y - g.y) < g.size / 2) { S.bigPiece = i; dirty = true; requestFrame(); return; } }
  }
}
function onMove(x, y, id) {
  if (drag.id !== id || !drag.kind) return;
  if (drag.kind === 'chips') {
    drag.moved = drag.moved || Math.abs(x - drag.x0) > 6;
    chipScrollX = drag.s0 - (x - drag.x0);
  } else if (drag.kind === 'albumscroll') {
    drag.moved = drag.moved || Math.abs(y - drag.y0) > 6;
    S.albumScroll = drag.s0 - (y - drag.y0);
  } else if (drag.kind === 'roll') {
    const now = performance.now();
    S.rollP = clamp(drag.p0 + (drag.y0 - y) / (L.sheet.h * 0.85));
    const speed = Math.abs(y - drag.lastY) / Math.max(1, now - drag.lastT); drag.lastY = y; drag.lastT = now;
    if (drag.samples && now - drag.sampT >= 8) { drag.samples.push(speed); drag.sampT = now; if (drag.samples.length > 240) drag.samples.shift(); }
    if (speed > 0.05) drag.moveT = now;
    sfx.rustle(speed * 1.5);
  } else if (drag.kind === 'move') {
    const uv = sheetUV(x, y), bb = bounds(drag.patch), hu = (bb.u1 - bb.u0) / 2, hv = (bb.v1 - bb.v0) / 2;
    drag.moved = drag.moved || Math.hypot(x - drag.x0, y - drag.y0) > 6;
    if (!drag.moved) return;
    drag.patch.u = clamp(uv.u + drag.ou, Math.min(0.5, hu), Math.max(0.5, 1 - hu));
    drag.patch.v = clamp(uv.v + drag.ov, Math.min(0.5, hv), Math.max(0.5, 1 - hv));
    drag.outside = !inRect(x, y, { x: L.sheet.x - 24, y: L.sheet.y - 24, w: L.sheet.w + 48, h: L.sheet.h + 48 });
  } else if (drag.kind === 'place') {
    drag.moved = drag.moved || Math.hypot(x - drag.x0, y - drag.y0) > 10;
  }
  dirty = true; requestFrame();
}
// Почерк из жеста: средняя скорость тяги, её неровность и удержание в конце.
// Всё считается из того, что сделала рука, — никакого Math.random, поэтому «стиль», а не лотерея.
function measureHand() {
  const sm = drag.samples; if (!sm || sm.length < 5) return;
  const use = sm.filter(v => v > 0.02).sort((a, b) => a - b); if (use.length < 5) return;
  const q = f => use[clamp(Math.round(f * (use.length - 1)), 0, use.length - 1)];
  const med = q(0.5), spread = (q(0.75) - q(0.25)) / Math.max(med, 1e-3);   // медиана и межквартильный разброс — устойчивы к выбросам
  const vRef = L.sheet.h / 600;                                   // спокойная тяга — примерно за 600 мс
  const v = clamp(med / vRef, 0.3, 3), cv = clamp(spread, 0, 1.5);
  const hold = clamp((performance.now() - drag.moveT) / 900, 0, 1);
  const phase = (sm.reduce((a, b, i) => a + b * (i + 1), 0) % TAU + TAU) % TAU;
  S.hand = { air: clamp(0.16 * (v - 1), 0, 0.22), wobble: clamp(0.09 * cv, 0, 0.11), phase,
             press: clamp(0.85 + 0.45 * hold, 0.85, 1.3), v: +v.toFixed(2), cv: +cv.toFixed(2), hold: +hold.toFixed(2) };
  touchModel();
}
function handLabelOf(h) { const k = S.hand; S.hand = h; const t = handLabel(); S.hand = k; return t; }
function handLabel() {
  const h = S.hand; if (!h || (h.air === 0 && h.wobble === 0 && h.press === 1)) return '';
  const parts = [h.v > 1.35 ? 'быстрая тяга' : h.v < 0.75 ? 'медленная тяга' : 'ровная тяга'];
  if (h.cv > 0.65) parts.push('рывками'); else if (h.cv < 0.3) parts.push('плавно');
  parts.push(h.press > 1.12 ? 'сильный прижим' : h.press < 0.95 ? 'лёгкий прижим' : 'обычный прижим');
  return 'почерк: ' + parts.join(' · ');
}
function onUp(x, y, id) {
  if (drag.id !== id) return;
  const kind = drag.kind; drag.id = null; drag.kind = null;
  if (kind === 'chips') {
    if (!drag.moved) for (const c of chips) if (inRect(x, y, c)) { S.sel = c.kind; break; }
  } else if (kind === 'roll') {
    sfx.rustleStop();
    measureHand();
    if (S.rollP >= 0.5) tween(S.rollP, 1, 380, v => { S.rollP = v; }, () => { S.mode = 'rolled'; S.rollP = 0; dirty = true; });
    else tween(S.rollP, 0, 260, v => { S.rollP = v; });
  } else if (kind === 'move') {
    const p = drag.patch; drag.patch = null;
    if (!drag.moved) { S.selPatch = S.selPatch === p ? null : p; }
    else { if (drag.outside) { const l = patches(); l.splice(l.indexOf(p), 1); S.selPatch = null; } touchModel(); }
    drag.outside = false;
  } else if (kind === 'place') {
    if (!drag.moved) { const uv = sheetUV(x, y); placeAt(uv.u, uv.v); }
  }
  dirty = true; requestFrame();
}
