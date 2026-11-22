"""(3) Caribbean fixed points via FVS with Python ints; (4) R/BoolNet rule semantics on Fisheries by sampling."""
import json, time
import numpy as np
import networkx as nx
import core_reduction as cr
from sespy import dynamics
from sespy.data_structure import Project

L = "C:/Users/arturas.baziukas/AppData/Local/"
T = L + "sespy-lib-v1180/sespy/templates/marinesabres/"


def step_bool(rules, X):
    """SESPy threshold kernel on a (S, n) uint8 matrix, same summation order."""
    out = np.zeros_like(X)
    for j, r in enumerate(rules):
        inflow = np.zeros(X.shape[0])
        for i, w in r["activators"]:
            inflow = inflow + w * X[:, i]
        for i, w in r["inhibitors"]:
            inflow = inflow + w * X[:, i]
        out[:, j] = inflow > r["threshold"]
    return out


def val(r, x):
    inflow = 0.0
    for i, w in r["activators"]:
        inflow += w * ((x >> i) & 1)
    for i, w in r["inhibitors"]:
        inflow += w * ((x >> i) & 1)
    return inflow > r["threshold"]


# (3) Caribbean
rules, _ = cr.rules_of(json.load(open(T + "Caribbean_SES_Template.json", encoding="utf-8")))
n = len(rules)
g = cr.graph(rules)
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
t = time.perf_counter()
fixed = []
for a in range(1 << len(fvs)):
    x = 0
    for k, v in enumerate(fvs):
        if (a >> k) & 1:
            x |= 1 << v
    for j in order:
        if val(rules[j], x):
            x |= 1 << j
    nxt = 0
    for j, r in enumerate(rules):
        if val(r, x):
            nxt |= 1 << j
    if nxt == x:
        fixed.append(x)
print(f"Caribbean n={n} FVS={len(fvs)}: {1 << len(fvs)} assignments in {time.perf_counter() - t:.2f}s -> "
      f"{len(fixed)} fixed points; on-counts {[bin(x).count('1') for x in fixed]}")
rng = np.random.default_rng(3)
S = 5000
X = rng.integers(0, 2, size=(S, n)).astype(np.uint8)
for _ in range(400):
    X = step_bool(rules, X)
X2 = step_bool(rules, X)
fp_rows = np.all(X2 == X, axis=1)
reached = {int("".join(str(b) for b in row[::-1]), 2) for row in X[fp_rows]}
print(f"  sampling {S} starts x 400 steps: {fp_rows.sum()} settled on fixed points, distinct {len(reached)}, "
      f"all among the FVS-enumerated set: {reached <= set(fixed)}; not settled (cycles/long transients): {S - fp_rows.sum()}")

# (4) R semantics on Fisheries: OR over regulators, inhibitor = NOT x, no regulators -> keeps its value
p = Project.from_dict(json.load(open(T + "Fisheries_SES_Template.json", encoding="utf-8")))
M, ids = dynamics.isa_to_numeric_matrix(p.isa_data)
B = np.sign(M)
n = B.shape[0]
pos = [np.where(B[:, j] == 1)[0] for j in range(n)]
neg = [np.where(B[:, j] == -1)[0] for j in range(n)]


def step_r(X):
    out = np.zeros_like(X)
    for j in range(n):
        if len(pos[j]) == 0 and len(neg[j]) == 0:
            out[:, j] = X[:, j]
        else:
            v = np.zeros(X.shape[0], dtype=bool)
            for i in pos[j]:
                v |= X[:, i] == 1
            for i in neg[j]:
                v |= X[:, i] == 0
            out[:, j] = v
    return out


S = 20000
X = rng.integers(0, 2, size=(S, n)).astype(np.uint8)
H = [X]
for _ in range(200):
    X = step_r(X)
    H.append(X)
H = np.stack(H, axis=1)  # (S, steps, n)
keys = (H.astype(np.int64) * (1 << np.arange(n, dtype=np.int64))).sum(axis=2)
att = {}
for row in keys:
    seen = {}
    for k, s in enumerate(row.tolist()):
        if s in seen:
            c = frozenset(row[seen[s]:k].tolist())
            att[c] = att.get(c, 0) + 1
            break
        seen[s] = k
periods = sorted((len(c), cnt) for c, cnt in att.items())
print(f"Fisheries under R/BoolNet rules (sampled {S}): {len(att)} distinct attractors reached; "
      f"periods/hits (first 10): {periods[:10]}; sources (keep value): {sum(1 for j in range(n) if len(pos[j]) + len(neg[j]) == 0)}")
print("SESPy threshold rules on the same network: exactly 1 attractor (all-off), basin 2^26")
