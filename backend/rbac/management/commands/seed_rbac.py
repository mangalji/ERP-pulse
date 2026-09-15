from django.core.management.base import BaseCommand

from rbac.models import Role


DEFAULT_PERMISSIONS = [
    'company.manage',
    'dashboard.view',
    'employee.manage',
    'netsuite.connect',
    'netsuite.sync',
    'ocr.export',
    'ocr.review',
    'ocr.upload',
    'settings.manage',
]


SYSTEM_ROLES = {
    'Super Admin': [
        'company.manage',
        'dashboard.view',
        'employee.manage',
        'netsuite.connect',
        'netsuite.sync',
        'ocr.export',
        'ocr.review',
        'ocr.upload',
        'settings.manage',
    ],

    'Company Admin': [
        'dashboard.view',
        'employee.manage',
        'netsuite.connect',
        'netsuite.sync',
        'ocr.export',
        'ocr.review',
        'ocr.upload',
        'settings.manage',
    ],

    'Employee': [
        'dashboard.view',
        'ocr.upload',
    ],
}


class Command(BaseCommand):
    help = 'Seed system roles and their permissions.'

    def handle(self, *args, **options):
        for role_name, permission_codes in SYSTEM_ROLES.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                company=None,
                defaults={
                    'description': f'System role: {role_name}',
                    'is_system': True,
                    'permissions': permission_codes,
                },
            )

            if not created:
                role.permissions = permission_codes
                role.is_system = True
                role.save(
                    update_fields=[
                        'permissions',
                        'is_system',
                    ]
                )

            action = 'Created' if created else 'Updated'

            self.stdout.write(
                self.style.SUCCESS(
                    f'{action} role: {role_name}'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                'RBAC roles and permissions seeded successfully.'
            )
        )