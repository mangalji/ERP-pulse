from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from audit.models import Notification


def visible(request):
    return Notification.objects.filter(recipient=request.user, company_id=request.user.company_id)


class NotificationList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            offset = max(0, int(request.query_params.get('offset', 0)))
            limit = max(1, min(100, int(request.query_params.get('limit', 10))))
        except (ValueError, TypeError):
            return Response({'detail': 'Invalid pagination.'}, status=400)
        all_items = visible(request)
        unread_count = all_items.filter(is_read=False).count()
        items = all_items.filter(is_read=False) if request.query_params.get('unread') == 'true' else all_items
        rows = items.select_related('actor')[offset:offset + limit]
        results = [{
            'id': item.id, 'message': item.message, 'link': item.link,
            'is_read': item.is_read, 'created_at': item.created_at,
            'activity_type': item.activity_type,
            'actor_name': (item.actor.get_full_name() or item.actor.email) if item.activity_type == 'manual' and item.actor else None,
        } for item in rows]
        return Response({'results': results, 'count': items.count(), 'unread_count': unread_count})


class NotificationRead(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        read = request.data.get('is_read')
        if not isinstance(read, bool):
            return Response({'detail': 'is_read must be a boolean.'}, status=400)
        if not visible(request).filter(pk=pk).update(is_read=read):
            return Response({'detail': 'Notification not found.'}, status=404)
        return Response({'success': True})


class NotificationsReadAll(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        count = visible(request).filter(is_read=False).update(is_read=True)
        return Response({'updated': count})
