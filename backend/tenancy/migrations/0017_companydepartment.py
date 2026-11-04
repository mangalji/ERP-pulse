from django.db import migrations, models
import django.db.models.deletion
from django.db.models.functions import Lower
import uuid


class Migration(migrations.Migration):
    dependencies = [('tenancy', '0016_company_status_lifecycle_cleanup')]

    operations = [
        migrations.CreateModel(
            name='CompanyDepartment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('name', models.CharField(max_length=150)),
                ('is_active', models.BooleanField(default=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='department_options', to='tenancy.company')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='accounts.user')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='accounts.user')),
            ],
            options={'db_table': 'company_department', 'ordering': ['name']},
        ),
        migrations.AddConstraint(
            model_name='companydepartment',
            constraint=models.UniqueConstraint(Lower('name'), 'company', name='unique_company_department_name_ci'),
        ),
    ]
