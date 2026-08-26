"""Show WHY nori_turns (run.py) over-counts: per-ray nori run extents on the 600x600 map.
A genuine second wrapper layer is separated by ~1 T of rice; raster holes split one 0.12 T
band into 2-3 runs a few pixels apart."""
import json, math
import numpy as np
ROOT = '/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference'
BG, NORI = 0, 2
PX, NRAY = 0.02, 36

def ray(img, cr, cc, ang, step=0.25):
    n = int(img.shape[0] / 2 / step); d = np.arange(n) * step
    rr = np.round(cr - d * math.sin(ang)).astype(int); c2 = np.round(cc + d * math.cos(ang)).astype(int)
    ok = (rr >= 0) & (rr < img.shape[0]) & (c2 >= 0) & (c2 < img.shape[1])
    return d[ok] * PX, img[rr[ok], c2[ok]]

for L in (1, 2, 4):
    met = json.load(open(f'{ROOT}/out/metrics_{L}.json'))
    img = np.load(f'{ROOT}/out/material_{L}.npy')
    rows, cols = np.nonzero(img != BG); cr, cc = rows.mean(), cols.mean()
    gaps_all, thick_all, nraw, nrob = [], [], 0, 0
    worst = None
    for i, a in enumerate(np.deg2rad(np.arange(0, 360, 360 / NRAY))):
        d, seq = ray(img, cr, cc, a)
        idx = np.nonzero(seq == NORI)[0]
        if not len(idx):
            continue
        gr = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        seg = [(d[g[0]], d[g[-1]]) for g in gr]
        gaps = [seg[k + 1][0] - seg[k][1] for k in range(len(seg) - 1)]
        gaps_all += gaps; thick_all += [b - a2 for a2, b in seg]
        nraw += len(seg)
        merged = [list(seg[0])]
        for a2, b in seg[1:]:
            if a2 - merged[-1][1] < 0.04: merged[-1][1] = b
            else: merged.append([a2, b])
        merged = [s for s in merged if s[1] - s[0] >= 0.04]
        nrob += len(merged)
        if worst is None or len(seg) - len(merged) > worst[1]:
            worst = (i * 10, len(seg) - len(merged), seg, merged)
    g = np.array(gaps_all)
    print(f'L{L}: raw runs/ray={nraw/NRAY:.3f} (metrics nori_turns={met["nori_turns"]}) '
          f'robust={nrob/NRAY:.3f}  runs split={nraw-nrob}')
    print(f'   inter-run gaps T: n={len(g)} <0.04T: {int((g<0.04).sum())}  '
          f'0.04..0.5T: {int(((g>=0.04)&(g<0.5)).sum())}  >=0.5T: {int((g>=0.5).sum())}')
    print(f'   run thickness T: median={np.median(thick_all):.3f} min={np.min(thick_all):.3f} '
          f'(nori band = 0.12 T)')
    print(f'   worst ray {worst[0]} deg: raw={[(round(a,3),round(b,3)) for a,b in worst[2]]}')
    print(f'                     merged={[(round(a,3),round(b,3)) for a,b in worst[3]]}')
