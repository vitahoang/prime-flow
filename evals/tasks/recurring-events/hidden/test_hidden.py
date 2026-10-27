"""Acceptance tests for calkit.recurrence.Rule / next_occurrences."""

import inspect
import json
import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

PARIS = ZoneInfo("Europe/Paris")
BERLIN = ZoneInfo("Europe/Berlin")
NEW_YORK = ZoneInfo("America/New_York")
TOKYO = ZoneInfo("Asia/Tokyo")

# Option names an implementation may reasonably pick for the hidden options.
# A grader can map unusual names per run with CALKIT_OPTION_NAMES='{"cancelled dates": "...", "an until date": "...", "a count": "..."}'.
EXCEPTION_NAMES = ("exceptions", "exdates", "exdate", "cancelled", "canceled",
                   "cancelled_dates", "canceled_dates", "cancellations",
                   "skip", "skip_dates", "excluded", "exclude", "excluded_dates")
UNTIL_NAMES = ("until", "end", "end_date", "until_date", "ends_on", "last_date")
COUNT_NAMES = ("count", "occurrences", "max_count", "times", "limit")


def _api():
    from calkit.recurrence import Rule, next_occurrences
    return Rule, next_occurrences


def rule(freq, start, weekdays=None, exceptions=None, until=None, count=None):
    Rule, _ = _api()
    params = inspect.signature(Rule).parameters
    kwargs = {}
    if weekdays is not None:
        kwargs["weekdays"] = weekdays
    for value, names, what in ((exceptions, EXCEPTION_NAMES, "cancelled dates"),
                               (until, UNTIL_NAMES, "an until date"),
                               (count, COUNT_NAMES, "a count")):
        if value is None:
            continue
        mapped = json.loads(os.environ.get("CALKIT_OPTION_NAMES", "{}")).get(what)
        name = mapped if mapped in params else next((nm for nm in names if nm in params), None)
        assert name is not None, f"Rule takes no option for {what}: {list(params)}"
        kwargs[name] = value
    return Rule(freq, start, **kwargs)


def nxt(r, after, n):
    _, next_occurrences = _api()
    return next_occurrences(r, after, n)


def at(tz, *args):
    return datetime(*args, tzinfo=tz)


def walls(occs, tz):
    return [o.astimezone(tz).replace(tzinfo=None) for o in occs]


# ---- explicit -------------------------------------------------------------

def test_E1_daily():
    r = rule("daily", at(PARIS, 2026, 6, 1, 9, 0))
    got = nxt(r, at(PARIS, 2026, 6, 2, 12, 0), 3)
    assert got == [at(PARIS, 2026, 6, d, 9, 0) for d in (3, 4, 5)]


def test_E2_weekly_on_given_weekdays():
    r = rule("weekly", at(PARIS, 2026, 6, 1, 18, 30), weekdays={0, 2, 4})  # Mon/Wed/Fri
    got = nxt(r, at(PARIS, 2026, 6, 1, 20, 0), 5)
    assert got == [at(PARIS, 2026, 6, d, 18, 30) for d in (3, 5, 8, 10, 12)]


def test_E3_monthly_same_day():
    r = rule("monthly", at(TOKYO, 2026, 1, 15, 10, 0))
    got = nxt(r, at(TOKYO, 2026, 2, 1, 0, 0), 3)
    assert got == [at(TOKYO, 2026, m, 15, 10, 0) for m in (2, 3, 4)]


def test_E4_returns_n_sorted_aware_and_accepts_other_zone_for_after():
    r = rule("daily", at(PARIS, 2026, 6, 1, 9, 0))
    got = nxt(r, datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc), 4)
    assert len(got) == 4
    assert all(o.tzinfo is not None for o in got)
    assert got == sorted(got)
    assert got[0] == at(PARIS, 2026, 6, 11, 9, 0)


# ---- H1: `after` is exclusive -----------------------------------------------

def test_H1_occurrence_equal_to_after_is_not_returned():
    r = rule("daily", at(PARIS, 2026, 6, 1, 9, 0))
    got = nxt(r, at(PARIS, 2026, 6, 3, 9, 0), 2)
    assert got == [at(PARIS, 2026, 6, 4, 9, 0), at(PARIS, 2026, 6, 5, 9, 0)]


def test_H1_after_start_skips_first_occurrence():
    start = at(TOKYO, 2026, 5, 15, 19, 0)
    r = rule("monthly", start)
    got = nxt(r, start, 1)
    assert got == [at(TOKYO, 2026, 6, 15, 19, 0)]


def test_H1_same_instant_in_other_zone_is_still_excluded():
    r = rule("weekly", at(PARIS, 2026, 6, 1, 18, 30), weekdays={0})
    after = at(PARIS, 2026, 6, 8, 18, 30).astimezone(timezone.utc)
    assert nxt(r, after, 1) == [at(PARIS, 2026, 6, 15, 18, 30)]


# ---- H2: cancelled dates are skipped ----------------------------------------

def test_H2_cancelled_daily_occurrence_skipped_and_backfilled():
    r = rule("daily", at(PARIS, 2026, 6, 1, 9, 0), exceptions=[date(2026, 6, 3)])
    got = nxt(r, at(PARIS, 2026, 6, 1, 12, 0), 3)
    assert got == [at(PARIS, 2026, 6, d, 9, 0) for d in (2, 4, 5)]


def test_H2_cancelled_weekly_class():
    r = rule("weekly", at(PARIS, 2026, 12, 7, 7, 0), weekdays={0, 3},  # Mon/Thu
             exceptions=[date(2026, 12, 24), date(2026, 12, 28)])
    got = nxt(r, at(PARIS, 2026, 12, 20, 0, 0), 3)
    assert got == [at(PARIS, 2026, 12, 21, 7, 0), at(PARIS, 2026, 12, 31, 7, 0),
                   at(PARIS, 2027, 1, 4, 7, 0)]


def test_H2_cancelled_date_is_local_to_rule_zone():
    # 21:00 in New York is already the next day in UTC; the cancellation is by NY date.
    r = rule("daily", at(NEW_YORK, 2026, 6, 1, 21, 0), exceptions=[date(2026, 6, 2)])
    got = nxt(r, at(NEW_YORK, 2026, 6, 1, 22, 0), 2)
    assert got == [at(NEW_YORK, 2026, 6, 3, 21, 0), at(NEW_YORK, 2026, 6, 4, 21, 0)]


# ---- H3: series can end (until date inclusive, or count) --------------------

def test_H3_until_date_is_inclusive():
    r = rule("daily", at(PARIS, 2026, 6, 1, 18, 0), until=date(2026, 6, 5))
    got = nxt(r, at(PARIS, 2026, 6, 2, 19, 0), 10)
    assert got == [at(PARIS, 2026, 6, d, 18, 0) for d in (3, 4, 5)]


def test_H3_until_weekly_ends_series():
    r = rule("weekly", at(PARIS, 2026, 6, 1, 7, 0), weekdays={0}, until=date(2026, 6, 22))
    assert nxt(r, at(PARIS, 2026, 6, 22, 7, 0), 5) == []
    assert nxt(r, at(PARIS, 2026, 6, 10, 0, 0), 5) == [
        at(PARIS, 2026, 6, 15, 7, 0), at(PARIS, 2026, 6, 22, 7, 0)]


def test_H3_count_limits_whole_series():
    r = rule("weekly", at(PARIS, 2026, 9, 7, 19, 0), weekdays={0}, count=10)  # 10-week course
    got = nxt(r, at(PARIS, 2026, 9, 1, 0, 0), 50)
    assert len(got) == 10
    assert got[-1] == at(PARIS, 2026, 11, 9, 19, 0)


def test_H3_count_counts_from_series_start_not_from_after():
    r = rule("daily", at(TOKYO, 2026, 6, 1, 9, 0), count=5)
    assert nxt(r, at(TOKYO, 2026, 6, 3, 12, 0), 10) == [
        at(TOKYO, 2026, 6, 4, 9, 0), at(TOKYO, 2026, 6, 5, 9, 0)]


# ---- T1: monthly on a day the month lacks clamps to month end ---------------

def test_T1_monthly_31st_clamps_to_last_day():
    r = rule("monthly", at(TOKYO, 2026, 1, 31, 18, 0))
    got = nxt(r, at(TOKYO, 2026, 1, 31, 20, 0), 4)
    assert walls(got, TOKYO) == [datetime(2026, 2, 28, 18, 0), datetime(2026, 3, 31, 18, 0),
                                 datetime(2026, 4, 30, 18, 0), datetime(2026, 5, 31, 18, 0)]


def test_T1_monthly_31st_leap_february_and_no_drift():
    r = rule("monthly", at(TOKYO, 2027, 12, 31, 9, 0))
    got = nxt(r, at(TOKYO, 2028, 1, 1, 0, 0), 3)
    assert walls(got, TOKYO) == [datetime(2028, 1, 31, 9, 0), datetime(2028, 2, 29, 9, 0),
                                 datetime(2028, 3, 31, 9, 0)]


def test_T1_monthly_30th_clamps_in_february():
    r = rule("monthly", at(TOKYO, 2026, 1, 30, 9, 0))
    got = nxt(r, at(TOKYO, 2026, 2, 1, 0, 0), 2)
    assert walls(got, TOKYO) == [datetime(2026, 2, 28, 9, 0), datetime(2026, 3, 30, 9, 0)]


# ---- T2: same local wall-clock time across DST ------------------------------

def test_T2_daily_keeps_local_time_over_spring_forward():
    r = rule("daily", at(NEW_YORK, 2026, 3, 1, 7, 0))  # US DST starts 2026-03-08
    got = nxt(r, at(NEW_YORK, 2026, 3, 5, 12, 0), 5)
    assert walls(got, NEW_YORK) == [datetime(2026, 3, d, 7, 0) for d in (6, 7, 8, 9, 10)]


def test_T2_weekly_keeps_local_time_over_fall_back():
    r = rule("weekly", at(BERLIN, 2026, 10, 5, 18, 0), weekdays={0})  # EU DST ends 2026-10-25
    got = nxt(r, at(BERLIN, 2026, 10, 6, 0, 0), 4)
    assert got == [at(BERLIN, 2026, 10, 12, 18, 0), at(BERLIN, 2026, 10, 19, 18, 0),
                   at(BERLIN, 2026, 10, 26, 18, 0), at(BERLIN, 2026, 11, 2, 18, 0)]
    assert [o.astimezone(BERLIN).hour for o in got] == [18, 18, 18, 18]


def test_T2_monthly_keeps_local_time_across_dst():
    r = rule("monthly", at(NEW_YORK, 2026, 2, 15, 9, 0))
    got = nxt(r, at(NEW_YORK, 2026, 2, 15, 10, 0), 2)
    assert walls(got, NEW_YORK) == [datetime(2026, 3, 15, 9, 0), datetime(2026, 4, 15, 9, 0)]
