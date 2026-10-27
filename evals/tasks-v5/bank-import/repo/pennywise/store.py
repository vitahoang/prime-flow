"""All reads and writes against the database go through Store.

Each write method commits on its own, so a crash never leaves a half-written
manual entry behind.
"""

from datetime import date

from . import db
from .errors import InvalidInput, NotFound
from .models import (CATEGORY_KINDS, RULE_MATCHES, RULE_SIGNS, Account, Budget,
                     Category, Rule, Transaction)


class Store:
    def __init__(self, conn):
        self.conn = conn

    @classmethod
    def open(cls, path):
        return cls(db.connect(path))

    def close(self):
        self.conn.close()

    # --- accounts ---------------------------------------------------------

    def add_account(self, name, bank="manual", currency="GBP", opened=None):
        name = name.strip()
        if not name:
            raise InvalidInput("account name can't be empty")
        if self._account_row(name) is not None:
            raise InvalidInput(f"account {name!r} already exists")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO accounts (name, bank, currency, opened) VALUES (?, ?, ?, ?)",
                (name, bank, currency.upper(), opened.isoformat() if opened else None),
            )
        return self.get_account_by_id(cur.lastrowid)

    def _account_row(self, name):
        return self.conn.execute(
            "SELECT * FROM accounts WHERE name = ? COLLATE NOCASE", (name.strip(),)
        ).fetchone()

    def get_account(self, name):
        row = self._account_row(name)
        if row is None:
            raise NotFound(f"no account called {name!r} (see `pennywise accounts list`)")
        return Account.from_row(row)

    def get_account_by_id(self, account_id):
        row = self.conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if row is None:
            raise NotFound(f"no account with id {account_id}")
        return Account.from_row(row)

    def list_accounts(self, include_closed=False):
        sql = "SELECT * FROM accounts"
        if not include_closed:
            sql += " WHERE closed IS NULL"
        return [Account.from_row(r) for r in self.conn.execute(sql + " ORDER BY name")]

    def close_account(self, name, on=None):
        account = self.get_account(name)
        with self.conn:
            self.conn.execute(
                "UPDATE accounts SET closed = ? WHERE id = ?",
                ((on or date.today()).isoformat(), account.id),
            )

    def balance(self, account_id):
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount_cents), 0) FROM transactions WHERE account_id = ?",
            (account_id,),
        ).fetchone()
        return row[0]

    def last_transaction_date(self, account_id):
        row = self.conn.execute(
            "SELECT MAX(posted) FROM transactions WHERE account_id = ?", (account_id,)
        ).fetchone()
        return date.fromisoformat(row[0]) if row[0] else None

    # --- categories -------------------------------------------------------

    def add_category(self, name, kind="expense", parent=None):
        if kind not in CATEGORY_KINDS:
            raise InvalidInput(f"kind must be one of {', '.join(CATEGORY_KINDS)}")
        parent_id = self.get_category(parent).id if parent else None
        try:
            with self.conn:
                cur = self.conn.execute(
                    "INSERT INTO categories (name, kind, parent_id) VALUES (?, ?, ?)",
                    (name.strip(), kind, parent_id),
                )
        except Exception as exc:  # sqlite3.IntegrityError
            raise InvalidInput(f"category {name!r} already exists") from exc
        return Category(cur.lastrowid, name.strip(), kind, parent_id)

    def get_category(self, name):
        row = self.conn.execute(
            "SELECT * FROM categories WHERE name = ?", (name.strip(),)
        ).fetchone()
        if row is None:
            raise NotFound(f"no category called {name!r}")
        return Category.from_row(row)

    def ensure_category(self, name, kind="expense"):
        try:
            return self.get_category(name)
        except NotFound:
            return self.add_category(name, kind)

    def list_categories(self):
        return [Category.from_row(r) for r in self.conn.execute("SELECT * FROM categories ORDER BY name")]

    def category_names(self):
        return {r["id"]: r["name"] for r in self.conn.execute("SELECT id, name FROM categories")}

    # --- transactions -----------------------------------------------------

    def add_transaction(self, account_id, posted, amount_cents, description,
                        category_id=None, note=None, source="manual"):
        """Insert one transaction and commit."""
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO transactions (account_id, posted, amount_cents, description,"
                " category_id, note, source) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (account_id, posted.isoformat(), int(amount_cents), description.strip(),
                 category_id, note, source),
            )
        return cur.lastrowid

    def get_transaction(self, txn_id):
        row = self.conn.execute("SELECT * FROM transactions WHERE id = ?", (txn_id,)).fetchone()
        if row is None:
            raise NotFound(f"no transaction with id {txn_id}")
        return Transaction.from_row(row)

    def list_transactions(self, account_id=None, start=None, end=None, category_id=None,
                          uncategorized=False, limit=None):
        where, args = [], []
        if account_id is not None:
            where.append("account_id = ?")
            args.append(account_id)
        if start is not None:
            where.append("posted >= ?")
            args.append(start.isoformat())
        if end is not None:
            where.append("posted <= ?")
            args.append(end.isoformat())
        if category_id is not None:
            where.append("category_id = ?")
            args.append(category_id)
        if uncategorized:
            where.append("category_id IS NULL")
        sql = "SELECT * FROM transactions"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY posted, id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [Transaction.from_row(r) for r in self.conn.execute(sql, args)]

    def set_category(self, txn_id, category_id):
        self.get_transaction(txn_id)
        with self.conn:
            self.conn.execute(
                "UPDATE transactions SET category_id = ? WHERE id = ?", (category_id, txn_id)
            )

    def delete_transaction(self, txn_id):
        self.get_transaction(txn_id)
        with self.conn:
            self.conn.execute("DELETE FROM transactions WHERE id = ?", (txn_id,))

    def count_transactions(self, account_id=None):
        if account_id is None:
            return self.conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        return self.conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE account_id = ?", (account_id,)
        ).fetchone()[0]

    # --- rules ------------------------------------------------------------

    def add_rule(self, pattern, category_id, match="contains", priority=100,
                 account_id=None, sign=None):
        if match not in RULE_MATCHES:
            raise InvalidInput(f"match must be one of {', '.join(RULE_MATCHES)}")
        if sign is not None and sign not in RULE_SIGNS:
            raise InvalidInput("sign must be 'in' or 'out'")
        if not pattern.strip():
            raise InvalidInput("rule pattern can't be empty")
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO rules (pattern, match, category_id, priority, account_id, sign)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (pattern, match, category_id, priority, account_id, sign),
            )
        return cur.lastrowid

    def list_rules(self):
        rows = self.conn.execute("SELECT * FROM rules ORDER BY priority, id")
        return [Rule.from_row(r) for r in rows]

    def delete_rule(self, rule_id):
        with self.conn:
            cur = self.conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        if cur.rowcount == 0:
            raise NotFound(f"no rule with id {rule_id}")

    # --- budgets ----------------------------------------------------------

    def set_budget(self, category_id, amount_cents):
        with self.conn:
            self.conn.execute(
                "INSERT INTO budgets (category_id, amount_cents) VALUES (?, ?)"
                " ON CONFLICT(category_id) DO UPDATE SET amount_cents = excluded.amount_cents",
                (category_id, amount_cents),
            )

    def list_budgets(self):
        rows = self.conn.execute("SELECT category_id, amount_cents FROM budgets")
        return [Budget(r["category_id"], r["amount_cents"]) for r in rows]
