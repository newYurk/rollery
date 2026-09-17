"""Картинка графа заметок: пружинная раскладка своими руками, рисуем через PIL.

networkx и matplotlib на маке не стоят, а тянуть их ради одной картинки незачем: пружины — двадцать
строк. Узел тем крупнее, чем больше у него связей; подписаны механизмы, вехи и всё, у чего связей
от пяти. Запуск: python3 tools/obsidian-graph.py [путь к хранилищу]."""
import os, re, math, random, sys
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'Rollery-Obsidian')
F = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 11)
FB = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', 13)
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
COL = {'01_Решения': (214, 158, 46), '02_Материалы': (110, 168, 92), '03_Механизмы': (92, 140, 196),
       '04_Дефекты': (198, 92, 84), '05_Сторожа': (150, 110, 190), '06_Источники': (120, 120, 120), 'карта': (30, 30, 30)}
rnd = random.Random(7)
pos = {n: [rnd.uniform(-1, 1), rnd.uniform(-1, 1)] for n in nodes}
deg = {n: 1 for n in nodes}
for a, b in edges: deg[a] += 1; deg[b] += 1
for step in range(420):                      # пружины: связанные тянутся, все отталкиваются
    disp = {n: [0.0, 0.0] for n in nodes}
    ns = list(nodes)
    for i, a in enumerate(ns):
        for b in ns[i + 1:]:
            dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
            d2 = dx * dx + dy * dy + 1e-4
            f = 0.0011 / d2
            disp[a][0] += dx * f; disp[a][1] += dy * f; disp[b][0] -= dx * f; disp[b][1] -= dy * f
    for a, b in edges:
        dx, dy = pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]
        d = math.hypot(dx, dy) + 1e-6
        f = 0.06 * d
        disp[a][0] -= dx / d * f; disp[a][1] -= dy / d * f; disp[b][0] += dx / d * f; disp[b][1] += dy / d * f
    t = 0.08 * (1 - step / 320) + 0.004
    for n in nodes:
        dx, dy = disp[n]; d = math.hypot(dx, dy) + 1e-9
        pos[n][0] += dx / d * min(d, t); pos[n][1] += dy / d * min(d, t)
xs = [p[0] for p in pos.values()]; ys = [p[1] for p in pos.values()]
W, H, M = 1700, 1150, 80
sx = (W - 2 * M) / (max(xs) - min(xs)); sy = (H - 2 * M) / (max(ys) - min(ys))
P = {n: (M + (p[0] - min(xs)) * sx, M + (p[1] - min(ys)) * sy) for n, p in pos.items()}
img = Image.new('RGB', (W, H), (250, 248, 242)); d = ImageDraw.Draw(img)
for a, b in edges: d.line([P[a], P[b]], fill=(206, 200, 188), width=1)
for n, (x, y) in P.items():
    r = 3 + min(9, deg[n])
    c = COL.get(folder[n], (90, 90, 90))
    d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    if deg[n] >= 5 or folder[n] in ('03_Механизмы', 'карта') or n.startswith('Веха'):
        t = n.split(': ')[-1]
        d.text((x + r + 3, y - 6), t[:34], fill=(40, 40, 40), font=F)
d.text((20, 16), 'Ролльня — граф знаний: %d заметок, %d связей' % (len(nodes), len(edges)), fill=(20, 20, 20), font=FB)
lx = 20
for k, c in COL.items():
    if k == 'карта': continue
    d.ellipse([lx, 44, lx + 12, 56], fill=c); d.text((lx + 18, 42), k.split('_')[1], fill=(40, 40, 40), font=F)
    lx += 20 + 8 + int(d.textlength(k.split('_')[1], font=F)) + 14
img.save(os.path.join(V, 'граф.png'))
print('узлов', len(nodes), 'связей', len(edges))
