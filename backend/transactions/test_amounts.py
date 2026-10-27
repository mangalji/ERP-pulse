from decimal import Decimal

from django.test import SimpleTestCase

from transactions.models import Transaction
from transactions.serializers import TransactionUpdateSerializer


class TransactionAmountTests(SimpleTestCase):
    def test_calculates_and_rounds_total(self):
        instance = Transaction(base_amount=None, gst_percentage=None, amount=Decimal('50.00'))
        serializer = TransactionUpdateSerializer(instance, data={'base_amount': '99.99', 'gst_percentage': '18'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['amount'], Decimal('117.99'))

    def test_preserves_old_total_when_new_fields_are_empty(self):
        instance = Transaction(base_amount=None, gst_percentage=None, amount=Decimal('50.00'))
        serializer = TransactionUpdateSerializer(instance, data={'base_amount': None, 'gst_percentage': None}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn('amount', serializer.validated_data)

    def test_rejects_incomplete_amount_and_gst(self):
        instance = Transaction(base_amount=None, gst_percentage=None, amount=Decimal('50.00'))
        serializer = TransactionUpdateSerializer(instance, data={'base_amount': '100.00'}, partial=True)
        self.assertFalse(serializer.is_valid())
