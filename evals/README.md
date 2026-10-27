# prime-flow eval

End-to-end comparison of prime-flow, Superpowers-only, mattpocock-only and pstack on underspecified feature requests, with a simulated user. Terms are in `GLOSSARY.md`, decisions in `docs/adr/`, the latest results in `results.md`.

- `tasks/<name>/`: `request.md`, `brief.md` (simulator only), `meta.json`, `hidden/test_hidden.py`, `ref/`, `naive/`, `verify.py`, and `repo.bundle` (the starting repo with its history; `repo/` is the same files without `.git`). See `tasks/BUILD.md`.
- `arms/`: each arm's workflow instructions. `harness/simulator.md`: the simulated user.

Run it:

1. `python3 harness/setup.py WS 3` creates `WS/<task>/<arm>/run-<k>/` with `TASK.md`.
2. Start one top-level agent per run with the description `RUN <task> <arm> r<k>` and the prompt "Read <run>/TASK.md and carry it out exactly."
3. `python3 harness/score.py WS ~/.claude/projects/<project>/<session>/subagents` for hidden tests, rounds and leak/crossover checks; `harness/cost.py` for dollars and active minutes.
4. `python3 harness/blind.py WS BLIND`, then one grader per task with `harness/grader.md`; `harness/summarize.py WS cost.json BLIND` prints the tables.
