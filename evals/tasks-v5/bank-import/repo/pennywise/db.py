"""SQLite connection and schema migrations.

The schema version lives in ``PRAGMA user_version``. Each entry in MIGRATIONS
moves the database up one version; ``connect`` applies whatever is missing.
Never edit a migration that has shipped; add a new one.
"""

import sqlite3
from pathlib import Path

MIGRATIONS = [
    # 1: accounts, categories, transactions
    """
    CREATE TABLE accounts (
        id        INTEGER PRIMARY KEY,
        name      TEXT NOT NULL UNIQUE,
        bank      TEXT NOT NULL DEFAULT 'manual',
        currency  TEXT NOT NULL DEFAULT 'GBP',
        opened    TEXT,
        closed    TEXT
    );
    CREATE TABLE categories (
        id        INTEGER PRIMARY KEY,
        name      TEXT NOT NULL UNIQUE COLLATE NOCASE,
        kind      TEXT NOT NULL DEFAULT 'expense',
        parent_id INTEGER REFERENCES categories(id)
    );
    CREATE TABLE transactions (
        id           INTEGER PRIMARY KEY,
        account_id   INTEGER NOT NULL REFERENCES accounts(id),
        posted       TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        description  TEXT NOT NULL DEFAULT '',
        category_id  INTEGER REFERENCES categories(id),
        note         TEXT,
        created_at   TEXT NOT NULL DEFAULT (datetime('now'))
    );
    CREATE INDEX ix_transactions_account_posted ON transactions(account_id, posted);
    """,
    # 2: categorisation rules
    """
    CREATE TABLE rules (
        id          INTEGER PRIMARY KEY,
        pattern     TEXT NOT NULL,
        match       TEXT NOT NULL DEFAULT 'contains',
        category_id INTEGER NOT NULL REFERENCES categories(id),
        priority    INTEGER NOT NULL DEFAULT 100,
        account_id  INTEGER REFERENCES accounts(id),
        sign        TEXT
    );
    """,
    # 3: where a transaction came from, and monthly budgets
    """
    ALTER TABLE transactions ADD COLUMN source TEXT NOT NULL DEFAULT 'manual';
    CREATE TABLE budgets (
        id           INTEGER PRIMARY KEY,
        category_id  INTEGER NOT NULL UNIQUE REFERENCES categories(id),
        amount_cents INTEGER NOT NULL
    );
    """,
]

SCHEMA_VERSION = len(MIGRATIONS)


def schema_version(conn):
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn):
    current = schema_version(conn)
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"database is at schema {current}, this pennywise only knows {SCHEMA_VERSION}"
        )
    for version in range(current + 1, SCHEMA_VERSION + 1):
        conn.executescript(MIGRATIONS[version - 1])
        conn.execute(f"PRAGMA user_version = {version}")
        conn.commit()


def connect(path):
    path = Path(path)
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn
