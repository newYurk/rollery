import {
  makeCucumberRecipe,
  makeF01Recipe,
  makeF02Recipe,
  makeF04bRecipe,
  makeF05Recipe,
  makeF07Recipe,
} from './recipe.js';
import { validateRecipe } from './validate.js';
import { buildWinding } from './winding.js';
import { sampleSection } from './section.js';
import { drawSheet, drawSlice } from './render.js';
import { placementWindowMm } from './units.js';

const FIXTURES = [
  { id: 'F01', label: 'Пустой', make: () => makeF01Recipe() },
  { id: 'F02', label: 'Каппамаки', make: () => makeF02Recipe() },
  { id: 'F03', label: 'Раскладка', make: (u) => makeCucumberRecipe(u ?? 36.25), slider: { min: 20, max: 55, step: 0.5, value: 36.25, unit: 'u мм' } },
  { id: 'F05', label: 'Футомаки', make: () => makeF05Recipe() },
  { id: 'F07', label: 'Зонд', make: (u) => makeF07Recipe(u ?? 56), slider: { min: 56, max: 64, step: 1, value: 56, unit: 'зонд u мм' } },
  { id: 'F04b', label: 'Отказ', make: () => makeF04bRecipe() },
];

const chips = document.getElementById('chips');
const meta = document.getElementById('meta');
const sliderWrap = document.getElementById('sliderWrap');
const slider = document.getElementById('slider');
const sliderLabel = document.getElementById('sliderLabel');
const slice = document.getElementById('slice');
const sheet = document.getElementById('sheet');
const refuse = document.getElementById('refuse');
const sctx = slice.getContext('2d');
const hctx = sheet.getContext('2d');

let current = FIXTURES[1];
let sliderVal = current.slider ? current.slider.value : 0;

function paint() {
  const recipe = current.make(sliderVal);
  const v = validateRecipe(recipe);
  const window = placementWindowMm(recipe.sheet);

  chips.querySelectorAll('button').forEach((b) => {
    b.setAttribute('aria-pressed', b.dataset.id === current.id ? 'true' : 'false');
  });

  if (current.slider) {
    sliderWrap.hidden = false;
    slider.min = current.slider.min;
    slider.max = current.slider.max;
    slider.step = current.slider.step;
    slider.value = String(sliderVal);
    sliderLabel.textContent = `${current.slider.unit}: ${Number(sliderVal).toFixed(1)}`;
  } else {
    sliderWrap.hidden = true;
  }

  const d0 = v.diagnostics[0];
  const lines = [
    `<span><b>${current.id}</b> · ${recipe.baseId} · лист ${recipe.sheet.lengthMm} мм</span>`,
    `<span>окно ${window.nearEdgeMm}–${window.farEdgeMm} мм · патчей ${recipe.patches.length}</span>`,
  ];
  if (v.status === 'valid') {
    const winding = buildWinding(recipe);
    sampleSection(recipe, winding, recipe.sheet.widthMm / 2);
    drawSlice(sctx, recipe, winding, slice.width);
    drawSheet(hctx, recipe, winding, sheet.width, sheet.height);
    slice.hidden = false;
    sheet.hidden = false;
    refuse.hidden = true;
    const dia = ((winding.diameterMinMm + winding.diameterMaxMm) / 2).toFixed(1);
    lines.push(`<span class="ok">valid · ⌀ ${dia} мм · ядро ${winding.Wc.toFixed(1)}×${winding.Hc.toFixed(1)} · нахлёст ${winding.Lbare.toFixed(1)} мм</span>`);
  } else {
    sctx.fillStyle = '#171713';
    sctx.fillRect(0, 0, slice.width, slice.height);
    slice.hidden = true;
    sheet.hidden = true;
    refuse.hidden = false;
    const msg = d0?.code === 'closure_window'
      ? 'След начинки вне окна раскладки.\nИдеальный ролл не рисуем.'
      : d0?.code === 'patch_out_of_sheet'
        ? 'След начинки уходит за край листа.'
        : (d0?.message || v.status);
    refuse.textContent = msg;
    lines.push(`<span class="no">${v.status}${d0?.code ? ': ' + d0.code : ''}</span>`);
  }
  meta.innerHTML = lines.join('');
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
    sliderVal = f.slider ? f.slider.value : 0;
    paint();
  });
  chips.append(b);
}

slider.addEventListener('input', () => {
  sliderVal = Number(slider.value);
  paint();
});

paint();
