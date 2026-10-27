import json

from ledger import storage
from ledger.cli import main


def test_add_and_list(home, capsys):
    assert main(["add", "1250.00", "Invoice 104", "--category", "income",
                 "--when", "2026-03-02T09:00"]) == 0
    assert main(["add", "-42.10", "Printer ink", "--when", "2026-03-03"]) == 0
    capsys.readouterr()
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "Invoice 104" in out and "$1,250.00" in out
    assert "-$42.10" in out
    assert "03/02/2026" in out


def test_add_stores_utc(home):
    main(["add", "10", "x", "--when", "2026-03-02T21:00"])
    (entry,) = storage.load_entries()
    assert entry.ts == "2026-03-03T03:00:00Z"
    assert entry.amount_cents == 1000


def test_balance_skips_archived(write_entries, capsys):
    write_entries([
        {"id": 1, "ts": "2026-03-01T15:00:00Z", "description": "a", "amount_cents": 10000},
        {"id": 2, "ts": "2026-03-02T15:00:00Z", "description": "b", "amount_cents": -2500},
        {"id": 3, "ts": "2026-03-03T15:00:00Z", "description": "c", "amount_cents": -999,
         "archived": True},
    ])
    assert main(["balance"]) == 0
    assert capsys.readouterr().out.strip() == "$75.00"


def test_balance_range(write_entries, capsys):
    write_entries([
        {"id": 1, "ts": "2026-02-10T15:00:00Z", "description": "a", "amount_cents": 100},
        {"id": 2, "ts": "2026-03-10T15:00:00Z", "description": "b", "amount_cents": 200},
    ])
    main(["balance", "--from", "2026-03-01"])
    assert capsys.readouterr().out.strip() == "$2.00"


def test_archive_and_undo(write_entries, home, capsys):
    write_entries([
        {"id": 1, "ts": "2026-03-01T15:00:00Z", "description": "a", "amount_cents": 100},
    ])
    assert main(["archive", "1"]) == 0
    assert storage.load_entries()[0].archived is True
    assert main(["archive", "1", "--undo"]) == 0
    assert storage.load_entries()[0].archived is False
    assert main(["archive", "9"]) == 1


def test_list_shows_archived_with_marker(write_entries, capsys):
    write_entries([
        {"id": 1, "ts": "2026-03-01T15:00:00Z", "description": "old", "amount_cents": 1,
         "archived": True},
    ])
    main(["list"])
    assert "[archived]" in capsys.readouterr().out
