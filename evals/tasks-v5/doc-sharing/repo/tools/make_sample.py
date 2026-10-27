"""Rebuild data/sample_workspace.json, the demo store used by the README and tests.

It mirrors what the directory sync gave us for Hollis & Grey, nesting included.

    FOLIO_NOW=2026-09-01T09:00:00+00:00 python tools/make_sample.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from folio.serialize import save  # noqa: E402
from folio.store import Store  # noqa: E402


def build() -> Store:
    s = Store()
    ws = s.add_workspace("Hollis & Grey", domain="hollisgrey.com")
    olive = s.add_user(ws, "olive@hollisgrey.com", "Olive Hollis")
    marcus = s.add_user(ws, "marcus@hollisgrey.com", "Marcus Grey")
    priya = s.add_user(ws, "priya@hollisgrey.com", "Priya Nair")
    jun = s.add_user(ws, "jun@hollisgrey.com", "Jun Park")
    tom = s.add_user(ws, "tom@hollisgrey.com", "Tom Reyes")
    sam = s.add_user(ws, "sam@hollisgrey.com", "Sam Ito")
    lena = s.add_user(ws, "lena@lenastudio.io", "Lena Vogel")
    s.add_admin(ws, olive)
    s.suspend_user(sam)

    everyone = s.add_group(ws, "Everyone", [olive])
    studio = s.add_group(ws, "Studio", [jun])
    architects = s.add_group(ws, "Architects", [marcus, priya])
    s.add_subgroup(everyone, studio)
    s.add_subgroup(studio, architects)
    design = s.add_group(ws, "Design", [tom])
    brand = s.add_group(ws, "Brand", [lena])
    s.add_subgroup(design, brand)
    s.add_subgroup(brand, design)
    s.add_subgroup(everyone, design)

    projects = s.create_folder(ws, "Projects", marcus)
    harbour = s.create_folder(ws, "Harbour Library", marcus, projects)
    market = s.create_folder(ws, "Market Hall", priya, projects)
    drawings = s.create_folder(ws, "Drawings", priya, market)
    admin = s.create_folder(ws, "Admin", olive)

    s.create_document(harbour, "Brief", marcus, "Client wants a reading room facing the water.")
    s.create_document(harbour, "Site visit notes", marcus, "Tide line is higher than the survey says.")
    s.create_document(market, "Planning application", priya, "Draft for the council, due in October.")
    s.create_document(drawings, "Roof options", priya, "Option B keeps the original trusses.")
    old = s.create_document(market, "Old fee proposal", priya, "Superseded by the July proposal.")
    s.trash_document(old)
    bands = s.create_document(admin, "Salary bands", olive, "Confidential.")
    s.set_restricted(bands)
    s.create_document(admin, "Office handbook", olive, "Kitchen rota, holidays, IT.")
    s.create_document(admin, "Brand guidelines", tom, "Logo spacing and colours.")
    return s


if __name__ == "__main__":
    os.environ.setdefault("FOLIO_NOW", "2026-09-01T09:00:00+00:00")
    out = ROOT / "data" / "sample_workspace.json"
    save(build(), out)
    print(f"wrote {out}")
