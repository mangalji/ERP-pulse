export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export const TOKEN_KEYS = {
  access: 'erp_pulse_access_token',
  refresh: 'erp_pulse_refresh_token',
}

export const getAccessToken = () => localStorage.getItem(TOKEN_KEYS.access)
export const getRefreshToken = () => localStorage.getItem(TOKEN_KEYS.refresh)
export const setTokens = (access, refresh) => {
  localStorage.setItem(TOKEN_KEYS.access, access)
  if (refresh) localStorage.setItem(TOKEN_KEYS.refresh, refresh)
}
export const clearTokens = () => {
  localStorage.removeItem(TOKEN_KEYS.access)
  localStorage.removeItem(TOKEN_KEYS.refresh)
}

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
}

export const DASHBOARD_ENDPOINTS = {
  summary: '/dashboard/summary/',
  recentCustomers: '/dashboard/recent-customers/',
  recentSalesOrders: '/dashboard/recent-sales-orders/',
  recentInvoices: '/dashboard/recent-invoices/',
}

export const NETSUITE_ENDPOINTS = {
  // connect: '/netsuite/connect/',
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

export const AI_ENDPOINTS = {
  chat: '/ai/chat/',
  history: '/ai/history/',
  messages: (conversationId) => `/ai/history/${conversationId}/messages/`,
}
