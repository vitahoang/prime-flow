"""Objective scores per run: hidden tests by requirement id, user rounds, leak + crossover checks.
usage: score.py WS SUBAGENTS_DIR  -> writes <run>/outputs/scores.json, prints a table"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, collections, xml.etree.ElementTree as ET
E = pathlib.Path(__file__).resolve().parent.parent
TASKS = E / os.environ.get("EVAL_TASKS", "tasks")
WS, SUB = pathlib.Path(sys.argv[1]).resolve(), pathlib.Path(sys.argv[2])
PLUG = {"prime-flow": None, "plain": None, "superpowers": "superpowers", "mattpocock": "mattpocock-skills", "pstack": "pstack"}
OTHER = {"superpowers", "mattpocock-skills", "pstack", "prime-flow"}
meta = {f.name[6:-10]: json.loads(f.read_text()) for f in SUB.glob("agent-*.meta.json")}
kids = collections.defaultdict(list)
for a, m in meta.items():
    if m.get("parentAgentId"): kids[m["parentAgentId"]].append(a)
def tree(a):
    st, out = [a], []
    while st:
        x = st.pop()
        if meta.get(x, {}).get("description") == "user-sim": continue
        out.append(x); st += kids.get(x, [])
    return out
def tool_inputs(a):
    f = SUB / f"agent-{a}.jsonl"
    for l in (f.open() if f.exists() else []):
        try: m = json.loads(l).get("message")
        except Exception: continue
        if isinstance(m, dict) and isinstance(m.get("content"), list):
            for c in m["content"]:
                if c.get("type") == "tool_use": yield c.get("name"), json.dumps(c.get("input"))
runs = {}
for a, m in sorted(meta.items(), key=lambda kv: (SUB / f"agent-{kv[0]}.jsonl").stat().st_mtime if (SUB / f"agent-{kv[0]}.jsonl").exists() else 0):
    if m.get("description", "").startswith("RUN ") and m.get("spawnDepth") == 1: runs[m["description"][4:]] = a
FLT = sys.argv[3] if len(sys.argv) > 3 else ""
for run in sorted(WS.glob("*/*/run-*")):
    if FLT not in str(run) or not (run / "outputs/timing.json").exists(): continue
    task, arm, k = run.parts[-3], run.parts[-2], run.parts[-1][4:]
    rid = f"{task}--{arm}--{k}"; res = {}
    t = pathlib.Path(tempfile.mkdtemp()) / "r"
    shutil.copytree(run / "repo", t, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    shutil.copy(TASKS / task / "hidden/test_hidden.py", t / "test_hidden_zz.py")
    x = t / "j.xml"
    try: subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "addopts=", "test_hidden_zz.py", f"--junitxml={x}"], cwd=t, capture_output=True, timeout=600)
    except subprocess.TimeoutExpired: pass
    ids = collections.defaultdict(list)
    if x.exists():
        for tc in ET.parse(x).iter("testcase"):
            mm = re.match(r"test_([A-Z]\d+)_", tc.get("name")); ok = not any(c.tag in ("failure", "error") for c in tc)
            if mm: ids[mm.group(1)].append(ok)
    shutil.rmtree(t.parent)
    req = {i: all(v) for i, v in ids.items()}
    ht = [i for i in req if i[0] in "HT"]; ex = [i for i in req if i[0] == "E"]
    res["requirements"] = req
    res["intent_match"] = round(sum(req[i] for i in ht) / len(ht), 3) if ht else None
    res["explicit_pass"] = round(sum(req[i] for i in ex) / len(ex), 3) if ex else None
    logs = [WS / "_sim/logs" / f"{rid}.md", run / "outputs/user_log.md"]
    res["user_rounds"] = sum(l.read_text().count("### Assistant") for l in logs if l.exists())
    cm = json.loads((TASKS / task / "meta.json").read_text()).get("change_of_mind")
    mk = (cm.get("markers") or [cm["marker"]]) if cm else []
    if cm: res["change_delivered"] = all(any(m.lower() in l.read_text().lower() for l in logs if l.exists()) for m in mk)
    a = runs.get(f"{task} {arm} r{k}")
    if a:
        leaks, cross = [], set()
        for x in tree(a):
            for name, inp in tool_inputs(x):
                if name in ("Read", "Bash", "Grep", "Glob", "Agent") and ("_sim/briefs" in inp or re.search(r"/evals/prime-flow/tasks[^/]*/", inp)): leaks.append(f"{x}:{name}")
                if name == "Skill":
                    sk = json.loads(inp).get("skill", ""); pl = sk.split(":")[0] if ":" in sk else None
                    if PLUG[arm] and pl in OTHER and pl != PLUG[arm]: cross.add(sk)
                for pl in OTHER:
                    if PLUG[arm] and pl != PLUG[arm] and re.search(rf"/{re.escape(pl)}/[^\"]*SKILL\.md", inp): cross.add(pl + " SKILL.md")
        res["leaks"], res["crossover"] = leaks[:5], sorted(cross)
        if cm and not res["change_delivered"]:
            sims = [k for x in tree(a) for k in kids.get(x, []) if meta[k].get("description") == "user-sim"]
            txt = "".join((SUB / f"agent-{k}.jsonl").read_text().lower() for k in sims if (SUB / f"agent-{k}.jsonl").exists())
            res["change_delivered"] = all(m.lower() in txt for m in mk)
    else: res["leaks"] = res["crossover"] = "run agent not found"
    res["commits"] = subprocess.run(["git", "-C", run / "repo", "rev-list", "--count", "HEAD"], capture_output=True, text=True).stdout.strip()
    (run / "outputs/scores.json").write_text(json.dumps(res, indent=1))
    print(f"{rid:45} intent={res['intent_match']} explicit={res['explicit_pass']} rounds={res['user_rounds']} leaks={len(res['leaks']) if isinstance(res['leaks'], list) else res['leaks']} cross={res['crossover']}")
