from django.contrib import admin

from .models import TransactionMenu, TransactionMenuItem


class TransactionMenuItemInline(admin.TabularInline):
    model = TransactionMenuItem
    extra = 0
    fields = (
        "name",
        "key",
        "parent_item",
        "route",
        "query_params",
        "sort_order",
        "is_active",
        "requires_netsuite",
    )
    ordering = ("sort_order", "id")


@admin.register(TransactionMenu)
class TransactionMenuAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "key",
        "sort_order",
        "is_active",
        "requires_netsuite",
    )
    list_filter = ("is_active", "requires_netsuite")
    search_fields = ("name", "key", "module_code")
    ordering = ("sort_order", "id")
    inlines = (TransactionMenuItemInline,)


@admin.register(TransactionMenuItem)
class TransactionMenuItemAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "key",
        "menu",
        "parent_item",
        "route",
        "sort_order",
        "is_active",
        "requires_netsuite",
    )
    list_filter = ("menu", "is_active", "requires_netsuite")
    search_fields = ("name", "key", "route", "module_code")
    ordering = ("menu", "parent_item", "sort_order", "id")
