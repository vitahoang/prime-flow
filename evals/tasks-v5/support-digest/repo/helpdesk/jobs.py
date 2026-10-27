"""Entry point for the cron job (every 15 minutes in production).

Each run is a fresh process: it opens the JSON store, does its work and exits,
so anything that must be remembered between runs has to live in the store.

    python -m helpdesk.jobs
"""

import logging

from . import config
from .clock import SystemClock
from .mailer import SmtpMailer
from .notifications import send_sla_warnings
from .store import JsonStore

log = logging.getLogger("helpdesk.jobs")


def run_all(store, mailer, clock) -> dict:
    results = {"sla_warnings": send_sla_warnings(store, mailer, clock)}
    log.info("jobs done: %s", results)
    return results


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_all(JsonStore(config.STORE_PATH), SmtpMailer(), SystemClock())


if __name__ == "__main__":
    main()
