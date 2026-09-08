from unittest.mock import patch

from django.test import TestCase

from accounts.models import User
from rbac.models import Role


class FirstUserRbacSeedSignalTests(TestCase):

    @patch("rbac.signals.call_command")
    def test_first_user_triggers_rbac_seed_after_commit(self, mock_call_command):
        with self.captureOnCommitCallbacks(execute=True):
            user = User.objects.create_user(
                email="first@example.com",
                password="test-password",
                first_name="First",
                last_name="User",
            )

        self.assertIsNotNone(user)

        mock_call_command.assert_called_once_with(
            "seed_rbac",
            interactive=False,
            verbosity=0,
        )

    @patch("rbac.signals.call_command")
    def test_second_user_does_not_trigger_rbac_seed(self, mock_call_command):
        with self.captureOnCommitCallbacks(execute=True):
            User.objects.create_user(
                email="first@example.com",
                password="test-password",
                first_name="First",
                last_name="User",
            )

        mock_call_command.reset_mock()

        with self.captureOnCommitCallbacks(execute=True):
            User.objects.create_user(
                email="second@example.com",
                password="test-password",
                first_name="Second",
                last_name="User",
            )

        mock_call_command.assert_not_called()

    @patch("rbac.signals.call_command")
    def test_existing_rbac_roles_prevent_reseeding(self, mock_call_command):
        Role.objects.create(
            name="Super Admin",
            description="Platform administrator",
            is_system=True,
        )

        with self.captureOnCommitCallbacks(execute=True):
            User.objects.create_user(
                email="first@example.com",
                password="test-password",
                first_name="First",
                last_name="User",
            )

        mock_call_command.assert_not_called()