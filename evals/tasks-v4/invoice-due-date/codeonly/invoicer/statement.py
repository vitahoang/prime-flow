"""Customer statements: every invoice for one customer, with balances and aging."""

from datetime import datetime
from decimal import Decimal

from . import billing, clock, config, dates, money, utils
from .models import Customer

BUCKETS = ("current", "1-30", "31-60", "60+")


def statement_rows(store, customer: Customer, now: datetime) -> list[dict]:
    today = clock.local_today(customer.timezone, now)
    rows = []
    for inv in store.invoices_for(customer.id):
        if inv.void:
            continue
        due = billing.due_date(inv, customer)
        bal = billing.balance(inv, store.payments)
        late = dates.days_late(due, today) if billing.is_overdue(inv, customer, store.payments, now) else 0
        rows.append(
            {
                "invoice": inv,
                "issued": dates.to_calendar_date(inv.issued, customer.timezone),
                "due": due,
                "total": inv.total,
                "balance": bal,
                "fee": billing.late_fee(inv, customer, store.payments, now, store.fees),
                "status": billing.status(inv, customer, store.payments, now),
                "bucket": dates.aging_bucket(late) if bal > 0 else "",
            }
        )
    return rows


def aging(rows) -> dict[str, Decimal]:
    totals = {b: Decimal("0") for b in BUCKETS}
    for r in rows:
        if r["bucket"]:
            totals[r["bucket"]] += r["balance"] + r["fee"]
    return totals


def render_statement(store, customer: Customer, now: datetime) -> str:
    rows = statement_rows(store, customer, now)
    cur = customer.currency
    out = [
        f"{config.BUSINESS_NAME} - statement for {customer.name}",
        f"As of {utils.format_date(clock.local_today(customer.timezone, now))}",
        "",
    ]
    table = [("Invoice", "Issued", "Due", "Total", "Balance", "Status")]
    for r in rows:
        table.append(
            (
                r["invoice"].id,
                utils.format_date(r["issued"], "short"),
                utils.format_date(r["due"], "short"),
                money.format_money(r["total"], cur),
                money.format_money(r["balance"] + r["fee"], cur),
                r["status"],
            )
        )
    out.extend(utils.table(table, [9, 8, 8, 14, 14, 8], ["left", "left", "left", "right", "right", "left"]))
    out.append("")
    ages = aging(rows)
    out.append("Aging:  " + "   ".join(f"{b}: {money.format_money(ages[b], cur)}" for b in BUCKETS))
    total = money.sum_money((r["balance"] + r["fee"] for r in rows), cur)
    out.append(f"Total outstanding: {money.format_money(total, cur)}")
    return "\n".join(out) + "\n"
