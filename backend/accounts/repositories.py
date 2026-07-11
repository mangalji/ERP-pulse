from accounts.models import OTP, User


class UserRepository:

    """
    Persistence-only operations for the User model.

    Contains no business rules — duplicate-registration decisions, account
    activation timing, and password verification orchestration belong to
    AuthenticationService (accounts/authentication_service.py).
    """

    def email_exists(self,email:str) ->bool:
        """Case-insensitive check, per AUTHENTICATION_DESIGN.md Section 9."""
        return User.objects.filter(email__iexact=email).exists()

    def mobile_number_exists(self,mobile_number:str)->bool:
        return User.objects.filter(mobile_number=mobile_number).exists()
    
    def create_user(
        self, *, 
        email: str, 
        password: str, 
        first_name: str, 
        last_name: str, 
        mobile_number: str
        ) -> User:
        
        """Create a new user via the model manager (inactive/unverified by its defaults)."""

        return User.objects.create_user(
            email=email,
            password=password,
            mobile_number=mobile_number,
            first_name=first_name,
            last_name=last_name,
        )
    
    def get_by_email(self,email:str)-> User | None:
        """Case-insensitive lookup, matching the uniqueness check above."""
        return User.objects.filter(email__iexact=email).first()
    
    def activate_and_verify(self,user:user)->User:
        """Mark a user active and email-verified, together, and persist the change."""
        user.is_active = True
        user.is_email_verified = True
        user.save(update_fields=['is_active', 'is_email_verified', 'updated_at'])
        return user



class OTPRepository:
    """
    Persistence-only operations for the OTP model.

    Contains no business rules — expiry checks, hashing, and generation
    belong to OTPService (accounts/services.py). This class only reads
    from and writes to the database.
    """

    def get_latest_active_otp(self, user, purpose: str) -> OTP | None:
        """Return the most recently created, unused OTP for a user/purpose, or None."""
        return (
            OTP.objects.filter(user=user, purpose=purpose, is_used=False)
            .order_by('-created_at')
            .first()
        )

    def create_otp(self, user, otp_hash: str, purpose: str, expires_at) -> OTP:
        """Create and persist a new OTP row."""
        return OTP.objects.create(
            user=user,
            otp_hash=otp_hash,
            purpose=purpose,
            expires_at=expires_at,
        )

    def invalidate_previous_otps(self, user, purpose: str) -> int:
        """
        Mark all currently unused OTPs for this user/purpose as used, so
        only a newly issued OTP remains valid. Returns the number of rows
        updated.
        """
        return OTP.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)

    def mark_as_used(self, otp: OTP) -> OTP:
        """Mark a specific OTP instance as used and persist the change."""
        otp.is_used = True
        otp.save(update_fields=['is_used', 'updated_at'])
        return otp
