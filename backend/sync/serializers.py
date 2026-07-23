from rest_framework import serializers
from sync.models import SyncRun, SyncStage
from netsuite.constants import NetSuiteRecordType

# NetSuiteRecordType.is_valid() currently recognizes 19 distinct record
# types — capped a bit above that (not exactly 19) so this doesn't need
# updating every time a new record type is added there.
MAX_RECORD_TYPES_PER_REQUEST = 25

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
    """
    record_types is optional — omit to sync SyncManager.DEFAULT_SYNC_RECORD_TYPES.

    Each value is validated against NetSuiteRecordType's real whitelist
    (previously this accepted any string at all — arbitrary garbage
    would have created a SyncRun + SyncStage row before failing later,
    deep in SyncManager._run_stage). max_length caps the list itself so
    a caller can't force thousands of SyncStage rows to be created in
    one request.
    """
    record_types = serializers.ListField(child=serializers.CharField(max_length=50), required=False, max_length=MAX_RECORD_TYPES_PER_REQUEST)

    def validate_record_types(self, value):
        invalid = [rt for rt in value if not NetSuiteRecordType.is_valid(rt)]
        if invalid:
            raise serializers.ValidationError(
                f'Unsupported record types(s): {", ".join(invalid)}.'
            )
        # Dedupe while preserving order — a caller sending the same type
        # twice shouldn't get two SyncStage rows for it.
        seen = set()
        deduped = []
        for record_type in value:
            if record_type not in seen:
                seen.add(record_type)
                deduped.append(record_type)
        return deduped

