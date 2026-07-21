import apiClient, { unwrap } from './apiClient.js'
import { MONITORING_ENDPOINTS } from '../utils/constants.js'

export const monitoringApi = {
  getHealth: () => apiClient.get(MONITORING_ENDPOINTS.health).then(unwrap),
  getErrors: (limit = 50) =>
    apiClient.get(MONITORING_ENDPOINTS.errors, { params: { limit } }).then(unwrap),
  getApiUsage: (hours = 24) =>
    apiClient.get(MONITORING_ENDPOINTS.apiUsage, { params: { hours } }).then(unwrap),
}
