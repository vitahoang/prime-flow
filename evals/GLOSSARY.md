# prime-flow eval

An end-to-end comparison of feature-building workflows: each one takes an underspecified request, works with a simulated user, and ships code that is scored against what that user actually wanted.

## Contenders

**Arm**:
One workflow being compared: prime-flow, Superpowers-only, mattpocock-only or pstack.
_Avoid_: Config, variant, contender

**Chain**:
The ordered skills an arm is built from. Every arm except prime-flow stays inside its own chain; prime-flow may use any installed skill.
_Avoid_: Pipeline, stack

**Run**:
One arm working one task from the first message to finished code.
_Avoid_: Trial, attempt

## Tasks

**Task**:
A feature request against a small existing repo, together with its brief, hidden requirements, traps and hidden tests.
_Avoid_: Eval case, scenario

**Request**:
The message the simulated user sends to open a run. It is deliberately underspecified.
_Avoid_: Prompt, ask

**Brief**:
The simulated user's private account of what they really want: goals, hidden requirements, preferences. No arm ever sees it.
_Avoid_: Persona, hidden spec

**Hidden requirement**:
Something the user needs that the request doesn't state, and that surfaces only if the arm asks about it or calls it right.
_Avoid_: Implicit requirement

**Trap**:
A decision where the obvious default is wrong for this user.
_Avoid_: Gotcha

**Code fact**:
Something about the task that the repo itself answers. An arm that asks the user for it adds to the user's burden for nothing.

## People

**Simulator**:
The agent that plays the user. It holds the brief, answers only what it's asked, and never volunteers hidden requirements.
_Avoid_: Fake user, user agent

## Scoring

**Intent match**:
How much of the brief the shipped code honours, measured by hidden tests. This is the primary score.
_Avoid_: Correctness, pass rate

**User burden**:
How much the run asked of the simulator: rounds of questions, total questions, and code facts it asked for.
_Avoid_: Friction, effort

## v4 tasks

**Change of mind**:
A point partway through a run where the simulator reverses a decision or adds a need, triggered by the arm's first report of written code.
_Avoid_: Scope change, pivot

**Planted bug**:
A defect deliberately left in the code a task hands over, scored as a trap even though the user never mentions it.
_Avoid_: Seeded bug

**Dry run**:
One plain-agent run per task before the eval, to check the task scores below 0.9 on intent match.

## v5 tasks

**Wrong fact**:
Something the simulated user states as true that the repo's code or data contradicts. An arm that checks before building catches it.

**Example-only need**:
A need the simulated user reveals only when shown a concrete worked example or sample output that covers the case.

**Fairness review**:
A fresh agent's check, before a task enters the eval, that every hidden need can be reached and that no hidden test rejects a reasonable implementation.
