import apiClient, { unwrap } from './apiClient.js'
import { SUPERADMIN_ENDPOINTS } from '../utils/constants.js'

export const subscriptionApi = {
  getMySubscription: () =>
    apiClient.get('/api/v1/subscriptions/my/').then(unwrap),

  getMyUsage: () =>
    apiClient.get('/api/v1/subscriptions/my-usage/').then(unwrap),

  getMyModules: () =>
    apiClient.get('/api/v1/subscriptions/my-modules/').then(unwrap),

  listPlans: (params) =>
    apiClient.get('/api/v1/subscriptions/plans/', { params }).then(unwrap),

  assignPlan: (payload) =>
    apiClient.post('/api/v1/subscriptions/assign/', payload).then(unwrap),

  upgradePlan: (payload) =>
    apiClient.post('/api/v1/subscriptions/upgrade/', payload).then(unwrap),

  downgradePlan: (payload) =>
    apiClient.post('/api/v1/subscriptions/downgrade/', payload).then(unwrap),

  renewPlan: (payload) =>
    apiClient.post('/api/v1/subscriptions/renew/', payload).then(unwrap),

  cancelPlan: (payload) =>
    apiClient.post('/api/v1/subscriptions/cancel/', payload).then(unwrap),

  resetUsage: (payload) =>
    apiClient.post('/api/v1/subscriptions/reset-usage/', payload).then(unwrap),

  listModules: (params) =>
    apiClient.get('/api/v1/subscriptions/modules/', { params }).then(unwrap),

  enableModule: (payload) =>
    apiClient.post('/api/v1/subscriptions/modules/enable/', payload).then(unwrap),

  disableModule: (payload) =>
    apiClient.post('/api/v1/subscriptions/modules/disable/', payload).then(unwrap),

  getCompanyPlanHistory: (companyId) =>
    apiClient.get(`${SUPERADMIN_ENDPOINTS.companyPlanHistory(companyId)}`).then(unwrap),
}
