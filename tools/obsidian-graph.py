"""Картинка графа блюда: семьи заметок лежат своими островами, рисуем через PIL.

networkx и matplotlib на маке не стоят, а тянуть их ради одной картинки незачем.

⚑ РАСКЛАДКА НЕ ПРУЖИННАЯ, А ПО СЕМЬЯМ (17.09). Чистые пружины держались, пока заметок было 77:
на 99 притяжение пересилило отталкивание, и начинки схлопнулись в три зелёных комка — подписи
пришлось бы ставить поверх каши. Читать такой граф нельзя, а он нужен именно для чтения:
владелец просила ориентироваться по нему в игре. Поэтому у каждой семьи свой остров, места в игре
(09) лежат в середине как якоря, и уже внутри этого узлы подтягиваются пружинами к тем, с кем
связаны. В конце — проход расталкивания: два узла не могут стоять ближе, чем их кружки.

Запуск: python3 tools/obsidian-graph.py [путь к хранилищу]."""
import os, re, math, random, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'Rollery-Obsidian')
F = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 11)
FB = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 13)

# ── кто с кем связан ──────────────────────────────────────────────────────
nodes, edges, folder = {}, set(), {}
for root, _, fs in os.walk(V):
    for f in fs:
        if not f.endswith('.md'): continue
        name = f[:-3]; rel = os.path.relpath(root, V)
        folder[name] = rel.split('/')[0] if rel != '.' else 'карта'
        nodes[name] = None
for root, _, fs in os.walk(V):
    for f in fs:
        if not f.endswith('.md'): continue
        src = f[:-3]
        for l in re.findall(r'\[\[([^\]]+)\]\]', open(os.path.join(root, f), encoding='utf-8').read()):
            if l in nodes and l != src: edges.add(tuple(sorted((src, l))))
deg = {n: 1 for n in nodes}
for a, b in edges: deg[a] += 1; deg[b] += 1

COL = {'01_Роллы': (198, 92, 84), '02_Приёмы': (92, 140, 196), '03_Каноны': (214, 158, 46),
       '04_Начинки': (110, 168, 92), '05_Нарезки': (150, 110, 190), '06_Обёртки': (196, 150, 90),
       '07_Решения': (214, 120, 40), '08_Источники': (120, 120, 120), '09_Где в игре': (28, 128, 132),
       '10_Пазл': (120, 160, 200), 'карта': (30, 30, 30)}
# Порядок островов по кругу — не алфавит, а смысл: роллы рядом с начинками и нарезками, каноны
# рядом с приёмами, пазл рядом с решениями. Соседей на картинке связывает меньше длинных хорд.
КРУГ = ['01_Роллы', '04_Начинки', '05_Нарезки', '06_Обёртки', '03_Каноны', '02_Приёмы',
        '07_Решения', '08_Источники', '10_Пазл']
# Кому подпись достаётся раньше: по графу ориентируются в игре, значит места и карта важнее всех.
ВЕС = {'09_Где в игре': 0, 'карта': 0, '01_Роллы': 1, '02_Приёмы': 1, '03_Каноны': 2, '10_Пазл': 3,
       '07_Решения': 3, '05_Нарезки': 3, '06_Обёртки': 3, '08_Источники': 4, '04_Начинки': 4}

# ── острова: у каждой семьи свой центр ────────────────────────────────────
ЦЕНТР = {'карта': (0.0, 0.0)}
for i, f in enumerate(КРУГ):
    a = 2 * math.pi * i / len(КРУГ) - math.pi / 2
    ЦЕНТР[f] = (1.35 * math.cos(a), 1.35 * math.sin(a))
ЦЕНТР['09_Где в игре'] = (0.0, 0.0)          # места в игре — якоря, они в середине
rnd = random.Random(7)
pos = {}
семья = {}
for f in set(folder.values()):
    семья[f] = sorted([n for n in nodes if folder[n] == f], key=lambda n: -deg[n])
for f, ns in семья.items():
    cx, cy = ЦЕНТР.get(f, (0, 0))
    R = 0.13 * math.sqrt(len(ns)) + (0.42 if f == '09_Где в игре' else 0.0)
    for i, n in enumerate(ns):
        a = 2 * math.pi * i / max(1, len(ns))
        r = R * (0.45 if f == '09_Где в игре' else (0.25 + 0.75 * (i % 3) / 2))
        pos[n] = [cx + r * math.cos(a) + rnd.uniform(-.02, .02),
                  cy + r * math.sin(a) + rnd.uniform(-.02, .02)]

# ── пружины внутри островов ───────────────────────────────────────────────
for step in range(260):
    disp = {n: [0.0, 0.0] for n in nodes}
    ns = list(nodes)
    for i, a in enumerate(ns):                         # все отталкиваются
        for b in ns[i + 1:]:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d2 = dx * dx + dy * dy + 1e-4
            fq = 0.0016 / d2
            disp[a][0] += dx * fq; disp[a][1] += dy * fq
            disp[b][0] -= dx * fq; disp[b][1] -= dy * fq
    for a, b in edges:                                 # связанные притягиваются
        dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
        d = math.hypot(dx, dy) + 1e-6
        fq = 0.035 * d
        disp[a][0] -= dx / d * fq; disp[a][1] -= dy / d * fq
        disp[b][0] += dx / d * fq; disp[b][1] += dy / d * fq
    for n in nodes:                                    # и каждый держится своего острова
        cx, cy = ЦЕНТР.get(folder[n], (0, 0))
        disp[n][0] += (cx - pos[n][0]) * 0.09; disp[n][1] += (cy - pos[n][1]) * 0.09
    t = 0.06 * (1 - step / 300) + 0.004
    for n in nodes:
        dx, dy = disp[n]; d = math.hypot(dx, dy) + 1e-9
        pos[n][0] += dx / d * min(d, t); pos[n][1] += dy / d * min(d, t)

# ── на холст ──────────────────────────────────────────────────────────────
W, H, M = 2000, 1350, 110
xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
sx = (W - 2 * M) / (max(xs) - min(xs)); sy = (H - 2 * M) / (max(ys) - min(ys))
P = {n: [M + (p[0] - min(xs)) * sx, M + (p[1] - min(ys)) * sy] for n, p in pos.items()}
RAD = {n: 3 + min(9, deg[n]) for n in nodes}
for _ in range(60):                                    # расталкивание: кружки не налезают друг на друга
    for a in nodes:
        for b in nodes:
            if a >= b: continue
            dx, dy = P[a][0] - P[b][0], P[a][1] - P[b][1]
            d = math.hypot(dx, dy) + 1e-6
            need = RAD[a] + RAD[b] + 7
            if d < need:
                k = (need - d) / 2 / d
                P[a][0] += dx * k; P[a][1] += dy * k
                P[b][0] -= dx * k; P[b][1] -= dy * k
for n in P:
    P[n][0] = min(W - 16, max(16, P[n][0])); P[n][1] = min(H - 16, max(70, P[n][1]))

img = Image.new('RGB', (W, H), (250, 248, 242)); d = ImageDraw.Draw(img)
for a, b in edges: d.line([tuple(P[a]), tuple(P[b])], fill=(212, 206, 194), width=1)
for n, (x, y) in P.items():
    r = RAD[n]
    c = COL.get(folder[n], (90, 90, 90))
    d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    if folder[n] in ('09_Где в игре', 'карта'):
        d.ellipse([x - r - 3, y - r - 3, x + r + 3, y + r + 3], outline=c, width=2)
# Подписей влезает не всё. Узлы идут по важности, подпись пробует четыре места вокруг кружка, и
# если все заняты — узел остаётся точкой: безымянная точка лучше, чем каша из наложенных букв.
занято = [(0, 0, 1100, 62)]                            # заголовок и легенда
def свободно(b):
    return all(not (b[0] < o[2] and o[0] < b[2] and b[1] < o[3] and o[1] < b[3]) for o in занято)
for n in sorted(P, key=lambda n: (ВЕС.get(folder[n], 5), -deg[n], n)):
    x, y = P[n]; r = RAD[n]
    t = n.split(': ')[-1][:32]
    шр = FB if folder[n] in ('09_Где в игре', 'карта') else F
    w = d.textlength(t, font=шр); h = 13
    for ax, ay in ((x + r + 4, y - h / 2), (x - r - 4 - w, y - h / 2),
                   (x - w / 2, y - r - h - 2), (x - w / 2, y + r + 2)):
        if ax < 2 or ax + w > W - 2: continue
        box = (ax - 1, ay - 1, ax + w + 1, ay + h + 1)
        if свободно(box):
            занято.append(box); d.text((ax, ay), t, fill=(30, 30, 30), font=шр); break
d.text((20, 16), 'Ролльня — граф блюда: %d заметок, %d связей. Подписано %d'
       % (len(nodes), len(edges), len(занято) - 1), fill=(20, 20, 20), font=FB)
lx = 20
for k in КРУГ + ['09_Где в игре']:
    им = k.split('_', 1)[1]
    d.ellipse([lx, 44, lx + 12, 56], fill=COL[k]); d.text((lx + 18, 42), им, fill=(40, 40, 40), font=F)
    lx += 20 + 8 + int(d.textlength(им, font=F)) + 14
img.save(os.path.join(V, 'граф.png'))
print('узлов', len(nodes), 'связей', len(edges), 'подписей', len(занято) - 1)
