import apiClient, { unwrap } from './apiClient.js'
import { DEMO_ENDPOINTS } from '../utils/constants.js'

export const demoApi = {
  submit: (payload) =>
    apiClient.post(DEMO_ENDPOINTS.submit, payload).then(unwrap),

  list: (params) =>
    apiClient.get(DEMO_ENDPOINTS.list, { params }).then(unwrap),

  get: (id) =>
    apiClient.get(DEMO_ENDPOINTS.detail(id)).then(unwrap),

  convert: (id, payload) =>
    apiClient.post(DEMO_ENDPOINTS.convert(id), payload).then(unwrap),

  approve: (id, notes) =>
    apiClient.post(DEMO_ENDPOINTS.approve(id), { notes }).then(unwrap),

  reject: (id, notes) =>
    apiClient.post(DEMO_ENDPOINTS.reject(id), { notes }).then(unwrap),

  assign: (id, userId, notes) =>
    apiClient.post(DEMO_ENDPOINTS.assign(id), { user_id: userId, notes }).then(unwrap),
}
