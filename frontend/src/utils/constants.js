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

export const CLIENT_ENDPOINTS = {
  me: '/client/me/',
  employees: '/client/employees/',
  employee: (id) => `/client/employees/${id}/`,
  employeeActivate: (id) => `/client/employees/${id}/activate/`,
  employeeDeactivate: (id) => `/client/employees/${id}/deactivate/`,
  employeeAssignRole: (id) => `/client/employees/${id}/assign_role/`,
  employeeRemoveRole: (id) => `/client/employees/${id}/remove_role/`,
  roles: '/client/roles/',
  settings: '/client/settings/',
  notifications: '/client/notifications/',
  notificationsUnreadCount: '/client/notifications/unread_count/',
  notificationMarkRead: (id) => `/client/notifications/${id}/mark_read/`,
  notificationMarkAllRead: '/client/notifications/mark_all_read/',
}

export const SUPERADMIN_ENDPOINTS = {
  companies: '/superadmin/companies/',
  companyStats: '/superadmin/companies/stats/',
  companySuspend: (id) => `/superadmin/companies/${id}/suspend/`,
  companyActivate: (id) => `/superadmin/companies/${id}/activate/`,
  companySoftDelete: (id) => `/superadmin/companies/${id}/soft_delete/`,
  companyRestore: (id) => `/superadmin/companies/${id}/restore/`,
  plans: '/superadmin/plans/',
  companyPlans: '/superadmin/company-plans/',
  companyPlanAssign: '/superadmin/company-plans/assign/',
  companyPlanUpgrade: '/superadmin/company-plans/upgrade/',
  companyPlanDowngrade: '/superadmin/company-plans/downgrade/',
  companyPlanCancel: '/superadmin/company-plans/cancel/',
  companyPlanRenew: '/superadmin/company-plans/renew/',
  companyPlanHistory: (id) => `/superadmin/company-plans/${id}/history/`,
  modules: '/superadmin/modules/',
  companyModules: '/superadmin/company-modules/',
  companyModulesFetch: '/superadmin/company-modules/fetch/',
  companyModulesSet: '/superadmin/company-modules/set_module/',
  companyModulesBulk: '/superadmin/company-modules/bulk_update/',
  employees: '/superadmin/employees/',
  employeeCreate: '/superadmin/employees/create_employee/',
  employeeDeactivate: (id) => `/superadmin/employees/${id}/deactivate/`,
  employeeActivate: (id) => `/superadmin/employees/${id}/activate/`,
  employeeAssignRole: (id) => `/superadmin/employees/${id}/assign_role/`,
  employeeRemoveRole: (id) => `/superadmin/employees/${id}/remove_role/`,
  supportSessions: '/superadmin/support-sessions/',
  supportSessionsStart: '/superadmin/support-sessions/start/',
  supportSessionsEnd: (id) => `/superadmin/support-sessions/${id}/end/`,
  dashboardSummary: '/superadmin/dashboard/summary/',
  notifications: '/superadmin/notifications/',
  notificationsFetch: '/superadmin/notifications/fetch/',
  notificationsUnreadCount: '/superadmin/notifications/unread_count/',
  notificationMarkRead: (id) => `/superadmin/notifications/${id}/mark_read/`,
  notificationMarkAllRead: '/superadmin/notifications/mark_all_read/',
}
