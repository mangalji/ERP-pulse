"""Shared invitation-status presentation rules."""

from invitations.models import Invitation, InvitationStatus


def get_user_invitation_status(user, *, latest_invitation_by_email=None):
    """Return the invitation lifecycle state for a user.

    ``latest_invitation_by_email`` lets list endpoints pass preloaded data and
    avoid one invitation query per employee.
    """
    if latest_invitation_by_email is not None:
        invitation = latest_invitation_by_email.get(user.email)
    else:
        invitation = (
            Invitation.objects.filter(
                email__iexact=user.email,
                company=user.company,
            )
            .order_by('-created_at')
            .first()
        )

    if invitation is None:
        return 'NONE'
    if invitation.status == InvitationStatus.ACCEPTED:
        return 'ACCEPTED'
    if invitation.is_expired():
        return 'EXPIRED'
    return invitation.status
