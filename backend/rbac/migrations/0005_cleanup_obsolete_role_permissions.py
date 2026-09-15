from django.db import migrations


OBSOLETE_PERMISSIONS = {
    'ai.chat',
    'ai.history',
    'reports.view',
    'reports.export',
}


def remove_obsolete_permissions(apps, schema_editor):
    Role = apps.get_model('rbac', 'Role')

    for role in Role.objects.all():
        current_permissions = role.permissions or []

        cleaned_permissions = [
            code
            for code in current_permissions
            if code not in OBSOLETE_PERMISSIONS
        ]

        if cleaned_permissions != current_permissions:
            role.permissions = cleaned_permissions
            role.save(update_fields=['permissions'])


class Migration(migrations.Migration):

    dependencies = [
        (
            'rbac',
            '0004_remove_permission_permission_module_idx_and_more',
        ),
    ]

    operations = [
        migrations.RunPython(
            remove_obsolete_permissions,
            migrations.RunPython.noop,
        ),
    ]