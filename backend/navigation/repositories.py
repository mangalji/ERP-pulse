from navigation.models import TransactionMenu


class TransactionMenuRepository:
    """Persistence-only access to the transaction menu tree."""

    def get_active_menu(self):
        return (
            TransactionMenu.objects
            .filter(is_active=True, key="transactions")
            .prefetch_related("items")
            .first()
        )

    def list_active_items(self, *, menu):
        return list(
            menu.items
            .filter(is_active=True)
            .select_related("parent_item")
            .order_by("sort_order", "id")
        )
