"""Invoice rendering: plain text for the terminal and email, HTML for PDFs."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import billing, config, dates, money, utils
from .models import Customer, Invoice, Payment

WIDTH = 64


def invoice_facts(invoice: Invoice, customer: Customer, payments: list[Payment], now: datetime, fees=()) -> dict:
    """Everything both renderers show, worked out once."""
    # Show dates in the customer's own time zone, not UTC.
    issued_local = invoice.issued.astimezone(ZoneInfo(customer.timezone))
    issued_on = issued_local.date()
    due = issued_on + timedelta(days=invoice.terms_days)
    paid = billing.amount_paid(invoice, payments)
    fee = billing.late_fee(invoice, customer, payments, now, fees)
    return {
        "issued": issued_on,
        "due": due,
        "terms": dates.format_terms(invoice.terms_days),
        "status": billing.status(invoice, customer, payments, now),
        "subtotal": invoice.subtotal,
        "tax": invoice.tax,
        "total": invoice.total,
        "paid": paid,
        "late_fee": fee,
        "amount_due": billing.balance(invoice, payments) + fee,
    }


def render_text(invoice: Invoice, customer: Customer, payments: list[Payment], now: datetime, fees=()) -> str:
    f = invoice_facts(invoice, customer, payments, now, fees)
    cur = invoice.currency
    out = []
    out.append(f"{config.BUSINESS_NAME}".ljust(WIDTH - 20) + f"INVOICE {invoice.id}".rjust(20))
    out.append("=" * WIDTH)
    out.append(f"Bill to:  {customer.name}")
    for line in customer.address:
        out.append(f"          {line}")
    if customer.contact:
        out.append(f"Attn:     {customer.contact}")
    out.append("")
    out.append(f"Issued:   {utils.format_date(f['issued'])}")
    out.append(f"Terms:    {f['terms']}")
    out.append(f"Due:      {utils.format_date(f['due'])}")
    if invoice.po_number:
        out.append(f"PO:       {invoice.po_number}")
    out.append(f"Status:   {f['status']}")
    out.append("-" * WIDTH)
    rows = [("Description", "Qty", "Price", "Amount")]
    for item in invoice.lines:
        rows.append(
            (
                item.description,
                f"{item.quantity.normalize():f}",
                money.format_money(item.unit_price, cur),
                money.format_money(item.amount, cur),
            )
        )
    out.extend(utils.table(rows, [26, 5, 14, 14], ["left", "right", "right", "right"]))
    out.append("-" * WIDTH)

    def total_line(label, amount):
        out.append(f"{label:>48}  {money.format_money(amount, cur):>14}")

    total_line("Subtotal", f["subtotal"])
    if f["tax"]:
        total_line(f"Tax ({(invoice.tax_rate * 100).normalize():f}%)", f["tax"])
    total_line("Total", f["total"])
    if f["paid"]:
        total_line("Paid", -f["paid"])
    if f["late_fee"]:
        total_line("Late fee", f["late_fee"])
    total_line("Amount due", f["amount_due"])
    if invoice.notes:
        out.append("")
        out.append(invoice.notes)
    out.append("")
    out.append(f"Please pay by bank transfer quoting {invoice.id}. Questions: {config.BUSINESS_EMAIL}")
    return "\n".join(out) + "\n"


HTML_STYLE = """
body { font-family: Helvetica, Arial, sans-serif; color: #222; margin: 40px; }
h1 { font-size: 20px; margin: 0; }
table { border-collapse: collapse; width: 100%; margin-top: 24px; }
th, td { padding: 6px 8px; border-bottom: 1px solid #ddd; text-align: left; }
td.num, th.num { text-align: right; }
.facts td { border: none; padding: 2px 8px 2px 0; }
.status-OVERDUE { color: #b00020; font-weight: bold; }
.totals td { border: none; }
"""


def render_html(invoice: Invoice, customer: Customer, payments: list[Payment], now: datetime, fees=()) -> str:
    f = invoice_facts(invoice, customer, payments, now, fees)
    cur = invoice.currency
    esc = utils.html_escape
    m = money.format_money_html
    rows = "\n".join(
        f"<tr><td>{esc(i.description)}</td><td class=num>{i.quantity.normalize():f}</td>"
        f"<td class=num>{m(i.unit_price, cur)}</td><td class=num>{m(i.amount, cur)}</td></tr>"
        for i in invoice.lines
    )
    totals = [("Subtotal", f["subtotal"])]
    if f["tax"]:
        totals.append(("Tax", f["tax"]))
    totals.append(("Total", f["total"]))
    if f["paid"]:
        totals.append(("Paid", -f["paid"]))
    if f["late_fee"]:
        totals.append(("Late fee", f["late_fee"]))
    totals.append(("Amount due", f["amount_due"]))
    total_rows = "\n".join(
        f"<tr><td colspan=3 class=num>{label}</td><td class=num>{m(amount, cur)}</td></tr>"
        for label, amount in totals
    )
    address = "<br>".join(esc(a) for a in customer.address)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Invoice {esc(invoice.id)}</title>
<style>{HTML_STYLE}</style></head>
<body>
<h1>{esc(config.BUSINESS_NAME)} &mdash; Invoice {esc(invoice.id)}</h1>
<p><strong>{esc(customer.name)}</strong><br>{address}</p>
<table class=facts>
<tr><td>Issued</td><td>{utils.format_date(f['issued'])}</td></tr>
<tr><td>Terms</td><td>{f['terms']}</td></tr>
<tr><td>Due</td><td class=due>{utils.format_date(f['due'])}</td></tr>
<tr><td>Status</td><td class="status-{f['status']}">{f['status']}</td></tr>
</table>
<table>
<tr><th>Description</th><th class=num>Qty</th><th class=num>Price</th><th class=num>Amount</th></tr>
{rows}
</table>
<table class=totals>
{total_rows}
</table>
<p>{esc(invoice.notes)}</p>
</body></html>
"""
