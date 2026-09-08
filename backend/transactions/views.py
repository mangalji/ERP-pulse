from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from common.utils.pagination import paginated_response
from transactions.serializers import TransactionListSerializer, TransactionCreateSerializer
from transactions.services import transaction_service
from common.utils.response import success_response

class TransactionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transaction_type = (request.query_params.get("transaction_type") or "").strip()
        record_type = (request.query_params.get("record_type") or "").strip()

        if not transaction_type:
            raise ValidationError({
                "transaction_type": "transaction_type is required."
            })

        if not record_type:
            raise ValidationError({
                "record_type": "record_type is required."
            })

        try:
            offset = max(0, int(request.query_params.get("offset", 0)))
            limit = int(request.query_params.get("limit", 20))
        except (TypeError, ValueError):
            raise ValidationError({
                "offset": "offset and limit must be integers."
            })

        limit = max(1, min(limit, 100))

        rows, count = transaction_service.list_transactions(
            user=request.user,
            transaction_type=transaction_type,
            record_type=record_type,
            limit=limit,
            offset=offset,
        )

        return paginated_response(
            message="Transactions fetched successfully.",
            results=TransactionListSerializer(rows, many=True).data,
            count=count,
            request=request,
            offset=offset,
            limit=limit,
        )

    def post(self, request):
        transaction_type = (request.query_params.get("transaction_type") or "").strip()
        record_type = (request.query_params.get("record_type") or "").strip()

        if not transaction_type:
            raise ValidationError({
                "transaction_type": "transaction_type is required."
            })

        if not record_type:
            raise ValidationError({
                "record_type": "record_type is required."
            })

        serializer = TransactionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # company = getattr(request.user, "company", None)

        # if company is None:
        #     return Response(
        #         {"detail": "User is not associated with a company."},
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

        # data = {
        #     "company": company.id,
        #     "transaction_type": transaction_type,
        #     "record_type": record_type,
        #     "tran_id": request.data.get("tran_id"),
        #     "tran_date": request.data.get("tran_date"),
        #     "entity": request.data.get("entity", ""),
        #     "name": request.data.get("name", ""),
        #     "invoice": request.data.get("invoice", ""),
        #     "amount": request.data.get("amount", "0.00"),
        # }

        # serializer = TransactionListSerializer(data=data)

        # if not serializer.is_valid():
        #     return Response(
        #         serializer.errors,
        #         status=status.HTTP_400_BAD_REQUEST,
        #     )

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