from types import SimpleNamespace

from django.test import SimpleTestCase

from superadmin.permissions import IsSuperAdmin


class IsSuperAdminPermissionTests(SimpleTestCase):
    def test_delegated_staff_user_is_allowed(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                is_authenticated=True,
                is_superuser=False,
                is_staff=True,
                role_id=None,
            )
        )

        self.assertTrue(IsSuperAdmin().has_permission(request, None))

    def test_regular_company_user_is_not_allowed(self):
        request = SimpleNamespace(
            user=SimpleNamespace(
                is_authenticated=True,
                is_superuser=False,
                is_staff=False,
                role_id=None,
            )
        )

        self.assertFalse(IsSuperAdmin().has_permission(request, None))
