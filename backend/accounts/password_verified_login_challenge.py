from django.core import signing
from django.utils.crypto import constant_time_compare, salted_hmac
from accounts.models import OTP
from accounts.exceptions import InvalidCredentialsException

SALT = 'agsuite.password-verified-login.v1'
MAX_AGE = 600

def issue(user):
    otp = OTP.objects.filter(user=user, purpose=OTP.Purpose.LOGIN, is_used=False).latest('created_at')
    return signing.dumps({
        'user': str(user.pk), 'otp': str(otp.pk),
        'password': salted_hmac(SALT, user.password).hexdigest(),
    }, salt=SALT)

def validate(user, challenge):
    try:
        payload = signing.loads(challenge, salt=SALT, max_age=MAX_AGE)
        valid = (
            user.is_active and user.is_email_verified
            and payload['user'] == str(user.pk)
            and constant_time_compare(payload['password'], salted_hmac(SALT, user.password).hexdigest())
            and OTP.objects.filter(pk=payload['otp'], user=user, purpose=OTP.Purpose.LOGIN, is_used=False).exists()
        )
        if valid:
            return payload['otp']
    except (signing.BadSignature, KeyError, TypeError, ValueError):
        pass
    raise InvalidCredentialsException('Login challenge expired or invalid. Sign in again.')
