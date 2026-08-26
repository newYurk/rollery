import time, gstaichi as ti
ti.init(arch=ti.cpu)
n = 8192
x = ti.Vector.field(2, float, n); v = ti.Vector.field(2, float, n)
grid = ti.Vector.field(2, float, (128, 128))
@ti.kernel
def init():
    for i in x: x[i] = [ti.random() * 0.4 + 0.3, ti.random() * 0.4 + 0.3]
@ti.kernel
def step():
    for I in ti.grouped(grid): grid[I] = [0.0, 0.0]
    for p in x:
        base = int(x[p] * 128 - 0.5); grid[base] += v[p]
    for p in x:
        v[p] += [0.0, -9.8 * 1e-4]; x[p] += v[p] * 1e-3
init(); t = time.time()
for _ in range(200): step()
ti.sync(); print('200 steps', round(time.time() - t, 3), 's, arch', ti.cfg.arch)
