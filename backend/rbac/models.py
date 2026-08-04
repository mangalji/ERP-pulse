"""
RBAC models — Roles, Permissions, and their relationships.

System roles and permissions (``is_system=True``) cannot be deleted.

Roles are scoped:
- ``company=None`` → global (AGSuite platform) role
- ``company=<Company>`` → company-specific role created by that company

The ``company.name + role name`` pair is unique for company roles; global
roles keep a unique name across the whole table.
"""

from django.conf import settings
from django.db import models

from core.models import BaseModel
from tenancy.models import Company


class Role(BaseModel):
    """A named set of permissions, either global or company-specific."""

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

    def __str__(self) -> str:
        if self.company_id:
            return f'{self.name} ({self.company.name})'
        return f'{self.name} (Global)'


class Permission(BaseModel):
    """A single permission code."""

    code = models.CharField(max_length=150, unique=True)
    name = models.CharField(max_length=255)
    module = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = 'permission'
        ordering = ['module', 'name']
        indexes = [
            models.Index(fields=['module'], name='permission_module_idx'),
            models.Index(fields=['code'], name='permission_code_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.code} ({self.module})'


class RolePermission(BaseModel):
    """Many-to-many link between Role and Permission."""

    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_permissions')

    class Meta:
        db_table = 'role_permission'
        constraints = [
            models.UniqueConstraint(fields=['role', 'permission'], name='unique_role_permission'),
        ]

    def __str__(self) -> str:
        return f'{self.role.name} → {self.permission.code}'


class UserRole(BaseModel):
    """Many-to-many link between User and Role."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')

    class Meta:
        db_table = 'user_role'
        constraints = [
            models.UniqueConstraint(fields=['user', 'role'], name='unique_user_role'),
        ]

    def __str__(self) -> str:
        return f'{self.user.email} → {self.role.name}'