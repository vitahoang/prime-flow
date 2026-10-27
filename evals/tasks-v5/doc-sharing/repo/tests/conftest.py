import os
from pathlib import Path

import pytest

from folio.store import Store

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample_workspace.json"


@pytest.fixture(autouse=True)
def pinned_clock(monkeypatch):
    monkeypatch.setenv("FOLIO_NOW", "2026-09-01T09:00:00+00:00")


@pytest.fixture
def world():
    """A workspace with an owner, a teammate, a guest, a folder and a doc."""
    s = Store()
    ws = s.add_workspace("Hollis & Grey", domain="hollisgrey.com")
    olive = s.add_user(ws, "olive@hollisgrey.com", "Olive")
    marcus = s.add_user(ws, "marcus@hollisgrey.com", "Marcus")
    lena = s.add_user(ws, "lena@lenastudio.io", "Lena")
    projects = s.create_folder(ws, "Projects", olive)
    harbour = s.create_folder(ws, "Harbour", olive, projects)
    doc = s.create_document(harbour, "Brief", olive, "Reading room facing the water.")
    return dict(store=s, ws=ws, olive=olive, marcus=marcus, lena=lena,
                projects=projects, harbour=harbour, doc=doc)


@pytest.fixture
def sample_path():
    return SAMPLE
