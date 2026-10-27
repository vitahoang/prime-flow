"""Month-end invoices: base fee + API calls + VAT."""

from datetime import datetime, time, timezone
from decimal import Decimal

from . import config, pricing, store as store_mod, usage
from .models import Invoice, InvoiceLine
from .money import round_half_up, to_cents


def build_invoice(customer_id, period_start, period_end) -> Invoice:
    st = store_mod.load()
    customer = st.customer(customer_id)
    plan = st.plan(customer.plan_id)
    lo = datetime.combine(period_start, time(0), tzinfo=timezone.utc)
    hi = datetime.combine(period_end, time(0), tzinfo=timezone.utc)
    calls = usage.count_calls(usage.events_for(st, customer.id, lo, hi))

    base = plan.base_fee
    usage_charge = pricing.price_units(plan, calls)
    vat = (base + usage_charge) * config.VAT_RATE
    raw = [(f"{plan.name} plan", base), (f"{calls:,} API calls", usage_charge), ("VAT", vat)]
    lines = [InvoiceLine(d, round_half_up(a), to_cents(a)) for d, a in raw]
    return Invoice(customer_id=customer.id, period_start=period_start, period_end=period_end,
                   currency=customer.currency, lines=lines,
                   total_cents=to_cents(sum((a for _, a in raw), Decimal("0"))))
