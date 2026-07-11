"""
OTP utility functions.

Contains only OTP generation logic.
No database access.
No email sending.
No business logic.
"""

# import secrets
# import string
# from common.constants import OTP_LENGTH

# def generate_otp(length:int=OTP_LENGTH) -> str:
#      """
#     Generate a numeric OTP.

#     Args:
#         length: Length of the OTP.

#     Returns:
#         Random numeric OTP.
#     """
#      digits = string.digits

#      return "".join(secrets.choice(digits) for _ in range(length))


import secrets
import string


def generate_otp_code(length: int = 6) -> str:
    """
    Generate a random numeric OTP code of the given length.

    Uses `secrets` (not `random`) because OTP codes are a security control —
    they must not be predictable from a seeded or time-based PRNG.
    """
    if length < 4:
        raise ValueError('OTP length must be at least 4 digits.')

    return ''.join(secrets.choice(string.digits) for _ in range(length))
