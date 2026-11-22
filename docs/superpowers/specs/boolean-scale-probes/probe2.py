"""Upstream sizes for the larger networks, Caribbean SCC structure, numba exhaustive benchmark."""
import json, sys, time
import numpy as np
import networkx as nx
import core_reduction as cr

L = "C:/Users/arturas.baziukas/AppData/Local/"
T = L + "sespy-lib-v1180/sespy/templates/marinesabres/"
for name in ["Fisheries", "Tourism", "Pollution", "Aquaculture", "OffshoreWind", "Caribbean"]:
    rules, _ = cr.rules_of(json.load(open(T + f"{name}_SES_Template.json", encoding="utf-8")))
    U, C, R = cr.partition(rules)
    g = cr.graph(rules)
    feeders = {u for u in U if any(v in C for v in g.successors(u))}
    print(f"{name:13s} n={len(rules):3d} U={len(U):2d} (feeding core {len(feeders):2d}) C={len(C):2d} R={len(R):2d}")
    if name == "Caribbean":
        sub = g.subgraph(C)
        sccs = sorted((len(c) for c in nx.strongly_connected_components(sub)), reverse=True)
        print("  core SCC sizes:", sccs[:10])
        fvs_greedy = []  # greedy feedback vertex set size estimate
        h = sub.copy()
        while True:
            cyc = [c for c in nx.strongly_connected_components(h) if len(c) > 1 or any(h.has_edge(v, v) for v in c)]
            if not cyc:
                break
            big = max(cyc, key=len)
            v = max(big, key=lambda x: h.in_degree(x) * h.out_degree(x))
            h.remove_node(v)
            fvs_greedy.append(v)
        print("  greedy feedback vertex set size:", len(fvs_greedy))

# numba exhaustive benchmark (uint32 next map + int32 labels, compiled walk)
try:
    import numba

    @numba.njit(cache=False)
    def build_next(n, act_idx, act_w, act_ptr, thr):
        N = 1 << n
        nxt = np.empty(N, dtype=np.uint32)
        for s in range(N):
            new = 0
            for j in range(n):
                inflow = 0.0
                for k in range(act_ptr[j], act_ptr[j + 1]):
                    inflow += act_w[k] * ((s >> act_idx[k]) & 1)
                if inflow > thr[j]:
                    new |= 1 << j
            nxt[s] = new
        return nxt

    @numba.njit(cache=False)
    def label(nxt):
        N = nxt.shape[0]
        lab = np.full(N, -1, dtype=np.int32)
        stamp = np.full(N, -1, dtype=np.int32)
        na = 0
        for start in range(N):
            if lab[start] != -1:
                continue
            cur = start
            while lab[cur] == -1 and stamp[cur] != start:
                stamp[cur] = start
                cur = nxt[cur]
            if lab[cur] != -1:
                a = lab[cur]
            else:
                a = na
                na += 1
            cur = start
            while lab[cur] == -1:
                lab[cur] = a
                cur = nxt[cur]
        return na

    rng = np.random.default_rng(0)
    for n in [20, 22, 24, 26]:
        idx, w, ptr = [], [], [0]
        for j in range(n):
            ins = rng.choice(n, size=3, replace=False)
            for i in ins:
                idx.append(i); w.append(rng.choice([-1.0, 1.0, 0.5, -0.5]))
            ptr.append(len(idx))
        args = (n, np.array(idx, np.int64), np.array(w, np.float64), np.array(ptr, np.int64), np.zeros(n))
        if n == 20:
            label(build_next(*args))  # JIT warm-up
        t = time.perf_counter(); nxt = build_next(*args); t1 = time.perf_counter(); na = label(nxt); t2 = time.perf_counter()
        print(f"numba n={n}: next map {t1 - t:.2f}s, labelling {t2 - t1:.2f}s, attractors {na}, arrays ~{(nxt.nbytes * 3) / 2**20:.0f} MB")
except Exception as e:  # noqa: BLE001
    print("numba bench failed:", type(e).__name__, e)
