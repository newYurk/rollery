#!/usr/bin/env python
"""Monotonicity + signal/noise verdict for the hand inputs of the sushi reference (layout 4).

Noise floor = spread over {4 repeats with identical args and --seed 1} + {--seed 2, --seed 3},
i.e. everything the operator cannot control. A hand input is 'readable' only if its step
exceeds that floor; it is 'monotone' only if every step keeps the same sign.
"""
import json, os
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
def M(t):
    return json.load(open(os.path.join(OUT, f'metrics_4_{t}.json')))

NOISE_TAGS = ['detA','detB','detC','detD','s2','s3']
REPEAT_TAGS = ['detA','detB','detC','detD']
SPEED = [(0.5,['sp05','sp05b','sp05s2']),(0.7,['sp07']),(1.0,REPEAT_TAGS),(1.5,['sp15']),(2.0,['sp20','sp20b'])]
PRESS = [(0.5,['pr05','pr05b']),(0.7,['pr07']),(1.0,REPEAT_TAGS),(1.5,['pr15']),(2.0,['pr20','pr20b'])]

def get(t, key):
    m = M(t)
    if key.startswith('r_'):
        d = {f['kind']: f['r_T'] for f in m['fillings']}; return d.get(key[2:], float('nan'))
    if key.startswith('ruf_'):
        return m['rice_under_filling_T'].get(key[4:], float('nan'))
    if key == 'roundness':
        return m['Rout_min_T'] / m['Rout_median_T']
    return m[key]

KEYS = ['Rout_median_T','Rout_T','Rout_min_T','roundness','nori_turns','conservation_rice','conservation',
        'tail_outside_frac','rice_outside_contour_frac',
        'r_cucumber','r_tamago','r_salmon','r_avocado',
        'ruf_cucumber','ruf_tamago','ruf_salmon','ruf_avocado']

def spread(tags, key):
    v = np.array([get(t, key) for t in tags], float)
    return float(np.nanmax(v) - np.nanmin(v)), float(np.nanstd(v, ddof=1))

print('NOISE FLOOR (peak-to-peak over 4 identical repeats, and over repeats+seeds 1..3)')
print(f"{'metric':22}{'repeat pp':>11}{'repeat sd':>11}{'seed+rep pp':>13}{'seed+rep sd':>13}")
floor = {}
for k in KEYS:
    rp, rs = spread(REPEAT_TAGS, k)
    sp, ss = spread(NOISE_TAGS, k)
    floor[k] = sp
    print(f'{k:22}{rp:>11.4f}{rs:>11.4f}{sp:>13.4f}{ss:>13.4f}')

def sweep(name, pts):
    print(f'\n{"="*96}\n{name} sweep, layout 4 (values are means over the runs at each level)\n{"="*96}')
    print(f"{'metric':22}" + ''.join(f'{p[0]:>9}' for p in pts) + f"{'span':>9}{'noise pp':>10}{'span/pp':>9}  steps          verdict")
    for k in KEYS:
        vals = [float(np.nanmean([get(t, k) for t in ts])) for _, ts in pts]
        span = max(vals) - min(vals)
        pp = floor[k]
        steps = np.diff(vals)
        sig = [s for s in steps if abs(s) > pp]          # steps that clear the noise floor
        signs = {np.sign(s) for s in sig}
        if not sig:
            verdict = 'INVISIBLE (all steps < noise)'
        elif len(signs) == 1:
            verdict = 'monotone' + ('' if len(sig) == len(steps) else ' (some steps < noise)')
        else:
            verdict = 'NON-MONOTONE'
        stepstr = ''.join('+' if s > pp else ('-' if s < -pp else '.') for s in steps)
        print(f'{k:22}' + ''.join(f'{v:>9.3f}' for v in vals) +
              f'{span:>9.3f}{pp:>10.4f}{(span/pp if pp>0 else np.inf):>9.1f}  {stepstr:<15}{verdict}')
    print('  steps: + up beyond noise, - down beyond noise, . inside noise')

sweep('--speed', SPEED)
sweep('--press', PRESS)

# analytic control for the one clean channel
print('\nconservation_rice vs analytic exp(-P_press/(lambda+mu)), lambda+mu = 1.234, P_press = 0.08*press')
for p, ts in PRESS:
    meas = float(np.mean([get(t,'conservation_rice') for t in ts]))
    pred = float(np.exp(-0.08*p/1.234))
    print(f'  press {p:>4}: measured {meas:.4f}   analytic {pred:.4f}   delta {meas-pred:+.4f}')
