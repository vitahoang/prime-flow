"""Unit labels and conversions.

Items are always counted in their own unit (``Item.unit``): cartons of oat
milk, kg of flour, sheets of croissant dough. Conversions are only used when
importing old spreadsheets that recorded grams or litres.
"""

from __future__ import annotations

PLURALS = {
    "box": "boxes",
    "loaf": "loaves",
    "each": "each",
    "kg": "kg",
    "g": "g",
    "l": "l",
    "ml": "ml",
}

# factor to multiply by to get the base unit
_TO_BASE = {
    ("g", "kg"): 0.001,
    ("kg", "g"): 1000.0,
    ("ml", "l"): 0.001,
    ("l", "ml"): 1000.0,
}


def plural(unit: str, qty: float) -> str:
    unit = unit.strip()
    if abs(qty) == 1:
        return unit
    if unit.lower() in PLURALS:
        return PLURALS[unit.lower()]
    return unit + "s"


def convert(qty: float, from_unit: str, to_unit: str) -> float:
    a, b = from_unit.lower(), to_unit.lower()
    if a == b:
        return qty
    try:
        return qty * _TO_BASE[(a, b)]
    except KeyError:
        raise ValueError(f"cannot convert {from_unit} to {to_unit}") from None


def is_weight(unit: str) -> bool:
    return unit.lower() in ("g", "kg")


def is_volume(unit: str) -> bool:
    return unit.lower() in ("ml", "l")
