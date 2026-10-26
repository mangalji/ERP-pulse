from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from audit.notification_views import NotificationRead, NotificationsReadAll, visible
from audit.notifications import activity_context, notify


class NotificationScopeTests(SimpleTestCase):
    def setUp(self):
        self.user = Mock(company_id='company-1', is_authenticated=True)
        self.factory = APIRequestFactory()

    @patch('audit.notification_views.Notification.objects')
    def test_queries_are_scoped_to_user_and_company(self, objects):
        request = Mock(user=self.user)
        visible(request)
        objects.filter.assert_called_once_with(recipient=self.user, company_id='company-1')

    @patch('audit.notification_views.visible')
    def test_cannot_mark_another_users_notification(self, query):
        query.return_value.filter.return_value.update.return_value = 0
        request = self.factory.patch('/notifications/4/', {'is_read': True}, format='json')
        force_authenticate(request, self.user)
        response = NotificationRead.as_view()(request, pk=4)
        self.assertEqual(response.status_code, 404)

    @patch('audit.notification_views.visible')
    def test_mark_all_only_updates_visible_unread(self, query):
        query.return_value.filter.return_value.update.return_value = 2
        request = self.factory.post('/notifications/read-all/', {}, format='json')
        force_authenticate(request, self.user)
        response = NotificationsReadAll.as_view()(request)
        query.return_value.filter.assert_called_once_with(is_read=False)
        self.assertEqual(response.data['updated'], 2)

    @patch('audit.notifications.transaction.on_commit', side_effect=lambda callback: callback())
    @patch('audit.notifications.Notification.objects.create')
    def test_actor_is_attached_only_to_manual_events(self, create, on_commit):
        with activity_context('manual', 'actor-1'):
            notify('recipient', 'company', 'Manual event')
        self.assertEqual(create.call_args.kwargs['actor_id'], 'actor-1')
        with activity_context('automated', 'actor-1'):
            notify('recipient', 'company', 'Automated event')
        self.assertIsNone(create.call_args.kwargs['actor_id'])
        self.assertEqual(create.call_args.kwargs['activity_type'], 'automated')
