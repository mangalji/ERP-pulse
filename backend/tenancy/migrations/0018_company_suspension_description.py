from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0017_companydepartment"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="suspension_description",
            field=models.TextField(
                blank=True,
                help_text="Additional explanation entered by the Super Admin for a manual suspension.",
                null=True,
            ),
        ),
    ]
