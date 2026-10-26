from django.urls import path
from audit.notification_views import NotificationList, NotificationRead, NotificationsReadAll

urlpatterns = [
    path('', NotificationList.as_view()),
    path('read-all/', NotificationsReadAll.as_view()),
    path('<int:pk>/', NotificationRead.as_view()),
]
