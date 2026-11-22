"""(1) Fisheries attractor identity; (2) reduced vs full on the 2-cluster sample; (3) Caribbean fixed points via FVS."""
import json, time
import numpy as np
import networkx as nx
import core_reduction as cr
from sespy import dynamics

L = "C:/Users/arturas.baziukas/AppData/Local/"
T = L + "sespy-lib-v1180/sespy/templates/marinesabres/"

# (1) Fisheries: is the single attractor the all-off state?  (state 0 is always a fixed point:
# inflow 0 > 0 is false for every node, so next(0) == 0)
rules, _ = cr.rules_of(json.load(open(T + "Fisheries_SES_Template.json", encoding="utf-8")))
print("Fisheries next(0) == 0:", int(cr.next_states(rules, np.array([0]))[0]) == 0)
got, _ = cr.reduced_attractors(rules)
print("Fisheries attractors:", [sorted(c) for c in got])

# (2) 17-node sample (two cycle clusters 8 + 6): reduced vs full exhaustive
rules, _ = cr.rules_of(json.load(open(L + "sespy-lib-v1180/data/sample_ses.json", encoding="utf-8")))
t = time.perf_counter()
full = dynamics.boolean_attractors(rules, max_nodes=20)
t_full = time.perf_counter() - t
want = {frozenset(a["states"]): a["basin_size"] for a in full["attractors"]}
got, (U, C, R) = cr.reduced_attractors(rules)
print(f"sample n={len(rules)} U={len(U)} C={len(C)} R={len(R)}: attractors full={len(want)} reduced={len(got)}"
      f" identical(attractors+basins)={got == want}  full search {t_full:.1f}s")
print("  basin sizes:", sorted(want.values(), reverse=True))

# (3) Caribbean fixed points by FVS enumeration (exact for fixed points: removing the FVS leaves a DAG,
# so FVS values determine every other node at a fixed point)
rules, _ = cr.rules_of(json.load(open(T + "Caribbean_SES_Template.json", encoding="utf-8")))
g = cr.graph(rules)
n = len(rules)
h = g.copy()
fvs = []
while True:
    cyc = [c for c in nx.strongly_connected_components(h) if len(c) > 1 or any(h.has_edge(v, v) for v in c)]
    if not cyc:
        break
    big = max(cyc, key=len)
    v = max(big, key=lambda x: h.in_degree(x) * h.out_degree(x))
    h.remove_node(v)
    fvs.append(v)
order = list(nx.topological_sort(h))
assert nx.is_directed_acyclic_graph(h)


def node_val(j, x):
    r = rules[j]
    inflow = 0.0
    for i, w in r["activators"]:
        inflow += w * ((x >> i) & 1)
    for i, w in r["inhibitors"]:
        inflow += w * ((x >> i) & 1)
    return inflow > r["threshold"]


t = time.perf_counter()
fixed = []
for a in range(1 << len(fvs)):
    x = 0
    for k, v in enumerate(fvs):
        if (a >> k) & 1:
            x |= 1 << v
    for j in order:  # DAG part: value determined by already-set predecessors
        if node_val(j, x):
            x |= 1 << j
    if int(cr.next_states(rules, np.array([x], dtype=np.int64))[0]) == x:  # full-kernel confirmation
        fixed.append(x)
dt = time.perf_counter() - t
print(f"Caribbean n={n} FVS={len(fvs)}: {1 << len(fvs)} assignments checked in {dt:.2f}s ->"
      f" {len(fixed)} fixed points; on-counts {[bin(x).count('1') for x in fixed]}")
# sampling cross-check: which fixed points do random full starts reach?
rng = np.random.default_rng(3)
S = 5000
st = rng.integers(0, 2, size=(S, n)) @ (1 << np.arange(n, dtype=np.int64))
for _ in range(400):
    st = cr.next_states(rules, st)
nx2 = cr.next_states(rules, st)
settled_fixed = st[nx2 == st]
print(f"  sampling {S} starts, 400 steps: {np.count_nonzero(nx2 == st)} on fixed points,"
      f" distinct {len(set(settled_fixed.tolist()))}, all in FVS set: {set(settled_fixed.tolist()) <= set(fixed)}")
