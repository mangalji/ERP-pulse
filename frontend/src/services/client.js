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

// The navigation menu is per-user and only changes when navigation is edited,

// but every page mounts its own <ClientLayout>, so it used to be refetched

// (and re-computed on the server) on every single navigation.

const MENU_TTL_MS = 2 * 60 * 1000
let menuCache = null // { key, at, promise}

const invalidateMenu = (result) => {
  menuCache = null
  return result
}

export const clientApi = {
  // ── Client context ─────────────────────────────────────────
  getMe: () => apiClient.get(CLIENT_ENDPOINTS.me).then(unwrap),

  // ── Dashboard (reused) ──────────────────────────────────────
  getExecutiveSummary: () => dashboardApi.getExecutiveSummary(),
  getActivityFeed: (limit) => dashboardApi.getActivityFeed(limit),

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
  resendEmployeeInvitation: (id) =>
    apiClient.post(CLIENT_ENDPOINTS.employeeResendInvitation(id)).then(unwrap),

  // ── Roles (company-scoped) ──────────────────────────────────
  listRoles: () => apiClient.get(CLIENT_ENDPOINTS.roles).then(unwrap),

  // ── Company settings (company-scoped) ───────────────────────
  getCompanySettings: () => apiClient.get(CLIENT_ENDPOINTS.settings).then(unwrap),
  updateCompanySettings: (payload) =>
    apiClient.patch(CLIENT_ENDPOINTS.settings, payload).then(unwrap),

  getNavigationMenu: (cacheKey = null) => {
    const now = Date.now()
    if(
      cacheKey && menuCache && menuCache.key === cacheKey && now - menuCache.at < MENU_TTL_MS
    ) {
      return menuCache.promise
    }
    const promise = apiClient.get('/navigation/menu/').then(unwrap)
    if (cacheKey) {
      const entry = { key: cacheKey, at: now, promise }
      menuCache = entry
      // Never keep a failed request cached.
      promise.catch(() => {
        if (menuCache === entry) menuCache = null
      })
    }

    return promise
  },
  
  createNavigationTab: (payload) =>
    apiClient.post('/navigation/customize/tab/', payload).then(unwrap).then(invalidateMenu),
  
  updateNavigationTab: (tabLevel, tabId, payload) =>
    apiClient.patch(`/navigation/customize/tab/${tabLevel}/${tabId}/`, payload).then(unwrap).then(invalidateMenu),

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
      .then(unwrap).then(invalidateMenu),

  getCenterCategoryChildren: (categoryId) =>
    apiClient
      .get(`/navigation/center-categories/${categoryId}/children/`)
      .then(unwrap),

  deleteCenterTabs: (ids) =>
    apiClient
      .post('/navigation/center-tabs/bulk-delete/', { ids })
      .then(unwrap).then(invalidateMenu),

  deleteCenterCategories: (ids) =>
    apiClient
      .post('/navigation/center-categories/bulk-delete/', { ids })
      .then(unwrap).then(invalidateMenu),

  deleteNavigationTab: (tabLevel, tabId) =>
    apiClient.delete(`/navigation/customize/tab/${tabLevel}/${tabId}/`).then(unwrap).then(invalidateMenu),
    
  getTransactions: (params) =>
    apiClient.get('/transactions/', { params }).then(unwrap),

  createTransaction: ({ transactionType, recordType, payload }) =>
    apiClient.post('/transactions/', payload, {
      params: {
        transaction_type: transactionType,
        record_type: recordType,
      },
    }).then(unwrap),

}
