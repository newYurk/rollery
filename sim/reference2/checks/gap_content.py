"""What sits inside the small gaps that split the nori runs?"""
import json, math, os, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, '..', 'out')
NAMES = {0: 'BG(void)', 1: 'rice', 2: 'nori', 3: 'salmon', 4: 'cucumber', 5: 'tamago', 6: 'avocado', 7: 'shrimp'}
STEP = 0.25

def ray(img, cr, cc_, ang, px):
    npx = img.shape[0]; d = np.arange(int(npx / 2 / STEP)) * STEP
    rr = np.round(cr - d * math.sin(ang)).astype(int); cc = np.round(cc_ + d * math.cos(ang)).astype(int)
    ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
    return d[ok] * px, img[rr[ok], cc[ok]]

small = collections.Counter(); big = collections.Counter()
small_len, big_len = [], []
comp = {}
for n in (1, 2, 3, 4, 5):
    img = np.load(os.path.join(OUT, f'material_{n}.npy'))
    met = json.load(open(os.path.join(OUT, f'metrics_{n}.json'))); px = met['px_T']
    comp[n] = (met['nori_components_map'], met['nori_max_gap_T'], met['nori_particle_spacing_T'], met['nori_torn'])
    fg = img != 0; r_, c_ = np.nonzero(fg); cr, cc_ = r_.mean(), c_.mean()
    for a in np.deg2rad(np.arange(0, 360, 10)):
        d, seq = ray(img, cr, cc_, a, px)
        idx = np.nonzero(seq == 2)[0]
        if len(idx) < 2: continue
        brk = np.nonzero(np.diff(idx) > 1)[0]
        gs = np.split(idx, brk + 1)
        for i in range(1, len(gs)):
            lo, hi = gs[i - 1][-1] + 1, gs[i][0]
            content = seq[lo:hi]
            gap = float(d[hi] - d[lo - 1])
            tgt, L = (small, small_len) if gap < 0.35 else (big, big_len)
            L.append(gap)
            for c in content: tgt[int(c)] += 1

print('nori map connectivity (from run.py metrics):')
for n, v in comp.items():
    print(f"  L{n}: components={v[0]}  max particle gap={v[1]} T  particle spacing={v[2]} T  torn={v[3]}")
print()
print(f"SMALL gaps (<0.35 T): {len(small_len)}  median length {np.median(small_len):.4f} T "
      f"= {np.median(small_len)/0.02:.1f} px")
tot = sum(small.values())
for c, k in small.most_common():
    print(f"   {NAMES[c]:<10} {k:>5} px  {100*k/tot:5.1f} %")
print()
print(f"BIG gaps (>=0.35 T): {len(big_len)}  median length {np.median(big_len):.3f} T")
tot = sum(big.values())
for c, k in big.most_common():
    print(f"   {NAMES[c]:<10} {k:>5} px  {100*k/tot:5.1f} %")
