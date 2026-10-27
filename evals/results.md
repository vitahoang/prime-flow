# Results: prime-flow 0.2.0 vs Superpowers vs mattpocock vs pstack

Run on 2026-10-16 to 18: 3 tasks × 4 arms × 3 runs = 36 end-to-end runs. Each run went from an underspecified request to committed code, working with a simulated user that holds a hidden brief (ADR 0001). The top-level agent was Opus 5.5 in every run, and each arm chose its own helper models (ADR 0002). Every run was checked: none read a brief, and none outside prime-flow borrowed another arm's skills.

## Headline

| Arm | Intent match | Explicit reqs | Rounds | Questions | Blind UX rank (1 best of 12) | Blind process (1–10) | $ / run | Active min |
|---|---|---|---|---|---|---|---|---|
| **prime-flow** | **1.00** (9/9 perfect) | 1.00 | 4.3 | 14.7 | 7.8 | **7.9** | 4.96 | 20.7 |
| Superpowers | 0.95 (8/9) | 0.89 | 6.2 | 8.6 | **3.3** | 7.1 | 3.89 | 20.1 |
| mattpocock | 0.98 (8/9) | 1.00 | 4.0 | 14.9 | 9.3 | 7.1 | **3.41** | 17.0 |
| pstack | 0.73 (0/9) | 0.94 | **1.2** | 5.4 | 5.6 | 6.3 | 4.00 | **15.7** |

Intent match is the share of hidden requirements and traps the shipped code honours, measured by hidden tests that run through the entry point named in the request. The other columns are averages per run. "Rounds" counts the messages that went to the user. The blind rankings come from a grader who saw anonymised conversations and worklogs. Cost covers every agent in the run except the simulated user.

## By task (intent match, average and range over 3 runs)

| Task | prime-flow | Superpowers | mattpocock | pstack |
|---|---|---|---|---|
| ledger-export | 1.00 | 1.00 | 1.00 | 0.80 (missed Excel BOM ×3) |
| alert-throttle | 1.00 | 0.86 [0.57–1] (one run built no rate limit) | 1.00 | 0.71 [0.43–0.86] (never collapsed duplicates ×3) |
| recurring-events | 1.00 | 1.00 | 0.93 [0.8–1] (no cancellations ×1) | 0.67 [0.6–0.8] (no cancellations ×3, no series end ×2) |

## What the numbers say

- **Building what the user wanted:** prime-flow is the only arm that got every hidden requirement in every run. The gap over mattpocock and Superpowers is one miss each in nine runs, so it is consistent but small. pstack is clearly behind: it usually asks one round of questions and decides the rest itself, so it never learns requirements the user would only state if asked.
- **User burden:** prime-flow and mattpocock ask the most, about 15 questions per run, in numbered rounds with a recommended answer for each. Superpowers asks about 9, one at a time over more messages. The blind grader found that easiest to answer and ranked it first for user experience. pstack asks the fewest and is the clearest, but that is why it misses requirements. Questions about facts the code already answers were rare; the few came from prime-flow and mattpocock on recurring-events.
- **Process:** the blind grader rated prime-flow's process highest. Its runs had a spec, a builder check, a plan, test-driven work, a review per task and a whole-branch review. Its standout ranks were on recurring-events (2.0 of 12) and alert-throttle.
- **Cost:** prime-flow is the most expensive, about $5 per run against $3.4–4.0. Almost all of the gap is on recurring-events, about $9 per run, where it ran the full spec, plan and per-task reviews. It does scale down: on ledger-export it called the work a small change and cost $1.6 per run. Totals for all 36 runs: prime-flow $44.7, pstack $36.0, Superpowers $35.0, mattpocock $30.7.

## Takeaways for prime-flow 0.3

1. **Keep the design-step split.** It ties for the best intent match, and its runs are rated best on process.
2. **Ask fewer, better questions.** About 15 questions per run is heavy. Cap a round at about 5. Ask open "how will you use this?" questions before detailed ones; those surfaced Excel and quiet-hours needs at the lowest cost. Look up code facts before asking (the event timezone and the `ZoneInfo` check were asked about).
3. **Use cheaper models for build helpers.** Opus did $36 of prime-flow's $45. Superpowers' own guidance says to send mechanical implementation tasks to cheaper models, and prime-flow runs should follow it.
4. **No pstack borrowing seen yet.** Runs could have borrowed pstack skills but didn't. pstack's two-design comparison caught real bugs in its own runs (e.g. the fold bug in recurring-events). That makes it worth trying as a stage-4 option for designs that are genuinely contested.

## Caveats

- Three runs per arm per task: differences of one run (prime-flow vs mattpocock and Superpowers) are suggestive, not proof.
- The simulated user is cooperative and consistent. A real user who changes their mind could favour different flows.
- Some simulator logs miss one or two exchanges, where the safety check blocked the simulator's log writes. Rounds and question counts may be slightly low for those runs.
- Nine runs were cut off by a usage limit and re-run from scratch. Wall-clock time spanning that pause is excluded; "active min" sums gaps under 10 minutes in the run's transcripts.
- The hidden tests for recurring-events accept common option names (`exceptions`, `until`, `count`…). A run using an unusual name would need a manual mapping; none did.
- Arms chose their own helper models, so cost and quality gaps mix method with model choice (ADR 0002).

## Re-run: prime-flow 0.3.0 (2026-10-19)

The prime-flow arm was re-run with 0.3.0, 9 runs on the same three tasks. 0.3.0's changes: open with how the result is used, at most five questions a round, look up code facts before asking, and sonnet for build helpers. Questions were counted with the same rules as above, but by a different, non-blind counter.

| | 0.2.0 | 0.3.0 |
|---|---|---|
| Intent match | 1.00 (9/9 perfect) | 0.95 (7/9 perfect) |
| Questions per run | 14.7 | 13.1 |
| Code-fact questions per run | 0.44 | 0 |
| Largest message (questions) | not limited | 5 |
| $ per run | 4.96 | 4.71 |
| Sonnet share of cost | 19% | 15% |

- **The two misses:**
  - recurring-events run 2: it judged the job a small change, asked three short rounds and never asked about cancelling single classes.
  - alert-throttle run 3: the simulator broke its rules and volunteered quiet hours in an approval reply. The run correctly ignored a requirement the user hadn't stated in their own words, so quiet hours weren't built. That miss is the harness's fault, not the workflow's.
- **The question rules worked:** every message stayed within five questions, nothing was asked that the code answers, and 8 of 9 runs opened with how the result is used. The total dropped only about 10%.
- **The model rule didn't move cost:** sonnet's share fell slightly. Most of the cost is the top-level agent, which runs on the session's own model (Opus here), plus opus reviewers. Cheaper helpers can't change that.
- **Verdict:** 0.3.0 is no clear improvement. It is a little lighter on the user and a little cheaper, and within noise on intent match. Keep the question rules. For 0.4, end the small-change path with one "what else should it handle (cancellations, end dates, failures)?" question, which would have caught the recurring-events miss. Cut cost by trimming review rounds on small plans, not by changing helper models.
- **Harness changes after this run:** the eval moved from `prime-flow/evals/` to `evals/prime-flow/` (prime-flow 0.3.1). Inside the plugin folder it was copied into the installed plugin, so a run could have read the briefs. A check of every run's tool calls found none that touched it.
