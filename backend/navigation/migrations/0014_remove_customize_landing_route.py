from django.db import migrations


def remove_customize_landing_route(apps, schema_editor):
    DynamicLevel2Tab = apps.get_model("navigation", "DynamicLevel2Tab")

    DynamicLevel2Tab.objects.filter(
        key="settings-customize",
    ).update(
        route="",
    )


def restore_customize_landing_route(apps, schema_editor):
    DynamicLevel2Tab = apps.get_model("navigation", "DynamicLevel2Tab")

    DynamicLevel2Tab.objects.filter(
        key="settings-customize",
    ).update(
        route="/app/settings/customize",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("navigation", "0013_alter_dynamiclevel2tab_options_and_more"),
    ]

    operations = [
        migrations.RunPython(
            remove_customize_landing_route,
            restore_customize_landing_route,
        ),
    ]