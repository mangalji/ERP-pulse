import apiClient, { unwrap } from './apiClient.js'
import { AI_ENDPOINTS } from '../utils/constants.js'

export const aiApi = {
  chat: (message, conversationId = null) =>
    apiClient.post(AI_ENDPOINTS.chat, { message, conversation_id: conversationId }).then(unwrap),

  getHistory: () => apiClient.get(AI_ENDPOINTS.history).then(unwrap),

  getMessages: (conversationId) =>
    apiClient.get(AI_ENDPOINTS.messages(conversationId)).then(unwrap),
}
