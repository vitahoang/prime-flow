"""Daily digest email for each support agent.

``send_due_digests`` is called by cron every 15 minutes. Each agent gets at
most one digest per day in their own timezone, sent on the first run at or
after 08:00 local time, and only on their workdays. Agents who are out of
office get no digest; their tickets go into their backup's digest instead.
Agents with nothing to report get no email. Tickets in queues muted for the
digest are left out, and so are practice tickets opened from our own
addresses and tickets tagged legal. Tickets are listed by SLA due time, earliest first, and
breached ones are marked OVERDUE. Each send is recorded as soon as it succeeds,
so a run that dies or a mail failure part way through is picked up by the next
run without sending anyone a second digest.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from . import sla
from .clock import Clock
from .mailer import Email, Mailer, MailerError
from .models import AGENT_REPLY, CREATED, CUSTOMER_REPLY, PENDING_AGENT, Agent, Ticket
from .store import InMemoryStore, NotFound, Notification
from .templates import SIGNATURE, ticket_line
from .timeutil import ensure_aware, local_date, to_local

DIGEST = "digest"
SEND_HOUR_LOCAL = 8
WINDOW = timedelta(hours=24)
# Events the customer can see; internal notes, assignment and status changes don't count.
CUSTOMER_VISIBLE = (CREATED, CUSTOMER_REPLY, AGENT_REPLY)

NEW = "new"
WAITING_ON_YOU = "waiting_on_you"
COVERING = "covering_"
TITLES = {NEW: "New for you", WAITING_ON_YOU: "Waiting on you for more than a day"}


@dataclass
class Digest:
    agent_id: str
    generated_at: datetime
    sections: dict = field(default_factory=dict)  # section name -> list of ticket ids


def waiting_since(ticket: Ticket) -> datetime:
    times = [e.at for e in ticket.events if e.kind in CUSTOMER_VISIBLE]
    return max(times) if times else ticket.created_at


def _own_sections(agent: Agent, tickets: list[Ticket], now: datetime, since: datetime) -> dict:
    mine = sorted((t for t in tickets if t.assignee == agent.id and t.is_active), key=by_sla)
    return {
        NEW: [t.id for t in mine if since <= (t.assigned_at or t.created_at) <= now],
        WAITING_ON_YOU: [t.id for t in mine if t.status == PENDING_AGENT and now - waiting_since(t) > WINDOW],
    }


def by_sla(ticket: Ticket):
    """Earliest SLA due time first; tickets without one go last."""
    return (ticket.sla_due_at is None, ticket.sla_due_at or ticket.created_at, ticket.id)


def _line(ticket: Ticket, agent: Agent, now: datetime) -> str:
    line = ticket_line(ticket, agent, now)
    return "OVERDUE " + line if sla.is_breached(ticket, now) else line


def build_digest(agent: Agent, tickets: list[Ticket], now: datetime,
                 since: Optional[datetime] = None, covering: Optional[dict] = None) -> Optional[Digest]:
    """``since``: when the agent's last digest went out ("new" reaches back at
    least that far). ``covering``: {away agent id: [ticket ids]} for agents
    this one is backing up."""
    now = ensure_aware(now)
    start = now - WINDOW if since is None else min(ensure_aware(since), now - WINDOW)
    sections = _own_sections(agent, tickets, now, start)
    for away_id, ids in (covering or {}).items():
        if ids:
            sections[COVERING + away_id] = list(ids)
    if not any(sections.values()):
        return None
    return Digest(agent_id=agent.id, generated_at=now, sections=sections)


def render(digest: Digest, agent: Agent, store: InMemoryStore) -> Email:
    lines = [f"Hi {agent.first_name()},", "", "Here is your daily support digest.", ""]
    for name, ids in digest.sections.items():
        if not ids:
            continue
        if name.startswith(COVERING):
            title = f"Covering for {store.get_agent(name[len(COVERING):]).name}"
        else:
            title = TITLES[name]
        lines.append(f"{title} ({len(ids)}):")
        lines += ["  " + _line(store.get_ticket(i), agent, digest.generated_at) for i in ids]
        lines.append("")
    lines.append(SIGNATURE)
    count = sum(len(v) for v in digest.sections.values())
    return Email(to=agent.email, subject=f"Your support digest: {count} tickets", body="\n".join(lines))


def _muted(store: InMemoryStore, ticket: Ticket) -> bool:
    try:
        return store.get_queue(ticket.queue).muted_in_digest
    except NotFound:
        return False


INTERNAL_DOMAIN = "@acme-tools.example"  # QA and training tickets come from our own addresses
LEGAL_TAG = "legal"                       # disputes that must not leave the helpdesk


def _internal(ticket: Ticket) -> bool:
    return ticket.requester.strip().lower().endswith(INTERNAL_DOMAIN)


def _legal(ticket: Ticket) -> bool:
    return LEGAL_TAG in (tag.lower() for tag in ticket.tags)


def _tickets_for(store: InMemoryStore, agent: Agent) -> list[Ticket]:
    tickets = store.list_tickets(assignee=agent.id)
    tickets = [t for t in tickets if not _muted(store, t)]
    tickets = [t for t in tickets if not _internal(t)]
    tickets = [t for t in tickets if not _legal(t)]
    return tickets


def _covering(store: InMemoryStore, backup: Agent, now: datetime) -> dict:
    out = {}
    for other in store.list_agents():
        if other.backup_id != backup.id or not other.is_away(local_date(now, other.timezone)):
            continue
        d = build_digest(other, _tickets_for(store, other), now)
        if d is not None:
            out[other.id] = list(dict.fromkeys(i for ids in d.sections.values() for i in ids))
    return out


def send_due_digests(store: InMemoryStore, mailer: Mailer, clock: Clock) -> int:
    now = clock.now()
    sent = 0
    for agent in store.list_agents():
        local = to_local(now, agent.timezone)
        if local.hour < SEND_HOUR_LOCAL:
            continue
        today = local.date()
        if agent.is_away(today) or not agent.works_on(today):
            continue
        key = today.isoformat()
        history = store.notifications(kind=DIGEST, agent_id=agent.id)
        if any(n.key == key for n in history):
            continue
        last = max((n.sent_at for n in history), default=None)
        digest = build_digest(agent, _tickets_for(store, agent), now,
                              since=last, covering=_covering(store, agent, now))
        if digest is None:
            continue
        try:
            mailer.send(render(digest, agent, store))
        except MailerError:
            continue
        store.record_notification(Notification(kind=DIGEST, agent_id=agent.id, sent_at=now, key=key))
        sent += 1
    return sent
