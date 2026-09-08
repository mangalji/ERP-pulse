from transactions.repositories import TransactionRepository


class TransactionService:
    def __init__(self, repository=None):
        self.repository = repository or TransactionRepository()

    def list_transactions(
        self,
        *,
        user,
        transaction_type,
        record_type,
        limit=20,
        offset=0,
    ):
        if not transaction_type:
            raise ValueError("transaction_type is required.")

        if not record_type:
            raise ValueError("record_type is required.")

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