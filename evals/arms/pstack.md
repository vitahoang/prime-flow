Your workflow is pstack. Read `~/.claude/plugins/cache/vita-tools/pstack/0.15.25/skills/poteto-mode/SKILL.md` in full and follow it; this request is a feature, so follow `playbooks/feature.md` and the skills and principles it names (bundled skills are at `../<name>/SKILL.md` from poteto-mode). Use only pstack skills; do not use skills from any other plugin.

Adaptations for Claude Code (pstack was written for Cursor):
- Subagents: use the Agent tool with `subagent_type: "pstack:poteto-agent"` (or `"poteto-agent"`). If neither type is available, use `"general-purpose"` and start its prompt with the full text of `~/.claude/plugins/cache/vita-tools/pstack/0.15.25/agents/poteto-agent.md`. The `model` parameter takes opus, sonnet, haiku or fable.
- Model table (replaces `~/.cursor/rules/pstack-models.mdc`; do not run setup-pstack): every role pstack assigns to a Grok model (feature, refactoring, bug-fix, perf-issue, hillclimb, how explorer, why investigators, reflect tooling, swarm workers) → sonnet; every role assigned to claude-opus (judgment and prose, hardest tasks, how explainer, why synthesizer, reflect judgment) → opus; panels (arena runners, arena cross-judge pool, architect runners, interrogate reviewers) → [opus, sonnet].
- `AskQuestion` → ask the user the way described in "Talking to the user" below.
- Skills from other plugins that pstack mentions (cursor-team-kit's deslop, control-cli, create-skill) are not installed: skip those steps.
- Do not open a PR or push; finish with local commits on a branch.
