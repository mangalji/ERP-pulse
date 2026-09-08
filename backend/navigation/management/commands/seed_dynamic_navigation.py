from django.core.management.base import BaseCommand
from navigation.models import (
    DynamicTopLevelTab,
    DynamicLevel2Tab,
    DynamicLevel3Tab,
)


class Command(BaseCommand):
    help = "Seed the initial dynamic navigation hierarchy."

    def handle(self, *args, **options):
        # top_tabs = [
        #     {
        #         "key": "dashboard",
        #         "name": "Dashboard",
        #         "route": "/app",
        #         "feature_code": "dashboard",
        #         "icon": "dashboard",
        #         "sort_order": 10,
        #     },
        #     {
        #         "key": "ocr",
        #         "name": "OCR",
        #         "route": "/app/ocr-test",
        #         "feature_code": "ocr",
        #         "icon": "ocr",
        #         "sort_order": 20,
        #     },
        #     {
        #         "key": "ai",
        #         "name": "AI",
        #         "route": "/app/ai-assistant",
        #         "feature_code": "ai",
        #         "icon": "ai",
        #         "sort_order": 30,
        #     },
        #     {
        #         "key": "reports",
        #         "name": "Reports",
        #         "route": "/app/reports",
        #         "feature_code": "reports",
        #         "icon": "reports",
        #         "sort_order": 40,
        #     },
        #     {
        #         "key": "company_settings",
        #         "name": "Company Settings",
        #         "route": "/app/settings",
        #         "feature_code": "company_settings",
        #         "icon": "settings",
        #         "sort_order": 50,
        #     },
        #     {
        #         "key": "netsuite",
        #         "name": "NetSuite",
        #         "route": "/app/integrations/netsuite",
        #         "feature_code": "netsuite",
        #         "icon": "netsuite",
        #         "sort_order": 60,
        #     },
        #     {
        #         "key": "transactions",
        #         "name": "Transactions",
        #         "route": "",
        #         "feature_code": "transactions",
        #         "icon": "transactions",
        #         "sort_order": 70,
        #     },
        # ]
        top_tabs = [
    {
        "key": "dashboard",
        "name": "Dashboard",
        "route": "/app",
        "feature_code": "dashboard",
        "icon": "dashboard",
        "sort_order": 10,
    },
    {
        "key": "invoice_reader",
        "name": "Invoice Reader",
        "route": "/app/invoice-reader",
        "feature_code": "invoice_reader",
        "icon": "invoice",
        "sort_order": 20,
    },
    {
        "key": "ocr_jobs",
        "name": "OCR Jobs",
        "route": "/app/ocr-jobs",
        "feature_code": "ocr",
        "icon": "ocr",
        "sort_order": 30,
    },
    {
        "key": "ai_assistant",
        "name": "AI Assistant",
        "route": "/app/ai-assistant",
        "feature_code": "ai",
        "icon": "ai",
        "sort_order": 40,
    },
    {
        "key": "employees",
        "name": "Employees",
        "route": "/app/employees",
        "feature_code": "employees",
        "icon": "employees",
        "sort_order": 50,
    },
    {
        "key": "reports",
        "name": "Reports",
        "route": "/app/reports",
        "feature_code": "reports",
        "icon": "reports",
        "sort_order": 60,
    },
    {
        "key": "reports_engine",
        "name": "Reports Engine",
        "route": "/app/reports-engine",
        "feature_code": "reports_engine",
        "icon": "reports",
        "sort_order": 70,
    },
    {
        "key": "analytics",
        "name": "Analytics",
        "route": "/app/analytics",
        "feature_code": "bi",
        "icon": "analytics",
        "sort_order": 80,
    },
    {
        "key": "notifications",
        "name": "Notifications",
        "route": "/app/notifications",
        "feature_code": "notifications",
        "icon": "notifications",
        "sort_order": 90,
    },
    {
        "key": "company_settings",
        "name": "Company Settings",
        "route": "/app/settings",
        "feature_code": "company_settings",
        "icon": "settings",
        "sort_order": 100,
    },
    {
        "key": "transactions",
        "name": "Transactions",
        "route": "",
        "feature_code": "transactions",
        "icon": "transactions",
        "sort_order": 110,
    },
]

        top_map = {}

        for data in top_tabs:
            tab, _ = DynamicTopLevelTab.objects.update_or_create(
                key=data["key"],
                defaults={
                    **data,
                    "is_active": True,
                },
            )

            top_map[tab.key] = tab

        transactions = top_map["transactions"]
        reports_engine = top_map["reports_engine"]
        settings = top_map["company_settings"]

        reports_engine = top_map["reports_engine"]

        level2_tabs = [
            {
                "parent": transactions,
                "key": "sales",
                "name": "Sales",
                "feature_code": "transactions.sales",
                "sort_order": 10,
            },
            {
                "parent": transactions,
                "key": "purchases",
                "name": "Purchases",
                "feature_code": "transactions.purchases",
                "sort_order": 20,
            },
            {
                "parent": reports_engine,
                "key": "reports_generate",
                "name": "Generate Report",
                "route": "/app/reports-engine/generate",
                "feature_code": "reports.generate",
                "icon": "reports",
                "sort_order": 10,
            },
            {
                "parent": reports_engine,
                "key": "reports_schedules",
                "name": "Scheduled Reports",
                "route": "/app/reports-engine/schedules",
                "feature_code": "reports.schedules",
                "icon": "reports",
                "sort_order": 20,
            },
            {
                "parent": reports_engine,
                "key": "reports_history",
                "name": "Report History",
                "route": "/app/reports-engine/history",
                "feature_code": "reports.history",
                "icon": "reports",
                "sort_order": 30,
            },
            {
                "parent": reports_engine,
                "key": "reports_templates",
                "name": "Templates",
                "route": "/app/reports-engine/templates",
                "feature_code": "reports.templates",
                "icon": "reports",
                "sort_order": 40,
            },
            {
                "parent": settings,
                "key": "company_info",
                "name": "Company Info",
                "route": "/app/settings",
                "feature_code": "company_settings.info",
                "sort_order": 10,
            },
            {
                "parent": settings,
                "key": "customize",
                "name": "Customize",
                "feature_code": "company_settings.customize",
                "sort_order": 20,
            },
]

        level2_map = {}

        for data in level2_tabs:
            parent = data.pop("parent")

            tab, _ = DynamicLevel2Tab.objects.update_or_create(
                key=data["key"],
                defaults={
                    **data,
                    "parent_tab": parent,
                    "is_active": True,
                },
            )

            level2_map[tab.key] = tab

        sales = level2_map["sales"]
        purchases = level2_map["purchases"]

        level3_tabs = [
            {
                "parent": sales,
                "key": "sales_orders",
                "name": "Sales Orders",
                "route": "/app/transactions",
                "query_params": {"view": "sales_orders"},
                "feature_code": "transactions.sales_orders",
                "sort_order": 10,
            },
            {
                "parent": sales,
                "key": "cash_sales",
                "name": "Cash Sales",
                "route": "/app/transactions",
                "query_params": {"view": "cash_sales"},
                "feature_code": "transactions.cash_sales",
                "sort_order": 20,
            },
            {
                "parent": purchases,
                "key": "purchase_orders",
                "name": "Purchase Orders",
                "route": "/app/transactions",
                "query_params": {"view": "purchase_orders"},
                "feature_code": "transactions.purchase_orders",
                "sort_order": 10,
            },
            {
                "parent": purchases,
                "key": "vendor_payments",
                "name": "Vendor Payments",
                "route": "/app/transactions",
                "query_params": {"view": "vendor_payments"},
                "feature_code": "transactions.vendor_payments",
                "sort_order": 20,
            },
        ]

        for data in level3_tabs:
            parent = data.pop("parent")

            DynamicLevel3Tab.objects.update_or_create(
                key=data["key"],
                defaults={
                    **data,
                    "parent_tab": parent,
                    "is_active": True,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Dynamic navigation hierarchy seeded successfully."
            )
        )