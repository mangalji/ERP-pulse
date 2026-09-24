import apiClient, { unwrap } from './apiClient.js'

const AI_ENDPOINTS = {
  config: '/ocr/ai/config/',
  test: '/ocr/ai/config/test/',
  disconnect: '/ocr/ai/config/disconnect/',
  providers: '/ocr/ai/providers/',
}

export const aiIntegrationApi = {
  getConfig: () => apiClient.get(AI_ENDPOINTS.config).then(unwrap),

  getProviders: () => apiClient.get(AI_ENDPOINTS.providers).then(unwrap),

  test: (payload) =>
    apiClient.post(AI_ENDPOINTS.test, payload).then(unwrap),

  connect: (payload) =>
    apiClient.post(AI_ENDPOINTS.config, payload).then(unwrap),

  disconnect: () =>
    apiClient.post(AI_ENDPOINTS.disconnect).then(unwrap),
}