from rest_framework import serializers

from sync.models import SyncRun, SyncStage


class SyncStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SyncStage
        fields = (
            'id', 'record_type', 'status', 'records_processed',
            'error_message', 'started_at', 'finished_at',
        )


class SyncRunSerializer(serializers.ModelSerializer):
    stages = SyncStageSerializer(many=True, read_only=True)

    class Meta:
        model = SyncRun
        fields = (
            'id', 'status', 'trigger', 'records_processed', 'records_failed',
            'started_at', 'finished_at', 'created_at', 'stages',
        )


class TriggerSyncSerializer(serializers.Serializer):
    """record_types is optional — omit to sync SyncManager.DEFAULT_SYNC_RECORD_TYPES."""
    record_types = serializers.ListField(child=serializers.CharField(), required=False)
