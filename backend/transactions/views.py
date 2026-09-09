from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.utils.pagination import paginated_response
from common.utils.response import success_response
from transactions.models import Transaction, get_model_schema
from transactions.serializers import (
    TransactionCreateSerializer,
    TransactionListSerializer,
)
from transactions.services import transaction_service


class TransactionsView(APIView):
    permission_classes = [IsAuthenticated]

    def _pagination(self, request):
        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
            limit = int(request.query_params.get("limit", 20))
        except (TypeError, ValueError):
            raise ValidationError({
                "offset": "offset and limit must be integers.",
            })

        return offset, max(1, min(limit, 100))

    def get(self, request):
        if request.query_params.get("schema") == "true":
            return success_response(
                message="Transaction schema fetched successfully.",
                data={
                    "fields": get_model_schema(Transaction),
                },
            )
        transaction_type = (
            request.query_params.get("transaction_type") or ""
        ).strip()
        record_type = (
            request.query_params.get("record_type") or ""
        ).strip()

        if record_type and not transaction_type:
            raise ValidationError({
                "transaction_type": (
                    "transaction_type is required when record_type is provided."
                ),
            })

        offset, limit = self._pagination(request)

        try:
            rows, count = transaction_service.list_transactions(
                user=request.user,
                transaction_type=transaction_type or None,
                record_type=record_type or None,
                limit=limit,
                offset=offset,
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        return paginated_response(
            message="Transactions fetched successfully.",
            results=TransactionListSerializer(rows, many=True).data,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

    def post(self, request):
        transaction_type = (
            request.query_params.get("transaction_type") or ""
        ).strip()
        record_type = (
            request.query_params.get("record_type") or ""
        ).strip()

        if not transaction_type:
            raise ValidationError({
                "transaction_type": "transaction_type is required.",
            })

        if not record_type:
            raise ValidationError({
                "record_type": "record_type is required.",
            })

        serializer = TransactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        transaction = transaction_service.create_transaction(
            user=request.user,
            transaction_type=transaction_type,
            record_type=record_type,
            data=serializer.validated_data,
        )

        return success_response(
            message="Transaction created successfully.",
            data=TransactionListSerializer(transaction).data,
        )
