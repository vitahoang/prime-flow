import csv
from datetime import date

from meterly import export


def test_export_events(store, tmp_path):
    path = tmp_path / "out.csv"
    n = export.export_events(store, "cus_pinecrest", date(2026, 9, 1), date(2026, 10, 1), path)
    rows = list(csv.DictReader(path.open()))
    assert n == len(rows) == 3
    assert rows[0]["units"] == "412"
