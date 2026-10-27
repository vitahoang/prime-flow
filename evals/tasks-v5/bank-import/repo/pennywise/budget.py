"""Monthly budgets per expense category."""

from dataclasses import dataclass

from .reports import monthly


@dataclass
class BudgetLine:
    category: str
    budget_cents: int
    spent_cents: int  # positive number: how much went out

    @property
    def remaining_cents(self):
        return self.budget_cents - self.spent_cents

    @property
    def over(self):
        return self.spent_cents > self.budget_cents


def status(store, year, month):
    report = monthly(store, year, month)
    names = store.category_names()
    lines = []
    for budget in store.list_budgets():
        name = names.get(budget.category_id, "?")
        spent = -min(report.by_category.get(name, 0), 0)
        lines.append(BudgetLine(name, budget.amount_cents, spent))
    lines.sort(key=lambda line: line.category.lower())
    return lines


def total(lines):
    return sum(line.budget_cents for line in lines), sum(line.spent_cents for line in lines)
