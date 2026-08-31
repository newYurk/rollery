"""НАКЛОН КАМЕРЫ ПО КРУГЛОЙ ТАРЕЛКЕ — как отобрать снимок, годный для замера среза.

ЗАЧЕМ. Ломтики на снимках стоят срезом вверх, то есть плоскость среза параллельна тарелке.
Круглый ободок лежит в той же плоскости — значит его эллипс на снимке И ЕСТЬ то искажение,
которым искажены все срезы. Померив эллипс, получаем наклон камеры числом.

Из этого выходит не оправдание, а СИТО: снимки можно упорядочить по пригодности.

Замер 31.08.2026 по найденным профессиональным снимкам:

    農水省 房総 (maff3)     сжатие 1,33 · наклон 41° ← лучший из найденных
    農水省 房総 (maff1)     сжатие 1,55 · наклон 50°
    JSIA краб    (pro6)     сжатие 1,89 · наклон 58°
    эхомаки      (cand6)    сжатие 2,47 · наклон 66°

Ни один не годится: даже 41° это далеко не отвес, а при таком наклоне в силуэт ломтика
входит его БОКОВАЯ СТЕНКА, и никакая коррекция по тарелке её не уберёт — тарелка правит
плоскость, а стенка из плоскости торчит. Нужен снимок, где наклон меньше примерно 15°.

⚠ Что коррекция ПО ТАРЕЛКЕ всё-таки чинит, а что нет:
  · чинит — сжатие плоскости среза (аффинное, одно на весь кадр);
  · НЕ чинит — боковую стенку, попавшую в силуэт при большом наклоне;
  · не нужно чинить — высоту ломтика над тарелкой: она даёт лишь равномерное увеличение,
    а мерка (r_макс − r_мин)/r_медиана от масштаба не зависит.

Эллипс строится по ДУГЕ ободка методом наименьших квадратов (fit_conic), а не по вторым
моментам: тарелку закрывают сами ролики, видимая её часть — серп, и моменты серпа врут.
Точки на рамке кадра выбрасываются — там граница не ободок, а обрез снимка.

Пара к tools/roundness-from-photo.py: сначала этим отобрать кадр, потом тем померить.
"""

import math, collections
import numpy as np
from PIL import Image

def biggest_blob(mask):
    H, W = mask.shape; lab = np.zeros((H,W), np.int32); n=0; best=(0,None)
    for y0 in range(H):
        for x0 in range(W):
            if mask[y0,x0] and lab[y0,x0]==0:
                n+=1; dq=collections.deque([(y0,x0)]); lab[y0,x0]=n; c=0
                while dq:
                    y,x=dq.popleft(); c+=1
                    for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)):
                        ny,nx=y+dy,x+dx
                        if 0<=ny<H and 0<=nx<W and mask[ny,nx] and lab[ny,nx]==0:
                            lab[ny,nx]=n; dq.append((ny,nx))
                if c>best[0]: best=(c,n)
    return lab==best[1]

def ellipse_axes(mask):
    """Полуоси и угол эллипса по вторым моментам заполненной области."""
    ys, xs = np.nonzero(mask)
    cy, cx = ys.mean(), xs.mean()
    y, x = ys-cy, xs-cx
    cov = np.array([[ (x*x).mean(), (x*y).mean() ], [ (x*y).mean(), (y*y).mean() ]])
    w, v = np.linalg.eigh(cov)
    order = np.argsort(w)[::-1]
    w, v = w[order], v[:, order]
    a, b = 2*math.sqrt(w[0]), 2*math.sqrt(w[1])   # для сплошного эллипса λ = (полуось)²/4
    ang = math.degrees(math.atan2(v[1,0], v[0,0]))
    return (cx, cy), a, b, ang


def boundary_points(mask, drop_frame=True):
    """Точки границы области. Пиксели на рамке кадра выбрасываются: там граница — не ободок
    тарелки, а обрез снимка, и она увела бы подгонку."""
    H, W = mask.shape
    m = mask
    edge = m & ~(np.roll(m,1,0) & np.roll(m,-1,0) & np.roll(m,1,1) & np.roll(m,-1,1))
    ys, xs = np.nonzero(edge)
    if drop_frame:
        keep = (xs > 1) & (ys > 1) & (xs < W-2) & (ys < H-2)
        ys, xs = ys[keep], xs[keep]
    return xs.astype(float), ys.astype(float)


def fit_conic(x, y):
    """Эллипс по точкам: A x² + B xy + C y² + D x + E y + F = 0, наименьшие квадраты через SVD.

    Работает по ДУГЕ — этим и отличается от вторых моментов, которым нужна вся фигура.
    Возвращает (центр, большая полуось, малая полуось, угол в градусах).
    """
    sx, sy = x.mean(), y.mean()
    sc = max(x.std(), y.std())
    u, v = (x - sx) / sc, (y - sy) / sc                  # нормировка: без неё SVD плывёт
    D = np.column_stack([u*u, u*v, v*v, u, v, np.ones_like(u)])
    _, _, Vt = np.linalg.svd(D, full_matrices=False)
    A, B, C, Dc, E, F = Vt[-1]
    M = np.array([[A, B/2], [B/2, C]])
    if np.linalg.det(M) <= 0: return None                # не эллипс
    cen = np.linalg.solve(2*M, [-Dc, -E])
    val = A*cen[0]**2 + B*cen[0]*cen[1] + C*cen[1]**2 + Dc*cen[0] + E*cen[1] + F
    w, vec = np.linalg.eigh(M / (-val))
    if np.any(w <= 0): return None
    ax = 1/np.sqrt(w)
    order = np.argsort(ax)[::-1]
    ax, vec = ax[order], vec[:, order]
    import math
    return ((cen[0]*sc + sx, cen[1]*sc + sy), ax[0]*sc, ax[1]*sc,
            math.degrees(math.atan2(vec[1,0], vec[0,0])))
