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

# Registration flow (email/OTP/password held in cache until profile
# completion — see accounts/registration_cache.py).
OTP_RESEND_COOLDOWN_SECONDS = 60
REGISTRATION_SESSION_TTL_MINUTES = 20
REGISTRATION_TOKEN_MAX_AGE_SECONDS = REGISTRATION_SESSION_TTL_MINUTES * 60

EMAIL_SUBJECT_REGISTER = "Verify your ERP Pulse account"
EMAIL_SUBJECT_LOGIN = "Your ERP Pulse login OTP"

# How many prior messages (not the whole conversation) get sent to the AI
# provider as context on each turn. Kept deliberately small — unlimited
# history would grow both token cost and latency unboundedly as a
# conversation gets longer. The full conversation remains readable via
# GET /api/v1/ai/conversations/<id>/messages/ regardless of this limit.
AI_CONVERSATION_HISTORY_LIMIT = 10