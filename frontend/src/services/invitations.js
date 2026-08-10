import apiClient, { unwrap } from './apiClient.js'
import { INVITATION_ENDPOINTS } from '../utils/constants.js'

export const invitationApi = {
  create: (payload) =>
    apiClient.post(INVITATION_ENDPOINTS.create, payload).then(unwrap),

  list: (params) =>
    apiClient.get(INVITATION_ENDPOINTS.list, { params }).then(unwrap),

  get: (id) =>
    apiClient.get(INVITATION_ENDPOINTS.detail(id)).then(unwrap),

  send: (id) =>
    apiClient.post(INVITATION_ENDPOINTS.send(id)).then(unwrap),

  resend: (id) =>
    apiClient.post(INVITATION_ENDPOINTS.resend(id)).then(unwrap),

  validate: (token) =>
    apiClient.get(INVITATION_ENDPOINTS.validate, { params: { token } }).then(unwrap),

  requestOtp: (payload) =>
    apiClient.post(INVITATION_ENDPOINTS.requestOtp, payload).then(unwrap),

  accept: (payload) =>
    apiClient.post(INVITATION_ENDPOINTS.accept, payload).then(unwrap),

  publicResend: (email) =>
    apiClient.post(INVITATION_ENDPOINTS.publicResend, { email }).then(unwrap),
}
