"""Acceptance tests for helpdesk.digest.build_digest and send_due_digests."""

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from helpdesk.clock import FakeClock
from helpdesk.digest import build_digest, send_due_digests
from helpdesk.mailer import FakeMailer
from helpdesk.models import (
    AGENT_REPLY, CREATED, CUSTOMER_REPLY, INTERNAL_NOTE, OPEN, PENDING_AGENT, PENDING_CUSTOMER, RESOLVED,
    STATUS_CHANGED, Agent, Comment, Event, OutOfOffice, Ticket,
)
from helpdesk.store import InMemoryStore, JsonStore

# Wednesday 14 Oct 2026, 10:00 UTC: after 09:00 UTC and 11:00 in London (BST).
NOW = datetime(2026, 10, 14, 10, 0, tzinfo=timezone.utc)


def utc(day, hour, minute=0, month=10):
    return datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)


def agent(id_="ana", tz="Europe/London", ooo=False, workdays=None, backup=None):
    extra = {} if workdays is None else {"workdays": tuple(workdays)}
    return Agent(id=id_, name=f"{id_.title()} Tester", email=f"{id_}@acme.example", timezone=tz,
                 out_of_office=ooo, backup_id=backup, **extra)


_n = [3000]


def ticket(assignee="ana", status=OPEN, created=None, assigned=None, updated=None, resolved=None, subject=None,
           events=None):
    """A ticket with a consistent event trail. By default the last event (at
    ``updated``) is what the status implies: a customer reply for
    pending_agent, an agent reply for pending_customer."""
    _n[0] += 1
    tid = f"T-{_n[0]}"
    created = created or NOW - timedelta(days=5)
    assigned_at = assigned if assigned is not None else created
    updated = updated or assigned_at
    if events is None:
        events = [Event(CREATED, created, "customer@example.com")]
        if assigned_at != created:
            events.append(Event("assigned", assigned_at, assignee or ""))
        if updated > assigned_at:
            kind = {PENDING_AGENT: CUSTOMER_REPLY, PENDING_CUSTOMER: AGENT_REPLY}.get(status, STATUS_CHANGED)
            events.append(Event(kind, updated))
    else:
        updated = max(e.at for e in events)
    return Ticket(
        id=tid,
        subject=subject or f"Problem number {_n[0]}",
        requester="customer@example.com",
        created_at=created,
        status=status,
        assignee=assignee,
        assigned_at=assigned_at,
        updated_at=updated,
        resolved_at=resolved,
        events=list(events),
        # Mirror workflow.customer_reply / agent_reply / internal_note, which write both trails.
        comments=[Comment(author=e.actor or ("customer@example.com" if e.kind == CUSTOMER_REPLY else assignee or "agent"),
                          body="...", at=e.at, public=e.kind != INTERNAL_NOTE)
                  for e in events if e.kind in (CUSTOMER_REPLY, AGENT_REPLY, INTERNAL_NOTE)],
    )


def new_ticket(assignee="ana", hours_ago=2):
    t = NOW - timedelta(hours=hours_ago)
    return ticket(assignee=assignee, created=t, assigned=t)


def waiting_ticket(assignee="ana"):
    # Waiting on the agent for weeks, so it is in every digest of the period.
    old = utc(1, 9)
    return ticket(assignee=assignee, status=PENDING_AGENT, created=old, assigned=old, updated=old)


def sections(digest):
    return {k: list(v) for k, v in digest.sections.items()}


def make_store(*agents, tickets=()):
    s = InMemoryStore()
    for a in agents:
        s.add_agent(a)
    for t in tickets:
        s.add_ticket(t)
    return s


def mails_to(mailer, address):
    return [e for e in mailer.sent if e.to == address]


def run_cron(store, mailer, start, end, every=timedelta(minutes=15)):
    """Call send_due_digests every 15 minutes; return [(utc time, email)] for each send."""
    clock = FakeClock(start)
    log = []
    while clock.now() <= end:
        before = len(mailer.sent)
        send_due_digests(store, mailer, clock)
        log += [(clock.now(), e) for e in mailer.sent[before:]]
        clock.advance(seconds=every.total_seconds())
    return log


# --- explicit ---------------------------------------------------------------

def test_E1_build_digest_has_new_and_waiting_sections():
    a = agent()
    fresh = new_ticket()
    stuck = ticket(status=PENDING_AGENT, created=NOW - timedelta(hours=30), updated=NOW - timedelta(hours=30))
    d = build_digest(a, [fresh, stuck], NOW)
    s = sections(d)
    assert isinstance(d.sections, dict)
    assert fresh.id in s["new"]
    assert stuck.id in s["waiting_on_you"]


def test_E2_send_due_digests_emails_the_agent():
    a = agent()
    t = new_ticket()
    store = make_store(a, tickets=[t])
    mailer = FakeMailer()
    send_due_digests(store, mailer, FakeClock(NOW))
    mine = mails_to(mailer, a.email)
    assert len(mine) == 1
    assert t.id in mine[0].body or t.subject in mine[0].body


# --- H1: out-of-office agents are skipped -----------------------------------

def test_H1_out_of_office_flag_skips_agent():
    away, here = agent("ana", ooo=True), agent("ben")
    store = make_store(away, here, tickets=[new_ticket("ana"), new_ticket("ben")])
    mailer = FakeMailer()
    send_due_digests(store, mailer, FakeClock(NOW))
    assert mails_to(mailer, away.email) == []
    assert len(mails_to(mailer, here.email)) == 1


def test_H1_out_of_office_range_today_skips_past_range_does_not():
    away = agent("ana", ooo=OutOfOffice(date(2026, 10, 12), date(2026, 10, 16)))
    back = agent("ben", ooo=OutOfOffice(date(2026, 10, 1), date(2026, 10, 5)))
    store = make_store(away, back, tickets=[new_ticket("ana"), new_ticket("ben")])
    mailer = FakeMailer()
    send_due_digests(store, mailer, FakeClock(NOW))
    assert mails_to(mailer, away.email) == []
    assert len(mails_to(mailer, back.email)) == 1


# --- H2: waiting on you = pending_agent, 24h since the last customer-visible event

def test_H2_pending_customer_is_not_waiting_on_you():
    a = agent()
    theirs = ticket(status=PENDING_CUSTOMER, updated=NOW - timedelta(hours=30))
    ours = ticket(status=PENDING_AGENT, updated=NOW - timedelta(hours=30))
    s = sections(build_digest(a, [theirs, ours], NOW))
    assert ours.id in s["waiting_on_you"]
    assert theirs.id not in s["waiting_on_you"]


def test_H2_waiting_counts_from_last_customer_reply_not_creation():
    a = agent()
    recent = ticket(status=PENDING_AGENT, created=NOW - timedelta(days=5), updated=NOW - timedelta(hours=3))
    stale = ticket(status=PENDING_AGENT, created=NOW - timedelta(days=5), updated=NOW - timedelta(hours=26))
    s = sections(build_digest(a, [recent, stale], NOW))
    assert stale.id in s["waiting_on_you"]
    assert recent.id not in s["waiting_on_you"]


def test_H2_internal_note_does_not_reset_the_clock():
    a = agent()
    opened = NOW - timedelta(days=5)
    noted = ticket(status=PENDING_AGENT, created=opened, events=[
        Event(CREATED, opened, "customer@example.com"),
        Event(CUSTOMER_REPLY, NOW - timedelta(hours=30), "customer@example.com"),
        Event(STATUS_CHANGED, NOW - timedelta(hours=30)),
        Event(INTERNAL_NOTE, NOW - timedelta(hours=2), "ana"),
    ])
    assert noted.updated_at == NOW - timedelta(hours=2)
    s = sections(build_digest(a, [noted], NOW))
    assert noted.id in s["waiting_on_you"]


# --- H3: nothing to report -> no digest, no email ----------------------------

def test_H3_build_digest_returns_none_when_empty():
    a = agent()
    assert build_digest(a, [], NOW) is None
    quiet = ticket(status=PENDING_CUSTOMER, updated=NOW - timedelta(hours=2))
    assert build_digest(a, [quiet], NOW) is None


def test_H3_agent_with_nothing_gets_no_email():
    idle, busy = agent("ana"), agent("ben")
    store = make_store(idle, busy, tickets=[new_ticket("ben")])
    mailer = FakeMailer()
    send_due_digests(store, mailer, FakeClock(NOW))
    assert mails_to(mailer, idle.email) == []
    assert len(mails_to(mailer, busy.email)) == 1


# --- H4: never twice a day, even with cron every 15 minutes ------------------

def test_H4_cron_every_15_minutes_sends_once():
    a = agent()
    store = make_store(a, tickets=[new_ticket(), waiting_ticket()])
    mailer = FakeMailer()
    log = run_cron(store, mailer, utc(14, 10), utc(14, 22, 45))
    assert len(log) == 1


def test_H4_late_run_yesterday_does_not_block_today():
    a = agent()
    store = make_store(a, tickets=[waiting_ticket()])
    mailer = FakeMailer()
    # Yesterday's cron was late; today's is on time.
    run_cron(store, mailer, utc(13, 12, 30), utc(13, 13, 0))
    run_cron(store, mailer, utc(14, 10, 5), utc(14, 11, 5))
    assert len(mails_to(mailer, a.email)) == 2


def test_H4_dedupe_survives_a_new_process(tmp_path):
    path = tmp_path / "store.json"
    s = JsonStore(path)
    a = agent()
    s.add_agent(a)
    s.add_ticket(new_ticket())
    mailer = FakeMailer()
    send_due_digests(s, mailer, FakeClock(NOW))
    send_due_digests(JsonStore(path), mailer, FakeClock(NOW + timedelta(minutes=15)))
    send_due_digests(JsonStore(path), mailer, FakeClock(NOW + timedelta(minutes=30)))
    assert len(mails_to(mailer, a.email)) == 1


# --- H5 (change of mind): 08:00 in the agent's own timezone ------------------

def test_H5_ho_chi_minh_agent_gets_it_after_8_local():
    a = agent("mai", tz="Asia/Ho_Chi_Minh")  # UTC+7
    store = make_store(a, tickets=[waiting_ticket("mai")])
    mailer = FakeMailer()
    send_due_digests(store, mailer, FakeClock(utc(14, 0, 45)))   # 07:45 local
    assert mails_to(mailer, a.email) == []
    send_due_digests(store, mailer, FakeClock(utc(14, 1, 5)))    # 08:05 local
    assert len(mails_to(mailer, a.email)) == 1


def test_H5_los_angeles_agent_not_before_8_local():
    a = agent("sam", tz="America/Los_Angeles")  # UTC-7 in October
    store = make_store(a, tickets=[waiting_ticket("sam")])
    mailer = FakeMailer()
    send_due_digests(store, mailer, FakeClock(utc(14, 10)))      # 03:00 local
    assert mails_to(mailer, a.email) == []
    send_due_digests(store, mailer, FakeClock(utc(14, 15, 10)))  # 08:10 local
    assert len(mails_to(mailer, a.email)) == 1


def test_H5_each_agent_once_per_local_day_after_8():
    agents = [agent("mai", "Asia/Ho_Chi_Minh"), agent("sam", "America/Los_Angeles"), agent("priya", "Europe/London")]
    store = make_store(*agents, tickets=[waiting_ticket(a.id) for a in agents])
    mailer = FakeMailer()
    # From midnight 13 Oct in Los Angeles (14:00 in Ho Chi Minh City, 08:00 in London).
    log = run_cron(store, mailer, utc(13, 7), utc(15, 23, 45))
    for a in agents:
        tz = ZoneInfo(a.timezone)
        local_times = [when.astimezone(tz) for when, e in log if e.to == a.email]
        assert all(t.hour >= 8 for t in local_times), (a.id, local_times)
        days = [t.date() for t in local_times]
        assert days == sorted(set(days)), (a.id, days)
        assert days == [date(2026, 10, 13), date(2026, 10, 14), date(2026, 10, 15)], (a.id, days)


# --- H6 (change of mind): no resolved section --------------------------------

def test_H6_digest_has_no_resolved_tickets():
    a = agent()
    done = ticket(status=RESOLVED, resolved=NOW - timedelta(hours=2), updated=NOW - timedelta(hours=2))
    fresh = new_ticket()
    s = sections(build_digest(a, [done, fresh], NOW))
    assert s.get("resolved", []) == []
    assert all(done.id not in ids for ids in s.values())


def test_H6_only_resolved_tickets_means_no_digest():
    a = agent()
    done = ticket(status=RESOLVED, resolved=NOW - timedelta(hours=2), updated=NOW - timedelta(hours=2))
    assert build_digest(a, [done], NOW) is None


def test_H6_email_does_not_mention_resolved():
    a = agent()
    done = ticket(status=RESOLVED, resolved=NOW - timedelta(hours=2), updated=NOW - timedelta(hours=2),
                  subject="Printer finally fixed")
    store = make_store(a, tickets=[done, new_ticket()])
    mailer = FakeMailer()
    send_due_digests(store, mailer, FakeClock(NOW))
    (email,) = mails_to(mailer, a.email)
    text = (email.subject + "\n" + email.body).lower()
    assert done.id.lower() not in text
    assert "printer finally fixed" not in text


# --- T1: "once a day" is the agent's local day, not the UTC date ------------

def test_T1_los_angeles_one_email_across_utc_midnight():
    a = agent("sam", tz="America/Los_Angeles")
    store = make_store(a, tickets=[waiting_ticket("sam")])
    mailer = FakeMailer()
    # 08:00 to 23:45 on Wed 14 Oct in Los Angeles; crosses midnight UTC.
    log = run_cron(store, mailer, utc(14, 15), utc(15, 6, 45))
    assert len(log) == 1


def test_T1_auckland_new_local_day_before_utc_midnight():
    a = agent("aroha", tz="Pacific/Auckland")  # UTC+13 in October
    store = make_store(a, tickets=[waiting_ticket("aroha")])
    mailer = FakeMailer()
    # 19:30 on 14 Oct in Auckland (a late run) through 09:00 on 15 Oct, all on 14 Oct UTC.
    log = run_cron(store, mailer, utc(14, 6, 30), utc(14, 20, 0))
    days = [when.astimezone(ZoneInfo("Pacific/Auckland")).date() for when, _ in log]
    assert days == [date(2026, 10, 14), date(2026, 10, 15)]


# --- T2: "new" = assigned within the 24 hours before the digest --------------

def test_T2_new_counts_from_assignment_not_creation():
    a = agent()
    handed_over = ticket(created=NOW - timedelta(days=4), assigned=NOW - timedelta(hours=2))
    old = ticket(created=NOW - timedelta(hours=30), assigned=NOW - timedelta(hours=30))
    s = sections(build_digest(a, [handed_over, old], NOW))
    assert handed_over.id in s["new"]
    assert old.id not in s["new"]


def test_T2_window_is_the_24_hours_before_now():
    a = agent()
    last_night = ticket(created=utc(13, 23), assigned=utc(13, 23))   # 11h before NOW
    day_before = ticket(created=utc(13, 8), assigned=utc(13, 8))     # 26h before NOW
    s = sections(build_digest(a, [last_night, day_before], NOW))
    assert last_night.id in s["new"]
    assert day_before.id not in s["new"]


# --- H7 (second change of mind): no digest on the agent's days off ----------

def test_H7_saturday_to_wednesday_agent_gets_nothing_thursday_friday():
    a = agent("mai", tz="Asia/Ho_Chi_Minh", workdays=(5, 6, 0, 1, 2))
    store = make_store(a, tickets=[waiting_ticket("mai")])
    mailer = FakeMailer()
    # Thu 15 Oct 00:00 to Sat 17 Oct 23:45 in Ho Chi Minh City.
    log = run_cron(store, mailer, utc(14, 17), utc(17, 16, 45))
    days = [when.astimezone(ZoneInfo("Asia/Ho_Chi_Minh")).date() for when, _ in log]
    assert days == [date(2026, 10, 17)]


def test_H7_default_workweek_has_no_weekend_digest():
    a = agent("priya")  # default workdays, Monday to Friday
    store = make_store(a, tickets=[waiting_ticket("priya")])
    mailer = FakeMailer()
    # Sat 17 Oct 00:00 to Mon 19 Oct 23:45 in London.
    log = run_cron(store, mailer, utc(16, 23), utc(19, 22, 45))
    days = [when.astimezone(ZoneInfo("Europe/London")).date() for when, _ in log]
    assert days == [date(2026, 10, 19)]


# --- H8 (second change of mind): first day back covers since the last digest ----

def _first_day_back(a, tz, before, gap_start, gap_ticket_at, after_end, back_day):
    store = make_store(a, tickets=[waiting_ticket(a.id)])
    mailer = FakeMailer()
    run_cron(store, mailer, *before)
    assert len(mails_to(mailer, a.email)) == 1
    gap = ticket(assignee=a.id, created=gap_ticket_at, assigned=gap_ticket_at, subject="Handed over on a day off")
    store.add_ticket(gap)
    log = run_cron(store, mailer, gap_start, after_end)
    back = [e for when, e in log if when.astimezone(ZoneInfo(tz)).date() == back_day]
    assert len(back) == 1
    assert gap.id in back[0].body or gap.subject in back[0].body


def test_H8_saturday_digest_covers_thursday_and_friday():
    a = agent("mai", tz="Asia/Ho_Chi_Minh", workdays=(5, 6, 0, 1, 2))
    _first_day_back(
        a, "Asia/Ho_Chi_Minh",
        before=(utc(14, 0, 30), utc(14, 2)),        # Wed 14 Oct, digest at 08:00 local
        gap_start=utc(14, 2, 15),
        gap_ticket_at=utc(15, 3),                    # Thu 15 Oct 10:00 local, a day off
        after_end=utc(17, 2),                        # Sat 17 Oct 09:00 local
        back_day=date(2026, 10, 17),
    )


def test_H8_monday_digest_covers_the_weekend():
    a = agent("priya")  # Monday to Friday, London
    _first_day_back(
        a, "Europe/London",
        before=(utc(16, 6, 30), utc(16, 8)),         # Fri 16 Oct, digest at 08:00 local
        gap_start=utc(16, 8, 15),
        gap_ticket_at=utc(17, 11),                   # Sat 17 Oct, about 44h before Monday's digest
        after_end=utc(19, 8),                        # Mon 19 Oct 09:00 local
        back_day=date(2026, 10, 19),
    )


# --- H9 (follow-up to H1): an away agent's tickets go to their backup --------

def test_H9_backup_digest_includes_away_agents_tickets():
    away = agent("ana", ooo=True, backup="ben")
    backup = agent("ben")
    stuck, fresh, own = waiting_ticket("ana"), new_ticket("ana"), new_ticket("ben")
    store = make_store(away, backup, tickets=[stuck, fresh, own])
    mailer = FakeMailer()
    send_due_digests(store, mailer, FakeClock(NOW))
    assert mails_to(mailer, away.email) == []
    (email,) = mails_to(mailer, backup.email)
    for t in (stuck, fresh, own):
        assert t.id in email.body or t.subject in email.body


def test_H9_backup_with_nothing_of_their_own_still_gets_covered_tickets():
    away = agent("ana", ooo=OutOfOffice(date(2026, 10, 12), date(2026, 10, 16)), backup="ben")
    present = agent("cara", backup="ben")  # names ben as backup but is not away
    backup = agent("ben")
    stuck, cara_t = waiting_ticket("ana"), new_ticket("cara")
    store = make_store(away, present, backup, tickets=[stuck, cara_t])
    mailer = FakeMailer()
    send_due_digests(store, mailer, FakeClock(NOW))
    (email,) = mails_to(mailer, backup.email)
    assert stuck.id in email.body or stuck.subject in email.body
    assert cara_t.id not in email.body
    assert len(mails_to(mailer, present.email)) == 1
