"""Anonymise finished runs for grading: BLIND/<task>/R01..R12/{conversation.md,worklog.md,diffstat.txt}; map in BLIND/map.json.
usage: blind.py WS BLIND"""
import json, pathlib, random, re, shutil, subprocess, sys
WS, B = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]); B.mkdir(parents=True, exist_ok=True)
RED = [(re.compile(p, re.I), "<METHOD>") for p in [r"prime-?flow", r"superpowers?", r"matt ?pocock(-skills)?", r"pstack", r"poteto(-mode|-agent)?", r"grill(-with-docs|ing)?", r"brainstorm(ing)?", r"to-spec", r"implement-spec", r"subagent-driven-development", r"writing-plans", r"executing-plans", r"arena", r"architect runners?", r"interrogate"]] + [(re.compile(r"/private/tmp/\S+"), "<PATH>"), (re.compile(r"~/\.claude/\S+"), "<PATH>")]
def red(t):
    for p, s in RED: t = p.sub(s, t)
    return t
mp = {}
for tdir in sorted(p for p in WS.iterdir() if p.is_dir() and not p.name.startswith("_")):
    runs = sorted(tdir.glob("*/run-*")); random.Random(tdir.name).shuffle(runs)
    for i, run in enumerate(runs, 1):
        lab = f"R{i:02d}"; d = B / tdir.name / lab
        if d.exists(): shutil.rmtree(d)
        d.mkdir(parents=True)
        arm, k = run.parts[-2], run.parts[-1][4:]
        logs = [WS / "_sim/logs" / f"{tdir.name}--{arm}--{k}.md", run / "outputs/user_log.md"]
        (d / "conversation.md").write_text(red("\n".join(l.read_text() for l in logs if l.exists())))
        w = run / "outputs/worklog.md"
        (d / "worklog.md").write_text(red(w.read_text()) if w.exists() else "(no worklog)")
        base = subprocess.run(["git", "-C", run / "repo", "rev-list", "--max-parents=0", "HEAD"], capture_output=True, text=True).stdout.split()[0]
        ds = subprocess.run(["git", "-C", run / "repo", "diff", "--stat", base], capture_output=True, text=True).stdout
        (d / "diffstat.txt").write_text(red(ds))
        mp[f"{tdir.name}/{lab}"] = f"{arm}/run-{k}"
(B / "map.json").write_text(json.dumps(mp, indent=1)); print("ok", len(mp))
