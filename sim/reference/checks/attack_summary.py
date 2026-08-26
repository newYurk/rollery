"""Verdict table for the attack. Run the three scripts first (they write JSON next to this file)."""
import json
ROOT='/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference'
cl={str(k):v for k,v in json.load(open(f'{ROOT}/checks/attack_centerline.json')).items()}
ce={str(k):v for k,v in json.load(open(f'{ROOT}/checks/attack_core_edges.json')).items()}
H=1.12
print('=== A. layers from ACTUAL final geometry vs measured 36-ray crossings ===')
print(f'{"L":>2} {"Rout_med":>8} {"Rcore_act":>9} {"layers":>7} {"pred_x":>7} '
      f'{"meas_honest":>11} {"D_honest":>8} | {"ref nori_turns":>14} {"D_ref":>7}')
for L in ('1','2','4'):
    v=cl[L]['variants']['contour_vs_ray_core']; meas=cl[L]['crossings_centreline_mean']
    ref=cl[L]['ref_nori_turns']
    print(f'{L:>2} {v["Rout"]:>8.3f} {v["Rcore"]:>9.3f} {v["layers"]:>7.3f} {v["crossings_pred"]:>7.3f} '
          f'{meas:>11.3f} {meas-v["crossings_pred"]:>+8.3f} | {ref:>14.3f} {ref-v["crossings_pred"]:>+7.3f}')
print()
print('=== B. criterion 1 (area formula) re-tested with the honest crossing count ===')
print(f'{"L":>2} {"honest":>7} {"pred_literal":>12} {"D":>7} {"pred_core":>10} {"D":>7} {"ref_turns":>9} {"D_core":>7}')
for L in ('1','2','4'):
    m=cl[L]; h=m['crossings_centreline_mean']
    print(f'{L:>2} {h:>7.3f} {m["ref_crossings_pred"]:>12.3f} {h-m["ref_crossings_pred"]:>+7.3f} '
          f'{m["ref_crossings_pred_core"]:>10.3f} {h-m["ref_crossings_pred_core"]:>+7.3f} '
          f'{m["ref_nori_turns"]:>9.3f} {m["ref_nori_turns"]-m["ref_crossings_pred_core"]:>+7.3f}')
print()
print('=== C. sheet ends ===')
for L in ('1','2','4'):
    e=ce[L]['ends']
    print(f'L{L} near r={e["near"]["r"]:.3f} ({e["near"]["frac_of_contour"]:.3f} of contour)  '
          f'far r={e["far"]["r"]:.3f} ({e["far"]["frac_of_contour"]:.3f})  '
          f'sheet r_min at s={e["s_of_r_min_frac"]*100:.0f}% of L  near_is_innermost={e["near_is_innermost"]}')
print()
print('=== D. layout 4 core ===')
d=ce['4']
for f in sorted(d['fillings'], key=lambda f:f['x']):
    print(f'  {f["kind"]:<9} x={f["x"]:.2f} r={f["r"]:.3f} r/Rout={f["r_over_Rout_med"]:.3f} phi={f["phi_deg"]:+.1f}')
print(f'  order sheet   : {d["order_initial_by_x"]}')
print(f'  order final x : {d["order_final_by_x"]}  preserved={d["order_preserved"]}')
print(f'  spread(max pairwise centroid dist)={d["core_spread_T"]:.3f} T  /Rout_med={d["core_spread_over_Rout"]:.3f}')
