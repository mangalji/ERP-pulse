"""
Management command to expire old subscriptions and reset usage.
"""

from django.core.management.base import BaseCommand
from subscriptions.services import subscription_service


class Command(BaseCommand):
    help = 'Expire old subscriptions and reset daily usage counters'

    def handle(self, *args, **options):
        count = subscription_service.check_expiry()
        self.stdout.write(
            self.style.SUCCESS(f'Successfully expired {count} subscriptions.')
        )
