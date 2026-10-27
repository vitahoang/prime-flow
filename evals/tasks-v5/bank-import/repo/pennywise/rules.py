"""Category rules: "anything containing TESCO is Groceries".

Rules are tried in priority order (lowest number first, then oldest first);
the first rule that matches wins. A rule can be limited to one account and to
money in or money out.
"""

import re

from .models import Rule


class CompiledRule:
    __slots__ = ("rule", "_test")

    def __init__(self, rule: Rule):
        self.rule = rule
        pattern = rule.pattern
        if rule.match == "regex":
            rx = re.compile(pattern, re.IGNORECASE)
            self._test = lambda text: rx.search(text) is not None
        elif rule.match == "exact":
            folded = pattern.casefold().strip()
            self._test = lambda text: text.strip() == folded
        elif rule.match == "startswith":
            folded = pattern.casefold()
            self._test = lambda text: text.startswith(folded)
        else:
            folded = pattern.casefold()
            self._test = lambda text: folded in text

    def matches(self, folded_description, amount_cents, account_id):
        rule = self.rule
        if rule.account_id is not None and rule.account_id != account_id:
            return False
        if rule.sign == "in" and amount_cents <= 0:
            return False
        if rule.sign == "out" and amount_cents >= 0:
            return False
        return self._test(folded_description)


class RuleSet:
    def __init__(self, rules):
        ordered = sorted(rules, key=lambda r: (r.priority, r.id or 0))
        self._rules = [CompiledRule(r) for r in ordered]

    def __len__(self):
        return len(self._rules)

    def category_for(self, description, amount_cents, account_id=None):
        """The category id of the first matching rule, or None."""
        folded = description.casefold()
        for compiled in self._rules:
            if compiled.matches(folded, amount_cents, account_id):
                return compiled.rule.category_id
        return None


def load_rules(store):
    return RuleSet(store.list_rules())


def apply_rules(store, account_id=None, only_uncategorized=True):
    """Categorise existing transactions. Returns how many were changed."""
    ruleset = load_rules(store)
    if not len(ruleset):
        return 0
    changed = 0
    for txn in store.list_transactions(account_id=account_id, uncategorized=only_uncategorized):
        category_id = ruleset.category_for(txn.description, txn.amount_cents, txn.account_id)
        if category_id is not None and category_id != txn.category_id:
            store.set_category(txn.id, category_id)
            changed += 1
    return changed
