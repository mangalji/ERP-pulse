import apiClient, { unwrap } from './apiClient.js'
import { SUPERADMIN_ENDPOINTS } from '../utils/constants.js'

/**
 * AGSuite Super Admin API service.
 * Single source of truth for all superadmin backend calls.
 * Reuses the shared apiClient + unwrap pattern.
 */
export const superadminApi = {
  // ── Dashboard ────────────────────────────────────────────────
  getDashboardSummary: () => apiClient.get(SUPERADMIN_ENDPOINTS.dashboardSummary).then(unwrap),

  // ── Companies ────────────────────────────────────────────────
  listCompanies: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.companies, { params }).then(unwrap),
  getCompany: (id) => apiClient.get(`${SUPERADMIN_ENDPOINTS.companies}${id}/`).then(unwrap),
  createCompany: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companies, payload).then(unwrap),
  updateCompany: (id, payload) => apiClient.patch(`${SUPERADMIN_ENDPOINTS.companies}${id}/`, payload).then(unwrap),
  deleteCompany: (id) => apiClient.delete(`${SUPERADMIN_ENDPOINTS.companies}${id}/`).then(unwrap),
  getCompanyStats: () => apiClient.get(SUPERADMIN_ENDPOINTS.companyStats).then(unwrap),
  suspendCompany: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.companySuspend(id)).then(unwrap),
  activateCompany: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.companyActivate(id)).then(unwrap),
  softDeleteCompany: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.companySoftDelete(id)).then(unwrap),
  restoreCompany: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.companyRestore(id)).then(unwrap),

  // ── Plans ────────────────────────────────────────────────────
  listPlans: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.plans, { params }).then(unwrap),
  getPlan: (id) => apiClient.get(`${SUPERADMIN_ENDPOINTS.plans}${id}/`).then(unwrap),
  createPlan: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.plans, payload).then(unwrap),
  updatePlan: (id, payload) => apiClient.patch(`${SUPERADMIN_ENDPOINTS.plans}${id}/`, payload).then(unwrap),
  deletePlan: (id) => apiClient.delete(`${SUPERADMIN_ENDPOINTS.plans}${id}/`).then(unwrap),

  // ── Company Plans (subscriptions) ────────────────────────────
  listCompanyPlans: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.companyPlans, { params }).then(unwrap),
  assignPlan: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companyPlanAssign, payload).then(unwrap),
  upgradePlan: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companyPlanUpgrade, payload).then(unwrap),
  downgradePlan: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companyPlanDowngrade, payload).then(unwrap),
  cancelPlan: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companyPlanCancel, payload).then(unwrap),
  renewPlan: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companyPlanRenew, payload).then(unwrap),
  getCompanyPlanHistory: (companyId) => apiClient.get(SUPERADMIN_ENDPOINTS.companyPlanHistory(companyId)).then(unwrap),

  // ── Modules ──────────────────────────────────────────────────
  listModules: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.modules, { params }).then(unwrap),
  fetchCompanyModules: (companyId) =>
    apiClient.get(SUPERADMIN_ENDPOINTS.companyModulesFetch, { params: { company_id: companyId } }).then(unwrap),
  setCompanyModule: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companyModulesSet, payload).then(unwrap),
  bulkSetCompanyModules: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companyModulesBulk, payload).then(unwrap),

  // ── Employees ────────────────────────────────────────────────
  listEmployees: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.employees, { params }).then(unwrap),
  getEmployee: (id) => apiClient.get(`${SUPERADMIN_ENDPOINTS.employees}${id}/`).then(unwrap),
  createEmployee: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeCreate, payload).then(unwrap),
  updateEmployee: (id, payload) => apiClient.patch(`${SUPERADMIN_ENDPOINTS.employees}${id}/`, payload).then(unwrap),
  deactivateEmployee: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeDeactivate(id)).then(unwrap),
  activateEmployee: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeActivate(id)).then(unwrap),
  assignEmployeeRole: (id, roleId) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeAssignRole(id), { role_id: roleId }).then(unwrap),
  removeEmployeeRole: (id, roleId) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeRemoveRole(id), { role_id: roleId }).then(unwrap),

  // ── Support Sessions ─────────────────────────────────────────
  listSupportSessions: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.supportSessions, { params }).then(unwrap),
  getSupportSession: (id) => apiClient.get(`${SUPERADMIN_ENDPOINTS.supportSessions}${id}/`).then(unwrap),
  startSupportSession: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.supportSessionsStart, payload).then(unwrap),
  endSupportSession: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.supportSessionsEnd(id)).then(unwrap),

  // ── Notifications ────────────────────────────────────────────
  fetchNotifications: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.notificationsFetch, { params }).then(unwrap),
  getUnreadNotificationCount: () => apiClient.get(SUPERADMIN_ENDPOINTS.notificationsUnreadCount).then(unwrap),
  markNotificationRead: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.notificationMarkRead(id)).then(unwrap),
  markAllNotificationsRead: () => apiClient.post(SUPERADMIN_ENDPOINTS.notificationMarkAllRead).then(unwrap),
}
