'use strict';
// ДЕЙСТВИЯ И ВВОД: одна точка, куда сходятся все команды игрока.
//
// Кнопки, иконки и жесты не трогают состояние сами — они зовут action(id). Поэтому список
// того, что игрок вообще может сделать, читается одним switch, и туда же встраивается история
// отмены: любое действие, меняющее раскладку, сначала кладёт снимок (см. state.js, pushHistory).
//
// Вынесено 30.08.2026 из modes/puzzle.js, куда попало при нарезке по разделам: action() — общий
// обработчик всей игры, а не часть режима «Пазл».

function layRose() {
  S.base = 'futo';
  S.shape = 'round';
  S.winding = 'spiral';
  S.turns = null;
  S.mode = 'lay';
  S.rollP = 0;
  S.puzzle = null;
  if (!S.lists[S.base]) S.lists[S.base] = [];
  palSync();
  const list = patches();
  if (!list) return;
  pushHistory();
  list.length = 0;
  const put = (kind, u) => {
    const m = dims({ kind });
    const p = { kind, u, v: 0.5, z0: 0, z1: m.h, phase: 0 };
    if (!layFits(p)) return;
    p.u = layU(p, u);
    list.push(p);
  };
  put('cucumber', 0.14);
  put('salmonSlice', 0.30);
  put('tunaSlice', 0.46);
  put('salmonSlice', 0.62);
  put('tunaSlice', 0.78);
  S.sel = 'salmonSlice';
  S.palGroup = 'fish';
  S.preview = true;
  touchModel(); layout(); dirty = true;
}

function action(id) {
  switch (id) {
    // Отмена и возврат — по ИСТОРИИ ДЕЙСТВИЙ, а не по концу списка (issue #84). Каждое
    // действие ниже, меняющее раскладку, кладёт снимок ПЕРЕД собой: pushHistory().
    case 'undo': if (S.mode === 'lay' && undo()) { sfx.place(); undoNote = 0; } break;
    case 'redo': if (S.mode === 'lay' && redo()) sfx.place(); break;
    // ОЧИСТКА — В ДВА КАСАНИЯ (#157). Первое взводит, второе чистит; разбор — над `clearArm`
    // в controls.js. Пустой лист чистить нечего, и взводить тоже: касание просто гаснет.
    case 'clear': {
      if (S.mode !== 'lay' || !patches().length) { clearArm = 0; break; }
      const т = performance.now();
      if (clearArm < т) { clearArm = т + 2500; break; }
      clearArm = 0; pushHistory(); S.lists[S.base] = []; S.selPatch = null; touchModel();
      undoNote = т + 5000; break;
    }
    case 'wrap': if (S.mode === 'lay' && S.selPatch) { pushHistory(); wrapInNori(S.selPatch); } break;
    // ПОВОРОТ — ТОЛЬКО В ПЛОСКОСТИ ЛИСТА, вокруг вертикали. Кусок нельзя положить на другую
    // грань: сектор огурца всегда лежит плоской гранью на рисе, кожицей вверх. Это решение
    // владельца (31.08) и оно записано в docs/domain-contract.md — не забыть при добавлении
    // вида сбоку: раскладка и поворот живут ТОЛЬКО в виде сверху.
    // Диапазон берётся ИЗ ФОРМЫ: у симметричного куска 180° — то же, что 0°, и лишние щелчки
    // только раздражают; у несимметричного (сектор) все 360° дают разные положения.
    case 'rotate': if (ROTATE_PIECE_ON && S.mode === 'lay' && S.selPatch) { pushHistory(); const p = S.selPatch;
      const span = cutSymmetric(ING[p.kind]) ? Math.PI : TAU;
      p.rot = ((p.rot || 0) + Math.PI / 4) % span; if (p.rot < 1e-6) delete p.rot; const bb = bounds(p), hv = (bb.v1 - bb.v0) / 2; p.u = layU(p, p.u); p.v = clamp(p.v, Math.min(0.5, hv), Math.max(0.5, 1 - hv)); touchModel(); sfx.place(); } break;   // по u — на рис (#253)
    case 'remove': if (S.mode === 'lay' && S.selPatch) { pushHistory(); const l = patches(), i = l.indexOf(S.selPatch); if (i >= 0) l.splice(i, 1); S.selPatch = null; touchModel(); } break;
    case 'deselect': S.selPatch = null; dirty = true; break;
    case 'back': S.mode = 'lay'; S.rollP = 0; S.bigPiece = -1; S.albumOpen = -1; cut = null; slicing = null; if (S.puzzle) S.puzzle.result = null; dirty = true; break;
    case 'new': S.lists[S.base] = []; histReset(); touchModel(); action('back'); break;   // #150
    case 'slice': if (S.mode === 'revealed') startSlicing(); break;
    case 'preview': S.preview = !S.preview; save(); layout(); dirty = true; break;
    // Контуры границ по модели поверх среза. Не сохраняются: это режим проверки, а не настройка.
    case 'lines': S.lines = !S.lines; dirty = true; break;
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
      const ks = Object.keys(WRAPPERS), cur = B().wrapKey || 'nori', i0 = ks.indexOf(cur);
      // Обёртку, на которой лежащий кусок не поместился бы на рис вовсе, перебор пропускает (#253,
      // 17.09): узумаки в пазле на двух витках — банан, положенный на омлете, на нори не ложится.
      // ⚠ ВОПРОС, КОТОРЫЙ ЗДЕСЬ ВОЗНИКАЕТ И ЗАКРЫТ ЗАМЕРОМ (слияние 17.09). sheetTakes спрашивает
      // про лист при НЫНЕШНИХ витках, а у уровня витки под новой обёрткой другие (строка ниже их
      // пересчитывает) — то есть теоретически перебор мог бы пропустить обёртку, которую лист
      // уровня принял бы. Спросили прямо: 1440 сцен (6 баз × 16 уровней × 3 зерна × 5 стартовых
      // обёрток), для каждой обёртки ответ sheetTakes при нынешних витках против ответа при витках
      // уровня на этой обёртке — расхождений 0, пропущенных обёрток 0. Причина: у уровня длина
      // листа от обёртки не зависит (sheets · b.L), а там, где она упирается в пол «не короче
      // 2 витков», лист на всех обёртках длиннее, чем нужно нынешним кускам. Поэтому усложнять
      // sheetTakes незачем; если уровни или каталог изменятся, замер надо повторить —
      // runs/continuation/task10-spiral-nori/round5/tools/probe-sheettakes.js.
      let next = cur;
      for (let d = 1; d < ks.length; d++) { const k = ks[(i0 + d) % ks.length]; if (sheetTakes(k)) { next = k; break; } }
      S.wrap = next;
      // ⚑ ЛИСТ УРОВНЯ ПЕРЕСЧИТЫВАЕТСЯ ПОД НОВУЮ ОБЁРТКУ (17.09, #134/#242). Лист уровня — СКОЛЬКО
      // ЛИСТОВ БАЗЫ (поле sheets), то есть ДЛИНА; витки — производная от неё и от шага витка (T + w).
      // Обёртка шаг меняет, и при тех же витках лист на циновке становится другой длины: замер
      // 17.09 — футомаки ур.1, подпись 334 мм, на циновке 349 (−4,4 %), то же у тюмаки, хосомаки
      // и урамаки. Без этой строки новое правило действовало до первого нажатия «●».
      // Перезапускать уровень, как при смене базы, не нужно: b.L от обёртки не зависит, длина
      // сохраняется, и цель уровня вместе с раскладкой игрока остаются в силе.
      // Пазл ПО ССЫЛКЕ (custom) не трогаем: там лист задан витками явно (у него нет sheets), а null — «лист базы».
      // Стоит ПОСЛЕ выбора обёртки и ДО layRefit: подгонка кусков к рису считает лист по S.turns,
      // и с непересчитанными витками она подгоняла бы к листу, которого на циновке не будет.
      if (S.puzzle && S.puzzle.lv && S.puzzle.lv.sheets != null) S.turns = levelTurns(S.puzzle.lv);
      layRefit();   // при заданных витках обёртка меняет длину листа, кусок у кромки съехал бы на голое (#253)
      selOnRice();  // и выбранная фишка могла перестать помещаться
      wrapNote = WRAPPERS[S.wrap].name + ' · ' + WRAPPERS[S.wrap].mm + ' мм';
      wrapNoteT = performance.now();
      save(); touchModel(); layout(); dirty = true; break;
    }
    // Перебор режима намотки (кнопка ◎/○/◍, #141) снят 17.09 по решению владельца: режим всегда
    // авто. S.winding остаётся параметром модели — им пользуются сторожа и отпечаток.
    case 'shape': { const ks = Object.keys(SHAPES); S.shape = ks[(ks.indexOf(S.shape) + 1) % ks.length]; save(); if (S.puzzle && S.puzzle.result) S.puzzle.result = null; dirty = true; break; }
    case 'rollnow':
      if (S.puzzle) { puzzleEvaluate(); dirty = true; break; }
      if (S.mode === 'lay' && !anim) tween(S.rollP, 1, 1600, v => { S.rollP = v; }, () => { S.mode = 'rolled'; S.rollP = 1; dirty = true; });
      break;
    case 'pause':
      if (anim) { anim = null; dirty = true; }
      break;
    case 'resume':
      if (!anim && S.rollP < 0.99) tween(S.rollP, 1, Math.max(200, 1600 * (1 - S.rollP)), v => { S.rollP = v; }, () => { S.mode = 'rolled'; S.rollP = 1; dirty = true; });
      break;
    case 'cutnow':
      if (typeof tablePlay === 'function' && tablePlay() && S.rollP < 0.98) {
        tween(S.rollP, 1, Math.max(180, 700 * (1 - S.rollP)), v => { S.rollP = v; }, () => { S.mode = 'rolled'; S.rollP = 1; startCut(0.5); dirty = true; });
        break;
      }
      if (S.mode === 'rolled') startCut(0.5);
      else if (S.mode === 'lay' && !anim) tween(S.rollP, 1, 520, v => { S.rollP = v; }, () => { S.mode = 'rolled'; S.rollP = 1; startCut(0.5); dirty = true; });
      break;
    case 'fold-core': S.winding = null; S.turns = null; touchModel(); break;
    case 'fold-one': S.winding = 'ring'; S.turns = null; touchModel(); break;
    case 'fold-spiral': S.winding = 'spiral'; S.turns = null; touchModel(); break;
    case 'fold-layer': S.winding = 'ring'; S.turns = 2; touchModel(); break;
    case 'fold-hoso': S.base = 'hoso'; S.shape = 'round'; palSync(); S.selPatch = null; layOnRice(patches()); selOnRice(); palSync(); touchModel(); layout(); break;
    case 'fold-futo': S.base = 'futo'; S.shape = 'round'; palSync(); S.selPatch = null; layOnRice(patches()); selOnRice(); palSync(); touchModel(); layout(); break;
    case 'fold-ura': S.base = 'ura'; S.shape = 'round'; palSync(); S.selPatch = null; layOnRice(patches()); selOnRice(); palSync(); touchModel(); layout(); break;
    case 'fold-square': S.shape = 'square'; touchModel(); layout(); break;
    case 'mute': S.mute = !S.mute; sfx.setMute(S.mute); if (!S.mute) sfx.start(); save(); break;
    case 'step-place': if (S.mode !== 'lay') action('back'); break;
    case 'demo-rose': layRose(); break;
    case 'next': if (S.puzzle && S.puzzle.result && S.puzzle.result.pass) puzzleStart(Math.max(0, S.puzzle.level + 1), S.puzzle.seed + 1); break;
    case 'lvprev': if (S.puzzle && S.puzzle.level > 0) puzzleStart(S.puzzle.level - 1, S.puzzle.seed); else if (S.puzzle && S.puzzle.level < 0) puzzleStart(0, 1); break;
    case 'lvnext': if (S.puzzle && S.puzzle.level + 1 < LEVELS.length && S.puzzle.level + 1 <= puzzleMax()) puzzleStart(S.puzzle.level + 1, S.puzzle.seed); break;
    // Кнопка звука снята 17.09 (решение владельца): громкостью управляет телефон.
    // ⚑ ВЫБОР НАЧИНКИ ПРИ СМЕНЕ БАЗЫ НЕ СБРАСЫВАЕТСЯ (17.09). Здесь стояло безусловное «первая
    // начинка новой базы»: выбрал лосося, переключил базу — выбран огурец, и почему, игрок не
    // узнавал. palSync() оставляет начинку, если она есть и у новой базы, и открывает её
    // страницу палитры, если прежняя группа у новой базы отсутствует.
    // ⚠ И ТО, И ДРУГОЕ (слияние 17.09): layOnRice переносит куски новой базы на её рис (#253),
    // selOnRice уводит выбор с фишки, которая на новом листе не помещается, а второй palSync
    // подтягивает страницу палитры к начинке, которую selOnRice мог сменить.
    case 'base': { const keys = uiBases(); S.base = keys[(keys.indexOf(S.base) + 1) % keys.length]; palSync(); S.selPatch = null; layOnRice(patches()); selOnRice(); palSync(); wrapNote = BASES[S.base].name; wrapNoteT = performance.now(); touchModel(); layout(); if (S.puzzle) puzzleStart(S.puzzle.level, S.puzzle.seed); else if (S.mode !== 'lay') action('back'); break; }
  }
  requestFrame();
}

function chipsRect() { const c = L.chips; const rowH = c.size + (c.labels ? (L.table ? 26 : 18) : 6); return { x: c.x - 4, y: c.y - 4, w: c.w + 8, h: c.rows * rowH + 8 }; }
// ЛИСТАНИЕ СТРАНИЦ ПАЛИТРЫ: порог в пикселях, а не в долях ленты (17.09).
// Палец проходит одно и то же расстояние на любом экране — той же мыслью считается и протяжка
// циновки (ROLL_REACH, #6). 40 px — больше порога «сдвинулся» (6) и меньше половины фишки.
const PAL_SWIPE = 40;
function onDown(x, y, id) {
  sfx.ensure();
  for (const ic of icons) if (inRect(x, y, ic)) { action(ic.id); return; }
  for (const b of buttons) if (inRect(x, y, b)) { action(b.id); return; }
  if (L.scrub && inRect(x, y, L.scrub)) {
    anim = null;
    const p = clamp((x - L.scrub.x) / L.scrub.w);
    S.rollP = p; S.mode = p >= 0.99 ? 'rolled' : 'lay';
    drag.id = id; drag.kind = 'scrub'; drag.x0 = x; drag.y0 = y;
    dirty = true; requestFrame();
    return;
  }
  if (typeof theaterOn === 'function' && theaterOn()) return;
  if (S.mode === 'lay') {
    if (anim) return;
    // Вкладка группы — как кнопка: открывает страницу и НЕ меняет выбранную начинку.
    for (const t of palTabs) if (inRect(x, y, t)) { if (palSet(t.key)) { palDX = 0; layout(); dirty = true; requestFrame(); } return; }
    if (inRect(x, y, chipsRect())) {
      // ⚑ ОДНА ТЯГА — ДВА СМЫСЛА, И РЕШАЕТ ЕГО ЛЕНТА, А НЕ ДОГАДКА. Пока ряд не влезает в
      // полосу (L.chipScroll), тяга ПРОКРУЧИВАЕТ его, как и раньше: иначе жест отнял бы у
      // игрока единственный способ добраться до спрятанных фишек. Когда группа показана целиком
      // и групп больше одной — прокручивать нечего, и та же тяга ЛИСТАЕТ страницы.
      const листаем = !L.chipScroll && uiGroups().length > 1;
      if (L.chipScroll || листаем) {
        drag.id = id; drag.kind = 'chips'; drag.x0 = x; drag.s0 = chipScrollX; drag.moved = false; drag.page = листаем; return;
      }
      // тусклая фишка (кусок не помещается на рис этого листа, #253) не выбирается
      for (const c of chips) if (inRect(x, y, c)) { if (!c.dead) S.sel = c.kind; dirty = true; requestFrame(); return; }
      return;
    }
    const s = L.sheet;
    if (inRect(x, y, L.handle) || (S.rollP > 0 && inRect(x, y, s))) { drag.id = id; drag.kind = 'roll'; drag.x0 = x; drag.y0 = y; drag.p0 = S.rollP; drag.lastX = x; drag.lastY = y; drag.lastT = performance.now(); drag.samples = []; drag.moveT = drag.lastT; drag.sampT = drag.lastT; sfx.rustleStart(); return; }
    if (inRect(x, y, s)) {
      const p = hitPatch(x, y);
      drag.id = id; drag.x0 = x; drag.y0 = y; drag.moved = false;
      if (p && p.kind === S.sel) { drag.kind = 'move'; drag.patch = p; const uv = sheetUV(x, y); drag.ou = p.u - uv.u; drag.ov = p.v - uv.v; }
      else drag.kind = 'place';
      dirty = true; requestFrame();
    }
    return;
  }
  if (S.mode === 'rolled') {
    const { R, len } = rollDims();
    if (Math.abs(y - L.roll.y) < R + 40 && Math.abs(x - L.roll.x) < len / 2 + 24) {
      const v = clamp((x - (L.roll.x - len / 2)) / len);
      const snapped = clamp(Math.round(v * npieces()), 1, npieces() - 1) / npieces();
      startCut(snapped, { held: true, fingerY: y, bladeY: L.roll.y - R - R * 2.2 });
      drag.id = id; drag.kind = 'cut'; drag.x0 = x; drag.y0 = y; drag.moved = false;
      requestFrame();
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
    for (let i = 0; i < npieces(); i++) { const g = L.grid[i]; if (Math.hypot(x - g.x, y - g.y) < g.size / 2) { S.bigPiece = i; dirty = true; requestFrame(); return; } }
  }
}
function onMove(x, y, id) {
  if (drag.id !== id || !drag.kind) return;
  if (drag.kind === 'chips') {
    drag.moved = drag.moved || Math.abs(x - drag.x0) > 6;
    // Страница идёт за пальцем, но не дальше полуторного порога: это ответ на жест, а не
    // прокрутка, и уезжать ленте некуда — соседняя группа появится сразу целиком.
    if (drag.page) palDX = clamp(x - drag.x0, -1.5 * PAL_SWIPE, 1.5 * PAL_SWIPE);
    else chipScrollX = drag.s0 - (x - drag.x0);
  } else if (drag.kind === 'albumscroll') {
    drag.moved = drag.moved || Math.abs(y - drag.y0) > 6;
    S.albumScroll = drag.s0 - (y - drag.y0);
  } else if (drag.kind === 'roll') {
    const now = performance.now();
    // Тяга и её скорость меряются ВДОЛЬ ОСИ СКРУТКИ: по вертикали, пока лист лежит осью u вверх,
    // по горизонтали — когда повёрнут (#23); знак горизонтали задаёт сторона u = 0 (SHEET_U0).
    // Чинить прогресс и скорость можно только ПАРОЙ: замер по новой оси при старом vRef молча
    // перекосил бы «почерк» — v упирается в потолок, air залипает, и все роллы выходят одинаковыми.
    const dPull = L.sheet.uAxis !== 'x' ? (drag.y0 - y) : (SHEET_U0 === 'left' ? x - drag.x0 : drag.x0 - x);
    S.rollP = clamp(drag.p0 + dPull / ROLL_REACH);            // #6: в css-px, а не в долях листа
    const dStep = L.sheet.uAxis !== 'x' ? Math.abs(y - drag.lastY) : Math.abs(x - drag.lastX);
    const speed = dStep / Math.max(1, now - drag.lastT); drag.lastX = x; drag.lastY = y; drag.lastT = now;
    if (drag.samples && now - drag.sampT >= 8) { drag.samples.push(speed); drag.sampT = now; if (drag.samples.length > 240) drag.samples.shift(); }
    if (speed > 0.05) drag.moveT = now;
    sfx.rustle(speed * 1.5);
  } else if (drag.kind === 'move') {
    const uv = sheetUV(x, y), bb = bounds(drag.patch), hv = (bb.v1 - bb.v0) / 2;
    const wasMoved = drag.moved;
    drag.moved = drag.moved || Math.hypot(x - drag.x0, y - drag.y0) > 6;
    if (!drag.moved) return;
    // Снимок кладём на ПЕРВОМ реальном сдвиге, а не при касании: тап по куску — это выделение,
    // и засорять им историю нельзя. Дальше кадры сдвига идут уже без снимков, поэтому «Отменить»
    // возвращает кусок туда, где он лежал ДО перетаскивания, а не на предыдущий кадр (issue #84).
    if (!wasMoved) pushHistory();
    // ⚑ ПО u КУСОК УПИРАЕТСЯ В КРОМКУ РИСА, А НЕ В КРАЙ ЛИСТА (#253, 17.09). Упор плавный: кусок
    // идёт за пальцем, пока может, стоит у кромки, пока палец над голой полосой, и едет обратно
    // вместе с пальцем — смещение пальца от куска не теряется. Пропадает он, как и раньше,
    // только если палец увели за лист (drag.outside ниже).
    drag.patch.u = layU(drag.patch, uv.u + drag.ou);
    drag.patch.v = clamp(uv.v + drag.ov, Math.min(0.5, hv), Math.max(0.5, 1 - hv));
    drag.outside = !inRect(x, y, { x: L.sheet.x - 24, y: L.sheet.y - 24, w: L.sheet.w + 48, h: L.sheet.h + 48 });
    touchModel();
  } else if (drag.kind === 'scrub' && L.scrub) {
    const p = clamp((x - L.scrub.x) / L.scrub.w);
    S.rollP = p; S.mode = p >= 0.99 ? 'rolled' : 'lay';
    anim = null;
  } else if (drag.kind === 'cut') {
    drag.moved = drag.moved || Math.abs(y - drag.y0) > 4;
    if (cut) { cut.held = true; cut.fingerY = y; }
  } else if (drag.kind === 'place') {
    drag.moved = drag.moved || Math.hypot(x - drag.x0, y - drag.y0) > 10;
  }
  dirty = true; requestFrame();
}
// ⚑ ЖЕСТ МЕРЯЕТСЯ В CSS-ПИКСЕЛЯХ, А НЕ В ДОЛЯХ ЛИСТА (#6, правка 01.09).
//
// Длина протяжки и опорная скорость брались от `L.sheet.lenU` — размера листа НА ЭКРАНЕ.
// Лист крупнее на планшете, значит один и тот же взмах пальца читался там иначе. Замер
// синтетической протяжкой (восемь шагов по 26 css-px через 12 мс) на шести размерах:
//
//   390×844   v 3,00  прогресс 0,618        1024×1366  v 1,20  прогресс 0,227
//   844×390   v 3,00  прогресс 0,948        1180×820   v 2,02  прогресс 0,380
//   1024×768  v 2,22  прогресс 0,418        1440×900   v 1,78  прогресс 0,334
//
// Разброс скорости 1,80 — это ВЕСЬ диапазон от «медленной тяги» до «быстрой». Один и тот же
// жест давал разный ролл в зависимости от того, на чём играют.
//
// Палец проходит одно и то же физическое расстояние независимо от экрана, а css-пиксель
// привязан к физическому размеру (номинально 1/96 дюйма) — значит опора должна быть в них.
//
// ⚠ ЧИСЛА ВЗЯТЫ ТАК, ЧТОБЫ ТЕЛЕФОН НЕ ИЗМЕНИЛСЯ. Правку уже писали однажды и откатили,
// потому что она сдвигала отклик телефона: один рывок давал 30,0 мм до и 27,98 после.
// Здесь опора равна нынешнему значению на 390×844 (lenU 395,7): ROLL_REACH = 395,7 × 0,85,
// HAND_REF = 395,7 / 600. На телефоне поведение прежнее до знака, меняются только планшеты.
const ROLL_REACH = 336;        // css-px протяжки на полный оборот (395,7 × 0,85)
const HAND_REF   = 0.66;       // css-px/мс — спокойная тяга (395,7 / 600)
// Почерк из жеста: средняя скорость тяги, её неровность и удержание в конце.
// Всё считается из того, что сделала рука, — никакого Math.random, поэтому «стиль», а не лотерея.
function measureHand() {
  const sm = drag.samples; if (!sm || sm.length < 5) return;
  const use = sm.filter(v => v > 0.02).sort((a, b) => a - b); if (use.length < 5) return;
  const q = f => use[clamp(Math.round(f * (use.length - 1)), 0, use.length - 1)];
  const med = q(0.5), spread = (q(0.75) - q(0.25)) / Math.max(med, 1e-3);   // медиана и межквартильный разброс — устойчивы к выбросам
  const vRef = HAND_REF;                                          // #6: спокойная тяга в css-px/мс, от экрана не зависит
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
    // Тап (не сдвинулся) — выбор начинки; протяжка на полный порог — соседняя группа.
    // Порог не взят — страница возвращается на место, выбор при этом не меняется НИ В ОДНОМ
    // из двух случаев: листание показывает другие начинки, а не выбирает их.
    if (!drag.moved) { for (const c of chips) if (inRect(x, y, c)) { if (!c.dead) S.sel = c.kind; break; } }
    else if (drag.page && Math.abs(x - drag.x0) >= PAL_SWIPE) { if (palStep(x - drag.x0 < 0 ? 1 : -1)) layout(); }
    palDX = 0; drag.page = false;
  } else if (kind === 'roll') {
    sfx.rustleStop();
    measureHand();
    if (S.rollP >= 0.5) tween(S.rollP, 1, 380, v => { S.rollP = v; }, () => { S.mode = 'rolled'; S.rollP = 0; dirty = true; });
    else tween(S.rollP, 0, 260, v => { S.rollP = v; });
  } else if (kind === 'move') {
    const p = drag.patch; drag.patch = null;
    if (!drag.moved) { S.selPatch = S.selPatch === p ? null : p; }
    else { if (drag.outside) { const l = patches(); l.splice(l.indexOf(p), 1); S.selPatch = null; } touchModel(); if (!drag.outside) tubePeekRoll(); }
    drag.outside = false;
  } else if (kind === 'cut') {
    if (cut) {
      cut.held = false;
      if (cut.phase === 'drive') cut.bladeVy = Math.max(cut.bladeVy, 1100);
    }
  } else if (kind === 'place') {
    // Кусок шире всей грядки не ложится (#253). Через палитру такой выбор не попадает: фишка
    // тусклая, а выбранная уходит на доступную при смене листа (selOnRice). Если он всё же пришёл
    // в обход (код, консоль), касание не молчит: выбор уходит на доступную фишку, и кладётся она.
    if (!drag.moved) {
      selOnRice();
      if (chipFits(S.sel)) { const uv = sheetUV(x, y); pushHistory(); placeAt(uv.u, uv.v); tubePeekRoll(); }
    }
  }
  dirty = true; requestFrame();
}

