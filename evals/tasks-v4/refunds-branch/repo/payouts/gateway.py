"""Client for the card processor, plus the fake we run against locally.

The real processor client lives in the infra repo; everything here talks to
``FakeGateway``, which behaves like the processor closely enough for
development and tests: it hands out references, keeps a record of every
operation it has *committed*, and can be told to misbehave.

Fault injection
---------------
Set PAYOUTS_GATEWAY_FAULTS to a comma-separated list of OP:FAULT items. Each
call of OP consumes the next fault queued for that OP:

    timeout   the call times out before reaching the processor (nothing happens)
    decline   the processor declines the call
    lost      the processor commits the operation, but the response is lost
              and the client sees a timeout

e.g. ``PAYOUTS_GATEWAY_FAULTS=charge:timeout,charge:timeout`` makes the first
two charge attempts in the process time out.

Idempotency keys are accepted for signature compatibility with the real
client, but the fake does not enforce them.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, TypeVar

from payouts import clock, config
from payouts.errors import PayoutsError
from payouts.store import Store

STATE = "gateway"
FAULTS = ("timeout", "decline", "lost")

T = TypeVar("T")


class GatewayError(PayoutsError):
    """The processor rejected a call or could not be reached."""


class GatewayTimeout(GatewayError):
    """No response from the processor. The call may or may not have happened."""


class GatewayDeclined(GatewayError):
    """The processor said no."""


def new_idempotency_key() -> str:
    return uuid.uuid4().hex


def call_with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = config.GATEWAY_ATTEMPTS,
    backoff: float = config.GATEWAY_BACKOFF_SECONDS,
) -> T:
    """Call ``fn``, retrying on GatewayTimeout up to ``attempts`` times in total.

    Declines and other errors are not retried. If every attempt times out the
    last GatewayTimeout is raised.
    """
    last: GatewayTimeout | None = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except GatewayTimeout as exc:
            last = exc
            if attempt < attempts and backoff:
                time.sleep(backoff * attempt)
    assert last is not None
    raise last


class FakeGateway:
    """Stand-in processor. State lives in the store so separate CLI runs see
    the same processor."""

    def __init__(self, store: Store, faults: list[tuple[str, str]] | None = None):
        self.store = store
        if faults is None:
            faults = config.gateway_faults()
        for op, fault in faults:
            if fault not in FAULTS:
                raise ValueError(f"unknown gateway fault {fault!r} for {op!r}")
        self._faults = list(faults)

    # -- public operations ------------------------------------------------

    def charge(self, amount_cents: int, description: str, idempotency_key: str | None = None) -> dict[str, Any]:
        if amount_cents <= 0:
            raise GatewayDeclined("amount must be positive")
        return self._call("charge", {"amount_cents": amount_cents, "description": description}, idempotency_key)

    def payout(self, merchant_id: str, amount_cents: int, idempotency_key: str | None = None) -> dict[str, Any]:
        if amount_cents <= 0:
            raise GatewayDeclined("amount must be positive")
        return self._call("payout", {"amount_cents": amount_cents, "merchant_id": merchant_id}, idempotency_key)

    def refund(self, charge_ref: str, amount_cents: int, idempotency_key: str | None = None) -> dict[str, Any]:
        if amount_cents <= 0:
            raise GatewayDeclined("amount must be positive")
        if not any(op["op"] == "charge" and op["ref"] == charge_ref for op in self.operations()):
            raise GatewayDeclined(f"unknown charge {charge_ref}")
        return self._call("refund", {"amount_cents": amount_cents, "charge_ref": charge_ref}, idempotency_key)

    def operations(self) -> list[dict[str, Any]]:
        """Every operation the processor has committed, oldest first."""
        return list(self._state().get("operations", []))

    # -- internals --------------------------------------------------------

    def _state(self) -> dict[str, Any]:
        state = self.store.load_doc(STATE)
        state.setdefault("operations", [])
        state.setdefault("seq", 0)
        state.setdefault("keys", {})
        return state

    def _next_fault(self, op: str) -> str | None:
        for i, (fault_op, fault) in enumerate(self._faults):
            if fault_op == op:
                del self._faults[i]
                return fault
        return None

    def _call(self, op: str, payload: dict[str, Any], idempotency_key: str | None) -> dict[str, Any]:
        fault = self._next_fault(op)
        if fault == "timeout":
            raise GatewayTimeout(f"{op}: timed out")
        if fault == "decline":
            raise GatewayDeclined(f"{op}: declined by processor")

        state = self._state()
        if idempotency_key and idempotency_key in state["keys"]:
            # Replay: same key, same answer, nothing new happens.
            result = dict(state["keys"][idempotency_key])
            if fault == "lost":
                raise GatewayTimeout(f"{op}: response lost")
            return result

        state["seq"] += 1
        result = {
            "op": op,
            "ref": f"gw_{op[:2]}_{state['seq']:05d}",
            "status": "succeeded",
            "created_at": clock.now_iso(),
            **payload,
        }
        state["operations"].append(result)
        if idempotency_key:
            state["keys"][idempotency_key] = result
        self.store.save_doc(STATE, state)
        if fault == "lost":
            raise GatewayTimeout(f"{op}: response lost")
        return dict(result)
