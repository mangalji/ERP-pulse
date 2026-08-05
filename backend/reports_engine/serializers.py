from rest_framework import serializers

from reports_engine.models import ReportHistory, ReportTemplate, ScheduledReport


class ReportTemplateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = ReportTemplate
        fields = '__all__'
        read_only_fields = ('id', 'company', 'created_by', 'created_at', 'updated_at')


class ScheduledReportSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = ScheduledReport
        fields = '__all__'
        read_only_fields = ('id', 'company', 'created_by', 'created_at', 'updated_at')


class ReportHistorySerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)

    class Meta:
        model = ReportHistory
        fields = '__all__'
        read_only_fields = (
            'id',
            'company',
            'created_by',
            'record_count',
            'file_size',
            'execution_time_ms',
            'file',
            'download_count',
            'generated_at',
        )
