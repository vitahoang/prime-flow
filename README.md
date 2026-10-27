# prime-flow

One workflow from idea to finished branch, self-contained in a single skill:

1. **Grill:** rounds of numbered, repo-grounded questions, each with a recommended answer, until the design is settled and confirmed. Terms land in a glossary, decisions in ADRs.
2. **Spec:** the agreed design is written to `docs/specs/…-design.md`, checked by a fresh builder subagent, and approved by you.
3. **Plan:** the spec becomes a task-by-task plan with files, tests and verification per task.
4. **Build:** each task runs test-first, with root-cause debugging on any failure and a fresh-subagent review of each diff, then a full verified test run before done.

Each stage's method came out ahead in a head-to-head eval of design-to-delivery workflows (see `evals/`); the winning methods are inlined, so no other plugin is required.

## Install

    /plugin marketplace add vitahoang/prime-flow
    /plugin install prime-flow@prime-flow

## Run

    /prime-flow:start <what you want to build>

The skill also starts on its own when you ask to build a feature, add functionality, or start a project.
