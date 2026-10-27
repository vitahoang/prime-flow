"""Daily digest email for each support agent.

``send_due_digests`` is called by cron every 15 minutes. Each agent gets at
most one digest per day in their own timezone, sent on the first run at or
after 08:00 local time. Agents who are out of office and agents with nothing
to report get no email.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from .clock import Clock
from .mailer import Email, Mailer, MailerError
from .models import PENDING_AGENT, Agent, Ticket
from .store import InMemoryStore, Notification
from .templates import SIGNATURE, ticket_line
from .timeutil import ensure_aware, to_local

DIGEST = "digest"
SEND_HOUR_LOCAL = 8
WINDOW = timedelta(hours=24)

NEW = "new"
WAITING_ON_YOU = "waiting_on_you"
TITLES = {NEW: "New for you (last 24 hours)", WAITING_ON_YOU: "Waiting on you for more than a day"}


@dataclass
class Digest:
    agent_id: str
    generated_at: datetime
    sections: dict = field(default_factory=dict)  # section name -> list of ticket ids


def build_digest(agent: Agent, tickets: list[Ticket], now: datetime) -> Optional[Digest]:
    now = ensure_aware(now)
    mine = [t for t in tickets if t.assignee == agent.id and t.is_active]
    new = [t.id for t in mine if now - WINDOW <= (t.assigned_at or t.created_at) <= now]
    waiting = [t.id for t in mine if t.status == PENDING_AGENT and now - t.updated_at > WINDOW]
    if not new and not waiting:
        return None
    return Digest(agent_id=agent.id, generated_at=now, sections={NEW: new, WAITING_ON_YOU: waiting})


def render(digest: Digest, agent: Agent, tickets: list[Ticket]) -> Email:
    by_id = {t.id: t for t in tickets}
    lines = [f"Hi {agent.first_name()},", "", "Here is your daily support digest.", ""]
    for name in (NEW, WAITING_ON_YOU):
        ids = digest.sections.get(name, [])
        if not ids:
            continue
        lines.append(f"{TITLES[name]} ({len(ids)}):")
        lines += ["  " + ticket_line(by_id[i], agent, digest.generated_at) for i in ids]
        lines.append("")
    lines.append(SIGNATURE)
    count = sum(len(v) for v in digest.sections.values())
    return Email(to=agent.email, subject=f"Your support digest: {count} tickets", body="\n".join(lines))


def send_due_digests(store: InMemoryStore, mailer: Mailer, clock: Clock) -> int:
    now = clock.now()
    sent = 0
    for agent in store.list_agents():
        local = to_local(now, agent.timezone)
        if local.hour < SEND_HOUR_LOCAL:
            continue
        today = local.date()
        if agent.is_away(today):
            continue
        key = today.isoformat()
        if any(n.key == key for n in store.notifications(kind=DIGEST, agent_id=agent.id)):
            continue
        tickets = store.list_tickets(assignee=agent.id)
        digest = build_digest(agent, tickets, now)
        if digest is None:
            continue
        try:
            mailer.send(render(digest, agent, tickets))
        except MailerError:
            continue
        store.record_notification(Notification(kind=DIGEST, agent_id=agent.id, sent_at=now, key=key))
        sent += 1
    return sent
