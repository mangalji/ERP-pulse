import apiClient, { unwrap } from './apiClient.js'

const root = '/email/integrations/'
export const emailIntegrationApi = {
  list: () => apiClient.get(root).then(unwrap),
  health: () => apiClient.get('/email/processing-health/').then(unwrap),
  connect: (payload) => apiClient.post(root, payload).then(unwrap),
  activate: (id) => apiClient.post(`${root}${id}/activate/`).then(unwrap),
  configureInitialSync: (id, payload) => apiClient.patch(`${root}${id}/initial-sync/`, payload).then(unwrap),
  checkSyncReadiness: (id) => apiClient.post(`${root}${id}/sync-readiness/`).then(unwrap),
  pause: (id) => apiClient.post(`${root}${id}/pause/`).then(unwrap),
  resume: (id) => apiClient.post(`${root}${id}/resume/`).then(unwrap),
  disconnect: (id) => apiClient.post(`${root}${id}/disconnect/`).then(unwrap),
  reconnect: (id) => apiClient.post(`${root}${id}/reconnect/`).then(unwrap),
}
