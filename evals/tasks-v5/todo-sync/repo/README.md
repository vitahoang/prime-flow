# tickoff

An offline-first todo library, with a small CLI on top. It is what my todo
app on the phone and the laptop runs on.

Each device keeps a **replica**: a JSON file with that device's copy of the
tasks and a **change log** of every change made on it. Nothing needs a
network to work. Sync between devices is the next step (see
`docs/sync-notes.md`); for now the hub in `tickoff/hub.py` is an in-memory
stub.

## Tasks

A task has `title`, `done`, `due` (ISO date or none), `list` (default
`inbox`) and `order`. Tasks are shown by `order` within their list; `order`
is a whole number kept contiguous per list (1, 2, 3, ...).

```python
from tickoff import Replica

r = Replica("laptop")
t = r.add_task("Buy stamps", list="errands", due="2026-11-02")
r.add_task("Call the bank", list="errands", position=0)   # goes on top
r.complete(t.id)
r.list_tasks("errands")
r.save("~/.tickoff/laptop.json")
```

All changes go through `Replica` methods (`add_task`, `edit_task`,
`complete`, `reopen`, `delete_task`, `move_task`). Each one appends a
`Change` to `replica.log` with the device id, a Lamport counter and the wall
time. Device clocks are set from the network, so wall times can be compared
between devices.

## CLI

```
python -m tickoff add Buy stamps --list errands --due fri
python -m tickoff ls
python -m tickoff done <id-prefix or title>
python -m tickoff mv <task> 0
python -m tickoff agenda
python -m tickoff export
```

`--device` (or `$TICKOFF_DEVICE`) picks the replica, stored in
`$TICKOFF_HOME` (default `~/.tickoff`).

## Layout

- `tickoff/models.py` — Task and field validation
- `tickoff/replica.py` — the replica and all local changes
- `tickoff/changelog.py`, `tickoff/clock.py` — the log, Lamport and wall clocks
- `tickoff/storage.py` — replica files (format 2; format 1 is upgraded)
- `tickoff/hub.py` — in-memory hub stub
- `tickoff/due.py`, `query.py`, `lists.py`, `export.py` — helpers
- `samples/` — real replicas from my phone and laptop, trimmed

## Tests

`python -m pytest`
