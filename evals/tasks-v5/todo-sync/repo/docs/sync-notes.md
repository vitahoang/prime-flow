# Sync notes

Working notes for adding sync. Nothing here is built yet except the hub stub
(`tickoff/hub.py`) and the change log.

## Shape

- Every device keeps its own replica and its own change log. A change is
  `{device, lamport, wall, task, kind, fields}`; `device:lamport` is unique.
- Devices talk only to the hub. They push their own changes and pull
  everyone else's. The hub just stores changes in arrival order and never
  merges anything.
- Merge plan (2025, written before the clock bug below):
  - when two devices change the same task, the newest whole task wins, the
    same way `updated_at` shows the last edit;
  - a delete is final: once a task is deleted on any device it stays deleted
    (tombstone), like the old app did;
  - if two tasks end up at the same place in a list, the higher device id
    goes first, the same tie-break as below.

## device_clock_skew

Don't trust wall times across devices. Lena's phone has been running about
two hours behind since the timezone-settings bug (#41), and the sample
replicas in `samples/` show it: the phone's edits after the copy carry wall
times from before the laptop's last edit. Laptops drift less, but they
drift.

`wall` is fine for showing "edited 5 min ago" on the device that made the
edit. It must not decide which of two devices' changes came last.

Use the Lamport counter instead. Every change already gets one
(`Replica._record`), and `LamportClock.observe()` is there so a device can
move its counter past anything it receives. When two changes have the same
counter, the higher device id wins (compare the ids as plain strings), so
every device picks the same one.

## Hub stub

- `push`, `pull(since)`, `stored()`, `head(device)`.
- `drop_after(n)` fakes a dropped connection partway through a push.

## Open questions

- How much log to keep once the hub has it.
