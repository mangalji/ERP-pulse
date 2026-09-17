import apiClient, { unwrap } from './apiClient.js'
import { INVITATION_ENDPOINTS } from '../utils/constants.js'

export const invitationApi = {
  validate: (token) =>
    apiClient.get(INVITATION_ENDPOINTS.validate, { params: { token } }).then(unwrap),

  requestOtp: (payload) =>
    apiClient.post(INVITATION_ENDPOINTS.requestOtp, payload).then(unwrap),

  accept: (payload) =>
    apiClient.post(INVITATION_ENDPOINTS.accept, payload).then(unwrap),

}
