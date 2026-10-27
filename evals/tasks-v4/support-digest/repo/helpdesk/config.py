"""Deployment settings. Override with environment variables in production."""

import os

SUPPORT_FROM_ADDRESS = os.environ.get("HELPDESK_FROM", "support@acme-tools.example")
SMTP_HOST = os.environ.get("HELPDESK_SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("HELPDESK_SMTP_PORT", "587"))

# Where JsonStore keeps its file when the cron jobs run.
STORE_PATH = os.environ.get("HELPDESK_STORE", "/var/lib/helpdesk/store.json")

# Auto-assignment skips agents who already hold this many active tickets
# unless the agent has their own max_open_tickets.
DEFAULT_MAX_OPEN = 25

# All agents work 09:00-17:00 UTC, so every scheduled email goes out at a
# fixed UTC hour. The daily digest will use DIGEST_HOUR_UTC once it lands.
DIGEST_HOUR_UTC = 9

# The cron schedule for `python -m helpdesk.jobs`.
CRON_INTERVAL_MINUTES = 15
