from django.urls import path
from accounts.views import (
    LoginView,
    LogoutView,
    MeView,
    TokenRefreshView,
    VerifyLoginOTPView,
    ResendLoginOTPView,
    LoginHistoryView,
    ForgotPasswordView,
    ResetPasswordView,
    ProfileUpdateSendOTPView,
    ProfileUpdateView,
    health
)

# --------------------------------------------------------------------
# LEGACY — Public Registration (Sprint 8.4)
#
# Sprint 8.4 retires public self-registration: every user now enters the
# system exclusively through the Invitation Activation flow (see
# invitations.views.InvitationViewSet). RegisterView, VerifyRegistrationOTP
# View, ResendRegistrationOTPView, and CompleteProfileView are kept in
# accounts/views.py and accounts/authentication_service.py untouched —
# per DEVELOPMENT_GUIDELINES.md ("do not delete files/classes/functions/
# endpoints"), obsolete code is marked LEGACY rather than removed — but
# are deliberately NOT wired into urlpatterns below, so they are no
# longer publicly reachable. Do not re-add these paths without a
# product decision to bring registration back.
# --------------------------------------------------------------------

urlpatterns = [
    path('login/',LoginView.as_view(),name='login'),
    path('login/verify-otp/',VerifyLoginOTPView.as_view(),name='verify-login-otp'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path("login/resend-otp/",ResendLoginOTPView.as_view(),name="resend-login-otp"),
    path("login-history/", LoginHistoryView.as_view(), name="login-history"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path("forgot-password/reset/", ResetPasswordView.as_view(), name="reset-password"),
    path("profile/send-otp/", ProfileUpdateSendOTPView.as_view(), name="profile-send-otp"),
    path("profile/update/", ProfileUpdateView.as_view(), name="profile-update"),
    path("health/",health,name="health"),
]
