from django.db import migrations, models
from django.utils import timezone


def normalize_legacy_company_statuses(apps, schema_editor):
    Company = apps.get_model("tenancy", "Company")

    today = timezone.now().date()

    for company in Company.objects.filter(
        status__in=["TRIAL", "EXPIRED"]
    ).iterator():

        if company.is_deleted:
            company.status = "SUSPENDED"
            company.suspension_reason = "DELETED"

        elif company.suspension_reason == "MANUAL":
            company.status = "SUSPENDED"
            company.suspension_reason = "MANUAL"

        elif (
            company.plan_id
            and (
                company.plan_start_date is None
                or company.plan_start_date <= today
            )
            and (
                company.plan_end_date is None
                or company.plan_end_date >= today
            )
        ):
            company.status = "ACTIVE"
            company.suspension_reason = "NONE"

        else:
            company.status = "SUSPENDED"
            company.suspension_reason = "PLAN"

        company.save(
            update_fields=[
                "status",
                "suspension_reason",
                "updated_at",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        (
            "tenancy",
            "0015_company_plan_company_plan_end_date_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            normalize_legacy_company_statuses,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="company",
            name="status",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("ACTIVE", "Active"),
                    ("SUSPENDED", "Suspended"),
                ],
                default="SUSPENDED",
                db_index=True,
            ),
        ),
    ]