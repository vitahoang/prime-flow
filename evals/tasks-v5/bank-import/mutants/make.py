"""Rebuild each mutant from ref: ref with exactly one H/T item broken.
Run from the task directory after copying ref files in (see verify notes)."""
from pathlib import Path


def edit(p, old, new):
    p = Path(p); s = p.read_text(); assert old in s, (p, old); p.write_text(s.replace(old, new))


# H1: one key per (date, amount, description); no bank ids, no occurrence number
edit('mutants/H1/pennywise/importer.py', '''    seen = defaultdict(int)
    keys = []
    for posted, cents, desc, ref in rows:
        if ref:
            keys.append("ref:" + ref)
            continue
        base = f"{posted}|{cents}|{' '.join(desc.split()).casefold()}"
        n = seen[base]
        seen[base] = n + 1
        keys.append(f"row:{base}#{n}")
    return keys''', '''    return [f"row:{posted}|{cents}|{' '.join(desc.split()).casefold()}"
            for posted, cents, desc, _ref in rows]''')
# H2: a commit per row
edit('mutants/H2/pennywise/importer.py', '''    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO transactions (account_id, posted, amount_cents, description,"
            " category_id, created_at, source, import_key) VALUES (?, ?, ?, ?, ?, ?, 'import', ?)",
            new,
        )''', '''    for row in new:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO transactions (account_id, posted, amount_cents, description,"
                " category_id, created_at, source, import_key) VALUES (?, ?, ?, ?, ?, ?, 'import', ?)",
                row,
            )''')
# H3: remembers the file as imported before its rows are in
edit('mutants/H3/pennywise/importer.py', '''    profile = get_profile(account.bank)
    rows = read_rows(path, profile)''', '''    profile = get_profile(account.bank)
    import hashlib
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    with store.conn:
        store.conn.execute("CREATE TABLE IF NOT EXISTS imported_files (account_id INTEGER, sha256 TEXT)")
        if store.conn.execute("SELECT 1 FROM imported_files WHERE account_id = ? AND sha256 = ?",
                              (account.id, digest)).fetchone():
            return ImportResult(read=0, added=0, skipped=0)
        store.conn.execute("INSERT INTO imported_files VALUES (?, ?)", (account.id, digest))
    rows = read_rows(path, profile)''')
# H4: card amounts as written
edit('mutants/H4/pennywise/bank_profiles.py', '''        invert_amounts=True,\n''', '')
# H5: no rules
edit('mutants/H5/pennywise/importer.py', '''    categorize = ruleset.category_for if len(ruleset) else None''', '''    categorize = None''')
# H6: pending rows imported
edit('mutants/H6/pennywise/importer.py', '''            if i_type is not None and row[i_type].strip().upper() in skip_types:
                continue  # pending: it comes back later as a normal row
''', '')
# H7: zero-amount rows imported
edit('mutants/H7/pennywise/importer.py', '''            if cents == 0:
                continue  # card checks (hotels, car hire): no money moved
''', '')
# T1: card dates day-first
edit('mutants/T1/pennywise/bank_profiles.py', '''date_format="%m/%d/%Y"''', '''date_format="%d/%m/%Y"''')
