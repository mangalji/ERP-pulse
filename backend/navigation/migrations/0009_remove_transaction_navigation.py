from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        (
            "navigation",
            "0008_remove_dynamiclevel2tab_feature_code_and_more",
        ),
    ]

    operations = [
        migrations.DeleteModel(
            name="TransactionMenuItem",
        ),
        migrations.DeleteModel(
            name="TransactionMenu",
        ),
    ]