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
  { n: 2, turns: 3, pieces: 1, wrap: 1, rot: 1 },   // rot добавлен 02.09: без wrap уровень был копией второго (#159)
  { n: 3, turns: 2, pieces: 1, shape: 'square' },
  { n: 3, turns: 3, pieces: 3, local: 1 },
  { n: 4, turns: 4, pieces: 1, shape: 'triangle' },
  { n: 3, turns: 3, pieces: 6, local: 2 },
  { n: 3, turns: 3, pieces: 6, rot: 1 },
  { n: 3, turns: 3, pieces: 3, local: 1, wrap: 1, rot: 1 },   // то же: без wrap был копией шестого (#159)
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
  // Уровни свои `wrap` не теряют — их просто не исполняем, пока приём выключен: иначе цель
  // потребовала бы того, чего игрок сделать не может (#159). Разбор — над WRAP_PIECE_ON.
  for (let w = 0; WRAP_PIECE_ON && w < (lv.wrap || 0); w++) {
    // Генерация обёрнутых кусков остановлена 31.08 и ВОЗВРАЩЕНА 01.09 (#115): обёртка перестала
    // быть четырьмя несходящимися плашками и стала свойством самого куска, так что цель больше
    // не требует от игрока повторить то, что модель считает неверно.
    const cands = list.filter(p => p.kind !== 'nori' && !isLong(p.kind) && !p.wrapped); if (!cands.length) break;
    const F = cands[Math.floor(rnd() * cands.length)]; F.wrapped = true; wrapInNoriList(F, list);
  }
  for (const p of list) delete p.wrapped;   // временная метка генератора; noriWrap остаётся — он и есть обёртка
  return list;
}
function puzzleStart(level, seed) {
  level = clamp(level, 0, LEVELS.length - 1); const lv = LEVELS[level];
  S.turns = lv.turns; S.selPatch = null; S.shape = lv.shape || 'round';
  S.puzzle = { level, seed, lv, target: null, vs: puzzleSlices(lv.pieces), result: null };
  S.puzzle.target = genTarget(lv, seed * 7919 + level * 131);
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
  S.lists[S.base] = []; histReset(); touchModel(); layout();   // #150
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
  // w — обёртка: она меняет шаг витка, а с ним число оборотов и ⌀ (issue #86). Без неё
  // друг открывал ссылку и получал ДРУГОЙ ролл: цель пазла считалась по нори вместо блина.
  const h = S.hand || {}; const data = { b: S.base, w: B().wrapKey || null, t: turns || null, s: S.shape, h: (h.air || h.wobble || (h.press !== 1)) ? [+h.air.toFixed(3), +h.wobble.toFixed(3), +h.phase.toFixed(2), +h.press.toFixed(2)] : null, l: list.map(p => [p.kind, +p.u.toFixed(4), +p.v.toFixed(3), p.wU ?? null, p.hU ?? null, p.dv ?? null, +p.phase.toFixed(3), p.rot ? +p.rot.toFixed(4) : null]) };
  return location.origin + location.pathname + '#p=' + btoa(unescape(encodeURIComponent(JSON.stringify(data)))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function decodePuzzle(hash) {
  try {
    const mm = /#p=([A-Za-z0-9_-]+)/.exec(hash); if (!mm) return null;
    const json = decodeURIComponent(escape(atob(mm[1].replace(/-/g, '+').replace(/_/g, '/'))));
    const data = JSON.parse(json); if (!data.l || !BASES[data.b]) return null;
    const list = data.l.map(a => { const p = { kind: a[0], u: a[1], v: a[2], z0: 0, z1: 0, phase: a[6] || 0 }; if (a[3] != null) p.wU = a[3]; if (a[4] != null) p.hU = a[4]; if (a[5] != null) p.dv = a[5]; if (a[7]) p.rot = a[7]; return p; }).filter(p => ING[p.kind]);
    // Рука из ссылки может прийти короткой или с мусором — handOf дополнит по полю (#36).
    const hh = Array.isArray(data.h) ? handOf({ air: data.h[0], wobble: data.h[1], phase: data.h[2], press: data.h[3] }) : null;
    // Ссылки БЕЗ поля w (созданные до 30.08) читаются как обёртка базы по умолчанию —
    // формат расширен совместимо, старые ссылки продолжают открываться.
    const wrap = (data.w && WRAPPERS[data.w]) ? data.w : null;
    return { base: data.b, wrap, turns: data.t, shape: SHAPES[data.s] ? data.s : 'round', hand: hh, list };
  } catch (e) { return null; }
}
function puzzleFromLink(pz) {
  S.base = pz.base; S.wrap = pz.wrap || null; S.sel = uiIngredients()[0] || B().ingredients[0];
  S.turns = turnsOf(pz.turns); S.selPatch = null; S.shape = pz.shape || 'round';
  if (pz.hand) S.hand = pz.hand;
  const local = pz.list.some(p => (p.dv ?? ING[p.kind].dv) < 1), n = pz.list.filter(p => p.kind !== 'nori').length;
  const lv = { n, turns: S.turns || B().turns, pieces: local ? 3 : 1, custom: true };
  S.puzzle = { level: -1, seed: 0, lv, target: pz.list, vs: puzzleSlices(lv.pieces), result: null };
  S.lists[S.base] = []; histReset(); touchModel(); layout();   // #150 if (S.mode !== 'lay') action('back'); dirty = true; requestFrame();
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
