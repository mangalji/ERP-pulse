from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from audit.models import Notification


def visible(request):
    return Notification.objects.filter(
        recipient=request.user,
        company_id=request.user.company_id,
    ).filter(deleted_at__isnull=True)


class NotificationList(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        message = request.data.get('message')
        if not isinstance(message, str) or not message.strip():
            return Response({'detail': 'message is required.'}, status=400)
        link = request.data.get('link', '')
        if not isinstance(link, str):
            return Response({'detail': 'link must be a string.'}, status=400)
        activity_type = request.data.get('activity_type', 'manual')
        if activity_type not in {'manual', 'automated'}:
            return Response({'detail': 'activity_type must be manual or automated.'}, status=400)
        company_id = getattr(request.user, 'company_id', None)
        if not company_id:
            return Response({'detail': 'A company context is required.'}, status=400)
        notification = Notification.objects.create(
            recipient=request.user,
            company_id=company_id,
            message=message.strip()[:500],
            link=link[:500],
            activity_type=activity_type,
            actor=request.user if activity_type == 'manual' else None,
        )
        return Response({'id': notification.id, 'success': True}, status=201)

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


class NotificationDelete(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        owned = Notification.objects.filter(recipient=request.user, company_id=request.user.company_id)
        if request.query_params.get('permanent') == 'true':
            deleted, _ = owned.filter(pk=pk).delete()
            if not deleted:
                return Response({'detail': 'Notification not found.'}, status=404)
            return Response({'deleted': True})
        updated = owned.filter(deleted_at__isnull=True, pk=pk).update(
            deleted_at=timezone.now(),
            delete_after=timezone.now() + timedelta(seconds=10),
        )
        if not updated:
            return Response({'detail': 'Notification not found.'}, status=404)
        return Response({'deleted': True, 'undo_seconds': 10})


class NotificationRestore(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        now = timezone.now()
        updated = Notification.objects.filter(
            pk=pk,
            recipient=request.user,
            company_id=request.user.company_id,
            deleted_at__isnull=False,
            delete_after__gt=now,
        ).update(deleted_at=None, delete_after=None)
        if not updated:
            return Response({'detail': 'Undo window has expired.'}, status=410)
        return Response({'restored': True})
