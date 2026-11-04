from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from accounts.models import User
from rbac.models import Role
from tenancy.models import Company
from tenancy.permissions import IsCompanyAdmin


class CompanySettingsPermissionTests(SimpleTestCase):
    def test_only_company_admin_can_change_company_settings(self):
        company = Company(id='b896fe2e-0ba5-48da-902c-bfe2ff79dfbb')
        employee_role = Role(name='Employee', company=company)
        admin_role = Role(name='Company Admin', company=company)
        factory = APIRequestFactory()

        employee_request = factory.patch('/api/v1/client/settings/', {})
        employee_request.user = User(company=company, role=employee_role, is_active=True)
        admin_request = factory.patch('/api/v1/client/settings/', {})
        admin_request.user = User(company=company, role=admin_role, is_active=True)

        permission = IsCompanyAdmin()
        self.assertFalse(permission.has_permission(employee_request, None))
        self.assertTrue(permission.has_permission(admin_request, None))
