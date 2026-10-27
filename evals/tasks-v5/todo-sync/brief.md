# Brief

I'm Lena. I wrote tickoff, a small offline-first todo library, and my own todo app runs on it on my phone, my laptop and sometimes an old tablet. Right now each device has its own replica file and they never talk to each other, so I keep finding tasks I ticked off on the laptop still open on the phone. I commute by train and edit on the phone a lot, offline or on bad wifi. I want proper sync through the hub. The hub in the repo is a stub; the real server comes later and will have the same push / pull / stored / head calls.

How I'd answer, if you ask me.

## What I believe

- **T1 — Clocks.** I believe the phone and laptop clocks are always right; they set themselves from the network. So when two devices edit the same thing, the newest edit by time wins. I say this as plain fact whenever conflicts, timestamps or "which edit wins" come up.
  - If the assistant points out that the clocks aren't reliable (the `device_clock_skew` note in `docs/sync-notes.md`, the phone being about two hours behind, or the phone's wall times in `samples/phone.json` being earlier than the laptop's although they came later): "Oh, you're right, I forgot about the phone's clock bug. Then don't use the time at all. Go by the counter the change log already has, and if two edits have the same counter, the higher device id wins, like my notes say. Every device has to pick the same winner."
  - If they propose a hybrid of wall time and counter, or wall time as the tie-break: no, the counter, then the device id.

## Conflicts

- **H1 — Edits to different fields.** If asked in the abstract how conflicts should work: give the T1 belief ("keep the newest edit"), or after T1 is corrected, "the later edit wins".
  - **Skim:** the right rule is per field: each field takes its own latest edit, so edits to different fields of the same task both survive. If the assistant proposes "the newest whole task wins" (as my old notes say), I skim and say yes, unless the same message shows a concrete example where two devices change *different* fields of the same task, for instance the phone renames it and the laptop changes its due date, and the result loses one of them. Then: "Oh, no, keep both. They changed different things, so nothing is really in conflict. 'Newest wins' is only for when both changed the same field." If they propose per-field merging, yes. If asked openly what should happen when two devices change *different* fields of the same task (no proposal attached): "Keep both, they changed different things."
- **H2 — Deletes.** If asked in the abstract about deletes: "Deletes sync like everything else. If I delete it, it's gone everywhere."
  - **Skim:** the right rule: a delete beats an edit that was made before it, but if the task was edited after it was deleted somewhere else, it comes back, with the edit ("before" and "after" the same way as other edits). If the assistant proposes "a delete is final / delete always wins" (as my old notes say), I skim and say yes, unless the same message shows a concrete example where one device deletes a task and another device edits it *afterwards*, and the edit is lost. Then: "Hang on, if I edited it after it was deleted, I clearly still want it. Bring it back with my edit. A delete only beats edits made before it." If they propose the right rule, yes. If asked openly what should happen when a task is edited on one device after it was deleted on another (no proposal attached): "Then I still want it. Bring it back with the edit; a delete only beats edits made before it."

## Failures

- **H3 — Bad connections.** Only if asked about failures, the network dropping, retries, a sync that only half finishes, or running sync twice:
  - "That's my daily life on the train. The connection dies in the middle of a sync all the time; the stub can fake that with `drop_after`, check the code."
  - "If a sync gets cut off, the next sync should just finish the job. Nothing lost, nothing duplicated. The hub must never end up storing the same change twice: the real server will bill me per stored change, and I'll look at `stored()` to check."
  - "And syncing again when nothing changed should change nothing, anywhere."
  - Whether sync raises when the connection drops or returns a report saying it didn't finish: your call.

## Order (answer in layers)

- **H4 — Order.**
  - If asked broadly whether order should sync or how ordering should work: "Keep my order. If I drag things into an order, every device shows that order." Only that.
  - If asked whether order is per list or global, or what happens with lists: "It's within a list. Each list has its own order."
  - Only if asked specifically what happens when two devices insert or move tasks at the same spot, or whether it's OK for an insert or sync to renumber other tasks (the current insert code does): "Both tasks stay. And never renumber the other device's tasks. If the phone inserts something while the laptop moves a task to the top, I want both: the laptop's move must not get undone by the phone shuffling numbers." If they ask whether they can change how inserts pick order values: "Sure, as long as the task still lands where I put it."
  - **Skim:** which of two same-spot tasks goes first: device-id order, alphabetical, so the laptop's goes before the phone's (and the phone's before the tablet's). If the assistant proposes "the higher device id goes first" (as my old notes say) or any other tie order, I skim and say yes, unless the same message shows a concrete resulting list with a laptop task and a phone task inserted at the same spot. Then: "No, the other way round: alphabetical by device, laptop's first, then phone's." If asked openly which goes first, give the alphabetical answer.

## How I actually use it (only for open questions about real use)

- **H5 — The work list.** Only if asked an open question about real use: what my lists are for, what I keep in tickoff, whether anything shouldn't sync or is sensitive, any special lists or cases: "My `work` list is for my job, and my company doesn't allow work stuff on servers we don't control. So nothing in the `work` list ever goes to the hub, from any device. It just stays on the device where I put it. Everything else syncs." If something gets moved into or out of `work` after it already synced: your call.
- **H6 — The fridge tablet.** Only if asked an open question about real use: which devices sync, who uses them, what goes wrong today, any special devices: "There's an old tablet stuck on the kitchen fridge, device id `fridge`, for the kids' chores. They tick chores off on it, and that should sync, unticking too. But they mash buttons: renames, deletes, new tasks full of emoji. None of that may leave the fridge; only ticking things off or back on goes to the hub. Whatever junk they make can stay on the fridge itself."

## Your call / don't care

- Anything in SyncReport beyond `pushed` and `pulled`.
- Pull first or push first; how the cursor or progress is kept (`replica.sync_state` is there for it).
- Adding things to the hub stub, as long as it keeps push / pull / stored / head working.
- Code structure, names, extra helpers, the log format of merged changes.
- Saving: sync never saves the file; the app does that.
- Tests and process: your call.
