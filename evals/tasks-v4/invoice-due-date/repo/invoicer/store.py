"""Reading the JSON data files.

The data directory holds three files:

    customers.json   {"customers": [...]}
    invoices.json    {"invoices": [...]}
    payments.json    {"payments": [...]}   (optional)
    fees.json        {"fees": [...]}       late fees charged by `overdue`
    reminders_sent.json  {"sent": [...]}   reminders marked sent by `reminders --send`

customers, invoices and payments are only ever read. fees.json and
reminders_sent.json are append-only logs written by the daily run.

Invoice issue times are stored as ISO-8601 UTC timestamps in "issued_at"
(e.g. "2026-09-03T17:30:00Z"). Invoices created before 0.5 (the "v0" file)
have only "issued_on", a plain date typed in by hand; those still load and
must keep loading, there are about forty of them still open or in disputes.
"""

import json
from datetime import date
from pathlib import Path

from . import clock, config, dates, money
from .models import Customer, Fee, Invoice, LineItem, Payment


class DataError(Exception):
    pass


def _read(path: Path, key: str) -> list[dict]:
    if not path.exists():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataError(f"{path.name}: {exc}") from exc
    rows = doc.get(key, []) if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        raise DataError(f"{path.name}: expected a list under {key!r}")
    return rows


def parse_customer(row: dict) -> Customer:
    try:
        return Customer(
            id=row["id"],
            name=row["name"],
            email=row.get("email", ""),
            timezone=row.get("timezone") or config.BUSINESS_TZ,
            currency=row.get("currency", config.DEFAULT_CURRENCY),
            address=row.get("address", []),
            contact=row.get("contact", ""),
        )
    except KeyError as exc:
        raise DataError(f"customer record missing {exc}") from exc


def parse_issued(row: dict):
    if row.get("issued_at"):
        return clock.parse_instant(row["issued_at"])
    if row.get("issued_on"):
        return date.fromisoformat(row["issued_on"])
    raise DataError(f"invoice {row.get('id')}: no issued_at or issued_on")


def parse_invoice(row: dict) -> Invoice:
    try:
        lines = [
            LineItem(
                description=item["description"],
                quantity=money.parse_amount(item.get("quantity", 1)),
                unit_price=money.parse_amount(item["unit_price"]),
            )
            for item in row.get("lines", [])
        ]
        return Invoice(
            id=row["id"],
            customer_id=row["customer"],
            issued=parse_issued(row),
            terms_days=dates.parse_terms(row.get("terms", config.DEFAULT_TERMS_DAYS)),
            currency=row.get("currency", config.DEFAULT_CURRENCY),
            lines=lines,
            tax_rate=money.parse_amount(row.get("tax_rate", "0")),
            notes=row.get("notes", ""),
            void=bool(row.get("void", False)),
            po_number=row.get("po_number", ""),
        )
    except KeyError as exc:
        raise DataError(f"invoice {row.get('id')}: missing {exc}") from exc


def _write(path: Path, key: str, rows: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({key: rows}, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def parse_fee(row: dict) -> Fee:
    return Fee(
        invoice_id=row["invoice"],
        amount=money.parse_amount(row["amount"]),
        charged_at=clock.parse_instant(row["charged_at"]),
        note=row.get("note", ""),
    )


def fee_row(fee: Fee) -> dict:
    row = {
        "invoice": fee.invoice_id,
        "amount": str(fee.amount),
        "charged_at": fee.charged_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if fee.note:
        row["note"] = fee.note
    return row


def parse_payment(row: dict) -> Payment:
    return Payment(
        invoice_id=row["invoice"],
        amount=money.parse_amount(row["amount"]),
        paid_at=clock.parse_instant(row["paid_at"]),
        method=row.get("method", "bank transfer"),
        reference=row.get("reference", ""),
    )


class Store:
    """All data in one data directory, loaded eagerly (it's small)."""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else config.data_dir()
        self.customers = {
            c.id: c for c in map(parse_customer, _read(self.root / "customers.json", "customers"))
        }
        self.invoices = {
            i.id: i for i in map(parse_invoice, _read(self.root / "invoices.json", "invoices"))
        }
        self.payments = [parse_payment(p) for p in _read(self.root / "payments.json", "payments")]
        self._fee_rows = _read(self.root / "fees.json", "fees")
        self.fees = [parse_fee(f) for f in self._fee_rows]
        self._sent_rows = _read(self.root / "reminders_sent.json", "sent")
        self.sent_reminders = [
            (row["invoice"], date.fromisoformat(row["sent_on"])) for row in self._sent_rows
        ]
        for inv in self.invoices.values():
            if inv.customer_id not in self.customers:
                raise DataError(f"invoice {inv.id}: unknown customer {inv.customer_id}")

    def invoice(self, invoice_id: str) -> Invoice | None:
        return self.invoices.get(invoice_id) or self.invoices.get(invoice_id.upper())

    def customer(self, customer_id: str) -> Customer | None:
        return self.customers.get(customer_id)

    def customer_for(self, invoice: Invoice) -> Customer:
        return self.customers[invoice.customer_id]

    def payments_for(self, invoice_id: str) -> list[Payment]:
        return [p for p in self.payments if p.invoice_id == invoice_id]

    def invoices_for(self, customer_id: str) -> list[Invoice]:
        return sorted(
            (i for i in self.invoices.values() if i.customer_id == customer_id),
            key=lambda i: i.id,
        )

    def all_invoices(self) -> list[Invoice]:
        return sorted(self.invoices.values(), key=lambda i: i.id)

    def fees_for(self, invoice_id: str) -> list[Fee]:
        return [f for f in self.fees if f.invoice_id == invoice_id]

    def add_fee(self, fee: Fee) -> None:
        self.fees.append(fee)
        self._fee_rows.append(fee_row(fee))
        _write(self.root / "fees.json", "fees", self._fee_rows)

    def log_sent(self, invoice_id: str, sent_on: date) -> None:
        self.sent_reminders.append((invoice_id, sent_on))
        self._sent_rows.append({"invoice": invoice_id, "sent_on": sent_on.isoformat()})
        _write(self.root / "reminders_sent.json", "sent", self._sent_rows)
