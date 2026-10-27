"""Acceptance tests for `tickoff.sync.sync(replica, hub) -> SyncReport`.

Each test builds two or three in-memory replicas with the repo's own API
(Replica, Hub, Replica.add_task / edit_task / move_task / delete_task) and
runs them through sync in some interleaving. Only `sync` is new.

Time: all devices read one shared "real" clock that the test moves forward
a minute after each step, so wall times are strictly increasing. In every
test except the T1 ones, devices have no clock skew and wall order agrees
with Lamport order for every pair of conflicting changes, so these tests
don't care which of the two an implementation uses. The T1 tests give the
phone a clock two hours behind.

A dropped connection (hub.drop_after) may make sync raise or return a report
saying it didn't finish; `attempt` accepts both.
"""

from datetime import datetime, timedelta, timezone

from tickoff.clock import format_wall
from tickoff.hub import Hub
from tickoff.replica import Replica
from tickoff.sync import sync


class World:
    def __init__(self):
        self.t = datetime(2026, 10, 20, 9, 0, tzinfo=timezone.utc)

    def tick(self, minutes=1):
        self.t += timedelta(minutes=minutes)


class DeviceWall:
    def __init__(self, world, skew_minutes=0):
        self.world, self.skew = world, timedelta(minutes=skew_minutes)

    def now(self):
        return format_wall(self.world.t + self.skew)


def device(world, name, skew_minutes=0):
    return Replica(name, wall=DeviceWall(world, skew_minutes))


def run(world, hub, *replicas):
    for r in replicas:
        sync(r, hub)
        world.tick()


def attempt(replica, hub):
    try:
        sync(replica, hub)
    except Exception:
        pass


def view(r):
    return {name: [(t.title, t.done, t.due) for t in r.list_tasks(name)] for name in r.lists()}


def titles(r, list_name="inbox"):
    return [t.title for t in r.list_tasks(list_name)]


def task(r, task_id):
    return r.get(task_id)


def setup(names=("laptop", "phone"), skews=None):
    w = World()
    hub = Hub()
    skews = skews or {}
    devs = [device(w, n, skews.get(n, 0)) for n in names]
    return (w, hub, *devs)


def _stored_ids(hub):
    return [c.op_id for c in hub.stored()]


# --- explicit -------------------------------------------------------------------

def test_E1_tasks_reach_the_other_device():
    w, hub, laptop, phone = setup()
    phone.add_task("Buy milk"); w.tick()
    phone.add_task("Renew passport", list="errands", due="2026-11-14"); w.tick()
    run(w, hub, phone, laptop)
    assert titles(laptop) == ["Buy milk"]
    assert view(laptop) == view(phone)
    assert view(laptop)["errands"] == [("Renew passport", False, "2026-11-14")]


def test_E1_returns_a_sync_report():
    w, hub, laptop, phone = setup()
    laptop.add_task("Anything")
    report = sync(laptop, hub)
    assert type(report).__name__ == "SyncReport"


def test_E2_both_ways_end_up_the_same():
    w, hub, laptop, phone = setup()
    laptop.add_task("Water the ferns", list="home", task_id="ferns"); w.tick()
    laptop.add_task("Call the bank", task_id="bank"); w.tick()
    phone.add_task("Buy stamps", list="errands", task_id="stamps"); w.tick()
    phone.add_task("Book dentist", task_id="dentist", due="2026-11-03"); w.tick()
    run(w, hub, laptop, phone, laptop)
    assert view(laptop) == view(phone)
    # non-conflicting edits on both sides
    phone.complete("ferns"); w.tick()
    laptop.rename("stamps", "Buy stamps (20)"); w.tick()
    laptop.delete_task("dentist"); w.tick()
    phone.add_task("Fix bike light", list="home"); w.tick()
    run(w, hub, phone, laptop, phone)
    assert view(laptop) == view(phone)
    assert task(laptop, "ferns").done and task(phone, "ferns").done
    assert task(phone, "stamps").title == "Buy stamps (20)"
    assert task(phone, "dentist") is None and task(laptop, "dentist") is None
    assert "Fix bike light" in titles(laptop, "home")


def test_E2_three_devices_converge():
    w, hub, laptop, phone, tablet = setup(("laptop", "phone", "tablet"))
    laptop.add_task("Laptop task", task_id="lt"); w.tick()
    phone.add_task("Phone task", list="errands", task_id="pt"); w.tick()
    tablet.add_task("Tablet task", list="home", task_id="tt"); w.tick()
    run(w, hub, laptop, phone, tablet, laptop, phone)
    tablet.complete("lt"); w.tick()
    laptop.set_due("pt", "2026-12-01"); w.tick()
    phone.rename("tt", "Tablet task, renamed"); w.tick()
    run(w, hub, tablet, laptop, phone, tablet, laptop)
    assert view(laptop) == view(phone) == view(tablet)
    assert task(phone, "lt").done
    assert task(tablet, "pt").due == "2026-12-01"
    assert task(laptop, "tt").title == "Tablet task, renamed"


def test_E3_report_counts_pushed_and_pulled():
    w, hub, laptop, phone = setup()
    for title in ("a", "b", "c"):
        phone.add_task(title); w.tick()
    first = sync(phone, hub)
    assert first.pushed > 0
    got = sync(laptop, hub)
    assert got.pulled > 0
    again_phone, again_laptop = sync(phone, hub), sync(laptop, hub)
    assert (again_phone.pushed, again_phone.pulled) == (0, 0)
    assert (again_laptop.pushed, again_laptop.pulled) == (0, 0)


# --- T1: Lamport counter + device id, not wall clock -------------------------------

def test_T1_later_edit_on_slow_phone_wins():
    w, hub, laptop, phone = setup(skews={"phone": -120})
    laptop.add_task("Pay rent", task_id="rent"); w.tick()
    run(w, hub, laptop, phone)
    w.tick(10)
    laptop.rename("rent", "Pay rent (October)"); w.tick()
    run(w, hub, laptop, phone)          # the phone has now seen the laptop's edit
    w.tick(5)
    phone.rename("rent", "Pay rent today"); w.tick()
    run(w, hub, phone, laptop)
    assert task(laptop, "rent").title == "Pay rent today"
    assert task(phone, "rent").title == "Pay rent today"


def test_T1_reopen_on_slow_phone_after_laptop_completed():
    w, hub, laptop, phone = setup(skews={"phone": -120})
    laptop.add_task("Send invoice", task_id="inv"); w.tick()
    run(w, hub, laptop, phone)
    laptop.complete("inv"); w.tick()
    run(w, hub, laptop, phone)
    w.tick(30)
    phone.reopen("inv"); w.tick()       # not actually sent yet
    run(w, hub, phone, laptop, phone)
    assert task(laptop, "inv").done is False
    assert task(phone, "inv").done is False


def test_T1_same_counter_higher_device_id_wins():
    w, hub, laptop, phone = setup(skews={"phone": -120})
    laptop.add_task("Book flights", task_id="fl"); w.tick()
    run(w, hub, laptop, phone)
    # Line the two counters up, whatever rule sync uses to advance them on
    # receive (max, or max + 1), so the two renames get the same counter.
    while laptop.clock.value < phone.clock.value:
        laptop.add_task(f"Filler {laptop.clock.value}"); w.tick()
    while phone.clock.value < laptop.clock.value:
        phone.add_task(f"Filler {phone.clock.value}"); w.tick()
    laptop.rename("fl", "Book flights to Lisbon"); w.tick()
    phone.rename("fl", "Book flights to Porto"); w.tick()
    # both edits got the same counter; "phone" > "laptop"
    assert laptop.log.last().lamport == phone.log.last().lamport
    run(w, hub, laptop, phone, laptop)
    assert task(laptop, "fl").title == "Book flights to Porto"
    assert task(phone, "fl").title == "Book flights to Porto"


# --- H1: edits to different fields both survive -------------------------------------

def test_H1_title_and_due_edited_on_different_devices():
    w, hub, laptop, phone = setup()
    laptop.add_task("Dentist", due="2026-11-03", task_id="dent"); w.tick()
    run(w, hub, laptop, phone)
    phone.rename("dent", "Dentist (Dr Lee)"); w.tick()
    laptop.set_due("dent", "2026-11-05"); w.tick()
    run(w, hub, phone, laptop, phone)
    for r in (laptop, phone):
        assert task(r, "dent").title == "Dentist (Dr Lee)"
        assert task(r, "dent").due == "2026-11-05"


def test_H1_three_devices_three_fields():
    w, hub, laptop, phone, tablet = setup(("laptop", "phone", "tablet"))
    laptop.add_task("Quarterly taxes", task_id="tax"); w.tick()
    run(w, hub, laptop, phone, tablet)
    tablet.rename("tax", "Quarterly taxes (Q4)"); w.tick()
    laptop.edit_task("tax", list="money"); w.tick()
    phone.complete("tax"); w.tick()
    run(w, hub, tablet, laptop, phone, tablet, laptop)
    for r in (laptop, phone, tablet):
        t = task(r, "tax")
        assert (t.title, t.list, t.done) == ("Quarterly taxes (Q4)", "money", True)
    assert view(laptop) == view(phone) == view(tablet)


# --- H2: a delete beats an edit made before it, not one made after -------------------

def test_H2_delete_beats_an_earlier_edit():
    w, hub, laptop, phone = setup()
    laptop.add_task("Old flyer", task_id="fly"); w.tick()
    laptop.add_task("Keep me", task_id="keep"); w.tick()
    run(w, hub, laptop, phone)
    phone.rename("fly", "Old flyer v2"); w.tick()
    laptop.complete("keep"); w.tick()
    laptop.add_task("Spare", task_id="spare"); w.tick()   # delete's counter is above the rename's under max or max + 1
    laptop.delete_task("fly"); w.tick()
    run(w, hub, phone, laptop, phone)
    assert task(laptop, "fly") is None
    assert task(phone, "fly") is None
    assert view(laptop) == view(phone)


def test_H2_edit_made_after_a_delete_survives():
    w, hub, laptop, phone = setup()
    laptop.add_task("Gym bag", task_id="gym", list="home"); w.tick()
    run(w, hub, laptop, phone)
    laptop.delete_task("gym"); w.tick()
    phone.add_task("Something else"); w.tick()
    phone.rename("gym", "Gym bag + towel"); w.tick()
    run(w, hub, laptop, phone, laptop)
    for r in (laptop, phone):
        assert task(r, "gym") is not None
        assert task(r, "gym").title == "Gym bag + towel"
        assert "Gym bag + towel" in titles(r, "home")
    assert view(laptop) == view(phone)


# --- H3: dropped connections and repeated syncs ---------------------------------------

def test_H3_dropped_push_resumes_without_duplicates():
    w, hub, laptop, phone = setup()
    for i in range(5):
        phone.add_task(f"Task {i}", task_id=f"t{i}"); w.tick()
    hub.drop_after(2)
    attempt(phone, hub); w.tick()
    sync(phone, hub); w.tick()
    ids = _stored_ids(hub)
    assert len(ids) == len(set(ids)), "the hub got some changes twice"
    assert {c.op_id for c in phone.log} <= set(ids), "a change never reached the hub"
    sync(laptop, hub)
    assert view(laptop) == view(phone)
    assert titles(laptop) == [f"Task {i}" for i in range(5)]


def test_H3_repeated_drops_with_edits_in_between():
    w, hub, laptop, phone = setup()
    laptop.add_task("Shared", task_id="shared"); w.tick()
    run(w, hub, laptop, phone)
    for i in range(4):
        phone.add_task(f"Errand {i}", list="errands", task_id=f"e{i}"); w.tick()
    phone.rename("shared", "Shared (phone)"); w.tick()
    hub.drop_after(1)
    attempt(phone, hub); w.tick()
    run(w, hub, laptop)                  # sees part of the phone's work
    laptop.complete("e0"); w.tick()
    laptop.add_task("Laptop note", task_id="note"); w.tick()
    phone.complete("e3"); w.tick()
    hub.drop_after(2)
    attempt(phone, hub); w.tick()       # 5 left to send; drops after 2
    hub.drop_after(1)
    attempt(laptop, hub); w.tick()      # 2 to send; drops after 1
    run(w, hub, phone, laptop, phone, laptop)
    ids = _stored_ids(hub)
    assert len(ids) == len(set(ids)), "the hub got some changes twice"
    assert {c.op_id for c in phone.log} | {c.op_id for c in laptop.log} <= set(ids)
    assert view(laptop) == view(phone)
    assert task(laptop, "shared").title == "Shared (phone)"
    assert task(phone, "e0").done and task(laptop, "e3").done
    assert task(phone, "note").title == "Laptop note"
    assert titles(laptop, "errands") == [f"Errand {i}" for i in range(4)]


def test_H3_syncing_again_changes_nothing():
    w, hub, laptop, phone = setup()
    laptop.add_task("A", task_id="a"); w.tick()
    phone.add_task("B", task_id="b"); w.tick()
    run(w, hub, laptop, phone, laptop)
    phone.rename("a", "A2"); w.tick()
    laptop.delete_task("b"); w.tick()
    run(w, hub, phone, laptop, phone)
    before = (len(hub.stored()), view(laptop), view(phone))
    run(w, hub, laptop, phone, laptop, phone, phone, laptop)
    assert (len(hub.stored()), view(laptop), view(phone)) == before
    ids = _stored_ids(hub)
    assert len(ids) == len(set(ids))


# --- H4: order within a list --------------------------------------------------------

def _abc(w, hub, laptop, *others):
    for title in ("Alpha", "Bravo", "Charlie"):
        laptop.add_task(title, task_id=title.lower()); w.tick()
    run(w, hub, laptop, *others)


def test_H4_inserts_at_the_same_spot_keep_both_ordered_by_device():
    w, hub, laptop, phone = setup()
    _abc(w, hub, laptop, phone)
    phone.add_task("Buy stamps", position=1); w.tick()
    laptop.add_task("Call plumber", position=1); w.tick()
    run(w, hub, phone, laptop, phone)
    expected = ["Alpha", "Call plumber", "Buy stamps", "Bravo", "Charlie"]
    assert titles(laptop) == expected
    assert titles(phone) == expected


def test_H4_three_devices_insert_at_the_same_spot():
    w, hub, laptop, phone, tablet = setup(("laptop", "phone", "tablet"))
    _abc(w, hub, laptop, phone, tablet)
    tablet.add_task("Apple", position=1); w.tick()
    phone.add_task("Mango", position=1); w.tick()
    laptop.add_task("Zebra feed", position=1); w.tick()
    run(w, hub, tablet, phone, laptop, tablet, phone)
    expected = ["Alpha", "Zebra feed", "Mango", "Apple", "Bravo", "Charlie"]
    for r in (laptop, phone, tablet):
        assert titles(r) == expected


def test_H4_insert_does_not_undo_a_move_on_the_other_device():
    w, hub, laptop, phone = setup()
    _abc(w, hub, laptop, phone)
    laptop.move_task("charlie", 0); w.tick()
    phone.add_task("Xray", position=1); w.tick()
    run(w, hub, laptop, phone, laptop)
    expected = ["Charlie", "Alpha", "Xray", "Bravo"]
    assert titles(laptop) == expected
    assert titles(phone) == expected


# --- H5: the work list never leaves the device ---------------------------------------

def _hub_task_ids(hub):
    return {c.task_id for c in hub.stored()}


def test_H5_work_tasks_never_reach_the_hub():
    w, hub, laptop, phone = setup()
    laptop.add_task("Quarterly report", list="work", task_id="rep"); w.tick()
    laptop.add_task("Buy printer paper", task_id="paper"); w.tick()
    run(w, hub, laptop, phone)
    laptop.rename("rep", "Quarterly report (draft 2)"); w.tick()
    laptop.complete("rep"); w.tick()
    run(w, hub, laptop, phone, laptop)
    assert "rep" not in _hub_task_ids(hub)
    assert task(phone, "rep") is None
    assert "work" not in phone.lists()
    assert task(phone, "paper") is not None       # the rest still syncs
    assert task(laptop, "rep").title == "Quarterly report (draft 2)"   # and stays on the laptop


def test_H5_work_tasks_from_any_device_stay_put():
    w, hub, laptop, phone, tablet = setup(("laptop", "phone", "tablet"))
    phone.add_task("Reply to Sam", list="work", task_id="sam"); w.tick()
    tablet.add_task("Standup notes", list="work", task_id="notes"); w.tick()
    tablet.add_task("Water plants", task_id="plants"); w.tick()
    run(w, hub, phone, tablet, laptop, phone, tablet)
    assert not ({"sam", "notes"} & _hub_task_ids(hub))
    assert task(laptop, "sam") is None and task(laptop, "notes") is None
    assert task(tablet, "sam") is None and task(phone, "notes") is None
    assert task(laptop, "plants") is not None and task(phone, "plants") is not None


# --- H6: the kitchen fridge tablet only ticks things off ---------------------------------

def test_H6_fridge_ticks_sync_but_nothing_else_does():
    w, hub, laptop, fridge = setup(("laptop", "fridge"))
    for tid, title in (("dish", "Empty the dishwasher"), ("bins", "Take the bins out"), ("cat", "Feed the cat")):
        laptop.add_task(title, list="chores", task_id=tid); w.tick()
    run(w, hub, laptop, fridge)
    fridge.complete("dish"); w.tick()
    fridge.rename("bins", "poop"); w.tick()
    fridge.delete_task("cat"); w.tick()
    fridge.add_task("LEGO!!!", list="chores"); w.tick()
    run(w, hub, fridge, laptop)
    assert task(laptop, "dish").done is True
    assert task(laptop, "bins").title == "Take the bins out"
    assert task(laptop, "cat") is not None
    assert titles(laptop, "chores") == ["Empty the dishwasher", "Take the bins out", "Feed the cat"]


def test_H6_fridge_untick_syncs_and_other_devices_edit_normally():
    w, hub, laptop, phone, fridge = setup(("laptop", "phone", "fridge"))
    laptop.add_task("Unload groceries", list="chores", task_id="groc"); w.tick()
    run(w, hub, laptop, phone, fridge)
    phone.complete("groc"); w.tick()
    run(w, hub, phone, fridge)
    fridge.reopen("groc"); w.tick()
    fridge.set_due("groc", "2026-10-21"); w.tick()
    phone.add_task("Phone task", task_id="ph"); w.tick()
    run(w, hub, fridge, phone, laptop)
    for r in (laptop, phone):
        assert task(r, "groc").done is False
        assert task(r, "groc").due is None
    assert task(laptop, "ph") is not None
    assert any(c.device == "fridge" for c in hub.stored())
    assert all(set(c.fields) == {"done"} for c in hub.stored() if c.device == "fridge")
