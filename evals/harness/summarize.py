"""Combine scores.json, cost.json and blind grading into a table. usage: summarize.py WS COST_JSON BLIND"""
import json, pathlib, sys, statistics as st, collections
WS, COST, B = pathlib.Path(sys.argv[1]), json.loads(pathlib.Path(sys.argv[2]).read_text()), pathlib.Path(sys.argv[3])
mp = json.loads((B / "map.json").read_text()); inv = {k.split("/")[0] + "/" + v: k for k, v in mp.items()}
ARMS = ["prime-flow", "superpowers", "mattpocock", "pstack"]
rows = collections.defaultdict(list)
for run in sorted(WS.glob("*/*/run-*")):
    t, a, k = run.parts[-3], run.parts[-2], run.parts[-1][4:]
    s = json.loads((run / "outputs/scores.json").read_text()); c = COST.get(f"{t} {a} r{k}", {})
    g = {}; lab = inv.get(f"{t}/{a}/run-{k}")
    if lab and (B / lab / "grading.json").exists(): g = json.loads((B / lab / "grading.json").read_text())
    rk = {}
    if (B / t / "ranking.json").exists():
        r = json.loads((B / t / "ranking.json").read_text())
        for key in ("by_user_experience", "by_process"):
            if lab and lab.split("/")[1] in r.get(key, []): rk[key] = r[key].index(lab.split("/")[1]) + 1
    rows[(t, a)].append(dict(intent=s["intent_match"], explicit=s["explicit_pass"], rounds=s["user_rounds"], usd=c.get("usd"), mins=c.get("active_min"),
        q=g.get("questions_total"), cf=g.get("code_fact_questions"), proc=g.get("process_quality_1to10"), clar=g.get("clarity_1to5"),
        ux_rank=rk.get("by_user_experience"), proc_rank=rk.get("by_process"), req=s["requirements"]))
def agg(xs):
    xs = [x for x in xs if x is not None]
    return f"{st.mean(xs):.2f} [{min(xs):g}–{max(xs):g}]" if xs else "-"
keys = ["intent", "explicit", "rounds", "q", "cf", "clar", "proc", "ux_rank", "proc_rank", "usd", "mins"]
print("| task | arm | " + " | ".join(keys) + " |"); print("|" + "---|" * (len(keys) + 2))
for t in sorted({t for t, _ in rows}):
    for a in ARMS:
        R = rows[(t, a)]; print(f"| {t} | {a} | " + " | ".join(agg([r[k] for r in R]) for k in keys) + " |")
print("\n**All tasks**\n"); print("| arm | " + " | ".join(keys) + " |"); print("|" + "---|" * (len(keys) + 1))
for a in ARMS:
    R = [r for (t, aa), v in rows.items() if aa == a for r in v]; print(f"| {a} | " + " | ".join(agg([r[k] for r in R]) for k in keys) + " |")
print("\n**Hidden requirements missed (runs out of 3)**\n")
for t in sorted({t for t, _ in rows}):
    for a in ARMS:
        miss = collections.Counter(i for r in rows[(t, a)] for i, ok in r["req"].items() if not ok)
        if miss: print(f"- {t} / {a}: " + ", ".join(f"{i}×{n}" for i, n in sorted(miss.items())))
