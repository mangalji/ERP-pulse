from django.db import migrations


def fix_login_audit_timestamps(apps, schema_editor):
    LoginActivity = apps.get_model('accounts', 'LoginActivity')
    AuditLog = apps.get_model('audit', 'AuditLog')

    db_alias = schema_editor.connection.alias

    login_activities = list(
        LoginActivity.objects.using(db_alias)
        .order_by('created_at', 'id')
    )

    audit_logs = list(
        AuditLog.objects.using(db_alias)
        .filter(
            module='auth',
            action='login',
            entity='User',
        )
        .order_by('id')
    )

    if len(login_activities) != len(audit_logs):
        raise RuntimeError(
            'Login activity and migrated audit login row counts do not match: '
            f'{len(login_activities)} != {len(audit_logs)}'
        )

    for login_activity, audit_log in zip(login_activities, audit_logs):
        audit_log.created_at = login_activity.created_at
        AuditLog.objects.using(db_alias).filter(pk=audit_log.pk).update(
            created_at=login_activity.created_at,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0006_migrate_login_activity_to_audit_log'),
    ]

    operations = [
        migrations.RunPython(
            fix_login_audit_timestamps,
            migrations.RunPython.noop,
        ),
    ]