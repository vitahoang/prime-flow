"""Import a bank's CSV export into an account.

Every imported row gets an import key that identifies it within the bank's
export: the bank's own transaction id when the export has one, otherwise
date + amount + description plus an occurrence number (the 1st, 2nd, ...
identical row that day), so two real coffees on the same day both stay.
Re-importing the same or an overlapping export skips rows whose key is
already there.

The whole file goes in as one database transaction: an import that is killed
part-way leaves nothing behind, and running it again imports everything once.
"""

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from .bank_profiles import get_profile
from .dates import DEFAULT_FORMAT
from .errors import InvalidInput
from .money import parse_amount
from .rules import load_rules


@dataclass
class ImportResult:
    read: int
    added: int
    skipped: int


def _date_parser(fmt):
    cache = {}

    def parse(text):
        iso = cache.get(text)
        if iso is None:
            try:
                iso = datetime.strptime(text.strip(), fmt).date().isoformat()
            except ValueError:
                raise InvalidInput(f"not a date in {fmt}: {text!r}") from None
            cache[text] = iso
        return iso

    return parse


def _cents(text, decimal):
    """Fast path for the plain amounts exports use; anything odd goes to parse_amount."""
    s = text.strip()
    s2 = s.replace(",", "") if decimal == "." else s.replace(".", "").replace(",", ".")
    neg = s2[:1] == "-"
    whole, _, frac = (s2[1:] if neg else s2).partition(".")
    if whole.isdigit() and len(frac) == 2 and frac.isdigit():
        v = int(whole) * 100 + int(frac)
        return -v if neg else v
    return parse_amount(text, decimal)


def read_rows(path, profile):
    """[(posted_iso, amount_cents, description, reference_or_None), ...] in file order."""
    parse_date = _date_parser(profile.date_format or DEFAULT_FORMAT)
    decimal = profile.decimal
    sign = -1 if profile.invert_amounts else 1
    out = []
    with open(path, encoding=profile.encoding, newline="") as fh:
        reader = csv.reader(fh, delimiter=profile.delimiter)
        header = [h.strip() for h in next(reader, [])]
        missing = profile.missing_columns(header)
        if missing:
            raise InvalidInput(f"{path} doesn't look like a {profile.label} export "
                               f"(missing columns: {', '.join(missing)})")
        col = {name: i for i, name in enumerate(header)}
        i_date, i_desc = col[profile.date_column], col[profile.description_column]
        i_ref = col[profile.reference_column] if profile.reference_column else None
        i_type = col.get(profile.type_column) if profile.type_column else None
        skip_types = {t.upper() for t in profile.skip_types}
        if profile.amount_column:
            i_amt = col[profile.amount_column]
            i_in = i_out = None
        else:
            i_amt = None
            i_in, i_out = col[profile.paid_in_column], col[profile.paid_out_column]
        for line_no, row in enumerate(reader, start=2):
            if not row or not any(cell.strip() for cell in row):
                continue
            if i_type is not None and row[i_type].strip().upper() in skip_types:
                continue  # pending: it comes back later as a normal row
            try:
                posted = parse_date(row[i_date])
                if i_amt is not None:
                    cents = _cents(row[i_amt], decimal)
                else:
                    paid_in, paid_out = row[i_in].strip(), row[i_out].strip()
                    cents = (_cents(paid_in, decimal) if paid_in else 0) - \
                            (_cents(paid_out, decimal) if paid_out else 0)
            except (InvalidInput, IndexError) as exc:
                raise InvalidInput(f"{path}, line {line_no}: {exc}") from None
            if cents == 0:
                continue  # card checks (hotels, car hire): no money moved
            ref = row[i_ref].strip() if i_ref is not None else ""
            out.append((posted, sign * cents, row[i_desc].strip(), ref or None))
    return out


def import_keys(rows):
    """One key per row, stable across exports that contain the same row."""
    seen = defaultdict(int)
    keys = []
    for posted, cents, desc, ref in rows:
        if ref:
            keys.append("ref:" + ref)
            continue
        base = f"{posted}|{cents}|{' '.join(desc.split()).casefold()}"
        n = seen[base]
        seen[base] = n + 1
        keys.append(f"row:{base}#{n}")
    return keys


def import_file(store, account, path):
    if account.bank == "manual":
        raise InvalidInput(f"account {account.name!r} is a manual account; "
                           "set it up with --bank to import exports")
    profile = get_profile(account.bank)
    import hashlib
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    with store.conn:
        store.conn.execute("CREATE TABLE IF NOT EXISTS imported_files (account_id INTEGER, sha256 TEXT)")
        if store.conn.execute("SELECT 1 FROM imported_files WHERE account_id = ? AND sha256 = ?",
                              (account.id, digest)).fetchone():
            return ImportResult(read=0, added=0, skipped=0)
        store.conn.execute("INSERT INTO imported_files VALUES (?, ?)", (account.id, digest))
    rows = read_rows(path, profile)
    keys = import_keys(rows)
    conn = store.conn
    existing = {r[0] for r in conn.execute(
        "SELECT import_key FROM transactions WHERE account_id = ? AND import_key IS NOT NULL",
        (account.id,))}
    ruleset = load_rules(store)
    categorize = ruleset.category_for if len(ruleset) else None
    created = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    new = []
    for (posted, cents, desc, _ref), key in zip(rows, keys):
        if key in existing:
            continue
        existing.add(key)
        category_id = categorize(desc, cents, account.id) if categorize else None
        new.append((account.id, posted, cents, desc, category_id, created, key))
    conn.execute("PRAGMA cache_size = -65536")  # 64 MB: big imports touch many index pages
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO transactions (account_id, posted, amount_cents, description,"
            " category_id, created_at, source, import_key) VALUES (?, ?, ?, ?, ?, ?, 'import', ?)",
            new,
        )
    return ImportResult(read=len(rows), added=len(new), skipped=len(rows) - len(new))
