from django.db import migrations


def delete_profile_picture_files(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.exclude(profile_pic__isnull=True).exclude(profile_pic="").iterator():
        try:
            user.profile_pic.storage.delete(user.profile_pic.name)
        except Exception:
            # Removing the database reference still prevents any new access;
            # storage cleanup is best-effort for unavailable legacy backends.
            pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0015_user_preferred_ocr_template"),
    ]

    operations = [
        migrations.RunPython(delete_profile_picture_files, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="user",
            name="profile_pic",
        ),
    ]
