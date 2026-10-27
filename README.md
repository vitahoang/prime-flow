# prime-flow

One workflow from idea to finished branch, using each plugin where it did best in a head-to-head eval:

1. **Grill:** mattpocock-skills `grilling` + `domain-modeling` (what `/mattpocock-skills:grill-with-docs` runs).
2. **Spec:** the agreed design is written to `docs/superpowers/specs/…-design.md`, checked by a fresh builder subagent, and approved by you.
3. **Plan:** `superpowers:writing-plans`.
4. **Build:** `superpowers:subagent-driven-development` with `test-driven-development`, `systematic-debugging` and `requesting-code-review`, then `finishing-a-development-branch`.

Needs both the `superpowers` and `mattpocock-skills` plugins installed.

## Run

    /prime-flow:start <what you want to build>

The skill also starts on its own when you ask to build a feature, in place of `superpowers:brainstorming`. Invoke `/superpowers:brainstorming` yourself to use that instead.
