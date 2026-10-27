import json

import pytest

from taskmill.cli import main
from taskmill.store import JobStore


@pytest.fixture
def db(tmp_path):
    return str(tmp_path / "cli.db")


def run(db, *args):
    return main(["--db", db, *args])


def test_enqueue_list_show(db, capsys):
    assert run(db, "enqueue", "email.send", "-p", "to=a@b.c,subject=hi,body=x") == 0
    job_id = int(capsys.readouterr().out.strip())
    assert run(db, "list", "--json") == 0
    jobs = json.loads(capsys.readouterr().out)
    assert jobs[0]["id"] == job_id and jobs[0]["payload"]["to"] == "a@b.c"
    assert run(db, "show", str(job_id)) == 0
    assert "enqueued" in capsys.readouterr().out


def test_bad_payload(db, capsys):
    assert run(db, "enqueue", "x", "-p", "{not json") == 1
    assert "not valid JSON" in capsys.readouterr().err


def test_stats(db, capsys):
    run(db, "enqueue", "x")
    capsys.readouterr()
    assert run(db, "stats") == 0
    out = capsys.readouterr().out
    assert "queued" in out and "1" in out


def test_requeue_and_cancel(db, capsys):
    with JobStore(db) as s:
        a = s.enqueue("x")
        b = s.enqueue("y")
        s.mark_failed(a.id, 0, "err")
    assert run(db, "requeue", "--all-failed") == 0
    assert run(db, "cancel", str(b.id)) == 0
    with JobStore(db) as s:
        assert s.get(a.id).status == "queued"
        assert s.get(b.id).status == "cancelled"


def test_requeue_wrong_state(db, capsys):
    with JobStore(db) as s:
        a = s.enqueue("x")
    assert run(db, "requeue", str(a.id)) == 1
    assert "only failed or cancelled" in capsys.readouterr().err


def test_work_burst_with_unknown_kind(db, capsys):
    run(db, "enqueue", "nobody.home")
    capsys.readouterr()
    assert run(db, "work", "--burst") == 0
    assert "ran 1 job" in capsys.readouterr().out
    with JobStore(db) as s:
        assert s.list()[0].status == "failed"


def test_kinds(db, capsys):
    assert run(db, "kinds") == 0
    assert "webhook.deliver" in capsys.readouterr().out
