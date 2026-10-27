---
name: start
description: The design-to-delivery workflow for building anything non-trivial in a codebase. Grills the user with mattpocock-skills (grilling + domain-modeling), writes the result up as a Superpowers spec, then hands off to superpowers:writing-plans and builds the plan with Superpowers TDD, systematic debugging and code review. Use this whenever the user wants to build a feature, add functionality, change behaviour, or start a project, in place of superpowers:brainstorming. Only skip it when the user explicitly invoked /superpowers:brainstorming.
---

# Prime flow

This workflow links two plugins at the point where each did best in a head-to-head eval:

- **Design:** mattpocock grilling. Its rounds of numbered, repo-grounded questions, each with a recommended answer, got better results than brainstorming's single open question.
- **Everything after:** Superpowers. Its code review clearly outperformed mattpocock's, and its TDD and debugging matched or edged ahead.

The two halves don't connect on their own. Grilling ends in a shared understanding held in chat. Superpowers' planning expects a written, approved design document. Stage 2 below is that bridge, so don't skip it.

Before each stage, tell the user in one line which stage you're starting (for example "Design settled; writing it up as a spec next.").

## Stage 0: Size the work

Read the request and the relevant code first.

| Size | Do this |
|------|---------|
| A quick, clear task (everything that matters is in the request) | Do it, then say what you did. This workflow doesn't apply. |
| A small change | Grill briefly (stage 1), restate the agreed change in chat, get a yes, then build it with superpowers:test-driven-development. Skip stages 2–3. |
| A project | Run every stage below. |

If the work turns out bigger mid-way, stop, say so, and step up a size.

## Stage 1: Grill

Invoke the Skill tool twice: `mattpocock-skills:grilling` and `mattpocock-skills:domain-modeling`. This is what `/mattpocock-skills:grill-with-docs` does; that wrapper can only be started by the user, so call the two skills directly. Follow them fully:

- Ask in rounds.
- Look facts up yourself rather than asking the user for them.
- Record terms and decisions in the glossary and ADRs as they settle.

Keep the user's load light. In the end-to-end eval these flows asked about 15 questions per run, and the arm that asked fewer, simpler questions was rated easier to work with:

- **Open with how it's used.** Make the first round's first one or two questions open ones about the real use: who uses the result, what they do with it, and what goes wrong today. In the eval, answers to those questions surfaced most of the hidden needs (Excel on Windows, people in other timezones) before any detailed question.
- **At most five questions a round.** If the frontier holds more, ask the five that unblock the most, and leave the rest for the next round.
- **Check each question against the repo before sending it.** If the code, config or docs can answer it (which setting exists, which timezone type is used, what the CLI already does), look it up and state the finding instead of asking.

The stage ends when the frontier is empty **and** the user confirms you share an understanding. Don't move on before that confirmation.

Do not also run superpowers:brainstorming. It would ask the same questions again in a different style.

## Stage 2: Write the spec

Write the design at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, unless the user prefers another location. That's where superpowers:writing-plans looks for it. Write it for a talented engineer who must plan from it without talking to the user. Cover:

- the intent and the why
- goals, non-goals and anti-goals
- constraints
- the decisions from the grilling, worded as the user decided them, with links to any glossary entries and ADRs written in stage 1
- what's left to the builder

Mark your own calls as yours. Only what the user said goes in as theirs.

**Builder check.** A fresh reader catches what the grilling left implicit.

1. Find the prompt with a glob for `~/.claude/plugins/cache/*/superpowers/*/skills/brainstorming/builder-check-prompt.md`, and use the newest version.
2. Dispatch a fresh general-purpose subagent with that prompt, filled in with the domain and the spec path. If you have no subagent tool, read the spec as that builder yourself.
3. Sort what comes back into three piles:
   - **Already answered** by the grilling or the repo: add the answer to the spec.
   - **Minor:** a sensible builder could settle it. Settle it, and mark it in the spec as your call.
   - **The user's:** only the user can answer it, and the answer changes what gets built. Ask these in one round, numbered, each with your recommended answer, grilling-style. Then update the spec.

Commit the spec. Hand it over with a short list of the calls you made, so the user can check them while reading.

**Gate:** nothing gets built until the user approves the spec. "Building" covers product code, scaffolding, installing dependencies, and invoking any implementation skill. Reading and exploring are fine.

## Stage 3: Plan

Once the spec is approved, invoke `superpowers:writing-plans` with the spec path, and no other planning skill. Don't use mattpocock's to-spec, to-tickets or implement-spec here, and don't use the planner or architect agents.

## Stage 4: Build

Run the plan with `superpowers:subagent-driven-development`. Use `superpowers:executing-plans` instead if subagents aren't available or the user asks for in-session execution. Those skills drive the per-task loop; keep these three disciplines on throughout:

- **TDD:** every task follows `superpowers:test-driven-development`. When dispatching an implementer subagent, tell it to use that skill and to show each failing test run before the code that passes it.
- **Debugging:** any unexpected failure, flaky test or bug goes through `superpowers:systematic-debugging` before any fix is attempted. That covers failures in your own work, in an implementer's report, and a reviewer's finding you can't explain. Pass this rule to implementer subagents too.
- **Review:** use the reviewers the execution skill dispatches. They are `superpowers:requesting-code-review`'s code reviewer; don't swap in another one. If you run a review yourself, invoke `superpowers:requesting-code-review`, then `superpowers:receiving-code-review` to act on the findings.
- **Models:** follow the execution skill's model guidance. Implementer subagents for well-specified tasks run on sonnet. Keep opus for reviewers, for a fix that has already failed twice, and for tasks the plan marks as hard. In the eval, opus made up four-fifths of this workflow's cost, which put it at the top of the four arms.

Finish with `superpowers:verification-before-completion`, then `superpowers:finishing-a-development-branch`.

## Never mix in

These duplicate a stage above, and the eval found them weaker in this role:

- **mattpocock-skills:** `tdd`, `diagnosing-bugs`, `code-review`, `to-spec`, `implement-spec` and `implement`.
- **Agents:** `planner`, `architect`, `tdd-guide` and `code-reviewer`, unless a Superpowers skill dispatches the agent itself.
