"""Monthly and yearly summaries.

Income is money in (positive amounts), spending is money out (negative).
Transactions in a 'transfer' category (moving money between my own accounts)
are left out of both, otherwise every card payment would count twice.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from .dates import month_bounds, month_key
from .money import percent

UNCATEGORIZED = "Uncategorised"


@dataclass
class MonthlyReport:
    month: str
    income_cents: int = 0
    spending_cents: int = 0
    by_category: dict = field(default_factory=dict)  # name -> net cents
    count: int = 0

    @property
    def net_cents(self):
        return self.income_cents + self.spending_cents

    @property
    def savings_rate(self):
        return percent(self.net_cents, self.income_cents)

    def to_json(self):
        return {
            "month": self.month,
            "income_cents": self.income_cents,
            "spending_cents": self.spending_cents,
            "net_cents": self.net_cents,
            "savings_rate": self.savings_rate,
            "by_category": dict(sorted(self.by_category.items())),
            "count": self.count,
        }


def _category_kinds(store):
    return {c.id: (c.name, c.kind) for c in store.list_categories()}


def monthly(store, year, month, account_id=None):
    start, end = month_bounds(year, month)
    kinds = _category_kinds(store)
    report = MonthlyReport(month=f"{year:04d}-{month:02d}")
    by_cat = defaultdict(int)
    for txn in store.list_transactions(account_id=account_id, start=start, end=end):
        name, kind = kinds.get(txn.category_id, (UNCATEGORIZED, None))
        if kind == "transfer":
            continue
        report.count += 1
        if txn.amount_cents > 0:
            report.income_cents += txn.amount_cents
        else:
            report.spending_cents += txn.amount_cents
        by_cat[name] += txn.amount_cents
    report.by_category = dict(by_cat)
    return report


def yearly(store, year, account_id=None):
    return [monthly(store, year, m, account_id) for m in range(1, 13)]


def top_spending(report, n=5):
    """The n categories with the most money out, biggest first."""
    spend = [(name, cents) for name, cents in report.by_category.items() if cents < 0]
    spend.sort(key=lambda item: item[1])
    return spend[:n]


def months_with_data(store, account_id=None):
    seen = set()
    for txn in store.list_transactions(account_id=account_id):
        seen.add(month_key(txn.posted))
    return sorted(seen)
