"""Opt-in 'drivers hold their value' variant: drivers (input-less nodes) are fixed parameters.
For each driver setting: propagate the upstream part with driver bits forced, then core search.
Reports distinct core attractors across settings and runtime. Usage: python probe6.py FILE..."""
import sys, time
import numpy as np
import core_reduction as cr

for p in sys.argv[1:]:
    rules, _ = cr.rules_of(__import__("json").load(open(p, encoding="utf-8")))
    U, C, R = cr.partition(rules)
    drv = [r["node_id"] for r in rules if not r["activators"] and not r["inhibitors"]]
    md = cr.mask(drv)
    mu = cr.mask(U)
    k = len(C)
    idx = np.arange(1 << k, dtype=np.int64)
    core_full = cr.scatter(idx, C)
    t = time.perf_counter()
    per_setting, distinct, allzero_core = [], set(), 0
    for a in range(1 << len(drv)):
        dbits = int(cr.scatter(np.array([a]), drv)[0])
        s = np.array([dbits], dtype=np.int64)
        for _ in range(len(U) + 1):
            s = (cr.next_states(rules, s) & ~md) | dbits
        ustar = int(s[0]) & mu
        if k == 0:
            per_setting.append(1)
            distinct.add((ustar, ()))
            continue
        nf = (cr.next_states(rules, core_full | ustar) & ~md) | dbits
        nxt = np.zeros_like(idx)
        for kk, v in enumerate(C):
            nxt |= ((nf >> v) & 1) << kk
        m, fp = idx.copy(), nxt.copy()
        for _ in range(k):
            m = np.minimum(m, m[fp])
            fp = fp[fp]
        labs = np.unique(m[fp])
        per_setting.append(len(labs))
        if len(labs) == 1 and labs[0] == 0 and nxt[0] == 0:
            allzero_core += 1
        for lab in labs:
            distinct.add((ustar, int(lab)))
    dt = time.perf_counter() - t
    name = p.replace("\\", "/").split("/")[-1]
    print(f"{name:32s} n={len(rules):2d} drivers={len(drv):2d} core={k:2d}: settings {1 << len(drv)}, "
          f"attractors per setting min/max {min(per_setting)}/{max(per_setting)}, distinct (upstream pattern, core attractor) {len(distinct)}, "
          f"settings with core all-off only {allzero_core}; {dt:.2f}s")
