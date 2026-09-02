'use strict';
// АЛЬБОМ: сохранённые роллы. Хранится РЕЦЕПТ (база, раскладка, форма, почерк), а не картинка,
// поэтому запись можно открыть «на лист», доложить начинку и скрутить заново.
//
// ⚠ Обёртка в рецепт пока НЕ входит — issue #86: сохранил в блине, откроешь в нори.

// ---------------------------------------------------------------- альбом
// Храним не картинки, а рецепт: база, лист, почерк, форма. Срезы пересчитываются — это дёшево
// и позволяет открыть свой старый ролл, доложить начинку и скрутить заново.
const ALBUM_MAX = 60;
function albumSave() {
  const list = patches(); if (!list.length) return;
  const h = S.hand || {};
  // ⚠ wrap ОБЯЗАН быть в записи: обёртка входит в шаг витка (T + w), а с ним в число оборотов
  // и диаметр — блин 2 мм против нори 0,1 мм даёт у футомаки 62,4 против 58,7 мм (замер fixture
  // F03). Без неё запись с блином открывалась как нори, молча и без ошибки (issue #86).
  // Пишем разрешённую обёртку базы, а не сырое S.wrap: у баз с wrapFixed (рулет) своя, и
  // S.wrap там не участвует — иначе в записи оказалось бы то, чего в модели не было.
  const e = { id: 'a' + Date.now().toString(36), base: S.base, wrap: B().wrapKey || null,
              turns: turnsOf(S.turns), shape: S.shape,
              hand: { air: +(h.air || 0).toFixed(3), wobble: +(h.wobble || 0).toFixed(3), phase: +(h.phase || 0).toFixed(2), press: +(h.press || 1).toFixed(2) },
              list: JSON.parse(JSON.stringify(list)), at: Date.now(),
              level: S.puzzle ? S.puzzle.level : null, sim: S.puzzle && S.puzzle.result ? Math.round(S.puzzle.result.sim * 100) : null };
  S.album.unshift(e); if (S.album.length > ALBUM_MAX) S.album.length = ALBUM_MAX;
  try { localStorage.setItem('rollery.album', JSON.stringify(S.album)); } catch (err) { S.album.length = Math.min(S.album.length, 30); }
  S.saved = performance.now() + 1600; dirty = true; sfx.place();
}
function albumRemove(i) {
  S.album.splice(i, 1); S.albumOpen = -1;
  try { localStorage.setItem('rollery.album', JSON.stringify(S.album)); } catch (err) {}
  dirty = true;
}
// Отрисовать чужой рецепт: временно подменяем состояние, считаем модель, возвращаем всё назад.
function withRecipe(e, fn) {
  // S.wrap снимается и ВОЗВРАЩАЕТСЯ наравне с остальным: без этого просмотр альбома менял
  // обёртку в текущей сессии — открыл миниатюру записи на блине, вернулся к своему роллу,
  // а он уже на блине (issue #86).
  const keep = { base: S.base, wrap: S.wrap, turns: S.turns, shape: S.shape, hand: S.hand, list: S.lists[e.base] };
  S.base = e.base; S.wrap = (e.wrap && WRAPPERS[e.wrap]) ? e.wrap : null;
  S.turns = turnsOf(e.turns); S.shape = SHAPES[e.shape] ? e.shape : 'round';
  S.hand = Object.assign(handOf(), e.hand || {});
  let out;
  try { out = fn(buildModel(JSON.parse(JSON.stringify(e.list)))); }
  finally { S.base = keep.base; S.wrap = keep.wrap; S.turns = keep.turns; S.shape = keep.shape; S.hand = keep.hand; S.lists[e.base] = keep.list; }
  return out;
}
function albumFace(e, size, v) { return withRecipe(e, m => face(v == null ? 0.5 : v, size, m)); }
function albumLoad(i) {
  const e = S.album[i]; if (!e) return;
  if (S.puzzle) puzzleStop();
  S.base = e.base; S.wrap = (e.wrap && WRAPPERS[e.wrap]) ? e.wrap : null;   // старые записи без поля → обёртка базы (issue #86)
  S.turns = turnsOf(e.turns); S.shape = SHAPES[e.shape] ? e.shape : 'round';
  S.hand = Object.assign(handOf(), e.hand || {});
  S.sel = uiIngredients()[0] || B().ingredients[0]; S.selPatch = null;
  // ⚠ ФИЛЬТР ПО KIND, КАК ПРИ ЗАГРУЗКЕ СОХРАНЁННОГО (#150). Альбом хранит рецепты и открывает
  // их СЕГОДНЯШНЕЙ моделью, а начинки со временем снимают: pepper, pinkcream и choco уже сняты.
  // `load()` в state.js такие отсеивает, а этот путь клал список как есть — и запись со снятой
  // начинкой валила не плитку, а саму игру.
  S.lists[e.base] = JSON.parse(JSON.stringify(e.list)).filter(p => ING[p.kind]);
  histReset();                                   // #150: пришла другая раскладка — прошлого нет
  S.albumOpen = -1; S.mode = 'lay'; S.rollP = 0; anim = null; cut = null; slicing = null;
  touchModel(); layout(); dirty = true; requestFrame();
}
function albumShare(i) {
  const e = S.album[i]; if (!e) return;
  withRecipe(e, () => { const url = encodePuzzle(e.list, e.turns); if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).catch(() => { location.hash = url.slice(url.indexOf('#')); }); else location.hash = url.slice(url.indexOf('#')); });
  shareNote = performance.now() + 2200; dirty = true; requestFrame();
}
function albumDate(t) {
  const d = new Date(t), n = new Date();
  const sameDay = d.toDateString() === n.toDateString();
  const hh = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  return sameDay ? hh : String(d.getDate()).padStart(2, '0') + '.' + String(d.getMonth() + 1).padStart(2, '0') + ' ' + hh;
}
function drawAlbum() {
  const cw = L.cw, ox = L.ox, top = L.top + 8;
  if (!S.album.length) {
    ctx.fillStyle = '#8d846f'; ctx.font = font(15); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('Альбом пуст', ox + cw / 2, top + 90);
    ctx.font = font(13); ctx.fillStyle = '#6f6754';
    ctx.fillText('Скрути ролл, разрежь — и нажми «В альбом».', ox + cw / 2, top + 118);
    ctx.fillText('Роллы хранятся рецептом: можно открыть, доложить начинку и скрутить заново.', ox + cw / 2, top + 138);
    buttons = []; buttonRow([['back', '← К листу', true]]);
    drawButtons(); drawTopBar('Альбом');
    return;
  }
  const per = Math.max(2, Math.min(5, Math.floor((cw - 24) / 150)));
  const cell = Math.floor((cw - 24 - (per - 1) * 12) / per), rowH = cell + 26;
  const rows = Math.ceil(S.album.length / per);
  const viewH = L.rowBtn.y - 12 - top;
  const maxScroll = Math.max(0, rows * rowH - viewH);
  S.albumScroll = clamp(S.albumScroll, 0, maxScroll);
  albumCells = [];
  ctx.save(); ctx.beginPath(); ctx.rect(ox, top - 4, cw, viewH + 8); ctx.clip();
  S.album.forEach((e, i) => {
    const r = Math.floor(i / per), c = i % per;
    const x = ox + 12 + c * (cell + 12), y = top + r * rowH - S.albumScroll;
    if (y > top + viewH || y + rowH < top - rowH) return;
    albumCells.push({ i, x, y, w: cell, h: cell });
    const bp = Math.max(5, Math.round(cell * 0.07)), cfs = cell - 2 * bp;
    drawMat(x, y, cell, cell, 12, BASES[e.base] || B());
    try { drawFaceImg(albumFace(e, cfs), x + cell / 2, y + cell / 2, cfs); } catch (err) {}
    ctx.fillStyle = '#6f6754'; ctx.font = font(11); ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    const tag = (BASES[e.base] ? BASES[e.base].emoji : '') + ' ' + albumDate(e.at) + (e.sim != null ? ' · ' + e.sim + ' %' : '');
    ctx.fillText(tag, x + cell / 2, y + cell + 5);
  });
  ctx.restore();
  if (maxScroll > 0) {
    const th = Math.max(30, viewH * viewH / (rows * rowH)), ty = top + (viewH - th) * (S.albumScroll / maxScroll);
    ctx.fillStyle = 'rgba(243,231,202,0.18)'; rr(ox + cw - 6, ty, 3, th, 2); ctx.fill();
  }
  buttons = []; buttonRow([['back', '← К листу', true], ['albumclear', 'Очистить альбом']]);
  drawButtons(); drawTopBar(`Альбом · ${S.album.length}`);
  if (S.albumOpen >= 0 && S.album[S.albumOpen]) {
    const e = S.album[S.albumOpen];
    ctx.fillStyle = 'rgba(23,23,19,0.93)'; ctx.fillRect(0, 0, W, H);
    // Число кусков — у базы САМОЙ ЗАПИСИ, а не текущей: футомаки режется на восемь, хосомаки
    // на шесть, и запись помнит, чем была (#134-side, правка 01.09).
    const eb0 = BASES[e.base] || B(), k = eb0.pieces || 6;
    const fs = Math.min((cw - 40 - (k - 1) * 8) / k, 0.22 * L.ch, 120);
    const cx = ox + cw / 2, y0 = L.top + 40;
    ctx.fillStyle = '#b8ad95'; ctx.font = font(13); ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
    ctx.fillText(`${BASES[e.base] ? BASES[e.base].name : e.base} · ${albumDate(e.at)}${e.sim != null ? ' · совпало на ' + e.sim + ' %' : ''}`, cx, y0 - 12);
    const x0 = cx - ((k - 1) * (fs + 8)) / 2, eb = eb0;
    drawSlab(Array.from({ length: k }, (_, i) => ({ x: x0 + i * (fs + 8), y: y0 + fs / 2, size: fs })), 1, eb, k);
    for (let i = 0; i < k; i++) { try { drawFaceImg(albumFace(e, fs, pieceV(i, k)), x0 + i * (fs + 8), y0 + fs / 2, fs); } catch (err) {} }
    const big = Math.min(0.5 * cw, 0.42 * L.ch, 300);
    drawSlab([{ x: cx, y: y0 + fs + 24 + big / 2, size: big }], 1, eb, 8);
    try { drawFaceImg(albumFace(e, big), cx, y0 + fs + 24 + big / 2, big); } catch (err) {}
    const hl = e.hand && (e.hand.air || e.hand.wobble || e.hand.press !== 1) ? handLabelOf(e.hand) : '';
    if (hl) { ctx.fillStyle = '#6f6754'; ctx.font = font(12); ctx.textBaseline = 'top'; ctx.fillText(hl, cx, y0 + fs + 24 + big + 12); }
    buttons = []; buttonRow([['albumopen_load', 'На лист', true], ['albumopen_share', '🔗 Ссылка'], ['albumopen_del', 'Убрать']]);
    drawButtons();
    ctx.fillStyle = '#6f6754'; ctx.font = font(12); ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
    ctx.fillText('тап по фону — закрыть', ox + cw / 2, L.rowBtn.y - 14);
  }
}
let albumCells = [];

