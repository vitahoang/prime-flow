import pytest

from alertd.settings import (
    InvalidSettings, UserSettings, load_settings, save_settings, settings_from_dict,
)


def test_default_timezone_is_utc():
    assert UserSettings(user_id="u").timezone == "UTC"


def test_bad_timezone_rejected():
    with pytest.raises(InvalidSettings):
        UserSettings(user_id="u", timezone="Mars/Olympus")


def test_from_dict_rejects_unknown_keys():
    with pytest.raises(InvalidSettings):
        settings_from_dict({"user_id": "u", "pager": "123"})


def test_from_dict_requires_user_id():
    with pytest.raises(InvalidSettings):
        settings_from_dict({"timezone": "UTC"})


def test_round_trip(tmp_path, settings):
    path = tmp_path / "dana.json"
    save_settings(settings, str(path))
    assert load_settings(str(path)) == settings
