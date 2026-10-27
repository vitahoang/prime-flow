import json

from ledger.settings import DEFAULTS, load_settings


def test_defaults_when_no_config(home):
    s = load_settings()
    assert s.timezone == DEFAULTS["timezone"]
    assert s.date_format == DEFAULTS["date_format"]


def test_config_overrides_defaults(home):
    (home / "config.json").write_text(json.dumps({"timezone": "Europe/Berlin"}))
    s = load_settings()
    assert s.timezone == "Europe/Berlin"
    assert s.currency_symbol == "$"
    assert s.tz.key == "Europe/Berlin"
