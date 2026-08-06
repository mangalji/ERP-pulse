"""
Demo Request service layer.

All business logic for demo requests lives here. Views stay thin and
only delegate to this service. Status changes are recorded through the
existing AuditService.
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.db import transaction
from audit.models import AuditAction, AuditModule
from audit.services import audit_service

from .models import DemoRequest

User = get_user_model()


class DemoRequestService:
    """Business logic for demo request handling."""

    #: Demo requests that are not yet closed (used for duplicate checks).
    ACTIVE_STATUSES = (
        DemoRequest.Status.NEW,
        DemoRequest.Status.CONTACTED,
        DemoRequest.Status.DEMO_SCHEDULED,
        DemoRequest.Status.DEMO_COMPLETED,
        DemoRequest.Status.PROPOSAL_SENT,
    )

    @staticmethod
    def _audit_user(request=None):
        """Return only a real authenticated user for audit logging."""
        user = getattr(request, "user", None) if request else None
        if user is not None and getattr(user, "is_authenticated", False):
            return user
        return None

    @staticmethod
    def _json_safe(value):
        """Convert model ids/UUIDs to JSON-serializable strings."""
        if value is None:
            return None
        if hasattr(value, "hex") and hasattr(value, "__int__"):
            return str(value)
        return value

    def _generate_demo_request_number(self) -> str:
        """Generate a unique demo request number like ``DR-2026-000001``."""
        year = timezone.now().year
        prefix = f"DR-{year}-"
        last = (
            DemoRequest.objects.filter(demo_request_number__startswith=prefix)
            .order_by("-demo_request_number")
            .values_list("demo_request_number", flat=True)
            .first()
        )
        if last:
            try:
                seq = int(last.rsplit("-", 1)[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1
        return f"{prefix}{seq:06d}"

    @staticmethod
    def _is_agsuite_user(user) -> bool:
        """AGSuite employees are users not tied to a client company."""
        if getattr(user, "is_superuser", False):
            return True
        return user is not None and getattr(user, "company", None) is None

    def create_request(self, data: dict, created_by=None) -> DemoRequest:
        """
        Create a new demo request.
        """
        active_statuses = [
            DemoRequest.Status.NEW,
            DemoRequest.Status.CONTACTED,
            DemoRequest.Status.DEMO_SCHEDULED,
            DemoRequest.Status.DEMO_COMPLETED,
            DemoRequest.Status.PROPOSAL_SENT,
        ]

        existing = DemoRequest.objects.filter(
            business_email__iexact=data["business_email"],
            status__in=active_statuses,
        ).exists()

        if existing:
            raise ValueError("An active demo request already exists.")

        with transaction.atomic():
            request = DemoRequest.objects.create(**data)

            if not request.demo_request_number:
                request.demo_request_number = (
                    f"DR-{timezone.now().year}-{request.id:06d}"
                )
                request.save(update_fields=["demo_request_number"])

            audit_service.log(
                user=created_by,
                module=AuditModule.DEMO,
                action=AuditAction.CREATE,
                entity="DemoRequest",
                entity_id=str(request.id),
                company=None,
                old_value=None,
                new_value={
                    "company_name": request.company_name,
                    "business_email": request.business_email,
                },
            )

        return request

    def list_requests(self, *, request, status=None, search=None):
        """Return a paginated list of demo requests."""
        qs = DemoRequest.objects.select_related("assigned_to").all()
        if status:
            qs = qs.filter(status=status)
        if search:
            qs = qs.filter(
                models.Q(company_name__icontains=search)
                | models.Q(business_email__icontains=search)
                | models.Q(demo_request_number__icontains=search)
            )
        qs = qs.order_by("-created_at")

        try:
            offset = int(request.query_params.get("offset", 0))
        except (ValueError, TypeError):
            offset = 0
        try:
            limit = int(request.query_params.get("limit", 20))
        except (ValueError, TypeError):
            limit = 20
        offset = max(0, offset)
        limit = max(1, min(limit, 100))

        count = qs.count()
        page = qs[offset : offset + limit]
        return page, count, offset, limit

    def get_request(self, *, request_id) -> DemoRequest:
        """Retrieve a single demo request."""
        return DemoRequest.objects.select_related("assigned_to").get(pk=request_id)

    def assign_sales(self, *, request_id, user_id, notes=None, request=None):
        """
        Assign an AGSuite sales person.
        """
        request_obj = DemoRequest.objects.select_related("assigned_to").get(pk=request_id)
        user = User.objects.get(pk=user_id)

        if user.company is not None and not user.is_superuser:
            raise ValueError(
                "Only AGSuite users can be assigned."
            )

        request_obj.assigned_to = user
        request_obj.save(update_fields=["assigned_to"])

        audit_service.log(
            module=AuditModule.DEMO,
            action=AuditAction.UPDATE,
            entity="DemoRequest",
            entity_id=str(request_obj.id),
            company=None,
            user=self._audit_user(request),
            old_value={"assigned_to": None},
            new_value={"assigned_to": str(user.id)},
        )

        return request_obj

    def approve(self, *, request_id, notes=None, request=None) -> DemoRequest:
        """Approve a demo request."""
        req = DemoRequest.objects.get(pk=request_id)
    
        old_value = {"status": req.status}
    
        req.status = DemoRequest.Status.APPROVED
    
        if notes is not None:
            req.notes = notes
    
        req.save(update_fields=["status", "notes"])
    
        audit_service.log(
            module=AuditModule.DEMO,
            action=AuditAction.UPDATE,
            entity="DemoRequest",
            entity_id=str(req.id),
            company=None,
            user=self._audit_user(request),
            old_value=old_value,
            new_value={
                "status": req.status,
                "notes": req.notes,
            },
        )
    
        return req

    def reject(self, *, request_id, notes=None, request=None) -> DemoRequest:
        """Reject a demo request."""
        req = DemoRequest.objects.get(pk=request_id)
        old_value = {"status": req.status}
        req.status = DemoRequest.Status.REJECTED
        if notes is not None:
            req.notes = notes
        req.save(update_fields=["status", "notes"])
        audit_service.log(
            module=AuditModule.DEMO,
            action=AuditAction.REJECT,
            entity="DemoRequest",
            entity_id=str(req.id),
            user=self._audit_user(request),
            old_value=old_value,
            new_value={"status": req.status},
        )
        return req

    def convert_to_company(self, *, request_id, request=None, plan_id=None, module_ids=None, admin_email=None, admin_first_name=None, admin_last_name=None) -> dict:
        """
        Convert an approved demo request into a company.
        
        Flow:
        1. Create Company
        2. Assign Plan
        3. Assign Modules
        4. Create Company Admin User (inactive, no password)
        5. Create Invitation
        6. Audit Log
        7. Return Company
        """
        from tenancy.models import Company, CompanyModule
        from superadmin.models import Plan, CompanyPlan, CompanyPlanStatus
        from invitations.models import Invitation, InvitationStatus
        from invitations.services import invitation_service
        from django.utils import timezone
        from datetime import timedelta

        demo_request = DemoRequest.objects.get(pk=request_id)

        if demo_request.status not in [DemoRequest.Status.APPROVED, DemoRequest.Status.CONTACTED]:
            raise ValueError('Only approved or contacted demo requests can be converted.')

        with transaction.atomic():
            # 1. Create Company
            base_code = demo_request.company_name.replace(' ', '').replace('-', '')[:10].upper()
            code = base_code
            counter = 1
            while Company.objects.filter(code=code).exists():
                code = f"{base_code[:8]}{counter}"
                counter += 1

            company = Company.objects.create(
                name=demo_request.company_name,
                code=code,
                status=Company.Status.TRIAL,
                contact_email=demo_request.business_email,
                contact_phone=demo_request.phone,
                country=demo_request.country,
            )

            # 2. Assign Plan
            if plan_id:
                plan = Plan.objects.filter(pk=plan_id, status=Plan.Status.ACTIVE).first()
                if plan:
                    CompanyPlan.objects.create(
                        company=company,
                        plan=plan,
                        start_date=timezone.now().date(),
                        status=CompanyPlanStatus.TRIAL,
                    )

            # 3. Assign Modules
            if module_ids:
                modules = Module.objects.filter(pk__in=module_ids, is_active=True)
                for module in modules:
                    CompanyModule.objects.get_or_create(
                        company=company,
                        module=module,
                        defaults={'enabled': True},
                    )

            # 4. Create Company Admin User (inactive, no password)
            admin_email = admin_email or demo_request.business_email
            admin_first_name = admin_first_name or demo_request.contact_person.split(' ')[0]
            admin_last_name = admin_last_name or ' '.join(demo_request.contact_person.split(' ')[1:]) or 'Admin'

            admin_user = User.objects.create(
                email=admin_email.lower().strip(),
                first_name=admin_first_name,
                last_name=admin_last_name,
                company=company,
                is_active=False,
                is_email_verified=False,
            )

            # 5. Create Invitation
            invitation = Invitation.objects.create(
                email=admin_email.lower().strip(),
                company=company,
                expires_at=timezone.now() + timedelta(days=7),
                created_by=request.user if request and request.user.is_authenticated else None,
            )

            # 6. Send invitation email
            invitation_service.send_invitation(invitation_id=invitation.id, request=request)

            # 7. Audit logs
            audit_service.log(
                module=AuditModule.COMPANY,
                action=AuditAction.CREATE,
                entity='Company',
                entity_id=str(company.id),
                company=company,
                user=self._audit_user(request),
                old_value=None,
                new_value={
                    'name': company.name,
                    'code': company.code,
                    'contact_email': company.contact_email,
                },
            )

            audit_service.log(
                module=AuditModule.INVITATION,
                action=AuditAction.CREATE,
                entity='Invitation',
                entity_id=str(invitation.id),
                company=company,
                user=self._audit_user(request),
                old_value=None,
                new_value={
                    'email': invitation.email,
                    'company': company.name,
                },
            )

            # 8. Update demo request status
            demo_request.status = DemoRequest.Status.ONBOARDED
            demo_request.save(update_fields=['status'])

        return {
            'company_id': str(company.id),
            'company_name': company.name,
            'company_code': company.code,
            'invitation_id': str(invitation.id),
            'admin_email': admin_email,
            'message': 'Company created and invitation sent successfully.',
        }


demo_request_service = DemoRequestService()
