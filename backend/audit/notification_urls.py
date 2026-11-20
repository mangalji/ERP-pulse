from django.urls import path
from audit.notification_views import NotificationBulkDelete, NotificationBulkRead, NotificationDelete, NotificationList, NotificationRead, NotificationsReadAll

urlpatterns = [
    path('', NotificationList.as_view()),
    path('read-all/', NotificationsReadAll.as_view()),
    path('read-bulk/', NotificationBulkRead.as_view()),
    path('delete-bulk/', NotificationBulkDelete.as_view()),
    path('<int:pk>/', NotificationRead.as_view()),
    path('<int:pk>/delete/', NotificationDelete.as_view()),
]
