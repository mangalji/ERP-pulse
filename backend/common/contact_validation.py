"""
Shared country/phone validation for AGSuite ERP.

The selected country is the source of truth for validating the phone number.
Phones are normalized to E.164 format before being persisted.

Dependency:
    pip install phonenumbers
"""

from __future__ import annotations

from dataclasses import dataclass

import phonenumbers
from phonenumbers import NumberParseException

@dataclass(frozen=True)
class NormalizedPhone:
    number: str
    country_code: str
    dial_code: str


def _validate_country(country: str) -> str:
    region = str(country or "").strip().upper()

    if len(region) != 2 or not region.isalpha():
        raise ValueError("Country must be a valid 2-letter country code.")

    try:
        calling_code = phonenumbers.country_code_for_region(region)
    except Exception as exc:
        raise ValueError("Invalid country selected.") from exc

    if not calling_code:
        raise ValueError("The selected country has no valid calling code.")

    return region


def normalize_phone(*, phone: str, country: str) -> NormalizedPhone:
    if not phone or not str(phone).strip():
        raise ValueError("Phone number is required.")

    region = _validate_country(country)
    dial_code = f"+{phonenumbers.country_code_for_region(region)}"

    raw = str(phone).strip()
    digits = "".join(
        character for character in raw
        if character.isdigit()
    )

    if not digits:
        raise ValueError("Phone number must contain digits.")

    if len(digits) < 7 or len(digits) > 15:
        raise ValueError(
            "Phone number must contain between 7 and 15 digits."
        )

    if raw.startswith("+"):
        normalized = f"+{digits}"
    else:
        try:
            parsed = phonenumbers.parse(raw, region)

            normalized = phonenumbers.format_number(
                parsed,
                phonenumbers.PhoneNumberFormat.E164,
            )

        except NumberParseException:
            # Parsing failed, but the basic phone data is usable.
            # Fall back to the selected country's calling code.
            national_digits = digits.lstrip("0") or digits
            normalized = f"{dial_code}{national_digits}"

    normalized_digits = "".join(
        character for character in normalized
        if character.isdigit()
    )

    if len(normalized_digits) > 15:
        raise ValueError(
            "Phone number is too long for international storage."
        )

    return NormalizedPhone(
        number=normalized,
        country_code=region,
        dial_code=dial_code,
    )