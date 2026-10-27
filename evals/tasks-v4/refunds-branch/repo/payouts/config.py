"""Runtime configuration, read from the environment.

PAYOUTS_DATA_DIR        directory holding the JSON store (default ./.payouts-data)
PAYOUTS_GATEWAY_FAULTS  faults the fake gateway should inject, see gateway.py
"""

from __future__ import annotations

import os
from pathlib import Path

DATA_DIR_ENV = "PAYOUTS_DATA_DIR"
GATEWAY_FAULTS_ENV = "PAYOUTS_GATEWAY_FAULTS"
DEFAULT_DATA_DIR = ".payouts-data"

# Marketplace default pricing: 2.9% + 30c per charge.
DEFAULT_FEE_BPS = 290
DEFAULT_FEE_FIXED_CENTS = 30

# How many times a gateway call is attempted when it times out.
GATEWAY_ATTEMPTS = 3
GATEWAY_BACKOFF_SECONDS = 0.0

CURRENCY = "USD"


def data_dir() -> Path:
    return Path(os.environ.get(DATA_DIR_ENV) or DEFAULT_DATA_DIR)


def gateway_faults() -> list[tuple[str, str]]:
    """Parse PAYOUTS_GATEWAY_FAULTS into (operation, fault) pairs.

    The value is a comma-separated list of OP:FAULT items, consumed in order
    by calls of that operation, for example ``charge:timeout,charge:lost``.
    An empty or unset variable means no faults.
    """
    raw = os.environ.get(GATEWAY_FAULTS_ENV, "")
    faults = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        op, sep, fault = item.partition(":")
        if not sep or not op or not fault:
            raise ValueError(f"bad {GATEWAY_FAULTS_ENV} item: {item!r} (want OP:FAULT)")
        faults.append((op.strip(), fault.strip()))
    return faults
