# Brief

I run the infrastructure team at a small SaaS company. Five of us share an on-call rotation and alertd pages whoever is on call. Last month a flapping disk check sent the same SMS forty times overnight, and a noisy cron job buried a real outage in Slack. Two people have told me they're close to quitting the rotation. I want alertd to stop flooding people without ever hiding something that really matters.

What I want, if you ask me:

- **H1 — Critical always gets through.** Critical alerts are never throttled: not by rate limits, not as duplicates, not at night. If the database is down at 3am I want every one of those pages. (Whether criticals count toward a channel's budget is your call, as long as they themselves always go out.)
- **H2 — Limits per channel.** Each channel has its own budget, counted over 30 minutes:
  - SMS: at most 3 in any 30 minutes. SMS wakes people up; it has to be rare.
  - Email: at most 10 in any 30 minutes.
  - Slack: up to 30 in any 30 minutes. Slack is where the noise is allowed to live.
  Alerts over the limit are just dropped.
- **H3 — Quiet hours.** From 22:00 to 07:00 only critical alerts go out. Info and warning alerts during quiet hours are dropped, not held for the morning; we see them on the dashboard anyway, and a pile of stale alerts at 7am would be worse. Quiet hours are the same for everyone, 22:00 to 07:00; whether it's configurable is your call.
- **H4 — Collapse duplicates.** If the same source sends the same message again within 10 minutes, only the first one goes out. Same source with a different message, or a different source with the same message, is a different alert. Whether the 10 minutes run from the first one sent or the latest repeat, and whether the same alert on another channel counts as a duplicate, is your call.
- **H5 — Sliding window.** "3 in 30 minutes" means any 30 minutes, not "per half hour on the clock". Three texts at 10:29 and three more at 10:31 is exactly the flood I'm trying to stop.

If you suggest these, here's what I'd say:

- **T1 — One overall limit?** No. A noisy Slack channel must never use up the budget so that an SMS or email can't go out. Each channel counts separately.
- **T2 — Quiet hours in server time / UTC?** No. Quiet hours are in the on-call person's own timezone, the one in their settings. Half the team is in Ho Chi Minh City and one person is in Los Angeles; 22:00 UTC is the middle of their working day.

Your call / don't care:

- Where the limit numbers live (constants, settings, constructor arguments).
- Whether rejected alerts are logged, and what the Router logs.
- Exact behaviour at the boundary instant (exactly 30:00 or exactly 07:00:00).
- Code structure, naming and internal storage.
