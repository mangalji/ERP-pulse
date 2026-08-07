import apiClient, { unwrap } from './apiClient.js'
import { CLIENT_ENDPOINTS } from '../utils/constants.js'
import { invoiceApi } from './invoice.js'
import { aiApi } from './ai.js'
import { reportsApi } from './reports.js'
import { dashboardApi } from './dashboard.js'

/**
 * Client Company Portal API service.
 *
 * Reuses existing feature services (invoice, ai, reports, dashboard)
 * for company-scoped data, and talks to the dedicated company-scoped
 * `/client/*` backend endpoints for employees, roles, settings and
 * notifications. The backend derives the company from the authenticated
 * user — the client never sends a company_id.
 */
export const clientApi = {
  // ── Client context ─────────────────────────────────────────
  getMe: () => apiClient.get(CLIENT_ENDPOINTS.me).then(unwrap),

  // ── Dashboard (reused) ──────────────────────────────────────
  getDashboardSummary: () => dashboardApi.getSummary(),
  getExecutiveSummary: () => dashboardApi.getExecutiveSummary(),
  getExecutiveCharts: () => dashboardApi.getExecutiveCharts(),
  getActivityFeed: (limit) => dashboardApi.getActivityFeed(limit),
  getRecentInvoices: () => dashboardApi.getRecentInvoices(),
  getRecentSalesOrders: () => dashboardApi.getRecentSalesOrders(),

  // ── Invoice (reused) ────────────────────────────────────────
  uploadInvoices: (files) => invoiceApi.upload(files),
  listInvoiceBatches: (params) => invoiceApi.listBatches(params),
  getInvoiceBatch: (id) => invoiceApi.getBatch(id),
  getInvoiceFile: (id) => invoiceApi.getFile(id),
  deleteInvoiceFile: (id) => invoiceApi.deleteFile(id),
  retryInvoiceFile: (id) => invoiceApi.retryFile(id),
  patchInvoiceExtraction: (id, data) => invoiceApi.patchExtraction(id, data),
  reviewInvoiceFile: (fileId, payload) =>
    apiClient.post(`/api/v1/invoice/review/${fileId}/`, payload).then(unwrap),
  previewInvoicePayload: (fileId) =>
    apiClient.post(`/api/v1/invoice/preview-payload/${fileId}/`).then(unwrap),

  // ── AI Assistant (reused) ───────────────────────────────────
  chat: (message, conversationId) => aiApi.chat(message, conversationId),
  getAiHistory: () => aiApi.getHistory(),
  getAiMessages: (conversationId) => aiApi.getMessages(conversationId),

  // ── Reports (reused) ────────────────────────────────────────
  getSalesTrend: (months) => reportsApi.getSalesTrend(months),

  // ── Employees (company-scoped /client/*) ────────────────────
  listEmployees: (params) =>
    apiClient.get(CLIENT_ENDPOINTS.employees, { params }).then(unwrap),
  getEmployee: (id) => apiClient.get(CLIENT_ENDPOINTS.employee(id)).then(unwrap),
  createEmployee: (payload) =>
    apiClient.post(CLIENT_ENDPOINTS.employees, payload).then(unwrap),
  updateEmployee: (id, payload) =>
    apiClient.patch(CLIENT_ENDPOINTS.employee(id), payload).then(unwrap),
  deactivateEmployee: (id) =>
    apiClient.post(CLIENT_ENDPOINTS.employeeDeactivate(id)).then(unwrap),
  activateEmployee: (id) =>
    apiClient.post(CLIENT_ENDPOINTS.employeeActivate(id)).then(unwrap),
  assignEmployeeRole: (id, roleId) =>
    apiClient.post(CLIENT_ENDPOINTS.employeeAssignRole(id), { role_id: roleId }).then(unwrap),
  removeEmployeeRole: (id, roleId) =>
    apiClient.post(CLIENT_ENDPOINTS.employeeRemoveRole(id), { role_id: roleId }).then(unwrap),
  resendEmployeeInvitation: (id) =>
    apiClient.post(CLIENT_ENDPOINTS.employeeResendInvitation(id)).then(unwrap),

  // ── Roles (company-scoped) ──────────────────────────────────
  listRoles: () => apiClient.get(CLIENT_ENDPOINTS.roles).then(unwrap),

  // ── Company settings (company-scoped) ───────────────────────
  getCompanySettings: () => apiClient.get(CLIENT_ENDPOINTS.settings).then(unwrap),
  updateCompanySettings: (payload) =>
    apiClient.patch(CLIENT_ENDPOINTS.settings, payload).then(unwrap),

  // ── Notifications (user-scoped /client/*) ──────────────────
  fetchNotifications: (params) =>
    apiClient.get(CLIENT_ENDPOINTS.notifications, { params }).then(unwrap),
  getUnreadNotificationCount: () =>
    apiClient.get(CLIENT_ENDPOINTS.notificationsUnreadCount).then(unwrap),
  markNotificationRead: (id) =>
    apiClient.post(CLIENT_ENDPOINTS.notificationMarkRead(id)).then(unwrap),
  markAllNotificationsRead: () =>
    apiClient.post(CLIENT_ENDPOINTS.notificationMarkAllRead).then(unwrap),
}
