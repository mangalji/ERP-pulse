"""
Django management command to seed demo data for AGSuite ERP demonstration.

Creates a demo company with:
- Company Admin and employees
- Invoice batches and files
- OCR uploads and documents
- AI conversations and messages
- Report history
- Dashboard-ready NetSuite connections

Usage::

    python manage.py seed_demo_data

Optional flags:
    --company-name  : Override demo company name (default: "Demo Company")
    --email-domain  : Override email domain (default: "demo.agsuiterp.com")
    --clear         : Delete existing demo data before seeding
"""

import uuid
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta, date
import random

from accounts.models import User
from invitations.models import Invitation, InvitationStatus
from rbac.models import Role, UserRole
from tenancy.models import Company, CompanyModule, Module, CompanyStatus
from superadmin.models import Plan, CompanyPlan, CompanyPlanStatus, PlanStatus
from invoice.models import InvoiceBatch, InvoiceFile, ExtractedInvoice, FileStatus, ExtractionStatus, BatchStatus
from ocr.models import OCRUpload, OCRDocument, OCRDocumentStatus, OCRQualityMetric, DocumentType
from ai.models import AIConversation, AIMessage
from reports_engine.models import ReportHistory, ReportType, ReportStatus, ExportFormat
from dashboard.services import DashboardAggregateService
from demo.models import DemoRequest


class Command(BaseCommand):
    help = 'Seed demo data for AGSuite ERP demonstration.'

    def add_arguments(self, parser):
        parser.add_argument('--company-name', type=str, default='Demo Company')
        parser.add_argument('--email-domain', type=str, default='demo.agsuiterp.com')
        parser.add_argument('--clear', action='store_true', help='Delete existing demo data before seeding')

    def handle(self, *args, **options):
        if options['clear']:
            self._clear_demo_data(options['company_name'])

        self.stdout.write(self.style.MIGRATE_HEADING('Seeding demo data...'))

        with transaction.atomic():
            company = self._create_company(options['company_name'])
            plan = self._create_plan()
            self._assign_plan(company, plan)
            self._assign_modules(company)
            admin = self._create_admin(company, options['email_domain'])
            employees = self._create_employees(company, admin, options['email_domain'])
            self._create_invoices(company, admin, employees)
            self._create_ocr_data(company, admin)
            self._create_ai_history(company, admin)
            self._create_reports(company, admin)
            self._create_dashboard_data(company, admin)

        self.stdout.write(self.style.SUCCESS('Demo data seeded successfully!'))
        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('Demo Credentials:'))
        self.stdout.write(f'  Company: {options["company_name"]}')
        self.stdout.write(f'  Admin: admin@{options["email_domain"]} / Admin@123')
        self.stdout.write(f'  Employee: employee@{options["email_domain"]} / Employee@123')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Note: Users are created as inactive. Use the invitation system to activate them.'))

    def _clear_demo_data(self, company_name):
        self.stdout.write(self.style.WARNING('Clearing existing demo data...'))
        companies = Company.objects.filter(name=company_name)
        for company in companies:
            User.objects.filter(company=company).delete()
            InvoiceBatch.objects.filter(company=company).delete()
            OCRUpload.objects.filter(user__company=company).delete()
            AIConversation.objects.filter(user__company=company).delete()
            ReportHistory.objects.filter(company=company).delete()
            CompanyModule.objects.filter(company=company).delete()
            CompanyPlan.objects.filter(company=company).delete()
            company.delete()
        self.stdout.write(self.style.SUCCESS('Demo data cleared.'))

    def _create_company(self, name):
        code = name.replace(' ', '').replace('-', '')[:10].upper()
        company, created = Company.objects.get_or_create(
            name=name,
            defaults={
                'code': code,
                'status': CompanyStatus.ACTIVE,
                'contact_email': f'admin@{code.lower()}.com',
                'contact_phone': '+91 98765 43210',
                'country': 'India',
            },
        )
        if created:
            self.stdout.write(f'  Created company: {company.name}')
        return company

    def _create_plan(self):
        plan, created = Plan.objects.get_or_create(
            name='Professional',
            defaults={
                'description': 'Professional plan for growing businesses',
                'monthly_price': 24999,
                'yearly_price': 249999,
                'max_employees': 50,
                'max_ocr_documents': 500,
                'max_storage_gb': 50,
                'status': PlanStatus.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f'  Created plan: {plan.name}')
        return plan

    def _assign_plan(self, company, plan):
        company_plan, created = CompanyPlan.objects.get_or_create(
            company=company,
            plan=plan,
            defaults={
                'start_date': date.today() - timedelta(days=30),
                'end_date': date.today() + timedelta(days=335),
                'status': CompanyPlanStatus.ACTIVE,
                'is_auto_renew': True,
            },
        )
        if created:
            self.stdout.write(f'  Assigned plan: {plan.name} to {company.name}')

    def _assign_modules(self, company):
        modules = Module.objects.filter(is_active=True)
        for module in modules:
            CompanyModule.objects.get_or_create(
                company=company,
                module=module,
                defaults={'enabled': True},
            )
        self.stdout.write(f'  Assigned {modules.count()} modules to {company.name}')

    def _create_admin(self, company, email_domain):
        email = f'admin@{email_domain}'
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'first_name': 'Admin',
                'last_name': 'User',
                'company': company,
                'is_active': False,
                'is_email_verified': False,
            },
        )
        if created:
            user.set_password('Admin@123')
            user.save()
            self.stdout.write(f'  Created admin: {email}')

        role, _ = Role.objects.get_or_create(
            name='Company Admin',
            company=company,
            defaults={'description': 'Company administrator', 'is_system': True},
        )
        UserRole.objects.get_or_create(user=user, role=role)
        return user

    def _create_employees(self, company, admin, email_domain):
        employees = []
        for i in range(1, 6):
            email = f'employee{i}@{email_domain}'
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': f'Employee {i}',
                    'last_name': 'User',
                    'company': company,
                    'department': random.choice(['Finance', 'Operations', 'Sales', 'IT']),
                    'designation': random.choice(['Analyst', 'Manager', 'Specialist', 'Coordinator']),
                    'is_active': False,
                    'is_email_verified': False,
                },
            )
            if created:
                user.set_password('Employee@123')
                user.save()
            employees.append(user)

        role, _ = Role.objects.get_or_create(
            name='Employee',
            company=company,
            defaults={'description': 'Standard employee', 'is_system': True},
        )
        for emp in employees:
            UserRole.objects.get_or_create(user=emp, role=role)

        self.stdout.write(f'  Created {len(employees)} employees')
        return employees

    def _create_invoices(self, company, admin, employees):
        for i in range(1, 11):
            batch = InvoiceBatch.objects.create(
                company=company,
                uploaded_by=admin,
                total_files=random.randint(1, 5),
                status=BatchStatus.COMPLETED,
            )
            for j in range(1, random.randint(2, 6)):
                status = random.choice([
                    FileStatus.EXTRACTED,
                    FileStatus.APPROVED,
                    FileStatus.READY_FOR_NETSUITE,
                    FileStatus.FAILED,
                ])
                invoice_file = InvoiceFile.objects.create(
                    batch=batch,
                    original_filename=f'invoice_{i}_{j}.pdf',
                    file_type='pdf',
                    file_size=random.randint(50000, 500000),
                    status=status,
                )
                if status in [FileStatus.EXTRACTED, FileStatus.APPROVED]:
                    ExtractedInvoice.objects.create(
                        invoice_file=invoice_file,
                        extracted_json={
                            'vendor': f'Vendor {random.randint(1, 10)}',
                            'invoice_number': f'INV-{1000 + i * 10 + j}',
                            'invoice_date': (date.today() - timedelta(days=random.randint(1, 30))).isoformat(),
                            'total_amount': round(random.uniform(1000, 50000), 2),
                            'currency': 'USD',
                        },
                        confidence_score=round(random.uniform(0.7, 0.99), 2),
                        extraction_status=ExtractionStatus.COMPLETED,
                    )

        self.stdout.write('  Created invoice batches and files')

    def _create_ocr_data(self, company, admin):
        for i in range(1, 21):
            status = random.choice([OCRUpload.Status.COMPLETED, OCRUpload.Status.FAILED, OCRUpload.Status.PROCESSING])
            upload = OCRUpload.objects.create(
                user=admin,
                original_filename=f'document_{i}.pdf',
                stored_filename=f'{uuid.uuid4().hex}.pdf',
                file_size=random.randint(50000, 500000),
                mime_type='application/pdf',
                extension='pdf',
                file_hash=uuid.uuid4().hex,
                status=status,
            )
            if status == OCRUpload.Status.COMPLETED:
                document = OCRDocument.objects.create(
                    upload=upload,
                    user=admin,
                    company=company,
                    document_type=random.choice([
                        DocumentType.INVOICE,
                        DocumentType.PURCHASE_ORDER,
                        DocumentType.SALES_ORDER,
                    ]),
                    status=random.choice([
                        OCRDocumentStatus.EXTRACTED,
                        OCRDocumentStatus.APPROVED,
                        OCRDocumentStatus.READY_FOR_NETSUITE,
                    ]),
                    overall_confidence=round(random.uniform(0.7, 0.95), 2),
                )
                OCRQualityMetric.objects.create(
                    upload=upload,
                    user=admin,
                    company=company,
                    document_type=document.document_type,
                    processing_time_ms=random.randint(500, 3000),
                    overall_confidence=document.overall_confidence,
                    success=True,
                )

        self.stdout.write('  Created OCR uploads and documents')

    def _create_ai_history(self, company, admin):
        for i in range(1, 11):
            conversation = AIConversation.objects.create(
                user=admin,
                title=f'Demo Conversation {i}',
            )
            for j in range(1, 6):
                AIMessage.objects.create(
                    conversation=conversation,
                    role=random.choice([AIMessage.Role.USER, AIMessage.Role.ASSISTANT]),
                    content=f'Sample message {j} in conversation {i}',
                )

        self.stdout.write('  Created AI conversations and messages')

    def _create_reports(self, company, admin):
        for report_type in ReportType.values:
            ReportHistory.objects.create(
                company=company,
                created_by=admin,
                report_type=report_type,
                format=random.choice([ExportFormat.PDF, ExportFormat.XLSX, ExportFormat.CSV]),
                status=random.choice([ReportStatus.COMPLETED, ReportStatus.PROCESSING, ReportStatus.FAILED]),
                record_count=random.randint(100, 10000),
                file_size=random.randint(10000, 5000000),
                execution_time_ms=random.randint(500, 5000),
            )

        self.stdout.write('  Created report history')

    def _create_dashboard_data(self, company, admin):
        service = DashboardAggregateService()
        service.get_executive_summary(user=admin)
        service.get_invoice_charts(user=admin)
        service.get_activity_feed(user=admin, limit=10)
        self.stdout.write('  Dashboard data prepared')

