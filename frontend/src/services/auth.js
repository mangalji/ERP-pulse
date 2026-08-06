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

  forgotPassword: (email) =>
    apiClient.post(AUTH_ENDPOINTS.forgotPassword, { email }).then(unwrap),

  resetPassword: (email, otpCode, password, confirmPassword) =>
    apiClient.post(AUTH_ENDPOINTS.resetPassword, { email, otp_code: otpCode, password, confirm_password: confirmPassword }).then(unwrap),

  profileSendOtp: () =>
    apiClient.post(AUTH_ENDPOINTS.profileSendOtp).then(unwrap),

  profileUpdate: (otpCode, { firstName, lastName, mobileNumber, profilePic } = {}) => {
    const hasFile = profilePic instanceof File
    const body = hasFile ? new FormData() : { otp_code: otpCode }
    if (hasFile) {
      body.append('otp_code', otpCode)
    } else {
      body.otp_code = otpCode
    }
    if (firstName !== undefined) {
      hasFile ? body.append('first_name', firstName) : body.first_name = firstName
    }
    if (lastName !== undefined) {
      hasFile ? body.append('last_name', lastName) : body.last_name = lastName
    }
    if (mobileNumber !== undefined) {
      hasFile ? body.append('mobile_number', mobileNumber) : body.mobile_number = mobileNumber
    }
    if (profilePic !== undefined && profilePic !== null) {
      body.append('profile_pic', profilePic)
    }
    return apiClient.post(AUTH_ENDPOINTS.profileUpdate, body).then(unwrap)
  },

  me: () => apiClient.get(AUTH_ENDPOINTS.me).then(unwrap),

  getLoginHistory: () => apiClient.get(AUTH_ENDPOINTS.loginHistory).then(unwrap),

  logout: () =>
    apiClient.post(AUTH_ENDPOINTS.logout).then(unwrap),

  refreshToken: (refresh) =>
    apiClient.post(AUTH_ENDPOINTS.refresh, refresh ? { refresh } : {}).then(unwrap),
}
