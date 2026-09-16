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
  permanentlyDeletedCompanies: (params) => apiClient.get(`${SUPERADMIN_ENDPOINTS.companies}permanently-deleted/`,{params}).then(unwrap),

  // ── Plans ────────────────────────────────────────────────────
  listPlans: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.plans, { params }).then(unwrap),
  getPlan: (id) => apiClient.get(`${SUPERADMIN_ENDPOINTS.plans}${id}/`).then(unwrap),
  createPlan: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.plans, payload).then(unwrap),
  updatePlan: (id, payload) => apiClient.patch(`${SUPERADMIN_ENDPOINTS.plans}${id}/`, payload).then(unwrap),
  deletePlan: (id) => apiClient.post(`${SUPERADMIN_ENDPOINTS.plans}${id}/delete_plan/`).then(unwrap),
  activatePlan: (id) => apiClient.post(`${SUPERADMIN_ENDPOINTS.plans}${id}/activate/`).then(unwrap),
  deactivatePlan: (id) => apiClient.post(`${SUPERADMIN_ENDPOINTS.plans}${id}/deactivate/`).then(unwrap),

  // ── Company Plans (subscriptions) ────────────────────────────
  assignPlanPending: (companyId, payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companyAssignPlanPending(companyId),  payload).then(unwrap),
  completeTransaction: (companyId, transactionId) => apiClient.post(SUPERADMIN_ENDPOINTS.companyCompleteTransaction(companyId),{ transaction_id: transactionId }).then(unwrap),
  fetchCompanyTransactions: (companyId) => apiClient.get(`/superadmin/companies/${companyId}/transactions/`).then(unwrap),

  // ── Modules ──────────────────────────────────────────────────
  listModules: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.modules, { params }).then(unwrap),
  getModule: (id) => apiClient.get(`${SUPERADMIN_ENDPOINTS.modules}${id}/`).then(unwrap),
  updateModule: (id, payload) => apiClient.patch(`${SUPERADMIN_ENDPOINTS.modules}${id}/`, payload).then(unwrap),
  // ── Employees ────────────────────────────────────────────────
  listEmployees: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.employees, { params }).then(unwrap),
  getEmployee: (id) => apiClient.get(`${SUPERADMIN_ENDPOINTS.employees}${id}/`).then(unwrap),
  createEmployee: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeCreate, payload).then(unwrap),
  updateEmployee: (id, payload) => apiClient.patch(`${SUPERADMIN_ENDPOINTS.employees}${id}/`, payload).then(unwrap),
  deactivateEmployee: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeDeactivate(id)).then(unwrap),
  activateEmployee: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeActivate(id)).then(unwrap),
  assignEmployeeRole: (id, roleId) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeAssignRole(id), { role_id: roleId }).then(unwrap),
  removeEmployeeRole: (id, roleId) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeRemoveRole(id), { role_id: roleId }).then(unwrap),
  resendEmployeeInvitation: (employeeId) => apiClient.post(`/superadmin/employees/${employeeId}/resend_invitation/`).then(unwrap),
}
