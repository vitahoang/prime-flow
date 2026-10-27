from pennywise.rules import RuleSet, apply_rules, load_rules
from pennywise.models import Rule
from tests.conftest import d


def rule(i, pattern, cat, **kw):
    return Rule(id=i, pattern=pattern, category_id=cat, **kw)


def test_contains_is_case_insensitive():
    rs = RuleSet([rule(1, "tesco", 7)])
    assert rs.category_for("TESCO STORES 2231", -100) == 7
    assert rs.category_for("Sainsburys", -100) is None


def test_priority_then_age():
    rs = RuleSet([rule(1, "AMAZON", 1, priority=100), rule(2, "AMAZON PRIME", 2, priority=10)])
    assert rs.category_for("AMAZON PRIME UK", -899) == 2
    assert rs.category_for("AMAZON MKTPLACE", -899) == 1


def test_match_kinds():
    rs = RuleSet([rule(1, "^TFL", 1, match="regex"), rule(2, "rent flat 3", 2, match="exact"),
                  rule(3, "pret", 3, match="startswith")])
    assert rs.category_for("TFL TRAVEL CH", -780) == 1
    assert rs.category_for("RENT FLAT 3", -95000) == 2
    assert rs.category_for("PRET A MANGER", -450) == 3
    assert rs.category_for("A PRET", -450) is None


def test_sign_and_account_filters():
    rs = RuleSet([rule(1, "kestrel", 1, sign="out", account_id=5)])
    assert rs.category_for("KESTREL TOP UP", -20000, account_id=5) == 1
    assert rs.category_for("KESTREL TOP UP", 20000, account_id=5) is None
    assert rs.category_for("KESTREL TOP UP", -20000, account_id=6) is None


def test_apply_rules_only_uncategorized(store):
    a = store.add_account("Main")
    food = store.add_category("Food")
    fun = store.add_category("Fun")
    t1 = store.add_transaction(a.id, d("2025-08-01"), -450, "PRET A MANGER")
    t2 = store.add_transaction(a.id, d("2025-08-02"), -450, "PRET A MANGER", category_id=fun.id)
    store.add_rule("pret", food.id)
    assert apply_rules(store) == 1
    assert store.get_transaction(t1).category_id == food.id
    assert store.get_transaction(t2).category_id == fun.id
    assert len(load_rules(store)) == 1
