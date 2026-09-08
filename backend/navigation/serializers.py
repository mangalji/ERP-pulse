from rest_framework import serializers


class TransactionMenuItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    key = serializers.CharField()
    route = serializers.CharField()
    query_params = serializers.DictField()
    icon = serializers.CharField()
    module_code = serializers.CharField()
    requires_netsuite = serializers.BooleanField()
    sort_order = serializers.IntegerField()
    children = serializers.ListField(child=serializers.DictField())


class TransactionMenuSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    key = serializers.CharField()
    icon = serializers.CharField()
    module_code = serializers.CharField()
    requires_netsuite = serializers.BooleanField()
    sort_order = serializers.IntegerField()
    children = serializers.ListField(child=serializers.DictField())
