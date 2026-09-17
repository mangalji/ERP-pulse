from transactions.models import Transaction


class TransactionRepository:
    def list_for_user(
        self,
        *,
        user,
        transaction_type=None,
        record_type=None,
        limit=20,
        offset=0,
    ):
        company = getattr(user, "company", None)

        if company is None:
            return [], 0

        filters = {"company": company}

        if transaction_type:
            filters["transaction_type"] = transaction_type

        if record_type:
            filters["record_type"] = record_type

        queryset = (
            Transaction.objects
            .filter(**filters)
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
