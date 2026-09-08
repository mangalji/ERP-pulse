from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from uuid import UUID
from common.utils.response import success_response
from navigation.serializers import TransactionMenuSerializer
from navigation.services import transaction_menu_service
from django.core.paginator import Paginator
from .models import (
    DynamicTopLevelTab,
    DynamicLevel2Tab,
    DynamicLevel3Tab,
    NavigationUserAccess,
)

User = get_user_model()

class TransactionMenuView(APIView):
    """
    GET /api/v1/navigation/menu/

    Returns the transaction navigation tree for a company user with an
    authorized/current NetSuite connection.

    Super Admin users are excluded from the transaction menu by the
    company requirement: users without request.user.company receive no menu.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        menu = transaction_menu_service.get_menu_for_user(user=request.user)

        if menu is None:
            return success_response(
                message="Transaction menu is not available for this user.",
                data=[],
            )

        return success_response(
            message="Transaction menu fetched successfully.",
            data=TransactionMenuSerializer(menu).data,
        )

class DynamicNavigationMenuView(APIView):
    """Return the active 3-level navigation tree for the current user."""

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _visible_ids(user):
        rows = NavigationUserAccess.objects.filter(user=user)

        top = {
            row.top_level_tab_id: row.is_visible
            for row in rows
            if row.top_level_tab_id
        }

        level2 = {
            row.level2_tab_id: row.is_visible
            for row in rows
            if row.level2_tab_id
        }

        level3 = {
            row.level3_tab_id: row.is_visible
            for row in rows
            if row.level3_tab_id
        }

        return top, level2, level3

    @staticmethod
    def _tab_data(tab):
        return {
            "id": str(tab.id),
            "name": tab.name,
            "key": tab.key,
            "route": tab.route,
            # "query_params": tab.query_params or {},
            # "feature_code": tab.feature_code,
            # "icon": tab.icon,
        }


    def get(self, request):
        _ensure_system_tabs()

        top_visibility, level2_visibility, level3_visibility = (
            self._visible_ids(request.user)
        )

        is_admin = _is_company_admin(request.user)

        top_level_tabs = (
            DynamicTopLevelTab.objects
            .filter(is_active=True)
            .prefetch_related(
                "level2_tabs__level3_tabs",
            )
            .order_by("sort_order", "name")
        )

        data = []

        for top_tab in top_level_tabs:

            # Employees is a system tab:
            # visible only to Company Admin.
            if top_tab.key == "employees" and not is_admin:
                continue

            # Settings is always visible.
            if (
                top_tab.key != "settings"
                and top_visibility.get(top_tab.id, True) is False
            ):
                continue

            level2_data = []

            for level2_tab in (
                top_tab.level2_tabs
                .filter(is_active=True)
                .order_by("sort_order", "name")
            ):
                if (
                    level2_tab.key == "settings-customize"
                    and not is_admin
                ):
                    continue

                if level2_visibility.get(level2_tab.id, True) is False:
                    continue

                level3_data = []

                for level3_tab in (
                    level2_tab.level3_tabs
                    .filter(is_active=True)
                    .order_by("sort_order", "name")
                ):
                    if level3_visibility.get(level3_tab.id, True) is False:
                        continue

                    level3_data.append(
                        self._tab_data(level3_tab)
                    )

                level2_data.append({
                    **self._tab_data(level2_tab),
                    "children": level3_data,
                })

            data.append({
                **self._tab_data(top_tab),
                "children": level2_data,
            })

        return success_response(
            message="Navigation menu fetched successfully.",
            data=data,
        )
    

def _is_company_admin(user):
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return user.user_roles.filter(role__name__iexact="Company Admin").exists()

# def _ensure_system_tabs():
#     system_tabs = [
#         {
#             "key": "employees",
#             "name": "Employees",
#             "route": "/app/employees",
#             "feature_code": "system.employees",
#             "sort_order": 10,
#         },
#         {
#             "key": "settings",
#             "name": "Settings",
#             "route": "/app/settings",
#             "feature_code": "system.settings",
#             "sort_order": 9990,
#         },
#     ]

#     for tab_data in system_tabs:
#         DynamicTopLevelTab.objects.get_or_create(
#             key=tab_data["key"],
#             defaults={
#                 "name": tab_data["name"],
#                 "route": tab_data["route"],
#                 "feature_code": tab_data["feature_code"],
#                 "sort_order": tab_data["sort_order"],
#                 "is_active": True,
#             },
#         )

def _ensure_system_tabs():
    system_tabs = [
        {
            "key": "employees",
            "name": "Employees",
            "route": "/app/employees",
            # "feature_code": "system.employees",
            "sort_order": 10,
        },
        {
            "key": "settings",
            "name": "Settings",
            "route": "/app/settings",
            # "feature_code": "system.settings",
            "sort_order": 9990,
        },
    ]

    for tab_data in system_tabs:
        DynamicTopLevelTab.objects.get_or_create(
            key=tab_data["key"],
            defaults={
                "name": tab_data["name"],
                "route": tab_data["route"],
                # "feature_code": tab_data["feature_code"],
                "sort_order": tab_data["sort_order"],
                "is_active": True,
            },
        )

    settings_tab = DynamicTopLevelTab.objects.get(key="settings")

    settings_children = [
        {
            "key": "settings-company-info",
            "name": "Company Info",
            "route": "/app/settings",
            # "feature_code": "system.settings.company_info",
            "sort_order": 10,
        },
        {
            "key": "settings-customize",
            "name": "Customize",
            "route": "/app/settings/customize",
            # "feature_code": "system.settings.customize",
            "sort_order": 20,
        },
        {
            "key": "settings-personal-info",
            "name": "Personal Info",
            "route": "/app/profile",
            # "feature_code": "system.settings.personal_info",
            "sort_order": 30,
        },
    ]

    for tab_data in settings_children:
        DynamicLevel2Tab.objects.get_or_create(
            key=tab_data["key"],
            defaults={
                "parent_tab": settings_tab,
                "name": tab_data["name"],
                "route": tab_data["route"],
                # "feature_code": tab_data["feature_code"],
                "sort_order": tab_data["sort_order"],
                "is_active": True,
            },
        )

    customize_tab = DynamicLevel2Tab.objects.filter(
        key="settings-customize",
        is_active=True,
    ).first()

    if customize_tab:
        customize_children = [
            {
                "key": "center-tabs",
                "name": "Center Tabs",
                "route": "/app/settings/customize/center-tabs",
                "sort_order": 10,
            },
            {
                "key": "center-categories",
                "name": "Center Categories",
                "route": "/app/settings/customize/center-categories",
                "sort_order": 20,
            },
        ]

        for child_data in customize_children:
            DynamicLevel3Tab.objects.get_or_create(
                key=child_data["key"],
                defaults={
                    "parent_tab": customize_tab,
                    "name": child_data["name"],
                    "route": child_data["route"],
                    "sort_order": child_data["sort_order"],
                    "is_active": True,
                },
            )


def _company_user_or_none(request, user_id):
    if not user_id:
        return None

    try:
        UUID(str(user_id))
    except(TypeError, ValueError,AttributeError):
        return None
    return User.objects.filter(pk=user_id, company=request.user.company).first()


def _access_row_for_item(user, tab_level, tab_id):
    if tab_level == "top":
        tab = DynamicTopLevelTab.objects.filter(
            pk=tab_id,
            is_active=True,
        ).first()

        if not tab:
            raise ValueError("Top-level navigation tab was not found.")

        return NavigationUserAccess.objects.filter(
            user=user,
            top_level_tab=tab,
        ).first(), {
            "top_level_tab": tab,
            "level2_tab": None,
            "level3_tab": None,
        }

    if tab_level == "level2":
        tab = DynamicLevel2Tab.objects.filter(
            pk=tab_id,
            is_active=True,
        ).first()

        if not tab:
            raise ValueError("Level-2 navigation tab was not found.")

        return NavigationUserAccess.objects.filter(
            user=user,
            level2_tab=tab,
        ).first(), {
            "top_level_tab": None,
            "level2_tab": tab,
            "level3_tab": None,
        }

    if tab_level == "level3":
        tab = DynamicLevel3Tab.objects.filter(
            pk=tab_id,
            is_active=True,
        ).first()

        if not tab:
            raise ValueError("Level-3 navigation tab was not found.")

        return NavigationUserAccess.objects.filter(
            user=user,
            level3_tab=tab,
        ).first(), {
            "top_level_tab": None,
            "level2_tab": None,
            "level3_tab": tab,
        }

    raise ValueError("tab_level must be top, level2, or level3")

class CenterTabsView(APIView):
    """
    Center Tabs master-management page.

    GET:
        Returns active top-level tabs, 10 per page.

    POST:
        Creates a new top-level tab using only:
        - name
        - route (optional)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_number = request.query_params.get("page", "1")

        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            page_number = 1

        if page_number < 1:
            page_number = 1

        tabs = (
            DynamicTopLevelTab.objects
            .filter(is_active=True)
            .order_by("sort_order", "name", "id")
        )

        paginator = Paginator(tabs, 10)
        page = paginator.get_page(page_number)

        return success_response(
            message="Center tabs fetched successfully.",
            data={
                "results": [
                    {
                        "id": str(tab.id),
                        "name": tab.name,
                        "route": tab.route or "",
                    }
                    for tab in page.object_list
                ],
                "pagination": {
                    "page": page.number,
                    "page_size": 10,
                    "total": paginator.count,
                    "total_pages": paginator.num_pages,
                    "has_next": page.has_next(),
                    "has_previous": page.has_previous(),
                },
            },
        )

    def post(self, request):
        name = str(request.data.get("name") or "").strip()
        route = str(request.data.get("route") or "").strip()

        if not name:
            return Response(
                {"detail": "Center Tab name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_key = slugify(name) or "tab"
        key = base_key
        suffix = 2

        while DynamicTopLevelTab.objects.filter(key=key).exists():
            key = f"{base_key}-{suffix}"
            suffix += 1

        latest_sort_order = (
            DynamicTopLevelTab.objects
            .order_by("-sort_order")
            .values_list("sort_order", flat=True)
            .first()
        )

        sort_order = (latest_sort_order or 0) + 10

        tab = DynamicTopLevelTab.objects.create(
            name=name,
            key=key,
            route=route,
            sort_order=sort_order,
            is_active=True,
        )

        return success_response(
            message="Center Tab created successfully.",
            data={
                "id": str(tab.id),
                "name": tab.name,
                "route": tab.route or "",
            },
        )

class CenterTabsBulkDeleteView(APIView):
    """
    POST /api/v1/navigation/center-tabs/bulk-delete/

    Body:
    {
        "ids": ["uuid1", "uuid2"]
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get("ids")

        if not isinstance(ids, list) or not ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = list(dict.fromkeys(str(item) for item in ids))

        tabs = DynamicTopLevelTab.objects.filter(
            id__in=ids,
            is_active=True,
        )

        system_keys = {"employees", "settings"}

        protected_tabs = tabs.filter(key__in=system_keys)

        if protected_tabs.exists():
            return Response(
                {
                    "detail": (
                        "Employees and Settings are system tabs "
                        "and cannot be deleted."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            deleted_count = tabs.update(
                is_active=False,
            )

            # Deactivate all categories under selected tabs.
            categories = DynamicLevel2Tab.objects.filter(
                parent_tab_id__in=ids,
                is_active=True,
            )

            category_ids = list(
                categories.values_list("id", flat=True)
            )

            categories.update(is_active=False)

            # Deactivate all Level-3 children as well.
            if category_ids:
                DynamicLevel3Tab.objects.filter(
                    parent_tab_id__in=category_ids,
                    is_active=True,
                ).update(is_active=False)

            # Remove user-specific visibility overrides.
            NavigationUserAccess.objects.filter(
                top_level_tab_id__in=ids,
            ).delete()

            if category_ids:
                NavigationUserAccess.objects.filter(
                    level2_tab_id__in=category_ids,
                ).delete()

                NavigationUserAccess.objects.filter(
                    level3_tab_id__in=DynamicLevel3Tab.objects.filter(
                        parent_tab_id__in=category_ids,
                    ).values("id"),
                ).delete()

        return success_response(
            message=f"{deleted_count} Center Tab(s) deleted successfully.",
            data={
                "deleted_count": deleted_count,
                "ids": ids,
            },
        )

class CenterCategoriesBulkDeleteView(APIView):
    """
    POST /api/v1/navigation/center-categories/bulk-delete/

    Body:
    {
        "ids": ["uuid1", "uuid2"]
    }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        ids = request.data.get("ids")

        if not isinstance(ids, list) or not ids:
            return Response(
                {"detail": "ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ids = list(dict.fromkeys(str(item) for item in ids))

        categories = DynamicLevel2Tab.objects.filter(
            id__in=ids,
            is_active=True,
        )

        system_keys = {
            "settings-company-info",
            "settings-customize",
            "settings-personal-info",
        }

        protected_categories = categories.filter(
            key__in=system_keys
        )

        if protected_categories.exists():
            return Response(
                {
                    "detail": (
                        "System Settings categories "
                        "cannot be deleted."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            category_ids = list(
                categories.values_list("id", flat=True)
            )

            deleted_count = categories.update(
                is_active=False,
            )

            # Deactivate Level-3 children.
            DynamicLevel3Tab.objects.filter(
                parent_tab_id__in=category_ids,
                is_active=True,
            ).update(is_active=False)

            NavigationUserAccess.objects.filter(
                level2_tab_id__in=category_ids,
            ).delete()

            NavigationUserAccess.objects.filter(
                level3_tab_id__in=DynamicLevel3Tab.objects.filter(
                    parent_tab_id__in=category_ids,
                ).values("id"),
            ).delete()

        return success_response(
            message=(
                f"{deleted_count} Center Category(s) "
                "deleted successfully."
            ),
            data={
                "deleted_count": deleted_count,
                "ids": ids,
            },
        )

class NavigationCustomizationDataView(APIView):
    """GET the company users and full 3-level tree with effective visibility."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_company_admin(request.user):
            return Response({"detail": "Only Company Admin can customize navigation."}, status=status.HTTP_403_FORBIDDEN)
        if not request.user.company:
            return success_response(message="No company associated with user.", data={"employees": [], "tree": []})

        # employees = (
        #     User.objects.filter(company=request.user.company)
        #     .exclude(pk=request.user.pk)
        #     .exclude(user_roles__role__name__iexact="Company Admin")
        #     .distinct()
        #     .order_by("first_name", "last_name", "email")
        # )
        # employee_data = [
        #     {
        #         "id": str(user.id),
        #         "name": user.get_full_name().strip() or user.email,
        #         "email": user.email,
        #     }
        #     for user in employees
        # ]

        company_users = (
            User.objects
            .filter(company=request.user.company)
            # .exclude(pk=request.user.pk)
            .distinct()
            .order_by("first_name", "last_name", "email")
        )

        employees = company_users.exclude(
            user_roles__role__name__iexact="Company Admin"
        ).distinct()

        admins = company_users.filter(
            user_roles__role__name__iexact="Company Admin"
        ).distinct()

        employee_data = [
            {
                "id": str(user.id),
                "name": user.get_full_name().strip() or user.email,
                "email": user.email,
            }
            for user in employees
        ]

        admin_data = [
            {
                "id": str(user.id),
                "name": user.get_full_name().strip() or user.email,
                "email": user.email,
            }
            for user in admins
        ]

        target_user_id = request.query_params.get("target_user_id")
        target_user = _company_user_or_none(request, target_user_id) if target_user_id else None
        if target_user_id and not target_user:
            return Response({"detail": "Selected user does not belong to your company."}, status=status.HTTP_404_NOT_FOUND)

        access_by_top = {}
        access_by_l2 = {}
        access_by_l3 = {}

        if target_user:
            for row in NavigationUserAccess.objects.filter(user=target_user):
                if row.top_level_tab_id:
                    access_by_top[row.top_level_tab_id] = row.is_visible
                elif row.level2_tab_id:
                    access_by_l2[row.level2_tab_id] = row.is_visible
                elif row.level3_tab_id:
                    access_by_l3[row.level3_tab_id] = row.is_visible

        _ensure_system_tabs()

        tree = []

        is_admin = _is_company_admin(request.user)

        for top in (
            DynamicTopLevelTab.objects
            .filter(is_active=True)
            .prefetch_related("level2_tabs__level3_tabs")
            .order_by("sort_order", "name")
        ):
            # Employees should still appear in the customization tree
            # because the Company Admin may see/manage the system structure,
            # but its visibility is role-controlled.
            top_visible = access_by_top.get(top.id, True)

            top_node = {
                "id": str(top.id),
                "name": top.name,
                "key": top.key,
                "route": top.route,
                # "query_params": top.query_params or {},
                # "feature_code": top.feature_code,
                # "icon": top.icon,
                "level": "top",
                "visible": top_visible,
                "system": top.key in {"employees", "settings"},
                "children": [],
            }

            for l2 in (
                top.level2_tabs
                .filter(is_active=True)
                .order_by("sort_order", "name")
            ):
                l2_node = {
                "id": str(l2.id),
                "name": l2.name,
                "key": l2.key,
                "route": l2.route,
                # "query_params": l2.query_params or {},
                # "feature_code": l2.feature_code,
                # "icon": l2.icon,
                "level": "level2",
                "visible": access_by_l2.get(l2.id, True),
                # "system": False,
                "system": (
                    top.key == "settings"
                    and l2.key in {
                        "settings-company-info",
                        "settings-customize",
                        "settings-personal-info",
                    }
                ),
                "children": [],
                }

                for l3 in (
                    l2.level3_tabs
                    .filter(is_active=True)
                    .order_by("sort_order", "name")
                ):
                    l2_node["children"].append({
                        "id": str(l3.id),
                        "name": l3.name,
                        "key": l3.key,
                        "route": l3.route,
                        # "query_params": l3.query_params or {},
                        # "feature_code": l3.feature_code,
                        # "icon": l3.icon,
                        "level": "level3",
                        "visible": access_by_l3.get(l3.id, True),
                        "system": False,
                        "children": [],
                    })

                top_node["children"].append(l2_node)

            tree.append(top_node)

        return success_response(
            message="Navigation customization data fetched successfully.",
            data={
                "target_user": {
                    "id": str(target_user.id),
                    "name": target_user.get_full_name().strip() or target_user.email,
                    "email": target_user.email,
                } if target_user else None,
                "employees": employee_data,
                "admins": admin_data,
                "tree": tree,
            },
        )


class NavigationAccessUpdateView(APIView):
    """Show/remove one master navigation tab for a company user."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_company_admin(request.user):
            return Response({"detail": "Only Company Admin can customize navigation."}, status=status.HTTP_403_FORBIDDEN)
        
        target_user_ids = request.data.get("target_user_ids")

        if not isinstance(target_user_ids, list) or not target_user_ids:
            return Response(
                {"detail": "target_user_ids must be a non-empty list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target_user_ids = list(dict.fromkeys(
            str(user_id) for user_id in target_user_ids
        ))

        target_users = User.objects.filter(
            pk__in=target_user_ids,
            company=request.user.company,
        ).distinct()

        if target_users.count() != len(target_user_ids):
            return Response(
                {"detail": "One or more selected users were not found in your company."},
                status=status.HTTP_404_NOT_FOUND,
            )

        action = request.data.get("action")
        if action not in {"show", "remove"}:
            return Response(
                {"detail": "action must be show or remove."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        tab_level = request.data.get("tab_level")
        tab_id = request.data.get("tab_id")
        
        if tab_level == "top":
            system_tab = DynamicTopLevelTab.objects.filter(
                pk=tab_id,
                key__in={"employees", "settings"},
                is_active=True,
            ).first()
        
            if system_tab:
                return Response(
                    {"detail": "System navigation tabs cannot be removed or customized."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if tab_level == "level2":
            system_level2 = DynamicLevel2Tab.objects.filter(
                pk=tab_id,
                key__in={
                    "settings-company-info",
                    "settings-customize",
                    "settings-personal-info",
                },
                is_active=True,
            ).first()

            if system_level2:
                return Response(
                    {
                        "detail": (
                            "System Settings tabs cannot be removed "
                            "or customized."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        try:
            _, lookup = _access_row_for_item(
                target_users.first(),
                tab_level,
                tab_id,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        visible = action == "show"

        created_count = 0
        updated_count = 0

        lookup = {
            k: v
            for k, v in lookup.items()
            if v is not None
        }

        with transaction.atomic():
            for target_user in target_users:
                row = NavigationUserAccess.objects.filter(
                    user=target_user,
                    **lookup,
                ).first()

                if row:
                    if row.is_visible != visible:
                        row.is_visible = visible
                        row.save(update_fields=["is_visible", "updated_at"])
                        updated_count += 1
                else:
                    NavigationUserAccess.objects.create(
                        user=target_user,
                        is_visible=visible,
                        **lookup,
                    )
                    created_count += 1

        return success_response(
            message=(
                f"Navigation tab {'shown' if visible else 'removed'} "
                f"for {len(target_user_ids)} employee(s) successfully."
            ),
            data={
                "target_user_ids": target_user_ids,
                "tab_level": request.data.get("tab_level"),
                "tab_id": str(request.data.get("tab_id")),
                "visible": visible,
                "created_count": created_count,
                "updated_count": updated_count,
            },
        )


class NavigationMasterCreateView(APIView):
    """Create a new top-level, level-2, or level-3 navigation tab."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _is_company_admin(request.user):
            return Response(
                {"detail": "Only Company Admin can add navigation tabs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        name = str(request.data.get("name") or "").strip()
        route = str(request.data.get("route") or "").strip()
        # feature_code = str(request.data.get("feature_code") or "").strip()
        # icon = str(request.data.get("icon") or "").strip()
        parent_level = request.data.get("parent_level") or "root"
        parent_id = request.data.get("parent_id")
        # query_params = request.data.get("query_params") or {}

        if not name:
            return Response(
                {"detail": "name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not route:
            return Response(
                {"detail": "Path is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # if not isinstance(query_params, dict):
        #     return Response(
        #         {"detail": "query_params must be a JSON object."},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        if parent_level not in {"root", "top", "level2"}:
            return Response(
                {"detail": "parent_level must be root, top or level2."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if parent_level in {"top", "level2"} and not parent_id:
            return Response(
                {"detail": "parent_id is required for child tabs."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route = route.strip()

        if not route:
            return Response(
                {"detail": "Path is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if route.startswith(("http://", "https://")):
            return Response(
                {"detail": "Only internal /app/ paths are allowed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if route == "/app":
            return Response(
                {"detail": "Path must contain a dynamic path after /app/."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if route.startswith("/app/"):
            dynamic_path = route[len("/app/"):].strip("/")
        else:
            dynamic_path = route.strip("/")

        if not dynamic_path:
            return Response(
                {"detail": "Path must contain a dynamic path after /app/."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        route = f"/app/{dynamic_path}"

        base_key = slugify(name) or "tab"
        sort_order = int(request.data.get("sort_order") or 0)

        with transaction.atomic():
            if parent_level == "root":
                key = base_key
                suffix = 2

                while DynamicTopLevelTab.objects.filter(key=key).exists():
                    key = f"{base_key}-{suffix}"
                    suffix += 1

                tab = DynamicTopLevelTab.objects.create(
                    name=name,
                    key=key,
                    route=route,
                    # query_params=query_params,
                    # feature_code=feature_code,
                    # icon=icon,
                    sort_order=sort_order,
                    is_active=True,
                )

                level = "top"

            elif parent_level == "top":
                parent = DynamicTopLevelTab.objects.filter(
                    pk=parent_id,
                    is_active=True,
                ).first()

                if not parent:
                    return Response(
                        {"detail": "Parent top-level tab not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                key = base_key
                suffix = 2

                while DynamicLevel2Tab.objects.filter(key=key).exists():
                    key = f"{base_key}-{suffix}"
                    suffix += 1

                tab = DynamicLevel2Tab.objects.create(
                    parent_tab=parent,
                    name=name,
                    key=key,
                    route=route,
                    # query_params=query_params,
                    # feature_code=feature_code,
                    # icon=icon,
                    sort_order=sort_order,
                    is_active=True,
                )

                level = "level2"

            else:
                parent = DynamicLevel2Tab.objects.filter(
                    pk=parent_id,
                    is_active=True,
                ).first()

                if not parent:
                    return Response(
                        {"detail": "Parent level-2 tab not found."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                key = base_key
                suffix = 2

                while DynamicLevel3Tab.objects.filter(key=key).exists():
                    key = f"{base_key}-{suffix}"
                    suffix += 1

                tab = DynamicLevel3Tab.objects.create(
                    parent_tab=parent,
                    name=name,
                    key=key,
                    route=route,
                    # query_params=query_params,
                    # feature_code=feature_code,
                    # icon=icon,
                    sort_order=sort_order,
                    is_active=True,
                )

                level = "level3"

        return success_response(
            message="Navigation tab created successfully.",
            data={
                "id": str(tab.id),
                "name": tab.name,
                "key": tab.key,
                "level": level,
                "route": tab.route,
                # "query_params": tab.query_params or {},
            },
        )

class NavigationMasterUpdateView(APIView):
    """Update an existing top-level, level-2, or level-3 navigation tab."""

    permission_classes = [IsAuthenticated]

    def patch(self, request, level, tab_id):
        if not _is_company_admin(request.user):
            return Response(
                {"detail": "Only Company Admin can update navigation tabs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        model_map = {
            "top": DynamicTopLevelTab,
            "level2": DynamicLevel2Tab,
            "level3": DynamicLevel3Tab,
        }

        model = model_map.get(level)
        if model is None:
            return Response(
                {"detail": "level must be top, level2, or level3."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tab = model.objects.get(pk=tab_id)
        except model.DoesNotExist:
            return Response(
                {"detail": "Navigation tab not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Employees and Settings are protected system tabs.
        if level == "top" and tab.key in {"employees", "settings"} or (
            level == "level2"
            and tab.key in {
                "settings-company-info",
                "settings-customize",
                "settings-personal-info",
            }
        ):
            return Response(
                {
                    "detail": (
                        "System navigation tabs cannot be removed or "
                        "customized."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_fields = {
            "name",
            "route",
            # "query_params",
            # "feature_code",
            # "icon",
            "sort_order",
        }

        unknown_fields = set(request.data.keys()) - allowed_fields
        if unknown_fields:
            return Response(
                {
                    "detail": (
                        "Unsupported fields: "
                        + ", ".join(sorted(unknown_fields))
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if "name" in request.data:
            name = str(request.data.get("name") or "").strip()

            if not name:
                return Response(
                    {"detail": "name cannot be empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tab.name = name

        if "route" in request.data:
            route = str(request.data.get("route") or "").strip()

            if not route:
                return Response(
                    {"detail": "Path cannot be empty."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if route.startswith(("http://", "https://")):
                return Response(
                    {"detail": "Only internal /app/ paths are allowed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if route == "/app":
                return Response(
                    {
                        "detail": (
                            "Path must contain a dynamic path after /app/."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if route.startswith("/app/"):
                dynamic_path = route[len("/app/"):].strip("/")
            else:
                dynamic_path = route.strip("/")

            if not dynamic_path:
                return Response(
                    {"detail": "Path must contain a dynamic path after /app/."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tab.route = f"/app/{dynamic_path}"

        # if "query_params" in request.data:
        #     query_params = request.data.get("query_params")

        #     if not isinstance(query_params, dict):
        #         return Response(
        #             {"detail": "query_params must be a JSON object."},
        #             status=status.HTTP_400_BAD_REQUEST,
        #         )

        #     tab.query_params = query_params

        # if "feature_code" in request.data:
        #     tab.feature_code = str(
        #         request.data.get("feature_code") or ""
        #     ).strip()

        # if "icon" in request.data:
        #     tab.icon = str(request.data.get("icon") or "").strip()

        if "sort_order" in request.data:
            try:
                tab.sort_order = int(request.data.get("sort_order"))
            except (TypeError, ValueError):
                return Response(
                    {"detail": "sort_order must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        tab.save()

        return success_response(
            message="Navigation tab updated successfully.",
            data={
                "id": str(tab.id),
                "name": tab.name,
                "key": tab.key,
                "level": level,
                "route": tab.route,
                # "query_params": tab.query_params or {},
                # "feature_code": tab.feature_code,
                # "icon": tab.icon,
                "sort_order": tab.sort_order,
            },
        )

    def delete(self, request, level, tab_id):
        if not _is_company_admin(request.user):
            return Response(
                {"detail": "Only Company Admin can delete navigation tabs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        model_map = {
            "top": DynamicTopLevelTab,
            "level2": DynamicLevel2Tab,
            "level3": DynamicLevel3Tab,
        }

        model = model_map.get(level)

        if model is None:
            return Response(
                {"detail": "level must be top, level2, or level3."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tab = model.objects.get(pk=tab_id)
        except model.DoesNotExist:
            return Response(
                {"detail": "Navigation tab not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        system_keys = {
            "employees",
            "settings",
            "settings-company-info",
            "settings-customize",
            "settings-personal-info",
        }

        if tab.key in system_keys:
            return Response(
                {
                    "detail": (
                        "System navigation tabs cannot be deleted."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            tab_name = tab.name

            # Soft-delete the selected tab.
            tab.is_active = False
            tab.save(update_fields=["is_active", "updated_at"])

            # Deactivate descendants when a parent is deleted.
            if level == "top":
                DynamicLevel2Tab.objects.filter(
                    parent_tab=tab,
                    is_active=True,
                ).update(is_active=False)

                DynamicLevel3Tab.objects.filter(
                    parent_tab__parent_tab=tab,
                    is_active=True,
                ).update(is_active=False)

            elif level == "level2":
                DynamicLevel3Tab.objects.filter(
                    parent_tab=tab,
                    is_active=True,
                ).update(is_active=False)

            # Remove per-user overrides for the deleted branch.
            access_filter = {}

            if level == "top":
                access_filter["top_level_tab"] = tab
            elif level == "level2":
                access_filter["level2_tab"] = tab
            else:
                access_filter["level3_tab"] = tab

            NavigationUserAccess.objects.filter(
                **access_filter
            ).delete()

        return success_response(
            message=f'Navigation tab "{tab_name}" deleted successfully.',
            data={
                "id": str(tab.id),
                "level": level,
                "is_active": False,
            },
        )

class CenterCategoriesView(APIView):
    """
    GET  /api/v1/navigation/center-categories/
    POST /api/v1/navigation/center-categories/

    Manage Level-2 Center Categories.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        page_number = request.query_params.get("page", "1")

        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            page_number = 1

        if page_number < 1:
            page_number = 1

        categories = (
            DynamicLevel2Tab.objects
            .filter(is_active=True)
            .select_related("parent_tab")
            .order_by("sort_order", "name", "id")
        )

        paginator = Paginator(categories, 10)
        page = paginator.get_page(page_number)

        center_tabs = (
            DynamicTopLevelTab.objects
            .filter(is_active=True)
            .order_by("sort_order", "name", "id")
        )

        return success_response(
            message="Center Categories fetched successfully.",
            data={
                "results": [
                    {
                        "id": str(category.id),
                        "name": category.name,
                        "route": category.route or "",
                        "center_tab": {
                            "id": str(category.parent_tab.id),
                            "name": category.parent_tab.name,
                        },
                    }
                    for category in page.object_list
                ],
                "center_tabs": [
                    {
                        "id": str(tab.id),
                        "name": tab.name,
                    }
                    for tab in center_tabs
                ],
                "pagination": {
                    "page": page.number,
                    "page_size": 10,
                    "total": paginator.count,
                    "total_pages": paginator.num_pages,
                    "has_next": page.has_next(),
                    "has_previous": page.has_previous(),
                },
            },
        )

    def post(self, request):
        name = str(request.data.get("name") or "").strip()
        route = str(request.data.get("route") or "").strip()
        center_tab_id = request.data.get("center_tab_id")

        if not name:
            return Response(
                {"detail": "Center Category name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not center_tab_id:
            return Response(
                {"detail": "Center Tab is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        parent = (
            DynamicTopLevelTab.objects
            .filter(
                pk=center_tab_id,
                is_active=True,
            )
            .first()
        )

        if not parent:
            return Response(
                {"detail": "Selected Center Tab was not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        base_key = slugify(name) or "category"
        key = base_key
        suffix = 2

        while DynamicLevel2Tab.objects.filter(key=key).exists():
            key = f"{base_key}-{suffix}"
            suffix += 1

        latest_sort_order = (
            DynamicLevel2Tab.objects
            .filter(parent_tab=parent)
            .order_by("-sort_order")
            .values_list("sort_order", flat=True)
            .first()
        )

        sort_order = (latest_sort_order or 0) + 10

        category = DynamicLevel2Tab.objects.create(
            parent_tab=parent,
            name=name,
            key=key,
            route=route,
            sort_order=sort_order,
            is_active=True,
        )

        return success_response(
            message="Center Category created successfully.",
            data={
                "id": str(category.id),
                "name": category.name,
                "route": category.route or "",
                "center_tab": {
                    "id": str(parent.id),
                    "name": parent.name,
                },
            },
        )

class CenterCategoryChildrenView(APIView):
    """
    GET  /api/v1/navigation/center-categories/<category_id>/children/
    POST /api/v1/navigation/center-categories/<category_id>/children/
    """

    permission_classes = [IsAuthenticated]

    def get_category(self, category_id):
        return (
            DynamicLevel2Tab.objects
            .filter(
                pk=category_id,
                is_active=True,
            )
            .first()
        )

    def get(self, request, category_id):
        category = self.get_category(category_id)

        if not category:
            return Response(
                {"detail": "Center Category not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        children = (
            DynamicLevel3Tab.objects
            .filter(
                parent_tab=category,
                is_active=True,
            )
            .order_by("sort_order", "name", "id")
        )

        return success_response(
            message="Center Category children fetched successfully.",
            data={
                "category": {
                    "id": str(category.id),
                    "name": category.name,
                },
                "results": [
                    {
                        "id": str(child.id),
                        "name": child.name,
                        "route": child.route or "",
                    }
                    for child in children
                ],
            },
        )

    def post(self, request, category_id):
        category = self.get_category(category_id)

        if not category:
            return Response(
                {"detail": "Center Category not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        name = str(request.data.get("name") or "").strip()
        route = str(request.data.get("route") or "").strip()

        if not name:
            return Response(
                {"detail": "Level-3 name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base_key = slugify(name) or "item"
        key = base_key
        suffix = 2

        while DynamicLevel3Tab.objects.filter(key=key).exists():
            key = f"{base_key}-{suffix}"
            suffix += 1

        latest_sort_order = (
            DynamicLevel3Tab.objects
            .filter(parent_tab=category)
            .order_by("-sort_order")
            .values_list("sort_order", flat=True)
            .first()
        )

        sort_order = (latest_sort_order or 0) + 10

        child = DynamicLevel3Tab.objects.create(
            parent_tab=category,
            name=name,
            key=key,
            route=route,
            sort_order=sort_order,
            is_active=True,
        )

        return success_response(
            message="Level-3 item created successfully.",
            data={
                "id": str(child.id),
                "name": child.name,
                "route": child.route or "",
            },
        )