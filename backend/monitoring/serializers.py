from rest_framework import serializers

from monitoring.models import ErrorLog


class ErrorLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ErrorLog
        fields = (
            "id",
            "level",
            "message",
            "exception_type",
            "method",
            "path",
            "status_code",
            "created_at",
        )