# How a v4 task is built

v4 tasks follow `../tasks/BUILD.md`, with these changes. They exist because three of the four arms scored 95–100% on the v3 tasks.

- **Bigger, messier repos.** 1,500–3,000 lines of Python across 8+ modules, with 5–10 commits of plausible history, at least one misleading or stale comment or README line, and dead code. Existing tests pass, except where a task plants a flaky test on purpose.
- **One main difficulty per task:**

  | Task | Kind | Difficulty |
  |---|---|---|
  | `invoice-due-date` | Bug fix | The obvious fix is wrong. The root cause is in a shared helper with several callers, and a flaky test leads the wrong way. |
  | `refunds-branch` | Finish and ship | A teammate's half-done branch has three planted bugs (traps T1–T3). The user only asks for it to be finished. |
  | `reorder-alerts` | Feature | Hidden needs come out only after a follow-up question, and two of the user's goals conflict until the arm points it out. |
  | `support-digest` | Feature | The user changes their mind partway through the build (see below). |

- **Follow-up needs.** `surfaces_if` must say when a need takes a second question to surface, for example "asked how reorder points are decided, and then how usage is measured".
- **Change of mind.** The brief has a `## Change of mind` section. It sets the trigger (the first assistant message that reports product code written, tests passing, a task done or a commit, or that asks to approve finished work) and gives the exact words to say. `meta.json` has `"change_of_mind": {"marker": "<a phrase from those words>"}`, and the scorer checks that the marker reached the simulator log. Requirements that change get H ids. E tests check only behaviour the change leaves alone.
- **Branches.** `repo.bundle` may hold several branches. `main` is the default, and `harness/setup.py` creates a local branch for each one. `repo/` holds the files the hidden tests start from: for `refunds-branch`, that's the tip of the `refunds` branch.
- **Side checks.** These go in `meta.json` under `"side_checks"`, for example "the flaky test still exists and wasn't skipped" or "the arm told the user about each planted bug". Graders record them, but they don't count toward intent match.
- **Dry run.** Before the eval, one plain opus agent (`arms/plain.md`, no skills) runs each task once. If it scores 0.9 or more on intent match, the task is made harder.
