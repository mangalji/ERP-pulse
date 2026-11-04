from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from accounts.models import User
from rbac.models import Role
from subscriptions.permissions import IsSuperAdminOrCompanyAdmin, IsSuperAdminOrInternalUser
from tenancy.models import Company


class SubscriptionPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.company = Company(id='b896fe2e-0ba5-48da-902c-bfe2ff79dfbb')
        self.employee_role = Role(name='Employee', company=self.company)
        self.admin_role = Role(name='Company Admin', company=self.company)

    def _request_for(self, user):
        request = self.factory.get('/api/v1/subscriptions/my-transactions/')
        request.user = user
        return request

    def test_client_employee_cannot_view_billing_transactions(self):
        employee = User(
            company=self.company,
            role=self.employee_role,
            is_active=True,
        )

        self.assertFalse(
            IsSuperAdminOrInternalUser().has_permission(
                self._request_for(employee), None
            )
        )

    def test_platform_internal_user_can_view_billing_transactions(self):
        internal_user = User(is_active=True)

        self.assertTrue(
            IsSuperAdminOrInternalUser().has_permission(
                self._request_for(internal_user), None
            )
        )

    def test_only_company_admin_passes_company_admin_permission(self):
        employee = User(company=self.company, role=self.employee_role, is_active=True)
        company_admin = User(company=self.company, role=self.admin_role, is_active=True)

        self.assertFalse(
            IsSuperAdminOrCompanyAdmin().has_permission(
                self._request_for(employee), None
            )
        )
        self.assertTrue(
            IsSuperAdminOrCompanyAdmin().has_permission(
                self._request_for(company_admin), None
            )
        )
