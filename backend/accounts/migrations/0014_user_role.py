from django.db import migrations, models
import django.db.models.deletion


def copy_user_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    UserRole = apps.get_model("rbac", "UserRole")

    for user_role in UserRole.objects.select_related("role").all():
        User.objects.filter(
            pk=user_role.user_id,
            role__isnull=True,
        ).update(role_id=user_role.role_id)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0013_user_current_netsuite_connection"),
        ("rbac", "0002_role_company_alter_role_name_and_more"),  # IMPORTANT: use your actual latest rbac migration
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="role",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="users",
                to="rbac.role",
            ),
        ),
        migrations.RunPython(
            copy_user_roles,
            migrations.RunPython.noop,
        ),
    ]