import uuid
from django.conf import settings
from django.db import models


class TransactionMenu(models.Model):
    """Single top-level parent record for the transaction menu."""

    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    name = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)
    icon = models.CharField(max_length=50, blank=True, default="transaction")
    module_code = models.CharField(max_length=80, blank=True, default="")
    requires_netsuite = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "navigation_transaction_menu"
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(
                fields=["is_active", "sort_order"],
                name="nav_tx_menu_active_order_idx",
            ),
        ]

    def __str__(self):
        return self.name


class TransactionMenuItem(models.Model):
    """All first-level and leaf transaction menu items in one child table.

    ``parent_item`` is self-referencing so the same table can represent any
    depth without creating separate tables for Sales, Purchases, Orders, etc.
    """

    id = models.UUIDField(
    primary_key=True,
    default=uuid.uuid4,
    editable=False,
)
    menu = models.ForeignKey(
        TransactionMenu,
        on_delete=models.CASCADE,
        related_name="items",
    )
    parent_item = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    name = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)
    route = models.CharField(max_length=255, blank=True, default="")
    query_params = models.JSONField(default=dict, blank=True)
    icon = models.CharField(max_length=50, blank=True, default="transaction")
    module_code = models.CharField(max_length=80, blank=True, default="")
    requires_netsuite = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "navigation_transaction_menu_item"
        ordering = ["sort_order", "id"]
        indexes = [
            models.Index(
                fields=["menu", "parent_item", "is_active", "sort_order"],
                name="nav_tx_item_tree_idx",
            ),
            models.Index(
                fields=["is_active", "sort_order"],
                name="nav_tx_item_active_order_idx",
            ),
        ]

    def __str__(self):
        return self.name


class DynamicTopLevelTab(models.Model):
    id = models.UUIDField(
    primary_key=True,
    default=uuid.uuid4,
    editable=False,
)

    name = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)

    route = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # query_params = models.JSONField(
    #     default=dict,
    #     blank=True,
    # )

    # feature_code = models.CharField(
    #     max_length=120,
    #     blank=True,
    #     default="",
    # )

    # icon = models.CharField(
    #     max_length=50,
    #     blank=True,
    #     default="",
    # )

    sort_order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dynamic_top_level_tab"
        ordering = ["sort_order", "id"]

        indexes = [
            models.Index(
                fields=["is_active", "sort_order"],
                name="dyn_top_tab_active_order_idx",
            ),
        ]

    def __str__(self):
        return self.name


class DynamicLevel2Tab(models.Model):
    id = models.UUIDField(
    primary_key=True,
    default=uuid.uuid4,
    editable=False,
)

    parent_tab = models.ForeignKey(
        DynamicTopLevelTab,
        on_delete=models.CASCADE,
        related_name="level2_tabs",
    )

    name = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)

    route = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # query_params = models.JSONField(
    #     default=dict,
    #     blank=True,
    # )

    # feature_code = models.CharField(
    #     max_length=120,
    #     blank=True,
    #     default="",
    # )

    # icon = models.CharField(
    #     max_length=50,
    #     blank=True,
    #     default="",
    # )

    sort_order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dynamic_level2_tab"
        ordering = ["sort_order", "id"]

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
    id = models.UUIDField(
    primary_key=True,
    default=uuid.uuid4,
    editable=False,
)

    parent_tab = models.ForeignKey(
        DynamicLevel2Tab,
        on_delete=models.CASCADE,
        related_name="level3_tabs",
    )

    name = models.CharField(max_length=120)
    key = models.SlugField(max_length=120, unique=True)

    route = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # query_params = models.JSONField(
    #     default=dict,
    #     blank=True,
    # )

    # feature_code = models.CharField(
    #     max_length=120,
    #     blank=True,
    #     default="",
    # )

    # icon = models.CharField(
    #     max_length=50,
    #     blank=True,
    #     default="",
    # )

    sort_order = models.PositiveIntegerField(default=0)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dynamic_level3_tab"
        ordering = ["sort_order", "id"]

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

    id = models.UUIDField(
    primary_key=True,
    default=uuid.uuid4,
    editable=False,
)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="navigation_access",
    )
    top_level_tab = models.ForeignKey(
        DynamicTopLevelTab,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="user_access_rows",
    )
    level2_tab = models.ForeignKey(
        DynamicLevel2Tab,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="user_access_rows",
    )
    level3_tab = models.ForeignKey(
        DynamicLevel3Tab,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="user_access_rows",
    )

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
