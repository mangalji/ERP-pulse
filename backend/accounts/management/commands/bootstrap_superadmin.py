import os

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from rbac.models import Role, UserRole


class Command(BaseCommand):
    help = "Create the initial platform Super Admin from environment variables."

    @transaction.atomic
    def handle(self, *args, **options):
        email = os.environ.get("INITIAL_SUPERADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("INITIAL_SUPERADMIN_PASSWORD", "")
        first_name = os.environ.get("INITIAL_SUPERADMIN_FIRST_NAME", "AGSuite")
        last_name = os.environ.get("INITIAL_SUPERADMIN_LAST_NAME", "Admin")

        if not email:
            raise CommandError("INITIAL_SUPERADMIN_EMAIL is not configured.")

        if not password:
            raise CommandError("INITIAL_SUPERADMIN_PASSWORD is not configured.")

        User = get_user_model()

        user = User.objects.filter(email=email).first()

        if user is None:
            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                company=None,
                is_active=True,
                is_staff=True,
                is_superuser=True,
                is_email_verified=True,
            )
            user.set_password(password)
            user.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Initial Super Admin created: {email}"
                )
            )
        else:
            changed = False

            if not user.is_superuser:
                user.is_superuser = True
                changed = True

            if not user.is_staff:
                user.is_staff = True
                changed = True

            if not user.is_active:
                user.is_active = True
                changed = True

            if not user.is_email_verified:
                user.is_email_verified = True
                changed = True

            if changed:
                user.save(
                    update_fields=[
                        "is_superuser",
                        "is_staff",
                        "is_active",
                        "is_email_verified",
                    ]
                )

            self.stdout.write(
                self.style.WARNING(
                    f"Super Admin already exists: {email}"
                )
            )

        role = Role.objects.filter(
            name="Super Admin",
            company__isnull=True,
        ).first()

        if role is None:
            raise CommandError(
                "Global 'Super Admin' role does not exist. "
                "Run seed_rbac before bootstrap_superadmin."
            )

        UserRole.objects.get_or_create(
            user=user,
            role=role,
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Super Admin RBAC role verified."
            )
        )