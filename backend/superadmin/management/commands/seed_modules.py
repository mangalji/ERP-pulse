"""
Seed default system modules.

Creates the standard set of feature modules if they do not already exist.
Safe to run repeatedly — uses get_or_create.
"""

from django.core.management.base import BaseCommand
from tenancy.models import Module

DEFAULT_MODULES = [
    {
        'name': 'Dashboard',
        'code': 'dashboard',
        'display_name': 'Dashboard',
        'icon': 'layout-dashboard',
        'description': 'Company dashboard with overview metrics.',
        'sort_order': 0,
        'is_system': True,
    },
    {
        'name': 'OCR',
        'code': 'ocr',
        'display_name': 'OCR Jobs',
        'icon': 'scan',
        'description': 'Optical character recognition for document processing.',
        'sort_order': 10,
        'is_system': True,
    },
    {
        'name': 'Invoice Reader',
        'code': 'invoice_reader',
        'display_name': 'Invoice Reader',
        'icon': 'file-text',
        'description': 'Intelligent invoice extraction and data capture.',
        'sort_order': 20,
        'is_system': True,
    },
    {
        'name': 'AI Assistant',
        'code': 'ai',
        'display_name': 'AI Assistant',
        'icon': 'sparkle',
        'description': 'AI-powered assistant for business queries.',
        'sort_order': 30,
        'is_system': True,
    },
    {
        'name': 'Reports Engine',
        'code': 'reports',
        'display_name': 'Reports Engine',
        'icon': 'printer',
        'description': 'Generate and schedule custom business reports.',
        'sort_order': 40,
        'is_system': True,
    },
    {
        'name': 'Business Intelligence',
        'code': 'bi',
        'display_name': 'Business Intelligence',
        'icon': 'chart',
        'description': 'BI analytics and dashboards for sales, purchase, inventory, and finance.',
        'sort_order': 50,
        'is_system': True,
    },
    {
        'name': 'NetSuite',
        'code': 'netsuite',
        'display_name': 'NetSuite Integration',
        'icon': 'cube',
        'description': 'NetSuite integration for data sync.',
        'sort_order': 60,
        'is_system': True,
    },
    {
        'name': 'Employees',
        'code': 'employees',
        'display_name': 'Employees',
        'icon': 'users',
        'description': 'Employee management and directory.',
        'sort_order': 70,
        'is_system': True,
    },
    {
        'name': 'Notifications',
        'code': 'notifications',
        'display_name': 'Notifications',
        'icon': 'bell',
        'description': 'User notifications and alerts.',
        'sort_order': 80,
        'is_system': True,
    },
]


class Command(BaseCommand):
    help = "Seed default system modules (idempotent)"

    def handle(self, *args, **options):
        created = []
        for spec in DEFAULT_MODULES:
            obj, was_created = Module.objects.get_or_create(
                code=spec['code'],
                defaults=spec,
            )
            if was_created:
                created.append(obj)
                self.stdout.write(self.style.SUCCESS(f"Created module: {obj.name}"))
        self.stdout.write(
            self.style.SUCCESS(f"{'No new modules needed. ' if not created else ''}"
                               f"Total modules in database: {Module.objects.count()}")
        )
