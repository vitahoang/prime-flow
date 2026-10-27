"""Ticket queues.

Every ticket sits in exactly one queue (``Ticket.queue``). Queues are not tied
to agents: whoever is assigned a ticket owns it whatever queue it is in, so one
agent usually holds tickets from several queues at once.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Queue:
    id: str
    name: str
    # Set by team leads for queues that another team follows up day to day.
    muted_in_digest: bool = False


# The queues every install starts with (see ``install_standard_queues``).
STANDARD_QUEUES = (
    Queue("support", "Customer support"),
    Queue("hardware", "Hardware returns and repairs"),
    Queue("billing", "Billing and invoices (finance team)", muted_in_digest=True),
)


def install_standard_queues(store) -> None:
    """Add any standard queue the store doesn't have yet."""
    have = {q.id for q in store.list_queues()}
    for queue in STANDARD_QUEUES:
        if queue.id not in have:
            store.add_queue(queue)
