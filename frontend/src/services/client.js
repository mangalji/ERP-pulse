import apiClient, { unwrap } from './apiClient.js'
import { CLIENT_ENDPOINTS } from '../utils/constants.js'
import { dashboardApi } from './dashboard.js'

/**
 * Client Company Portal API service.
 *
 * Reuses existing feature services (invoice, ai, reports, dashboard)
 * for company-scoped data, and talks to the dedicated company-scoped
 * `/client/*` backend endpoints for employees, roles, settings and
 * user — the client never sends a company_id.
 */
export const clientApi = {
  // ── Client context ─────────────────────────────────────────
  getMe: () => apiClient.get(CLIENT_ENDPOINTS.me).then(unwrap),

  // ── Dashboard (reused) ──────────────────────────────────────
  getDashboardSummary: () => dashboardApi.getSummary(),
  getExecutiveSummary: () => dashboardApi.getExecutiveSummary(),
  // getExecutiveCharts: () => dashboardApi.getExecutiveCharts(),
  getActivityFeed: (limit) => dashboardApi.getActivityFeed(limit),
  getRecentInvoices: () => dashboardApi.getRecentInvoices(),

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

  // ── Transaction navigation (DB-driven) ─────────────────────
  getNavigationMenu: () =>
    apiClient.get('/navigation/menu/').then(unwrap),
  
  getNavigationCustomizeData: (params = {}) =>
    apiClient.get('/navigation/customize/', { params }).then(unwrap),
  
  updateNavigationAccess: (payload) =>
    apiClient.post('/navigation/customize/access/', payload).then(unwrap),
  
  createNavigationTab: (payload) =>
    apiClient.post('/navigation/customize/tab/', payload).then(unwrap),
  
  updateNavigationTab: (tabLevel, tabId, payload) =>
    apiClient.patch(`/navigation/customize/tab/${tabLevel}/${tabId}/`, payload).then(unwrap),

  getCenterTabs: (page = 1) =>
    apiClient.get('/navigation/center-tabs/', {
      params: { page },
    }).then(unwrap),

  getCenterTabChildren: (tabId) =>
    apiClient.get(`/navigation/center-tabs/${tabId}/children/`).then(unwrap),

  getCenterCategories: (page = 1) =>
  apiClient
    .get('/navigation/center-categories/', {
      params: { page },
    })
    .then(unwrap),

  createCenterCategory: (payload) =>
    apiClient
      .post('/navigation/center-categories/', payload)
      .then(unwrap),

  getCenterCategoryChildren: (categoryId) =>
    apiClient
      .get(`/navigation/center-categories/${categoryId}/children/`)
      .then(unwrap),

  createCenterCategoryChild: (categoryId, payload) =>
    apiClient
      .post(
        `/navigation/center-categories/${categoryId}/children/`,
        payload,
      )
      .then(unwrap),

  deleteCenterCategoryChildren: (categoryId, ids) =>
    apiClient
      .post(`/navigation/center-categories/${categoryId}/children/bulk-delete/`, { ids })
      .then(unwrap),

  createCenterTab: (payload) =>
    apiClient.post('/navigation/center-tabs/', payload).then(unwrap),

  deleteCenterTabs: (ids) =>
    apiClient
      .post('/navigation/center-tabs/bulk-delete/', { ids })
      .then(unwrap),

  deleteCenterCategories: (ids) =>
    apiClient
      .post('/navigation/center-categories/bulk-delete/', { ids })
      .then(unwrap),

  deleteNavigationTab: (tabLevel, tabId) =>
    apiClient.delete(`/navigation/customize/tab/${tabLevel}/${tabId}/`).then(unwrap),
  
  getNetsuiteTransactions: (params) =>
    apiClient.get('/api/v1/netsuite/transactions/', { params }).then(unwrap),
  
  getTransactions: (params) =>
    apiClient.get('/transactions/', { params }).then(unwrap),

  createTransaction: ({ transactionType, recordType, payload }) =>
    apiClient.post('/transactions/', payload, {
      params: {
        transaction_type: transactionType,
        record_type: recordType,
      },
    }).then(unwrap),

  getProducts:(params) =>
    apiClient.get('/products/', {params}).then(unwrap),

  createProduct: ({ transactionType, recordType, payload}) =>
    apiClient.post('/product/',payload,{
      params:{
        transaction_type: transactionType,
        record_type: recordType,
      },
    }).then(unwrap),
}
