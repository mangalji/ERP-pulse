"""
Invoice module views.

Provides APIs for batch invoice upload, listing, review, and NetSuite preview.
"""

import os
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from audit.services import audit_service
from audit.models import AuditAction, AuditModule

from invoice.services import invoice_service, start_background_processing
from invoice.validators import InvoiceValidator
from invoice.models import InvoiceBatch, InvoiceFile, ExtractedInvoice, InvoiceReviewHistory, InvoiceNetSuiteMapping, FileStatus, ExtractionStatus, BatchStatus
from invoice.serializers import InvoiceBatchSerializer, InvoiceFileSerializer, ExtractedInvoiceSerializer, InvoiceNetSuiteMappingSerializer
from tenancy.services import company_lifecycle_service

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
MAX_FILE_SIZE_MB = 10
MAX_FILES = 1000


class InvoiceUploadView(views.APIView):
    """POST /api/invoice/upload/"""
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        company = getattr(request.user, 'company', None)
        if company is None:
            return Response({'detail': 'Company context required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            company_lifecycle_service.ensure_operational(
                company=company
            )
        except ValueError as exc:
            return Response(
                {'detail': str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )

        files = request.FILES.getlist('files')
        if not files:
            return Response({'detail': 'No files uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        if len(files) > MAX_FILES:
            return Response({'detail': f'Maximum {MAX_FILES} files allowed per upload.'}, status=status.HTTP_400_BAD_REQUEST)

        for f in files:
            ext = os.path.splitext(f.name)[1][1:].lower()
            if ext not in ALLOWED_EXTENSIONS:
                return Response({'detail': f'Unsupported file type: {f.name}'}, status=status.HTTP_400_BAD_REQUEST)
            size_mb = f.size / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                return Response({'detail': f'File too large: {f.name} ({size_mb:.1f}MB > {MAX_FILE_SIZE_MB}MB)'}, status=status.HTTP_400_BAD_REQUEST)
            if f.size == 0:
                return Response({'detail': f'Empty file: {f.name}'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            batch = InvoiceBatch.objects.create(
                company=company,
                uploaded_by=request.user if request.user.is_authenticated else None,
                total_files=len(files),
                status=BatchStatus.UPLOADING,
            )
            for f in files:
                ext = os.path.splitext(f.name)[1][1:].lower()
                InvoiceFile.objects.create(
                    batch=batch,
                    uploaded_file=f,
                    original_filename=f.name,
                    file_type=ext,
                    file_size=f.size,
                    status=FileStatus.UPLOADED,
                )
        invoice_service.process_batch(str(batch.id))
        batch.refresh_from_db()
        # start_background_processing(batch.id)
        serializer = InvoiceBatchSerializer(batch)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InvoiceBatchViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/invoice/batches/"""
    serializer_class = InvoiceBatchSerializer

    def get_queryset(self):
        company = getattr(self.request, 'company', None)
        if company is None:
            return InvoiceBatch.objects.none()
        return InvoiceBatch.objects.filter(company=company).prefetch_related('files')


class InvoiceFileViewSet(viewsets.ModelViewSet):
    """GET/PATCH/DELETE /api/invoice/files/{id}/"""
    serializer_class = InvoiceFileSerializer
    queryset = InvoiceFile.objects.all()

    def get_object(self):
        company = getattr(self.request, 'company', None)
        if company is not None:
            try:
                company_lifecycle_service.ensure_operational(
                    company=company
                )
            except ValueError as exc:
                raise PermissionError(str(exc))

        obj = get_object_or_404(
            InvoiceFile,
            pk=self.kwargs['pk'],
        )
        if company and obj.batch.company_id != company.id:
            raise PermissionError('File does not belong to your company.')
        return obj

    def destroy(self, request, *args, **kwargs):
        company = getattr(request, 'company', None)

        if company is not None:
            try:
                company_lifecycle_service.ensure_operational(
                    company=company
                )
            except ValueError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_403_FORBIDDEN,
                )
        instance = self.get_object()
        if instance.status not in [FileStatus.UPLOADED, FileStatus.FAILED]:
            return Response({'detail': 'Cannot delete file while processing.'}, status=status.HTTP_400_BAD_REQUEST)
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def retry(self, request, pk=None):
        company = getattr(request, 'company', None)

        if company is not None:
            try:
                company_lifecycle_service.ensure_operational(
                    company=company
                )
            except ValueError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_403_FORBIDDEN,
                )
        invoice_file = self.get_object()
        if invoice_file.status == FileStatus.PROCESSING:
            return Response({'detail': 'File is already processing.'}, status=status.HTTP_400_BAD_REQUEST)
        invoice_service.retry_file(str(invoice_file.id))
        serializer = self.get_serializer(invoice_file)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['patch'])
    def extraction(self, request, pk=None):
        company = getattr(request, 'company', None)

        if company is not None:
            try:
                company_lifecycle_service.ensure_operational(
                    company=company
                )
            except ValueError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_403_FORBIDDEN,
                )
        invoice_file = self.get_object()
        extraction = getattr(invoice_file, 'extraction', None)
        if not extraction:
            return Response({'detail': 'No extraction found.'}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.get('extracted_json')
        if data is None:
            return Response({'detail': 'extracted_json is required.'}, status=status.HTTP_400_BAD_REQUEST)
        extraction.extracted_json = data
        extraction.save()
        serializer = self.get_serializer(invoice_file)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvoiceReviewView(views.APIView):
    """POST /api/invoice/review/{file_id}/"""

    def post(self, request, file_id):
        invoice_file = get_object_or_404(InvoiceFile, pk=file_id)
        company = getattr(request, 'company', None)
        if company:
            if invoice_file.batch.company_id != company.id:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            try:
                company_lifecycle_service.ensure_operational(
                    company=company
                )
            except ValueError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_403_FORBIDDEN,
                )

        extraction = getattr(invoice_file, 'extraction', None)
        if not extraction:
            return Response({'detail': 'No extraction found.'}, status=status.HTTP_404_NOT_FOUND)

        action_type = request.data.get('action')
        new_data = request.data.get('data', {})

        if action_type == 'approve':
            validator = InvoiceValidator()
            errors = validator.validate(extraction.extracted_json or {})
            if errors:
                return Response(
                    {'detail': 'Validation failed', 'errors': [e.to_dict() for e in errors]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            extraction.extraction_status = ExtractionStatus.COMPLETED
            invoice_file.status = FileStatus.APPROVED
            extraction.reviewed_by = request.user
            extraction.reviewed_at = timezone.now()
        elif action_type == 'reject':
            extraction.extraction_status = ExtractionStatus.FAILED
            invoice_file.status = FileStatus.REJECTED
            extraction.reviewed_by = request.user
            extraction.reviewed_at = timezone.now()
        elif action_type == 'edit':
            if not new_data:
                return Response({'detail': 'data is required for edit.'}, status=status.HTTP_400_BAD_REQUEST)
            for field, new_value in new_data.items():
                old_value = extraction.extracted_json.get(field)
                if old_value != new_value:
                    InvoiceReviewHistory.objects.create(
                        extracted_invoice=extraction,
                        field=field,
                        old_value=str(old_value) if old_value is not None else '',
                        new_value=str(new_value) if new_value is not None else '',
                        edited_by=request.user,
                    )
            extraction.extracted_json = new_data
            invoice_file.status = FileStatus.REVIEW_REQUIRED
        else:
            return Response({'detail': 'Invalid action.'}, status=status.HTTP_400_BAD_REQUEST)

        extraction.save()
        invoice_file.save()

        audit_service.log(
            module=AuditModule.INVOICE,
            action=AuditAction.UPDATE if action_type == 'edit' else AuditAction.APPROVE if action_type == 'approve' else AuditAction.REJECT,
            entity='ExtractedInvoice',
            entity_id=str(extraction.id),
            company=invoice_file.batch.company,
            user=request.user,
            old_value={'status': extraction.extraction_status},
            new_value={'status': extraction.extraction_status, 'action': action_type},
        )

        serializer = ExtractedInvoiceSerializer(extraction)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvoiceNetSuiteMappingViewSet(viewsets.ModelViewSet):
    """GET/POST /api/invoice/netsuite-mapping/"""
    serializer_class = InvoiceNetSuiteMappingSerializer
    queryset = InvoiceNetSuiteMapping.objects.filter(is_active=True)


class InvoicePayloadPreviewView(views.APIView):
    """POST /api/invoice/preview-payload/{file_id}/"""

    def post(self, request, file_id):
        invoice_file = get_object_or_404(InvoiceFile, pk=file_id)
        company = getattr(request, 'company', None)
        if company:
            if invoice_file.batch.company_id != company.id:
                return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
            try:
                company_lifecycle_service.ensure_operational(
                    company=company
                )
            except ValueError as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_403_FORBIDDEN,
                )

        extraction = getattr(invoice_file, 'extraction', None)
        if not extraction:
            return Response({'detail': 'No extraction found.'}, status=status.HTTP_404_NOT_FOUND)

        mappings = InvoiceNetSuiteMapping.objects.filter(is_active=True)
        payload = {}
        for mapping in mappings:
            value = extraction.extracted_json.get(mapping.invoice_field)
            if value is not None:
                payload[mapping.netsuite_field] = value

        return Response({'payload': payload}, status=status.HTTP_200_OK)