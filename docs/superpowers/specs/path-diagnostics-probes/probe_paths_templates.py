"""Probe for the path-diagnostics spec:
(a) truncation frequency of causal_paths at the panel defaults (max_length=8, max_paths=100)
    over all shipped templates (all ordered pairs, or a seeded sample of 400 for big ones);
(b) duplicate (source, target) connections per template;
(c) cost of a path_sensitivity-style loop: n_draws x (perturb + causal_paths) on the heaviest pair."""
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from sespy.data_structure import IsaData, Project
from sespy.network import _perturbed_connections, causal_paths

LIB = Path(sys.argv[1])
files = sorted((LIB / "sespy" / "templates").rglob("*.json"))
tot_pairs = tot_trunc = 0
heavy = (0.0, None, None, None)
for f in files:
    try:
        isa = Project.from_dict(json.loads(f.read_text(encoding="utf-8"))).isa_data
    except Exception as exc:  # noqa: BLE001
        print(f"skip {f.name}: {exc}")
        continue
    ids = [e.id for e in isa.elements]
    dup = sum(v - 1 for v in Counter((c.source, c.target) for c in isa.connections).values() if v > 1)
    pairs = [(s, t) for s in ids for t in ids if s != t]
    if len(pairs) > 400:
        random.Random(0).shuffle(pairs)
        pairs = pairs[:400]
    trunc, worst = 0, 0.0
    t_all = time.perf_counter()
    for s, t in pairs:
        t0 = time.perf_counter()
        r = causal_paths(isa, s, t)
        dt = time.perf_counter() - t0
        if r["truncated"]:
            trunc += 1
        if dt > worst:
            worst = dt
        if dt > heavy[0]:
            heavy = (dt, f, s, t)
    tot_pairs += len(pairs)
    tot_trunc += trunc
    if trunc or dup or worst > 0.2:
        print(f"{f.relative_to(LIB / 'sespy' / 'templates')}: n={len(ids)} e={len(isa.connections)} dup_pairs={dup} truncated {trunc}/{len(pairs)} worst {worst:.3f}s total {time.perf_counter()-t_all:.1f}s", flush=True)
print(f"ALL: {len(files)} templates, truncated {tot_trunc}/{tot_pairs} pairs")
dt, f, s, t = heavy
print(f"heaviest pair: {f.name} {s}->{t} {dt:.3f}s")
isa = Project.from_dict(json.loads(f.read_text(encoding="utf-8"))).isa_data
rng = np.random.default_rng(0)
t0 = time.perf_counter()
for _ in range(200):
    conns = _perturbed_connections(isa, 0.5, rng)
    causal_paths(IsaData(elements=isa.elements, connections=conns), s, t)
print(f"200 draws on heaviest pair: {time.perf_counter()-t0:.1f}s")
