# A simulated user with a hidden brief stands in for the real user

Runs go end to end, from an underspecified request to working code, and stop at every point where a workflow would talk to its user. A real person can't sit through 36 runs of 20–40 minutes. A fully specified request would remove the very thing the design step is for. So each task has a private brief, held by a simulator that answers only what it's asked and never volunteers anything. The primary score, intent match, is how much of that brief the shipped code honours.

## Consequences

- The results measure a workflow's ability to draw out requirements from a cooperative but unforthcoming user. They don't measure how it handles a user who changes their mind, contradicts themselves or doesn't know what they want.
- A run that reads the brief would make its result meaningless, so every run's log is checked for leaks.
