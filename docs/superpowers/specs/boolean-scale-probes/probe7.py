"""Caribbean (78 nodes) sampled convergence: 2000 starts x 1000 steps, repeat detection per trajectory."""
import json, time
import numpy as np
import core_reduction as cr

T = "C:/Users/arturas.baziukas/AppData/Local/sespy-lib-v1180/sespy/templates/marinesabres/"
rules, _ = cr.rules_of(json.load(open(T + "Caribbean_SES_Template.json", encoding="utf-8")))
n = len(rules)


def step(X):
    out = np.zeros_like(X)
    for j, r in enumerate(rules):
        inflow = np.zeros(X.shape[0])
        for i, w in r["activators"]:
            inflow = inflow + w * X[:, i]
        for i, w in r["inhibitors"]:
            inflow = inflow + w * X[:, i]
        out[:, j] = inflow > r["threshold"]
    return out


S, STEPS = 2000, 1000
rng = np.random.default_rng(0)
X = rng.integers(0, 2, size=(S, n)).astype(np.uint8)
t = time.perf_counter()
hist = [np.packbits(X, axis=1)]
for _ in range(STEPS):
    X = step(X)
    hist.append(np.packbits(X, axis=1))
H = np.stack(hist, axis=1)  # (S, STEPS+1, bytes)
t_step = time.perf_counter() - t
att, unconv, trans = {}, 0, []
for row in H:
    seen = {}
    for k in range(row.shape[0]):
        key = row[k].tobytes()
        if key in seen:
            cyc = frozenset(r.tobytes() for r in row[seen[key]:k])
            att[cyc] = att.get(cyc, 0) + 1
            trans.append(seen[key])
            break
        seen[key] = k
    else:
        unconv += 1
print(f"Caribbean n={n}: {S} starts x {STEPS} steps in {t_step:.1f}s (+ detection {time.perf_counter() - t - t_step:.1f}s)")
print(f"  unconverged {unconv}; attractors reached {len(att)}; periods/hits {sorted(((len(c), h) for c, h in att.items()), key=lambda x: -x[1])[:10]}")
if trans:
    print(f"  transient length: median {int(np.median(trans))}, max {max(trans)}")
