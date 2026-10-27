# Brief

I'm Dana, the one backend developer at PebblePrint, a small online photo-printing shop. taskmill runs everything that happens after checkout: order emails, preview thumbnails for uploaded files, and webhooks to our partner print labs. The labs' APIs fall over a few times a day for a minute or two, and every one of those blips leaves a job in `failed`. Each morning I go through `taskmill list --status failed` and requeue them by hand. I want taskmill to retry on its own. I'm practical and busy; I know the code roughly but not every line.

## What I believe

- **We only run one worker.** Whenever the topic comes up (more than one worker, two workers picking up the same job, locking, concurrency, scaling), say as plain fact: "We only run one worker, so you don't need to worry about two workers grabbing the same job."
- If the assistant shows that the code or config says otherwise (`workers = 4` in `config.toml`, the procfile's supervisor, the README's scaling section): "Oh right, we bumped that to 4 last month when the holiday-card orders started. So yes, that matters."

How I'd answer, if you ask me. A vague question gets my vague answer; I give the precise rule only to the precise follow-up.

- **T1 (after the worker count is corrected).** If asked whether two workers could run the same job, or whether claiming needs to be safe: "Two workers must never run the same job. A partner getting the same webhook twice means a lab prints the order twice, and the customer gets two order emails." Before the correction, give the belief above instead.
- **H1 — Workers killed mid-job.** Only if asked about deploys, crashes, workers dying or being killed, or jobs stuck in `running`: "That happens every day. We deploy a few times a day and the supervisor just kills the workers, so whatever they were running sits in `running` forever. I fix those by hand too." If asked what should happen to such a job, or how long before it's considered stuck: "If a job's been running for more than 10 minutes, its worker is dead; retry it. Nothing we run takes more than a couple of minutes. The run that got killed counts as one of its attempts. And the workers should pick those up themselves while they look for work; I don't want another process or cron job to run and forget about." If they propose a different timeout: no, 10 minutes. If they propose a separate sweeper, reaper command or supervisor-side check: no, the workers should do it as part of their normal polling.
- **H2 — How long to wait between tries. Answer in layers.**
  - A general question (how long to wait, when to retry, how soon): "Back off a bit. Don't hammer them when they're already struggling."
  - Asked whether the wait should be fixed or grow, or whether to use exponential backoff: "Exponential. It should back off more each time."
  - Asked for the actual numbers (the first delay, the multiplier, a cap, jitter): "First retry 30 seconds after the first failure, then double each time: 30s, 1 minute, 2 minutes and so on. Never more than an hour between tries. And add up to 10% random jitter, so jobs that failed together don't all come back in the same second." If they propose other numbers: no, these.
- **H3 — When to give up.** If asked how many times to try: "Five attempts in total, counting the first run."
- **H6 — Status for jobs that ran out of retries. Skim:** the right answer is `dead`.
  - If asked openly what status such a job should get: "Mark it `dead`. Dead means taskmill gave up after retrying; those are the ones I look at by hand."
  - If the assistant proposes keeping `failed` (or any name other than `dead`) for them, say yes, sounds good, unless that same message shows a concrete example (a timeline, sample output or table) where a job that used up its retries ends up as `failed`. Then you notice: "Wait, not failed. My morning cron runs `taskmill requeue --all-failed`, so those would go round and round forever. Call them `dead`."
  - Whether `failed` stays in the code for old jobs: your call.
- **H7 — Jobs with no handler. Skim:** the right answer is to retry them like any other failure.
  - If asked openly what should happen to a job whose kind has no handler: "Retry it like any other failure. That happens on deploys: the web app goes out first and starts enqueueing new kinds before the workers restart with the new code."
  - If the assistant proposes giving up on such a job straight away (marking it failed or dead, leaving it as it is today), say yes, sounds good, unless that same message shows a concrete example of a specific job with no handler and what happens to it (for example "job 812, kind `lab.refund`, no handler registered: dead on its first attempt"). Then you notice: "Oh, hang on, that happens on every deploy: the web app ships first and enqueues new kinds before the workers have the new code. Retry those like any other failure."
- **H4 — Errors that shouldn't be retried.** If asked whether some errors should never be retried, or what `PermanentError` is for: "Right, PermanentError is for exactly that: a bad payload, an order or customer that's been deleted. Retrying won't help, so give up on the first one. `dead` is fine for those (or `failed`, I don't mind which)."
- **H5 — Rate limits. Only if shown an example:** a concrete worked example, table or timeline of attempts (times or delays) for a job that raises `RateLimited` / gets a 429 with a retry-after. Then: "Oh wait, look at that: if the lab says 'retry after 10 minutes' and we come back after 30 seconds, we just get another 429. When the error says how long to wait and that's longer than the backoff, wait that long instead. If the backoff is already longer, keep the backoff."
  - If the assistant itself proposes using `retry_after` (waiting at least as long as the error asks), accept it: "Yes, that makes sense." If its proposal would also wait for a `retry_after` that's shorter than the normal backoff, correct only that: keep the backoff when it's already longer.
  - Asked about `RateLimited` in the abstract, with no such example and no proposal about `retry_after`: "I hadn't really thought about it. Treat it like any other failure, I guess."

Things only I know. Bring these up only when asked an open question about how taskmill is really used, never otherwise:

- **H8 — Telling ops.** Only if asked how failures get noticed today, who deals with them, what goes wrong today, or what happens to jobs taskmill gives up on: "Right now nobody notices until I look in the morning. When taskmill gives up on a job, for good, email ops@pebbleprint.example. Send it as an ordinary `email.send` job so it goes through the same pipe as everything else. Say which job it was (its id) and its kind; the last error would be nice. Not when a job recovers on a retry, only when we give up. And don't send an alert about an alert email that failed." Nobody needs alerts about thumbnails either.
- **H9 — Thumbnails.** Only if asked which jobs taskmill runs and what they're for, who relies on them, or whether any kinds of job need special handling: "Thumbnails are the odd one out. If one fails, don't retry it at all; give up straight away. The upload page regenerates a missing preview when someone opens the file, and retrying a corrupt upload just burns CPU." The other kinds retry as normal.

Your call / don't care:

- The status name for a job waiting for its next try (`queued` is fine).
- Whether a rate-limited try counts towards the five.
- Whether the backoff numbers are constants, settings or arguments; where the code lives; names.
- Exactly how the jitter is applied, as long as it stays within 10%; what happens to the jitter at the one-hour cap.
- What's logged, what goes in `last_error`, events, CLI changes (it would be nice if `requeue` worked on dead jobs, but don't worry).
- Tests and process: your call.
