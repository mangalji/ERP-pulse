import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class StrongPasswordValidator:
    """
    Enforces the password rules used by the AGSuite ERP frontend:
    - minimum 8 characters
    - at least one uppercase letter
    - at least one lowercase letter
    - at least one number
    - at least one special character
    """

    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError(
                _("Password must contain at least 8 characters.")
            )

        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                _("Password must contain at least one uppercase letter.")
            )

        if not re.search(r"[a-z]", password):
            raise ValidationError(
                _("Password must contain at least one lowercase letter.")
            )

        if not re.search(r"\d", password):
            raise ValidationError(
                _("Password must contain at least one number.")
            )

        if not re.search(r"[^A-Za-z0-9]", password):
            raise ValidationError(
                _("Password must contain at least one special character.")
            )

    def get_help_text(self):
        return _(
            "Password must contain at least 8 characters, "
            "one uppercase letter, one lowercase letter, "
            "one number, and one special character."
        )