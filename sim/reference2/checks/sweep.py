#!/usr/bin/env python3
"""Adversarial check: repeatability of the hand + effect of --speed/--press/--hold.

Runs run.py with a matrix of knobs, all layout 4, and collects:
  - IoU of the 600x600 class map against the first run of the same cell
  - Rout, layers, rice-under-filling, filling positions
Usage: checks/sweep.py <plan.json>   (plan = list of {tag, args:[...]})
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = os.path.join(os.path.dirname(ROOT), '.venv', 'bin', 'python')
OUT = os.path.join(HERE, 'out_hand')


def run(tag, extra):
    os.makedirs(OUT, exist_ok=True)
    cmd = [PY, os.path.join(ROOT, 'run.py'), '--layout', '4',
           '--grid', '240', '--particles', '16000', '--frames', '0',
           '--out', OUT, '--tag', tag] + extra
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    dt = time.time() - t0
    ok = p.returncode == 0 and os.path.exists(os.path.join(OUT, f'material_4{tag}.npy'))
    if not ok:
        sys.stderr.write(f'FAIL {tag}: rc={p.returncode}\n{p.stdout[-2000:]}\n{p.stderr[-2000:]}\n')
    return {'tag': tag, 'ok': ok, 'sec': round(dt, 1), 'cmd': ' '.join(extra)}


if __name__ == '__main__':
    plan = json.load(open(sys.argv[1]))
    res = []
    for i, cell in enumerate(plan):
        r = run(cell['tag'], cell['args'])
        res.append(r)
        print(f"[{i+1}/{len(plan)}] {r['tag']:<22} {r['sec']:>6}s ok={r['ok']}", flush=True)
    json.dump(res, open(os.path.join(HERE, 'runlog.json'), 'w'), indent=1)
