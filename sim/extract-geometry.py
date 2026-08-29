# -*- coding: utf-8 -*-
import io, re
s = io.open('index.html', encoding='utf-8').read()
js = s[s.index('<script>')+8 : s.rindex('</script>')]
lines = js.split('\n')

def block(name):
    """Блок, где имя объявлено — включая объявления вида `const A = 1, B = 2;`."""
    pat = re.compile(r'^\s*(?:function\s+%s\s*\(|(?:const|let)\s+(?:[\w$]+\s*=[^;]*,\s*)*%s\s*=)' % (name, name))
    for i, ln in enumerate(lines):
        if pat.match(ln):
            depth = 0; started = False
            for j in range(i, len(lines)):
                for ch in lines[j]:
                    if ch in '{[(': depth += 1; started = True
                    elif ch in '}])': depth -= 1
                if started and depth <= 0: return i, j
                if not started and lines[j].rstrip().endswith(';'): return i, j
            return i, i
    return None

# строки-инициализаторы, которые надо взять дословно (они не «объявления»)
INIT_AFTER = {
 'BASES': [r'^for \(const k in BASES\) \{ const b = BASES\[k\]'],
 'ING':   [r'^for \(const k in ING\) ING\[k\]\.rgb', r'^for \(const k in BASES\) \{ BASES\[k\]\.wrapperRgb'],
}
NAMES = [
 'clamp','lerp','fract','smooth','hexRgb','mix','shade','hash',
 'BASES','R0','ING','NPIECES','pieceV',
 'sheetLen','dims','bounds','overlap','restack','patchSRange','matAt','covers',
 'NB','TAPER','PROF_DS','geometry','stackTopAt','spreadAt','betaEff','bandAt',
 'thicknessProfile','wind','sampleWind','innerAt','topAt',
 'computeCore','diskToSquare','coreMaterial',
 'SLICES','modelCaches','buildModel','getModel','windFor','materialAt',
 'SHAPES','shapeCache','shapeInfo','shapeK',
 'KIND_IDS','materialMap','similarity',
]
# собираем ДИАПАЗОНЫ строк, потом сортируем по исходному порядку — иначе ломаются зависимости
ranges, missing = [], []
for n in NAMES:
    b = block(n)
    if not b: missing.append(n); continue
    ranges.append(b)
    for pat in INIT_AFTER.get(n, []):
        for i, ln in enumerate(lines):
            if re.match(pat, ln): ranges.append((i, i))
ranges = sorted(set(ranges))
# выкинуть вложенные диапазоны
keep = []
for r in ranges:
    if any(r != k and k[0] <= r[0] and r[1] <= k[1] for k in ranges): continue
    keep.append(r)
out = ['\n'.join(lines[a:b+1]) for a, b in keep]

header = io.open('/Users/newyurk/.claude/jobs/5de4c815/tmp/header.txt', encoding='utf-8').read() if False else u"""// ============================================================================
//  «Ролльня» — ядро геометрии: лист → намотка → срез
//  Извлечено из index.html 26.08.2026. Ни одной зависимости, ни одного
//  обращения к canvas / document / window — чистая математика.
//  Проверено: считается в Node без браузера (тест в конце файла).
//
//  МОДЕЛЬ В ДВУХ АБЗАЦАХ
//
//  Лист хранится в координатах (u, v, z): u — вдоль направления скрутки
//  (0 — ближний край, уходит в центр ролла; 1 — дальний край), v — вдоль
//  оси ролла (какой ломтик), z — по толщине намазки (0 — на обёртке,
//  1 — верх намазки). Начинка — прямоугольный патч с интервалом по z,
//  возможно повёрнутый (rot: 0 вдоль оси, π/2 поперёк, π/4 по диагонали).
//  Единица длины — толщина намазки: у суши это слой риса ≈ 5 мм.
//
//  Скрутка — намотка листа ПЕРЕМЕННОЙ толщины: лист режется на 1440 угловых
//  бинов и наматывается виток за витком. Где стопка толще намазки — слой
//  толще, рис под начинкой выдавлен (сжимаемость kappa), избыток сжат
//  циновкой (beta), профиль сглажен, чтобы бугор не был уступом. Начинки
//  у ближнего края сминаются в плотное ядро (подворот). Срез — попиксельная
//  развёртка: для точки (r, φ) находим виток, положение внутри него и
//  спрашиваем, какой материал лежит в соответствующей точке листа.
//
//  ВХОД:  список патчей [{kind, u, v, rot?, wU?, hU?, dv?, phase}]
//  ВЫХОД: materialAt(...)  — что лежит в точке среза;
//         materialMap(...) — карта классов: 0 фон, 1 намазка, 2 обёртка, 3+ начинки;
//         similarity(...)  — сходство двух роллов (для пазла и калибровки).
//
//  ЧТО ПОДСТАВИТЬ ПРИ ПЕРЕНОСЕ (единственные внешние связи):
//    S.base    — активная база: 'sushi' | 'cake' | 'lavash'
//    S.turns   — число витков, если задано пазлом, иначе null
//    S.shape   — форма прессовки: 'round' | 'square' | 'triangle'
//    S.hand    — почерк: {air, wobble, phase, press}
//    B()       — текущая база: BASES[S.base]
//    patches() — текущий список патчей
//    modelKey  — строка-ключ кэша (можно оставить пустой)
//  В другом языке это становится аргументами функций.
// ============================================================================

const TAU = Math.PI * 2;
"""

tail = u"""

// ============================================================================
//  САМОПРОВЕРКА. Скопируй файл в rollery-geometry.js, раскомментируй блок
//  ниже и запусти:  node rollery-geometry.js
// ============================================================================
/*
const S = { base: 'sushi', turns: null, shape: 'round',
            hand: { air: 0, wobble: 0, phase: 0, press: 1 },
            lists: { sushi: [], cake: [], lavash: [] } };
const B = () => BASES[S.base];
const patches = () => S.lists[S.base];
let modelKey = '';

S.lists.sushi = [
  { kind: 'tamago',   u: 0.06, v: 0.5, z0: 0, z1: 0, phase: 0 },
  { kind: 'salmon',   u: 0.15, v: 0.5, z0: 0, z1: 0, phase: 0 },
  { kind: 'cucumber', u: 0.24, v: 0.5, z0: 0, z1: 0, phase: 0 },
];
const m = buildModel(patches());
const wd = windFor(m, 0.5);
console.log('радиус ролла:', wd.Rout.toFixed(2),
            '· оборотов:', wd.turns.toFixed(2),
            '· радиус ядра:', m.core.R.toFixed(2));
for (const phi of [0.3, 2.0, 4.5]) {
  let last = null, seq = [];
  for (let r = 0.03; r < wd.Rout; r += 0.01) {
    const mt = materialAt(m, wd, 0.5, r, phi);
    const id = mt.cls === 'patch' ? mt.mt.p.kind : mt.cls;
    if (id !== last) { seq.push(id); last = id; }
  }
  console.log('луч', phi, ':', seq.join(' -> '));
}
*/
"""
code = header + '\n\n'.join(out) + tail
# Куда писать: по умолчанию — снимок в репозитории. Раньше путь был жёстко зашит на Desktop,
# и повторный запуск молча затирал файл, по которому шло ревью. Теперь путь задаётся аргументом,
# а снимок в git остаётся эталоном той версии, которую проверяли.
import sys
dest = sys.argv[1] if len(sys.argv) > 1 else 'sim/geometry-core.txt'
io.open(dest,'w',encoding='utf-8').write(code)
print('записано в', dest)
print('строк:', code.count('\n'), '· символов:', len(code), '· не найдено:', ', '.join(missing) or 'ничего')
