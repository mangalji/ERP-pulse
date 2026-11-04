from types import SimpleNamespace

from django.test import SimpleTestCase

from invitations.permissions import CanVerifyInvitationEmail


def _request(*, staff=False, company_id=None, role_name="", role_company_id=None):
    role = (
        SimpleNamespace(name=role_name, company_id=role_company_id)
        if role_name else None
    )
    return SimpleNamespace(user=SimpleNamespace(
        is_authenticated=True,
        is_superuser=False,
        is_staff=staff,
        company_id=company_id,
        role=role,
    ))


class EmailVerificationPermissionTests(SimpleTestCase):
    def test_allows_platform_staff_and_company_admin_only(self):
        permission = CanVerifyInvitationEmail()

        self.assertTrue(permission.has_permission(_request(staff=True), None))
        self.assertTrue(permission.has_permission(_request(
            company_id="company-1", role_name="Company Admin", role_company_id="company-1",
        ), None))
        self.assertFalse(permission.has_permission(_request(
            company_id="company-1", role_name="Employee", role_company_id="company-1",
        ), None))
