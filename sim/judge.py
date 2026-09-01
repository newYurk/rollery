#!/usr/bin/env python3
"""Common, attempt-agnostic judging metrics for kin-grab / kin-mat outputs.

Reads out*/particles_<L>.npz + metrics_<L>.json, recomputes every number with ONE
implementation so the two attempts are compared on the same ruler.
"""
import importlib.util, json, math, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import fold                                  # одно определение посадки края на всю лабораторию


def geometry(mod):
    """Sheet geometry of the attempt being judged, read from ITS OWN run.py.

    These four numbers used to be hardcoded here as T = 1.0, W = 0.12, L_SHEET = 38.7, L_FLAP = 5.0.
    That was fine only while every attempt shared them. reference2 corrected its thicknesses to the
    sourced ones on 26.08.2026 (rice bed 1.4 U = 7 mm, nori 0.02 U = 0.1 mm, sheet 42 U = 21 cm) and
    renamed `T` to `T_RICE`, so a hardcoded copy here would silently judge a reference2 dump with the
    old spiral pitch. Both spellings are accepted; nothing is guessed.
    """
    t_rice = getattr(mod, 'T_RICE', None)
    if t_rice is None:
        t_rice = mod.T                       # attempts predating the 26.08.2026 rename
    w = mod.W_NORI
    pitch = getattr(mod, 'H_SHEET', t_rice + w)
    return t_rice, w, mod.L_SHEET, mod.L_FLAP, pitch


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def predicted(mod, L):
    lay = mod.LAYOUTS[L]
    xs, cls, vol, nr, nc, info = mod.sample_layout(lay, 16000)
    T, W, L_SHEET, L_FLAP, PITCH = geometry(mod)
    a_rice = (L_SHEET - L_FLAP) * T
    a_nori = L_SHEET * W
    a_fill = info['area_fill']
    A = a_rice + a_nori + a_fill
    Rout = math.sqrt(A / math.pi)
    # Посадка ближнего края. Судья берёт её из ОБЩЕГО МОДУЛЯ sim/fold.py — одного на всех, —
    # а не у прогона. И это осознанная разница с геометрией двумя функциями выше: геометрию
    # спрашивают у самой попытки (getattr(mod, 'T_RICE'), mod.W_NORI, mod.L_SHEET), потому что
    # у попыток она РАЗНАЯ и это законно. Правило посадки одно на всех — иначе судья мерил бы
    # каждого его собственной линейкой и сравнивать было бы нечего.
    # ⚠ Не переписывать это на «спрашиваю у прогона»: правило посадки одно на всех, иначе
    # судья мерил бы каждого его собственной линейкой и сравнивать было бы нечего (#113).
    # ⚠ СУДЬЯ МЕРЯЕТ ВСЕХ ОДНОЙ ЛИНЕЙКОЙ, И ЛИНЕЙКА ТЕПЕРЬ ИСПРАВЛЕНА. Прогоны, сделанные до
    # 31.08.2026, крутились по старому правилу (конец начинок + 1 T, потолок 0,45 L) — их
    # s_fold в дампах не совпадёт с этим числом. Это не сбой судьи, а сам результат: он и
    # показывает, насколько старые прогоны недоводили край. Подгонять линейку под дамп нельзя,
    # иначе судья перестанет судить.
    s_fold = fold.fold_landing(L_SHEET, L_FLAP)
    # ⚠ ЭТА ФОРМУЛА ВЫРОДИЛАСЬ ПОСЛЕ ИСПРАВЛЕНИЯ ПОСАДКИ 31.08 — печатается, но не годится
    # как предсказание. Rcore = sqrt(s_fold·h/π) писалась, когда s_fold был маленькой зоной
    # сгиба у ближнего края. Теперь s_fold — вся длина риса (87 % листа), и формула объявляет
    # ядром почти весь ролл: на раскладке 1 она даёт Rcore 3,466 против Rout 3,494, то есть
    # layers ≈ 0,02 вместо примерно витка. Разбор — sim/mat-sdf/run.py, predict_layers.
    #
    # Ролл в ОДИН оборот не имеет кольца витков снаружи ядра — считать его как «ядро плюс
    # намотка» больше нечего. Рабочей осталась третья форма, layers_close: она отсчитывает от
    # ФИЗИЧЕСКОГО радиуса сгиба R_fold, а не от площади свёрнутой длины, и в том же замере
    # сошлась (2,444 измеренных пересечения против 2,62 при допуске 0,25). Судья её не считает:
    # R_fold известен только внутри прогона.
    #
    # Числа ниже оставлены, а не удалены, потому что на них ссылаются прежние дампы; читать их
    # надо как «формула образца до 31.08». Развилка — #113.
    Rcore = math.sqrt(s_fold * PITCH / math.pi)
    layers = (Rout - Rcore) / PITCH
    degenerate = Rcore >= 0.9 * Rout
    # ⚑ КОРИДОР ПОСАДКИ ТЕПЕРЬ ДЕЙСТВИТЕЛЬНО ПРОСЕИВАЕТ. LANDING_WINDOW объявлен в fold.py
    # ситом против правки, уводящей край на половину листа, но до 31.08 его не звал НИКТО:
    # ни landing_ok, ни landing_fraction не вызывались за пределами собственных определений,
    # и сама посадка не попадала даже в печать судьи. Сито, через которое ничего не проходит,
    # не ловит ничего. Величина, ради которой заведён #113, теперь в отчёте.
    land_frac = fold.landing_fraction(L_SHEET, L_FLAP)
    land_ok = fold.landing_ok(L_SHEET, L_FLAP)
    return dict(A=A, Rout_pred=Rout, Rcore_pred=Rcore, s_fold=s_fold,
                landing_frac=round(land_frac, 4), landing_ok=bool(land_ok),
                landing_window=list(fold.LANDING_WINDOW),
                layers_pred=layers, cross_pred=layers + 1.0, a_fill=a_fill,
                # ⚑ Флаг вырождения печатается рядом с числом, чтобы его нельзя было прочитать
                # как исправное предсказание, не заметив оговорки выше.
                area_model_degenerate=bool(degenerate)), (xs, cls, vol, nr, nc, info)


def contour(xs, cen, nb=36, pct=98.0, half=2):
    rel = xs - np.asarray(cen)
    r = np.hypot(rel[:, 0], rel[:, 1])
    a = np.arctan2(rel[:, 1], rel[:, 0])
    b = np.clip(((a + math.pi) / (2 * math.pi) * nb).astype(int), 0, nb - 1)
    c = np.zeros(nb)
    for k in range(nb):
        m = b == k
        c[k] = np.percentile(r[m], pct) if m.sum() >= 3 else np.nan
    good = ~np.isnan(c)
    if not good.all():
        c[~good] = np.interp(np.nonzero(~good)[0], np.nonzero(good)[0], c[good])
    sm = np.array([np.median(np.take(c, range(k - half, k + half + 1), mode='wrap')) for k in range(nb)])
    return r, b, c, sm


# ⚑ КРИТЕРИЙ 3 ПРИЁМКИ: ПО ЛУЧУ ИЗ ЦЕНТРА НОРИ ПЕРЕСЕКАЕТСЯ РОВНО ОДИН РАЗ
# (кроме дуги шва длиной в нориcиро). Заведён 01.09 по issue #113: из четырёх критериев,
# записанных в sim/KINEMATICS.md 31.08, судья считал ОДИН — посадку в окно. Остальные три
# существовали прозой, то есть проверялись глазами или никак.
#
# Как меряется. Луч — сектор шириной 360°/NB. Частицы нори внутри сектора сортируются по
# радиусу; разрыв больше GAP медианных шагов между соседями означает, что лента прошла здесь
# ещё раз. Порог по МЕДИАННОМУ ШАГУ, а не по абсолютной длине: разрешение прогонов разное,
# и абсолютный порог пришлось бы править вслед за числом частиц — ровно та ошибка, которую
# разбирает «Поправка 11» в KINEMATICS.md (планка разрыва уехала сама вслед за толщинами).
#
# Что это ловит: лишний виток («гармошку»), разорванную ленту, лист не по размеру ролла.
# Чего НЕ ловит: одно пересечение при неверной ПОСАДКЕ края — за это отвечает критерий 1.
def nori_crossings(x, cls, cen, nb=72, gap=5.0):
    nori = cls == 2
    if nori.sum() < 4:
        return None
    rel = x - np.asarray(cen)
    r = np.hypot(rel[:, 0], rel[:, 1])
    a = np.arctan2(rel[:, 1], rel[:, 0])
    out = []
    for k in range(nb):
        lo = -math.pi + k * 2 * math.pi / nb
        hi = -math.pi + (k + 1) * 2 * math.pi / nb
        m = nori & (a >= lo) & (a < hi)
        if m.sum() < 2:
            out.append(0)
            continue
        rr = np.sort(r[m])
        d = np.diff(rr)
        pos = d[d > 0]
        step = float(np.median(pos)) if pos.size else 1e-9
        out.append(1 + int((d > gap * step).sum()))
    c = np.array(out)
    # Дуга шва: нориcиро 1,5–3 см при обхвате ~18 см — до ~17 % окружности законно даёт два.
    seam = max(1, int(round(nb * 0.17)))
    over = int((c > 1).sum())
    return dict(cross_rays_med=float(np.median(c)), cross_rays_max=int(c.max()),
                cross_rays_one=round(float((c == 1).mean()), 3),
                # ⚑ Критерий: всё, что сверх одного пересечения, обязано уместиться в дугу шва.
                single_layer_ok=bool(over <= seam))


def judge(attempt, out, L, mod):
    pred, (xs0, cls0, vol, nr, nc, info) = predicted(mod, L)
    z = np.load(f'{ROOT}/{attempt}/{out}/particles_{L}.npz')
    met = json.load(open(f'{ROOT}/{attempt}/{out}/metrics_{L}.json'))
    x, cls, J = z['x'], z['cls'], z['J']
    assert len(x) == len(vol), (len(x), len(vol))
    rice, nori, fil = cls == 1, cls == 2, cls > 2
    cons = float(np.sum(vol * J) / np.sum(vol))
    cons_rice = float(np.sum(vol[rice] * J[rice]) / np.sum(vol[rice]))
    cen = (float(x[:, 0].mean()), float(x[:, 1].mean()))
    r, b, craw, sm = contour(x, cen)
    excess = r - sm[b]
    out_m = excess > 0.3
    rmed, rmax, rmin = float(np.median(sm)), float(sm.max()), float(sm.min())
    round_cv = float(sm.std() / sm.mean())
    # near edge (tuck) and far edge (flap) radial position, normalised
    ne = nori & (nc <= 2)
    fe = nori & (nc >= info['nori_cols'] - 3)
    r_near = float(np.median(r[ne])) / rmed
    r_far = float(np.median(r[fe])) / rmed
    # core
    core = []
    for f in mod.LAYOUTS[L]['fillings']:
        c = mod.CLASS_OF_KIND[f['kind']]
        m = cls == c
        if not m.any():
            continue
        cx, cy = float(x[m, 0].mean()), float(x[m, 1].mean())
        rr = math.hypot(cx - cen[0], cy - cen[1])
        ph = math.degrees(math.atan2(cy - cen[1], cx - cen[0]))
        core.append((f['kind'], rr, ph, cx, float(np.percentile(np.hypot(x[m, 0] - cen[0], x[m, 1] - cen[1]), 95))))
    order_x = [c[0] for c in sorted(core, key=lambda c: c[3])]
    core_rmax = max((c[4] for c in core), default=0.0)
    return dict(
        attempt=attempt, L=L,
        turns=met['nori_turns'], cross_pred=round(pred['cross_pred'], 3),
        d_turns=round(met['nori_turns'] - pred['cross_pred'], 3),
        layers_pred=round(pred['layers_pred'], 3),
        Rout_pred=round(pred['Rout_pred'], 3), Rout_med=round(rmed, 3), Rout_max=round(rmax, 3),
        round_cv=round(round_cv, 4), rmin_rmax=round(rmin / rmax, 3),
        cons=round(cons, 4), cons_rice=round(cons_rice, 4), J_rice=met['rice_J_mean'],
        map_ratio=met['rice_area_ratio'],
        out_frac=round(float(out_m.mean()), 5), out_n=int(out_m.sum()),
        out_nori=int((out_m & nori).sum()), out_max=round(float(excess.max()), 3),
        r_near=round(r_near, 3), r_far=round(r_far, 3),
        core_rmax=round(core_rmax, 2), order_x=order_x,
        # ⚑ КРИТЕРИЙ 4: ближняя кромка нори лежит В СТЕНКЕ, а не между начинкой и рисом
        # (#113). Данные для него собирались (r_near), а самой проверки не было. Кромка в
        # стенке значит: её радиус БОЛЬШЕ внешнего радиуса начинок. Допуск 2 % — толщина
        # ленты и разброс частиц.
        edge_in_wall=bool(r_near * rmed > core_rmax * 1.02) if core_rmax > 0 else None,
        r_near_abs=round(r_near * rmed, 3),
        core=[(c[0], round(c[1], 2), round(c[2], 1)) for c in core],
        sec=met['timing']['seconds'], stable=met['stable'], esc=met['escaped'],
        gap=met['nori_max_gap_T'], torn=met['nori_torn'],
        **(nori_crossings(x, cls, cen) or {}),
    )
# ⚠ КРИТЕРИЙ 2 («рис к рису торцами») ПО-ПРЕЖНЕМУ НЕ МЕРЯЕТСЯ, и это не забывчивость.
# В .npz лежат координаты и класс частицы, но НЕ её исходное положение на листе, а «торцы
# риса» — это два конца исходной постели. Отличить их от любых других частиц риса после
# скрутки нечем. Чтобы критерий стал измеримым, прогон должен сохранять исходную координату
# вдоль листа (аналог nc, который уже есть у нори). Это правка run.py и пересъёмка прогонов,
# то есть работа отдельной задачи, а не судьи. В ИГРЕ критерий снят построением: в кольце
# (#132) постель непрерывна, два конца — одна лента, встреча торцов выполнена тождественно.


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'out_judge'
    mods = {'kin-grab': load(f'{ROOT}/kin-grab/run.py', 'rg'), 'kin-mat': load(f'{ROOT}/kin-mat/run.py', 'rm')}
    rows = []
    for L in (1, 2, 3, 4, 5):
        for a, mod in mods.items():
            try:
                rows.append(judge(a, out, L, mod))
            except FileNotFoundError:
                pass
    hdr = ['attempt', 'L', 'turns', 'cross_pred', 'd_turns', 'cons', 'cons_rice', 'map_ratio',
           'Rout_med', 'Rout_pred', 'round_cv', 'out_frac', 'out_max', 'out_nori', 'r_near', 'r_far',
           'core_rmax', 'sec', 'stable', 'gap',
           'cross_rays_med', 'cross_rays_max', 'single_layer_ok', 'edge_in_wall']
    print(' | '.join(f'{h:>10}' for h in hdr))
    for r in rows:
        print(' | '.join(f'{str(r[h]):>10}' for h in hdr))
    print()
    for r in rows:
        print(r['attempt'], r['L'], 'order_x=', r['order_x'], 'core=', r['core'])
    json.dump(rows, open(f'{ROOT}/judge_{out}.json', 'w'), indent=1)
