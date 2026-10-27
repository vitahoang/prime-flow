# The v5 difficulty gate uses the best arm, not a plain agent

In v4, a task counted as hard enough if a plain opus agent with no skills scored below 0.9. That check passed tasks that every skill workflow then aced (reorder-alerts: plain 0.75, all four arms 1.0), because the skills mainly add better questions, and that was exactly the gap the plain agent fell into. v5 runs the dry run with the arm that did best in v4 wave 1 (mattpocock) and requires 0.8 or less. Each task also gets a fairness review by a fresh agent, after v4's H2 test turned out to reject a correct implementation.
