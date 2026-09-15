from django.db import migrations, models


def migrate_role_permissions(apps, schema_editor):
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")

    for role in Role.objects.all():
        permission_codes = list(
            RolePermission.objects
            .filter(role_id=role.id)
            .values_list("permission__code", flat=True)
            .distinct()
            .order_by("permission__code")
        )

        role.permissions = permission_codes
        role.save(update_fields=["permissions"])


class Migration(migrations.Migration):

    dependencies = [
        ("rbac", "0003_remove_userrole_unique_user_role_delete_userrole"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="permissions",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="List of permission codes assigned to this role.",
            ),
        ),

        migrations.RunPython(
            migrate_role_permissions,
            migrations.RunPython.noop,
        ),

        migrations.DeleteModel(
            name="RolePermission",
        ),

        migrations.DeleteModel(
            name="Permission",
        ),
    ]