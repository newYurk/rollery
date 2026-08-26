#!/usr/bin/env python3
"""Final table: knob signal vs two noise floors (same-seed repeat, seed change)."""
import json, os
import numpy as np
O = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out_hand')
def g(t): return json.load(open(os.path.join(O, f'metrics_4{t}.json')))
def val(d, k):
    if k == 'round': return d['Rout_T']/d['Rout_min_T']
    if k.startswith('phi_'): return [f for f in d['fillings'] if f['kind']==k[4:]][0]['phi_deg']
    if k.startswith('u_'):   return d['rice_under_filling_T'][k[2:]]
    if k == 'steps': return d['timing']['steps']
    return d[k]
KEYS = ['Rout_T','Rout_mean_T','round','conservation','rice_J_min_run','steps','phi_cucumber','u_tamago']
REP  = ['_rep_a','_rep_b','_rep_c','_rep_d']
SEED = ['_rep_a','_seed2','_seed3','_seed4']
CELL = {'speed 0.5':['_sp05_a','_sp05_b'],'speed 2.0':['_sp20_a','_sp20_b'],
        'press 0.5':['_pr05_a','_pr05_b'],'press 2.0':['_pr20_a','_pr20_b'],
        'hold 0':['_ho0_a','_ho0_b'],'hold 4':['_ho4_a','_ho4_b'],'hold 8':['_ho8_a','_ho8_b']}
def span(tags,k): 
    v=[val(g(t),k) for t in tags]; return max(v)-min(v), float(np.mean(v))
print(f"{'metric':<16} {'base':>9} {'rep span':>9} {'seed span':>10} | " + ' '.join(f'{c:>11}' for c in CELL))
for k in KEYS:
    rs,base = span(REP,k); ss,_ = span(SEED,k)
    line = f"{k:<16} {base:>9.4f} {rs:>9.4f} {ss:>10.4f} | "
    for c,tags in CELL.items():
        _,mu = span(tags,k); line += f'{mu:>11.4f} '
    print(line)
print()
print(f"{'metric':<16} " + ' '.join(f'{c:>11}' for c in CELL) + '   (|delta from base| / seed span)')
for k in KEYS:
    rs,base = span(REP,k); ss,_ = span(SEED,k)
    line = f"{k:<16} "
    for c,tags in CELL.items():
        _,mu = span(tags,k)
        line += f'{abs(mu-base)/ss if ss>0 else float("inf"):>11.1f} '
    print(line)
