"""Dollar cost of runs, helpers included, user-sim excluded.
usage: cost.py SUBAGENTS_DIR  -> prints JSON {run_description: {usd, tokens, agents, by_model, sim_calls}}"""
import json, pathlib, sys, collections, datetime
D = pathlib.Path(sys.argv[1]); PR = json.loads((pathlib.Path(__file__).resolve().parents[3] / "vita-hud/prices.json").read_text())
meta = {f.name[len("agent-"):-len(".meta.json")]: json.loads(f.read_text()) for f in D.glob("agent-*.meta.json")}
kids = collections.defaultdict(list)
for a, m in meta.items():
    if m.get("parentAgentId"): kids[m["parentAgentId"]].append(a)
def usage(a):
    by = collections.defaultdict(lambda: [0.0, 0])
    f = D / f"agent-{a}.jsonl"
    if not f.exists(): return by
    seen = set()
    for l in f.open():
        try: d = json.loads(l)
        except Exception: continue
        m = d.get("message")
        if not isinstance(m, dict) or not m.get("usage") or d.get("requestId") in seen: continue
        seen.add(d.get("requestId")); u = m["usage"]; p = PR["models"].get(m.get("model"), {"input": 0, "output": 0})
        cc = u.get("cache_creation") or {}
        usd = (u.get("input_tokens", 0) * p["input"] + u.get("output_tokens", 0) * p["output"]
               + cc.get("ephemeral_5m_input_tokens", 0) * p["input"] * PR["cacheWrite5mMultiplier"]
               + cc.get("ephemeral_1h_input_tokens", 0) * p["input"] * PR["cacheWrite1hMultiplier"]
               + u.get("cache_read_input_tokens", 0) * p["input"] * 0.1) / 1e6
        tok = u.get("input_tokens", 0) + u.get("output_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        by[m.get("model")][0] += usd; by[m.get("model")][1] += tok
    return by
out = {}
for a, m in sorted(meta.items(), key=lambda kv: (D / f"agent-{kv[0]}.jsonl").stat().st_mtime if (D / f"agent-{kv[0]}.jsonl").exists() else 0):
    if m.get("spawnDepth") != 1 or not m.get("description", "").startswith("RUN "): continue
    tot = collections.defaultdict(lambda: [0.0, 0]); n = 0; sims = 0; stack = [a]; ts = []
    while stack:
        x = stack.pop()
        if meta.get(x, {}).get("description") == "user-sim": sims += 1; continue
        n += 1
        f = D / f"agent-{x}.jsonl"
        for l in (f.open() if f.exists() else []):
            try: ts.append(datetime.datetime.fromisoformat(json.loads(l)["timestamp"].replace("Z", "+00:00")).timestamp())
            except Exception: pass
        for mod, (u, t) in usage(x).items(): tot[mod][0] += u; tot[mod][1] += t
        stack += kids.get(x, [])
    out[m["description"][4:]] = {"usd": round(sum(v[0] for v in tot.values()), 3), "tokens": sum(v[1] for v in tot.values()),
                                "agents": n, "sim_calls": sims, "active_min": round(sum(d for d in (b - a for a, b in zip(sorted(ts), sorted(ts)[1:])) if d < 600) / 60, 1), "by_model": {k: round(v[0], 3) for k, v in tot.items()}}
print(json.dumps(out, indent=1))
