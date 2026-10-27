import csv
from pathlib import Path

import pytest

from pennywise.bank_profiles import PROFILES, get_profile
from pennywise.errors import NotFound

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


def header(name, delimiter):
    with open(SAMPLES / name, encoding="utf-8-sig", newline="") as fh:
        return next(csv.reader(fh, delimiter=delimiter))


@pytest.mark.parametrize("key,sample", [
    ("northbank", "northbank-2025-08.csv"),
    ("kestrel", "kestrel-2025-08.csv"),
])
def test_profile_matches_sample_header(key, sample):
    profile = get_profile(key)
    assert profile.missing_columns(header(sample, profile.delimiter)) == []


@pytest.mark.skip(reason="uscard profile not finished yet")
def test_uscard_profile_matches_sample():
    profile = get_profile("uscard")
    assert profile.missing_columns(header("uscard-2025-08.csv", profile.delimiter)) == []


def test_unknown_bank():
    with pytest.raises(NotFound):
        get_profile("monzo")


def test_every_profile_has_a_label():
    assert all(p.label for p in PROFILES.values())
