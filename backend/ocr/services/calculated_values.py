"""Deterministic financial-field calculations for OCR extraction results.

The AI extracts only values that appear in the source.  Amounts that can be
derived from those source values are calculated here so the same business
rules apply to file uploads, email extraction, review saves, and APIs.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


_MONEY_QUANTUM = Decimal("0.01")
_RATE_QUANTUM = Decimal("0.000001")


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, TypeError, ValueError):
        return None


def _money(value: Decimal) -> int | float:
    rounded = value.quantize(_MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    return int(rounded) if rounded == rounded.to_integral_value() else float(rounded)


def _rate(value: Decimal) -> int | float:
    """Keep derived unit prices precise enough for fractional quantities."""
    rounded = value.quantize(_RATE_QUANTUM, rounding=ROUND_HALF_UP)
    return int(rounded) if rounded == rounded.to_integral_value() else float(rounded)


def _set_calculated(target: dict[str, Any], key: str, value: int | float | None, *, overwrite: bool) -> None:
    """Set only configured fields; preserve explicit values for review saves."""
    if key not in target:
        return
    if overwrite or target.get(key) in (None, ""):
        target[key] = value


def apply_calculated_values(
    extraction: dict[str, Any], *, overwrite: bool = True
) -> dict[str, Any]:
    """Normalize financial values without relying on AI arithmetic.

    Direct values from the source remain inputs, but all derivable values are
    resolved deterministically.  In particular, a gross line total can be
    converted to a pre-tax subtotal when tax information is available; that
    subtotal can then derive a missing unit price or quantity.  This is used
    after both email and file extraction, so their results behave identically.
    """
    if not isinstance(extraction, dict):
        return extraction

    result = dict(extraction)
    raw_items = result.get("line_items")
    if not isinstance(raw_items, list):
        return result

    calculated_items: list[Any] = []
    line_taxes: list[Decimal] = []
    line_totals: list[Decimal] = []
    has_line = False
    all_line_totals_known = True

    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            calculated_items.append(raw_item)
            all_line_totals_known = False
            continue

        has_line = True
        item = dict(raw_item)
        quantity = _decimal(item.get("quantity"))
        unit_price = _decimal(item.get("unit_price"))
        source_subtotal = _decimal(item.get("subtotal"))
        tax_rate = _decimal(item.get("tax_rate"))
        source_tax = _decimal(item.get("tax_amount"))
        source_total = _decimal(item.get("total_amount"))

        # For review saves, an explicit user value remains authoritative.  For
        # initial extraction, recompute derived values from the raw inputs.
        if not overwrite and source_subtotal is not None:
            subtotal = source_subtotal
        elif quantity is not None and unit_price is not None:
            subtotal = quantity * unit_price
        elif source_subtotal is not None:
            subtotal = source_subtotal
        elif source_total is not None:
            # A provided total is gross only if the source also supplied tax
            # information.  Otherwise total and subtotal are the same.
            if source_tax is not None:
                subtotal = source_total - source_tax
            elif tax_rate is not None and tax_rate > Decimal("-100"):
                subtotal = source_total / (Decimal("1") + (tax_rate / Decimal("100")))
            else:
                subtotal = source_total
        else:
            subtotal = None

        # Derive one missing line input when the other input and the resolved
        # pre-tax subtotal are known.  Never divide by zero or invent a value.
        if quantity is None and unit_price not in (None, Decimal("0")) and subtotal is not None:
            quantity = subtotal / unit_price
            _set_calculated(item, "quantity", _rate(quantity), overwrite=overwrite)
        elif unit_price is None and quantity not in (None, Decimal("0")) and subtotal is not None:
            unit_price = subtotal / quantity
            _set_calculated(item, "unit_price", _rate(unit_price), overwrite=overwrite)

        _set_calculated(item, "subtotal", _money(subtotal) if subtotal is not None else None, overwrite=overwrite)

        if not overwrite and source_tax is not None:
            tax_amount = source_tax
        elif subtotal is not None and tax_rate is not None:
            tax_amount = subtotal * tax_rate / Decimal("100")
        else:
            tax_amount = source_tax
        _set_calculated(item, "tax_amount", _money(tax_amount) if tax_amount is not None else None, overwrite=overwrite)

        if not overwrite and source_total is not None:
            total_amount = source_total
        elif subtotal is not None:
            total_amount = subtotal + (tax_amount or Decimal("0"))
        else:
            total_amount = source_total
        _set_calculated(item, "total_amount", _money(total_amount) if total_amount is not None else None, overwrite=overwrite)

        if tax_amount is not None:
            line_taxes.append(tax_amount)
        if total_amount is None:
            all_line_totals_known = False
        else:
            line_totals.append(total_amount)
        calculated_items.append(item)

    result["line_items"] = calculated_items
    if "total_tax_amount" in result:
        total_tax = sum(line_taxes, Decimal("0")) if line_taxes else None
        _set_calculated(result, "total_tax_amount", _money(total_tax) if total_tax is not None else None, overwrite=overwrite)
    if "amount" in result:
        invoice_total = sum(line_totals, Decimal("0")) if has_line and all_line_totals_known else None
        _set_calculated(result, "amount", _money(invoice_total) if invoice_total is not None else None, overwrite=overwrite)

    return result
