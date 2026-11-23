import apiClient from '../services/apiClient.js'

export function persistNotificationToast(message, link) {
  return apiClient.post('/notifications/', {
    message,
    link,
    activity_type: 'manual',
  }).then(() => window.dispatchEvent(new Event('notifications-changed')))
}
