"""Role-scoped activity-log API."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import AuditLog
from tenancy.permissions import IsCompanyUser
from superadmin.permissions import IsSuperAdmin


def _actor_name(user):
    return (user.get_full_name() or user.email) if user else None


class CompanyActivityLogView(APIView):
    """Existing activity-log endpoint with company/SuperAdmin scoping."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
            limit = max(1, min(100, int(request.query_params.get("limit", 15))))
        except (TypeError, ValueError):
            return Response({"detail": "offset and limit must be valid integers."}, status=400)

        is_superadmin = IsSuperAdmin().has_permission(request, self)
        if is_superadmin:
            queryset = AuditLog.objects.select_related("user", "company")
            company_search = (request.query_params.get("company") or "").strip()
            if company_search:
                queryset = queryset.filter(company__name__icontains=company_search)
        else:
            if not IsCompanyUser().has_permission(request, self) or not request.user.company_id:
                return Response({"detail": "You do not have access to activity logs."}, status=403)
            queryset = AuditLog.objects.filter(company=request.user.company).select_related("user", "company")
        for field in ("module", "status", "activity_type"):
            value = (request.query_params.get(field) or "").strip()
            if value:
                queryset = queryset.filter(**{field: value})

        total = queryset.count()
        rows = queryset[offset:offset + limit]
        results = [{
            "id": row.id,
            "created_at": row.created_at,
            "company_id": str(row.company_id) if row.company_id else None,
            "company_name": row.company.name if row.company_id else "—",
            "module": row.module,
            "action": row.action,
            "activity": row.entity,
            "entity_id": row.entity_id,
            "activity_type": row.activity_type,
            "status": row.status,
            "user_name": _actor_name(row.user) if row.activity_type == "manual" else None,
            "summary": (row.detail or {}).get("summary") or row.entity,
            "ip_address": row.ip_address,
            "user_agent": row.user_agent,
            "request": (row.detail or {}).get("request"),
            "netsuite": (row.detail or {}).get("netsuite"),
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
