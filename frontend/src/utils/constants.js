export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

/**
 * JWT tokens are stored as httpOnly cookies set by the backend
 * (access_token, refresh_token). JavaScript cannot read httpOnly
 * cookies, so there are NO localStorage getter/setter functions here.
 *
 * This eliminates the XSS risk of token theft via localStorage.
 * The browser automatically attaches the cookies on every API request
 * when `withCredentials: true` is set on the HTTP client.
 */

export const AUTH_ENDPOINTS = {
  register: '/auth/register/',
  resendRegisterOtp: '/auth/register/resend-otp/',
  verifyRegisterOtp: '/auth/register/verify-otp/',
  completeProfile: '/auth/register/complete-profile/',
  login: '/auth/login/',
  verifyLoginOtp: '/auth/login/verify-otp/',
  resendLoginOtp: '/auth/login/resend-otp/',
  refresh: '/auth/token/refresh/',
  logout: '/auth/logout/',
  me: '/auth/me/',
  loginHistory: '/auth/login-history/',
  forgotPassword: '/auth/forgot-password/',
  resetPassword: '/auth/forgot-password/reset/',
  profileSendOtp: '/auth/profile/send-otp/',
  profileUpdate: '/auth/profile/update/',
}

export const DASHBOARD_ENDPOINTS = {
  summary: '/dashboard/summary/',
  recentCustomers: '/dashboard/recent-customers/',
  recentSalesOrders: '/dashboard/recent-sales-orders/',
  recentInvoices: '/dashboard/recent-invoices/',
}

export const REPORTS_ENDPOINTS = {
  salesTrend: '/reports/sales-trend/',
}

export const NETSUITE_ENDPOINTS = {
  connections: '/netsuite/connections/',
  callback: '/netsuite/callback/',
  customers: '/netsuite/customers/',
  employees: '/netsuite/employees/',
  vendors: '/netsuite/vendors/',
  items: '/netsuite/items/',
  salesOrders: '/netsuite/sales-orders/',
  purchaseOrders: '/netsuite/purchase-orders/',
  invoices: '/netsuite/invoices/',
}

export const MONITORING_ENDPOINTS = {
  health: '/monitoring/health/',
  errors: '/monitoring/errors/',
  apiUsage: '/monitoring/api-usage/',
}

export const AI_ENDPOINTS = {
  chat: '/ai/chat/',
  history: '/ai/history/',
  messages: (conversationId) => `/ai/history/${conversationId}/messages/`,
}
