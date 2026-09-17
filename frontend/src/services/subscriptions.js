import apiClient, { unwrap } from './apiClient.js'

export const subscriptionApi = {
  getMySubscription: () =>
    apiClient.get('/subscriptions/my/').then(unwrap),

  getMyUsage: () =>
    apiClient.get('/subscriptions/my-usage/').then(unwrap),

  getMyTransactions: () =>
    apiClient.get('/subscriptions/my-transactions/').then(unwrap),
}
