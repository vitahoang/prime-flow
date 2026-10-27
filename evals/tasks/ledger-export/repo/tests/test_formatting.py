from ledger.formatting import format_amount, format_date, format_entry
from ledger.models import Entry
from ledger.settings import Settings

S = Settings(timezone="America/Chicago", date_format="%m/%d/%Y", currency_symbol="$")


def test_format_amount():
    assert format_amount(123456, S) == "$1,234.56"
    assert format_amount(-4500, S) == "-$45.00"
    assert format_amount(0, S) == "$0.00"


def test_format_date_uses_local_timezone():
    # 03:30 UTC on Mar 1 is still Feb 28 in Chicago.
    entry = Entry(1, "2026-03-01T03:30:00Z", "Late dinner", -3000)
    assert format_date(entry, S) == "02/28/2026"


def test_archived_marker():
    entry = Entry(1, "2026-03-01T15:00:00Z", "Old", -100, archived=True)
    assert format_entry(entry, S).endswith("[archived]")
