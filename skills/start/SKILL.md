---
name: start
description: The design-to-delivery workflow for building anything non-trivial in a codebase. Grills the user in rounds of repo-grounded questions to settle the design, writes it up as a spec the user approves, plans from the spec, then builds the plan task by task with TDD, systematic debugging and code review. Use this whenever the user wants to build a feature, add functionality, change behaviour, or start a project.
---

# Prime flow

One workflow from idea to merged code. Each stage's method came out ahead in a head-to-head eval of design-to-delivery workflows; the stages are inlined here so the skill runs self-contained, with no other plugin installed.

The stages connect through written artifacts: the grilling ends in a spec, the spec becomes a plan, the plan drives the build. Don't skip the writing — a shared understanding held only in chat doesn't survive the handoff to planning.

Before each stage, tell the user in one line which stage you're starting (for example "Design settled; writing it up as a spec next.").

## Stage 0: Size the work

Read the request and the relevant code first.

| Size | Do this |
|------|---------|
| A quick, clear task (everything that matters is in the request) | Do it, then say what you did. This workflow doesn't apply. |
| A small change | Grill briefly (stage 1), restate the agreed change in chat, get a yes, then build it test-first (stage 4's TDD rule). Skip stages 2–3. |
| A project | Run every stage below. |

If the work turns out bigger mid-way, stop, say so, and step up a size.

## Stage 1: Grill

Settle the design by questioning the user in rounds. Each round is a numbered list; every question comes with your recommended answer, so the user can reply "1 yes, 2 the second option, 3 your call". Between rounds, update your picture and work out the next frontier of unknowns.

Keep the user's load light. In the end-to-end eval these flows asked about 15 questions per run, and the arm that asked fewer, simpler questions was rated easier to work with:

- **Open with how it's used.** Make the first round's first one or two questions open ones about the real use: who uses the result, what they do with it, and what goes wrong today. In the eval, answers to those questions surfaced most of the hidden needs (Excel on Windows, people in other timezones) before any detailed question.
- **At most five questions a round.** If the frontier holds more, ask the five that unblock the most, and leave the rest for the next round.
- **Check each question against the repo before sending it.** If the code, config or docs can answer it (which setting exists, which timezone type is used, what the CLI already does), look it up and state the finding instead of asking.

As terms and decisions settle, record them so they outlive the chat:

- **Glossary:** project terms with their agreed meaning, in `docs/GLOSSARY.md`. Add or sharpen an entry whenever a round settles what a word means here.
- **ADRs:** one short file per significant decision in `docs/adr/NNNN-<slug>.md` — context, the decision as the user worded it, consequences.

The stage ends when the frontier is empty **and** the user confirms you share an understanding. Don't move on before that confirmation.

## Stage 2: Write the spec

Write the design at `docs/specs/YYYY-MM-DD-<topic>-design.md`, unless the user prefers another location. Write it for a talented engineer who must plan from it without talking to the user. Cover:

- the intent and the why
- goals, non-goals and anti-goals
- constraints
- the decisions from the grilling, worded as the user decided them, with links to any glossary entries and ADRs written in stage 1
- what's left to the builder

Mark your own calls as yours. Only what the user said goes in as theirs.

**Builder check.** A fresh reader catches what the grilling left implicit. Dispatch a fresh general-purpose subagent with this brief (fill in the blanks); if you have no subagent tool, read the spec as that builder yourself:

> You are a talented engineer joining this project cold. Your only input is the design spec at `<spec path>`; you cannot talk to the person who wrote it. Read it, then list every question you would need answered before you could plan and build this with confidence — ambiguities, missing constraints, undefined terms, choices the spec leaves open that change what gets built. Number the questions. Don't propose solutions; just surface what the spec doesn't settle.

Sort what comes back into three piles:

- **Already answered** by the grilling or the repo: add the answer to the spec.
- **Minor:** a sensible builder could settle it. Settle it, and mark it in the spec as your call.
- **The user's:** only the user can answer it, and the answer changes what gets built. Ask these in one round, numbered, each with your recommended answer, grilling-style. Then update the spec.

Commit the spec. Hand it over with a short list of the calls you made, so the user can check them while reading.

**Gate:** nothing gets built until the user approves the spec. "Building" covers product code, scaffolding, installing dependencies, and invoking any implementation skill. Reading and exploring are fine.

## Stage 3: Plan

Once the spec is approved, turn it into a plan at `docs/plans/YYYY-MM-DD-<topic>-plan.md`. Write it for an implementer who has the spec but none of this conversation:

- Break the work into tasks of a few hours at most, ordered so every task lands on a green test suite.
- Per task: the exact files to create or change, the observable behaviour it adds, the test(s) that prove it, and how to verify (the command to run and what its output should show).
- State what the plan deliberately leaves out.

Use no other planning route for this — no separate planner or architect agent; the spec plus this plan is the design authority. Show the plan to the user before building.

## Stage 4: Build

Execute the plan task by task. For each task, prefer dispatching a fresh implementer subagent with the task's section of the plan; run tasks yourself if subagents aren't available or the user asks for in-session work. Keep these disciplines on throughout, and pass them to every implementer:

- **TDD:** every task is test-first. Write the test, run it, show it failing for the right reason, then write the minimum code that passes, then refactor on green. No production code without a failing test demanding it. Implementers must show each failing test run before the code that passes it.
- **Debugging:** any unexpected failure, flaky test or bug gets diagnosed before any fix is attempted: reproduce it, read the actual error, trace it to a root cause you can state in one sentence, and only then change code. If a fix fails twice, stop and re-examine the diagnosis instead of trying a third variation. That covers failures in your own work, in an implementer's report, and a reviewer's finding you can't explain.
- **Review:** after each task (or small group of tasks), have a fresh subagent review the diff against the plan: correctness first, then whether the tests actually pin the behaviour, then simplicity. Act on findings by verifying them against the code — push back with evidence on a finding that's wrong, fix what's real, and re-run the tests after.
- **Models:** implementer subagents for well-specified tasks run on sonnet. Keep opus for reviewers, for a fix that has already failed twice, and for tasks the plan marks as hard. In the eval, opus made up four-fifths of this workflow's cost, which put it at the top of the four arms.

**Before claiming done:** run the full test suite and any linters the repo has, and show the output. No success claims without the passing run in front of you. Then ask the user how to land the branch (PR, merge, or leave it) rather than assuming.

## If other workflow plugins are installed

This skill already covers design questioning, spec writing, planning, TDD, debugging and review. If plugins such as superpowers or mattpocock-skills are present, don't also run their overlapping skills (brainstorming, grilling, tdd, code-review, writing-plans and kin) in the same run — they'd repeat a stage in a different style. Running this workflow means these stages, as written here.
