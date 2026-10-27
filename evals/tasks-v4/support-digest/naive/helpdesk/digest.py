"""Daily digest email for each support agent, sent at DIGEST_HOUR_UTC."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from . import config
from .clock import Clock
from .mailer import Email, Mailer
from .models import RESOLVED, Agent, Ticket
from .store import InMemoryStore
from .templates import SIGNATURE, ticket_line
from .timeutil import ensure_aware

DAY = timedelta(hours=24)
TITLES = {"new": "New tickets", "waiting_on_you": "Waiting on you", "resolved": "Resolved"}


@dataclass
class Digest:
    agent_id: str
    generated_at: datetime
    sections: dict = field(default_factory=dict)


def build_digest(agent: Agent, tickets: list[Ticket], now: datetime) -> Digest:
    now = ensure_aware(now)
    mine = [t for t in tickets if t.assignee == agent.id]
    return Digest(agent.id, now, {
        "new": [t.id for t in mine if t.status != RESOLVED and now - t.created_at <= DAY],
        "waiting_on_you": [t.id for t in mine if t.is_active],
        "resolved": [t.id for t in mine if t.resolved_at and now - t.resolved_at <= DAY],
    })


def send_due_digests(store: InMemoryStore, mailer: Mailer, clock: Clock) -> int:
    now = clock.now()
    if now.hour < config.DIGEST_HOUR_UTC:
        return 0
    count = 0
    for agent in store.list_agents():
        tickets = store.list_tickets(assignee=agent.id)
        digest = build_digest(agent, tickets, now)
        by_id = {t.id: t for t in tickets}
        lines = [f"Hi {agent.first_name()},", ""]
        for name, ids in digest.sections.items():
            lines.append(f"{TITLES[name]}:")
            lines += ["  " + ticket_line(by_id[i], agent, now) for i in ids] or ["  (none)"]
            lines.append("")
        mailer.send(Email(to=agent.email, subject="Your daily digest", body="\n".join(lines + [SIGNATURE])))
        count += 1
    return count
