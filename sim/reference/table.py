#!/usr/bin/env python3
"""Results table for README.md: reads out/metrics_<L>.json and prints Markdown rows."""
import importlib.util, json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
_sp = importlib.util.spec_from_file_location('refrun', os.path.join(ROOT, 'run.py'))
_m = importlib.util.module_from_spec(_sp); sys.modules['refrun'] = _m; _sp.loader.exec_module(_m)
LAYOUTS = _m.LAYOUTS
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'out')
NAMES = {1: 'пустой лист', 2: 'тамаго у края', 3: 'лосось в середине',
         4: 'четыре у края', 5: 'переполнение + квадрат'}

rows = []
for L in (1, 2, 3, 4, 5):
    p = os.path.join(OUT, f'metrics_{L}.json')
    if not os.path.exists(p):
        continue
    rows.append(json.load(open(p)))

def g(d, k, nd=3):
    v = d.get(k)
    return '—' if v is None else (f'{v:.{nd}f}' if isinstance(v, float) else str(v))

print('| метрика | ' + ' | '.join(f'{d["layout"]} — {NAMES[d["layout"]]}' for d in rows) + ' |')
print('|---|' + '---|' * len(rows))
LINES = [
    ('`nori_turns` (пересечений нори лучом)', lambda d: g(d, 'nori_turns')),
    ('`crossings_predicted` (буквальная формула)', lambda d: g(d, 'crossings_predicted')),
    ('Δ к буквальной', lambda d: f'{d["turns_minus_predicted"]:+.3f}'),
    ('`crossings_predicted_core` (+ ядро и полость)', lambda d: g(d, 'crossings_predicted_core')),
    ('**Δ к уточнённой**', lambda d: f'**{d["turns_minus_predicted_core"]:+.3f}**'),
    ('`conservation` = Σ(vol·J)/Σ(vol)', lambda d: g(d, 'conservation', 4)),
    ('  · рис / нори', lambda d: f'{d["conservation_rice"]:.4f} / {d["conservation_nori"]:.4f}'),
    ('`Rout_T` (макс. по 36 лучам)', lambda d: g(d, 'Rout_T')),
    ('`Rout_median_T` / `Rout_pred_T`', lambda d: f'{d["Rout_median_T"]:.3f} / {d["Rout_pred_T"]:.3f}'),
    ('`Rout_min_T`', lambda d: g(d, 'Rout_min_T')),
    ('`rice_area_ratio` (карта, артефакт растра)', lambda d: g(d, 'rice_area_ratio')),
    ('`rice_outside_contour_frac`', lambda d: g(d, 'rice_outside_contour_frac', 5)),
    ('`tail_outside_frac` / макс. вынос, T', lambda d: f'{d["tail_outside_frac"]:.5f} / {d["tail_outside_max_excess_T"]:.2f}'),
    ('  · из них нори', lambda d: str(d['tail_outside_nori'])),
    ('`nori_max_gap_T` (шаг частиц)', lambda d: f'{d["nori_max_gap_T"]:.4f} ({d["nori_particle_spacing_T"]:.4f})'),
    ('`nori_torn` / `escaped` / `stable`', lambda d: f'{d["nori_torn"]} / {d["escaped"]} / {d["stable"]}'),
    ('`s_fold` / `a_fold`, T · T²', lambda d: f'{d["grab"]["s_fold"]:.1f} / {d["grab"]["a_fold_T2"]:.2f}'),
    ('секунды (M4 Max, CPU)', lambda d: f'{d["timing"]["seconds"]:.1f}'),
]
for label, f in LINES:
    print(f'| {label} | ' + ' | '.join(f(d) for d in rows) + ' |')

print()
print('| раскладка | порядок слева направо (было → стало) | по φ вокруг ядра | рис под начинкой, T |')
print('|---|---|---|---|')
for d in rows:
    was = ' → '.join(f['kind'] for f in sorted(LAYOUTS[d['layout']]['fillings'], key=lambda f: f['u'])) or '—'
    got = ' → '.join(d.get('core_order_left_to_right') or []) or '—'
    phi = ' → '.join(d.get('core_order_by_phi') or []) or '—'
    ru = ', '.join(f'{k} {v}' for k, v in (d.get('rice_under_filling_T') or {}).items()) or '—'
    print(f'| {d["layout"]} | {was} → **{got}** | {phi} | {ru} |')
