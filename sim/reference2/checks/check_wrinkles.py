"""The claim under test (run.py:962-963, `wrinkle_ok`): with the real mat, ZERO wrinkles at EVERY
phase on all five layouts, amplitude below 0.3 T.

This reads the metrics written by run.py itself -- no reinterpretation -- and prints every sampled
state where the count is non-zero.
"""
import json, sys
from collections import Counter

OUT = sys.argv[1] if len(sys.argv) > 1 else "/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference2/out"

tot = bad = badmat = 0
print("L  name             wrinkle_ok  final  max(phase)  mat_max  amp_max_T  samples w>0  samples mat>0")
for n in range(1, 6):
    d = json.load(open(f"{OUT}/metrics_{n}.json"))
    h = d['wrinkle_hist']
    w = sum(1 for s in h if s['w'] > 0)
    m = sum(1 for s in h if s['wm'] > 0)
    tot += len(h); bad += w; badmat += m
    print("%-3d%-16s%12s%7d%7d (%-5s)%7d%12.4f%13d%15d" % (
        n, d['layout_name'], str(d['wrinkle_ok']), d['wrinkles'], d['wrinkles_max'],
        d['wrinkles_max_phase'], d['wrinkles_mat_max'], d['wrinkle_amp_max_T'], w, m))
print(f"\ntotal: {bad}/{tot} sampled states have wrinkles > 0; {badmat}/{tot} exceed the bamboo threshold")
print("wrinkle_ok is False on", sum(1 for n in range(1, 6)
      if not json.load(open(f"{OUT}/metrics_{n}.json"))['wrinkle_ok']), "of 5 layouts\n")

for n in range(1, 6):
    d = json.load(open(f"{OUT}/metrics_{n}.json"))
    nz = [(p, v) for p, v in d['wrinkles_by_phase'].items() if v['wrinkles'] or v['mat'] or v['nonose']]
    if nz:
        print(f"layout {n} {d['layout_name']}: phases with a non-zero count")
        for p, v in nz:
            print("    %-6s wrinkles=%d  wrinkles_mat=%d  nonose=%d  amp=%.4f T  tightest bend R=%.3f T"
                  % (p, v['wrinkles'], v['mat'], v['nonose'], v['amp_T'], v['r_fold_T']))
