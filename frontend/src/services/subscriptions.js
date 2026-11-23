import apiClient, { unwrap } from './apiClient.js'

export const subscriptionApi = {
  getMySubscription: () =>
    apiClient.get('/subscriptions/my/').then(unwrap),

  getMyTransactions: () =>
    apiClient.get('/subscriptions/my-transactions/').then(unwrap),
}
