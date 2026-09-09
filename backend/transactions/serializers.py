from rest_framework import serializers

from transactions.models import Transaction


# class TransactionListSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Transaction
#         fields = [
#             "id",
#             "tran_id",
#             "tran_date",
#             "entity",
#             "name",
#             "invoice",
#             "amount",
#         ]
#         read_only_fields = [
#             "id",
#         ]

class TransactionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"
        read_only_fields = (
            "id",
            "company",
            "created_at",
            "updated_at",
        )

class TransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "tran_id",
            "tran_date",
            "entity",
            "name",
            "invoice",
            "amount",
        ]