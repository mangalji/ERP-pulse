"""
Business logic for the Dashboard module.

Provides the company-scoped executive summary and Recent Activity
feed for the client dashboard.
"""

from accounts.models import User

DEFAULT_RECENT_LIMIT = 5


class DashboardAggregateService:
    """
    Aggregates cross-module dashboard data for the Executive Dashboard.

    Reuses existing services and models. No fake data. All counts come
    from real database records.
    """

    # def __init__(self):
    #     self.netsuite_service = NetSuiteDataService()

    def get_executive_summary(self, *, user: User) -> dict:
        company = getattr(user, 'company', None)
        if not company:
            return self._empty_summary()

        from accounts.models import User as UserModel
        from invitations.models import Invitation, InvitationStatus
        from netsuite.models import NetSuiteConnection

        # Employee stats
        total_employees = UserModel.objects.filter(company=company).count()
        active_employees = UserModel.objects.filter(company=company, is_active=True).count()

        # Invitation stats
        pending_invitations = Invitation.objects.filter(
            company=company, status=InvitationStatus.PENDING
        ).count()

        # NetSuite connections
        connected_netsuite = NetSuiteConnection.objects.filter(
            company=company, is_active=True
        ).count()

        # Subscription

        subscription_plan = company.plan.name if company else None
        plan_expiry = company.plan_end_date.isoformat() if company.plan_end_date else None

        return {
            'total_employees': total_employees,
            'active_employees': active_employees,
            'pending_invitations': pending_invitations,
            'connected_netsuite': connected_netsuite,
            'subscription_plan': subscription_plan,
            'plan_expiry': plan_expiry,
        }


    def get_activity_feed(self, *, user: User, limit: int = 10) -> list:
        """
        Return only the business activities that belong in the dashboard
        Recent Activity section.

        Included:
        - employee create/delete
        - NetSuite connect/disconnect
        - NetSuite employee assignment
        - subscription renew/expire

        Excluded:
        - login/logout
        - settings
        - RBAC
        - invoice/OCR
        - dashboard views
        - generic updates
        """
        from django.db.models import Q
        from audit.models import AuditAction, AuditLog, AuditModule

        company = getattr(user, 'company', None)
        if not company:
            return []

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10

        limit = max(1, min(limit, 50))

        logs = (
            AuditLog.objects
            .filter(company=company)
            .filter(
                Q(
                    module=AuditModule.EMPLOYEE,
                    action__in=[
                        AuditAction.CREATE,
                        AuditAction.DELETE,
                    ],
                )
                |
                Q(
                    module=AuditModule.NETSUITE,
                    action__in=[
                        AuditAction.CONNECT,
                        AuditAction.DISCONNECT,
                        AuditAction.ASSIGN,
                    ],
                )
                |
                Q(
                    module=AuditModule.SUBSCRIPTION,
                    action=AuditAction.UPDATE,
                )
            )
            .select_related('user')
            .order_by('-created_at')
        )

        activities = []

        for log in logs:
            new_value = log.new_value or {}
            old_value = log.old_value or {}

            if not isinstance(new_value, dict):
                new_value = {}

            if not isinstance(old_value, dict):
                old_value = {}

            event_data = new_value or old_value
            event = event_data.get('event')

            actor = self._audit_actor_name(log.user)

            # ---------------------------------------------------------
            # 1. EMPLOYEE CREATED
            # ---------------------------------------------------------
            if (
                log.module == AuditModule.EMPLOYEE
                and log.action == AuditAction.CREATE
                and event == 'created'
            ):
                employee_name = (
                    new_value.get('employee_name')
                    or new_value.get('name')
                    or log.entity
                    or 'Unknown employee'
                )

                activities.append({
                    'id': str(log.id),
                    'type': 'employee_created',
                    'text': f'{actor} created employee {employee_name}',
                    'time': log.created_at,
                    'meta': {
                        'actor': actor,
                        'employee_name': employee_name,
                    },
                })

            # ---------------------------------------------------------
            # 2. EMPLOYEE DELETED
            # ---------------------------------------------------------
            elif (
                log.module == AuditModule.EMPLOYEE
                and log.action == AuditAction.DELETE
                and event == 'deleted'
            ):
                employee_name = (
                    old_value.get('employee_name')
                    or old_value.get('name')
                    or new_value.get('employee_name')
                    or log.entity
                    or 'Unknown employee'
                )

                activities.append({
                    'id': str(log.id),
                    'type': 'employee_deleted',
                    'text': f'{actor} deleted employee {employee_name}',
                    'time': log.created_at,
                    'meta': {
                        'actor': actor,
                        'employee_name': employee_name,
                    },
                })

            # ---------------------------------------------------------
            # 3. NETSUITE CONNECTED
            # ---------------------------------------------------------
            elif (
                log.module == AuditModule.NETSUITE
                and log.action == AuditAction.CONNECT
                and event == 'connected'
            ):
                account_name = (
                    new_value.get('account_name')
                    or new_value.get('client_name')
                    or new_value.get('account_id')
                    or log.entity
                    or 'NetSuite account'
                )

                activities.append({
                    'id': str(log.id),
                    'type': 'netsuite_connected',
                    'text': f'{actor} connected NetSuite account {account_name}',
                    'time': log.created_at,
                    'meta': {
                        'actor': actor,
                        'account_name': account_name,
                    },
                })

            # ---------------------------------------------------------
            # 4. NETSUITE DISCONNECTED
            # ---------------------------------------------------------
            elif (
                log.module == AuditModule.NETSUITE
                and log.action == AuditAction.DISCONNECT
                and event == 'disconnected'
            ):
                account_name = (
                    old_value.get('account_name')
                    or old_value.get('client_name')
                    or old_value.get('account_id')
                    or new_value.get('account_name')
                    or new_value.get('client_name')
                    or new_value.get('account_id')
                    or log.entity
                    or 'NetSuite account'
                )

                activities.append({
                    'id': str(log.id),
                    'type': 'netsuite_disconnected',
                    'text': f'{actor} disconnected NetSuite account {account_name}',
                    'time': log.created_at,
                    'meta': {
                        'actor': actor,
                        'account_name': account_name,
                    },
                })

            # ---------------------------------------------------------
            # 5. NETSUITE EMPLOYEE ASSIGNMENT
            # ---------------------------------------------------------
            elif (
                log.module == AuditModule.NETSUITE
                and log.action == AuditAction.ASSIGN
                and event == 'employees_assigned'
            ):
                account_name = (
                    new_value.get('account_name')
                    or new_value.get('client_name')
                    or new_value.get('account_id')
                    or log.entity
                    or 'NetSuite account'
                )

                employee_names = (
                    new_value.get('employee_names')
                    or new_value.get('employees')
                    or []
                )

                if not isinstance(employee_names, list):
                    employee_names = [str(employee_names)]

                employee_names = [str(name) for name in employee_names if name]

                employee_count = new_value.get(
                    'employee_count',
                    len(employee_names),
                )

                activities.append({
                    'id': str(log.id),
                    'type': 'netsuite_employees_assigned',
                    'text': (
                        f'{actor} assigned {employee_count} employees '
                        f'to NetSuite account {account_name}'
                        + (
                            f": {', '.join(employee_names)}"
                            if employee_names
                            else ''
                        )
                    ),
                    'time': log.created_at,
                    'meta': {
                        'actor': actor,
                        'account_name': account_name,
                        'employee_count': employee_count,
                        'employee_names': employee_names,
                    },
                })

            # ---------------------------------------------------------
            # 6. SUBSCRIPTION RENEWED
            # ---------------------------------------------------------
            elif (
                log.module == AuditModule.SUBSCRIPTION
                and log.action == AuditAction.UPDATE
                and event == 'renewed'
            ):
                plan_name = (
                    new_value.get('plan_name')
                    or old_value.get('plan_name')
                    or 'subscription'
                )

                activities.append({
                    'id': str(log.id),
                    'type': 'subscription_renewed',
                    'text': f'{actor} renewed {plan_name}',
                    'time': log.created_at,
                    'meta': {
                        'actor': actor,
                        'plan_name': plan_name,
                    },
                })

            # ---------------------------------------------------------
            # 7. SUBSCRIPTION EXPIRED
            # ---------------------------------------------------------
            elif (
                log.module == AuditModule.SUBSCRIPTION
                and log.action == AuditAction.UPDATE
                and event == 'expired'
            ):
                plan_name = (
                    new_value.get('plan_name')
                    or old_value.get('plan_name')
                    or 'subscription'
                )

                activities.append({
                    'id': str(log.id),
                    'type': 'subscription_expired',
                    'text': f'{plan_name} expired',
                    'time': log.created_at,
                    'meta': {
                        'actor': actor,
                        'plan_name': plan_name,
                    },
                })

            if len(activities) >= limit:
                break

        return activities

    @staticmethod
    def _audit_actor_name(user) -> str:
        if not user:
            return 'System'

        full_name = (
            f'{getattr(user, "first_name", "")} '
            f'{getattr(user, "last_name", "")}'
        ).strip()

        return full_name or getattr(user, 'email', 'User')

    def _empty_summary(self) -> dict:
        return {
            'total_employees': 0,
            'active_employees': 0,
            'pending_invitations': 0,
            'connected_netsuite': 0,
            'subscription_plan': None,
            'plan_expiry': None,
        }
