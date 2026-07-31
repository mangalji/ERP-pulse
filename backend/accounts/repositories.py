from accounts.models import OTP, User, LoginActivity


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

    def create_verified_user(
        self, *,
        email: str,
        password_hash: str,
        first_name: str,
        last_name: str,
        mobile_number: str,
    ) -> User:
        """
        Create a User whose email has already been OTP-verified before
        this call — used only by the Complete Profile step of
        registration. `password_hash` was produced by common.utils.hash
        at Register time and stored in the registration cache; it is
        assigned directly here rather than passed through
        set_password()/create_user(), which would hash it a second time
        and make the account impossible to log into.
        """
        user = User(
            email=User.objects.normalize_email(email),
            first_name=first_name,
            last_name=last_name,
            mobile_number=mobile_number or None,
            is_active=True,
            is_email_verified=True,
        )
        user.password = password_hash
        user.save()
        return user
    
    def get_by_email(self,email:str)-> User | None:
        """Case-insensitive lookup, matching the uniqueness check above."""
        return User.objects.filter(email__iexact=email).first()



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

    def increment_attempt_count(self,otp:OTP) -> OTP:
        """Increment the wrong-guess counter on a specific OTP instance and persist it."""
        otp.attempt_count += 1
        otp.save(update_fields=['attempt_count','updated_at'])
        return otp
    
class LoginActivityRepository:
    """
    Persistence-only operations for LoginActivity.
 
    Contains no business rules — deciding *when* a login counts as
    "completed" belongs to AuthenticationService. This class only reads
    from and writes to the database.
    """
    def create(self,*,user:User,ip_address:str|None,user_agent:str|None)->LoginActivity:
        return LoginActivity.objects.create(
            user=user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    def get_queryset_by_user(self,user:User,*,limit:int=50):
        """FIX: Return un-evaluated QuerySet so the View layer can handle
        proper ORM slicing and count queries without evaluation side-effects."""
        return LoginActivity.objects.filter(user=user)