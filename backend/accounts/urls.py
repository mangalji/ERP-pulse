from django.urls import path
from accounts.views import (
    RegisterView, 
    VerifyRegistrationOTPView,
    LoginView,
    LogoutView,
    MeView,
    TokenRefreshView,
    VerifyLoginOTPView,
    ResendRegistrationOTPView,
    CompleteProfileView,
    ResendLoginOTPView,
    health
)
urlpatterns = [
    path('register/',RegisterView.as_view(),name='register'),
    path('register/verify-otp/',VerifyRegistrationOTPView.as_view(),name='verify-register-otp'),
    path('login/',LoginView.as_view(),name='login'),
    path('login/verify-otp/',VerifyLoginOTPView.as_view(),name='verify-login-otp'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
    path("register/resend-otp/", ResendRegistrationOTPView.as_view(), name="resend-registration-otp"),
    path("register/complete-profile/", CompleteProfileView.as_view(), name="complete-profile"),
    path("login/resend-otp/",ResendLoginOTPView.as_view(),name="resend-login-otp"),
    path("health/",health,name="health"),
]