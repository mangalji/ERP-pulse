import apiClient, { unwrap } from './apiClient.js'
import { DASHBOARD_ENDPOINTS } from '../utils/constants.js'

export const dashboardApi = {
  getSummary: () => apiClient.get(DASHBOARD_ENDPOINTS.summary).then(unwrap),
  getRecentCustomers: () => apiClient.get(DASHBOARD_ENDPOINTS.recentCustomers).then(unwrap),
  getRecentSalesOrders: () => apiClient.get(DASHBOARD_ENDPOINTS.recentSalesOrders).then(unwrap),
  getRecentInvoices: () => apiClient.get(DASHBOARD_ENDPOINTS.recentInvoices).then(unwrap),
}
