import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netsuite', '0014_delete_netsuiteuserconnectionpreference'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NetSuiteBatchJob',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(max_length=16)),
                ('document_ids', models.JSONField(default=list)),
                ('connection_id', models.CharField(blank=True, max_length=64, null=True)),
                ('status', models.CharField(db_index=True, default='PENDING', max_length=16)),
                ('total', models.PositiveIntegerField(default=0)),
                ('completed', models.PositiveIntegerField(default=0)),
                ('succeeded', models.PositiveIntegerField(default=0)),
                ('failed', models.PositiveIntegerField(default=0)),
                ('results', models.JSONField(default=list)),
                ('error', models.TextField(blank=True, default='')),
                ('lease_owner', models.CharField(blank=True, default='', max_length=80)),
                ('lease_expires_at', models.DateTimeField(blank=True, null=True)),
                ('attempt_count', models.PositiveSmallIntegerField(default=0)),
                ('next_attempt_at', models.DateTimeField(blank=True, null=True)),
                ('queued_at', models.DateTimeField(blank=True, null=True)),
                ('queued_via', models.CharField(blank=True, default='', max_length=16)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='netsuite_batch_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'netsuite_batch_job',
                'ordering': ['-created_at'],
            },
        ),
    ]