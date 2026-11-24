import apiClient, { unwrap } from './apiClient.js'
import { AUTH_ENDPOINTS } from '../utils/constants.js'

const LOGIN_CHALLENGE_KEY = 'agsuite_login_challenge'
const rememberChallenge = (data) => {
  sessionStorage.setItem(LOGIN_CHALLENGE_KEY, data.challenge)
  return data
}
const challenge = () => sessionStorage.getItem(LOGIN_CHALLENGE_KEY) || ''

export const authApi = {
  requestLoginOtp: (email, password) =>
  apiClient.post(AUTH_ENDPOINTS.login, {
    email,
    password,
  }).then(unwrap).then(rememberChallenge),

  verifyLoginOtp: (email, otpCode) =>
    apiClient.post(AUTH_ENDPOINTS.verifyLoginOtp, { email, otp_code: otpCode, challenge: challenge() }).then(unwrap).then((data) => {
      sessionStorage.removeItem(LOGIN_CHALLENGE_KEY)
      return data
    }),

  resendLoginOtp: (email) =>
    apiClient.post(AUTH_ENDPOINTS.resendLoginOtp, { email, challenge: challenge() }).then(unwrap).then(rememberChallenge),

  forgotPassword: (email) =>
    apiClient.post(AUTH_ENDPOINTS.forgotPassword, { email }).then(unwrap),

  resetPassword: (email, otpCode, password, confirmPassword) =>
    apiClient.post(AUTH_ENDPOINTS.resetPassword, { email, otp_code: otpCode, password, confirm_password: confirmPassword }).then(unwrap),

  profileSendOtp: () =>
  apiClient.post(AUTH_ENDPOINTS.profileSendOtp).then(unwrap),

profileUpdate: ({ firstName, lastName, mobileNumber } = {}) => {
  const body = {}

  if (firstName !== undefined) {
    body.first_name = firstName
  }

  if (lastName !== undefined) {
    body.last_name = lastName
  }

  if (mobileNumber !== undefined) {
    body.mobile_number = mobileNumber
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
