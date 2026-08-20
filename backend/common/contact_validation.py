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

def _validate_india_mobile_sanity(digits: str) -> None:
    first_digit = digits[0]

    if first_digit not in {'6', '7', '8', '9'}:
        raise ValueError(
            'Indian mobile numbers must start with 6, 7, 8, or 9.'
        )

    if digits.count(first_digit) >= 4:
        raise ValueError(
            'The first digit cannot repeat 4 or more times in the number.'
        )

    if len(set(digits)) == 1:
        raise ValueError(
            'Mobile number cannot contain the same digit throughout.'
        )

    for index in range(len(digits) - 5):
        if len(set(digits[index:index + 6])) == 1:
            raise ValueError(
                'Mobile number cannot contain the same digit more than 5 times continuously.'
            )

    if digits in {'1234567890', '9876543210'}:
        raise ValueError(
            'Mobile number cannot be a simple sequential number.'
        )

    if (
        len(digits) == 10
        and all(digits[index] == digits[index % 2] for index in range(10))
        and digits[0] != digits[1]
    ):
        raise ValueError(
            'Mobile number cannot follow a repeating two-digit pattern.'
        )


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
    """
    Validate a phone number against the selected ISO country and normalize it.

    Example:
        country="IN", phone="9425457160"
        -> "+919425457160", "+91", "IN"
    """
    if not phone or not str(phone).strip():
        raise ValueError("Phone number is required.")

    region = _validate_country(country)

    raw = str(phone).strip()

    try:
        parsed = phonenumbers.parse(raw, region)
    except NumberParseException as exc:
        raise ValueError(
            "Enter a valid phone number for the selected country."
        ) from exc

    if not phonenumbers.is_possible_number(parsed):
        raise ValueError(
            "Enter a valid phone number for the selected country."
        )

    if not phonenumbers.is_valid_number(parsed):
        raise ValueError(
            "Enter a valid phone number for the selected country."
        )

    national_digits = str(parsed.national_number)
    if region == "IN":
        _validate_india_mobile_sanity(national_digits)

    normalized = phonenumbers.format_number(
        parsed,
        phonenumbers.PhoneNumberFormat.E164,
    )

    dial_code = f"+{parsed.country_code}"

    return NormalizedPhone(
        number=normalized,
        country_code=region,
        dial_code=dial_code,
    )