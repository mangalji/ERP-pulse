"""Company-scoped activity-log API."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from tenancy.permissions import IsCompanyUser


def _actor_name(user):
    return (user.get_full_name() or user.email) if user else None


class CompanyActivityLogView(APIView):
    """Read-only paginated audit evidence for the authenticated company."""

    permission_classes = [IsAuthenticated, IsCompanyUser]

    def get(self, request):
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
            limit = max(1, min(100, int(request.query_params.get("limit", 15))))
        except (TypeError, ValueError):
            return Response({"detail": "offset and limit must be valid integers."}, status=400)

        queryset = AuditLog.objects.filter(company=request.user.company).select_related("user")
        for field in ("module", "status", "activity_type"):
            value = (request.query_params.get(field) or "").strip()
            if value:
                queryset = queryset.filter(**{field: value})

        total = queryset.count()
        rows = queryset[offset:offset + limit]
        results = [{
            "id": row.id,
            "created_at": row.created_at,
            "module": row.module,
            "action": row.action,
            "activity": row.entity,
            "entity_id": row.entity_id,
            "activity_type": row.activity_type,
            "status": row.status,
            "user_name": _actor_name(row.user) if row.activity_type == "manual" else None,
            "summary": (row.detail or {}).get("summary") or row.entity,
            "detail": row.detail or {},
        } for row in rows]
        return Response({
            "results": results,
            "count": total,
            "offset": offset,
            "limit": limit,
            "next_offset": offset + limit if offset + limit < total else None,
            "previous_offset": max(0, offset - limit) if offset else None,
        })
