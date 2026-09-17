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
  { n: 2, turns: 4, pieces: 1, wrap: 1, rot: 1 },   // rot добавлен 02.09, turns 3→4 16.09: без wrap и rot уровень — копия второго (#159, #168)
  { n: 3, turns: 2, pieces: 1, shape: 'square' },
  { n: 3, turns: 3, pieces: 3, local: 1 },
  { n: 4, turns: 4, pieces: 1, shape: 'triangle' },
  { n: 3, turns: 3, pieces: 6, local: 2 },
  { n: 3, turns: 3, pieces: 6, rot: 1 },
  { n: 3, turns: 4, pieces: 3, local: 1, wrap: 1, rot: 1 },   // то же, копия шестого; turns 3→4 16.09 (#159, #168)
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
  // В цель — только то, что игрок может положить на этот лист: фишка не тусклая (#253). Сегодня
  // фильтр ничего не отсекает — все обычные куски и краски, что ложатся в уровнях, помещаются
  // (дэмбу не помещается только на двух витках, а краски там нет), — он стережёт завтрашние уровни.
  const base = b.ingredients.filter(k => k !== 'nori' && !ING[k].wave && !isLong(k) && !ING[k].paint && chipFits(k));
  const paints = b.ingredients.filter(k => ING[k].paint && chipFits(k));
  const full = base.filter(k => !isLocal(k)), local = base.filter(isLocal);
  const kinds = [];
  for (let i = 0; i < (lv.local || 0) && local.length; i++) kinds.push(local[Math.floor(rnd() * local.length)]);
  // Длинный кусок — только если он вообще ложится на рис (#253): у узумаки на двух витках лист
  // 53 мм, грядка 45, а омлет-лист 50 — такой цели игроку не собрать. Слот тогда отдаётся
  // обычному куску ниже.
  if (lv.sheet && rnd() < 0.7) { const k = b.ingredients.find(isLong); if (k && layFits({ kind: k, u: 0.5, v: 0.5 })) kinds.push(k); }
  for (let i = 0; i < (lv.paint || 0) && paints.length; i++) kinds.push(paints[Math.floor(rnd() * paints.length)]);
  while (kinds.length < lv.n) kinds.push(full[Math.floor(rnd() * full.length)]);
  const items = kinds.map(kind => ({ kind, half: ING[kind].wU / L / 2 + 0.012 }));
  const uMax = 0.92;   // суши: только то, что точно намотается до замыкания (ядро + первый оборот)
  // ⚑ ПОПЫТКА С КУСКОМ НА ГОЛОМ КРАЕ БРАКУЕТСЯ (#253, 17.09). Окно шло от 0,012 листа до uMax, то
  // есть и по голым полям: замер 17.09 (шесть баз × 16 уровней × 24 зерна) — 976 кусков из 7344
  // на голом крае, у хосомаки дальняя кромка риса 0,863 при uMax 0,92. Игрок так положить уже не
  // может, значит и цель не может. Окно не сдвинуто, а попытка отбрасывается, как при наложении
  // кусков: цели, которые и раньше лежали на рисе, остаются побитно прежними, меняются только те,
  // что лежали на голом. Вариантов станет меньше — владелец это приняла.
  const рис = riceSpanU();
  const полу = items.map(it => { const bb = bounds({ kind: it.kind, u: 0, v: 0.5 }, undefined, true); return (bb.u1 - bb.u0) / 2; });
  let us = null, снизу = null;   // снизу — порядок кусков в цели при вынужденной стопке (ниже)
  for (let tries = 0; tries < 80 && !us; tries++) {
    const cand = items.map(it => it.half + rnd() * (uMax - 2 * it.half));
    const order = cand.map((u, i) => i).sort((a, c) => cand[a] - cand[c]); let ok = true;
    for (let j = 1; j < order.length; j++) { const a = order[j - 1], c = order[j]; if (cand[c] - cand[a] < items[a].half + items[c].half) { ok = false; break; } }
    if (ok && cand.some((u, i) => u - полу[i] < рис.u0 || u + полу[i] > рис.u1)) ok = false;
    if (ok) us = cand;
  }
  if (!us) {
    // Запасная укладка — подряд от кромки риса (прежде от 0,03 листа, то есть с голого края).
    // Окно риса уже листа, и подряд с прежними зазорами (0,012 у кромки, 0,044 между следами)
    // влезает не всегда: тогда зазоры сжимаются поровну.
    const n = items.length, W = рис.u1 - рис.u0, своб = W - полу.reduce((a, h) => a + 2 * h, 0);
    if (своб >= 0) {
      const край = Math.max(0, Math.min(0.012, своб / 2));
      const зазор = Math.max(0, Math.min(0.044, (своб - 2 * край) / Math.max(1, n - 1)));
      let u = рис.u0 + край; us = полу.map(h => { const x = u + h; u += 2 * h + зазор; return x; });
    } else {
      // ⚑ ВСЁ ПОДРЯД НЕ ВЛЕЗАЕТ (17.09, замечание проверки #253). Прежде хвост ряда прижимал к
      // кромке последний рубеж, и куски ложились стопкой даже там, где твёрдым места хватало:
      // место съедали краска, ложбинка и грядка, а они стопки не образуют (restack их не
      // складывает). Теперь ряд — только из твёрдых, плоские (краска, ложбинка, грядка) ложатся
      // в просветы между ними:
      //   · твёрдые помещаются — просветы поровну, у кромок тоже; плоский кусок — посреди
      //     просвета, а если шире его — заходит на соседей поровну с двух сторон;
      //   · не помещаются даже встык — это ВЫНУЖДЕННАЯ СТОПКА, и она ПРИНЯТА: так положил бы и
      //     повар, когда куски шире риса. Куски раскладываются РЯДАМИ СНИЗУ ВВЕРХ: широкие первыми,
      //     каждый в первый ряд, где он ещё помещается (омлет-лист поэтому всегда внизу, как лист
      //     под начинкой); ряд — по всему рису с равными просветами; в списке нижний ряд идёт
      //     раньше верхнего, потому что restack кладёт позднее на раннее. Ярусов столько, сколько
      //     рядов, — обычно два. Прежде хвост прижимался к кромке и мог встать башней (два джема
      //     в одной точке, 3 яруса), а раскладка внахлёст по всему рису, опробованная 17.09, дала
      //     лесенку: каждый кусок ложился на соседа, и ярусов было столько, сколько кусков.
      //     Плоские — поровну по рису.
      // Вынужденных стопок с запретом голого края стало больше: окно риса уже листа (у хосомаки
      // на двух витках 84 мм вместо 95 по листу), и уровень 12 — омлет-лист 50 мм и ещё три куска
      // на листе 105 мм — встык не помещается чаще. Замер 17.09, 100 зёрен, обёртка по умолчанию,
      // уровень 12, целей со стопкой до запрета / после: хосомаки 14 → 40, тюмаки 12 → 29,
      // футомаки 6 → 12, урамаки 12 → 4, узумаки 87 → 45 (омлет-лист там больше не берётся).
      // Все — вынужденные, у хосомаки, тюмаки, футомаки и урамаки все с омлет-листом; сторож ГК-5
      // держит, что других нет. Не собирать их значило бы выкинуть омлет-лист из уровня 12 в 40
      // зёрнах хосомаки из 100 (берётся он в 70) — а уровень ради длинного куска и заведён.
      const плоск = i => !!ING[items[i].kind].paint || !!ING[items[i].kind].bedDelta;
      const тв = [], кр = [];
      for (let i = 0; i < n; i++) (плоск(i) ? кр : тв).push(i);
      const сумма = тв.reduce((a, i) => a + 2 * полу[i], 0);
      us = new Array(n);
      if (сумма <= W) {
        const просвет = (W - сумма) / (тв.length + 1), середины = [];
        let u = рис.u0;
        for (const i of тв) { середины.push(u + просвет / 2); u += просвет; us[i] = u + полу[i]; u += 2 * полу[i]; }
        середины.push(u + просвет / 2);
        кр.forEach((i, j) => { us[i] = середины[Math.min(середины.length - 1, Math.floor((j + 0.5) * середины.length / кр.length))]; });
      } else {
        const ряды = [];
        for (const i of тв.slice().sort((a, c) => полу[c] - полу[a])) {
          let ряд = ряды.find(r => r.сумма + 2 * полу[i] <= W);
          if (!ряд) { ряд = { idx: [], сумма: 0 }; ряды.push(ряд); }
          ряд.idx.push(i); ряд.сумма += 2 * полу[i];
        }
        ряды.forEach((ряд, r) => {
          ряд.idx.sort((a, c) => a - c);                      // внутри ряда — в прежнем порядке
          // ряд из одного куска — не посередине, а по очереди от ближней кромки к дальней (при двух
          // рядах — на четверти и трёх четвертях риса): иначе одиночные ряды встают точно друг на
          // друга — узумаки на нори, уровень 5: два джема в одной точке, глазами 17.09
          if (ряд.idx.length === 1) { const i = ряд.idx[0]; us[i] = рис.u0 + полу[i] + (W - 2 * полу[i]) * ((r + 0.5) / ряды.length); return; }
          const просвет = (W - ряд.сумма) / (ряд.idx.length + 1);
          let u = рис.u0;
          for (const i of ряд.idx) { u += просвет; us[i] = u + полу[i]; u += 2 * полу[i]; }
        });
        кр.forEach((i, j) => { us[i] = рис.u0 + W * (j + 0.5) / кр.length; });
        снизу = ряды.flatMap(r => r.idx).concat(кр);
      }
    }
  }
  const все = items.map((it, i) => { const d = ING[it.kind]; const p = { kind: it.kind, u: us[i], v: 0.5, z0: 0, z1: 0, phase: rnd() * TAU }; if (d.dv < 1) p.v = d.dv / 2 + rnd() * (1 - d.dv); return p; });
  const list = снизу ? снизу.map(i => все[i]) : все;
  // Поворот исполняется, только пока он есть у игрока (#168) — тот же приём, что с wrap ниже.
  if (ROTATE_PIECE_ON && lv.rot) for (let r = 0, n0 = 0; r < list.length && n0 < lv.rot; r++) { const p = list[r]; if (ING[p.kind].wave || isLong(p.kind)) continue; p.rot = rnd() < 0.5 ? Math.PI / 4 : Math.PI / 2; p.dv = 0.22; p.v = 0.25 + rnd() * 0.5; n0++; }
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
  // Последний рубеж — то же правило, что у игрока (#253): что не влезло в окно (запасная укладка,
  // кусок шире окна, поворот или обёртка, если их вернут), встаёт на ближайшее место на рисе.
  for (const p of list) p.u = layU(p, p.u);
  return list;
}
function puzzleStart(level, seed) {
  level = clamp(level, 0, LEVELS.length - 1); const lv = LEVELS[level];
  S.turns = lv.turns; S.selPatch = null; S.shape = lv.shape || 'round';
  selOnRice();   // лист уровня короче — выбранная фишка могла стать тусклой (#253)
  S.puzzle = { level, seed, lv, target: null, vs: puzzleSlices(lv.pieces), result: null };
  S.puzzle.target = genTarget(lv, seed * 7919 + level * 131);
  // Сгенерированная цель хранится отдельно: при смене обёртки цель выводится из неё заново, и
  // круг обёрток возвращает её до бита (#253, 17.09, layRefit в state.js).
  S.puzzle.target0 = S.puzzle.target.map(p => Object.assign({}, p));
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
  // ⚑ ЧИСЛА — КАК ЕСТЬ, БЕЗ ОКРУГЛЕНИЯ (#236, 16.09). Здесь стояли toFixed(4) у u, (3) у v и фазы,
  // (2–3) у руки: друг открывал ДРУГОЙ ролл, а у порога режима — даже другой режим (футомаки, тамаго
  // на 149,13 мм: спираль → после ссылки кольцо). JSON и так пишет число кратчайшей точной записью.
  // Старые ссылки с округлёнными числами читаются как раньше.
  const h = S.hand || {}; const data = { b: S.base, w: B().wrapKey || null, t: turns || null, s: S.shape, h: (h.air || h.wobble || (h.press !== 1)) ? [h.air, h.wobble, h.phase, h.press] : null, l: list.map(p => [p.kind, p.u, p.v, p.wU ?? null, p.hU ?? null, p.dv ?? null, p.phase, p.rot || null]) };
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
    // ⚑ СТАРАЯ ССЫЛКА С КУСКОМ НА ГОЛОМ КРАЮ (#253, 17.09): кусок сдвигается по u на ближайшее
    // место на рисе — на листе той ссылки (база, обёртка, витки), а не того, что открыт сейчас.
    // Лежавшее на рисе не трогается до бита (#236). Витки — не меньше 2 и такие, чтобы на рис лёг
    // каждый кусок (`recipeTurns`, решение владельца 17.09): старая цель узумаки уровня 12 с
    // омлет-листом открывается на 3 витках, а не с омлетом на голой нори.
    const turns = recipeTurns({ base: data.b, wrap, turns: data.t }, list);
    withSheetOf({ base: data.b, wrap, turns }, () => layOnRice(list));
    return { base: data.b, wrap, turns, shape: SHAPES[data.s] ? data.s : 'round', hand: hh, list };
  } catch (e) { return null; }
}
function puzzleFromLink(pz) {
  S.base = pz.base; S.wrap = pz.wrap || null; S.sel = uiIngredients()[0] || B().ingredients[0];
  S.turns = turnsOf(pz.turns); S.selPatch = null; S.shape = pz.shape || 'round';
  selOnRice();   // #253: первая фишка всегда ложится, но правило одно на все пути
  if (pz.hand) S.hand = pz.hand;
  const local = pz.list.some(p => (p.dv ?? ING[p.kind].dv) < 1), n = pz.list.filter(p => p.kind !== 'nori').length;
  const lv = { n, turns: S.turns || B().turns, pieces: local ? 3 : 1, custom: true };
  S.puzzle = { level: -1, seed: 0, lv, target: pz.list, target0: pz.list.map(p => Object.assign({}, p)), vs: puzzleSlices(lv.pieces), result: null };
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
  if (lv.wrap && WRAP_PIECE_ON) parts.push('нори'); if (lv.local) parts.push('короткие'); if (lv.paint) parts.push('цв. рис'); if (lv.rot && ROTATE_PIECE_ON) parts.push('поворот'); if (lv.shape && lv.shape !== 'round') parts.push(SHAPES[lv.shape].glyph);
  return parts.join(' · ');
}
