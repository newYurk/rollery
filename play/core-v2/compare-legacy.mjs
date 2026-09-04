#!/usr/bin/env node
// ADR-001 step 5: compare V2 to live geometry.js on the same F01/F02 inputs.
// Document divergence. Do not fit.

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runF01, runF02, cucumberCatalogAreaMm2 } from './fixtures.js';
import { buildWinding } from './winding.js';
import {
  EPS_AREA_RATIO,
  EPS_CORE_ASYMMETRY_MM,
  EPS_LENGTH_MM,
} from './units.js';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)));
const REPO = path.resolve(ROOT, '../..');

function v2pack(r) {
  const w = r.report;
  const wind = r.winding || buildWinding(r.recipe);
  const p = w.visiblePatches[0] || null;
  return {
    lengthMm: w.sheet.lengthMm,
    sRice0Mm: w.sheet.arcByLayerMm[0].u0Mm,
    sRice1Mm: w.sheet.arcByLayerMm[0].u1Mm,
    overlapMm: w.seam.overlapMm,
    coreWcMm: wind.Wc,
    coreHcMm: wind.Hc,
    diameterMinMm: w.roll.diameterMinMm,
    diameterMaxMm: w.roll.diameterMaxMm,
    riceArcMm: w.sheet.arcByLayerMm[0].arcMm,
    noriArcMm: w.sheet.arcByLayerMm[1].arcMm,
    turns: w.seam.turnsMeasured,
    twoIntersectionCount: w._meta.twoIntersectionCount,
    cucumberAreaMm2: p ? p.areaMm2 : 0,
    cucumberCenterXmm: p ? p.centerXmm : 0,
    cucumberCenterYmm: p ? p.centerYmm : 0,
  };
}

function num(x) { return Number(x); }

const METRICS = [
  { key: 'lengthMm', label: 'длина листа', unit: 'мм', eps: EPS_LENGTH_MM, kind: 'identity' },
  { key: 'sRice0Mm', label: 'рис u0', unit: 'мм', eps: EPS_LENGTH_MM, kind: 'identity' },
  { key: 'sRice1Mm', label: 'рис u1', unit: 'мм', eps: EPS_LENGTH_MM, kind: 'identity' },
  { key: 'overlapMm', label: 'нахлёст Lbare', unit: 'мм', eps: EPS_LENGTH_MM, kind: 'identity' },
  { key: 'coreWcMm', label: 'ядро Wc', unit: 'мм', eps: EPS_CORE_ASYMMETRY_MM, kind: 'identity' },
  { key: 'coreHcMm', label: 'ядро Hc', unit: 'мм', eps: EPS_CORE_ASYMMETRY_MM, kind: 'identity' },
  { key: 'diameterMinMm', label: '⌀ min', unit: 'мм', eps: EPS_LENGTH_MM, kind: 'geometry' },
  { key: 'diameterMaxMm', label: '⌀ max', unit: 'мм', eps: EPS_LENGTH_MM, kind: 'geometry' },
  { key: 'riceArcMm', label: 'дуга риса (пространственная)', unit: 'мм', eps: EPS_LENGTH_MM, kind: 'geometry' },
  { key: 'noriArcMm', label: 'дуга нори (пространственная)', unit: 'мм', eps: EPS_LENGTH_MM, kind: 'geometry' },
  { key: 'turns', label: 'витки нори', unit: '', eps: 0.01, kind: 'geometry' },
  { key: 'twoIntersectionCount', label: 'лучи с двумя слоями нори', unit: '', eps: 8, kind: 'geometry' },
  { key: 'cucumberAreaMm2', label: 'площадь огурца', unit: 'мм²', eps: null, kind: 'filling' },
  { key: 'cucumberCenterXmm', label: 'центр огурца X', unit: 'мм', eps: 0.15, kind: 'filling' },
  { key: 'cucumberCenterYmm', label: 'центр огурца Y', unit: 'мм', eps: 0.15, kind: 'filling' },
];

function row(metric, v2, leg, catalogArea) {
  const a = num(v2[metric.key]);
  const b = num(leg[metric.key]);
  const d = a - b;
  let gate = '—';
  let note = '';
  if (metric.key === 'cucumberAreaMm2') {
    const ratio = catalogArea / Math.max(b, 1e-9);
    gate = ratio <= EPS_AREA_RATIO ? 'MATCH' : 'DIVERGE';
    note = `каталог/legacy = ${ratio.toFixed(3)} (EPS_AREA_RATIO ${EPS_AREA_RATIO})`;
  } else if (metric.eps != null) {
    gate = Math.abs(d) <= metric.eps ? 'MATCH' : 'DIVERGE';
    note = `|Δ| ${Math.abs(d).toFixed(3)} ≷ ${metric.eps}`;
  }
  return { ...metric, v2: a, legacy: b, delta: d, gate, note };
}

const probe = spawnSync(process.execPath, [path.join(ROOT, 'load-legacy.cjs')], {
  encoding: 'utf8',
  cwd: REPO,
});
if (probe.status !== 0) {
  console.error(probe.stderr || probe.stdout);
  process.exit(probe.status || 1);
}
const legacy = JSON.parse(probe.stdout);
const v2 = { F01: v2pack(runF01()), F02: v2pack(runF02()) };
const catalogArea = cucumberCatalogAreaMm2();

const tables = {};
for (const id of ['F01', 'F02']) {
  const keys = id === 'F02' ? METRICS : METRICS.filter((m) => m.kind !== 'filling');
  tables[id] = keys.map((m) => row(m, v2[id], legacy[id], catalogArea));
}

function fmt(n) {
  if (!Number.isFinite(n)) return '—';
  if (Math.abs(n) >= 100) return n.toFixed(2);
  if (Math.abs(n) >= 10) return n.toFixed(3);
  return n.toFixed(4);
}

function mdTable(rows) {
  const lines = [
    '| метрика | V2 | legacy | Δ (V2−legacy) | ворота |',
    '|---|---:|---:|---:|---|',
  ];
  for (const r of rows) {
    lines.push(`| ${r.label} | ${fmt(r.v2)} | ${fmt(r.legacy)} | ${fmt(r.delta)} | ${r.gate} |`);
  }
  return lines.join('\n');
}

const md = `# Расхождение геометрии: Core V2 ↔ live \`geometry.js\`

ADR-001, шаг 5: сравнить на сценариях, где legacy в своей области; расхождение
записать, не подгонять. Снято с \`main\`-кода \`play/model/geometry.js\` и с ядра
ветки \`core-v2/f01-f02\`. Одни входы.

Прогон: \`node play/core-v2/compare-legacy.mjs\`.

## Входы

| | V2 | legacy |
|---|---|---|
| F01 | пустой хосомаки, \`neutralHand\`, \`fromUZero\` | \`S.base='hoso'\`, \`list=[]\`, \`handOf()\` |
| F02 | огурец \`uMm=36.25\` (центр окна) | \`kind:'cucumber', u:36.25/105, v:0.5\` |
| лист | 105 × 190 мм | \`g.L × U_MM\`, \`U_MM=5\` |
| рука | только neutral | \`handOf()\` — нули |

Legacy внутри считает в единицах каталога. Все числа ниже уже в мм
(\`× U_MM\` ровно один раз, в \`legacy-probe.js\`).

## Какие метрики и зачем

Три слоя. Смешивать их в один «процент похожести» нельзя.

1. **Тождество листа** — длина, опоры риса, нахлёст, коробка пустого ядра.
   Если здесь не MATCH, сравнивать диаметры бессмысленно: это разные роллы.
   Ворота: \`EPS_LENGTH_MM = ${EPS_LENGTH_MM}\`, для ядра \`EPS_CORE_ASYMMETRY_MM = ${EPS_CORE_ASYMMETRY_MM}\`.
2. **Геометрия кольца** — диаметры, пространственные дуги риса и нори, витки,
   лучи с двумя слоями нори. Пространственные дуги *должны* отличаться между
   рисом и нори (разный радиус). Инвариант 1 про длину *листа*, не про мм дуги
   в срезе. Ворота на Δ: \`EPS_LENGTH_MM\` (для витков 0,01).
3. **Начинка** — площадь и центр огурца. V2 кладёт в отчёт каталожную площадь
   сектора (erratum-015) и центр в начале координат при одном патче. Legacy
   семплирует \`materialAt\` по сетке. Ворота площади: каталог / legacy ≤
   \`EPS_AREA_RATIO = ${EPS_AREA_RATIO}\`. Центр: 0,15 мм.

Не метрики этого сравнения (и не подгоняются): карта материалов, пиксельный
срез, обжим граней, \`kappa\` сжатия риса под начинкой, почерк руки.

## F01 — пустой хосомаки

${mdTable(tables.F01)}

Лист и ядро совпали побайтово в мм. Кольцо разошлось на **0,3–0,7 мм** по
диаметру и на **~0,35 мм** по каждой дуге: V2 интегрирует среднюю линию слоя
на сетке \`4×NB\` (erratum-010/021), legacy — по \`NB\` бинам уже обжатого
\`rin/rout\`. Это одна и та же формула кольца, разная сетка и отсутствие обжима
в V2.

## F02 — каппамаки

${mdTable(tables.F02)}

Тождество листа снова MATCH. Дальше — структурное, не сеточное.

- **⌀ max +3,3 мм, дуга риса +3,5 мм, дуга нори +5,3 мм.** V2 кладёт рис
  кольцом вокруг коробки 14×10,1 мм без сжатия под огурцом. Legacy давит рис
  (\`kappa\`) и обжимает контур: ролл круглее и меньше. Подгонять V2 под этот
  ⌀ — значит втащить \`kappa\` в ядро, чего контракт V2 alpha не делает.
- **Площадь огурца.** Каталог (и V2) ${fmt(catalogArea)} мм². Сетка legacy
  ${fmt(legacy.F02.cucumberAreaMm2)} мм², отношение
  ${(catalogArea / legacy.F02.cucumberAreaMm2).toFixed(3)} >
  EPS_AREA_RATIO. Это потеря площади в семпле/сжатии, не в формуле сектора.
- **Центр.** V2 при одном патче — начало координат (F01–F04). Legacy — центроид
  сектора в полярной коробке, ~1,3 мм от нуля. Erratum-007 это разрешает только
  как \`f(uMm)\`; для одного патча V2 сознательно держит ноль.

## Что из этого следует

| слой | F01 | F02 | действие |
|---|---|---|---|
| лист / нахлёст / пустое ядро | MATCH | MATCH | якорь, не трогать |
| кольцо (⌀, дуги) | DIVERGE сеточное, < 0,8 мм | DIVERGE структурное, 3–5 мм | не подгонять; \`kappa\` — отдельный ADR |
| начинка | — | DIVERGE площади и центра | V2 держит каталог и origin; не копировать семпл |

Шаг 6 ADR (адаптер в один ручной сценарий) можно начинать с **пустого хосомаки
и каппамаки как картинки ядра**, не ожидая совпадения ⌀ с live-игрой. Расхождение
F02 по диаметру — не регресс V2 и не баг legacy: две модели риса под начинкой.

Числа прогона: \`play/core-v2/reports/divergence.json\`.
`;

fs.writeFileSync(path.join(ROOT, 'reports/divergence.json'), JSON.stringify({
  generated: 'compare-legacy.mjs',
  eps: { EPS_LENGTH_MM, EPS_CORE_ASYMMETRY_MM, EPS_AREA_RATIO },
  catalogCucumberMm2: catalogArea,
  v2, legacy, tables,
}, null, 2));
fs.writeFileSync(path.join(REPO, 'docs/handoff/core-v2-geometry-divergence.md'), md);
console.log(md);
