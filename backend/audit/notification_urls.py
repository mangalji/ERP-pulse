from django.urls import path
from audit.notification_views import NotificationDelete, NotificationList, NotificationRead, NotificationsReadAll, NotificationRestore

urlpatterns = [
    path('', NotificationList.as_view()),
    path('read-all/', NotificationsReadAll.as_view()),
    path('<int:pk>/restore/', NotificationRestore.as_view()),
    path('<int:pk>/', NotificationRead.as_view()),
    path('<int:pk>/delete/', NotificationDelete.as_view()),
]
