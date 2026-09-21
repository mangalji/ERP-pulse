from django.core.management import call_command
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import User
from rbac.models import Role


@receiver(post_save, sender=User)
def seed_rbac_after_first_user_created(sender, instance, created, **kwargs):
    """
    Automatically seed RBAC exactly when the first User is created.

    Rules:
    - Only runs for a newly created user.
    - Only triggers when the total user count becomes 1.
    - Does not run if RBAC roles already exist.
    - Runs only after the surrounding database transaction commits.
    """

    if not created:
        return

    if sender.objects.count() != 1:
        return

    if Role.objects.exists():
        return

    transaction.on_commit(
        lambda: call_command(
            "seed_rbac",
            verbosity=0,
        )
    )