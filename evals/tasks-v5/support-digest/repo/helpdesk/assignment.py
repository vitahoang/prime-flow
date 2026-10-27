"""Assigning tickets to agents, by hand or automatically."""

from typing import Optional

from . import config
from .clock import Clock
from .mailer import Mailer
from .models import ASSIGNED, Agent, Ticket
from .notifications import notify_assignment
from .store import InMemoryStore
from .timeutil import local_date


class NoAgentAvailable(RuntimeError):
    pass


def assign(store: InMemoryStore, clock: Clock, ticket_id: str, agent_id: str,
           mailer: Optional[Mailer] = None) -> Ticket:
    """Assign a ticket. Sets ``assigned_at``; emails the agent if a mailer is given."""
    ticket = store.get_ticket(ticket_id)
    store.get_agent(agent_id)  # must exist
    if ticket.assignee == agent_id:
        return ticket
    now = clock.now()
    ticket.assignee = agent_id
    ticket.assigned_at = now
    ticket.log(ASSIGNED, now, agent_id)
    store.save_ticket(ticket)
    if mailer is not None:
        notify_assignment(store, mailer, clock, ticket)
    return ticket


def unassign(store: InMemoryStore, clock: Clock, ticket_id: str) -> Ticket:
    ticket = store.get_ticket(ticket_id)
    ticket.assignee = None
    ticket.assigned_at = None
    ticket.touch(clock.now())
    store.save_ticket(ticket)
    return ticket


def open_load(store: InMemoryStore, agent_id: str) -> int:
    return sum(1 for t in store.list_tickets(assignee=agent_id) if t.is_active)


def available_agents(store: InMemoryStore, clock: Clock, skill: Optional[str] = None) -> list[Agent]:
    """Agents who can take a new ticket right now: not away today (in their own
    timezone), under their ticket limit, and with the skill if one is asked for."""
    now = clock.now()
    out = []
    for agent in store.list_agents():
        if agent.is_away(local_date(now, agent.timezone)):
            continue
        limit = agent.max_open_tickets or config.DEFAULT_MAX_OPEN
        if open_load(store, agent.id) >= limit:
            continue
        if skill and skill not in agent.skills:
            continue
        out.append(agent)
    return out


def auto_assign(store: InMemoryStore, clock: Clock, ticket_id: str,
                mailer: Optional[Mailer] = None) -> Ticket:
    """Give the ticket to the available agent with the fewest active tickets.

    A ticket tagged ``skill:<name>`` only goes to agents with that skill.
    """
    ticket = store.get_ticket(ticket_id)
    skill = next((tag.split(":", 1)[1] for tag in ticket.tags if tag.startswith("skill:")), None)
    candidates = available_agents(store, clock, skill=skill)
    if not candidates:
        raise NoAgentAvailable(ticket_id)
    best = min(candidates, key=lambda a: (open_load(store, a.id), a.id))
    return assign(store, clock, ticket_id, best.id, mailer=mailer)


def rebalance(store: InMemoryStore, clock: Clock, mailer: Optional[Mailer] = None) -> list[Ticket]:
    """Move active tickets off agents who are away today."""
    now = clock.now()
    moved = []
    for agent in store.list_agents():
        if not agent.is_away(local_date(now, agent.timezone)):
            continue
        for ticket in store.list_tickets(assignee=agent.id):
            if ticket.is_active:
                try:
                    moved.append(auto_assign(store, clock, ticket.id, mailer=mailer))
                except NoAgentAvailable:
                    pass
    return moved
