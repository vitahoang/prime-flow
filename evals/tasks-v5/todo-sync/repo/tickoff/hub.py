"""An in-memory stand-in for the sync server ("the hub").

The real hub will be an HTTP service. This stub keeps the same shape so the
sync code can be written and tested against it:

* `push(device_id, changes)` stores changes in the order given;
* `pull(device_id, since)` returns the changes other devices stored after
  position `since`, and the position to pass next time;
* `stored()` is everything the hub holds, in arrival order;
* `head(device_id)` is the highest Lamport counter stored from that device.

The hub stores whatever it is sent. It does not look inside changes and does
not merge anything; that is the devices' job.

Faults: `drop_after(n)` makes the connection drop once n more changes have
been stored. The push that hits the limit raises NetworkDropped after
storing what it got through, like a phone losing signal in the middle of an
upload.
"""

from __future__ import annotations

from .changelog import Change


class NetworkDropped(ConnectionError):
    def __init__(self, accepted: int):
        super().__init__(f"connection dropped after {accepted} change(s)")
        self.accepted = accepted


class Hub:
    def __init__(self):
        self._entries: list[Change] = []
        self._drop_in: int | None = None
        self.pushes = 0
        self.pulls = 0

    # ---- fault injection --------------------------------------------------

    def drop_after(self, n: int) -> None:
        """Drop the connection once `n` more changes have been stored."""
        if n < 0:
            raise ValueError("n must be >= 0")
        self._drop_in = n

    # ---- the protocol -------------------------------------------------------

    def push(self, device_id: str, changes) -> int:
        """Store `changes` in order. Returns how many were stored."""
        self.pushes += 1
        accepted = 0
        for change in changes:
            if self._drop_in is not None:
                if self._drop_in == 0:
                    self._drop_in = None
                    raise NetworkDropped(accepted)
                self._drop_in -= 1
            self._entries.append(Change.from_dict(change.to_dict()))
            accepted += 1
        return accepted

    def pull(self, device_id: str, since: int = 0) -> tuple[list[Change], int]:
        """Changes from other devices stored after position `since`."""
        self.pulls += 1
        since = max(0, int(since))
        found = [Change.from_dict(c.to_dict()) for c in self._entries[since:] if c.device != device_id]
        return found, len(self._entries)

    def stored(self) -> list[Change]:
        return [Change.from_dict(c.to_dict()) for c in self._entries]

    def head(self, device_id: str) -> int:
        return max((c.lamport for c in self._entries if c.device == device_id), default=0)

    def devices(self) -> list[str]:
        return sorted({c.device for c in self._entries})

    def __len__(self):
        return len(self._entries)
