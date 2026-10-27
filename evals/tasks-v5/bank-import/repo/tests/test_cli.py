def test_accounts_add_and_list(cli):
    cli("accounts", "add", "Northbank", "--bank", "northbank")
    cli("accounts", "add", "Kestrel", "--bank", "kestrel", "--currency", "eur")
    data = cli.json("accounts", "list")
    assert [(a["name"], a["bank"], a["currency"]) for a in data] == [
        ("Kestrel", "kestrel", "EUR"), ("Northbank", "northbank", "GBP")]


def test_unknown_bank_rejected(cli):
    proc = cli("accounts", "add", "X", "--bank", "monzo", check=False)
    assert proc.returncode != 0


def test_txn_add_and_list_json(cli):
    cli("accounts", "add", "Main")
    cli("txn", "add", "--account", "Main", "--date", "2025-08-04", "--amount", "-4.50",
        "--desc", "PRET A MANGER")
    rows = cli.json("txn", "list", "--account", "Main")
    assert rows == [{"id": 1, "account": "Main", "date": "2025-08-04", "amount": "-4.50",
                     "amount_cents": -450, "description": "PRET A MANGER", "category": None,
                     "source": "manual"}]


def test_rules_apply_via_cli(cli):
    cli("accounts", "add", "Main")
    cli("txn", "add", "--account", "Main", "--date", "2025-08-04", "--amount", "-4.50",
        "--desc", "PRET A MANGER")
    cli("rules", "add", "pret", "--category", "Eating out")
    assert "categorised 1" in cli("rules", "apply").stdout
    assert cli.json("txn", "list")[0]["category"] == "Eating out"


def test_missing_account_is_an_error(cli):
    proc = cli("txn", "list", "--account", "Nope", check=False)
    assert proc.returncode == 2
    assert "no account called" in proc.stderr


def test_report_monthly_json(cli):
    cli("accounts", "add", "Main")
    cli("txn", "add", "--account", "Main", "--date", "2025-08-01", "--amount", "1000",
        "--desc", "Invoice")
    cli("txn", "add", "--account", "Main", "--date", "2025-08-02", "--amount", "-250",
        "--desc", "Rent")
    rep = cli.json("report", "monthly", "2025-08")
    assert rep["income_cents"] == 100000 and rep["net_cents"] == 75000


def test_export_csv(cli):
    cli("accounts", "add", "Main")
    cli("txn", "add", "--account", "Main", "--date", "2025-08-01", "--amount", "-1.00",
        "--desc", "Gum")
    out = cli("export", "--account", "Main").stdout.splitlines()
    assert out == ["date,description,amount,category,note", "2025-08-01,Gum,-1.00,,"]
