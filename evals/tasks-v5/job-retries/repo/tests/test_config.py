import pytest

from taskmill import config
from taskmill.errors import ConfigError


def write(tmp_path, text):
    p = tmp_path / "c.toml"
    p.write_text(text)
    return p


def test_defaults_without_file():
    cfg = config.load()
    assert cfg.workers == 1
    assert cfg.database == "taskmill.db"


def test_reads_file(tmp_path):
    p = write(tmp_path, '[taskmill]\nworkers = 3\ndatabase = "x.db"\n[email]\nport = 2525\n')
    cfg = config.load(p)
    assert cfg.workers == 3 and cfg.database == "x.db" and cfg.email.port == 2525
    assert cfg.source == str(p)


def test_env_db_override(tmp_path, monkeypatch):
    p = write(tmp_path, '[taskmill]\ndatabase = "x.db"\n')
    monkeypatch.setenv("TASKMILL_DB", "y.db")
    assert config.load(p).database == "y.db"


@pytest.mark.parametrize("text", [
    "[taskmill]\nworkers = 0\n",
    "[taskmill]\nbogus = 1\n",
    "[nope]\nx = 1\n",
    "[email]\nhots = 'typo'\n",
    "[taskmill]\nlog_level = 'LOUD'\n",
])
def test_bad_config(tmp_path, text):
    with pytest.raises(ConfigError):
        config.load(write(tmp_path, text))


def test_missing_explicit_file(tmp_path):
    with pytest.raises(ConfigError):
        config.load(tmp_path / "missing.toml")


def test_repo_config_is_valid():
    from pathlib import Path
    cfg = config.load(Path(__file__).resolve().parent.parent / "config.toml")
    assert cfg.handler_modules == ["taskmill.handlers"]
