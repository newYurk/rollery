"""НЕКРУГЛОСТЬ НАСТОЯЩЕГО РОЛЛА ПО ФОТОГРАФИИ.

Меряет ТУ ЖЕ величину, что называет сторож стенда (play/checks.js:98):

    некруглость = 100 · (r_макс − r_мин) / r_медиана     по 360 лучам из центроида

Зачем. В списке «чего в источниках нет вообще» (play/test/practice.js, PRACTICE_UNKNOWN)
первой строкой стоит: «Некруглость настоящего ролла — не измерена никем. Наши пороги
ROUND_MAX стоят на пустом месте». ROUND_MAX = 8 % при нейтральной руке — догадка. Этот
скрипт нужен, чтобы догадку заменить замером, когда найдётся годный снимок.

⚠ ЧТО ТАКОЕ ГОДНЫЙ СНИМОК, И ПОЧЕМУ ЗАМЕРА ПОКА НЕТ (проверено 31.08.2026).
Обход профессиональных источников — JSIA/東京すしアカデミー, 農林水産省 «うちの郷土料理:
太巻ずし 千葉県», Wikimedia Commons — дал десятки снимков срезов, и ни одного пригодного:

  · всё снято в ТРИ ЧЕТВЕРТИ, а не анфас. Перспектива сжимает одну ось, и отношение сторон
    выходит завышенным: у ролла с фото JSIA габарит дал 1,43, но это ракурс, а не форма;
  · ломтики лежат ВПЛОТНУЮ и сливаются в одну связную область — по отдельности не выделить
    (замер 31.08: четыре ломтика JSIA слиплись в кусок 2015×1256 px);
  · тесный кроп ломает автоподбор цвета фона: эталон берётся из углов, а в тесном кропе
    углы — уже сам ролл. Отсюда параметр `ref`: фон можно задать явно.

Нужен ОДИН ломтик, АНФАС, на ровном фоне. Такой снимок у мастеров пока не найден.

Как звать:
    python tools/roundness-from-photo.py фото.jpg x0 y0 x1 y1
"""

import sys, math, collections
import numpy as np
from PIL import Image

def hsv(a):
    r, g, b = a[..., 0] / 255., a[..., 1] / 255., a[..., 2] / 255.
    mx, mn = np.max(a, 2) / 255., np.min(a, 2) / 255.
    v = mx; s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return s, v

def segment(img, tol=34.0, ref=None):
    """Фон определяется НЕ порогом яркости, а цветом самого кадра.

    Первая редакция считала фоном «светлое и малонасыщенное» — и белый рис внутри ролла
    попадал под это правило вместе с блюдом. Теперь цвет блюда берётся из УГЛОВ кропа
    (там заведомо блюдо), и фон — то, что от него недалеко. Блюдо голубовато-серое, рис
    тёплый: по цвету они расходятся, по яркости почти нет.
    """
    a = np.asarray(img).astype(np.float32)
    H, W, _ = a.shape
    k = max(4, min(H, W) // 12)
    corners = np.concatenate([a[:k, :k].reshape(-1, 3), a[:k, -k:].reshape(-1, 3),
                              a[-k:, :k].reshape(-1, 3), a[-k:, -k:].reshape(-1, 3)])
    ref = np.array(ref, np.float32) if ref is not None else np.median(corners, 0)
    d = np.sqrt(((a - ref) ** 2).sum(2))
    bg = d < tol
    out = np.zeros_like(bg)
    dq = collections.deque()
    for x in range(W):
        for y in (0, H - 1):
            if bg[y, x] and not out[y, x]: out[y, x] = True; dq.append((y, x))
    for y in range(H):
        for x in (0, W - 1):
            if bg[y, x] and not out[y, x]: out[y, x] = True; dq.append((y, x))
    while dq:
        y, x = dq.popleft()
        for dy, dx in ((1,0),(-1,0),(0,1),(0,-1)):
            ny, nx = y+dy, x+dx
            if 0 <= ny < H and 0 <= nx < W and bg[ny,nx] and not out[ny,nx]:
                out[ny,nx] = True; dq.append((ny,nx))
    return ~out

def largest(mask):
    H, W = mask.shape; lab = np.zeros((H,W), np.int32); n = 0; best = (0, None)
    for y0 in range(H):
        for x0 in range(W):
            if mask[y0,x0] and lab[y0,x0] == 0:
                n += 1; dq = collections.deque([(y0,x0)]); lab[y0,x0] = n; cnt = 0
                while dq:
                    y,x = dq.popleft(); cnt += 1
                    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny,nx = y+dy, x+dx
                        if 0<=ny<H and 0<=nx<W and mask[ny,nx] and lab[ny,nx]==0:
                            lab[ny,nx]=n; dq.append((ny,nx))
                if cnt > best[0]: best = (cnt, n)
    return lab == best[1], best[0]

def roundness(mask, N=360):
    ys, xs = np.nonzero(mask)
    cy, cx = ys.mean(), xs.mean()
    R = int(max(mask.shape))
    rs = []
    for i in range(N):
        a = 2*math.pi*i/N; dy, dx = math.sin(a), math.cos(a)
        last = 0
        for k in range(1, R*2):
            r = k*0.5; y, x = int(round(cy+dy*r)), int(round(cx+dx*r))
            if not (0 <= y < mask.shape[0] and 0 <= x < mask.shape[1]): break
            if mask[y, x]: last = r
        rs.append(last)
    rs = np.array(sorted(rs))
    med = rs[N//2]
    return dict(центр=(round(cx,1), round(cy,1)), r_мин=round(float(rs[0]),1),
                r_мед=round(float(med),1), r_макс=round(float(rs[-1]),1),
                некруглость=round(float(100*(rs[-1]-rs[0])/med),1),
                отношение_осей=round(float(rs[-1]/rs[0]),2))

if __name__ == '__main__':
    f, x0, y0, x1, y1 = sys.argv[1], *map(int, sys.argv[2:6])
    im = Image.open(f).convert('RGB').crop((x0, y0, x1, y1))
    im = im.resize((im.width*3, im.height*3), Image.LANCZOS)
    m = segment(im)
    m, n = largest(m)
    print(f'{f} [{x0},{y0}-{x1},{y1}] пикселей ролла: {n}')
    print(' ', roundness(m))
    Image.fromarray((m*255).astype(np.uint8)).save(f.replace('.jpg','')+f'_seg{x0}.png')
