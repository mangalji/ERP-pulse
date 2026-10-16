from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import Gender
from invitations.models import Invitation, InvitationStatus
from invitations.services import invitation_service
from rbac.models import Role
from superadmin.models import Plan
from tenancy.models import Company, CompanyStatus


User = get_user_model()


class SharedCompanyInvitationFlowTests(TestCase):
    def setUp(self):
        plan = Plan.objects.create(name='Invitation test plan')
        self.company = Company.objects.create(
            name='Invitation Test Company',
            code='INVITE-TEST',
            status=CompanyStatus.ACTIVE,
            plan=plan,
            plan_start_date=timezone.localdate(),
            plan_end_date=timezone.localdate() + timedelta(days=30),
        )
        self.role = Role.objects.create(name='Invitation Test Employee')
        self.actor = User.objects.create_user(
            email='platform-admin@example.com',
            password='safe-password',
            first_name='Platform',
            last_name='Admin',
            is_staff=True,
            is_active=True,
            is_email_verified=True,
        )

    @patch.object(invitation_service, '_send_invitation_email', return_value=True)
    def test_creates_pending_company_user_and_invitation(self, send_email):
        result = invitation_service.create_company_user_and_invite(
            company=self.company,
            acting_user=self.actor,
            email='new.employee@example.com',
            first_name='New',
            last_name='Employee',
            country='IN',
            gender=Gender.PREFER_NOT_TO_SAY,
            role_id=self.role.id,
            mobile_number='+919999999999',
            designation='Analyst',
            department='Operations',
        )

        user = result['user']
        invitation = result['invitation']
        user.refresh_from_db()

        self.assertEqual(user.company_id, self.company.id)
        self.assertEqual(user.role_id, self.role.id)
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(invitation.email, user.email)
        self.assertEqual(invitation.company_id, self.company.id)
        self.assertEqual(invitation.role_id, self.role.id)
        self.assertEqual(invitation.status, InvitationStatus.PENDING)
        self.assertTrue(result['invitation_email_sent'])
        send_email.assert_called_once_with(invitation)

    def test_rejects_the_platform_super_admin_role_for_company_user(self):
        super_admin_role = Role.objects.create(name='Super Admin')

        with self.assertRaisesMessage(
            ValueError,
            'The Super Admin role cannot be assigned to a company user.',
        ):
            invitation_service.create_company_user_and_invite(
                company=self.company,
                acting_user=self.actor,
                email='not-super-admin@example.com',
                first_name='Not',
                last_name='Platform',
                country='IN',
                gender=Gender.PREFER_NOT_TO_SAY,
                role_id=super_admin_role.id,
            )

        self.assertFalse(
            User.objects.filter(email='not-super-admin@example.com').exists()
        )
