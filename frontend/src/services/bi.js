import apiClient, { unwrap } from './apiClient.js'
import { BI_ENDPOINTS } from '../utils/constants.js'

/**
 * Executive BI API service.
 * Single source of truth for all Sprint 6 BI dashboard calls.
 * Reuses the shared apiClient + unwrap pattern.
 */
export const biApi = {
  // ── Executive summary ───────────────────────────────────────
  getSummary: (params) => apiClient.get(BI_ENDPOINTS.summary, { params }).then(unwrap),

  // ── Governance analytics ────────────────────────────────────
  getSales: (params) => apiClient.get(BI_ENDPOINTS.sales, { params }).then(unwrap),
  getPurchase: (params) => apiClient.get(BI_ENDPOINTS.purchase, { params }).then(unwrap),
  getCustomers: (params) => apiClient.get(BI_ENDPOINTS.customer, { params }).then(unwrap),
  getInventory: (params) => apiClient.get(BI_ENDPOINTS.inventory, { params }).then(unwrap),
  getFinance: (params) => apiClient.get(BI_ENDPOINTS.finance, { params }).then(unwrap),

  // ── Alerts & AI insights ────────────────────────────────────
  getAlerts: (params) => apiClient.get(BI_ENDPOINTS.alerts, { params }).then(unwrap),
  getInsights: (params) => apiClient.get(BI_ENDPOINTS.insights, { params }).then(unwrap),

  // ── Executive system health ─────────────────────────────────
  getHealth: () => apiClient.get(BI_ENDPOINTS.health).then(unwrap),
}
