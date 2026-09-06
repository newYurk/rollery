#!/usr/bin/env node
// ADR-001 step 5: compare V2 to live geometry.js on the same F01/F02 inputs.
// Document divergence. Do not fit.

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { runF01, runF02, runF05, cucumberCatalogAreaMm2 } from './fixtures.js';
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
  { key: 'overlapMm', label: 'нахлёст (остаток листа)', unit: 'мм', eps: EPS_LENGTH_MM, kind: 'identity' },
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

// ⚑ ЧИСЛА В ПРОЗЕ БЕРУТСЯ ИЗ ТАБЛИЦЫ, А НЕ ВПИСЫВАЮТСЯ (внешнее ревью, PR #202).
// Стоял текст «разошлось на ~0,35 мм по каждой дуге» — при том, что таблица прямо над ним
// показывала по рису 31,487. Отчёт пересобирает CI, и читатель принимал решения по выводу,
// который опровергается его же таблицей строкой выше.
function δ(id, key) {
  const r = (tables[id] || []).find((x) => x.key === key);
  return r ? Math.abs(r.delta).toFixed(3) : '—';
}

// ⚑ ТРЕТИЙ СЛОЙ ТОЙ ЖЕ БОЛЕЗНИ (внешнее ревью, PR #211). Ворота площади я сделала
// симметричными, а проза ниже продолжала считать СВОЁ одностороннее отношение и печатала
// «0.893 > EPS_AREA_RATIO» — число, которое противоречит и порогу, и таблице. Пока проза
// умеет считать сама, она будет расходиться с воротами. Теперь ей нечем: берёт готовое.
// ⚑ ЧЕТВЁРТЫЙ ЗАХОД НА ТУ ЖЕ БОЛЕЗНЬ (ревью CodeRabbit на PR #211).
// Проза F02 несла вписанные руками «⌀ max +3,3 · дуга риса +3,5 · дуга нори +5,3», тогда
// как таблица давала −0,097 (и вовсе MATCH), 18,914 и −0,472 — мимо на порядок и по знаку.
// Проза F01 говорила «совпали побайтово» при DIVERGE у шва (−2,357) и умалчивала о нём.
// Пока текст может назвать хоть одно число сам, он разойдётся. Теперь список расхождений
// СОБИРАЕТСЯ из таблицы: чего в ней нет — того не будет и в прозе.
// Группа «тождество листа» обязана быть MATCH — значит утверждать это надо ЗАМЕРОМ,
// а не текстом. Раньше стояло «Тождество листа снова MATCH» безусловно, при том что
// нахлёст стоял на DIVERGE и числился в этой же группе (ревью CodeRabbit на PR #212).
const ТОЖДЕСТВО = ['lengthMm', 'sRice0Mm', 'sRice1Mm', 'coreWcMm', 'coreHcMm'];
const КОЛЬЦО = ['overlapMm', 'diameterMinMm', 'diameterMaxMm', 'riceArcMm', 'noriArcMm',
  'turns', 'twoIntersectionCount'];
const НАЧИНКА = ['cucumberAreaMm2', 'cucumberCenterXmm', 'cucumberCenterYmm'];

// ⚑ ИТОГОВАЯ ТАБЛИЦА ТОЖЕ СЧИТАЕТСЯ (ревью Greptile на PR #212). Она была вписана руками
// и спорила с посчитанными таблицами над ней: строка «лист / нахлёст / пустое ядро» стояла
// MATCH при DIVERGE у нахлёста в обеих фикстурах и у коробки ядра в F02, а «кольцо
// структурное, 3–5 мм» — при дуге риса 18,914. Пятый заход на одну болезнь за вечер, и
// каждый раз это было место, которому позволено назвать число самому.
function сводка(id, ключи) {
  const строки = (tables[id] || []).filter((r) => ключи.includes(r.key));
  if (!строки.length) return '—';
  const плохие = строки.filter((r) => r.gate === 'DIVERGE');
  if (!плохие.length) return 'MATCH';
  // «Больше всех» ищется в ПРЕДЕЛАХ ОДНОЙ ЕДИНИЦЫ: миллиметры и счёт лучей не сравнимы,
  // и без этого «до 40.000» у счётчика лучей читалось как сорок миллиметров.
  const пределы = new Map();
  for (const r of плохие) {
    const ед = r.unit || 'шт';
    const п = пределы.get(ед);
    if (!п || Math.abs(r.delta) > Math.abs(п.delta)) пределы.set(ед, r);
  }
  const хвост = [...пределы.values()]
    .map((r) => `до ${Math.abs(r.delta).toFixed(3)} ${r.unit || 'шт'} (${r.label})`)
    .join('; ');
  return `DIVERGE ${плохие.length} из ${строки.length}: ${хвост}`;
}
function тождество(id) {
  const строки = (tables[id] || []).filter((r) => ТОЖДЕСТВО.includes(r.key));
  const плохие = строки.filter((r) => r.gate !== 'MATCH');
  if (!строки.length) return 'Тождество листа не измерено.';
  const сошлось = строки.filter((r) => r.gate === 'MATCH').map((r) => r.label);
  return плохие.length
    ? `Совпало побайтово: ${сошлось.join(', ') || '—'}. ` +
      `А вот ${плохие.map((r) => r.label).join(', ')} — уже нет, и это не сеточная разница: ` +
      `причина названа ниже, она же объясняет диаметры.`
    : 'Длина листа, опоры риса и коробка ядра совпали побайтово в мм.';
}

function расходятся(id) {
  const плохие = (tables[id] || []).filter((r) => r.gate === 'DIVERGE');
  if (!плохие.length) return 'ни одной строки — все ворота MATCH';
  return плохие
    .map((r) => `**${r.label}** ${r.delta >= 0 ? '+' : '−'}${Math.abs(r.delta).toFixed(3)} ${r.unit || ''}`.trim())
    .join(', ');
}

function площадьF02() {
  const r = (tables.F02 || []).find((x) => x.key === 'cucumberAreaMm2');
  if (!r || r.areaRatio == null) return '—';
  const знак = r.areaRatio > EPS_AREA_RATIO ? '>' : '≤';
  return `${r.areaRatio.toFixed(3)} ${знак} EPS_AREA_RATIO ${EPS_AREA_RATIO} → ${r.gate}`;
}

function диапазон(id, k1, k2) {
  const a = +δ(id, k1), b = +δ(id, k2);
  return Number.isFinite(a) && Number.isFinite(b)
    ? `${Math.min(a, b).toFixed(3)}…${Math.max(a, b).toFixed(3)}` : '—';
}

function row(metric, v2, leg, catalogArea) {
  const a = num(v2[metric.key]);
  const b = num(leg[metric.key]);
  const d = a - b;
  let gate = '—';
  let note = '';
  let areaRatio = null;
  if (metric.key === 'cucumberAreaMm2') {
    // ⚑ ОТНОШЕНИЕ СИММЕТРИЧНО (внешнее ревью, PR #202). Стояло `catalogArea / legacy`
    // без симметризации: если legacy БОЛЬШЕ каталога, отношение меньше единицы и ворота
    // пропускали любое расхождение. F02: каталог 64 против legacy 71,663 давало 0,893 и
    // «MATCH» при разнице в 12 %, тогда как приёмка фикстур на том же EPS_AREA_RATIO
    // симметрична и такое отвергает.
    const big = Math.max(catalogArea, b), small = Math.max(Math.min(catalogArea, b), 1e-9);
    const ratio = big / small;
    gate = ratio <= EPS_AREA_RATIO ? 'MATCH' : 'DIVERGE';
    note = `каталог ${catalogArea.toFixed(3)} ↔ legacy ${b.toFixed(3)}, отношение ${ratio.toFixed(3)} (EPS_AREA_RATIO ${EPS_AREA_RATIO})`;
    areaRatio = ratio;   // проза ниже берёт ЭТО число, а не считает своё
  } else if (metric.eps != null) {
    gate = Math.abs(d) <= metric.eps ? 'MATCH' : 'DIVERGE';
    note = `|Δ| ${Math.abs(d).toFixed(3)} ≷ ${metric.eps}`;
  }
  return { ...metric, v2: a, legacy: b, delta: d, gate, note, areaRatio };
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
// ⚑ ВТОРАЯ БАЗА (#209, пункт 2). Сверка двух движков стояла на ОДНОЙ базе из шести — пустом
// хосомаки и хосомаки с огурцом. Про футомаки не было измерено ничего, при том что запас уже
// на самом простом случае невелик: витки 1,159973 против 1,187600 при допуске 0,05.
//
// ⚠ ШЕСТИ БАЗ НЕ БУДЕТ, И ЭТО НЕ ЛЕНЬ. V2 alpha считает только хосомаки и футомаки, остальным
// отвечает `base_unsupported` (`erratum-023`). Сверять можно ровно то, что оба движка умеют;
// тюмаки, урамаки, узумаки и фруктовый сравнивать не с чем, пока V2 их не считает.
//
// ⚠ ГРУППА НАЧИНКИ У F05 НЕ МЕРИТСЯ, и причина — разные величины по обе стороны. Легаси-зонд
// суммирует площадь и центроид ПО ВСЕМ патчам сразу (`q.cls === 'patch'` по сетке), а V2
// отдаёт патчи поштучно, и `visiblePatches[0]` — только огурец. Сравнить сумму трёх с одним
// значило бы поставить ворота на разницу определений. У F02 патч один, и там всё сходится.
const v2 = { F01: v2pack(runF01()), F02: v2pack(runF02()), F05: v2pack(runF05().abc) };
const catalogArea = cucumberCatalogAreaMm2();

const tables = {};
for (const id of ['F01', 'F02', 'F05']) {
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
| F05 | футомаки: огурец 35, тамаго 55, лосось 80 мм | \`S.base='futo'\`, те же три в долях листа 210 |
| лист | 105 × 190 мм | \`g.L × U_MM\`, \`U_MM=5\` |
| рука | только neutral | \`handOf()\` — нули |

Legacy внутри считает в единицах каталога. Все числа ниже уже в мм
(\`× U_MM\` ровно один раз, в \`legacy-probe.js\`).

## Какие метрики и зачем

Три слоя. Смешивать их в один «процент похожести» нельзя.

1. **Тождество листа** — длина, опоры риса, коробка пустого ядра.
   Если здесь не MATCH, сравнивать диаметры бессмысленно: это разные роллы.
   Ворота: \`EPS_LENGTH_MM = ${EPS_LENGTH_MM}\`, для ядра \`EPS_CORE_ASYMMETRY_MM = ${EPS_CORE_ASYMMETRY_MM}\`.
   ⚠ **Нахлёст отсюда убран** и переехал в геометрию: с #188 V2 считает его остатком
   листа (\`L − периметр\`), а legacy — длиной голых полей. Это разные величины, и их
   расхождение ожидаемо; держать его в группе, обязанной быть MATCH, значило называть
   MATCH то, что стоит на DIVERGE.
2. **Геометрия кольца** — нахлёст, диаметры, пространственные дуги риса и нори, витки,
   лучи с двумя слоями нори. Пространственные дуги *должны* отличаться между
   рисом и нори (разный радиус). Инвариант 1 про длину *листа*, не про мм дуги
   в срезе. Ворота на Δ: \`EPS_LENGTH_MM\` (для витков 0,01).
3. **Начинка** — площадь и центр огурца. V2 кладёт в отчёт каталожную площадь
   сектора (erratum-015) и центр в начале координат при одном патче. Legacy
   семплирует \`materialAt\` по сетке. Ворота площади:
   \`max(каталог, legacy) / min(каталог, legacy) ≤ EPS_AREA_RATIO = ${EPS_AREA_RATIO}\`
   — отношение СИММЕТРИЧНО, иначе превышение legacy проходило бы любым.
   Центр: 0,15 мм.

Не метрики этого сравнения (и не подгоняются): карта материалов, пиксельный
срез, обжим граней, \`kappa\` сжатия риса под начинкой, почерк руки.

## Два разных инварианта листа — и «legacy теряет лист» смешивало их

Формулировка ходила по задачам с 02.09 (#165) и была верна наполовину.

**Длина.** V2 сохраняет её: \`overlapMm = L − noriPerimeter\`, невязка 0,00e+0 на всех
фикстурах, держит \`sheet-conserved\` (#188). Кольцо legacy — нет, и не может: оно отдаёт
постели ровно один оборот, какой бы длинной та ни была. Решение 05.09 приняло это как
свойство кольца, а не поломку: одним оборотом площадь и длину сразу не удержать, и
выбрана площадь. Величина замерена по базам и печатается мягким каналом \`play/?check\`
(«нори растянута/сжата в N раз») — знак там меняется: хосомаки лист растягивает,
остальные жмут. Числа держатся живым замером и здесь не дублируются: вписанное руками
протухает, а мерка — нет.

**Адрес.** А вот это было поломкой, и её больше нет (#165, 06.09). Кольцо кладёт нахлёстом
обе голые полосы листа — дальнюю \`[spreadEnd, L]\` и ближнюю \`[0, spreadStart]\`, — но
раскладывало их одним сплошным отрезком от \`spreadEnd\`, будто они лежат подряд. Они на
разных концах, и адрес уезжал за конец листа ровно на длину ближней полосы; у урамаки
(\`spreadEnd = 1\`, дальней полосы нет вовсе) за листом лежал весь нахлёст. Починено
заворотом по модулю листа: в кольце угол ровно \`τ\`, конец листа встречает своё начало.
Правка тронула только \`u0\`/\`u1\` — радиусы, витки и рисунок не изменились, и числа
в таблицах ниже остались прежними.

## F01 — пустой хосомаки

${mdTable(tables.F01)}

${тождество('F01')} Список расхождений собран из таблицы выше целиком, а не
отобран на глаз: ${расходятся('F01')}.

Разница по нори сеточная: V2 интегрирует среднюю линию слоя на сетке \`4×NB\`
(erratum-010/021), legacy — по \`NB\` бинам уже обжатого \`rin/rout\`. Это одна и та
же формула кольца, разная сетка и отсутствие обжима в V2.

Разница по РИСУ структурная и на два порядка больше: V2 кладёт рис лентой длиной
\`Lrice\` (#183), legacy растягивает ту же постель на один оборот. Это и есть цена кольца
из #165 — не дефект, а следствие выбора «площадь вместо длины» (см. раздел выше).

## F02 — каппамаки

${mdTable(tables.F02)}

${тождество('F02')} Дальше — структурное, не сеточное.

- **Что разошлось** (из таблицы, целиком): ${расходятся('F02')}.

  Причин две, и они разные. **Кольцо и ядро:** V2 кладёт рис кольцом вокруг СВОЕЙ коробки
  ${fmt(v2.F02.coreWcMm)}×${fmt(v2.F02.coreHcMm)} мм без сжатия под огурцом
  (у legacy она ${fmt(legacy.F02.coreWcMm)}×${fmt(legacy.F02.coreHcMm)}).
  Legacy давит рис (\`kappa\`) и обжимает контур: ролл круглее и меньше. Подгонять
  V2 под этот ⌀ — значит втащить \`kappa\` в ядро, чего контракт V2 alpha не делает.
  **Начинка** (площадь и центр огурца) к сжатию ядра отношения не имеет — её причины
  ниже, отдельными пунктами.
- **Площадь огурца.** Каталог (и V2) ${fmt(catalogArea)} мм². Сетка legacy
  ${fmt(legacy.F02.cucumberAreaMm2)} мм². Отношение берётся из таблицы выше, а не
  пересчитывается здесь: ${площадьF02()}. Это потеря площади в семпле или
  сжатии, не в формуле сектора.
- **Центр.** V2 при одном патче — начало координат (F01–F04). Legacy — центроид
  сектора в полярной коробке, ~1,3 мм от нуля. Erratum-007 это разрешает только
  как \`f(uMm)\`; для одного патча V2 сознательно держит ноль.

## Что из этого следует

## F05 — футомаки с тремя начинками

Вторая база сверки, заведена по #209. До неё оба движка сравнивались только на хосомаки, и
про футомаки не было измерено ничего.

${mdTable(tables.F05)}

${тождество('F05')}

- **Что разошлось** (из таблицы, целиком): ${расходятся('F05')}.
- **Запас по виткам съеден целиком.** На хосомаки расхождение витков ${δ('F01', 'turns')}
  при допуске ${METRICS.find((m) => m.key === 'turns').eps}; здесь — ${δ('F05', 'turns')}.
  Это не «чуть хуже», а другой порядок, и увидеть его было нельзя, пока мерили одну базу.

| слой | F01 | F02 | F05 | действие |
|---|---|---|---|---|
| лист и пустое ядро | ${сводка('F01', ТОЖДЕСТВО)} | ${сводка('F02', ТОЖДЕСТВО)} | ${сводка('F05', ТОЖДЕСТВО)} | якорь, не трогать |
| кольцо (нахлёст, ⌀, дуги) | ${сводка('F01', КОЛЬЦО)} | ${сводка('F02', КОЛЬЦО)} | ${сводка('F05', КОЛЬЦО)} | не подгонять; \`kappa\` — отдельный ADR |
| начинка | ${сводка('F01', НАЧИНКА)} | ${сводка('F02', НАЧИНКА)} | не мерится (см. выше) | V2 держит каталог и origin; не копировать семпл |

Ни одно число в этой таблице не вписано: все собраны из таблиц выше.

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
