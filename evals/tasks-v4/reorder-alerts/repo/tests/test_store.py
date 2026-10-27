import json

import pytest

from stockroom.models import MovementType, POStatus
from stockroom.store import DataError, append_movements, load, load_movements, parse_movement

from conftest import write_data


def test_load_everything(inv):
    assert inv.shop_codes() == ["HAR", "MKT", "STN"]
    assert inv.item("oat-1l").name == "Oat milk 1L"
    assert inv.supplier_for("OAT-1L").lead_time_days == 2
    assert inv.suppliers["laminata"].case_size("CRD-SHEET") == 20
    assert len(inv.movements) == 10
    assert {po.status for po in inv.purchase_orders} == set(POStatus)


def test_movements_sorted_by_date(inv):
    dates = [m.date for m in inv.movements]
    assert dates == sorted(dates)


def test_unknown_shop_and_sku(inv):
    with pytest.raises(DataError, match="unknown shop"):
        inv.shop("XYZ")
    with pytest.raises(DataError, match="unknown SKU"):
        inv.item("NOPE")


def test_missing_directory(tmp_path):
    with pytest.raises(DataError, match="not found"):
        load(tmp_path / "nowhere")


def test_purchase_orders_optional(tmp_path):
    inv = load(write_data(tmp_path / "d", orders=None))
    assert inv.purchase_orders == []


def test_bad_movement_type():
    with pytest.raises(DataError, match="unknown movement type"):
        parse_movement({"date": "2026-10-01", "shop": "HAR", "sku": "X", "type": "stolen", "qty": "1"})


def test_negative_qty_rejected():
    with pytest.raises(DataError, match="positive"):
        parse_movement({"date": "2026-10-01", "shop": "HAR", "sku": "X", "type": "sale", "qty": "-1"})


def test_bad_date():
    with pytest.raises(DataError, match="YYYY-MM-DD"):
        parse_movement({"date": "01/10/2026", "shop": "HAR", "sku": "X", "type": "sale", "qty": "1"})


def test_append_round_trip(tmp_path, inv):
    path = tmp_path / "out.csv"
    assert append_movements(path, inv.movements[:3]) == 3
    append_movements(path, inv.movements[3:5])
    back = load_movements(path)
    assert len(back) == 5
    assert back[0].type is MovementType.DELIVERY


def test_items_json_must_be_list(tmp_path):
    d = write_data(tmp_path / "d")
    (d / "items.json").write_text(json.dumps({"sku": "X"}))
    with pytest.raises(DataError, match="expected a list"):
        load(d)
