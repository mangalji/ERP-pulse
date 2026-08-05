import apiClient, { unwrap } from './apiClient.js'
import { REPORTS_ENGINE_ENDPOINTS as E } from '../utils/constants.js'

/**
 * Enterprise Reporting Engine API service.
 * Single source of truth for all Sprint 7 report calls.
 * Reuses the shared apiClient + unwrap pattern. Groups:
 *   templates, reports, history, schedules
 */

export const reportsEngineApi = {
  // ── Templates ─────────────────────────────────────────────────
  templates: {
    list: (params) => apiClient.get(E.templates, { params }).then(unwrap),
    get: (id) => apiClient.get(E.template(id)).then(unwrap),
    create: (data) => apiClient.post(E.templates, data).then(unwrap),
    update: (id, data) => apiClient.patch(E.template(id), data).then(unwrap),
    remove: (id) => apiClient.delete(E.template(id)).then(unwrap),
    types: () => apiClient.get(E.templateTypes).then(unwrap),
  },

  // ── Reports (generate / preview / email) ──────────────────────
  reports: {
    generate: (data) => apiClient.post(E.generate, data).then(unwrap),
    preview: (data) => apiClient.post(E.preview, data).then(unwrap),
    email: (data) => apiClient.post(E.email, data).then(unwrap),
  },

  // ── History ───────────────────────────────────────────────────
  history: {
    list: (params) => apiClient.get(E.history, { params }).then(unwrap),
    metadata: (id) => apiClient.get(E.historyMetadata(id)).then(unwrap),
    downloadUrl: (id) => E.historyDownload(id),
    download: (id) =>
      apiClient.get(E.historyDownload(id), { responseType: 'blob' }).then((res) => res.data),
  },

  // ── Schedules ─────────────────────────────────────────────────
  schedules: {
    list: (params) => apiClient.get(E.schedules, { params }).then(unwrap),
    get: (id) => apiClient.get(E.schedule(id)).then(unwrap),
    create: (data) => apiClient.post(E.schedules, data).then(unwrap),
    update: (id, data) => apiClient.patch(E.schedule(id), data).then(unwrap),
    remove: (id) => apiClient.delete(E.schedule(id)).then(unwrap),
    activate: (id) => apiClient.post(E.scheduleActivate(id)).then(unwrap),
    deactivate: (id) => apiClient.post(E.scheduleDeactivate(id)).then(unwrap),
    runNow: (id) => apiClient.post(E.scheduleRunNow(id)).then(unwrap),
  },
}

export default reportsEngineApi
