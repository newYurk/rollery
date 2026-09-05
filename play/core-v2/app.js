import { deepClone, makeCucumberRecipe, makeF01Recipe, makeF02Recipe, makeF05Recipe, makeHosogiriRecipe } from './recipe.js';
import { validateRecipe, assessWinding } from './validate.js';
import { buildWinding } from './winding.js';
import { drawBar, drawSlice, rollRadiusPx, rollSideLayout, sheetGeom, sheetShare } from './render.js';
import { clampPatchU, placementWindowMm } from './units.js';
import {
  cutFractions,
  firstCutFraction,
  pieceCountOf,
  pieceLeftOfCut,
  pieceLengthMm,
  snapCutFraction,
  vSliceMm,
} from './knife.js';

const FIXTURES = [
  { id: 'F01', label: 'Пустой', make: () => makeF01Recipe() },
  { id: 'F02', label: 'Каппамаки', make: () => makeF02Recipe() },
  { id: 'hogi', label: '細切り', make: () => makeHosogiriRecipe() },
  { id: 'F03', label: 'Раскладка', make: () => makeCucumberRecipe(36.25) },
  { id: 'F05', label: 'Футомаки', make: () => makeF05Recipe() },
];

function fixtureFromUrl() {
  const q = new URLSearchParams(location.search);
  const id = q.get('f') || q.get('v2');
  if (!id || id === '1' || id === 'true') return FIXTURES[1];
  const aliases = { empty: 'F01', kappa: 'F02', hosogiri: 'hogi' };
  const want = aliases[id] || id;
  return FIXTURES.find((x) => x.id === want) || FIXTURES[1];
}

const chips = document.getElementById('chips');
const meta = document.getElementById('meta');
const slice = document.getElementById('slice');
const bar = document.getElementById('bar');
const refuse = document.getElementById('refuse');
const sctx = slice.getContext('2d');
const bctx = bar.getContext('2d');

let current = fixtureFromUrl();
let vFrac = 0.5;
let lastRecipe = null;
let lastWinding = null;
let knifeAnim = null;
let patchU = {};

function resetKnife(recipe) {
  vFrac = firstCutFraction(pieceCountOf(recipe));
}

function rollH() {
  return bar.height - sheetShare(bar.height);
}

function recipeNow() {
  const base = current.make();
  if (!base.patches?.length) return base;
  const r = deepClone(base);
  for (const p of r.patches) {
    if (patchU[p.id] != null) p.uMm = patchU[p.id];
  }
  return r;
}

function paint() {
  const recipe = recipeNow();
  const v = validateRecipe(recipe);
  const window = placementWindowMm(recipe.sheet);
  lastRecipe = recipe;
  lastWinding = null;

  chips.querySelectorAll('[data-id]').forEach((b) => {
    b.setAttribute('aria-pressed', b.dataset.id === current.id ? 'true' : 'false');
  });

  const d0 = v.diagnostics[0];
  if (v.status === 'valid') {
    const winding = buildWinding(recipe);
    const phys = assessWinding(recipe, winding);
    if (phys.status !== 'valid') {
      const d = phys.diagnostics[0];
      sctx.fillStyle = '#171713';
      sctx.fillRect(0, 0, slice.width, slice.height);
      slice.hidden = true;
      bar.hidden = true;
      refuse.hidden = false;
      cutBtn.disabled = true;
      refuse.textContent = d?.code === 'sheet_too_short'
        ? 'Листа не хватает на кольцо нори. Идеальный ролл не рисуем.'
        : d?.code === 'chef_corridor'
          ? 'Диаметр вне коридора хосомаки 28–32 мм.'
          : (d?.message || phys.status);
      meta.innerHTML = `<b>${current.id}</b> · <span class="no">${phys.status}${d?.code ? ': ' + d.code : ''}</span>`;
      return;
    }
    lastWinding = winding;
    const n = pieceCountOf(recipe);
    vFrac = snapCutFraction(vFrac, n);
    drawSlice(sctx, recipe, winding, slice.width);
    drawBarNow(recipe, winding, n);
    slice.hidden = false;
    bar.hidden = false;
    refuse.hidden = true;
    cutBtn.disabled = false;
    const dia = ((winding.diameterMinMm + winding.diameterMaxMm) / 2).toFixed(1);
    const plen = pieceLengthMm(recipe).toFixed(1).replace('.', ',');
    const left = pieceLeftOfCut(vFrac, n);
    meta.innerHTML = `<b>${current.id}</b> · ⌀ ${dia} · ${n}×${plen} мм · рез ${left}/${n} · окно ${window.nearEdgeMm}–${window.farEdgeMm}`;
  } else {
    sctx.fillStyle = '#171713';
    sctx.fillRect(0, 0, slice.width, slice.height);
    slice.hidden = true;
    bar.hidden = true;
    refuse.hidden = false;
    cutBtn.disabled = true;
    refuse.textContent = d0?.code === 'closure_window'
      ? 'След начинки вне окна раскладки. Идеальный ролл не рисуем.'
      : d0?.code === 'patch_out_of_sheet'
        ? 'След начинки уходит за край листа.'
        : (d0?.message || v.status);
    meta.innerHTML = `<b>${current.id}</b> · <span class="no">${v.status}${d0?.code ? ': ' + d0.code : ''}</span>`;
  }
}

function drawBarNow(recipe, winding, n, knifeY) {
  drawBar(bctx, recipe, winding, bar.width, bar.height, cutFractions(n), vFrac, knifeY);
}

function barPointer(ev) {
  const rect = bar.getBoundingClientRect();
  return {
    x: (ev.clientX - rect.left) * (bar.width / rect.width),
    y: (ev.clientY - rect.top) * (bar.height / rect.height),
  };
}

function vFromPointer(ev) {
  const { x } = barPointer(ev);
  const { x0, innerW } = rollSideLayout(bar.width, rollH());
  return Math.min(1, Math.max(0, (x - x0) / innerW));
}

let dragging = false;
let dragPatch = null;
let dragGrab = 0;

bar.addEventListener('pointerdown', (ev) => {
  if (!lastRecipe || !lastWinding) return;
  const { x, y } = barPointer(ev);
  const sheetTop = rollH();
  if (y >= sheetTop) {
    if (lastRecipe.patches.length) {
      const geom = sheetGeom(lastRecipe, lastWinding, bar.width, sheetShare(bar.height));
      const ly = y - sheetTop;
      const hit = [...geom.chips].reverse().find((c) => x >= c.x && x <= c.x + c.w && ly >= c.y && ly <= c.y + c.h);
      if (hit) {
        const p = lastRecipe.patches.find((q) => q.id === hit.id);
        dragPatch = p;
        dragGrab = geom.xToU(x) - p.uMm;
        dragging = true;
        bar.setPointerCapture(ev.pointerId);
      }
    }
    return;
  }
  dragPatch = null;
  dragging = true;
  bar.setPointerCapture(ev.pointerId);
  vFrac = snapCutFraction(vFromPointer(ev), pieceCountOf(lastRecipe));
  paint();
});
bar.addEventListener('pointermove', (ev) => {
  if (!dragging || !lastRecipe) return;
  if (dragPatch) {
    const geom = sheetGeom(lastRecipe, lastWinding, bar.width, sheetShare(bar.height));
    const u = clampPatchU(lastRecipe.sheet, dragPatch, geom.xToU(barPointer(ev).x) - dragGrab);
    patchU = { ...patchU, [dragPatch.id]: u };
    paint();
    return;
  }
  vFrac = snapCutFraction(vFromPointer(ev), pieceCountOf(lastRecipe));
  paint();
});
bar.addEventListener('pointerup', (ev) => {
  dragging = false;
  dragPatch = null;
  try { bar.releasePointerCapture(ev.pointerId); } catch { /* already released */ }
});
bar.addEventListener('pointercancel', (ev) => {
  dragging = false;
  dragPatch = null;
  try { bar.releasePointerCapture(ev.pointerId); } catch { /* already released */ }
});

function easeInOut(t) {
  return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
}

function pullCut() {
  if (!lastRecipe || !lastWinding || knifeAnim) return;
  const n = pieceCountOf(lastRecipe);
  const recipe = lastRecipe;
  const winding = lastWinding;
  const { y0 } = rollSideLayout(bar.width, rollH());
  // Был свой min(18, …) против min(22, …) в render.js: при высоте полосы
  // выше 169 px нож приезжал не туда, куда нарисован ролл.
  const RoutPx = rollRadiusPx(rollH());
  const yTop = y0 - RoutPx - 12;
  const yCut = y0 + RoutPx * 0.9;
  const t0 = performance.now();
  knifeAnim = { t0 };
  cutBtn.disabled = true;

  function frame(now) {
    const t = Math.min(1, (now - t0) / 640);
    drawBarNow(recipe, winding, n, yTop + (yCut - yTop) * easeInOut(t));
    if (t < 1) requestAnimationFrame(frame);
    else {
      knifeAnim = null;
      cutBtn.disabled = false;
      paint();
    }
  }
  requestAnimationFrame(frame);
}

for (const f of FIXTURES) {
  const b = document.createElement('button');
  b.className = 'chip';
  b.type = 'button';
  b.dataset.id = f.id;
  b.textContent = f.label;
  b.setAttribute('aria-pressed', f.id === current.id ? 'true' : 'false');
  b.addEventListener('click', () => {
    current = f;
    patchU = {};
    const recipe = recipeNow();
    if (validateRecipe(recipe).status === 'valid') resetKnife(recipe);
    paint();
  });
  chips.append(b);
}

const cutBtn = document.createElement('button');
cutBtn.className = 'cut';
cutBtn.type = 'button';
cutBtn.textContent = 'Нарезать';
cutBtn.addEventListener('click', pullCut);
chips.append(cutBtn);

resetKnife(current.make());
paint();
