"""Investigation: exact feedback-core reduction for synchronous Boolean attractors.

Modes:
  diff N            differential test on N random networks vs sespy boolean_attractors
  check FILE        reduced exact attractors+basins on a project; full-space sampling cross-check
  dist FILE...      core-size distribution (SESPy projects or MosaicSES .multises/loac files)
PYTHONPATH = a sespy 1.18+ tree.
"""
from __future__ import annotations

import json
import sys
import time

import networkx as nx
import numpy as np
from sespy import dynamics
from sespy.data_structure import Project


# ---- kernel: same summation order as sespy (activators then inhibitors, float adds) ----
def next_states(rules, states):
    states = np.asarray(states, dtype=np.int64)
    out = np.zeros_like(states)
    for j, r in enumerate(rules):
        inflow = np.zeros(states.shape, dtype=np.float64)
        for i, w in r["activators"]:
            inflow = inflow + w * ((states >> i) & 1)
        for i, w in r["inhibitors"]:
            inflow = inflow + w * ((states >> i) & 1)
        out |= (inflow > r["threshold"]).astype(np.int64) << j
    return out


def graph(rules):
    g = nx.DiGraph()
    g.add_nodes_from(range(len(rules)))
    for r in rules:
        for i, w in r["activators"] + r["inhibitors"]:
            g.add_edge(i, r["node_id"])
    return g


def partition(rules):
    g = graph(rules)
    cyc = set()
    for c in nx.strongly_connected_components(g):
        if len(c) > 1 or any(g.has_edge(v, v) for v in c):
            cyc |= c
    down, up = set(cyc), set(cyc)
    for v in cyc:
        down |= nx.descendants(g, v)
        up |= nx.ancestors(g, v)
    core = sorted(down & up)
    upstream = sorted(set(g) - down)          # no cycle above: settles to a constant pattern
    readout = sorted(down - up)               # below cycles only: deterministic outputs
    return upstream, core, readout


def mask(nodes):
    m = 0
    for v in nodes:
        m |= 1 << v
    return m


def scatter(bits_idx, nodes):
    """Map compact indices (bit k = nodes[k]) to full-width states."""
    out = np.zeros_like(bits_idx)
    for k, v in enumerate(nodes):
        out |= ((bits_idx >> k) & 1) << v
    return out


def reduced_attractors(rules):
    n = len(rules)
    U, C, R = partition(rules)
    mu, mc = mask(U), mask(C)
    # constant propagation of the upstream part (independent of everything else)
    s = np.zeros(1, dtype=np.int64)
    for _ in range(len(U) + 1):
        s = next_states(rules, s)
    ustar = int(s[0]) & mu
    for _ in range(2):  # confirm it is a fixed pattern
        s = next_states(rules, s)
        assert int(s[0]) & mu == ustar
    # core map on full-width states (U at u*, R at 0)
    k = len(C)
    idx = np.arange(1 << k, dtype=np.int64)
    full = scatter(idx, C) | ustar
    nxt_full = next_states(rules, full)
    # compact the core bits of next
    nxt = np.zeros_like(idx)
    for kk, v in enumerate(C):
        nxt |= ((nxt_full >> v) & 1) << kk
    # cycle labelling on the core map (pointer doubling + orbit min)
    m, fp = idx.copy(), nxt.copy()
    for _ in range(max(k, 1)):
        m = np.minimum(m, m[fp])
        fp = fp[fp]
    label = m[fp]
    # full attractor reconstruction (readouts settle within len(R) steps)
    attractors = {}
    for rep in np.unique(label):
        st = np.array([(scatter(np.array([rep]), C)[0]) | ustar], dtype=np.int64)
        for _ in range(len(R) + 2 * (1 << 0)):
            st = next_states(rules, st)
        # walk until the full state repeats
        seen, path, cur = {}, [], int(st[0])
        while cur not in seen:
            seen[cur] = len(path)
            path.append(cur)
            cur = int(next_states(rules, np.array([cur]))[0])
        cyc = frozenset(path[seen[cur]:])
        attractors[int(rep)] = cyc
    # exact basins: every upstream initial pattern x every core state; readouts factor 2^|R|
    depth = len(U) + 1
    basins = {int(r): 0 for r in attractors}
    core_full = scatter(idx, C)
    for uidx in range(1 << len(U)):
        st = core_full | int(scatter(np.array([uidx]), U)[0])
        for _ in range(depth):
            st = next_states(rules, st)
        assert np.all((st & mu) == ustar)
        cidx = np.zeros_like(idx)
        for kk, v in enumerate(C):
            cidx |= ((st >> v) & 1) << kk
        lab, cnt = np.unique(label[cidx], return_counts=True)
        for a, c in zip(lab, cnt):
            basins[int(a)] += int(c) << len(R)
    return {attractors[r]: basins[r] for r in attractors}, (U, C, R)


def rules_of(project_dict):
    p = Project.from_dict(project_dict)
    M, ids = dynamics.isa_to_numeric_matrix(p.isa_data)
    return dynamics.create_boolean_rules(M), ids


def random_network(rng):
    n_core = int(rng.integers(2, 7))
    n_up = int(rng.integers(0, 4))
    n_out = int(rng.integers(0, 4))
    n = n_core + n_up + n_out
    perm = rng.permutation(n)
    core, up, out = perm[:n_core], perm[n_core:n_core + n_up], perm[n_core + n_up:]
    M = np.zeros((n, n))
    vals = [-1, 1, -0.1, 0.2, -0.3, 0.7, 0.1, -0.2, 0.3]
    ring = list(core)
    for a, b in zip(ring, ring[1:] + ring[:1]):
        M[a, b] = rng.choice(vals)
    for _ in range(int(rng.integers(0, n_core + 1))):
        a, b = rng.choice(core, 2)
        M[a, b] = rng.choice(vals)
    for j, u in enumerate(up):       # upstream chain feeding the core
        tgt = up[j + 1] if j + 1 < len(up) and rng.random() < 0.5 else rng.choice(core)
        M[u, tgt] = rng.choice(vals)
    for j, o in enumerate(out):      # readouts below the core
        src = out[j - 1] if j > 0 and rng.random() < 0.5 else rng.choice(core)
        M[src, o] = rng.choice(vals)
    return M


def orient(M):
    # rules expect the same matrix orientation sespy uses (create_boolean_rules on isa matrix)
    return dynamics.create_boolean_rules(M)


def mode_diff(N):
    rng = np.random.default_rng(12345)
    bad = 0
    for t in range(N):
        rules = orient(random_network(rng))
        full = dynamics.boolean_attractors(rules, max_nodes=20)
        want = {frozenset(a["states"]): a["basin_size"] for a in full["attractors"]}
        got, (U, C, R) = reduced_attractors(rules)
        if got != want:
            bad += 1
            print("MISMATCH", t, len(rules), (len(U), len(C), len(R)))
            if bad > 5:
                break
    print(f"diff: {N - bad}/{N} networks identical (attractor sets AND exact basins)")


def mode_check(path):
    rules, ids = rules_of(json.load(open(path, encoding="utf-8")))
    n = len(rules)
    t0 = time.perf_counter()
    got, (U, C, R) = reduced_attractors(rules)
    dt = time.perf_counter() - t0
    print(f"n={n} upstream={len(U)} core={len(C)} readout={len(R)}  reduced exact search {dt:.2f}s")
    tot = sum(got.values())
    print(f"attractors={len(got)} basin total={tot} (2^{n}={1 << n}) ok={tot == 1 << n}")
    for cyc, b in sorted(got.items(), key=lambda kv: -kv[1]):
        print(f"  period {len(cyc)}  basin fraction {b / tot:.4f}")
    # full-space sampling cross-check with the plain kernel
    rng = np.random.default_rng(7)
    S = 20000
    st = rng.integers(0, 2, size=(S, n)) @ (1 << np.arange(n, dtype=np.int64))
    hist = [st]
    for _ in range(4 * n + 64):
        st = next_states(rules, st)
        hist.append(st)
    H = np.stack(hist, axis=1)
    reached = {}
    for row in H:
        seen = {}
        for pos, s in enumerate(row):
            s = int(s)
            if s in seen:
                cyc = frozenset(int(x) for x in row[seen[s]:pos])
                reached[cyc] = reached.get(cyc, 0) + 1
                break
            seen[s] = pos
    unknown = [c for c in reached if c not in got]
    print(f"sampling {S} full states: {len(reached)} attractors reached, unknown to reduction: {len(unknown)}")
    for cyc, b in got.items():
        print(f"  exact {b / tot:.4f} vs sampled {reached.get(cyc, 0) / S:.4f}")


def projects_in(path):
    d = json.load(open(path, encoding="utf-8"))
    if "isa_data" in d:
        yield path, d
        return
    for c in d.get("compartments", []) if isinstance(d.get("compartments"), list) else []:
        if isinstance(c, dict) and "project" in c:
            yield f"{path}::{c.get('id', c.get('name', '?'))}", c["project"]


def mode_dist(paths):
    rows = []
    for p in paths:
        try:
            for name, proj in projects_in(p):
                rules, _ = rules_of(proj)
                if not rules:
                    continue
                U, C, R = partition(rules)
                rows.append((len(rules), len(C), name.replace("\\", "/").split("/")[-1]))
        except Exception as e:  # noqa: BLE001
            print("skip", p, type(e).__name__, e)
    rows.sort()
    for n, c, name in rows:
        print(f"{n:4d} -> core {c:3d}   {name}")
    if rows:
        over = [r for r in rows if r[0] > 20]
        print(f"networks: {len(rows)}; n>20: {len(over)}; of those core<=20: {sum(1 for r in over if r[1] <= 20)}")
        print(f"max n {max(r[0] for r in rows)}, max core {max(r[1] for r in rows)}")


if __name__ == "__main__":
    mode, *args = sys.argv[1:]
    {"diff": lambda: mode_diff(int(args[0])), "check": lambda: mode_check(args[0]),
     "dist": lambda: mode_dist(args)}[mode]()
