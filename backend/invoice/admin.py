from django.contrib import admin

from invoice.models import InvoiceBatch, InvoiceFile


@admin.register(InvoiceBatch)
class InvoiceBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'uploaded_by', 'total_files', 'processed_files', 'failed_files', 'status', 'created_at')
    list_filter = ('status', 'company', 'created_at')
    search_fields = ('company__name', 'uploaded_by__email')
    readonly_fields = ('id', 'created_at')


@admin.register(InvoiceFile)
class InvoiceFileAdmin(admin.ModelAdmin):
    list_display = ('id', 'batch', 'original_filename', 'file_type', 'file_size', 'status', 'processing_time', 'created_at')
    list_filter = ('status', 'file_type', 'batch')
    search_fields = ('original_filename', 'batch__id')
