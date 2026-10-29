"""Deterministic financial-field calculations for OCR extraction results.

The AI extracts only values that appear in the source.  Amounts that can be
derived from those source values are calculated here so the same business
rules apply to file uploads, email extraction, review saves, and APIs.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


_MONEY_QUANTUM = Decimal("0.01")


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


def _set_calculated(target: dict[str, Any], key: str, value: int | float | None, *, overwrite: bool) -> None:
    """Set only configured fields; preserve explicit values for review saves."""
    if key not in target:
        return
    if overwrite or target.get(key) in (None, ""):
        target[key] = value


def apply_calculated_values(
    extraction: dict[str, Any], *, overwrite: bool = True
) -> dict[str, Any]:
    """Calculate line and invoice values without relying on AI arithmetic.

    A line subtotal is quantity × unit price.  A line tax is calculated only
    when a tax rate is supplied.  Line total is subtotal plus the available
    tax.  Header total tax stays empty when no line contains known tax data;
    header amount is populated only when every line has a calculable total.
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
        subtotal = quantity * unit_price if quantity is not None and unit_price is not None else source_subtotal
        _set_calculated(item, "subtotal", _money(subtotal) if subtotal is not None else None, overwrite=overwrite)

        tax_rate = _decimal(item.get("tax_rate"))
        source_tax = _decimal(item.get("tax_amount"))
        tax_amount = subtotal * tax_rate / Decimal("100") if subtotal is not None and tax_rate is not None else source_tax
        _set_calculated(item, "tax_amount", _money(tax_amount) if tax_amount is not None else None, overwrite=overwrite)

        source_total = _decimal(item.get("total_amount"))
        total_amount = subtotal + (tax_amount or Decimal("0")) if subtotal is not None else source_total
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
