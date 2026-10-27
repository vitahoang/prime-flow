"""Acceptance tests for alertd.throttle.Throttler(settings, clock).should_send(alert)."""

from datetime import datetime, timezone

from alertd.clock import FakeClock
from alertd.models import Alert, CRITICAL, INFO, WARNING, EMAIL, SMS, SLACK
from alertd.notifiers import build_notifiers
from alertd.router import Router
from alertd.settings import UserSettings
from alertd.throttle import Throttler

DAY = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)


def at(hour, minute=0, second=0, day=14):
    return datetime(2026, 10, day, hour, minute, second, tzinfo=timezone.utc)


def make(tz="UTC", start=DAY):
    settings = UserSettings(user_id="dana", timezone=tz, email="d@x", phone="+1", slack_handle="@d")
    clock = FakeClock(start)
    return settings, clock, Throttler(settings, clock)


_n = [0]


def alert(channel, severity=WARNING, source="api", message=None):
    if message is None:
        _n[0] += 1
        message = f"event {_n[0]}"
    return Alert(severity, source, message, channel)


# --- explicit ---------------------------------------------------------------

def test_E1_should_send_returns_bool_and_first_alert_goes():
    _, _, t = make()
    result = t.should_send(alert(EMAIL))
    assert isinstance(result, bool)
    assert result is True


def test_E1_flood_on_one_channel_is_cut_down():
    _, clock, t = make()
    results = []
    for _ in range(60):
        results.append(t.should_send(alert(SLACK, severity=INFO)))
        clock.advance(seconds=1)
    assert results[0] is True
    assert results.count(True) < 60


def test_E2_router_uses_throttler():
    settings, clock, t = make()
    notifiers = build_notifiers(settings)
    router = Router(notifiers, clock=clock, throttler=t)
    outcomes = [router.route(alert(SLACK)) for _ in range(60)]
    assert outcomes[0] is True
    assert False in outcomes
    assert len(notifiers[SLACK].sent) == outcomes.count(True) < 60


# --- H1: critical is never throttled -----------------------------------------

def test_H1_critical_flood_on_sms_all_goes():
    _, clock, t = make()
    for _ in range(20):
        assert t.should_send(alert(SMS, severity=CRITICAL)) is True
        clock.advance(seconds=5)


def test_H1_critical_duplicates_all_go():
    _, clock, t = make()
    for _ in range(5):
        assert t.should_send(alert(SLACK, severity=CRITICAL, source="db", message="primary down")) is True
        clock.advance(seconds=30)


def test_H1_critical_goes_after_channel_budget_spent():
    _, clock, t = make()
    for _ in range(15):
        t.should_send(alert(SMS))
        clock.advance(seconds=10)
    assert t.should_send(alert(SMS, severity=CRITICAL)) is True


def test_H1_critical_goes_during_quiet_hours():
    _, _, t = make(start=at(2))
    assert t.should_send(alert(SMS, severity=CRITICAL)) is True


# --- H2: per-channel limits, SMS strictest ------------------------------------

def test_H2_sms_allows_three_then_blocks_within_half_hour():
    _, clock, t = make()
    results = []
    for _ in range(8):
        results.append(t.should_send(alert(SMS)))
        clock.advance(minutes=3)  # 8 alerts over 24 minutes
    assert results[:3] == [True, True, True]
    assert not any(results[3:])


def test_H2_slack_is_lenient():
    _, clock, t = make()
    results = []
    for _ in range(25):
        results.append(t.should_send(alert(SLACK)))
        clock.advance(seconds=2)  # 25 alerts in under a minute
    assert all(results)


def test_H2_email_allows_ten_then_blocks():
    _, clock, t = make()
    results = []
    for _ in range(14):
        results.append(t.should_send(alert(EMAIL)))
        clock.advance(minutes=1)
    assert all(results[:10])
    assert not any(results[10:])


# --- H3: quiet hours 22:00-07:00, only critical goes ---------------------------

def test_H3_warning_blocked_late_evening():
    _, _, t = make(start=at(23, 30))
    assert t.should_send(alert(SLACK)) is False


def test_H3_info_blocked_early_morning_then_allowed_at_seven():
    _, clock, t = make(start=at(6, 50))
    assert t.should_send(alert(EMAIL, severity=INFO)) is False
    clock.set(at(7, 5))
    assert t.should_send(alert(EMAIL, severity=INFO)) is True


def test_H3_evening_before_ten_still_sends():
    _, _, t = make(start=at(21, 50))
    assert t.should_send(alert(SMS)) is True


def test_H3_critical_still_goes_at_night():
    _, _, t = make(start=at(3, 15))
    assert t.should_send(alert(EMAIL, severity=CRITICAL)) is True
    assert t.should_send(alert(EMAIL, severity=WARNING)) is False


# --- H4: duplicates collapsed within ten minutes ------------------------------

def test_H4_same_source_and_message_collapsed():
    _, clock, t = make()
    assert t.should_send(alert(SLACK, source="db", message="disk 91%")) is True
    clock.advance(minutes=3)
    assert t.should_send(alert(SLACK, source="db", message="disk 91%")) is False


def test_H4_rapid_repeats_send_once():
    _, clock, t = make()
    results = []
    for _ in range(6):
        results.append(t.should_send(alert(SLACK, source="cron", message="job late")))
        clock.advance(seconds=20)
    assert results == [True] + [False] * 5


def test_H4_different_source_or_message_not_collapsed():
    _, clock, t = make()
    assert t.should_send(alert(SLACK, source="db", message="disk 91%")) is True
    clock.advance(seconds=10)
    assert t.should_send(alert(SLACK, source="db2", message="disk 91%")) is True
    clock.advance(seconds=10)
    assert t.should_send(alert(SLACK, source="db", message="disk 95%")) is True


def test_H4_duplicate_goes_again_after_window():
    _, clock, t = make()
    assert t.should_send(alert(SLACK, source="db", message="disk 91%")) is True
    clock.advance(minutes=12)
    assert t.should_send(alert(SLACK, source="db", message="disk 91%")) is True


# --- H5: sliding window, not fixed buckets -------------------------------------

def test_H5_burst_across_bucket_boundary_still_blocked():
    _, clock, t = make(start=at(10, 29))
    for _ in range(3):
        assert t.should_send(alert(SMS)) is True
        clock.advance(seconds=10)
    clock.set(at(10, 30, 30))
    assert t.should_send(alert(SMS)) is False
    clock.set(at(10, 59, 30))
    assert t.should_send(alert(SMS)) is True  # all three have aged out


def test_H5_budget_frees_up_as_old_sends_age_out():
    _, clock, t = make(start=at(10, 0))
    for minute in (0, 5, 10):
        clock.set(at(10, minute))
        assert t.should_send(alert(SMS)) is True
    clock.set(at(10, 31))
    assert t.should_send(alert(SMS)) is True   # 10:00 send has aged out
    clock.set(at(10, 32))
    assert t.should_send(alert(SMS)) is False  # 10:05, 10:10, 10:31 still in window
    clock.set(at(10, 36))
    assert t.should_send(alert(SMS)) is True   # 10:05 has aged out


# --- T1: budgets are per channel, not one global limit -------------------------

def test_T1_busy_slack_does_not_block_sms():
    _, clock, t = make()
    for _ in range(25):
        t.should_send(alert(SLACK))
        clock.advance(seconds=1)
    assert t.should_send(alert(SMS)) is True


def test_T1_spent_sms_does_not_block_email_or_slack():
    _, clock, t = make()
    for _ in range(3):
        t.should_send(alert(SMS))
        clock.advance(seconds=1)
    assert t.should_send(alert(SMS)) is False
    for _ in range(10):
        assert t.should_send(alert(EMAIL)) is True
    for _ in range(10):
        assert t.should_send(alert(SLACK)) is True


# --- T2: quiet hours use the user's timezone, not UTC --------------------------

def test_T2_quiet_hours_in_los_angeles_evening():
    # 06:00 UTC on 14 Oct is 23:00 PDT on 13 Oct
    _, _, t = make(tz="America/Los_Angeles", start=at(6, 0))
    assert t.should_send(alert(SLACK)) is False


def test_T2_utc_night_is_daytime_in_los_angeles():
    # 23:30 UTC is 16:30 PDT
    _, _, t = make(tz="America/Los_Angeles", start=at(23, 30))
    assert t.should_send(alert(SLACK)) is True


def test_T2_quiet_hours_in_ho_chi_minh():
    # 16:00 UTC is 23:00 in Ho Chi Minh City (UTC+7); 02:00 UTC is 09:00 there
    _, clock, t = make(tz="Asia/Ho_Chi_Minh", start=at(16, 0))
    assert t.should_send(alert(EMAIL)) is False
    clock.set(at(2, 0, day=15))
    assert t.should_send(alert(EMAIL)) is True
