from datetime import date

from stockroom import clock, config


def test_today_override(monkeypatch):
    monkeypatch.setenv("STOCKROOM_TODAY", "2026-01-31")
    assert clock.today() == date(2026, 1, 31)


def test_today_default(monkeypatch):
    monkeypatch.delenv("STOCKROOM_TODAY", raising=False)
    assert clock.today() == date.today()


def test_data_dir_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("STOCKROOM_DATA", str(tmp_path))
    assert config.data_dir("elsewhere").name == "elsewhere"
    assert config.data_dir() == tmp_path
    monkeypatch.delenv("STOCKROOM_DATA")
    assert str(config.data_dir()) == "data"


def test_shop_sort_key():
    assert sorted(["STN", "ZZZ", "HAR", "MKT"], key=config.shop_sort_key) == ["HAR", "MKT", "STN", "ZZZ"]
