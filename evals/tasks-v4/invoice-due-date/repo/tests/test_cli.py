def test_list(run):
    code, out, _ = run("list")
    assert code == 0
    assert "INV-1" in out and "OPEN" in out
    assert "INV-0900" in out and "OVERDUE" in out


def test_show(run):
    code, out, _ = run("show", "INV-1")
    assert code == 0
    assert "Due:      1 Oct 2026" in out


def test_show_html(run):
    code, out, _ = run("show", "INV-1", "--html")
    assert code == 0 and out.startswith("<!doctype html>")


def test_show_unknown(run):
    code, _, err = run("show", "INV-404")
    assert code == 2 and "No invoice" in err


def test_customers(run):
    code, out, _ = run("customers")
    assert "Asia/Singapore" in out


def test_statement(run):
    code, out, _ = run("statement", "C1")
    assert code == 0 and "Total outstanding" in out


def test_reminders(run):
    code, out, _ = run("reminders")
    assert code == 0
    assert out.splitlines()[0] == "2026-09-17  INV-2  Lim & Tan Pte Ltd  1 day before due (2026-09-18)"


def test_reminders_on(run):
    _, out, _ = run("reminders", "--on", "2026-10-01")
    assert out.strip() == "2026-10-01  INV-3  Brightline Media  1 day before due (2026-10-02)"


def test_reminders_none(run):
    _, out, _ = run("reminders", "--on", "2026-12-25")
    assert out.strip() == "No reminders scheduled."


def test_overdue(run):
    code, out, _ = run("overdue")
    assert code == 0
    assert out.strip().startswith("INV-0900  Northgate Books  due 2025-12-03")
    assert "late fee GBP 10.00" in out


def test_overdue_later(run):
    _, out, _ = run("overdue", now="2026-10-05T12:00:00Z")
    assert "INV-1  Northgate Books  due 2026-10-01  4 days late" in out
    assert "late fee GBP 24.00" in out


def test_nothing_overdue(run):
    _, out, _ = run("overdue", now="2025-11-10T12:00:00Z")
    assert out.strip() == "No overdue invoices."


def test_data_dir_option(run, data_dir, tmp_path, monkeypatch):
    monkeypatch.delenv("INVOICER_DATA_DIR")
    code, out, _ = run("--data-dir", str(data_dir), "show", "INV-2")
    assert code == 0 and "INVOICE INV-2" in out


def test_reminders_send_logs_them(run, data_dir):
    _, out, _ = run("reminders", "--send", now="2026-09-17T03:00:00Z")
    assert out.strip() == "sent  2026-09-17  INV-2  Lim & Tan Pte Ltd  1 day before due (2026-09-18)"
    _, out, _ = run("reminders", "--send", now="2026-09-17T05:00:00Z")
    assert out.strip() == "No reminders to send today."
    assert (data_dir / "reminders_sent.json").exists()


def test_overdue_records_the_fee(run, data_dir):
    run("overdue", now="2026-10-05T12:00:00Z")
    assert "INV-1" in (data_dir / "fees.json").read_text()
    _, out, _ = run("show", "INV-1", now="2026-10-09T12:00:00Z")
    assert "GBP 24.00" in out  # the fee charged on the 5th, not recomputed
