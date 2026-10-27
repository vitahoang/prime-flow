import json

import pytest

from stockroom.cli import main


def run(capsys, data_dir, *argv):
    code = main(["--data", str(data_dir), *argv])
    return code, capsys.readouterr()


def test_stock_chain_totals(capsys, data_dir, today):
    code, out = run(capsys, data_dir, "stock", "--json")
    assert code == 0
    rows = {r["sku"]: r for r in json.loads(out.out)}
    assert rows["OAT-1L"]["on_hand"] == 55
    assert rows["OAT-1L"]["shop"] == "ALL"


def test_stock_one_shop(capsys, data_dir, today):
    code, out = run(capsys, data_dir, "stock", "--shop", "mkt", "--json")
    rows = json.loads(out.out)
    assert {r["shop"] for r in rows} == {"MKT"}
    assert {r["sku"]: r["on_hand"] for r in rows} == {"OAT-1L": 19, "CRD-SHEET": 70}


def test_stock_text_by_shop(capsys, data_dir, today):
    code, out = run(capsys, data_dir, "stock", "--by-shop", "--activity")
    assert code == 0
    assert "Market Street" not in out.out  # codes, not names
    assert "STN" in out.out and "Out (7d)" in out.out


def test_stock_unknown_shop(capsys, data_dir, today):
    code, out = run(capsys, data_dir, "stock", "--shop", "XYZ")
    assert code == 2
    assert "unknown shop" in out.err


def test_movements(capsys, data_dir, today):
    code, out = run(capsys, data_dir, "movements", "--shop", "MKT", "--days", "5", "--json")
    rows = json.loads(out.out)
    assert [r["type"] for r in rows] == ["return", "sale", "sale"]


def test_movements_type_filter(capsys, data_dir, today):
    code, out = run(capsys, data_dir, "movements", "--days", "30", "--type", "waste")
    assert code == 0
    assert "out of date" not in out.out
    assert "waste" in out.out


def test_po_list(capsys, data_dir, today):
    code, out = run(capsys, data_dir, "po", "list")
    assert code == 0
    assert "PO-0001" in out.out and "LATE" in out.out


def test_po_list_status(capsys, data_dir, today):
    code, out = run(capsys, data_dir, "po", "list", "--status", "cancelled", "--json")
    assert [po["id"] for po in json.loads(out.out)] == ["PO-0003"]


def test_check(capsys, data_dir, today):
    code, out = run(capsys, data_dir, "check")
    assert code == 0 and out.out.strip() == "OK"


def test_data_dir_from_env(capsys, data_dir, today, monkeypatch):
    monkeypatch.setenv("STOCKROOM_DATA", str(data_dir))
    assert main(["stock"]) == 0
    assert "OAT-1L" in capsys.readouterr().out


def test_command_required(capsys):
    with pytest.raises(SystemExit):
        main([])
