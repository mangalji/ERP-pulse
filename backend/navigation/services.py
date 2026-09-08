from navigation.repositories import TransactionMenuRepository
from netsuite.repositories import NetSuiteConnectionRepository


class TransactionMenuService:
    """
    Build the transaction navigation for the authenticated company user.

    Visibility is intentionally based on the user's currently authorized
    NetSuite connection. The NetSuite repository already resolves that
    differently for Company Admin vs Employee, including EmployeeConnection
    assignment and current-connection preference.
    """

    def __init__(self, *, repository=None, netsuite_repository=None):
        self.repository = repository or TransactionMenuRepository()
        self.netsuite_repository = (
            netsuite_repository or NetSuiteConnectionRepository()
        )

    def get_menu_for_user(self, *, user):
        if not getattr(user, "is_authenticated", False):
            return None

        company = getattr(user, "company", None)
        if company is None:
            return None

        current_connection = self.netsuite_repository.get_for_user(user)
        if current_connection is None:
            return None

        menu = self.repository.get_active_menu()
        if menu is None:
            return None

        items = self.repository.list_active_items(menu=menu)

        # For this transaction module every seeded item requires NetSuite.
        # Keep the check data-driven so future menu entries can opt out.
        items = [
            item
            for item in items
            if not item.requires_netsuite or current_connection is not None
        ]

        by_parent = {}
        for item in items:
            by_parent.setdefault(item.parent_item_id, []).append(item)

        def serialize_item(item):
            return {
                "id": item.id,
                "name": item.name,
                "key": item.key,
                "route": item.route,
                "query_params": item.query_params or {},
                "icon": item.icon,
                "module_code": item.module_code,
                "requires_netsuite": item.requires_netsuite,
                "sort_order": item.sort_order,
                "children": [
                    serialize_item(child)
                    for child in by_parent.get(item.id, [])
                ],
            }

        return {
            "id": menu.id,
            "name": menu.name,
            "key": menu.key,
            "icon": menu.icon,
            "module_code": menu.module_code,
            "requires_netsuite": menu.requires_netsuite,
            "sort_order": menu.sort_order,
            "children": [
                serialize_item(item)
                for item in by_parent.get(None, [])
            ],
        }


transaction_menu_service = TransactionMenuService()
