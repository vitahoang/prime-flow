# Arms choose their own helper models, and cost is measured in dollars

Each workflow already has its own view on which model fits which job: Superpowers sends routine build tasks to cheap models, and pstack assigns a model per role. Forcing one model everywhere would test each workflow with part of its design switched off. So every run's top-level agent uses the same model, as a real session would, and each arm picks models freely for the helpers it starts. Token counts are no longer comparable across models, so cost is priced in dollars across every agent in a run, helpers included.

## Consequences

- Arms differ in model choice as well as method, so a cost or quality gap may come from either.
- pstack's default Grok roles map to sonnet, and its `[opus, grok]` panels become `[opus, sonnet]`, because Claude Code can't reach Grok.
