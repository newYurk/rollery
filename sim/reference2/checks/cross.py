#!/usr/bin/env python3
"""Knob effect vs noise floor: IoU / interface shift / contour profile against the baseline."""
import json, os, math, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); O = os.path.join(HERE, 'out_hand'); PX = 12.0/600
def m(t): return np.load(os.path.join(O, f'material_4{t}.npy'))
def j(t): return json.load(open(os.path.join(O, f'metrics_4{t}.json')))
def perim(a, c):
    A = a == c; b = np.zeros_like(A)
    d = A[1:,:]^A[:-1,:]; b[1:,:]|=d; b[:-1,:]|=d
    d = A[:,1:]^A[:,:-1]; b[:,1:]|=d; b[:,:-1]|=d
    return (A&b).sum()
YY, XX = np.mgrid[0:600,0:600]; RR = np.hypot(XX-300,300-YY)*PX
THI = (((np.arctan2(300-YY,XX-300)+math.pi)/(2*math.pi))*72).astype(int)%72
def prof(a):
    mk = a > 0; out = np.zeros(72)
    for k in range(72):
        s = mk & (THI==k); out[k] = RR[s].max() if s.any() else 0
    return out
def cmp(a, b):
    A, B = m(a), m(b)
    roll = (A>0)&(B>0); un = (A>0)|(B>0)
    sh = {}
    for c,n in ((1,'rice'),(2,'nori')):
        sh[n] = round(((A==c)^(B==c)).sum()/max(perim(A,c),1)*PX, 4)
    d = prof(A)-prof(B)
    return dict(iou=round(float(roll.sum()/un.sum()),4), rice_T=sh['rice'], nori_T=sh['nori'],
                dR_rms=round(float(np.sqrt((d**2).mean())),4), dR_max=round(float(np.abs(d).max()),4))
BASE='_rep_a'
GR={'noise same-seed':[('_rep_a','_rep_b'),('_rep_a','_rep_c'),('_rep_a','_rep_d'),('_rep_c','_rep_d')],
    'noise seed':[('_rep_a','_seed2'),('_rep_a','_seed3'),('_rep_a','_seed4'),('_seed2','_seed3')],
    'speed 0.5 rep':[('_sp05_a','_sp05_b')], 'speed 2.0 rep':[('_sp20_a','_sp20_b')],
    'press 0.5 rep':[('_pr05_a','_pr05_b')], 'press 2.0 rep':[('_pr20_a','_pr20_b')],
    'hold 0 rep':[('_ho0_a','_ho0_b')], 'hold 4 rep':[('_ho4_a','_ho4_b')], 'hold 8 rep':[('_ho8_a','_ho8_b')],
    'SIG speed0.5':[(BASE,'_sp05_a')], 'SIG speed2.0':[(BASE,'_sp20_a')],
    'SIG press0.5':[(BASE,'_pr05_a')], 'SIG press2.0':[(BASE,'_pr20_a')],
    'SIG hold0':[(BASE,'_ho0_a')], 'SIG hold4':[(BASE,'_ho4_a')], 'SIG hold8':[(BASE,'_ho8_a')]}
print(f"{'comparison':<16} {'pair':<22} {'IoU':>7} {'rice_T':>8} {'nori_T':>8} {'dR_rms_T':>9} {'dR_max_T':>9}")
for g, prs in GR.items():
    for a,b in prs:
        r = cmp(a,b)
        print(f"{g:<16} {a+' vs '+b:<22} {r['iou']:>7} {r['rice_T']:>8} {r['nori_T']:>8} {r['dR_rms']:>9} {r['dR_max']:>9}")
print()
print(f"{'run':<10} {'order_ok':>9} {'order_mirror':>13} {'stable':>7} {'nori_torn':>10} {'comp':>5} {'esc':>4} {'steps':>7} {'wr_fin':>7} {'wrmat_fin':>10} {'riceJ':>7} {'cons':>7} {'Rout':>6} {'Rmin':>6} {'Rmean':>6}")
for t in ['_rep_a','_seed2','_sp05_a','_sp20_a','_pr05_a','_pr20_a','_ho0_a','_ho4_a','_ho8_a']:
    d = j(t)
    print(f"{t:<10} {str(d['core_order_preserved']):>9} {str(d['core_order_preserved_mirrored']):>13} {str(d['stable']):>7} {str(d['nori_torn']):>10} {d['nori_components_map']:>5} {d['escaped']:>4} {d['timing']['steps']:>7} {d['wrinkles']:>7} {d['wrinkles_mat']:>10} {d['rice_J_min_run']:>7} {d['conservation']:>7} {d['Rout_T']:>6} {d['Rout_min_T']:>6} {d['Rout_mean_T']:>6}")
