from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("navigation", "0011_internal_id_sequences"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="dynamiclevel2tab",
                    name="internal_id",
                    field=models.PositiveIntegerField(
                        unique=True,
                        editable=False,
                    ),
                ),
                migrations.AddField(
                    model_name="dynamiclevel3tab",
                    name="internal_id",
                    field=models.PositiveIntegerField(
                        unique=True,
                        editable=False,
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]