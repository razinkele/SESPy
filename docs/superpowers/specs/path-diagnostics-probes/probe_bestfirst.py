"""Probe decision 3: best-first path enumeration (nx.shortest_simple_paths, cost -log w + lam)
vs causal_paths' enumeration-order truncation, on the largest shipped templates."""
import itertools
import json
import math
import sys
import time
from pathlib import Path

import networkx as nx
from sespy.bayes import STRENGTH_LINK
from sespy.data_structure import Project
from sespy.network import causal_paths

LIB = Path(sys.argv[1])
LAM = 0.2
K = 100
MAXLEN = 8

for name in ["marinesabres/Caribbean_SES_Template.json"] + [str(p.relative_to(LIB / "sespy/templates")) for p in sorted((LIB / "sespy/templates").rglob("*.json"))][:0]:
    proj = Project.from_dict(json.loads((LIB / "sespy/templates" / name).read_text(encoding="utf-8")))
    isa = proj.isa_data
    g = nx.DiGraph()
    for c in isa.connections:
        w = STRENGTH_LINK.get(c.strength, STRENGTH_LINK["medium"])
        g.add_edge(c.source, c.target, cost=-math.log(w) + LAM)
    print(f"{name}: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")
    nodes = sorted(g.nodes)
    # pick pairs with many paths: drivers -> welfare-ish, approximated by highest out/in degree
    srcs = sorted(nodes, key=lambda n: -g.out_degree(n))[:4]
    tgts = sorted(nodes, key=lambda n: -g.in_degree(n))[:4]
    worst, missed = 0.0, 0
    for s, t in itertools.product(srcs, tgts):
        if s == t or not nx.has_path(g, s, t):
            continue
        t0 = time.perf_counter()
        best = []
        seen = 0
        for p in nx.shortest_simple_paths(g, s, t, weight="cost"):
            seen += 1
            if seen > 3000 or time.perf_counter() - t0 > 30:
                print(f"    gave up after {seen} yielded paths, {time.perf_counter()-t0:.1f}s, kept {len(best)}", flush=True)
                break
            if len(p) - 1 > MAXLEN:
                continue  # no cutoff in nx: filter (cost of the probe includes the skipped ones)
            best.append(p)
            if len(best) >= K:
                break
        dt = time.perf_counter() - t0
        worst = max(worst, dt)
        t1 = time.perf_counter()
        cp = causal_paths(isa, s, t, max_length=MAXLEN, max_paths=K)
        dt2 = time.perf_counter() - t1
        cp_set = {tuple(r["path"]) for r in cp["paths"]}
        top = tuple(best[0]) if best else None
        if top and top not in cp_set and cp.get("truncated"):
            missed += 1
        print(flush=True); print(f"  {s}->{t}: best-first top{len(best)} {dt:.2f}s | causal_paths {len(cp_set)} paths truncated={cp.get('truncated')} {dt2:.2f}s | strongest path in causal_paths' set: {top in cp_set}")
    print(f"  worst best-first time {worst:.2f}s; pairs where truncation missed the strongest path: {missed}")
