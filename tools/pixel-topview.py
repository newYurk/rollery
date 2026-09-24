#!/usr/bin/env python3
"""Шкуры вида сверху: как начинка лежит на листе (issue #256, просьба владельца 17.09).

ЧТО ЭТО ЗА КАРТИНКИ И ЧЕМ ОНИ НЕ ЯВЛЯЮТСЯ. Вид сверху в игре ВЫВОДИТСЯ из тела начинки
(#105): форму, размер, место и цвет считает модель. Картинка даёт ТОЛЬКО рисунок — фактуру, —
и входит в отрисовку одним множителем яркости (play/render/sheet.js, skinField). Поэтому здесь
не «арт начинки», а полоса фактуры: чем она отличается ВДОЛЬ куска, тем и полезна.

ПРАВИЛА, КОТОРЫЕ ДЕЛАЮТ ИЗ РАЗНЫХ ГЕНЕРАЦИЙ ОДИН НАБОР (владелец 17.09: «рваные, нет общего
стилистического фона»):
  1. Одна палитра на всё — PALETTE ниже, снята с 27 иконок набора (play/assets/icons).
  2. Один свет и одна кромка у всех: тёмная кромка, светлый ряд под верхней, тень над нижней.
     Тонкая полоса не отдаёт под них всю себя — см. порог в styled_strip.
  3. Размер — ИЗ КАТАЛОГА: высота полосы = ширина куска (ING[k].wU × 5 мм) × мм на пиксель.
     Фактура рассчитана на размер НА ЛИСТЕ, а не на размер генерации.
  4. Клетка — 2 css px: вдвое мельче клетки риса (см. topCell в play/render/sheet.js).
  5. Повтор по длине — БЕЗ ЗЕРКАЛА, поэтому из кадра берётся длинный серединный отрезок.

ЗАПУСК.
  python3 tools/pixel-topview.py build --raw <папка с кадрами> [--out play/assets/topview] [ключи]
      пересобрать спрайты из УЖЕ СНЯТЫХ кадров (Draw Things не нужен);
  python3 tools/pixel-topview.py gen --raw <папка> [--seeds 7,11,23] [ключи]
      снять кадры заново (нужен запущенный Draw Things, см. tools/pixel-icons.py).

Кадры и выбранные варианты живут ВНЕ git (results, не исходник): runs/continuation/task13-topview/.
В git идут только этот файл и собранные спрайты. PICK ниже — это и есть запись выбора глазами:
из какой партии и с каким сидом взят кадр каждой начинки.
"""
import argparse, importlib.util, json, os, sys
from collections import Counter
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Палитра набора: 42 цвета. Снята с иконок, плюс белые и розовые, которых не хватало майо и
# розовому рису (владелец 17.09). Живёт здесь, а не отдельным json: это ИСХОДНИК инструмента.
PALETTE = [
    (34, 52, 43), (59, 42, 32), (74, 50, 32), (74, 68, 64), (121, 181, 92), (122, 82, 48),
    (141, 191, 76), (167, 196, 85), (176, 32, 62), (181, 121, 63), (183, 207, 134), (192, 57, 43),
    (224, 54, 74), (227, 192, 105), (228, 222, 214), (230, 221, 201), (232, 181, 81), (239, 138, 102),
    (239, 230, 212), (240, 210, 122), (242, 136, 63), (242, 179, 194), (243, 201, 79), (243, 227, 160),
    (244, 164, 140), (244, 167, 187), (244, 237, 226), (244, 242, 236), (246, 176, 47), (255, 255, 255),
    (208, 202, 190), (24, 22, 20), (60, 52, 44), (240, 236, 66), (207, 233, 121), (240, 157, 110),
    (173, 168, 84), (174, 61, 30), (161, 0, 5), (27, 35, 14), (35, 0, 3), (0, 0, 0),
]

# Ширина куска на листе, в единицах модели (5 мм) — ING[k].wU из play/model/catalog.js.
# Держится здесь копией НАМЕРЕННО: инструмент обязан работать без запуска игры. Расхождение
# ловит сторож §5а-секст в play/checks.js — он мерит спрайт против модельного размера куска.
WU = {'salmon': 2.0, 'tuna': 1.5, 'kanikama': 2.2, 'tamago': 2.4, 'avocado': 2.0, 'shiitake': 2.0,
      'cucumber': 2.8, 'kanpyo': 2.4, 'anago': 3.6, 'eggsheet': 10, 'nori': 2.4, 'naruto': 5.0,
      'banana': 6.4, 'mango': 8.0, 'mayo': 1.2, 'jam': 3.5, 'denbu': 6, 'ricePink': 4,
      'riceGreen': 4, 'riceYellow': 4, 'riceBlack': 4, 'shrimp': 2.0, 'strawberry': 5.0,
      'kiwi': 9.0, 'nut': 1.2}

# ⚠ У МАЙО И НАРУТО ШИРИНА ЗДЕСЬ НЕ РАВНА wU КАТАЛОГА, И ЭТО НЕ ОПЕЧАТКА. Майо в каталоге
# wU 0,8 (4 мм), но рисуется волнистой линией и шкуру пока не получает; наруто — кружок ⌀25 мм.
# Числа подобраны под ВИДИМЫЙ размер на листе; сторож сверяет не их, а то, что спрайт
# растягивается до модельного размера куска без обрезки.

STRIP = ('a long straight horizontal strip running across the whole image from the left edge '
         'to the right edge')
# key: (нарезка каталога, вид, описание). 'strip' — длинная полоса вдоль ролла, повторяется;
# 'item' — короткие кусочки, спрайт и есть рядок, он выкладывается по длине куска.
TABLE = {
 'salmon':     ('брусок', 'strip', 'a raw salmon stick seen from directly above, bright orange flesh with thin diagonal white fat lines'),
 'tuna':       ('брусок', 'strip', 'a raw tuna stick seen from directly above, bright deep red, smooth, fine white connective lines across'),
 'kanikama':   ('брусок', 'strip', 'a japanese crab stick seen from directly above, white fibrous body with a bright red orange stripe along the whole top edge'),
 'tamago':     ('брусок', 'strip', 'a stick of japanese rolled omelette seen from directly above, golden yellow with light brown spots'),
 'avocado':    ('брусок', 'strip', 'a long straight slice of avocado seen from directly above, even width, smooth bright yellow-green flesh, thin dark green skin line along the bottom edge'),
 'shiitake':   ('брусок', 'strip', 'a band of dark brown glossy simmered shiitake caps, seen from directly above, visible light stripes on each cap'),
 'cucumber':   ('сектор', 'strip', 'a cucumber stick seen from directly above, dark green skin with pale green flesh along the edge'),
 'kanpyo':     ('лист',   'strip', 'a ribbon of simmered kanpyo gourd seen from directly above, amber brown, glossy, slightly wrinkled'),
 'anago':      ('лист',   'strip', 'a flat fillet of grilled sea eel seen from directly above, glossy dark amber tare glaze with grill marks'),
 'eggsheet':   ('лист',   'strip', 'a flat ribbon of yellow egg crepe seen from directly above, vivid yellow, soft brown spots'),
 'nori':       ('лист',   'strip', 'a narrow strip of dark green nori seaweed seen from directly above, matte, fine texture'),
 'naruto':     ('кружок', 'strip', 'a narutomaki fish cake log, seen from directly above, white body with a bold pink stripe swirling along its whole length, scalloped pink edges'),
 'banana':     ('кружок', 'strip', 'a peeled banana lying straight, seen from directly above, creamy yellow body with three clear lengthwise ridges and a small brown tip, soft shadow along the bottom edge'),
 'mango':      ('брусок', 'strip', 'a strip of ripe mango flesh seen from directly above, bright orange, juicy'),
 'mayo':       ('паста',  'strip', 'a thick rope of white japanese mayonnaise piped in a tight zigzag, seen from directly above, bright white body, clear grey shadow along the lower side, small cream highlights'),
 'jam':        ('паста',  'strip', 'a thick line of bright red strawberry jam, seen from directly above, glossy with small seeds and light highlights'),
 'denbu':      ('присыпка', 'strip', 'a line of fluffy pink sakura denbu fish flakes, seen from directly above'),
 'ricePink':   ('присыпка', 'strip', 'a line of pink coloured sushi rice grains, seen from directly above'),
 'riceGreen':  ('присыпка', 'strip', 'a line of green coloured sushi rice grains, seen from directly above'),
 'riceYellow': ('присыпка', 'strip', 'a line of yellow coloured sushi rice grains, seen from directly above'),
 'riceBlack':  ('присыпка', 'strip', 'a line of black sesame coloured sushi rice grains, seen from directly above'),
 'shrimp':     ('полукруг', 'item', 'a boiled shrimp butterflied and flattened, seen from directly above, pink and white stripes, tail on'),
 'strawberry': ('брусок', 'item', 'three strawberry halves in a row, seen from directly above, red with tiny seeds, cut side down'),
 'kiwi':       ('брусок', 'item', 'three half slices of kiwi in a row, seen from directly above, bright green with black seeds'),
 'nut':        ('кружок', 'item', 'three roasted hazelnuts in a row, seen from directly above, warm brown'),
}

# ВЫБОР ГЛАЗАМИ, ЗАПИСАННЫЙ ЧИСЛОМ: откуда взят кадр каждой начинки. Партия 1 — по описанию из
# TABLE, сид 7; партии 2 и 3 — переписанные описания для слабых видов, несколько сидов, из них
# выбран один. Без этой таблицы «пересобрать спрайт» означало бы «сгенерировать другой».
PICK = {
 'avocado':  ('gen2/seed-7',  'avocado-v0'),
 'kanikama': ('gen2/seed-11', 'kanikama-v0'),
 'jam':      ('gen2/seed-23', 'jam-v0'),
 'eggsheet': ('gen2/seed-11', 'eggsheet-v1'),
 'tuna':     ('gen2/seed-23', 'tuna-v0'),
 'mayo':     ('gen3/seed-7',  'mayo-v0'),
 'banana':   ('gen3/seed-11', 'banana-v1'),
 'naruto':   ('gen3/seed-7',  'naruto-v0'),
 'shiitake': ('gen3/seed-7',  'shiitake-v1'),
}

PX_PER_MM = 1.9    # css px на мм у листа на телефоне (футомаки, 393 px в ширину) — замер layout
CELL = 2           # css px на клетку куска: вдвое мельче клетки риса (topCell в sheet.js)
U_MM = 5           # единица модели

_pi = None
def pixel_icons():
    """tools/pixel-icons.py: key_out (вырез ключевого фона) и generate (Draw Things)."""
    global _pi
    if _pi is None:
        spec = importlib.util.spec_from_file_location('pi', os.path.join(HERE, 'pixel-icons.py'))
        _pi = importlib.util.module_from_spec(spec); spec.loader.exec_module(_pi)
    return _pi


def lum(c): return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
DARK = min(PALETTE, key=lum)

def near(c):
    """Ближайший цвет палитры, по светлоте важнее, чем по тону: банды должны совпасть у всех."""
    return min(PALETTE, key=lambda p: (p[0] - c[0]) ** 2 * 0.3 + (p[1] - c[1]) ** 2 * 0.59 + (p[2] - c[2]) ** 2 * 0.11)

def lighter(c):
    cands = [p for p in PALETTE if lum(p) > lum(c) + 18]
    return min(cands, key=lambda p: sum((a - b) ** 2 for a, b in zip(p, c)) + 4 * (lum(p) - lum(c)) ** 2) if cands else c

def darker(c):
    cands = [p for p in PALETTE if lum(p) < lum(c) - 18]
    return min(cands, key=lambda p: sum((a - b) ** 2 for a, b in zip(p, c)) + 4 * (lum(p) - lum(c)) ** 2) if cands else c


def mode_down(img, w, h):
    """Уменьшение ВЫБОРОМ ПРЕОБЛАДАЮЩЕГО цвета, а не усреднением: среднее даёт грязь между
    двумя цветами и убивает пиксельность (то же правило, что в tools/pixel-icons.py)."""
    img = img.convert('RGBA'); W, H = img.size
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0)); p = img.load()
    for j in range(h):
        for i in range(w):
            x0, y0 = int(i * W / w), int(j * H / h)
            x1, y1 = max(x0 + 1, int((i + 1) * W / w)), max(y0 + 1, int((j + 1) * H / h))
            c = Counter()
            for y in range(y0, min(y1, H)):
                for x in range(x0, min(x1, W)):
                    r, g, b, a = p[x, y]
                    c[None if a < 128 else near((r, g, b))] += 1
            win = c.most_common(1)[0][0]
            out.putpixel((i, j), (0, 0, 0, 0) if win is None else (*win, 255))
    return out


def raw_band(key, rawdir):
    """Кадр генерации → область фактуры. У полосы берётся СЕРЕДИНА по длине: края кадра рваные,
    а шов повтора не должен быть зеркальным, значит нужен длинный однородный отрезок."""
    pi = pixel_icons()
    sub, name = PICK.get(key, ('gen/seed-7', key))
    path = os.path.join(rawdir, sub, 'raw-' + name + '.png')
    if not os.path.exists(path):
        return None, TABLE[key][1]
    raw = Image.open(path).convert('RGB')
    a = pi.key_out(raw.copy()); bb = a.getbbox()
    if TABLE[key][1] == 'strip':
        return a.crop((raw.width // 5, bb[1], raw.width * 4 // 5, bb[3])), 'strip'
    return a.crop(bb), 'item'


def styled_strip(band, key, cell=CELL):
    h = max(3, round(WU[key] * U_MM * PX_PER_MM / cell))
    w = max(8, round(band.width * h / band.height))
    s = mode_down(band, w, h)
    px = s.load()
    # Полоса на листе СПЛОШНАЯ: дырки внутри — мусор генерации, а не форма. Форму задаёт модель.
    for i in range(w):
        col = [px[i, j] for j in range(h) if px[i, j][3]]
        fill = col[len(col) // 2] if col else (*near((200, 200, 200)), 255)
        for j in range(h):
            if not px[i, j][3]:
                px[i, j] = fill
    # ⚑ СВЕТ И КРОМКА ОДИНАКОВЫЕ У ВСЕХ, НО ТОНКАЯ ПОЛОСА НЕ ОТДАЁТ ПОД НИХ ВСЮ СЕБЯ.
    # У майо на листе 6 мм — это 6 пикселей: две тёмные кромки плюс блик и тень съедали заливку,
    # и жгут выходил тёмным пунктиром. Поэтому: от 8 пикселей — кромка с обеих сторон, блик и
    # тень; 5–7 — кромка только снизу (свет сверху) и блик; тоньше — только нижняя кромка.
    for i in range(w):
        if h >= 8:
            px[i, 1] = (*lighter(px[i, 1][:3]), 255); px[i, h - 2] = (*darker(px[i, h - 2][:3]), 255)
            px[i, 0] = (*DARK, 255); px[i, h - 1] = (*DARK, 255)
        elif h >= 5:
            px[i, 0] = (*lighter(px[i, 0][:3]), 255); px[i, h - 1] = (*DARK, 255)
        else:
            px[i, h - 1] = (*darker(px[i, h - 1][:3]), 255)
    return s


def styled_item(obj, key, cell=CELL):
    h = max(4, round(WU[key] * U_MM * PX_PER_MM / cell * 0.9))
    w = max(4, round(obj.width * h / obj.height))
    s = mode_down(obj, w, h)
    px = s.load(); W, H = s.size
    # У коротких кусочков кромка идёт по СИЛУЭТУ: отсюда и рядок читается как отдельные кусочки.
    edge = [(x, y) for y in range(H) for x in range(W) if px[x, y][3] and any(
        not (0 <= x + dx < W and 0 <= y + dy < H) or not px[x + dx, y + dy][3]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    for x, y in edge:
        px[x, y] = (*DARK, 255)
    return s


def build(keys, rawdir, outdir, cell=CELL):
    os.makedirs(outdir, exist_ok=True)
    сделано, нет_кадра = [], []
    for k in keys:
        band, kind = raw_band(k, rawdir)
        if band is None:
            нет_кадра.append(k); continue
        spr = styled_strip(band, k, cell) if kind == 'strip' else styled_item(band, k, cell)
        p = os.path.join(outdir, k + '.png')
        spr.save(p, optimize=True)
        сделано.append(f'{k} {spr.size[0]}×{spr.size[1]} {os.path.getsize(p)} б')
    print('собрано:', ', '.join(сделано) or 'ничего')
    if нет_кадра:
        print('НЕТ КАДРА (снять через gen):', ', '.join(нет_кадра), file=sys.stderr)
    return not нет_кадра


def gen(keys, rawdir, seeds):
    """Съёмка кадров. Нужен запущенный Draw Things — без него это не работает и не должно:
    подделывать кадр нечем."""
    pi = pixel_icons()
    for seed in seeds:
        d = os.path.join(rawdir, f'gen/seed-{seed}')
        os.makedirs(d, exist_ok=True)
        for k in keys:
            cut, kind, what = TABLE[k]
            prompt = (f'pixel-art top-down view of {what}'
                      + (f', {STRIP}' if kind == 'strip' else ', single row centered')
                      + ' . low-res, blocky, pixel art style, 8-bit graphics, flat solid magenta background, game texture')
            size = (768, 192) if kind == 'strip' else (512, 256)
            raw = pi.generate(prompt, w=size[0], h=size[1], seed=seed, loras=pi.LORA_PIXEL)
            raw.save(os.path.join(d, 'raw-' + k + '.png'))
            print('снят', k, cut, kind, seed, flush=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('команда', choices=['build', 'gen', 'table'])
    ap.add_argument('--raw', default=None, help='папка с кадрами генерации (вне git)')
    ap.add_argument('--out', default=os.path.join(ROOT, 'play/assets/topview'))
    ap.add_argument('--cell', type=float, default=CELL, help='css px на клетку куска (по умолчанию 2)')
    ap.add_argument('--seeds', default='7,11,23')
    ap.add_argument('ключи', nargs='*', help='начинки; пусто — все из TABLE')
    a = ap.parse_args()
    keys = a.ключи or list(TABLE)
    if a.команда == 'table':
        print(json.dumps({k: {'cut': v[0], 'kind': v[1], 'what': v[2],
                              'pick': PICK.get(k, ('gen/seed-7', k)), 'wU': WU[k]}
                          for k, v in TABLE.items()}, ensure_ascii=False, indent=1))
    elif a.команда == 'gen':
        if not a.raw:
            ap.error('--raw обязателен: кадры хранятся вне git')
        gen(keys, a.raw, [int(s) for s in a.seeds.split(',')])
    else:
        if not a.raw:
            ap.error('--raw обязателен: собирать спрайт можно только из снятого кадра')
        sys.exit(0 if build(keys, a.raw, a.out, a.cell) else 1)
