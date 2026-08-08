import apiClient, { unwrap } from './apiClient.js'
import { SUPERADMIN_ENDPOINTS } from '../utils/constants.js'

export const subscriptionApi = {
  getMySubscription: () =>
    apiClient.get('/subscriptions/my/').then(unwrap),

  getMyUsage: () =>
    apiClient.get('/subscriptions/my-usage/').then(unwrap),

  getMyModules: () =>
    apiClient.get('/subscriptions/my-modules/').then(unwrap),

  getMyTransactions: () =>
    apiClient.get('/subscriptions/my-transactions/').then(unwrap),

  listPlans: (params) =>
    apiClient.get('/subscriptions/plans/', { params }).then(unwrap),

  assignPlan: (payload) =>
    apiClient.post('/subscriptions/assign/', payload).then(unwrap),

  upgradePlan: (payload) =>
    apiClient.post('/subscriptions/upgrade/', payload).then(unwrap),

  downgradePlan: (payload) =>
    apiClient.post('/subscriptions/downgrade/', payload).then(unwrap),

  renewPlan: (payload) =>
    apiClient.post('/subscriptions/renew/', payload).then(unwrap),

  cancelPlan: (payload) =>
    apiClient.post('/subscriptions/cancel/', payload).then(unwrap),

  resetUsage: (payload) =>
    apiClient.post('/subscriptions/reset-usage/', payload).then(unwrap),

  listModules: (params) =>
    apiClient.get('/subscriptions/modules/', { params }).then(unwrap),

  enableModule: (payload) =>
    apiClient.post('/subscriptions/modules/enable/', payload).then(unwrap),

  disableModule: (payload) =>
    apiClient.post('/subscriptions/modules/disable/', payload).then(unwrap),

  getCompanyPlanHistory: (companyId) =>
    apiClient.get(`${SUPERADMIN_ENDPOINTS.companyPlanHistory(companyId)}`).then(unwrap),
}
