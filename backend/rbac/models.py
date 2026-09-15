"""
RBAC models — Roles, Permissions, and their relationships.

System roles and permissions (``is_system=True``) cannot be deleted.

Roles are scoped:
- ``company=None`` → global (AGSuite platform) role
- ``company=<Company>`` → company-specific role created by that company

The ``company.name + role name`` pair is unique for company roles; global
roles keep a unique name across the whole table.
"""
from django.db import models
from core.models import BaseModel
from tenancy.models import Company


class Role(BaseModel):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    is_system = models.BooleanField(default=False)

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='roles',
        help_text='Company this role belongs to. NULL = global AGSuite role.',
    )

    permissions = models.JSONField(
        default=list,
        blank=True,
        help_text='List of permission codes assigned to this role.',
    )

    class Meta:
        db_table = 'role'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'company'],
                name='unique_role_name_company',
            ),
            models.UniqueConstraint(
                fields=['name'],
                condition=models.Q(company__isnull=True),
                name='unique_role_name_global',
            ),
        ]

    def __str__(self):
        if self.company_id:
            return f'{self.name} ({self.company.name})'
        return f'{self.name} (Global)'