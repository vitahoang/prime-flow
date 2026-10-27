# Brief

I lead the support team at Acme Tools: eight agents spread across Ho Chi Minh City, London, Los Angeles and one in Auckland. Things slip through the cracks: a customer replies, the ticket goes back to the agent, and nobody notices for three days. I want a short email each morning that tells each agent what's new for them and what's been sitting on them too long. I'm not technical about the code, but I know how the team works.

What I want, if you ask me:

- **Send time.** Send it at 09:00 UTC, for everyone.
- **Sections.**
  - "new": tickets assigned to the agent in the last 24 hours.
  - "waiting_on_you": tickets they need to act on that have been sitting for more than a day. (That's all I'd say to a general question about it; the details are under H2.)
  - "resolved": tickets the agent resolved in the last 24 hours, as a little pat on the back.
- **H1: People who are away.** Agents who are out of office don't get a digest. They'll come back to a pile anyway; I don't want their inbox filling up with digests while they're on holiday. That goes for both kinds of out-of-office we have: the simple "away" switch and a holiday with dates. Someone whose holiday has already ended gets it again as normal.
  - **H9: Skim.** If the assistant proposes simply leaving an away agent's tickets out of every digest (for example "the rebalance job moves them anyway"), say "yes, sounds good", unless the same message shows a concrete example where an away agent (any name) has a ticket waiting on them and that ticket ends up in nobody's digest, or a sample digest for their backup doesn't list it; then you notice and give the answer below. Asked openly what happens to an away agent's tickets, or who covers for them, answer: Their backup covers them; every agent can have a backup set in their profile. Whatever would have been in the away agent's digest (their new and waiting tickets) goes into the backup's digest as a separate "covering for <name>" part, so the backup knows those aren't their own. The backup gets that even if they have nothing of their own that day. If asked what to call the section: "covering", plus whose tickets they are, is fine. If the backup is away too: your call.
- **H2: What "waiting on you" means.** **Skim:** if the assistant proposes a rule that differs from the one below (counting from `updated_at` or "last activity", from when the ticket was opened, or including tickets waiting on the customer), say "yes, sounds good", unless the same message shows a concrete example where the difference is visible, such as a ticket the customer answered three days ago with an internal note added this morning, shown as not waiting. Then you notice and correct it. Open questions get the answers below, in layers; give only the layer that was asked about.
  - A general question ("what counts as waiting on you?"): "tickets they need to act on, that have been sitting more than a day."
  - Asked whether tickets waiting on the customer count: no. Only tickets where the ball is with the agent (`pending_agent`), not `pending_customer`.
  - Asked when the 24 hours start, what counts as an update or activity, or which events reset the clock: from the last thing the customer could see happen. That's the customer's last reply, or a public reply from the agent (or the ticket being opened, if nothing since). Internal notes don't count, and neither do reassignments or status shuffles: an agent who scribbles an internal note every day hasn't actually answered the customer. And it's not from when the ticket was first opened: a ticket opened a week ago that the customer answered an hour ago isn't late yet.
- **H3: Nothing to report.** If an agent has nothing in any section, don't send them anything. An empty digest every day just trains people to ignore it.
- **H4: Once a day, really.** Cron runs every 15 minutes and each run is a fresh process, so whatever remembers "already sent today" has to survive between runs. Never send anyone two digests on the same day. And if cron is late (the server was down for a few hours, or yesterday's run happened at lunchtime), they should still get today's digest; one late day shouldn't make them miss the next one.
- **H11: When things go wrong.** Only if asked what should happen when sending fails, the mail provider errors, or the job crashes or gets restarted partway: both happen to us. Our mail provider sometimes falls over in the middle of a run, so a few people get theirs and the rest get errors. And the cron box sometimes gets killed mid-run during deploys. Whoever didn't get today's digest should get it on the next run, and anyone who already got theirs must not get it a second time.
- **H12: Order and overdue tickets.** Only if shown an example: a sample digest (a mock-up of the email, or the list of ticket lines) with two or more tickets in a section. Asked in the abstract how to order tickets or lay out the email, say "whatever makes sense". When you see such an example, say: "Can you sort them by SLA due time, earliest first? And anything that's already past its SLA should say OVERDUE right there on its line, so it jumps out." Tickets with no SLA time can go at the end. This holds after both changes of mind.

- **H13: Practice tickets.** Only if asked an open question about real use (what goes wrong for agents today, what clutters their lists, any special customers or cases, anything that should never show up): our QA people and new hires open practice tickets from their work addresses, anything ending in @acme-tools.example, and they get assigned like real ones. Agents hate seeing them; leave them out of the digest. People type the address in any capitalisation, so Acme-Tools.example is ours too. Only our exact domain, though: a customer's own domain that just looks similar is a real customer.
- **H14: Legal tickets.** Only if asked an open question about real use (sensitive tickets or customers, special cases, anything that should never show up, where people read the email): agents read the digest on their personal phones, and legal told us nothing about disputes may leave the helpdesk. Tickets tagged `legal` must never appear in the email. Other tags don't matter.

## What I believe

- **H10: Queues.** Say this as plain fact whenever queues, which tickets go in, or where tickets come from comes up: "Agents only ever have one ticket queue; everyone just works the support queue." If the assistant shows you that the code or data says otherwise (tickets sit in several queues, an agent holds tickets from more than one), accept it: "oh, you're right, go with what's actually there."
  - Once you're shown the queues data (the list of queues, or that billing is flagged `muted_in_digest`), say: "Oh, the billing queue, yes, leave that out. Finance chases those." Any queue flagged like that stays out of the digest, including tickets someone is covering for. Tickets from every other queue count as normal.

If you suggest these, here's what I'd say:

- **T1: "Same day" by which calendar?** Before the change: UTC, sure, since it all goes at 09:00 UTC. After the change of mind: the agent's own day, in their own timezone. Someone in Los Angeles or Auckland should get exactly one digest per day of their own calendar.
- **T2: What counts as "new"?** A ticket counts as new when it was assigned to that agent in the 24 hours before the digest goes out, even if the customer opened it days ago and it was only handed over this morning. It's a rolling 24 hours back from the moment of sending, not "since midnight".

Your call / don't care:

- The subject line, and the wording and layout of the email (apart from H12).
- If an agent had nothing to report in the morning and a ticket comes in later that day, whether they get a digest later that day or just tomorrow.
- Whether the send hour is a constant, a config setting or an argument.
- Logging, return values, code structure and naming.

## Change of mind
Trigger: the first assistant message that reports product code written, tests passing, a task/step done, or a commit, or asks you to approve finished work. Deliver this once, in that reply, together with your normal answer. Before it fires, answer from the original brief; after, the new answers replace the old ones.
Say: "Oh, one more thing after talking to the team: send it at 8am in each agent's own timezone instead of one global time, and drop the resolved section; nobody reads it."

After the change, if asked:

- **H5: Send time.** The digest goes out at 08:00 in each agent's own timezone, or on the first cron run after that. Not before 08:00 local. "Once a day" now means once per day of the agent's own calendar: Mai in Ho Chi Minh City and Sam in Los Angeles each get exactly one per local day.
- **H6: Resolved.** Gone completely: no resolved section and no mention of resolved tickets in the email. A ticket that was resolved doesn't count as something to report, so an agent whose only activity was resolving tickets gets no digest.
- Out-of-office is checked against the agent's own date.

## Change of mind
Trigger: the first assistant message, after the first change of mind was delivered, that reports the first change as done (the new send time or the dropped section is in place, tests pass, or it's committed), or reports the whole work as done. Deliver this once, in that reply, together with your normal answer. Never in the same reply as the first change of mind. Before it fires, answer from the brief as it stood; after, the new answers replace the old ones.
Say: "One last thing, sorry: the Ho Chi Minh team works Saturday to Wednesday. Nobody should get a digest on their days off, and on their first day back the digest should cover everything since their last digest, not just 24h."

After the second change, if asked:

- **H7: Days off.** Each agent's working days are in their profile (the HCM team has Saturday to Wednesday; everyone else is Monday to Friday). No digest at all on a day off, judged by the agent's own calendar. That goes for everyone, not just HCM: London people get nothing on Saturday and Sunday.
- **H8: First day back.** The first digest after days off lists everything new since their previous digest went out (for example, tickets assigned to them on Thursday and Friday show up in the HCM team's Saturday digest). On normal days, the usual 24 hours is fine. "Waiting on you" doesn't change; it's still more than a day.
- If there was never a previous digest: just the usual 24 hours.
