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

  // ── Company Plans (subscriptions) ────────────────────────────
  assignPlanPending: (companyId, payload) => apiClient.post(SUPERADMIN_ENDPOINTS.companyAssignPlanPending(companyId),  payload).then(unwrap),
  completeTransaction: (companyId, transactionId) => apiClient.post(SUPERADMIN_ENDPOINTS.companyCompleteTransaction(companyId),{ transaction_id: transactionId }).then(unwrap),
  fetchCompanyTransactions: (companyId) => apiClient.get(`/superadmin/companies/${companyId}/transactions/`).then(unwrap),

  // ── Employees ────────────────────────────────────────────────
  listEmployees: (params) => apiClient.get(SUPERADMIN_ENDPOINTS.employees, { params }).then(unwrap),
  createEmployee: (payload) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeCreate, payload).then(unwrap),
  updateEmployee: (id, payload) => apiClient.patch(`${SUPERADMIN_ENDPOINTS.employees}${id}/`, payload).then(unwrap),
  deactivateEmployee: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeDeactivate(id)).then(unwrap),
  activateEmployee: (id) => apiClient.post(SUPERADMIN_ENDPOINTS.employeeActivate(id)).then(unwrap),
  resendEmployeeInvitation: (employeeId) => apiClient.post(`/superadmin/employees/${employeeId}/resend_invitation/`).then(unwrap),
}
