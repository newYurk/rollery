// ── РЕГРЕССИОННАЯ ПРОВЕРКА СТЕНДА ─────────────────────────────────────────────
// Запуск: открыть play/index.html?check — отчёт печатается в консоль и на страницу.
// Из кода: runChecks() возвращает строку; runChecks(true) — объект с подробностями.
//
// ЗАЧЕМ. За два дня четыре поломки прошли молча, и ни одну не поймал бы список задач:
//   • сняли флаг oneTurn — отключился подворот у всех суши-баз;
//   • перешли на целый лист — устарела константа пола, цель касания просела до 36,8 px;
//   • обёртка стала выбором — кеш модели про неё не знал, блин 2 мм возвращал модель нори;
//   • чипы обрезались в 3615 случаях на прогоне.
// Все четыре — тихие: код перестал соответствовать сам себе, и об этом никто не узнал.
//
// ЭТАЛОННЫЕ ЧИСЛА НИЖЕ — НЕ ПРОИЗВОЛ. Каждое добыто замером и записано в docs/.
// Менять их можно, но ТОЛЬКО осознанно: если проверка падает, сперва понять почему,
// и лишь потом править эталон — вместе с коммитом, где сказано, что изменилось в модели.

const REF = {
  // ⌀ по медиане и максимуму, мм · оборотов · есть ли ядро (подворот)
  hoso:  { d: 27.5, dmax: 29.0, turns: 1.34, core: true },
  futo:  { d: 50.5, dmax: 53.5, turns: 1.45, core: true },
  ura:   { d: 35.3, dmax: 36.5, turns: 1.04, core: true },
  fruit: { d: 49.5, dmax: 52.0, turns: 1.57, core: true },
  cake:  { d: 70.5, dmax: 71.0, turns: 2.06, core: false },
};
const TOL_D = 0.6, TOL_T = 0.05;      // мм и обороты
const TOL_LEVEL = 3;                  // средняя яркость риса: |Δ| ≤ 3 (см. docs/geometry-audit.md)
const ROUND_MAX = 8;                  // некруглость, % — циновка обжимает ролл (reality-check)
const PATCH_MIN = 24;                 // px: брусок на экране; +10 px ореола с каждой стороны = 44
const SIZES = [[390, 844], [844, 390], [1024, 768], [1024, 1366], [1440, 900]];

function runChecks(detail) {
  const fails = [], notes = [];
  const keep = { base: S.base, wrap: S.wrap, shape: S.shape, turns: S.turns, hand: S.hand, mode: S.mode,
                 lists: JSON.parse(JSON.stringify(S.lists)), W, H, DPR };
  const ok = (cond, msg) => { if (!cond) fails.push(msg); return cond; };
  const near = (a, b, t) => Math.abs(a - b) <= t;
  const clean = () => { S.shape = 'round'; S.turns = null; S.mode = 'lay';
    S.hand = { air: 0, wobble: 0, phase: 0, press: 1, v: 1, cv: 0, hold: 0 }; };
  const dia = () => {   // медиана, максимум, некруглость
    const m = getModel(), wd = windFor(m, 0.5), N = 360, rs = [];
    for (let i = 0; i < N; i++) rs.push(topAt(wd, i / N * TAU));
    rs.sort((a, b) => a - b);
    return { m, wd, med: 2 * rs[N >> 1] * U_MM, max: 2 * rs[N - 1] * U_MM,
             round: 100 * (rs[N - 1] - rs[0]) / rs[N >> 1] };
  };

  try {
    // ── 1. ГЕОМЕТРИЯ: диаметры, витки, ядро, круглость ──
    for (const k in REF) {
      S.base = k; S.wrap = null; S.lists[k] = []; clean(); touchModel(); layout();
      const r = REF[k], d = dia(), n = BASES[k].name;
      ok(near(d.med, r.d, TOL_D), `${n}: ⌀ по медиане ${d.med.toFixed(1)} мм, эталон ${r.d}`);
      ok(near(d.max, r.dmax, TOL_D * 2), `${n}: ⌀ по максимуму ${d.max.toFixed(1)} мм, эталон ${r.dmax}`);
      ok(near(d.wd.turns, r.turns, TOL_T), `${n}: витков ${d.wd.turns.toFixed(2)}, эталон ${r.turns}`);
      ok(!!d.m.core === r.core, `${n}: ядро ${d.m.core ? 'есть' : 'НЕТ'}, ожидалось ${r.core ? 'есть' : 'нет'}`);
      ok(d.round <= ROUND_MAX, `${n}: некруглость ${d.round.toFixed(0)} %, потолок ${ROUND_MAX}`);
    }

    // ── 2. ОБЁРТКА ВХОДИТ В МОДЕЛЬ ──
    // Ловит поломку кеша: без обёртки в ключе блин 2 мм возвращал модель нори.
    S.base = 'futo'; S.lists.futo = []; clean();
    const ws = Object.keys(WRAPPERS), got = [];
    for (const w of ws) { S.wrap = w; touchModel(); layout(); got.push(dia().med); }
    S.wrap = null;
    // Считаем по РАЗНЫМ толщинам: блин и шоколадный блин оба 2,0 мм, им и положено совпасть.
    const thick = new Set(Object.values(WRAPPERS).map(w => w.mm));
    ok(new Set(got.map(x => x.toFixed(1))).size === thick.size,
       `разные толщины дают одинаковый ⌀ — кеш не знает про обёртку: ${got.map(x => x.toFixed(1)).join(' / ')}`);
    const byMm = ws.map((w, i) => [WRAPPERS[w].mm, got[i]]).sort((a, b) => a[0] - b[0]);
    for (let i = 1; i < byMm.length; i++)
      ok(byMm[i][1] >= byMm[i - 1][1] - 0.05,
         `толще обёртка — должен быть толще ролл: ${byMm[i - 1][0]} мм → ${byMm[i - 1][1].toFixed(1)}, ${byMm[i][0]} мм → ${byMm[i][1].toFixed(1)}`);

    // ── 3. ПРОФИЛЬ НАМАЗКИ ──
    // Ловит обрыв стеной у дальнего края и потерю голой полосы у ближнего.
    for (const k of ['hoso', 'futo', 'cake']) {
      S.base = k; clean(); touchModel();
      const g = getModel().g, se = g.spreadEnd, n = BASES[k].name, N = 400;
      ok(spreadAt(se + 1e-4, g) === 0, `${n}: за spreadEnd намазка не ноль`);
      if (!g.sweet) ok(spreadAt(0, g) === 0, `${n}: у ближней кромки нет голой полосы`);
      let prev = 0, maxDrop = 0, area = 0;
      for (let i = 0; i <= N; i++) {
        const u = i / N * se, v = spreadAt(u, g);
        if (i) { maxDrop = Math.max(maxDrop, prev - v); area += (v + prev) / 2 * (se / N); }
        prev = v;
      }
      ok(maxDrop < 0.35, `${n}: намазка обрывается стеной — скачок ${maxDrop.toFixed(2)} за один шаг`);
      ok(near(area, se, se * 0.03), `${n}: масса не сохранена — ∫ ${area.toFixed(3)} против ${se}`);
    }

    // ── 4. ПАЗЛ ──
    S.base = 'futo'; clean();
    try {
      puzzleStart(0, 5);
      S.lists[S.base] = S.puzzle.target.map(x => ({ ...x })); touchModel(); layout();
      const same = puzzleEvaluate(); const sv = (same.sim !== undefined ? same.sim : same) * 100;
      S.lists[S.base] = S.puzzle.target.map(x => ({ ...x, u: 1 - x.u })); touchModel(); layout();
      const mir = puzzleEvaluate(); const mv = (mir.sim !== undefined ? mir.sim : mir) * 100;
      puzzleStop();
      ok(sv >= 99, `пазл: точная копия ${sv.toFixed(0)} %, ожидалось 100`);
      ok(mv <= 25, `пазл: зеркальная ${mv.toFixed(0)} %, потолок 25`);
    } catch (e) { fails.push('пазл: ' + e.message); }

    // ── 5. ЯРКОСТЬ РИСА ──
    // Рельеф и щели темнее намазки; без компенсации рис молча темнеет — это была бы
    // правка внешнего вида продукта, а не читаемости.
    S.base = 'futo'; clean(); touchModel();
    const b = B(), c = b.spreadRgb;
    for (const cut of [false, true]) {
      let s = [0, 0, 0], n = 0;
      for (let i = 0; i < 150; i++) for (let j = 0; j < 150; j++) {
        let p;
        if (cut) { const gx = (i - 75) * 0.12, gy = (j - 75) * 0.12, rr = Math.hypot(gx, gy) || 1e-6;
                   p = spreadColor(gx, gy, b, -gy / rr, gx / rr, 1); }
        else p = spreadColor(i * 0.062, j * 0.062, b, undefined, undefined, 1);
        s[0] += p[0]; s[1] += p[1]; s[2] += p[2]; n++;
      }
      const d = s.map((x, i) => (x / n) - c[i]);
      ok(d.every(x => Math.abs(x) <= TOL_LEVEL),
         `яркость риса ${cut ? 'на срезе' : 'на листе'}: Δ ${d.map(x => x.toFixed(1)).join('/')}, допуск ±${TOL_LEVEL}`);
    }

    // ── 6. РАСКЛАДКА: ничего не спрятано молча, палец достаёт ──
    for (const [w, h] of SIZES) {
      W = w; H = h; DPR = 2;
      for (const k in REF) {
        S.base = k; S.wrap = null; S.lists[k] = []; clean();
        for (const prev of [false, true]) {
          S.preview = prev; touchModel(); layout();
          const tag = `${w}×${h} ${BASES[k].name}${prev ? ' +превью' : ''}`;
          const ings = B().ingredients.length, per = L.chips.perRow || ings, rows = L.chips.rows || 1;
          const hidden = Math.max(0, ings - per * rows);
          ok(hidden === 0 || L.chipScroll, `${tag}: ${hidden} начинок спрятано БЕЗ прокрутки`);
          const patch = 2 / getModel().g.L * L.sheet.h;   // брусок 2 ед. на экране
          ok(patch >= PATCH_MIN, `${tag}: цель касания ${patch.toFixed(1)} px, нужно ≥ ${PATCH_MIN} (+ореол = 44)`);
          ok(L.sheet.w > 0 && L.sheet.h > 0, `${tag}: лист схлопнулся`);
        }
      }
    }
    S.preview = false;
  } catch (e) {
    fails.push('ПАДЕНИЕ: ' + e.message + (e.stack ? ' @ ' + e.stack.split('\n')[1] : ''));
  } finally {
    Object.assign(S, { base: keep.base, wrap: keep.wrap, shape: keep.shape, turns: keep.turns,
                       hand: keep.hand, mode: keep.mode, lists: keep.lists });
    W = keep.W; H = keep.H; DPR = keep.DPR;
    try { touchModel(); layout(); dirty = true; requestFrame(); } catch (e) {}
  }

  const head = fails.length ? `ПРОВАЛ · ${fails.length}` : 'ВСЁ ЦЕЛО';
  const text = head + (fails.length ? '\n  ' + fails.join('\n  ') : '');
  return detail ? { ok: !fails.length, fails, notes, text } : text;
}

if (location.search.indexOf('check') >= 0) {
  addEventListener('load', () => setTimeout(() => {
    const r = runChecks(true);
    console.log(r.text);
    const d = document.createElement('pre');
    d.style.cssText = 'position:fixed;inset:0;z-index:99;margin:0;padding:16px;overflow:auto;' +
      'background:#171713;color:' + (r.ok ? '#7ac77a' : '#e08a6a') +
      ';font:13px/1.6 ui-monospace,Menlo,monospace;white-space:pre-wrap';
    d.textContent = r.text + '\n\nЭталоны — в начале play/checks.js. Падение чинится в коде,\nа не правкой эталона, пока не понято, что именно изменилось в модели.';
    document.body.appendChild(d);
  }, 400));
}
