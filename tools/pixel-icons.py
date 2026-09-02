#!/usr/bin/env python3
"""Иконки-спрайты для «Ролльни»: генерация в Draw Things → настоящая пиксельная сетка → PNG с альфой.

ПОЧЕМУ НЕ ПРОСТО ГЕНЕРАЦИЯ. Модель рисует КАРТИНКУ, ПОХОЖУЮ на пиксель-арт: пиксели у неё
неровные, с переходными оттенками и сглаженными краями. Если взять её как есть, получится
ровно та же беда, что и с квантованием нашего рендера — «картинка квадратиками».
Поэтому после генерации:
  1. сажаем на СЕТКУ: уменьшаем до арт-разрешения выбором ПРЕОБЛАДАЮЩЕГО цвета в блоке
     (не усреднением — среднее даёт грязь между двумя цветами);
  2. прижимаем к ограниченной палитре (медианный срез по фактическим цветам);
  3. вырезаем фон: генерим на ключевом цвете (маджента — в еде не встречается), убираем его
     в альфу, и чистим ореол.
Результат — настоящий спрайт: N×N осмысленных пикселей, которые можно править руками.

Прозрачность сама модель не умеет: диффузия отдаёт непрозрачный RGB. Ключевой цвет — то, как
это делали всегда, и для плоского фона оно работает надёжно.
"""
import base64, io, json, os, sys, urllib.request
from collections import Counter
from PIL import Image

API = 'http://127.0.0.1:7860/sdapi/v1/txt2img'
KEY = (255, 0, 255)          # маджента: ключевой цвет фона
ART = 40                     # сторона спрайта в арт-пикселях
PALETTE = 12                 # сколько цветов оставить


def generate(prompt, neg=None, w=320, h=320, steps=8, seed=7, cfg=1, loras=None, sampler='Euler A Trailing'):
    # ⚠ У Flux.2 негативного промпта НЕТ: модель дистиллированная, идёт на guidance 1, и
    # отрицание попросту не участвует в расчёте (указание владельца 31.08). Раньше он
    # передавался и создавал ложное ощущение, что чем-то управляет.
    # Сэмплер: Euler A Trailing — он для Flux и родствен ему по расписанию шума. Замер 31.08
    # на одном seed: DPM++ SDE Karras даёт мутную картинку с фиолетовой каймой (он рассчитан на
    # другую модель), UniPC Trailing чистый, Euler A Trailing самый контрастный — берём его.
    body = {'prompt': prompt, 'steps': steps, 'sampler_name': sampler,
            'width': w, 'height': h, 'seed': seed, 'guidance_scale': cfg}
    if loras: body['loras'] = loras
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=300) as r:
        d = json.load(r)
    if not d.get('images'):
        raise RuntimeError('модель ничего не вернула: ' + json.dumps(d)[:200])
    return Image.open(io.BytesIO(base64.b64decode(d['images'][0]))).convert('RGB')


def to_grid(img, art=ART):
    """Уменьшение ВЫБОРОМ ПРЕОБЛАДАЮЩЕГО цвета блока, а не усреднением.

    Работает по RGBA и считает прозрачность наравне с цветом: если в блоке преобладает фон,
    клетка остаётся прозрачной. Так граница спрайта получается ступенчатой и чистой, без
    полупрозрачной каймы — усреднение дало бы кайму, а с ней и «мыло» на краю.
    """
    img = img.convert('RGBA')
    W, H = img.size
    bw, bh = W / art, H / art
    out = Image.new('RGBA', (art, art), (0, 0, 0, 0))
    px = img.load()
    for j in range(art):
        for i in range(art):
            x0, y0 = int(i * bw), int(j * bh)
            x1, y1 = max(x0 + 1, int((i + 1) * bw)), max(y0 + 1, int((j + 1) * bh))
            c = Counter()
            for y in range(y0, min(y1, H)):
                for x in range(x0, min(x1, W)):
                    r, g, b, a = px[x, y]
                    c[None if a < 128 else (r >> 4 << 4, g >> 4 << 4, b >> 4 << 4)] += 1
            win = c.most_common(1)[0][0]
            out.putpixel((i, j), (0, 0, 0, 0) if win is None else (*win, 255))
    return out


def limit_palette(img, n=PALETTE):
    """Сведение к n цветам ТОЛЬКО среди непрозрачных точек: прозрачные не должны тратить
    места в палитре и тянуть на себя ближайшие оттенки."""
    img = img.convert('RGBA')
    rgb = img.convert('RGB').convert('P', palette=Image.ADAPTIVE, colors=n).convert('RGB')
    out = Image.new('RGBA', img.size, (0, 0, 0, 0))
    a = img.getchannel('A')
    out.paste(rgb, (0, 0), a)
    return out


def key_out(img, tol=60):
    """Фон → альфа. Цвет фона берётся С КРАЯ картинки, а не задаётся числом.

    ⚠ Первая редакция сравнивала с эталонной маджентой (255,0,255) и не срабатывала: сведение
    к 12 цветам сдвигает фон в соседний оттенок (замерено: стал ≈191,0,160 — от эталона на 159
    по сумме модулей, при допуске 90). Преобладающий цвет рамки надёжен при любом сдвиге.
    Заливка ведётся ОТ КРАЯ (заливка связной области), поэтому такой же цвет внутри спрайта
    не выгрызается — важно, если в еде окажется розовое.
    """
    img = img.convert('RGBA')
    px = img.load(); W, H = img.size
    edge = Counter()
    for x in range(W):
        edge[px[x, 0][:3]] += 1; edge[px[x, H - 1][:3]] += 1
    for y in range(H):
        edge[px[0, y][:3]] += 1; edge[px[W - 1, y][:3]] += 1
    bg = edge.most_common(1)[0][0]
    near = lambda c: abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) < tol
    stack = [(0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)]
    seen = set()
    while stack:
        x, y = stack.pop()
        if (x, y) in seen or not (0 <= x < W and 0 <= y < H):
            continue
        seen.add((x, y))
        if not near(px[x, y][:3]):
            continue
        px[x, y] = (0, 0, 0, 0)
        stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

    # ВТОРОЙ ПРОХОД: фон, ЗАПЕРТЫЙ ВНУТРИ силуэта — в завитке майо, в кольце креветки. Заливка
    # от края туда не доходит по построению, и пятно оставалось.
    # ⚠ Сравнивать надо с ОБНАРУЖЕННЫМ цветом, а не с эталонной маджентой: модель рисует фон
    # НЕ таким, как просили. Замер 31.08 — просили magenta (255,0,255), получили тёмно-малиновый
    # (157,15,83) у майо и (178,12,90) у креветки. Жёсткий порог по «чистой мадженте» их
    # не ловил, а обнаруженный цвет ловит при любом оттенке.
    for y in range(H):
        for x in range(W):
            if px[x, y][3] and near(px[x, y][:3]):
                px[x, y] = (0, 0, 0, 0)

    # ОРЕОЛ: точки, у которых не осталось непрозрачных соседей, — обрывки кромки, не деталь.
    doomed = []
    for y in range(H):
        for x in range(W):
            if not px[x, y][3]:
                continue
            n = sum(1 for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))
                    if 0 <= x+dx < W and 0 <= y+dy < H and px[x+dx, y+dy][3])
            if n == 0:
                doomed.append((x, y))
    for x, y in doomed:
        px[x, y] = (0, 0, 0, 0)
    return img


def make(key_name, what, outdir, seed=7, loras=None):
    # ФОРМУЛИРОВКА СТИЛЯ — дословно из пресета sai-pixel-art, который владелец выбрала в
    # приложении (31.08). Пресет — это не модель и не LoRA, а обёртка промпта, и на генерации
    # через API он не действует: запрос идёт мимо интерфейса. Поэтому его слова повторены здесь.
    # Негативная половина пресета опущена: у Flux.2 негативного промпта нет.
    prompt = (f'pixel-art {what} . low-res, blocky, pixel art style, 8-bit graphics, '
              'single object centered, flat solid magenta background, game item icon')
    raw = generate(prompt, seed=seed, loras=loras)
    raw.save(os.path.join(outdir, f'raw-{key_name}.png'))
    # ⚠ ПОРЯДОК ВАЖЕН: фон вырезается ДО квантования, пока маджента ещё чистая. Сведение к
    # десяти цветам сдвигало её в тёмно-вишнёвый (замер: 144,0,80), и от красной полоски
    # креветки она становилась неотличима — запертые куски фона оставались пятнами.
    sprite = limit_palette(to_grid(key_out(raw)), PALETTE)
    p = os.path.join(outdir, f'{key_name}.png')
    sprite.save(p)
    # и увеличенная копия, чтобы смотреть глазами
    sprite.resize((ART * 8, ART * 8), Image.NEAREST).save(os.path.join(outdir, f'{key_name}@8x.png'))
    solid = sum(1 for p_ in sprite.getdata() if p_[3] > 0)
    print(f'{key_name}: {ART}×{ART}, непрозрачных {solid}, цветов {len(set(sprite.getdata()))}')
    return p


# ЧТО ИЗОБРАЖАЕТ ИКОНКА — решение, а не мелочь: она должна показывать то, что игрок КЛАДЁТ.
# Огурец сперва просился «палочкой» и выходил похожим на карандаш с одиноким бликом; в ролл
# кладут несколько брусочков — пучок и узнаётся сразу, и честен (владелец 31.08).
ITEMS = [
    ('salmon',   'a raw salmon fillet slice, orange with white fat stripes'),
    ('cucumber', 'a small bundle of three cucumber sticks lying side by side, dark green skin'),
    ('tamago',   'a block of japanese rolled omelette, golden yellow with visible layers'),
    ('avocado',  'an avocado half, bright green flesh with a big brown pit'),
    ('shrimp',   'a cooked shrimp, pink and white striped, curled'),
    ('nori',     'a folded sheet of dark green nori seaweed, matte'),
    ('mayo',     'a swirl of white mayonnaise sauce'),
    ('ricePink', 'a small mound of pink coloured sushi rice, grains visible'),
    ('riceGreen','a small mound of green coloured sushi rice, grains visible'),
    # Второй заход 02.09 (#157): палитра стенда росла с 9 до 15, и шесть новых выбраны не
    # «для разнообразия», а по канону футомаки из canon.js — кампё, шиитакэ, краб-палочка
    # достраивают праздничный ряд CANON7_ORDER до собираемого игроком. Тунец взят против
    # лосося (тот же приём, другой цвет), наруто — единственный материал со своей спиралью
    # на срезе, угорь — единственное тёмно-глянцевое в наборе.
    ('tuna',     'a raw tuna fillet slice, deep red with fine pale sinew lines'),
    ('kanikama', 'a japanese crab stick, white with red outer skin, one end cut showing fibres'),
    ('naruto',   'a slice of narutomaki fish cake, white disc with a pink spiral and scalloped edge'),
    ('shiitake', 'a simmered shiitake mushroom cap, dark brown with a pale cross-shaped crack on top'),
    ('kanpyo',   'three simmered kanpyo gourd ribbons, amber brown, glossy, lying side by side'),
    ('anago',    'a piece of grilled sea eel fillet glazed with dark tare sauce, glossy amber'),
]

# LoRA подключается ПРЯМО В ЗАПРОСЕ — проверено 31.08: API её принимает, а вот выбор в
# интерфейсе на генерации через API не влияет (как и стиль-пресет).
LORA_PIXEL = [{'file': 'limbicnation_pixel_art_lora_lora_f16.ckpt', 'weight': 1.0}]

def rebuild(outdir):
    """Пересобрать спрайты из сохранённых сырых кадров — без обращения к модели."""
    for k, _ in ITEMS:
        raw_p = os.path.join(outdir, f'raw-{k}.png')
        if not os.path.exists(raw_p):
            continue
        raw = Image.open(raw_p).convert('RGB')
        spr = limit_palette(to_grid(key_out(raw)), PALETTE)
        spr.save(os.path.join(outdir, f'{k}.png'))
        spr.resize((ART * 8, ART * 8), Image.NEAREST).save(os.path.join(outdir, f'{k}@8x.png'))
        solid = sum(1 for q in spr.getdata() if q[3] > 0)
        print(f'{k}: непрозрачных {solid}')


if __name__ == '__main__':
    outdir = sys.argv[1] if len(sys.argv) > 1 else '.'
    os.makedirs(outdir, exist_ok=True)
    args = sys.argv[2:]
    if 'rebuild' in args:
        rebuild(outdir); sys.exit(0)
    loras = LORA_PIXEL if 'lora' in args else None
    only = [a for a in args if a != 'lora'] or None
    for k, what in ITEMS:
        if only and k not in only:
            continue
        try:
            make(k, what, outdir, loras=loras)
        except Exception as e:
            print(f'{k}: ОШИБКА — {e}')
