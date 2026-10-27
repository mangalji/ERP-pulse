from decimal import Decimal, ROUND_HALF_UP

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
    company_name = serializers.CharField(source="company.name", read_only=True)

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
    def validate(self, attrs):
        base = attrs.get("base_amount", self.instance.base_amount if self.instance else None)
        gst = attrs.get("gst_percentage", self.instance.gst_percentage if self.instance else None)
        if base is None and gst is None and self.instance is not None:
            return attrs  # Preserve historical totals until the user enters both values.
        if base is None or gst is None:
            raise serializers.ValidationError("Enter both Amount and GST percentage; use 0 for no GST.")
        if base < 0 or gst < 0:
            raise serializers.ValidationError("Amount and GST percentage cannot be negative.")
        total = (base * (Decimal("1") + gst / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if total >= Decimal("10000000000000000"):
            raise serializers.ValidationError("Calculated total amount is too large.")
        attrs["amount"] = total
        return attrs

    class Meta:
        model = Transaction
        fields = [
            "tran_id",
            "tran_date",
            "due_date",
            "subsidiary",
            "entity",
            "name",
            "invoice",
            "base_amount",
            "gst_percentage",
            "amount",
        ]
        read_only_fields = ["amount"]


class TransactionUpdateSerializer(TransactionCreateSerializer):
    class Meta(TransactionCreateSerializer.Meta):
        fields = TransactionCreateSerializer.Meta.fields + ["transaction_type", "record_type"]
