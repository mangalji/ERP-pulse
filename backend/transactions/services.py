from transactions.repositories import TransactionRepository


class TransactionService:
    def __init__(self, repository=None):
        self.repository = repository or TransactionRepository()

    def list_transactions(
        self,
        *,
        user,
        transaction_type=None,
        record_type=None,
        limit=20,
        offset=0,
    ):
        if record_type and not transaction_type:
            raise ValueError(
                "transaction_type is required when record_type is provided."
            )

        rows, count = self.repository.list_for_user(
            user=user,
            transaction_type=transaction_type,
            record_type=record_type,
            limit=limit,
            offset=offset,
        )

        return rows, count

    def create_transaction(self, *, user, transaction_type, record_type, data):
        company = getattr(user, "company", None)

        if company is None:
            raise ValueError("User is not associated with a company.")

        return self.repository.create(
            company=company,
            transaction_type=transaction_type,
            record_type=record_type,
            data=data,
        )


transaction_service = TransactionService()
