"""Create runs: WS/<task>/<arm>/run-<k>/{repo,outputs,TASK.md}; simulator prompts in WS/_sim/.
usage: [EVAL_TASKS=tasks-v4] [EVAL_ARMS=a,b] [EVAL_ONLY=task,task] setup.py WS [runs=3]"""
import pathlib, shutil, sys, json, os
E = pathlib.Path(__file__).resolve().parent.parent
WS = pathlib.Path(sys.argv[1]).resolve(); RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
ARMS = os.environ.get("EVAL_ARMS", "prime-flow,superpowers,mattpocock,pstack").split(",")
TASKS = E / os.environ.get("EVAL_TASKS", "tasks")
SIM = WS / "_sim"; (SIM / "briefs").mkdir(parents=True, exist_ok=True); (SIM / "logs").mkdir(exist_ok=True)
ONLY = set(filter(None, os.environ.get("EVAL_ONLY", "").split(",")))
for tdir in sorted(p for p in TASKS.iterdir() if (p / "request.md").exists() and (not ONLY or p.name in ONLY)):
    task = tdir.name
    shutil.copy(tdir / "brief.md", SIM / "briefs" / f"{task}.md")
    request = (tdir / "request.md").read_text().strip()
    for arm in ARMS:
        for k in range(1, RUNS + 1):
            run = WS / task / arm / f"run-{k}"; repo, out = run / "repo", run / "outputs"
            if not repo.exists():
                import subprocess
                subprocess.run(["git", "clone", "-q", str(tdir / "repo.bundle"), str(repo)], check=True)
                subprocess.run(["git", "-C", str(repo), "checkout", "-q", "-B", "main", "origin/HEAD"], capture_output=True)
                for b in subprocess.run(["git", "-C", str(repo), "for-each-ref", "--format=%(refname:strip=3)", "refs/remotes/origin"], capture_output=True, text=True).stdout.split():
                    if b not in ("HEAD", "main"): subprocess.run(["git", "-C", str(repo), "branch", "-q", b, f"origin/{b}"], check=True)
                subprocess.run(["git", "-C", str(repo), "remote", "remove", "origin"], check=True)
            out.mkdir(parents=True, exist_ok=True)
            rid = f"{task}--{arm}--{k}"
            sim = SIM / f"{rid}.md"
            sim.write_text((E / "harness/simulator.md").read_text()
                           .replace("BRIEF_PATH", str(SIM / "briefs" / f"{task}.md"))
                           .replace("LOG_PATH", str(SIM / "logs" / f"{rid}.md")))
            (run / "TASK.md").write_text(f"""# Task

You are an AI coding assistant working for a user on their project. Treat this exactly as a real session.

- Project (a git repo; `cd` into it and work only there): {repo}
- Outputs directory: {out}
- Don't read or change anything outside those two directories, except skill and plugin files under `~/.claude/plugins/`. Python 3 and pytest are installed.

## Your workflow

{(E / "arms" / f"{arm}.md").read_text().strip()}

When your workflow tells you to use a skill, use the Skill tool if it works for that skill; if the Skill tool refuses (some skills are user-only), read that skill's SKILL.md from its plugin directory and follow it instead. Pick models for any helper agents you start however your workflow advises.

## Talking to the user

The user isn't in this chat. Every message you would send them (a question, a round of questions, a playback, a request to approve a document, a progress update that needs an answer, or a question about how to finish) goes through a relay agent:

- Agent tool, `subagent_type: "general-purpose"`, `description: "user-sim"`, `model: "opus"`, prompt: `Read {sim} and follow it exactly.` followed by a blank line and your full message to the user.

The relay's final reply is the user's answer: treat it exactly as a reply from the user. One message at a time; wait for each answer. Never read anything under `{SIM}` yourself, and don't use AskUserQuestion. Wherever your workflow says to ask, confirm or wait for the user, use the relay; never invent the user's answers.

## Finishing

Keep going until the feature is built, tested and committed on a local branch as your workflow directs, or the user tells you to stop. When you believe you're done, tell the user through the relay what you built and wait for their reply; if they ask for anything more, do it and report again. You're finished only once a report gets nothing but an acknowledgement. Don't push and don't open a pull request. Leave the finished work checked out in the project directory. Then write `{out}/worklog.md`: the stages you went through, the key decisions and who made each (user or you), and the commands you ran with short real excerpts of their output, especially test runs. If writing it is blocked, put it in your final message. Keep your final message under 10 lines.

## The user's first message

{request}
""")
print("ok", len(list(WS.glob("*/*/run-*"))))
