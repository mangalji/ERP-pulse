from django.urls import path

from navigation.views import (
    TransactionMenuView, 
    DynamicNavigationMenuView,
    NavigationCustomizationDataView,
    NavigationAccessUpdateView,
    NavigationMasterCreateView,
    NavigationMasterUpdateView,
    CenterTabsView,
    CenterCategoriesView,
    CenterCategoryChildrenView,
    CenterTabsBulkDeleteView,
    CenterCategoriesBulkDeleteView,
)

urlpatterns = [
    path("transaction-menu/", TransactionMenuView.as_view(), name="transaction-menu"),
    path("menu/",DynamicNavigationMenuView.as_view(),name="dynamic-navigation-menu"),
    path("customize/", NavigationCustomizationDataView.as_view(), name="navigation-customize-data"),
    path("customize/access/", NavigationAccessUpdateView.as_view(), name="navigation-customize-access"),
    path("customize/tab/", NavigationMasterCreateView.as_view(), name="navigation-customize-tab"),
    path("customize/tab/<str:level>/<uuid:tab_id>/",NavigationMasterUpdateView.as_view(),name="navigation-customize-tab-update"),
    path("center-tabs/", CenterTabsView.as_view(), name="center-tabs"),
    path("center-categories/", CenterCategoriesView.as_view(), name="center-categories"),
    path("center-categories/<uuid:category_id>/children/", CenterCategoryChildrenView.as_view(), name="center-category-children"),
    path("center-tabs/bulk-delete/", CenterTabsBulkDeleteView.as_view(), name="center-tabs-bulk-delete"),
    path("center-categories/bulk-delete/", CenterCategoriesBulkDeleteView.as_view(),name="center-categories-bulk-delete"),
]
