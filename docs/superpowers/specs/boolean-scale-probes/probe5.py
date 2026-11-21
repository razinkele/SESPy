"""Attractor counts (attractor set only, via core search) for every shipped network under SESPy rules.
Networks with n <= 20 and >= 2 attractors are also compared reduced vs full, basins included.
Also counts input-less nodes (drivers) per network.
Usage: python probe5.py FILE...   (PYTHONPATH = sespy tree; cwd = this directory)
"""
import sys, time
import numpy as np
import core_reduction as cr
from sespy import dynamics


def core_attractor_count(rules):
    U, C, R = cr.partition(rules)
    mu = cr.mask(U)
    s = np.zeros(1, dtype=np.int64)
    for _ in range(len(U) + 1):
        s = cr.next_states(rules, s)
    ustar = int(s[0]) & mu
    k = len(C)
    if k == 0:
        return 1, (U, C, R), "exact"
    idx = np.arange(1 << k, dtype=np.int64)
    nf = cr.next_states(rules, cr.scatter(idx, C) | ustar)
    nxt = np.zeros_like(idx)
    for kk, v in enumerate(C):
        nxt |= ((nf >> v) & 1) << kk
    m, fp = idx.copy(), nxt.copy()
    for _ in range(k):
        m = np.minimum(m, m[fp])
        fp = fp[fp]
    return len(np.unique(m[fp])), (U, C, R), "exact"


def drivers(rules):
    return sum(1 for r in rules if not r["activators"] and not r["inhibitors"])


rows = []
for p in sys.argv[1:]:
    for name, proj in cr.projects_in(p):
        rules, _ = cr.rules_of(proj)
        if not rules:
            continue
        n = len(rules)
        U, C, R = cr.partition(rules)
        short = name.replace("\\", "/").split("/")[-1]
        if len(C) > 22:
            rows.append((n, len(C), "sampled-only", None, drivers(rules), short))
            continue
        t = time.perf_counter()
        na, _, how = core_attractor_count(rules)
        dt = time.perf_counter() - t
        check = ""
        if n <= 20 and na >= 2:
            full = dynamics.boolean_attractors(rules, max_nodes=20)
            want = {frozenset(a["states"]): a["basin_size"] for a in full["attractors"]}
            got, _ = cr.reduced_attractors(rules)
            check = f" reduced==full(basins incl.): {got == want}; basins {sorted(want.values(), reverse=True)}"
        rows.append((n, len(C), na, round(dt, 2), drivers(rules), short + check))

rows.sort(key=lambda r: (r[0], r[5]))
for n, c, na, dt, d, name in rows:
    print(f"n={n:3d} core={c:3d} drivers={d:2d} attractors={na}  ({dt}s)  {name}")
multi = [r for r in rows if isinstance(r[2], int) and r[2] >= 2]
print(f"networks {len(rows)}; with >=2 attractors: {len(multi)}; single-attractor (all-off): "
      f"{sum(1 for r in rows if r[2] == 1)}; sampled-only: {sum(1 for r in rows if r[2] == 'sampled-only')}")
