"""
Project-wide constants.

Only stable values belong here.
Business logic must not live in this file.
"""
OTP_LENGTH = 6

OTP_EXPIRY_MINUTES = 5

MAX_OTP_ATTEMPTS = 3

# OTP_PURPOSE_REGISTRATION = "REGISTRATION"

# OTP_PURPOSE_LOGIN = "LOGIN"

EMAIL_SUBJECT_REGISTER = "Verify your ERP Pulse account"
EMAIL_SUBJECT_LOGIN = "Your ERP Pulse login OTP"