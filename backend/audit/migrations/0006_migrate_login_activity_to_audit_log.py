from django.db import migrations


def migrate_login_activity_to_audit_log(apps, schema_editor):
    LoginActivity = apps.get_model('accounts', 'LoginActivity')
    AuditLog = apps.get_model('audit', 'AuditLog')

    login_activities = (
        LoginActivity.objects
        .select_related('user')
        .order_by('created_at')
    )

    db_alias = schema_editor.connection.alias

    audit_logs = []

    for login_activity in login_activities:
        user = login_activity.user

        audit_logs.append(
            AuditLog(
                company_id=user.company_id,
                user_id=user.id,
                module='auth',
                action='login',
                entity='User',
                entity_id=str(user.id),
                old_value=None,
                new_value=None,
                ip_address=login_activity.ip_address,
                user_agent=login_activity.user_agent,
                created_at=login_activity.created_at,
            )
        )

    if audit_logs:
        AuditLog.objects.using(db_alias).bulk_create(
            audit_logs,
            batch_size=100,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0005_auditlog_user_agent'),
        ('accounts', '0011_alter_user_company'),
    ]

    operations = [
        migrations.RunPython(
            migrate_login_activity_to_audit_log,
            migrations.RunPython.noop,
        ),
    ]