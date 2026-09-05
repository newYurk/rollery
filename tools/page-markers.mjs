#!/usr/bin/env node
// МАРКЕРЫ КЭША У СТРАНИЦ (#144). Проверяет две вещи, которые молча расходятся.
//
// ЗАЧЕМ. 01.09 владелец трижды прислала снимок сломанной таблицы; я трижды правила файл и
// пушила, а она видела то же самое — браузер отдавал кэш, потому что ССЫЛКА на страницу не
// менялась. Полчаса и три неверных диагноза. 05.09 повторилось на корневой странице: карточка
// «Срез V2» приехала в репозиторий, а на телефоне её не было.
//
// ЧТО ИМЕННО ПРОВЕРЯЕТСЯ.
//   1. У каждой ссылки между страницами есть ?v=.
//   2. Маркер СВЕЖЕЕ страницы: если файл менялся после того, как маркер получил нынешнее
//      значение, — маркер просрочен. Прежняя проверка смотрела только на наличие ?v=, и
//      маркер, поставленный однажды и забытый, проходил её вечно.
//   3. У точек входа есть маяк версии (<meta name="rollery-v">), и он тоже свежий.
//
// СПИСОК СТРАНИЦ НЕ ПРИБИТ. Прибитый список — та же болезнь, что ручной маркер: в него не
// попали play/core-v2/index.html и архитектурный атлас, и они не проверялись вовсе — при
// том, что дыра была именно в core-v2. Страницы находятся обходом дерева.

import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, resolve, relative } from 'node:path';

const ROOT = resolve(dirname(new URL(import.meta.url).pathname), '..');
const git = (...a) => { try { return execFileSync('git', a, { cwd: ROOT, encoding: 'utf8' }).trim(); } catch { return ''; } };

// Точки входа — страницы, чей адрес НАБИРАЮТ или держат в закладке. Ссылки на них нет,
// поэтому ?v= им не поможет в принципе, а свои заголовки на GitHub Pages не задать:
// CDN отдаёт cache-control: max-age=600. Для них — маяк.
const ТОЧКИ_ВХОДА = ['index.html', 'play/index.html', 'play/core-v2/index.html'];

const ПРОПУСК = new Set(['.git', '.claude', 'node_modules', '.venv', 'sim']);

function страницы(dir = ROOT, out = []) {
  for (const e of readdirSync(dir)) {
    if (ПРОПУСК.has(e)) continue;
    const p = join(dir, e);
    if (statSync(p).isDirectory()) страницы(p, out);
    else if (e.endsWith('.html') && !e.endsWith('.template.html')) out.push(relative(ROOT, p));
  }
  return out;
}

const грязный = (f) => git('status', '--porcelain', '--', f) !== '';
const правкаFile = (f) => +git('log', '-1', '--format=%ct', '--', f) || 0;
// Когда нынешнее значение маркера было ВПИСАНО: последний коммит, изменивший число вхождений
// этой точной строки. Если страница правилась позже — маркер просрочен.
const правкаМаркера = (src, строка) => +git('log', '-1', '--format=%ct', `-S${строка}`, '--', src) || 0;

// --fix поднимает маркеры. Чинить ПО КОМАНДЕ, а не молча: молчаливая правка вернула бы
// ровно ту болезнь, от которой этот файл заведён, — расхождение, которого никто не видел.
const ЧИНИТЬ = process.argv.includes('--fix');
const беды = [];
const правки = [];               // { файл, было, стало }
const скажи = (s) => беды.push(s);
const следующий = (v) => (/^\d+$/.test(v) ? String(+v + 1) : '1');

// ── 1–2. ссылки между страницами
for (const src of страницы()) {
  const html = readFileSync(join(ROOT, src), 'utf8');
  for (const m of html.matchAll(/href="([^"#][^"]*)"/g)) {
    const raw = m[1];
    if (/^(https?:|mailto:|tel:|\/\/)/.test(raw)) continue;
    const [путь, запрос = ''] = raw.split('?');
    if (!путь) continue;
    let цель = resolve(dirname(join(ROOT, src)), путь);
    if (путь.endsWith('/')) цель = join(цель, 'index.html');
    if (!цель.endsWith('.html') || !existsSync(цель)) continue;
    const rel = relative(ROOT, цель);
    if (rel === src) continue;

    if (!/(^|&)v=/.test(запрос)) {
      скажи(`${src} → ${rel}: ссылка без ?v= — правка не дойдёт до открывавших`);
      правки.push({ файл: src, было: `href="${raw}"`, стало: `href="${raw}${запрос ? '&' : '?'}v=1"` });
      continue;
    }
    const t = грязный(rel) ? Math.floor(Date.now() / 1000) : правкаFile(rel);
    const tм = правкаМаркера(src, `href="${raw}"`);
    if (tм && t > tм) {
      const дней = Math.floor((t - tм) / 86400);
      const было = запрос.match(/v=([^&]*)/)[1];
      скажи(`${src} → ${rel}: ?v=${было} просрочен — страница правилась позже${дней ? ` (на ${дней} дн.)` : ''}`);
      правки.push({ файл: src, было: `href="${raw}"`, стало: `href="${raw.replace(`v=${было}`, `v=${следующий(было)}`)}"` });
    }
  }
}

// ── 3. маяк у точек входа
for (const p of ТОЧКИ_ВХОДА) {
  if (!existsSync(join(ROOT, p))) { скажи(`точка входа ${p} не найдена`); continue; }
  const html = readFileSync(join(ROOT, p), 'utf8');
  const m = html.match(/<meta name="rollery-v" content="([^"]+)">/);
  if (!m) { скажи(`${p}: нет маяка версии <meta name="rollery-v"> — точку входа маркер в ссылке не лечит`); continue; }  // маяк вписывается руками: это код, не число
  const t = грязный(p) ? Math.floor(Date.now() / 1000) : правкаFile(p);
  const tм = правкаМаркера(p, m[0]);
  if (tм && t > tм) {
    скажи(`${p}: маяк rollery-v=${m[1]} просрочен — страница правилась позже`);
    правки.push({ файл: p, было: m[0], стало: `<meta name="rollery-v" content="${следующий(m[1])}">` });
  }
}

for (const b of беды) console.log(b);

if (ЧИНИТЬ && правки.length) {
  for (const { файл, было, стало } of правки) {
    const путь = join(ROOT, файл);
    const txt = readFileSync(путь, 'utf8');
    if (!txt.includes(было)) { console.log(`  ! ${файл}: не нашлось «${было}»`); continue; }
    writeFileSync(путь, txt.replace(было, стало));
    console.log(`  ✎ ${файл}: ${было} → ${стало}`);
  }
  console.log(`подняты маркеры: ${правки.length}`);
  process.exit(0);
}
if (беды.length && !ЧИНИТЬ) console.log('поднять всё разом: node tools/page-markers.mjs --fix');
process.exit(беды.length ? 1 : 0);
