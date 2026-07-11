from django.urls import path
from accounts.views import (
    RegisterView, 
    VerifyRegistrationOTPView,
    LoginView,
    LogoutView,
    MeView,
    TokenRefreshView,
    VerifyLoginOTPView
)
urlpatterns = [
    path('register/',RegisterView.as_view(),name='register'),
    path('register/verify-otp/',VerifyRegistrationOTPView.as_view(),name='verify-register-otp'),
    path('login/',LoginView.as_view(),name='login'),
    path('login/verify-otp/',VerifyLoginOTPView.as_view(),name='verify-login-otp'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', MeView.as_view(), name='me'),
]