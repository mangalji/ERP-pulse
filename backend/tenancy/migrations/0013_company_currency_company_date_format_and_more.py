from django.db import migrations, models


def migrate_company_settings_to_company(apps, schema_editor):
    Company = apps.get_model('tenancy', 'Company')
    CompanySettings = apps.get_model('tenancy', 'CompanySettings')

    settings_rows = CompanySettings.objects.all()

    for settings in settings_rows:
        Company.objects.filter(id=settings.company_id).update(
            timezone=settings.timezone,
            currency=settings.currency,
            language=settings.language,
            date_format=settings.date_format,
            number_format=settings.number_format,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('tenancy', '0012_remove_companymodule_unique_company_module_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='company',
            name='currency',
            field=models.CharField(default='INR', max_length=10),
        ),
        migrations.AddField(
            model_name='company',
            name='date_format',
            field=models.CharField(default='DD/MM/YYYY', max_length=20),
        ),
        migrations.AddField(
            model_name='company',
            name='language',
            field=models.CharField(default='en', max_length=10),
        ),
        migrations.AddField(
            model_name='company',
            name='number_format',
            field=models.CharField(default='en-IN', max_length=20),
        ),
        migrations.AddField(
            model_name='company',
            name='timezone',
            field=models.CharField(default='UTC', max_length=100),
        ),
        migrations.RunPython(
            migrate_company_settings_to_company,
            migrations.RunPython.noop,
        ),
    ]