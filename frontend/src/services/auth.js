import apiClient, { unwrap } from './apiClient.js'
import { AUTH_ENDPOINTS } from '../utils/constants.js'

export const authApi = {
  requestLoginOtp: (email, password) =>
  apiClient.post(AUTH_ENDPOINTS.login, {
    email,
    password,
  }).then(unwrap),

  verifyLoginOtp: (email, otpCode) =>
    apiClient.post(AUTH_ENDPOINTS.verifyLoginOtp, { email, otp_code: otpCode }).then(unwrap),

  resendLoginOtp: (email) =>
    apiClient.post(AUTH_ENDPOINTS.resendLoginOtp, { email }).then(unwrap),

  requestRegisterOtp: (email, password, confirmPassword) =>
    apiClient.post(AUTH_ENDPOINTS.register, { email, password, confirm_password: confirmPassword }).then(unwrap),

  verifyRegisterOtp: (email, otpCode) =>
    apiClient.post(AUTH_ENDPOINTS.verifyRegisterOtp, { email, otp_code: otpCode }).then(unwrap),

  completeProfile: (registrationToken, firstName, lastName, mobileNumber) =>
    apiClient.post(AUTH_ENDPOINTS.completeProfile, { registration_token: registrationToken, first_name: firstName, last_name: lastName, mobile_number: mobileNumber }).then(unwrap),

  resendRegisterOtp: (email) =>
    apiClient.post(AUTH_ENDPOINTS.resendRegisterOtp, { email }).then(unwrap),

  me: () => apiClient.get(AUTH_ENDPOINTS.me).then(unwrap),

  logout: (refresh) =>
    apiClient.post(AUTH_ENDPOINTS.logout, { refresh }).then(unwrap),
}
