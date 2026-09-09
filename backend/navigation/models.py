import uuid
from django.conf import settings
from django.db import models

class DynamicTopLevelTab(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    name = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)
    route = models.CharField(max_length=255,blank=True,default="")
    query_params = models.JSONField(default=dict,blank=True)
    internal_id = models.PositiveIntegerField(unique=True,editable=False)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dynamic_top_level_tab"
        ordering = ["sort_order", "internal_id"]

        indexes = [
            models.Index(
                fields=["is_active", "sort_order"],
                name="dyn_top_tab_active_order_idx",
            ),
        ]

    def __str__(self):
        return self.name


class DynamicLevel2Tab(models.Model):

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False,)
    parent_tab = models.ForeignKey(DynamicTopLevelTab,on_delete=models.CASCADE,related_name="level2_tabs",)
    name = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)
    route = models.CharField(max_length=255,blank=True,default="",)
    query_params = models.JSONField(default=dict,blank=True,)
    sort_order = models.PositiveIntegerField(default=0)
    internal_id = models.PositiveIntegerField(unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dynamic_level2_tab"
        ordering = ["sort_order", "internal_id"]

        indexes = [
            models.Index(
                fields=[
                    "parent_tab",
                    "is_active",
                    "sort_order",
                ],
                name="dyn_l2_parent_order_idx",
            ),
        ]

    def __str__(self):
        return self.name

class DynamicLevel3Tab(models.Model):

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    parent_tab = models.ForeignKey(DynamicLevel2Tab,on_delete=models.CASCADE,related_name="level3_tabs")
    name = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)
    route = models.CharField(max_length=255,blank=True,default="")
    query_params = models.JSONField(default=dict,blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    internal_id = models.PositiveIntegerField(unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dynamic_level3_tab"
        ordering = ["sort_order", "internal_id"]

        indexes = [
            models.Index(
                fields=[
                    "parent_tab",
                    "is_active",
                    "sort_order",
                ],
                name="dyn_l3_parent_order_idx",
            ),
        ]

    def __str__(self):
        return self.name


class NavigationUserAccess(models.Model):
    """Per-user navigation override for a single master navigation item.

    A missing row means the item uses the normal/default visibility.  An
    explicit row allows Company Admin to show or remove an item for one user
    without changing the master navigation hierarchy.
    """

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,related_name="navigation_access")
    top_level_tab = models.ForeignKey(DynamicTopLevelTab,null=True,blank=True,on_delete=models.CASCADE,related_name="user_access_rows")
    level2_tab = models.ForeignKey(DynamicLevel2Tab,null=True,blank=True,on_delete=models.CASCADE,related_name="user_access_rows")
    level3_tab = models.ForeignKey(DynamicLevel3Tab,null=True,blank=True,on_delete=models.CASCADE,related_name="user_access_rows")
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "navigation_user_access"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        top_level_tab__isnull=False,
                        level2_tab__isnull=True,
                        level3_tab__isnull=True,
                    )
                    | models.Q(
                        top_level_tab__isnull=True,
                        level2_tab__isnull=False,
                        level3_tab__isnull=True,
                    )
                    | models.Q(
                        top_level_tab__isnull=True,
                        level2_tab__isnull=True,
                        level3_tab__isnull=False,
                    )
                ),
                name="nav_user_access_exactly_one_level",
            ),
            models.UniqueConstraint(
                fields=["user", "top_level_tab"],
                condition=models.Q(top_level_tab__isnull=False),
                name="nav_user_access_user_top_unique",
            ),
            models.UniqueConstraint(
                fields=["user", "level2_tab"],
                condition=models.Q(level2_tab__isnull=False),
                name="nav_user_access_user_l2_unique",
            ),
            models.UniqueConstraint(
                fields=["user", "level3_tab"],
                condition=models.Q(level3_tab__isnull=False),
                name="nav_user_access_user_l3_unique",
            ),
        ]
    indexes = [
        models.Index(
            fields=["user", "is_visible"],
            name="nav_user_access_user_vis_idx",
        ),
    ]

    def __str__(self):
        return f"{self.user_id}: navigation access"
