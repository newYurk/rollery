'use strict';
let rafId = 0, lastNow = 0;
function frame(now) {
  rafId = 0; lastNow = now; dirty = false; icons = [];
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.fillStyle = tubePlay() ? '#2a2e2c' : '#171713'; ctx.fillRect(0, 0, W, H);
  let animating = false;
  switch (S.mode) {
    case 'lay': drawLay(); animating = !!anim; break;
    case 'rolled': drawRolled(); break;
    case 'cut': drawCut(now); animating = S.mode === 'cut'; break;
    case 'revealed': drawRevealed(); break;
    case 'slicing': drawSlicing(now); animating = S.mode === 'slicing'; break;
    case 'plate': drawPlate(); break;
    case 'album': drawAlbum(); break;
  }
  if (anim) { animating = true; anim(now); }
  if (particles.length || shakeUntil > now) animating = true;
  if (animating || dirty) requestFrame();
}
function requestFrame() { if (!rafId) rafId = requestAnimationFrame(frame); }
let anim = null;
function tween(from, to, dur, apply, done) {
  const t0 = performance.now();
  anim = now => { const t = easeOutCubic(clamp((now - t0) / dur)); apply(lerp(from, to, t)); if (t >= 1) { anim = null; if (done) done(); } dirty = true; };
  requestFrame();
}
const drag = { id: null, kind: null, x0: 0, y0: 0, patch: null, ou: 0, ov: 0, moved: false, p0: 0, lastX: 0, lastY: 0, lastT: 0 };
const inRect = (x, y, r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h;
function sheetUV(x, y) { const q = toSheet(x, y), s = SB(); return { u: 1 - (q.y - s.y) / s.h, v: (q.x - s.x) / s.w }; }
function hitPatch(x, y) {
  const q = toSheet(x, y); x = q.x; y = q.y;
  const list = patches();
  for (let i = list.length - 1; i >= 0; i--) {
    const p = list[i], d = ING[p.kind];
    if (p.rot) { const t = patchScreen(p), dx = x - t.cx, dy = y - t.cy, c = Math.cos(t.ang), sn = Math.sin(t.ang); const ax = dx * c + dy * sn, ay = -dx * sn + dy * c; if (Math.abs(ax) <= t.lenPx / 2 + HIT_PAD && Math.abs(ay) <= t.wPx / 2 + HIT_PAD) return p; continue; }
    const r = patchRect(p);
    if (d.wave) { r.y -= d.wave.amp * SB().h; r.h += 2 * d.wave.amp * SB().h; }
    const pad = HIT_PAD; if (x >= r.x - pad && x <= r.x + r.w + pad && y >= r.y - pad && y <= r.y + r.h + pad) return p;
  }
  return null;
}
function placeAt(u, v) {
  const m = dims({ kind: S.sel });
  const p = { kind: S.sel, u, v: clamp(v, m.dv / 2, 1 - m.dv / 2), z0: 0, z1: m.h, phase: Math.random() * TAU };
  if (!layFits(p)) return false;
  p.u = layU(p, u);
  patches().push(p); S.selPatch = null; touchModel(); sfx.place();
  return true;
}
function wrapInNoriList(F, list) {
  if (list.indexOf(F) < 0) return;
  F.noriWrap = true;
}
function wrapInNori(F) { wrapInNoriList(F, patches()); S.selPatch = null; touchModel(); sfx.place(); }

canvas.addEventListener('pointerdown', e => { e.preventDefault(); if (drag.id !== null && drag.id !== e.pointerId) return; canvas.setPointerCapture(e.pointerId); onDown(e.clientX, e.clientY, e.pointerId); });
canvas.addEventListener('pointermove', e => { e.preventDefault(); onMove(e.clientX, e.clientY, e.pointerId); });
canvas.addEventListener('pointerup', e => { e.preventDefault(); onUp(e.clientX, e.clientY, e.pointerId); });
canvas.addEventListener('pointercancel', e => { onUp(e.clientX, e.clientY, e.pointerId); });
window.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z') { e.preventDefault(); action(e.shiftKey ? 'redo' : 'undo'); }
  else if (e.key === 'Backspace') action('undo');
  else if (e.key === 'Escape') action('back');
  else if (e.key === 'l' || e.key === 'L' || e.key === 'д' || e.key === 'Д') {
    S.lines = !S.lines; dirty = true; requestFrame();
  }
  else if (e.key === 'Enter') { if (S.mode === 'lay' && !anim) { S.hand = { air: 0, wobble: 0, phase: 0, press: 1, v: 1, cv: 0, hold: 0 }; } if (S.mode === 'lay' && !anim) tween(S.rollP, 1, 500, v => { S.rollP = v; }, () => { S.mode = 'rolled'; S.rollP = 0; dirty = true; }); else if (S.mode === 'rolled') { startCut(0.5); requestFrame(); } else if (S.mode === 'revealed') action('slice'); }
});
window.addEventListener('resize', () => { resize(); requestFrame(); });
if (window.visualViewport) window.visualViewport.addEventListener('resize', () => { resize(); requestFrame(); });
window.addEventListener('pageshow', () => { resize(); requestFrame(); });
setTimeout(() => { resize(); requestFrame(); }, 300); setTimeout(() => { resize(); requestFrame(); }, 1200);
window.addEventListener('orientationchange', () => setTimeout(() => { resize(); requestFrame(); }, 120));

load(); resize(); touchModel(); sfx.armStart();
tubeInstall();
if (S.v2 && S.v2Scenario !== 'layout') { S.mode = 'rolled'; S.base = 'hoso'; }
const linked = decodePuzzle(location.hash);
if (linked) puzzleFromLink(linked); else if (location.search.includes('puzzle')) action('puzzle'); else action('tube');
window.addEventListener('hashchange', () => { const pz = decodePuzzle(location.hash); if (pz) puzzleFromLink(pz); });
requestFrame();
