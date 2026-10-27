# Brief

I run a small yoga studio with two locations, one in Paris and one in New York, and I use calkit behind our booking page. Each class is an Event in its location's own timezone. The booking page shows "upcoming classes": for each class series it asks for the next few sessions after a given moment, and I want to stop hand-entering every single session.

What I mean, if you ask:

- **H1 — "after" means strictly after.** The page asks "what comes after this session?" by passing the session's own start time. If the session that starts exactly at `after` comes back, the page shows the same class twice. So an occurrence at exactly `after` must not be returned. (Comparing across timezones by the actual moment is obviously fine.)
- **H2 — I cancel individual sessions.** Holidays, teacher off sick: I cancel one session by its date ("no class on 24 December") and it should simply not show up; the list should still give me `n` sessions, taking the next ones. The cancelled dates belong on the rule — something like an `exceptions` option taking a list of dates. The date is the date at the studio (the rule's own timezone), not UTC.
- **H3 — series end.** Courses end. Sometimes I know the last day ("until 22 June", and that day's class still happens — the until date is inclusive), sometimes I know the number of sessions ("a 10-week course" = 10 sessions in total from the start, not 10 more from `after`). I'd pass `until=` (a date) or `count=` (an int) on the rule. If the series ends, just return fewer than `n`.
- **T1 — monthly on the 31st.** We hold a month-end community class on the last day of the month, so I set it up starting on the 31st. In months without a 31st it must fall on that month's last day (30th, or 28th/29th in February) — not be skipped. And it goes back to the 31st when the month has one.
- **T2 — daylight saving.** A 7:00 class is at 7:00 local all year round. When the clocks change, the class does not move to 6:00 or 8:00. Keep the local wall-clock time in the rule's own timezone, not a fixed UTC offset.

Things I don't care about ("your call"):

- Whether the returned datetimes are in the rule's timezone or UTC, as long as they're the right moments.
- Whether a cancelled session still counts toward `count`.
- Whether `start` itself counts when it isn't on one of the listed weekdays.
- What happens for a start time that doesn't exist on a DST-change day (e.g. 02:30) — we don't schedule classes then.
- Validation messages, extra helpers, an interval ("every 2 weeks"), RRULE strings — not needed.
- Internal structure and naming of anything beyond `Rule`, `next_occurrences` and the option names above.

Things the code already answers (I'd be puzzled to be asked): which timezone a class is in (each Event carries its own IANA zone), and which day weeks start on (there's already a Monday `WEEK_START` setting for the week view — it doesn't matter for this).
