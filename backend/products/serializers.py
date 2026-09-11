from rest_framework import serializers

from products.models import Product


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

class ProductListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = "__all__"
        read_only_fields = (
            "id",
            "company",
            "created_at",
            "updated_at",
        )

class ProductCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "tran_id",
            "tran_date",
            "entity",
            "name",
            "invoice",
            "amount",
        ]