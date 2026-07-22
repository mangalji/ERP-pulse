import apiClient, { unwrap } from './apiClient.js'
import { REPORTS_ENDPOINTS } from '../utils/constants.js'

export const reportsApi = {
  getSalesTrend: (months = 6) =>
    apiClient.get(REPORTS_ENDPOINTS.salesTrend, { params: { months } }).then(unwrap),
}
