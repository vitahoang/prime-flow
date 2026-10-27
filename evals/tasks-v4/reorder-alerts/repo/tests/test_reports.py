from datetime import date

from stockroom.cli import main
from stockroom.reports import top_sellers, waste_report

START, END = date(2026, 10, 1), date(2026, 10, 15)


def test_waste_report(inv):
    lines = waste_report(inv, START, END)
    assert len(lines) == 1
    line = lines[0]
    assert (line.shop, line.sku, line.qty) == ("HAR", "OAT-1L", 2)
    assert line.cost == 3.0
    assert line.share_of_sales == 0.2


def test_waste_report_other_shop_empty(inv):
    assert waste_report(inv, START, END, shop="MKT") == []


def test_top_sellers(inv):
    assert top_sellers(inv, START, END) == [("CRD-SHEET", 30), ("OAT-1L", 15)]
    assert top_sellers(inv, START, END, limit=1) == [("CRD-SHEET", 30)]


def test_report_command(capsys, data_dir, today):
    assert main(["--data", str(data_dir), "report", "waste", "--days", "28"]) == 0
    out = capsys.readouterr().out
    assert "OAT-1L" in out and "20%" in out
