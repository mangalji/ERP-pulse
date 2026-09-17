import apiClient, { unwrap } from './apiClient.js'
import { DASHBOARD_ENDPOINTS } from '../utils/constants.js'

export const dashboardApi = {
  getSummary: () => apiClient.get(DASHBOARD_ENDPOINTS.summary).then(unwrap),
  getRecentInvoices: () => apiClient.get(DASHBOARD_ENDPOINTS.recentInvoices).then(unwrap),
  getExecutiveSummary: () => apiClient.get(DASHBOARD_ENDPOINTS.executiveSummary).then(unwrap),
  getActivityFeed: (limit = 10) => apiClient.get(DASHBOARD_ENDPOINTS.activityFeed, { params: { limit } }).then(unwrap),
}
