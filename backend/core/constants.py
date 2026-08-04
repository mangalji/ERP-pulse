"""
Project-wide generic constants.

Only truly generic, cross-cutting constants belong here.
Module-specific constants stay in their respective apps.

HTTP status codes are NOT defined here. Use rest_framework.status directly
to avoid drifting from canonical DRF definitions.
"""

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MIN_PAGE_SIZE = 1

# ID / UUID
UUID_FIELD_MAX_LENGTH = 36

# String length limits
NAME_MAX_LENGTH = 255
SLUG_MAX_LENGTH = 255
DESCRIPTION_MAX_LENGTH = 2000