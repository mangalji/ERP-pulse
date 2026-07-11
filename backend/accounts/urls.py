from django.urls import path
from accounts.views import RegisterView, VerifyRegistrationOTPView

urlpatterns = [
    path('register/',RegisterView.as_view(),name='register'),
    path('register/verify-otp/',VerifyRegistrationOTPView.as_view(),name='verify-register-otp'),
]