from django.db import models

from transactions.models import Transaction


class TransactionRepository:
    def list_for_user(
        self,
        *,
        user,
        transaction_type,
        record_type,
        limit,
        offset,
    ):
        company = getattr(user, "company", None)

        if company is None:
            return [], 0

        queryset = (
            Transaction.objects
            .filter(
                company=company,
                transaction_type=transaction_type,
                record_type=record_type,
            )
            .annotate(line_count=models.Count("lines"))
            .order_by("-tran_date", "-id")
        )

        count = queryset.count()
        rows = queryset[offset:offset + limit]

        return list(rows), count

    def create(
        self,
        *,
        company,
        transaction_type,
        record_type,
        data,
    ):
        return Transaction.objects.create(
            company=company,
            transaction_type=transaction_type,
            record_type=record_type,
            **data,
        )