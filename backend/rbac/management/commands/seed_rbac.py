"""
Django management command to seed default RBAC data.

Creates default permissions and system roles if they don't already exist.

Usage::

    python manage.py seed_rbac
"""

from django.core.management.base import BaseCommand

from rbac.models import Permission, Role, RolePermission


DEFAULT_PERMISSIONS = [
    # (code, name, module)
    ('company.manage', 'Manage Company', 'company'),
    ('employee.manage', 'Manage Employee', 'employee'),
    ('ocr.upload', 'Upload OCR', 'ocr'),
    ('ocr.review', 'Review OCR', 'ocr'),
    ('ocr.export', 'Export OCR', 'ocr'),
    ('ai.chat', 'AI Chat', 'ai'),
    ('ai.history', 'AI History', 'ai'),
    ('reports.view', 'View Reports', 'reports'),
    ('reports.export', 'Export Reports', 'reports'),
    ('dashboard.view', 'View Dashboard', 'dashboard'),
    ('netsuite.connect', 'Connect NetSuite', 'netsuite'),
    ('netsuite.sync', 'Sync NetSuite', 'netsuite'),
    ('settings.manage', 'Manage Settings', 'settings'),
]

SYSTEM_ROLES = {
    'Super Admin': [
        'company.manage', 'employee.manage', 'ocr.upload', 'ocr.review',
        'ocr.export', 'ai.chat', 'ai.history', 'reports.view', 'reports.export',
        'dashboard.view', 'netsuite.connect', 'netsuite.sync', 'settings.manage',
    ],
    'Company Admin': [
        'employee.manage', 'ocr.upload', 'ocr.review', 'ocr.export',
        'ai.chat', 'ai.history', 'reports.view', 'reports.export',
        'dashboard.view', 'netsuite.connect', 'netsuite.sync', 'settings.manage',
    ],
    'Employee': [
        'ocr.upload', 'ai.chat', 'ai.history', 'reports.view',
        'dashboard.view',
    ],
}


class Command(BaseCommand):
    help = 'Seed default RBAC permissions and system roles.'

    def handle(self, *args, **options):
        # 1. Seed permissions
        created_perms = 0
        permission_map = {}
        for code, name, module in DEFAULT_PERMISSIONS:
            perm, created = Permission.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'module': module,
                    'is_system': True,
                },
            )
            if created:
                created_perms += 1
            permission_map[code] = perm

        self.stdout.write(
            self.style.SUCCESS(f'Permissions: {created_perms} created, '
                                f'{len(DEFAULT_PERMISSIONS)} total.')
        )

        # 2. Seed system roles + assign permissions
        for role_name, permission_codes in SYSTEM_ROLES.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                company=None,
                defaults={
                    'description': f'Default system role: {role_name}',
                    'is_system': True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Role created: {role_name}'))
            # 3. Assign permissions idempotently
            for code in permission_codes:
                perm = permission_map[code]
                _, perm_created = RolePermission.objects.get_or_create(
                    role=role,
                    permission=perm,
                )
                if perm_created:
                    self.stdout.write(
                        self.style.SUCCESS(f'  → {role_name}: {code}')
                    )

        self.stdout.write(self.style.SUCCESS('seed_rbac complete.'))